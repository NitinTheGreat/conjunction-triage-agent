"""Audit every feature individually: does it read the future, and do the splits agree?

Two independent questions, asked of all 56 columns rather than of the two the audit named.

**Causality.** Determined empirically, not by reading the SQL: the eligibility cohort is
pinned, post-cutoff rows are mutated three ways, and any column that moves is reading data
unavailable at prediction time. A column can only be cleared by surviving the mutation.

**Cross-split comparability.** A feature whose train and test ranges are *disjoint* is worse
than merely leaking. Any tree that splits on it sends every test point into a region it never
trained on, and the model's split-to-split behaviour is not interpretable at all.

    python scripts/audit_features.py
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tests"))

from core.config import settings  # noqa: E402
from core.features import FEATURE_COLUMNS, build_dataset  # noqa: E402
from core.features_causal import (  # noqa: E402
    FEATURE_COLUMNS_CAUSAL,
    LEAKING_COLUMNS,
    build_dataset_causal,
)
from test_causal_features import (  # noqa: E402
    MUTATIONS,
    NOISE_TOLERANCE,
    _build,
    _mutate_everything,
    _reading_from,
    _relative_change,
)

COHORT_SIZE = 400


def _peak_memory_mb() -> float:
    import psutil

    info = psutil.Process().memory_info()
    return getattr(info, "peak_wset", info.rss) / 1024**2


def causality(root: Path) -> dict[str, dict[str, float]]:
    """Maximum relative movement of every column under every mutation, per module."""
    base = root / "base"
    (base / "kelvins").mkdir(parents=True, exist_ok=True)
    source = settings.PROCESSED_DIR / "kelvins"
    for name in ("cdms_train.parquet", "series_train.parquet"):
        shutil.copy(source / name, base / "kelvins" / name)

    with _reading_from(base):
        eligible = build_dataset("train", eligible_only=True)
    cohort = eligible["series_id"].astype(str).tolist()[:COHORT_SIZE]
    cdms = pd.read_parquet(base / "kelvins" / "cdms_train.parquet")

    scenarios = {**MUTATIONS, "all_three": _mutate_everything}
    movement: dict[str, dict[str, float]] = {"frozen": {}, "causal": {}}
    for label, mutation in scenarios.items():
        directory = root / f"mutated_{label}"
        (directory / "kelvins").mkdir(parents=True, exist_ok=True)
        mutation(cdms).to_parquet(directory / "kelvins" / "cdms_train.parquet")
        shutil.copy(
            base / "kelvins" / "series_train.parquet",
            directory / "kelvins" / "series_train.parquet",
        )
        for module, columns in (("frozen", FEATURE_COLUMNS),
                                ("causal", FEATURE_COLUMNS_CAUSAL)):
            before = _build(module, base, cohort, columns)
            after = _build(module, directory, cohort, columns)
            for column, change in _relative_change(before, after).items():
                movement[module][column] = max(
                    movement[module].get(column, 0.0), change
                )
    return movement


def ranges(frame: pd.DataFrame, columns) -> dict[str, tuple[float, float]]:
    out = {}
    for column in columns:
        if column not in frame.columns:
            continue
        values = frame[column].to_numpy(dtype=np.float64, na_value=np.nan)
        finite = values[np.isfinite(values)]
        out[column] = (
            (float(finite.min()), float(finite.max())) if finite.size else (np.nan, np.nan)
        )
    return out


def overlap(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Fraction of the combined span the two ranges share. 0.0 means disjoint."""
    if not all(np.isfinite(v) for v in (*a, *b)):
        return float("nan")
    low, high = max(a[0], b[0]), min(a[1], b[1])
    union_low, union_high = min(a[0], b[0]), max(a[1], b[1])
    span = union_high - union_low
    if span == 0:
        return 1.0
    return max(0.0, (high - low)) / span


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    started = time.perf_counter()

    root = Path(tempfile.mkdtemp(prefix="feature-audit-"))
    try:
        movement = causality(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    train = build_dataset("train")
    test = build_dataset("test")
    train_ranges = ranges(train, FEATURE_COLUMNS)
    test_ranges = ranges(test, FEATURE_COLUMNS)

    rows: list[dict[str, Any]] = []
    for column in FEATURE_COLUMNS:
        moved = movement["frozen"].get(column, 0.0)
        reads_future = moved > NOISE_TOLERANCE
        a, b = train_ranges.get(column), test_ranges.get(column)
        share = overlap(a, b) if a and b else float("nan")
        disjoint = bool(np.isfinite(share) and share <= 0.0)

        if reads_future and disjoint:
            verdict = "LEAKS AND INCOMPARABLE"
        elif reads_future:
            verdict = "LEAKS"
        elif disjoint:
            verdict = "INCOMPARABLE ACROSS SPLITS"
        else:
            verdict = "ok"

        rows.append({
            "feature": column,
            "computed_over": "full sequence" if reads_future else "visible prefix",
            "max_relative_movement": moved,
            "train_range": a, "test_range": b,
            "range_overlap": share,
            "in_causal_module": column in FEATURE_COLUMNS_CAUSAL,
            "verdict": verdict,
        })

    frame = pd.DataFrame(rows)
    flagged = frame[frame["verdict"] != "ok"]

    print(f"{len(FEATURE_COLUMNS)} features audited by mutation, cohort pinned at "
          f"{COHORT_SIZE} events\n")
    print(f"{'feature':26s} {'computed over':15s} {'train range':26s} "
          f"{'test range':26s} verdict")
    print("-" * 118)
    for row in rows:
        if row["verdict"] == "ok":
            continue
        a, b = row["train_range"], row["test_range"]
        print(f"{row['feature']:26s} {row['computed_over']:15s} "
              f"[{a[0]:>10.4f}, {a[1]:>10.4f}] [{b[0]:>10.4f}, {b[1]:>10.4f}] "
              f"{row['verdict']}")
    if flagged.empty:
        print("  (none)")

    clean = frame[frame["verdict"] == "ok"]
    print(f"\n{len(clean)} of {len(frame)} features clean; {len(flagged)} flagged.")

    # The causal module must show nothing above the noise floor.
    causal_moved = {
        column: value for column, value in movement["causal"].items()
        if value > NOISE_TOLERANCE
    }
    print(f"\ncausal module, columns moving above {NOISE_TOLERANCE:g}: "
          f"{causal_moved or 'none'}")

    report = {
        "features_audited": len(FEATURE_COLUMNS),
        "cohort_size": COHORT_SIZE,
        "noise_tolerance": NOISE_TOLERANCE,
        "method": (
            "Empirical: the eligibility cohort is pinned, post-cutoff rows are mutated "
            "(perturb, delete, add, and all three), and any column moving by more than "
            "the float64 noise floor is reading data unavailable at prediction time."
        ),
        "rows": rows,
        "flagged": flagged["feature"].tolist(),
        "documented_leaking_columns": list(LEAKING_COLUMNS),
        "causal_module_columns_above_noise": causal_moved,
        "elapsed_seconds": round(time.perf_counter() - started, 1),
        "peak_memory_mb": round(_peak_memory_mb(), 1),
    }
    destination = settings.PROCESSED_DIR / "feature_audit.json"
    destination.write_text(json.dumps(report, indent=2, default=float), encoding="utf-8")
    print(f"\npeak memory {report['peak_memory_mb']} MB -> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
