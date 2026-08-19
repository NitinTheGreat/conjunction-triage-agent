"""The pre-registered paired comparison: agent against B1, and B5 against B1.

Follows ``docs/PHASE6_PREREGISTRATION.md`` exactly. Every constant here — the 50 seeds,
the Wilcoxon test, alpha, the 0.138 minimum important difference, the exclusion rule for
non-finite L, and the decision rule — is read from that file's specification and is not
chosen here. Any deviation is recorded in the report, never by editing the protocol.

The test split is never read.

    python scripts/compare_arms.py
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import settings  # noqa: E402
from core.evaluation import evaluate  # noqa: E402
from core.features import build_dataset  # noqa: E402
from core.kelvins_metric import kelvins_score  # noqa: E402
from run_baselines import stratified_split  # noqa: E402

# ---- pre-registered constants (docs/PHASE6_PREREGISTRATION.md) -----------------------
#: Section 3: 50 splits, the Phase 5 seeds, fixed in advance.
BASE_SEED = 20260819
N_SPLITS = 50
VALIDATION_FRACTION = 0.25
#: Section 4: two-sided Wilcoxon at alpha = 0.05, bootstrap CI with 10,000 resamples.
ALPHA = 0.05
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20260819
#: Section 5: the smallest effect worth caring about.
MINIMUM_IMPORTANT_DIFFERENCE = -0.138
#: Section 4: more than this many excluded splits makes the result uninterpretable.
MAX_EXCLUDED_SPLITS = 5


def _peak_memory_mb() -> float:
    import psutil

    info = psutil.Process().memory_info()
    return getattr(info, "peak_wset", info.rss) / 1024**2


def load_agent_predictions() -> pd.DataFrame:
    path = settings.PROCESSED_DIR / "agent_predictions.parquet"
    if not path.is_file():
        raise FileNotFoundError(f"{path}; run scripts/run_agent.py first")
    frame = pd.read_parquet(path)
    for column in ("series_id", "agent_prediction", "b1_risk"):
        if column not in frame.columns:
            raise RuntimeError(f"{path} is missing {column}")
    return frame


def b5_predictions(train: pd.DataFrame, seed: int) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    """Fit B5 on this split's fit portion and predict on its validation portion."""
    from run_baselines import b5_two_stage

    fit, validation = stratified_split(train, seed, VALIDATION_FRACTION)
    predictions = b5_two_stage(seed)(fit, validation)
    return predictions, validation["final_risk"].to_numpy(dtype=np.float64), validation


def bootstrap_median_ci(
    differences: np.ndarray, resamples: int = BOOTSTRAP_RESAMPLES, seed: int = BOOTSTRAP_SEED
) -> tuple[float, float]:
    """Percentile bootstrap CI for the median of the paired differences."""
    rng = np.random.default_rng(seed)
    n = differences.size
    medians = np.empty(resamples)
    for index in range(resamples):
        medians[index] = np.median(differences[rng.integers(0, n, n)])
    return float(np.percentile(medians, 2.5)), float(np.percentile(medians, 97.5))


def decide(median_difference: float, p_value: float, excluded: int) -> dict[str, str]:
    """Apply the pre-registered decision rule. Evaluated in the specified order."""
    if excluded > MAX_EXCLUDED_SPLITS:
        return {
            "outcome": "UNINTERPRETABLE",
            "statement": (
                f"{excluded} of {N_SPLITS} splits were excluded for non-finite L, above "
                f"the pre-registered limit of {MAX_EXCLUDED_SPLITS}. The comparison could "
                "not be made; no win or null is claimed."
            ),
        }
    if p_value < ALPHA and median_difference <= MINIMUM_IMPORTANT_DIFFERENCE:
        return {
            "outcome": "AGENT WINS",
            "statement": (
                "The agent beats B1 by a margin at least as large as the pre-specified "
                "minimum important difference."
            ),
        }
    if p_value < ALPHA and MINIMUM_IMPORTANT_DIFFERENCE < median_difference < 0:
        return {
            "outcome": "DETECTABLE BUT BELOW THRESHOLD",
            "statement": (
                "The agent produces a statistically detectable improvement that is "
                "smaller than the pre-specified minimum important difference "
                f"({MINIMUM_IMPORTANT_DIFFERENCE}) and is therefore not operationally "
                "meaningful. This is not a win."
            ),
        }
    if p_value < ALPHA and median_difference > 0:
        return {
            "outcome": "AGENT LOSES",
            "statement": "The agent performs worse than B1.",
        }
    return {
        "outcome": "NO EFFECT",
        "statement": (
            "Null result. No detectable difference between the agent and B1."
        ),
    }


