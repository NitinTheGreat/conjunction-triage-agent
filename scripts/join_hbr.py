"""Join hard-body radius onto both objects of every ingested event.

The two answer keys do **not** use the same HBR, and the Users Guide is explicit about
it, so a single naive join by ``catalog_num`` would misrepresent one of them:

* **Spherical** run -- "Use a constant HBR of 0.5 m for probability of collision
  calculation". Every object gets 0.5 m regardless of what the mappings file says.
* **SFSH** run -- "Use HBR values (per-object) as provided in the input mappings file".

Both are recorded, so nothing is lost:

* ``objN_hbr_m``          -- the HBR that actually produced that file's ``prob`` column.
* ``objN_hbr_catalog_m``  -- the per-object value from the mappings file, for every
  source, ``NULL`` when the object is absent from the file.
* ``objN_hbr_source``     -- ``"spherical_default"``, ``"screening_volumes"``, or
  ``"unmatched"``.

Unmatched objects are left ``NULL`` and counted. They are never filled with a default:
a silently substituted HBR would propagate into every later collision-probability
computation as a plausible-looking wrong number.

Idempotent -- safe to re-run. Operates batch-by-batch; no parquet file is ever fully
resident in memory. ``dataset/`` is read-only.

    python scripts/join_hbr.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import settings  # noqa: E402

SCREENING_VOLUMES = "AerospaceIVVDataset_20251009a_Size_ScreeningVolumes.csv"

#: Users Guide, Screening Volume section: "a CSieve run was conducted using a spherical
#: screening volume of 10 km and a default HBR of 0.5m".
SPHERICAL_DEFAULT_HBR_M = 0.5

#: HBR is in **metres**. Confirmed against catalogue 5 (Vanguard 1), a 16.5 cm sphere,
#: whose tabulated HBR is 0.0825 -- exactly its radius in metres.
HBR_UNIT = "m"

#: Rows per batch when rewriting parquet.
BATCH_SIZE = 100_000

ADDED_COLUMNS = [
    (f"obj{i}_{suffix}", kind)
    for i in (1, 2)
    for suffix, kind in (("hbr_catalog_m", pa.float64()), ("hbr_source", pa.string()))
]


def load_hbr_table(path: Path) -> tuple[dict[str, float], dict[str, Any]]:
    """Load catalogue -> HBR (metres), collapsing exact duplicate rows.

    Raises if a catalogue number carries genuinely conflicting HBR values, rather than
    silently picking one.
    """
    if not path.is_file():
        raise FileNotFoundError(path)

    frame = pd.read_csv(path, usecols=["catalog_num", "HBR"], dtype={"catalog_num": "int64", "HBR": "float64"})
    if frame["HBR"].isna().any():
        raise ValueError(f"{path.name}: HBR column contains nulls")

    conflicting = frame.groupby("catalog_num")["HBR"].nunique()
    conflicts = conflicting[conflicting > 1]
    if len(conflicts):
        raise ValueError(
            f"{path.name}: {len(conflicts)} catalogue numbers have conflicting HBR "
            f"values, e.g. {conflicts.index[:5].tolist()}; refusing to guess"
        )

    deduplicated = frame.drop_duplicates(subset="catalog_num")
    lookup = {
        str(int(c)): float(h)
        for c, h in zip(deduplicated["catalog_num"], deduplicated["HBR"])
    }
    stats = {
        "rows": len(frame),
        "unique_catalog_num": len(lookup),
        "exact_duplicate_rows_collapsed": len(frame) - len(lookup),
        "hbr_unit": HBR_UNIT,
        "hbr_min": float(frame["HBR"].min()),
        "hbr_max": float(frame["HBR"].max()),
        "hbr_median": float(frame["HBR"].median()),
    }
    return lookup, stats


def join_file(key: str, lookup: dict[str, float]) -> dict[str, Any]:
    """Rewrite one parquet file with HBR columns populated. Returns match statistics."""
    path = settings.PROCESSED_DIR / f"{key}.parquet"
    if not path.is_file():
        raise FileNotFoundError(f"{path}; run scripts/ingest.py first")

    parquet_file = pq.ParquetFile(path)
    existing = set(parquet_file.schema_arrow.names)
    schema = parquet_file.schema_arrow
    for name, kind in ADDED_COLUMNS:
        if name not in existing:
            schema = schema.append(pa.field(name, kind))

    is_spherical = key == "spherical"
    matched = {1: 0, 2: 0}
    unmatched = {1: 0, 2: 0}
    unmatched_ids: set[str] = set()
    total = 0

    temp = path.with_suffix(".parquet.tmp")
    writer = pq.ParquetWriter(temp, schema, compression="zstd")
    try:
        for batch in parquet_file.iter_batches(batch_size=BATCH_SIZE):
            frame = batch.to_pandas()
            total += len(frame)

            for index in (1, 2):
                catalog = frame[f"obj{index}_catalog_id"].astype("string")
                catalogue_hbr = catalog.map(lookup)

                hit = catalogue_hbr.notna()
                matched[index] += int(hit.sum())
                unmatched[index] += int((~hit).sum())
                unmatched_ids.update(catalog[~hit].dropna().unique().tolist())

                frame[f"obj{index}_hbr_catalog_m"] = catalogue_hbr.astype("float64")

                if is_spherical:
                    # The spherical answer key was produced with a flat 0.5 m HBR.
                    frame[f"obj{index}_hbr_m"] = SPHERICAL_DEFAULT_HBR_M
                    frame[f"obj{index}_hbr_source"] = "spherical_default"
                else:
                    frame[f"obj{index}_hbr_m"] = catalogue_hbr.astype("float64")
                    frame[f"obj{index}_hbr_source"] = pd.Series(
                        ["screening_volumes"] * len(frame), index=frame.index
                    ).where(hit, "unmatched")

            writer.write_table(pa.Table.from_pandas(frame, schema=schema, preserve_index=False))
    finally:
        writer.close()
    temp.replace(path)

    object_slots = 2 * total
    if matched[1] + matched[2] + unmatched[1] + unmatched[2] != object_slots:
        raise RuntimeError(f"{key}: match/miss counts do not sum to {object_slots}")

    return {
        "source": key,
        "events": total,
        "object_slots": object_slots,
        "matched": matched[1] + matched[2],
        "unmatched": unmatched[1] + unmatched[2],
        "matched_pct": round(100 * (matched[1] + matched[2]) / max(object_slots, 1), 4),
        "matched_obj1": matched[1],
        "matched_obj2": matched[2],
        "unmatched_obj1": unmatched[1],
        "unmatched_obj2": unmatched[2],
        "distinct_unmatched_catalog_ids": len(unmatched_ids),
        "unmatched_examples": sorted(unmatched_ids)[:15],
        "hbr_applied": (
            f"constant {SPHERICAL_DEFAULT_HBR_M} m (Users Guide spherical default)"
            if is_spherical
            else "per-object from ScreeningVolumes; unmatched left NULL"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=["spherical", "sfsh"])
    args = parser.parse_args()

    lookup, stats = load_hbr_table(settings.DATASET_DIR / SCREENING_VOLUMES)
    print(
        f"ScreeningVolumes: {stats['rows']:,} rows, "
        f"{stats['unique_catalog_num']:,} unique catalogue numbers "
        f"({stats['exact_duplicate_rows_collapsed']} exact duplicates collapsed), "
        f"HBR {stats['hbr_min']}-{stats['hbr_max']} {HBR_UNIT}"
    )

    keys = [args.source] if args.source else ["spherical", "sfsh"]
    summaries = [join_file(key, lookup) for key in keys]
    for summary in summaries:
        print(
            f"  [{summary['source']}] {summary['events']:,} events, "
            f"{summary['matched']:,}/{summary['object_slots']:,} object slots matched "
            f"({summary['matched_pct']}%), {summary['unmatched']:,} unmatched across "
            f"{summary['distinct_unmatched_catalog_ids']} distinct catalogue ids"
        )

    report = {"screening_volumes": stats, "joins": summaries}
    destination = settings.PROCESSED_DIR / "hbr_report.json"
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"-> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
