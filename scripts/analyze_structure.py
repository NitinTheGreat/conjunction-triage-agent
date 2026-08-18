"""Structural analysis of the full IV&V benchmark files.

Answers the questions that determine what research question is answerable at all --
above all, whether a ``conj_id`` ever repeats. If it does, the dataset contains risk
*trajectories* that evolve over time; if not, every row is an isolated snapshot.

Runs over the **full** files in chunks; nothing is sampled and no file is ever loaded
whole. ``dataset/`` is opened read-only. Writes ``processed/structure.json``.

    python scripts/analyze_structure.py
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import settings  # noqa: E402

#: Rows per chunk. 100k x 45 float columns is roughly 36 MB -- comfortably small while
#: keeping the number of chunks (and pandas call overhead) low.
CHUNK_SIZE = 100_000

FILES = {
    "spherical": "IVV_Releasable_Dataset_Spherical_DefaultHBR.csv",
    "sfsh": "IVV_Releasable_Dataset_SFSH_DiscreteHBR.csv",
}

#: Columns needed for structure. Reading a subset is what keeps memory flat.
STRUCTURE_COLUMNS = [
    "run_id", "conj_id", "obj1", "obj2", "met_criteria1", "met_criteria2",
    "epoch", "jdate", "min_range", "Vrel", "prob", "dilution", "mdistance",
]

#: Columns identifying a *physical* conjunction. `conj_id` turns out to be run-local, so
#: it cannot be used to match a conjunction across the two answer keys.
IDENTITY_COLUMNS = ["obj1", "obj2", "epoch", "obj1_filename", "obj2_filename", "jdate"]

#: Days offset between the Unix epoch and the Julian date epoch.
UNIX_EPOCH_JD = 2440587.5


def _peak_memory_mb() -> float:
    import psutil

    process = psutil.Process()
    info = process.memory_info()
    # peak_wset is Windows-only; fall back to current RSS elsewhere.
    return getattr(info, "peak_wset", info.rss) / 1024**2


def scan_file(path: Path) -> dict[str, Any]:
    """One chunked pass collecting everything needed for the structural questions."""
    if not path.is_file():
        raise FileNotFoundError(path)

    conj_ids: list[np.ndarray] = []
    obj1s: list[np.ndarray] = []
    obj2s: list[np.ndarray] = []
    run_counter: Counter = Counter()
    dilution_counter: Counter = Counter()
    epoch_min, epoch_max = None, None
    epoch_days: Counter = Counter()
    null_counts: Counter = Counter()
    obj2_gt_obj1 = 0
    total_rows = 0

    for chunk in pd.read_csv(path, usecols=STRUCTURE_COLUMNS, chunksize=CHUNK_SIZE):
        total_rows += len(chunk)

        conj_ids.append(chunk["conj_id"].to_numpy(dtype=np.int64))
        obj1s.append(chunk["obj1"].to_numpy(dtype=np.int64))
        obj2s.append(chunk["obj2"].to_numpy(dtype=np.int64))

        run_counter.update(chunk["run_id"].value_counts().to_dict())

        # dilution may be NULL -> NaN; count NaN under a distinct key.
        for value, count in chunk["dilution"].value_counts(dropna=False).items():
            key = "NULL" if pd.isna(value) else str(value)
            dilution_counter[key] += int(count)

        for column in STRUCTURE_COLUMNS:
            null_counts[column] += int(chunk[column].isna().sum())

        epochs = chunk["epoch"].astype("string")
        # ISO-like "YYYY-MM-DD HH:MM:SS.ffffff" sorts correctly as text.
        low, high = epochs.min(), epochs.max()
        epoch_min = low if epoch_min is None else min(epoch_min, low)
        epoch_max = high if epoch_max is None else max(epoch_max, high)
        epoch_days.update(epochs.str.slice(0, 10).value_counts().to_dict())

        obj2_gt_obj1 += int((chunk["obj2"] > chunk["obj1"]).sum())

    conj_id = np.concatenate(conj_ids)
    obj1 = np.concatenate(obj1s)
    obj2 = np.concatenate(obj2s)

    unique_conj, conj_counts = np.unique(conj_id, return_counts=True)
    repeated_mask = conj_counts > 1
    repeated_ids = unique_conj[repeated_mask]

    all_objects = np.concatenate([obj1, obj2])
    unique_objects, object_counts = np.unique(all_objects, return_counts=True)

    return {
        "path": path.name,
        "total_rows": total_rows,
        "unique_conj_id": int(unique_conj.size),
        "repeated_conj_id_count": int(repeated_ids.size),
        "rows_in_repeated_conj_ids": int(conj_counts[repeated_mask].sum()),
        "max_rows_per_conj_id": int(conj_counts.max()),
        "conj_id_multiplicity": {
            str(int(k)): int(v)
            for k, v in zip(*np.unique(conj_counts, return_counts=True))
        },
        "unique_run_id": len(run_counter),
        "rows_per_run_id": {str(int(k)): int(v) for k, v in sorted(run_counter.items())},
        "unique_objects": int(unique_objects.size),
        "object_appearance_stats": {
            "min": int(object_counts.min()),
            "max": int(object_counts.max()),
            "median": float(np.median(object_counts)),
            "mean": float(object_counts.mean()),
        },
        "most_common_objects": [
            {"catalog_id": int(o), "appearances": int(c)}
            for o, c in sorted(
                zip(unique_objects, object_counts), key=lambda t: -t[1]
            )[:10]
        ],
        "epoch_min": str(epoch_min),
        "epoch_max": str(epoch_max),
        "rows_per_day": {str(k): int(v) for k, v in sorted(epoch_days.items())},
        "dilution_values": dict(sorted(dilution_counter.items())),
        "null_counts": {k: int(v) for k, v in sorted(null_counts.items()) if v},
        "obj2_greater_than_obj1": obj2_gt_obj1,
        "obj2_greater_than_obj1_pct": round(100 * obj2_gt_obj1 / max(total_rows, 1), 4),
        "_conj_id_array": conj_id,          # kept for cross-file overlap, not serialised
        "_repeated_ids": repeated_ids,      # kept for the duplicate deep-dive
    }


def inspect_repeats(path: Path, repeated_ids: np.ndarray, limit: int = 5) -> dict:
    """For repeated conj_ids, check whether their values actually differ.

    A repeat whose fields are identical is a duplicated record; a repeat whose epoch or
    prob differs is a genuine time series. The distinction decides the research question.
    """
    if repeated_ids.size == 0:
        return {"examined": 0, "note": "no repeated conj_id values"}

    wanted = set(repeated_ids.tolist())
    collected: list[pd.DataFrame] = []
    for chunk in pd.read_csv(
        path,
        usecols=STRUCTURE_COLUMNS + ["c1_11", "c2_11", "local_x1"],
        chunksize=CHUNK_SIZE,
    ):
        hit = chunk[chunk["conj_id"].isin(wanted)]
        if not hit.empty:
            collected.append(hit)
    if not collected:
        return {"examined": 0, "note": "repeated ids not re-found (unexpected)"}

    frame = pd.concat(collected, ignore_index=True)
    varying: Counter = Counter()
    for column in ("epoch", "prob", "min_range", "obj1", "obj2", "c1_11", "mdistance"):
        differing = frame.groupby("conj_id")[column].nunique(dropna=False)
        varying[column] = int((differing > 1).sum())

    examples = []
    for conj in repeated_ids[:limit].tolist():
        rows = frame[frame["conj_id"] == conj]
        examples.append(
            {
                "conj_id": int(conj),
                "rows": len(rows),
                "obj_pairs": [
                    [int(a), int(b)] for a, b in zip(rows["obj1"], rows["obj2"])
                ],
                "epochs": sorted(set(rows["epoch"].astype(str))),
                "probs": sorted({float(p) for p in rows["prob"] if pd.notna(p)}),
                "min_ranges": sorted({round(float(m), 9) for m in rows["min_range"]}),
            }
        )

    return {
        "examined": int(repeated_ids.size),
        "groups_where_column_varies": dict(varying),
        "examples": examples,
    }


def analyse_identity(path: Path) -> tuple[dict[str, Any], set[str]]:
    """Determine what actually identifies a conjunction, and cross-check `jdate`.

    Returns the summary plus the set of ``obj1_obj2_epoch`` keys, used for cross-file
    matching. ``conj_id`` cannot serve that purpose -- it is unique per row and shares
    no values between the two files.
    """
    pair_keys: set[str] = set()
    file_keys: set[str] = set()
    pair_rows = 0
    jd_max_error = 0.0
    jd_errors: list[np.ndarray] = []
    min_range_lo, min_range_hi = np.inf, -np.inf
    criteria_counter: Counter = Counter()

    for chunk in pd.read_csv(
        path, usecols=IDENTITY_COLUMNS + ["min_range", "met_criteria1", "met_criteria2"],
        chunksize=CHUNK_SIZE,
    ):
        pair_rows += len(chunk)
        epoch = chunk["epoch"].astype(str)

        pair_keys.update(
            chunk["obj1"].astype(str) + "_" + chunk["obj2"].astype(str) + "_" + epoch
        )
        file_keys.update(
            chunk["obj1_filename"].astype(str)
            + "_" + chunk["obj2_filename"].astype(str)
            + "_" + epoch
        )

        # jdate cross-check. pandas 3.0 returns datetime64[us] from to_datetime, so the
        # resolution is pinned to ns explicitly before converting to an integer count.
        stamps = pd.to_datetime(epoch, format="mixed").astype("datetime64[ns]")
        julian = stamps.astype("int64") / 86400e9 + UNIX_EPOCH_JD
        errors = (julian - chunk["jdate"]).abs().to_numpy()
        jd_errors.append(errors)
        jd_max_error = max(jd_max_error, float(np.nanmax(errors)))

        min_range_lo = min(min_range_lo, float(chunk["min_range"].min()))
        min_range_hi = max(min_range_hi, float(chunk["min_range"].max()))

        for (a, b), count in chunk.groupby(
            ["met_criteria1", "met_criteria2"]
        ).size().items():
            criteria_counter[f"({int(a)},{int(b)})"] += int(count)

    all_errors = np.concatenate(jd_errors)
    return (
        {
            "rows": pair_rows,
            "unique_obj_pair_epoch": len(pair_keys),
            "duplicate_obj_pair_epoch_rows": pair_rows - len(pair_keys),
            "unique_filename_pair_epoch": len(file_keys),
            "duplicate_filename_pair_epoch_rows": pair_rows - len(file_keys),
            "jdate_vs_epoch_utc_max_error_seconds": round(jd_max_error * 86400, 9),
            "jdate_vs_epoch_utc_median_error_seconds": round(
                float(np.median(all_errors)) * 86400, 9
            ),
            "min_range_km": {"min": min_range_lo, "max": min_range_hi},
            "met_criteria_combinations": dict(sorted(criteria_counter.items())),
        },
        pair_keys,
    )


def main() -> int:
    settings.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    results: dict[str, Any] = {"chunk_size": CHUNK_SIZE, "files": {}}
    arrays: dict[str, np.ndarray] = {}
    pair_key_sets: dict[str, set[str]] = {}

    for key, filename in FILES.items():
        path = settings.DATASET_DIR / filename
        print(f"scanning {filename} ...", flush=True)
        summary = scan_file(path)
        arrays[key] = summary.pop("_conj_id_array")
        repeated_ids = summary.pop("_repeated_ids")

        print(
            f"  {summary['total_rows']:,} rows | "
            f"{summary['unique_conj_id']:,} unique conj_id | "
            f"{summary['repeated_conj_id_count']:,} repeated",
            flush=True,
        )
        summary["repeat_analysis"] = inspect_repeats(path, repeated_ids)
        identity, pair_keys = analyse_identity(path)
        summary["identity"] = identity
        pair_key_sets[key] = pair_keys
        results["files"][key] = summary

    left, right = arrays["spherical"], arrays["sfsh"]
    common = np.intersect1d(np.unique(left), np.unique(right))
    results["conj_id_overlap"] = {
        "spherical_unique": int(np.unique(left).size),
        "sfsh_unique": int(np.unique(right).size),
        "common": int(common.size),
        "only_spherical": int(np.unique(left).size - common.size),
        "only_sfsh": int(np.unique(right).size - common.size),
        "note": (
            "conj_id is run-local: the two files share a single value between them, so "
            "it cannot identify the same physical conjunction across answer keys."
        ),
    }

    sph, sfsh = pair_key_sets["spherical"], pair_key_sets["sfsh"]
    results["physical_overlap_obj_pair_epoch"] = {
        "spherical_unique": len(sph),
        "sfsh_unique": len(sfsh),
        "common": len(sph & sfsh),
        "only_spherical": len(sph - sfsh),
        "only_sfsh": len(sfsh - sph),
    }

    results["elapsed_seconds"] = round(time.perf_counter() - started, 1)
    results["peak_memory_mb"] = round(_peak_memory_mb(), 1)

    destination = settings.PROCESSED_DIR / "structure.json"
    destination.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(
        f"\nwrote {destination} in {results['elapsed_seconds']}s, "
        f"peak memory {results['peak_memory_mb']} MB"
    )
    print(json.dumps(results["physical_overlap_obj_pair_epoch"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
