"""Run the pre-registered Phase 11 ablation. No LLM calls.

Five arms, paired on the 50 pre-registered splits:

===  ====================================================================================
H0   B1 alone (reference)
H1   binary action space + the raw ``will_collapse`` verdict, uncalibrated
H2   binary action space + calibrated classifier on Phase 5 features only, **no LLM**
H3   binary action space + calibrated classifier on Phase 5 + LLM features (the hybrid)
H4   H3 with the LLM features permuted, over 20 seeds
===  ====================================================================================

**The headline is H3 vs H2**, per the pre-registration. If a calibrated model on features
that already existed does as well as one that also sees the LLM, the LLM contributed
nothing — and that is the finding, whatever H3 does against B1.

H4 is what makes an H3-vs-H2 gap believable. Permuting the LLM columns destroys their
signal while leaving capacity, feature count and fitting procedure identical, so a gap that
survives permutation is capacity rather than signal.

    python scripts/run_hybrid.py
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from agent.hybrid import (  # noqa: E402
    HybridConfig,
    build_llm_features,
    eligible_mask,
    fit_hybrid,
    minimum_precision,
)
from core.config import settings  # noqa: E402
from core.features import build_dataset  # noqa: E402
from core.kelvins_metric import HIGH_RISK_THRESHOLD, kelvins_score  # noqa: E402
from run_baselines import stratified_split  # noqa: E402

# -- pre-registered constants (docs/PHASE11_PREREGISTRATION.md) ------------------------
BASE_SEED = 20260819
N_SPLITS = 50
VALIDATION_FRACTION = 0.25
ALPHA = 0.05
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20260819
MINIMUM_IMPORTANT_DIFFERENCE = -0.138
MAX_EXCLUDED_SPLITS = 5
N_PERMUTATIONS = 20


def _peak_memory_mb() -> float:
    import psutil

    info = psutil.Process().memory_info()
    return getattr(info, "peak_wset", info.rss) / 1024**2


def load_joined() -> pd.DataFrame:
    """Train events joined to the cached v1 predictions, with the LLM feature columns."""
    train = build_dataset("train")
    predictions = pd.read_parquet(settings.PROCESSED_DIR / "agent_predictions.parquet")
    joined = train.merge(
        predictions[["series_id", "agent_analysed", "will_collapse", "confidence",
                     "n_citations", "reasoning", "evidence_cited"]],
        on="series_id", how="left", validate="one_to_one",
    )
    joined["agent_analysed"] = joined["agent_analysed"].fillna(False).astype(bool)
    return pd.concat([joined, build_llm_features(joined)], axis=1)


ARMS: dict[str, HybridConfig] = {
    "H1_verdict_only": HybridConfig(
        name="H1_verdict_only", use_phase5_features=False, use_llm_features=True,
        calibrate=False, rule_from_verdict=True,
    ),
    "H2_calibrated_no_llm": HybridConfig(
        name="H2_calibrated_no_llm", use_phase5_features=True, use_llm_features=False,
        calibrate=True,
    ),
    "H3_calibrated_with_llm": HybridConfig(
        name="H3_calibrated_with_llm", use_phase5_features=True, use_llm_features=True,
        calibrate=True,
    ),
}


# ------------------------------------------------------------------------------------
# scoring one arm across every split
# ------------------------------------------------------------------------------------

def run_arm(
    config: HybridConfig, joined: pd.DataFrame, classifier: str = "gbm"
) -> dict[str, Any]:
    """Score one arm on all 50 splits. Returns per-split L, plus the audit trail."""
    per_split: list[dict[str, Any]] = []
    for offset in range(N_SPLITS):
        seed = BASE_SEED + offset
        fit, validation = stratified_split(joined, seed, VALIDATION_FRACTION)
        truth = validation["final_risk"].to_numpy(dtype=np.float64)
        baseline = validation["latest_risk"].to_numpy(dtype=np.float64)

        result = fit_hybrid(
            HybridConfig(**{**config.__dict__, "classifier": classifier}),
            fit, validation, seed,
        )
        arm_score = kelvins_score(truth, result.predictions)
        b1_score = kelvins_score(truth, baseline)

        # Downgrade precision on this split, for the report -- not used for any fitting.
        downgraded = result.predictions < HIGH_RISK_THRESHOLD
        moved = downgraded & (baseline >= HIGH_RISK_THRESHOLD)
        truth_low = truth < HIGH_RISK_THRESHOLD
        n_moved = int(moved.sum())

        per_split.append({
            "seed": seed,
            "n": int(len(validation)),
            "n_high_risk": int((truth >= HIGH_RISK_THRESHOLD).sum()),
            "L_arm": float(arm_score.score),
            "L_b1": float(b1_score.score),
            "D": float(arm_score.score - b1_score.score),
            "f2_arm": float(arm_score.f2), "f2_b1": float(b1_score.f2),
            "mse_arm": float(arm_score.mse_hr), "mse_b1": float(b1_score.mse_hr),
            "threshold": result.threshold,
            "analytic_threshold": result.analytic_threshold,
            "n_eligible": result.n_eligible,
            "n_downgraded": n_moved,
            "downgrade_precision": (
                float(np.sum(moved & truth_low) / n_moved) if n_moved else None
            ),
        })

    return {"arm": config.name, "classifier": classifier, "per_split": per_split}


def paired_stats(differences: np.ndarray, label: str) -> dict[str, Any]:
    """Wilcoxon plus a bootstrap CI on the median, exactly as pre-registered."""
    from scipy.stats import wilcoxon

    finite = np.isfinite(differences)
    excluded = int((~finite).sum())
    usable = differences[finite]
    if usable.size == 0:
        return {"comparison": label, "usable": 0, "excluded_non_finite": excluded}

    if np.allclose(usable, 0.0):
        # Wilcoxon is undefined when every difference is exactly zero, and that is a
        # meaningful outcome here: the arm made no change on any split.
        statistic, p_value = float("nan"), 1.0
    else:
        statistic, p_value = wilcoxon(usable, alternative="two-sided")

    rng = np.random.default_rng(BOOTSTRAP_SEED)
    medians = np.array([
        np.median(rng.choice(usable, size=usable.size, replace=True))
        for _ in range(BOOTSTRAP_RESAMPLES)
    ])
    return {
        "comparison": label,
        "splits": int(differences.size),
        "usable": int(usable.size),
        "excluded_non_finite": excluded,
        "median_D": float(np.median(usable)),
        "mean_D": float(usable.mean()),
        "ci95_median_D": [float(np.percentile(medians, 2.5)),
                          float(np.percentile(medians, 97.5))],
        "wilcoxon_statistic": float(statistic),
        "p_value": float(p_value),
        "splits_arm_wins": int((usable < 0).sum()),
        "splits_arm_loses": int((usable > 0).sum()),
        "splits_tied": int((usable == 0).sum()),
    }


def decide(stats: dict[str, Any]) -> dict[str, str]:
    """The pre-registered decision rule, evaluated in the pre-registered order."""
    if stats.get("excluded_non_finite", 0) > MAX_EXCLUDED_SPLITS:
        return {"outcome": "UNINTERPRETABLE",
                "statement": f"{stats['excluded_non_finite']} splits excluded for "
                             f"non-finite L, above the pre-registered limit of "
                             f"{MAX_EXCLUDED_SPLITS}. No win or null is claimed."}
    median, p_value = stats["median_D"], stats["p_value"]
    if p_value >= ALPHA:
        return {"outcome": "NO EFFECT",
                "statement": "Null result. No detectable difference from the reference."}
    if median <= MINIMUM_IMPORTANT_DIFFERENCE:
        return {"outcome": "HYBRID WINS",
                "statement": "Beats the reference by at least the pre-specified minimum."}
    if median < 0:
        return {"outcome": "DETECTABLE BUT BELOW THRESHOLD",
                "statement": "A statistically detectable improvement smaller than the "
                             "pre-specified minimum important difference, and therefore "
                             "not operationally meaningful. Not a win."}
    return {"outcome": "HYBRID LOSES",
            "statement": "Performs worse than the reference."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--permutations", type=int, default=N_PERMUTATIONS)
    parser.add_argument("--classifiers", nargs="+", default=["gbm", "logistic"])
    args = parser.parse_args()

    started = time.perf_counter()
    joined = load_joined()
    eligible = eligible_mask(joined)
    truth = joined["final_risk"].to_numpy(dtype=np.float64)
    print(f"{len(joined):,} train events, {int(eligible.sum())} downgrade-eligible, "
          f"of which {int((truth[eligible] >= HIGH_RISK_THRESHOLD).sum())} truly high-risk")

    analytic = minimum_precision(truth, joined["latest_risk"].to_numpy(dtype=np.float64))
    print(f"analytic minimum downgrade precision on train: "
          f"{100 * analytic['minimum_precision']:.2f}%  "
          f"(one wrong downgrade costs {analytic['harm_to_benefit']:.1f}x one right one)\n")

    report: dict[str, Any] = {
        "preregistration": "docs/PHASE11_PREREGISTRATION.md",
        "protocol": {
            "splits": N_SPLITS,
            "seeds": [BASE_SEED + i for i in range(N_SPLITS)],
            "validation_fraction": VALIDATION_FRACTION,
            "alpha": ALPHA,
            "minimum_important_difference": MINIMUM_IMPORTANT_DIFFERENCE,
            "test_set_read": False,
        },
        "analytic_cost_derivation": analytic,
        "arms": {},
        "comparisons": {},
    }

    # -- the three named arms, per classifier --------------------------------------------
    stored: dict[str, dict[str, np.ndarray]] = {}
    for classifier in args.classifiers:
        print(f"== classifier: {classifier} ==")
        for name, config in ARMS.items():
            if config.rule_from_verdict and classifier != args.classifiers[0]:
                continue  # H1 uses no classifier; run it once
            key = name if config.rule_from_verdict else f"{name}__{classifier}"
            result = run_arm(config, joined, classifier)
            frame = pd.DataFrame(result["per_split"])
            stored.setdefault(key, {})["D"] = frame["D"].to_numpy(dtype=np.float64)
            stored[key]["L"] = frame["L_arm"].to_numpy(dtype=np.float64)

            stats = paired_stats(stored[key]["D"], f"{key} vs B1")
            decision = decide(stats)
            report["arms"][key] = {
                **result,
                "L_mean": float(frame["L_arm"].mean()),
                "L_b1_mean": float(frame["L_b1"].mean()),
                "mean_threshold": float(frame["threshold"].mean()),
                "mean_analytic_threshold": float(frame["analytic_threshold"].mean()),
                "mean_downgrades": float(frame["n_downgraded"].mean()),
                "mean_eligible": float(frame["n_eligible"].mean()),
                "mean_downgrade_precision": (
                    float(frame["downgrade_precision"].dropna().mean())
                    if frame["downgrade_precision"].notna().any() else None
                ),
                "vs_b1": {**stats, **decision},
            }
            print(f"  {key:34s} L = {frame['L_arm'].mean():7.4f}  "
                  f"median D = {stats['median_D']:+.4f}  p = {stats['p_value']:.4g}  "
                  f"-> {decision['outcome']}")
            print(f"  {' ':34s} threshold {frame['threshold'].mean():.4f} "
                  f"(analytic {frame['analytic_threshold'].mean():.4f}), "
                  f"downgrades {frame['n_downgraded'].mean():.1f}/"
                  f"{frame['n_eligible'].mean():.1f}")
        print()

    # -- THE HEADLINE: H3 vs H2 -----------------------------------------------------------
    for classifier in args.classifiers:
        h2, h3 = f"H2_calibrated_no_llm__{classifier}", f"H3_calibrated_with_llm__{classifier}"
        if h2 not in stored or h3 not in stored:
            continue
        difference = stored[h3]["L"] - stored[h2]["L"]
        stats = paired_stats(difference, f"H3 vs H2 ({classifier})")
        report["comparisons"][f"H3_vs_H2__{classifier}"] = {**stats, **decide(stats)}
        print(f"HEADLINE  H3 vs H2 ({classifier}): median D = {stats['median_D']:+.6f}, "
              f"p = {stats['p_value']:.4g} -> {decide(stats)['outcome']}")

    # -- H4: the permutation control ------------------------------------------------------
    print(f"\n== H4: permuting the LLM features, {args.permutations} seeds ==", flush=True)
    permuted_means: list[float] = []
    permuted_vs_h2: list[float] = []
    classifier = args.classifiers[0]
    h2_key = f"H2_calibrated_no_llm__{classifier}"
    for index in range(args.permutations):
        config = HybridConfig(
            name=f"H4_permuted_{index}", use_phase5_features=True, use_llm_features=True,
            calibrate=True, permute_llm=True, permute_seed=20261101 + index,
        )
        result = run_arm(config, joined, classifier)
        frame = pd.DataFrame(result["per_split"])
        permuted_means.append(float(frame["L_arm"].mean()))
        permuted_vs_h2.append(
            float(np.median(frame["L_arm"].to_numpy() - stored[h2_key]["L"]))
        )
        if (index + 1) % 5 == 0:
            print(f"  {index + 1}/{args.permutations} done", flush=True)

    h3_key = f"H3_calibrated_with_llm__{classifier}"
    observed = float(np.median(stored[h3_key]["L"] - stored[h2_key]["L"]))
    permuted_vs_h2 = np.asarray(permuted_vs_h2)
    # One-sided permutation p: how often does destroying the LLM signal do at least as well
    # as keeping it? A large value means the LLM columns carried nothing.
    permutation_p = float(np.mean(permuted_vs_h2 <= observed))
    report["H4_permutation_control"] = {
        "permutations": args.permutations,
        "classifier": classifier,
        "observed_H3_minus_H2_median": observed,
        "permuted_H3_minus_H2_median": {
            "mean": float(permuted_vs_h2.mean()),
            "std": float(permuted_vs_h2.std(ddof=1)),
            "min": float(permuted_vs_h2.min()),
            "max": float(permuted_vs_h2.max()),
        },
        "permutation_p_value": permutation_p,
        "interpretation": (
            "Fraction of permutations that matched or beat the real LLM features. A value "
            "near 1 means the intact features carried no signal the permuted ones lacked; "
            "a value near 0 means they did."
        ),
    }
    print(f"  observed H3-H2 median  {observed:+.6f}")
    print(f"  permuted H3-H2 median  {permuted_vs_h2.mean():+.6f} "
          f"+/- {permuted_vs_h2.std(ddof=1):.6f}  "
          f"[{permuted_vs_h2.min():+.6f}, {permuted_vs_h2.max():+.6f}]")
    print(f"  permutation p = {permutation_p:.4f}")

    report["elapsed_seconds"] = round(time.perf_counter() - started, 1)
    report["peak_memory_mb"] = round(_peak_memory_mb(), 1)
    destination = settings.PROCESSED_DIR / "hybrid_results.json"
    destination.write_text(json.dumps(report, indent=2, default=float), encoding="utf-8")
    print(f"\npeak memory {report['peak_memory_mb']} MB, "
          f"{report['elapsed_seconds']}s -> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
