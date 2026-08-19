"""Build a stratified ~2,000-event sample for the Phase 3 visualisation.

Phase 3 cannot render 1.2 M events. This selects a sample that spans the *interesting*
range rather than the typical one, so the visualisation exercises the extremes.

Selection rule (fully deterministic given ``--seed``)
----------------------------------------------------
1. Every ingested event is assigned a **pc class** -- the primary stratum, because
   collision probability is what triage is about, and because censoring makes a naive
   random sample almost entirely floor values:

   ``action`` (pc >= 1e-4), ``near_threshold`` (1e-6 <= pc < 1e-4),
   ``moderate`` (1e-8 <= pc < 1e-6), ``low`` (floor < pc < 1e-8),
   ``censored`` (pc <= 1e-10, a bound not a value), ``null`` (pc not computable).

2. And an **altitude band** from the primary object -- the secondary stratum, so the
   sample spans orbital regimes (this matters for the Phase 5 drag work, where only low
   orbits are meaningfully affected): ``<500``, ``500-800``, ``800-2000``, ``>=2000`` km.

3. Each (source, pc class, altitude band) cell gets a quota. Rare cells -- above all
   ``action`` -- are taken in full up to the cap, so the high-risk tail is never diluted
   away by the floor population. Remaining capacity is spread over the larger cells.

4. Within a cell, rows are ordered by ``miss_distance_km`` and picked at evenly spaced
   positions. That guarantees a miss-distance spread inside every stratum instead of
   relying on chance. The seed only breaks ties and shuffles the leftover allocation.

Writes ``processed/sample_for_viz.parquet`` with a ``stratum`` column, plus
``processed/sample_strata.json`` recording the rule, the seed and every cell count.

    python scripts/sample_for_viz.py --target 2000 --seed 20260818
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import settings  # noqa: E402
from core.schema import PC_FLOOR  # noqa: E402

EARTH_RADIUS_KM = 6378.137
BATCH_SIZE = 100_000
SOURCES = ("spherical", "sfsh")

PC_CLASSES = ("action", "near_threshold", "moderate", "low", "censored", "null")
ALTITUDE_BANDS = ("<500", "500-800", "800-2000", ">=2000")

#: Cells guaranteed to be taken in full first, because they are rare and are exactly
#: what the visualisation needs to show.
PRIORITY_CLASSES = ("action", "near_threshold")


def classify_pc(pc: np.ndarray, floored: np.ndarray) -> np.ndarray:
    """Assign each event to a pc class. Censoring is honoured, not averaged over."""
    out = np.full(pc.shape, "null", dtype=object)
    missing = np.isnan(pc)
    out[floored & ~missing] = "censored"
    live = (~floored) & (~missing)
    out[live & (pc < 1e-8)] = "low"
    out[live & (pc >= 1e-8) & (pc < 1e-6)] = "moderate"
    out[live & (pc >= 1e-6) & (pc < 1e-4)] = "near_threshold"
    out[live & (pc >= 1e-4)] = "action"
    return out


def band_altitude(altitude: np.ndarray) -> np.ndarray:
    out = np.full(altitude.shape, ">=2000", dtype=object)
    out[altitude < 2000] = "800-2000"
    out[altitude < 800] = "500-800"
    out[altitude < 500] = "<500"
    return out


def load_index(key: str) -> pd.DataFrame:
    """Load just the columns needed to stratify. Never the whole table."""
    path = settings.PROCESSED_DIR / f"{key}.parquet"
    if not path.is_file():
        raise FileNotFoundError(f"{path}; run scripts/ingest.py first")

    columns = ["pc", "pc_is_floored", "miss_distance_km", "obj1_x", "obj1_y", "obj1_z"]
    frames = []
    offset = 0
    for batch in pq.ParquetFile(path).iter_batches(batch_size=BATCH_SIZE, columns=columns):
        frame = batch.to_pandas()
        frame["row_index"] = np.arange(offset, offset + len(frame), dtype=np.int64)
        offset += len(frame)
        altitude = np.sqrt(
            frame["obj1_x"] ** 2 + frame["obj1_y"] ** 2 + frame["obj1_z"] ** 2
        ) - EARTH_RADIUS_KM
        frames.append(
            pd.DataFrame(
                {
                    "row_index": frame["row_index"],
                    "pc": frame["pc"].astype("float64"),
                    "floored": frame["pc_is_floored"].fillna(False).astype(bool),
                    "miss_distance_km": frame["miss_distance_km"].astype("float64"),
                    "altitude_km": altitude.astype("float64"),
                }
            )
        )

    index = pd.concat(frames, ignore_index=True)
    index["source"] = key
    index["pc_class"] = classify_pc(index["pc"].to_numpy(), index["floored"].to_numpy())
    index["altitude_band"] = band_altitude(index["altitude_km"].to_numpy())
    index["stratum"] = (
        index["source"] + "|" + index["pc_class"] + "|" + index["altitude_band"]
    )
    return index


def spread_pick(frame: pd.DataFrame, quota: int, rng: np.random.Generator) -> np.ndarray:
    """Pick ``quota`` rows spread evenly across the cell's miss-distance range."""
    if quota >= len(frame):
        return frame["row_index"].to_numpy()
    ordered = frame.sort_values(
        ["miss_distance_km", "row_index"], kind="mergesort"
    ).reset_index(drop=True)
    positions = np.linspace(0, len(ordered) - 1, quota).round().astype(int)
    positions = np.unique(positions)
    # linspace rounding can collapse neighbours; top up at random to hit the quota.
    if positions.size < quota:
        remaining = np.setdiff1d(np.arange(len(ordered)), positions)
        extra = rng.choice(remaining, size=quota - positions.size, replace=False)
        positions = np.union1d(positions, extra)
    return ordered.loc[positions, "row_index"].to_numpy()