def paired_comparison(
    name: str,
    train: pd.DataFrame,
    predictor: Callable[[pd.DataFrame, int], tuple[np.ndarray, np.ndarray, pd.DataFrame]],
) -> dict[str, Any]:
    """Score an arm against B1 across all pre-registered splits."""
    from scipy.stats import wilcoxon

    rows: list[dict[str, Any]] = []
    for offset in range(N_SPLITS):
        seed = BASE_SEED + offset
        predictions, truth, validation = predictor(train, seed)
        b1 = validation["latest_risk"].to_numpy(dtype=np.float64)

        arm = kelvins_score(truth, predictions)
        base = kelvins_score(truth, b1)
        rows.append({
            "seed": seed,
            "n": int(len(validation)),
            "n_high_risk": int(validation["is_high_risk"].sum()),
            "L_arm": arm.score, "L_b1": base.score,
            "f2_arm": arm.f2, "f2_b1": base.f2,
            "mse_arm": arm.mse_hr, "mse_b1": base.mse_hr,
            "D": arm.score - base.score,
        })

    frame = pd.DataFrame(rows)
    finite = np.isfinite(frame["L_arm"]) & np.isfinite(frame["L_b1"])
    excluded = int((~finite).sum())
    usable = frame.loc[finite]
    differences = usable["D"].to_numpy(dtype=np.float64)

    if differences.size < 2:
        return {
            "arm": name, "splits": N_SPLITS, "excluded_non_finite": excluded,
            "decision": decide(float("nan"), 1.0, excluded),
            "per_split": frame.to_dict(orient="records"),
        }

    if np.allclose(differences, 0):
        # Wilcoxon is undefined when every difference is exactly zero; that is itself a
        # finding (the arm never changed the score), not an error to paper over.
        p_value, statistic = 1.0, 0.0
    else:
        statistic, p_value = wilcoxon(differences, alternative="two-sided")

    median_difference = float(np.median(differences))
    low, high = bootstrap_median_ci(differences)

    return {
        "arm": name,
        "splits": N_SPLITS,
        "usable_splits": int(finite.sum()),
        "excluded_non_finite": excluded,
        "median_D": median_difference,
        "mean_D": float(differences.mean()),
        "ci95_median_D": [low, high],
        "wilcoxon_statistic": float(statistic),
        "p_value": float(p_value),
        "alpha": ALPHA,
        "minimum_important_difference": MINIMUM_IMPORTANT_DIFFERENCE,
        "splits_arm_wins": int((differences < 0).sum()),
        "splits_arm_loses": int((differences > 0).sum()),
        "splits_tied": int((differences == 0).sum()),
        "D_distribution": {
            "min": float(differences.min()),
            "q1": float(np.percentile(differences, 25)),
            "median": median_difference,
            "q3": float(np.percentile(differences, 75)),
            "max": float(differences.max()),
            "std": float(differences.std(ddof=1)),
        },
        "L_arm_mean": float(usable["L_arm"].mean()),
        "L_b1_mean": float(usable["L_b1"].mean()),
        "f2_arm_mean": float(usable["f2_arm"].mean()),
        "f2_b1_mean": float(usable["f2_b1"].mean()),
        "mse_arm_mean": float(usable["mse_arm"].mean()),
        "mse_b1_mean": float(usable["mse_b1"].mean()),
        "decision": decide(median_difference, float(p_value), excluded),
        "per_split": frame.to_dict(orient="records"),
    }


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    started = time.perf_counter()

    train = build_dataset("train")
    agent_frame = load_agent_predictions()
    lookup = dict(zip(agent_frame["series_id"], agent_frame["agent_prediction"]))
    missing = set(train["series_id"]) - set(lookup)
    if missing:
        raise RuntimeError(
            f"{len(missing)} eligible events have no agent prediction (e.g. "
            f"{sorted(missing)[:3]}); run scripts/run_agent.py over all events"
        )

    def agent_predictor(frame: pd.DataFrame, seed: int):
        _, validation = stratified_split(frame, seed, VALIDATION_FRACTION)
        predictions = validation["series_id"].map(lookup).to_numpy(dtype=np.float64)
        if not np.isfinite(predictions).all():
            raise RuntimeError(f"seed {seed}: agent predictions contain non-finite values")
        return predictions, validation["final_risk"].to_numpy(dtype=np.float64), validation

    print(f"paired comparison over {N_SPLITS} splits (seeds {BASE_SEED}..{BASE_SEED + N_SPLITS - 1})")
    print("  arm 1: agent vs B1 ...", flush=True)
    agent_result = paired_comparison("agent", train, agent_predictor)
    print("  arm 2: B5 two-stage GBM vs B1 ...", flush=True)
    b5_result = paired_comparison("B5_two_stage_gbm", train, b5_predictions)

    report = {
        "preregistration": "docs/PHASE6_PREREGISTRATION.md",
        "protocol": {
            "splits": N_SPLITS,
            "seeds": [BASE_SEED + i for i in range(N_SPLITS)],
            "validation_fraction": VALIDATION_FRACTION,
            "test": "Wilcoxon signed-rank, two-sided",
            "alpha": ALPHA,
            "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
            "minimum_important_difference": MINIMUM_IMPORTANT_DIFFERENCE,
            "max_excluded_splits": MAX_EXCLUDED_SPLITS,
        },
        "primary": agent_result,
        "secondary_b5": b5_result,
        "test_set_read": False,
        "wall_time_seconds": round(time.perf_counter() - started, 1),
        "peak_memory_mb": round(_peak_memory_mb(), 1),
    }
    destination = settings.PROCESSED_DIR / "comparison_results.json"
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")

    for result in (agent_result, b5_result):
        print(f"\n=== {result['arm']} vs B1 ===")
        if "median_D" not in result:
            print(f"  {result['decision']['outcome']}: {result['decision']['statement']}")
            continue
        print(
            f"  median D = {result['median_D']:+.4f}  "
            f"95% CI [{result['ci95_median_D'][0]:+.4f}, {result['ci95_median_D'][1]:+.4f}]"
        )
        print(f"  Wilcoxon p = {result['p_value']:.6f}  (alpha {ALPHA})")
        print(
            f"  wins {result['splits_arm_wins']}/{result['usable_splits']}, "
            f"loses {result['splits_arm_loses']}, tied {result['splits_tied']}, "
            f"excluded {result['excluded_non_finite']}"
        )
        print(
            f"  L: arm {result['L_arm_mean']:.4f} vs B1 {result['L_b1_mean']:.4f} | "
            f"F2: {result['f2_arm_mean']:.4f} vs {result['f2_b1_mean']:.4f} | "
            f"MSE_HR: {result['mse_arm_mean']:.4f} vs {result['mse_b1_mean']:.4f}"
        )
        print(f"  DECISION: {result['decision']['outcome']}")
        print(f"    {result['decision']['statement']}")

    print(f"\n-> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
