"""Explanation faithfulness on the held-out test predictions — Phase 7.

Reuses the Phase 6 measurements unchanged; only the split differs. Kept as a separate
entry point so ``scripts/faithfulness.py`` never names the held-out split and the Phase 6
train-only guarantee stays enforceable.

    python scripts/faithfulness_test.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402

from core.config import settings  # noqa: E402
from core.features import build_dataset  # noqa: E402
from faithfulness import build_report  # noqa: E402

SPLIT = "test"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--consistency-sample", type=int, default=100)
    args = parser.parse_args()

    predictions = settings.PROCESSED_DIR / f"agent_predictions_{SPLIT}.parquet"
    if not predictions.is_file():
        raise FileNotFoundError(f"{predictions}; run scripts/run_agent_{SPLIT}.py first")

    # The prediction file deliberately carries no label -- run_agent_test.py must be able
    # to run without ever seeing the answer. Calibration and discrimination need it, so it
    # is joined here, inside the evaluation, after the predictions were made.
    frame = pd.read_parquet(predictions)
    labels = build_dataset(SPLIT)[["series_id", "final_risk"]]
    joined = frame.merge(labels, on="series_id", how="left", validate="one_to_one")
    if joined["final_risk"].isna().any():
        raise RuntimeError(
            f"{int(joined['final_risk'].isna().sum())} predictions have no label"
        )
    labelled = settings.PROCESSED_DIR / f"_agent_predictions_{SPLIT}_labelled.parquet"
    joined.to_parquet(labelled)

    report = build_report(labelled, SPLIT, args.consistency_sample)
    destination = settings.PROCESSED_DIR / f"faithfulness_{SPLIT}.json"
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")

    grounded = report["groundedness"]
    print(
        f"[{SPLIT}] groundedness: {grounded['citations_accurate']:,}/"
        f"{grounded['citations_checked']:,} citations accurate "
        f"({100 * grounded['groundedness_rate']:.2f}%)"
    )
    print(f"  failures: {grounded['failure_categories']}")
    print(
        f"  fully grounded events: {grounded['events_fully_grounded']}/"
        f"{grounded['events_with_citations']} ({grounded['events_fully_grounded_pct']}%)"
    )
    consistency = report["consistency"]
    print(
        f"  consistency: {consistency['claims_uncertainty_shrinking']} shrink-claims, "
        f"{consistency['of_which_data_agrees']} supported "
        f"(accuracy {consistency['shrink_claim_accuracy']})"
    )
    for row in report["calibration"]:
        if row["n"]:
            print(
                f"  {row['confidence']:6s} n={row['n']:5d} collapse-accuracy "
                f"{row['collapse_accuracy']:.4f} MAE {row['mean_abs_risk_error']:.3f}"
            )
    print(f"-> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