def allocate(index: pd.DataFrame, target: int, rng: np.random.Generator) -> dict[str, int]:
    """Give rare, high-value strata their full size first, then spread the rest."""
    sizes = index.groupby("stratum").size().to_dict()
    quotas: dict[str, int] = {}
    remaining = target

    priority = [
        s for s in sizes
        if s.split("|")[1] in PRIORITY_CLASSES
    ]
    cap = max(1, target // max(len(sizes), 1) * 3)
    for stratum in sorted(priority):
        take = min(sizes[stratum], cap, remaining)
        quotas[stratum] = take
        remaining -= take

    others = sorted(s for s in sizes if s not in quotas)
    while remaining > 0 and others:
        share = max(1, remaining // len(others))
        progressed = False
        for stratum in list(others):
            if remaining <= 0:
                break
            room = sizes[stratum] - quotas.get(stratum, 0)
            if room <= 0:
                others.remove(stratum)
                continue
            take = min(share, room, remaining)
            quotas[stratum] = quotas.get(stratum, 0) + take
            remaining -= take
            progressed = progressed or take > 0
        if not progressed:
            break

    return {k: v for k, v in quotas.items() if v > 0}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20260818)
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    index = pd.concat([load_index(key) for key in SOURCES], ignore_index=True)
    quotas = allocate(index, args.target, rng)

    selected: dict[str, list[int]] = {}
    for stratum, quota in quotas.items():
        cell = index[index["stratum"] == stratum]
        selected[stratum] = spread_pick(cell, quota, rng).tolist()

    tables = []
    counts: dict[str, int] = {}
    for key in SOURCES:
        wanted = {
            stratum: rows for stratum, rows in selected.items()
            if stratum.startswith(f"{key}|")
        }
        row_ids = sorted({r for rows in wanted.values() for r in rows})
        if not row_ids:
            continue
        table = pq.read_table(settings.PROCESSED_DIR / f"{key}.parquet")
        picked = table.take(pa.array(row_ids, type=pa.int64()))

        lookup = {}
        for stratum, rows in wanted.items():
            for row in rows:
                lookup[row] = stratum
                counts[stratum] = counts.get(stratum, 0) + 1
        strata_column = pa.array([lookup[r] for r in row_ids], type=pa.string())
        picked = picked.append_column("stratum", strata_column)
        tables.append(picked)

    if not tables:
        raise RuntimeError("no rows selected; refusing to write an empty sample")

    combined = pa.concat_tables(tables, promote_options="default")
    destination = settings.PROCESSED_DIR / "sample_for_viz.parquet"
    pq.write_table(combined, destination, compression="zstd")

    manifest = {
        "target": args.target,
        "selected": combined.num_rows,
        "seed": args.seed,
        "pc_floor": PC_FLOOR,
        "pc_classes": {
            "action": "pc >= 1e-4",
            "near_threshold": "1e-6 <= pc < 1e-4",
            "moderate": "1e-8 <= pc < 1e-6",
            "low": "1e-10 < pc < 1e-8",
            "censored": "pc <= 1e-10 (bound, not a measurement)",
            "null": "pc not computable (non-PSD covariance)",
        },
        "altitude_bands_km": list(ALTITUDE_BANDS),
        "altitude_definition": "|r| of object 1 minus 6378.137 km (spherical, not geodetic)",
        "priority_classes_taken_first": list(PRIORITY_CLASSES),
        "within_cell_rule": "ordered by miss_distance_km, picked at evenly spaced positions",
        "strata_counts": dict(sorted(counts.items())),
        "population_by_stratum": index.groupby("stratum").size().sort_index().to_dict(),
    }
    (settings.PROCESSED_DIR / "sample_strata.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    print(f"selected {combined.num_rows:,} events into {len(counts)} strata (seed {args.seed})")
    for stratum, count in sorted(counts.items()):
        print(f"  {stratum:48s} {count:5d}")
    print(f"-> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
