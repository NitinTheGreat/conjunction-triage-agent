"""Statistical profile of the ingested benchmark.

Writes ``processed/profile.json`` and prints a readable summary.

**Censoring is respected everywhere.** ``pc`` is censored at 1e-10: that value is a
bound, not a measurement. Every ``pc`` statistic here is computed over the *uncensored*
population only, and the censored count is always reported alongside it. Mixing the two
would put a large fraction of records at an identical fictitious value and quietly
distort every distribution statistic.

Operates batch-by-batch; no file is ever fully resident. ``dataset/`` is not read at all
-- this works from the ingested store.

    python scripts/profile_dataset.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import settings  # noqa: E402
from core.schema import PC_FLOOR  # noqa: E402

#: Equatorial radius, km (WGS-84). Altitude here is |r| - Re, a spherical approximation
#: adequate for bucketing orbital regimes; it is NOT a geodetic altitude.
EARTH_RADIUS_KM = 6378.137

#: Operational manoeuvre-decision threshold widely used by satellite operators.
ACTION_THRESHOLD_PC = 1e-4

BATCH_SIZE = 100_000

SOURCES = ("spherical", "sfsh")

#: Columns pulled per batch. Reading a subset is what keeps memory flat.
COLUMNS = (
    ["pc", "pc_is_floored", "miss_distance_km", "relative_speed_kms",
     "mahalanobis_distance", "dilution"]
    + [f"obj{i}_{axis}" for i in (1, 2) for axis in ("x", "y", "z")]
    + [f"obj{i}_c_{e}" for i in (1, 2) for e in ("11", "12", "13", "22", "23", "33")]
    + [f"obj{i}_hbr_m" for i in (1, 2)]
)


def quantiles(values: np.ndarray) -> dict[str, float]:
    """Min / quartiles / median / max, or an explicit empty marker."""
    values = values[np.isfinite(values)]
    if values.size == 0:
        return {"count": 0, "note": "no finite values"}
    q1, median, q3 = np.percentile(values, [25, 50, 75])
    return {
        "count": int(values.size),
        "min": float(values.min()),
        "q1": float(q1),
        "median": float(median),
        "q3": float(q3),
        "max": float(values.max()),
        "mean": float(values.mean()),
    }


def decade_histogram(values: np.ndarray) -> dict[str, int]:
    """Count values per power-of-ten decade, e.g. '1e-09..1e-08'."""
    values = values[np.isfinite(values) & (values > 0)]
    if values.size == 0:
        return {}
    exponents = np.floor(np.log10(values)).astype(int)
    histogram: dict[str, int] = {}
    for exponent, count in zip(*np.unique(exponents, return_counts=True)):
        histogram[f"1e{exponent:+03d}..1e{exponent + 1:+03d}"] = int(count)
    return histogram


def largest_eigenvalues(batch: dict[str, np.ndarray], index: int) -> np.ndarray:
    """Largest eigenvalue of every covariance in the batch, vectorised.

    ``eigvalsh`` accepts a stacked (N, 3, 3) array, so this is one call rather than N.
    """
    c11 = batch[f"obj{index}_c_11"]
    c12 = batch[f"obj{index}_c_12"]
    c13 = batch[f"obj{index}_c_13"]
    c22 = batch[f"obj{index}_c_22"]
    c23 = batch[f"obj{index}_c_23"]
    c33 = batch[f"obj{index}_c_33"]
    stacked = np.empty((c11.size, 3, 3), dtype=np.float64)
    stacked[:, 0, 0] = c11
    stacked[:, 0, 1] = stacked[:, 1, 0] = c12
    stacked[:, 0, 2] = stacked[:, 2, 0] = c13
    stacked[:, 1, 1] = c22
    stacked[:, 1, 2] = stacked[:, 2, 1] = c23
    stacked[:, 2, 2] = c33
    finite = np.isfinite(stacked).all(axis=(1, 2))
    result = np.full(c11.size, np.nan)
    if finite.any():
        result[finite] = np.linalg.eigvalsh(stacked[finite])[:, -1]
    return result


def profile_source(key: str) -> dict[str, Any]:
    """Profile one ingested file."""
    path = settings.PROCESSED_DIR / f"{key}.parquet"
    if not path.is_file():
        raise FileNotFoundError(f"{path}; run scripts/ingest.py first")

    parquet_file = pq.ParquetFile(path)
    available = set(parquet_file.schema_arrow.names)
    columns = [c for c in COLUMNS if c in available]

    pc_all: list[np.ndarray] = []
    floored_all: list[np.ndarray] = []
    miss: list[np.ndarray] = []
    speed: list[np.ndarray] = []
    mahalanobis: list[np.ndarray] = []
    dilution: list[np.ndarray] = []
    altitudes: dict[int, list[np.ndarray]] = {1: [], 2: []}
    max_eigen: dict[int, list[np.ndarray]] = {1: [], 2: []}
    hbr_null = {1: 0, 2: 0}
    null_counts: dict[str, int] = {c: 0 for c in columns}
    total = 0

    for record_batch in parquet_file.iter_batches(batch_size=BATCH_SIZE, columns=columns):
        data = {
            name: np.asarray(record_batch.column(name).to_pandas(), dtype=object)
            if name == "pc_is_floored"
            else record_batch.column(name).to_numpy(zero_copy_only=False)
            for name in columns
        }
        total += record_batch.num_rows

        for name in columns:
            column = record_batch.column(name)
            null_counts[name] += column.null_count

        pc_all.append(np.asarray(data["pc"], dtype=np.float64))
        floored_all.append(np.asarray(data["pc_is_floored"], dtype=bool))
        miss.append(np.asarray(data["miss_distance_km"], dtype=np.float64))
        speed.append(np.asarray(data["relative_speed_kms"], dtype=np.float64))
        mahalanobis.append(np.asarray(data["mahalanobis_distance"], dtype=np.float64))
        dilution.append(np.asarray(data["dilution"], dtype=np.float64))

        for index in (1, 2):
            x = np.asarray(data[f"obj{index}_x"], dtype=np.float64)
            y = np.asarray(data[f"obj{index}_y"], dtype=np.float64)
            z = np.asarray(data[f"obj{index}_z"], dtype=np.float64)
            altitudes[index].append(np.sqrt(x * x + y * y + z * z) - EARTH_RADIUS_KM)
            max_eigen[index].append(largest_eigenvalues(data, index))
            if f"obj{index}_hbr_m" in data:
                hbr_null[index] += int(
                    np.isnan(np.asarray(data[f"obj{index}_hbr_m"], dtype=np.float64)).sum()
                )

    pc = np.concatenate(pc_all)
    floored = np.concatenate(floored_all)
    pc_missing = np.isnan(pc)

    censored = int((floored & ~pc_missing).sum())
    uncensored_mask = (~floored) & (~pc_missing)
    uncensored = pc[uncensored_mask]

    altitude_all = np.concatenate([np.concatenate(altitudes[1]), np.concatenate(altitudes[2])])
    eigen_all = np.concatenate([np.concatenate(max_eigen[1]), np.concatenate(max_eigen[2])])

    dilution_values = np.concatenate(dilution)
    dilution_counts: dict[str, int] = {}
    for value in np.unique(dilution_values[~np.isnan(dilution_values)]):
        dilution_counts[str(value)] = int((dilution_values == value).sum())
    dilution_counts["NULL"] = int(np.isnan(dilution_values).sum())

    altitude_bands = {
        "<200 km (decaying)": int((altitude_all < 200).sum()),
        "200-500 km": int(((altitude_all >= 200) & (altitude_all < 500)).sum()),
        "500-800 km": int(((altitude_all >= 500) & (altitude_all < 800)).sum()),
        "800-1200 km": int(((altitude_all >= 800) & (altitude_all < 1200)).sum()),
        "1200-2000 km (upper LEO)": int(((altitude_all >= 1200) & (altitude_all < 2000)).sum()),
        "2000-35000 km (MEO)": int(((altitude_all >= 2000) & (altitude_all < 35000)).sum()),
        ">=35000 km (GEO and beyond)": int((altitude_all >= 35000).sum()),
    }

    return {
        "source": key,
        "events": total,
        "pc": {
            "censored_at_floor": censored,
            "censored_pct": round(100 * censored / max(total, 1), 3),
            "uncensored": int(uncensored.size),
            "uncensored_pct": round(100 * uncensored.size / max(total, 1), 3),
            "null": int(pc_missing.sum()),
            "floor": PC_FLOOR,
            "uncensored_stats": quantiles(uncensored),
            "uncensored_decades": decade_histogram(uncensored),
            "note": (
                "All pc statistics above are over the UNCENSORED population only. "
                "Censored records sit at the 1e-10 floor and are bounds, not values."
            ),
        },
        "operational_threshold": {
            "threshold": ACTION_THRESHOLD_PC,
            "events_above": int((uncensored >= ACTION_THRESHOLD_PC).sum()),
            "events_above_pct_of_total": round(
                100 * int((uncensored >= ACTION_THRESHOLD_PC).sum()) / max(total, 1), 6
            ),
        },
        "miss_distance_km": quantiles(np.concatenate(miss)),
        "relative_speed_kms": quantiles(np.concatenate(speed)),
        "mahalanobis_distance": quantiles(np.concatenate(mahalanobis)),
        "dilution_values": dilution_counts,
        "altitude_km": {
            "stats": quantiles(altitude_all),
            "bands_object_slots": altitude_bands,
            "note": "spherical |r| - 6378.137 km, both objects pooled; not geodetic",
        },
        "covariance_largest_eigenvalue_km2": {
            "stats": quantiles(eigen_all),
            "decades": decade_histogram(eigen_all),
        },
        "hbr_null_object_slots": hbr_null[1] + hbr_null[2],
        "null_counts": {k: v for k, v in null_counts.items() if v},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=SOURCES)
    args = parser.parse_args()

    keys = [args.source] if args.source else list(SOURCES)
    profiles = {key: profile_source(key) for key in keys}

    destination = settings.PROCESSED_DIR / "profile.json"
    destination.write_text(json.dumps(profiles, indent=2), encoding="utf-8")

    for key, profile in profiles.items():
        pc = profile["pc"]
        print(f"\n=== {key}: {profile['events']:,} events ===")
        print(
            f"  pc: {pc['censored_at_floor']:,} censored ({pc['censored_pct']}%), "
            f"{pc['uncensored']:,} uncensored ({pc['uncensored_pct']}%), "
            f"{pc['null']:,} null"
        )
        stats = pc["uncensored_stats"]
        if stats.get("count"):
            print(
                f"  uncensored pc: min {stats['min']:.3e}, median {stats['median']:.3e}, "
                f"max {stats['max']:.3e}"
            )
        threshold = profile["operational_threshold"]
        print(
            f"  pc >= {threshold['threshold']:.0e}: {threshold['events_above']:,} events "
            f"({threshold['events_above_pct_of_total']}% of file)"
        )
        for name in ("miss_distance_km", "relative_speed_kms", "mahalanobis_distance"):
            s = profile[name]
            if s.get("count"):
                print(
                    f"  {name}: min {s['min']:.4g}, q1 {s['q1']:.4g}, "
                    f"median {s['median']:.4g}, q3 {s['q3']:.4g}, max {s['max']:.4g}"
                )
        print(f"  dilution: {profile['dilution_values']}")
        print(f"  altitude bands: {profile['altitude_km']['bands_object_slots']}")

    print(f"\n-> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
