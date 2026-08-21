"""The single, final, one-time evaluation on the held-out Kelvins test set.

**This runs once.** The test set has been read zero times for scoring across Phases 1-6.
Every arm is scored here in one pass and everything is reported, including whatever is
unflattering. Nothing is selected, weighted, thresholded or chosen using test data: every
hyperparameter, threshold, prompt and scope rule is frozen from Phases 5 and 6.

The learned arms (B4, B5) are refitted on the **full** train set — not the train/validation
carve used for model selection — with the hyperparameters frozen in Phase 5, then predict
test once.

Confidence intervals come from bootstrap resampling of the 2,167 test events. That measures
**sampling uncertainty within this one test set**, which is a different and generally
smaller quantity than the split-to-split variance Phase 5 measured (±0.500 on L). The two
must not be compared.

Writes ``processed/test_results.json`` and ``processed/test_predictions.parquet``.

    python scripts/evaluate_test.py
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from core.config import settings  # noqa: E402
from core.evaluation import TASK, evaluate  # noqa: E402
from core.features import FEATURE_COLUMNS, build_dataset  # noqa: E402
from core.kelvins_metric import (  # noqa: E402
    HIGH_RISK_THRESHOLD,
    PUBLISHED_SCORES,
    kelvins_score,
)

#: Bootstrap settings, recorded so the interval is reproducible.
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20260821

#: Published figures for this exact test set, all from arXiv:2008.03069 Table 3 and §4.4.
LEADERBOARD_SOURCE = "arXiv:2008.03069 (Uriot et al. 2020), Table 3 and section 4.4"

#: Artefacts whose commit hash is recorded so the evaluated state is provable.
FROZEN_ARTEFACTS = (
    "core/features.py",
    "core/evaluation.py",
    "core/kelvins_metric.py",
    "scripts/run_baselines.py",
    "agent/triage_agent.py",
    "agent/llm.py",
    "docs/PHASE6_PREREGISTRATION.md",
    "docs/PHASE6_DEVIATIONS.md",
)


def _git(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=REPO_ROOT, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(arguments)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def frozen_manifest() -> dict[str, Any]:
    """Commit hash and blob hash of every artefact being evaluated."""
    entries = {}
    for path in FROZEN_ARTEFACTS:
        commit = _git("log", "-1", "--format=%H", "--", path)
        if not commit:
            raise RuntimeError(f"{path} has never been committed; cannot freeze it")
        blob = _git("rev-parse", f"HEAD:{path}")
        dirty = bool(_git("status", "--porcelain", path))
        if dirty:
            raise RuntimeError(
                f"{path} has uncommitted changes; the evaluated state must be provable"
            )
        entries[path] = {"last_commit": commit, "blob": blob}

    from agent.triage_agent import PROMPT_VERSION, SCOPE_THRESHOLD

    return {
        "head": _git("rev-parse", "HEAD"),
        "artefacts": entries,
        "agent": {
            "prompt_version": PROMPT_VERSION,
            "scope_threshold": SCOPE_THRESHOLD,
            "provider": settings.LLM_PROVIDER,
            "model": settings.LLM_MODEL,
            "temperature": 0.0,
        },
    }


# --------------------------------------------------------------------------------------
# the arms, all frozen
# --------------------------------------------------------------------------------------

def b1_latest(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    return test["latest_risk"].to_numpy(dtype=np.float64)


def b2b_constant(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    from run_baselines import CRP_CONSTANT

    return np.full(len(test), CRP_CONSTANT)


def b3_extrapolate(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    from run_baselines import b3_extrapolate as frozen

    return frozen(train, test)


def b4_gbm(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    from run_baselines import b4_gbm as frozen

    return frozen(0)(train, test)


def b5_two_stage(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    from run_baselines import b5_two_stage as frozen

    return frozen(0)(train, test)


def agent_predictions(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    """Agent verdicts where in scope, B1 unchanged elsewhere — the Phase 6 design."""
    path = settings.PROCESSED_DIR / "agent_predictions_test.parquet"
    if not path.is_file():
        raise FileNotFoundError(
            f"{path}; run scripts/run_agent_test.py first to produce test-set verdicts"
        )
    frame = pd.read_parquet(path)
    lookup = dict(zip(frame["series_id"], frame["agent_prediction"]))
    missing = set(test["series_id"]) - set(lookup)
    if missing:
        raise RuntimeError(f"{len(missing)} test events have no agent prediction")
    values = test["series_id"].map(lookup).to_numpy(dtype=np.float64)
    if not np.isfinite(values).all():
        raise RuntimeError("agent predictions contain non-finite values")
    return values


ARMS: dict[str, Callable[[pd.DataFrame, pd.DataFrame], np.ndarray]] = {
    "B1_latest_cdm": b1_latest,
    "B2b_constant_minus5": b2b_constant,
    "B3_linear_extrapolation": b3_extrapolate,
    "B4_gbm_regressor": b4_gbm,
    "B5_two_stage_gbm": b5_two_stage,
    "agent": agent_predictions,
}


# --------------------------------------------------------------------------------------
# bootstrap
# --------------------------------------------------------------------------------------

def bootstrap_l(
    truth: np.ndarray, predictions: np.ndarray,
    resamples: int = BOOTSTRAP_RESAMPLES, seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """Percentile bootstrap CI for L, resampling the test events."""
    rng = np.random.default_rng(seed)
    n = truth.size
    scores = []
    for _ in range(resamples):
        index = rng.integers(0, n, n)
        try:
            scores.append(kelvins_score(truth[index], predictions[index]).score)
        except Exception:
            # A resample with no true high-risk event leaves MSE_HR undefined. Skipped
            # and counted rather than silently replaced with a number.
            continue
    finite = np.array([s for s in scores if np.isfinite(s)])
    return {
        "resamples": resamples,
        "usable": int(finite.size),
        "skipped_undefined": int(resamples - len(scores)),
        "non_finite": int(len(scores) - finite.size),
        "ci95": [float(np.percentile(finite, 2.5)), float(np.percentile(finite, 97.5))]
        if finite.size else None,
        "median": float(np.median(finite)) if finite.size else None,
    }


def bootstrap_difference(
    truth: np.ndarray, arm: np.ndarray, baseline: np.ndarray,
    resamples: int = BOOTSTRAP_RESAMPLES, seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """Paired bootstrap CI for L(arm) - L(baseline) on the same resampled events."""
    rng = np.random.default_rng(seed)
    n = truth.size
    differences = []
    for _ in range(resamples):
        index = rng.integers(0, n, n)
        try:
            a = kelvins_score(truth[index], arm[index]).score
            b = kelvins_score(truth[index], baseline[index]).score
        except Exception:
            continue
        if np.isfinite(a) and np.isfinite(b):
            differences.append(a - b)
    values = np.array(differences)
    if values.size == 0:
        return {"usable": 0, "ci95": None}
    return {
        "resamples": resamples,
        "usable": int(values.size),
        "median": float(np.median(values)),
        "mean": float(values.mean()),
        "ci95": [float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))],
        "fraction_favouring_arm": float((values < 0).mean()),
    }


def leaderboard_position(score: float) -> str:
    """Where this score would have placed in the 2019 competition."""
    if not np.isfinite(score):
        return "no valid score (F2 = 0)"
    if score < PUBLISHED_SCORES["winner_sesc"]["L"]:
        return "better than the winner (1st)"
    if score < PUBLISHED_SCORES["tenth_spacemeister"]["L"]:
        return "top 10"
    if score < PUBLISHED_SCORES["LRP_baseline_latest_risk"]["L"]:
        return "beats the LRP baseline (top ~12 of 97)"
    if score < PUBLISHED_SCORES["CRP_baseline_constant_minus5"]["L"]:
        return "below LRP, above the constant baseline"
    return "worse than the constant baseline"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-agent", action="store_true",
                        help="score only the non-agent arms")
    args = parser.parse_args()

    started = time.perf_counter()
    manifest = frozen_manifest()
    print(f"frozen at HEAD {manifest['head'][:12]}")
    print(f"  agent: {manifest['agent']['provider']}/{manifest['agent']['model']} "
          f"prompt {manifest['agent']['prompt_version']} scope "
          f"{manifest['agent']['scope_threshold']}")

    train = build_dataset("train")
    test = build_dataset("test")
    truth = test["final_risk"].to_numpy(dtype=np.float64)
    high = truth >= HIGH_RISK_THRESHOLD

    print(f"\ntrain {len(train):,} events ({int(train.is_high_risk.sum())} high-risk)")
    print(f"test  {len(test):,} events ({int(high.sum())} high-risk, "
          f"{100 * high.mean():.2f}%)  <- scored ONCE")

    results: dict[str, Any] = {}
    stored = {"series_id": test["series_id"].to_numpy(), "final_risk": truth}

    for name, predictor in ARMS.items():
        if name == "agent" and args.skip_agent:
            continue
        print(f"\nscoring {name} ...", flush=True)
        predictions = predictor(train, test)
        if predictions.shape != truth.shape:
            raise RuntimeError(f"{name}: {predictions.size} predictions for {truth.size} events")
        stored[f"pred_{name}"] = predictions

        result = evaluate(name, truth, predictions)
        score = result.official.score
        recall_high = (
            float(np.mean(predictions[high] >= HIGH_RISK_THRESHOLD)) if high.any() else None
        )
        results[name] = {
            **result.as_dict(),
            "recall_on_150_high_risk": recall_high,
            "bootstrap_L": bootstrap_l(truth, predictions),
            "leaderboard_position": leaderboard_position(score),
        }
        print(
            f"  L={score:.4f}  MSE_HR={result.official.mse_hr:.4f}  "
            f"F2={result.official.f2:.4f}  rho={result.ranking['spearman']:+.4f}  "
            f"recall={recall_high:.4f}" if recall_high is not None else f"  L={score:.4f}"
        )

    # paired difference against B1, the primary comparison
    if "agent" in results:
        results["agent_vs_b1"] = bootstrap_difference(
            truth, stored["pred_agent"], stored["pred_B1_latest_cdm"]
        )
    for arm in ("B5_two_stage_gbm", "B4_gbm_regressor", "B3_linear_extrapolation"):
        if arm in results:
            results[f"{arm}_vs_b1"] = bootstrap_difference(
                truth, stored[f"pred_{arm}"], stored["pred_B1_latest_cdm"]
            )

    report = {
        "evaluation": "SINGLE final test-set evaluation; the test set is scored once",
        "frozen_manifest": manifest,
        "test_events": int(len(test)),
        "test_high_risk": int(high.sum()),
        "test_high_risk_pct": round(100 * float(high.mean()), 3),
        "eligibility_filter_reapplied": False,
        "eligibility_note": (
            "The public test set is already truncated at 2 days by ESA. Reapplying the "
            "Phase 5 eligibility filter would reject all 2,167 events; core.features "
            "marks test as pre-filtered."
        ),
        "bootstrap": {
            "resamples": BOOTSTRAP_RESAMPLES,
            "seed": BOOTSTRAP_SEED,
            "measures": (
                "sampling uncertainty within this one test set, NOT the split-to-split "
                "variance of +/-0.500 measured in Phase 5"
            ),
        },
        "published_leaderboard": PUBLISHED_SCORES,
        "published_leaderboard_source": LEADERBOARD_SOURCE,
        "arms": results,
        "wall_time_seconds": round(time.perf_counter() - started, 1),
    }

    destination = settings.PROCESSED_DIR / "test_results.json"
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    pd.DataFrame(stored).to_parquet(
        settings.PROCESSED_DIR / "test_predictions.parquet"
    )

    print(f"\n{'arm':<26}{'L':>10}{'MSE_HR':>9}{'F2':>8}{'recall':>8}  position")
    print("-" * 86)
    ordered = sorted(
        results.items(),
        key=lambda kv: kv[1]["official"]["L"] if isinstance(kv[1], dict) and "official" in kv[1]
        and np.isfinite(kv[1]["official"]["L"]) else 9e9,
    )
    for name, block in ordered:
        if "official" not in block:
            continue
        official = block["official"]
        score = official["L"]
        shown = f"{score:10.4f}" if np.isfinite(score) else "       inf"
        recall = block.get("recall_on_150_high_risk")
        print(
            f"{name:<26}{shown}{official['mse_hr']:9.4f}{official['f2']:8.4f}"
            f"{(recall if recall is not None else float('nan')):8.4f}  "
            f"{block['leaderboard_position']}"
        )
    print(f"\n-> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
