"""Where the best baseline fails — the specification of what an agent must beat.

Reads ``processed/baseline_predictions.parquet`` (written by ``run_baselines.py`` for the
last validation split) and characterises B1's errors by event property.

This matters more than the headline scores: it says *which* events a reasoning system
would have to get right, and therefore whether there is anything for one to do.

Writes ``processed/error_analysis.json``. Train only — the test set is never read.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import settings  # noqa: E402
from core.evaluation import spearman  # noqa: E402
from core.kelvins_metric import HIGH_RISK_THRESHOLD, kelvins_score  # noqa: E402

PRIMARY = "pred_B1_latest_cdm"


def _load() -> pd.DataFrame:
    path = settings.PROCESSED_DIR / "baseline_predictions.parquet"
    if not path.is_file():
        raise FileNotFoundError(f"{path}; run scripts/run_baselines.py first")
    frame = pd.read_parquet(path)
    if PRIMARY not in frame.columns:
        raise RuntimeError(f"{PRIMARY} missing from {path}")
    return frame


def _group_stats(frame: pd.DataFrame, mask: np.ndarray, label: str) -> dict[str, Any]:
    subset = frame.loc[mask]
    if subset.empty:
        return {"group": label, "n": 0}
    truth = subset["final_risk"].to_numpy(dtype=np.float64)
    predicted = subset[PRIMARY].to_numpy(dtype=np.float64)
    error = predicted - truth
    high = truth >= HIGH_RISK_THRESHOLD
    return {
        "group": label,
        "n": int(len(subset)),
        "n_high_risk": int(high.sum()),
        "high_risk_pct": round(100 * float(high.mean()), 3),
        "mean_abs_error": float(np.mean(np.abs(error))),
        "median_abs_error": float(np.median(np.abs(error))),
        "mean_signed_error": float(np.mean(error)),
        "mae_high_risk_only": (
            float(np.mean(np.abs(error[high]))) if high.any() else None
        ),
        "spearman": float(spearman(truth, predicted)) if len(subset) > 2 else None,
        "recall_high_risk": (
            float(np.mean(predicted[high] >= HIGH_RISK_THRESHOLD)) if high.any() else None
        ),
    }


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    frame = _load()
    truth = frame["final_risk"].to_numpy(dtype=np.float64)
    predicted = frame[PRIMARY].to_numpy(dtype=np.float64)
    high = truth >= HIGH_RISK_THRESHOLD

    result: dict[str, Any] = {
        "baseline": PRIMARY,
        "n_events": int(len(frame)),
        "n_high_risk": int(high.sum()),
        "overall": kelvins_score(truth, predicted).as_dict(),
    }

    # -- 1. which events are ranked badly -------------------------------------------------
    # Rank error: how far the event sits from where it should in the predicted ordering.
    predicted_rank = pd.Series(-predicted).rank(method="average").to_numpy()
    truth_rank = pd.Series(-truth).rank(method="average").to_numpy()
    rank_error = predicted_rank - truth_rank
    frame = frame.assign(rank_error=rank_error, abs_error=np.abs(predicted - truth))

    worst = frame.reindex(frame["abs_error"].sort_values(ascending=False).index).head(15)
    result["worst_absolute_errors"] = [
        {
            "series_id": str(row["series_id"]),
            "true_risk": round(float(row["final_risk"]), 3),
            "predicted": round(float(row[PRIMARY]), 3),
            "error": round(float(row["abs_error"]), 3),
            "is_high_risk": int(row["is_high_risk"]),
            "n_cdms_input": int(row["n_cdms_input"]),
            "has_trend": int(row["has_trend"]),
            "any_diluted": int(row["any_diluted"]),
        }
        for _, row in worst.iterrows()
    ]

    # The costly failures: true high-risk events the baseline calls low-risk.
    missed = frame.loc[high & (predicted < HIGH_RISK_THRESHOLD)]
    result["false_negatives"] = {
        "n": int(len(missed)),
        "of_n_high_risk": int(high.sum()),
        "examples": [
            {
                "series_id": str(row["series_id"]),
                "true_risk": round(float(row["final_risk"]), 3),
                "predicted": round(float(row[PRIMARY]), 3),
                "n_cdms_input": int(row["n_cdms_input"]),
                "any_diluted": int(row["any_diluted"]),
                "slope_risk": (
                    None if not np.isfinite(row["slope_risk"])
                    else round(float(row["slope_risk"]), 4)
                ),
            }
            for _, row in missed.head(20).iterrows()
        ],
    }

    # -- 2. by event property -------------------------------------------------------------
    groups: list[dict[str, Any]] = []
    groups.append(_group_stats(frame, np.ones(len(frame), dtype=bool), "all"))
    groups.append(_group_stats(frame, frame["final_risk_is_floored"].to_numpy(bool), "censored label"))
    groups.append(_group_stats(frame, ~frame["final_risk_is_floored"].to_numpy(bool), "uncensored label"))
    groups.append(_group_stats(frame, frame["has_trend"].to_numpy() == 0, "single visible CDM"))
    groups.append(_group_stats(frame, frame["has_trend"].to_numpy() == 1, "multiple visible CDMs"))
    groups.append(_group_stats(frame, frame["any_diluted"].to_numpy() == 1, "any diluted CDM"))
    groups.append(_group_stats(frame, frame["any_diluted"].to_numpy() == 0, "no diluted CDM"))
    groups.append(_group_stats(frame, high, "true high-risk"))
    groups.append(_group_stats(frame, ~high, "true low-risk"))

    counts = frame["n_cdms_input"].to_numpy()
    for low, upper, label in ((1, 1, "1 CDM"), (2, 4, "2-4 CDMs"),
                              (5, 9, "5-9 CDMs"), (10, 10**6, "10+ CDMs")):
        groups.append(_group_stats(frame, (counts >= low) & (counts <= upper), label))
    result["by_group"] = groups

    # -- 3. does dilution correlate with error? -------------------------------------------
    diluted = frame["any_diluted"].to_numpy(dtype=float)
    absolute_error = frame["abs_error"].to_numpy(dtype=float)
    result["dilution_vs_error"] = {
        "spearman_dilution_vs_abs_error": float(spearman(diluted, absolute_error)),
        "mean_abs_error_diluted": float(absolute_error[diluted == 1].mean()),
        "mean_abs_error_robust": float(absolute_error[diluted == 0].mean()),
        "high_risk_rate_diluted": float(high[diluted == 1].mean()),
        "high_risk_rate_robust": float(high[diluted == 0].mean()),
        "note": (
            "Tests the Phase 4 hypothesis that diluted covariance associates with high "
            "risk. A positive rate difference supports it; it remains an association, "
            "not a validated flag."
        ),
    }

    # -- 4. how much does the risk actually move after the cutoff? ------------------------
    movement = truth - frame["latest_risk"].to_numpy(dtype=np.float64)
    uncensored = ~frame["final_risk_is_floored"].to_numpy(bool)
    result["risk_movement_after_cutoff"] = {
        "note": (
            "final risk minus the last visible risk. This is exactly what any model must "
            "predict beyond B1, so its spread bounds the achievable improvement."
        ),
        "all_events": {
            "mean": float(movement.mean()),
            "median": float(np.median(movement)),
            "std": float(movement.std(ddof=1)),
            "abs_median": float(np.median(np.abs(movement))),
            "frac_within_0.5": float(np.mean(np.abs(movement) <= 0.5)),
            "frac_within_1.0": float(np.mean(np.abs(movement) <= 1.0)),
        },
        "uncensored_only": {
            "n": int(uncensored.sum()),
            "mean": float(movement[uncensored].mean()),
            "median": float(np.median(movement[uncensored])),
            "std": float(movement[uncensored].std(ddof=1)),
            "abs_median": float(np.median(np.abs(movement[uncensored]))),
        },
        "high_risk_only": {
            "n": int(high.sum()),
            "mean": float(movement[high].mean()),
            "median": float(np.median(movement[high])),
            "std": float(movement[high].std(ddof=1)),
            "abs_median": float(np.median(np.abs(movement[high]))),
        },
    }

    destination = settings.PROCESSED_DIR / "error_analysis.json"
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(f"B1 on the last validation split: {len(frame):,} events, {int(high.sum())} high-risk")
    print(f"  false negatives: {result['false_negatives']['n']} of {int(high.sum())} high-risk missed")
    print(f"\n{'group':<24} {'n':>6} {'HR':>5} {'MAE':>8} {'MAE(HR)':>9} {'recall':>7}")
    print("-" * 64)
    for group in result["by_group"]:
        if not group.get("n"):
            continue
        mae_hr = group["mae_high_risk_only"]
        recall = group["recall_high_risk"]
        print(
            f"{group['group']:<24} {group['n']:>6} {group['n_high_risk']:>5} "
            f"{group['mean_abs_error']:>8.3f} "
            f"{('n/a' if mae_hr is None else f'{mae_hr:.3f}'):>9} "
            f"{('n/a' if recall is None else f'{recall:.3f}'):>7}"
        )
    d = result["dilution_vs_error"]
    print(
        f"\ndilution: high-risk rate {d['high_risk_rate_diluted']:.4f} (diluted) vs "
        f"{d['high_risk_rate_robust']:.4f} (robust); "
        f"MAE {d['mean_abs_error_diluted']:.3f} vs {d['mean_abs_error_robust']:.3f}"
    )
    m = result["risk_movement_after_cutoff"]
    print(
        f"\nrisk movement after the cutoff: median |delta| "
        f"{m['all_events']['abs_median']:.3f}, "
        f"{100 * m['all_events']['frac_within_0.5']:.1f}% move under 0.5 dex; "
        f"high-risk median |delta| {m['high_risk_only']['abs_median']:.3f}"
    )
    print(f"-> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
