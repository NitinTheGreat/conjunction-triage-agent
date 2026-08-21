"""EXPLORATORY — paired comparison for the restraint prompt v2.

**EXPLORATORY.** The primary result is fixed and published in ``docs/PHASE7_REPORT.md``:
agent L = 1.6606 against B1 0.6940, median paired D = +0.9462, 0.0% of resamples favouring
the agent. Nothing produced here can change, replace, amend or soften that finding
(``docs/PHASE6_PREREGISTRATION.md`` §10.3).

Two comparisons, both on the **same 50 split seeds** the primary result used, and both
through the **same paired-difference machinery** (`scripts/compare_arms.py`), which is
imported rather than reimplemented so the arithmetic cannot drift:

* **v2 vs B1** — does the restraint prompt beat the baseline?
* **v2 vs v1** — does it beat the prompt that produced the primary result?

The v1-vs-B1 numbers are re-derived here on identical splits rather than quoted, so all
three arms are compared on exactly the same events.

Writes ``processed/exploratory_v2_comparison.json``.

    python scripts/exploratory_compare_v2.py
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from compare_arms import (  # noqa: E402
    ALPHA,
    BASE_SEED,
    MINIMUM_IMPORTANT_DIFFERENCE,
    N_SPLITS,
    VALIDATION_FRACTION,
    bootstrap_median_ci,
)
from core.config import settings  # noqa: E402
from core.features import build_dataset  # noqa: E402
from core.kelvins_metric import kelvins_score  # noqa: E402
from run_baselines import stratified_split  # noqa: E402


def _load(name: str, column: str = "agent_prediction") -> dict[str, float]:
    path = settings.PROCESSED_DIR / name
    if not path.is_file():
        raise FileNotFoundError(f"{path}; run the corresponding runner first")
    frame = pd.read_parquet(path)
    return dict(zip(frame["series_id"], frame[column].astype(float)))


def paired(
    train: pd.DataFrame,
    arm: dict[str, float],
    reference: dict[str, float],
    label: str,
) -> dict[str, Any]:
    """Paired difference L(arm) − L(reference) across the pre-registered splits."""
    from scipy.stats import wilcoxon

    rows = []
    for offset in range(N_SPLITS):
        seed = BASE_SEED + offset
        _, validation = stratified_split(train, seed, VALIDATION_FRACTION)
        truth = validation["final_risk"].to_numpy(dtype=np.float64)
        ids = validation["series_id"]

        arm_values = ids.map(arm).to_numpy(dtype=np.float64)
        reference_values = ids.map(reference).to_numpy(dtype=np.float64)
        if not np.isfinite(arm_values).all() or not np.isfinite(reference_values).all():
            raise RuntimeError(f"{label} seed {seed}: non-finite predictions")

        a = kelvins_score(truth, arm_values)
        b = kelvins_score(truth, reference_values)
        rows.append({
            "seed": seed,
            "L_arm": a.score, "L_ref": b.score,
            "f2_arm": a.f2, "f2_ref": b.f2,
            "mse_arm": a.mse_hr, "mse_ref": b.mse_hr,
            "D": a.score - b.score,
        })

    frame = pd.DataFrame(rows)
    finite = np.isfinite(frame["L_arm"]) & np.isfinite(frame["L_ref"])
    usable = frame.loc[finite]
    differences = usable["D"].to_numpy(dtype=np.float64)

    if np.allclose(differences, 0):
        statistic, p_value = 0.0, 1.0
    else:
        statistic, p_value = wilcoxon(differences, alternative="two-sided")
    low, high = bootstrap_median_ci(differences)

    return {
        "comparison": label,
        "splits": N_SPLITS,
        "usable_splits": int(finite.sum()),
        "excluded_non_finite": int((~finite).sum()),
        "median_D": float(np.median(differences)),
        "mean_D": float(differences.mean()),
        "ci95_median_D": [low, high],
        "wilcoxon_statistic": float(statistic),
        "p_value": float(p_value),
        "splits_arm_wins": int((differences < 0).sum()),
        "splits_arm_loses": int((differences > 0).sum()),
        "D_distribution": {
            "min": float(differences.min()),
            "q1": float(np.percentile(differences, 25)),
            "median": float(np.median(differences)),
            "q3": float(np.percentile(differences, 75)),
            "max": float(differences.max()),
            "std": float(differences.std(ddof=1)),
        },
        "L_arm_mean": float(usable["L_arm"].mean()),
        "L_ref_mean": float(usable["L_ref"].mean()),
        "f2_arm_mean": float(usable["f2_arm"].mean()),
        "f2_ref_mean": float(usable["f2_ref"].mean()),
        "mse_arm_mean": float(usable["mse_arm"].mean()),
        "mse_ref_mean": float(usable["mse_ref"].mean()),
        "per_split": rows,
    }


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    started = time.perf_counter()

    train = build_dataset("train")
    v2 = _load("exploratory_v2_predictions.parquet")
    v1 = _load("agent_predictions.parquet")
    b1 = dict(zip(train["series_id"], train["latest_risk"].astype(float)))

    for name, mapping in (("v2", v2), ("v1", v1)):
        missing = set(train["series_id"]) - set(mapping)
        if missing:
            raise RuntimeError(f"{name}: {len(missing)} events have no prediction")

    v2_frame = pd.read_parquet(settings.PROCESSED_DIR / "exploratory_v2_predictions.parquet")
    answered = v2_frame.loc[v2_frame["agent_answered"].fillna(False)]

    # An unanswered in-scope event silently falls back to B1, so a *partial* run produces
    # a comparison that looks valid and means nothing. What matters is whether the run
    # finished, not what fraction the model happened to answer: an event the model tried
    # and failed on is a property of the arm and belongs in the comparison, whereas an
    # event never attempted is missing data.
    run_report_path = settings.PROCESSED_DIR / "exploratory_v2_run_report.json"
    if not run_report_path.is_file():
        raise RuntimeError(f"{run_report_path} missing; run the v2 runner first")
    run_report = json.loads(run_report_path.read_text(encoding="utf-8"))

    in_scope_total = int(v2_frame["in_scope"].sum())
    attempted = int(run_report["analysed"]) + int(run_report["n_failures"])
    if attempted != in_scope_total:
        raise RuntimeError(
            f"the v2 run is incomplete: {attempted} of {in_scope_total} in-scope events "
            "were attempted. Unattempted events fall back to B1 and would make this "
            "comparison meaningless. Finish scripts/exploratory_run_agent_v2.py first."
        )
    coverage = len(answered) / max(in_scope_total, 1)

    revision_rate = float(answered["revised"].mean()) if len(answered) else float("nan")

    # Win/loss on the answers v2 actually changed.
    labels = dict(zip(train["series_id"], train["final_risk"].astype(float)))
    changed = answered.loc[answered["revised"]]
    truth = changed["series_id"].map(labels).to_numpy(dtype=float)
    helped = hurt = 0
    if len(changed):
        base_error = np.abs(changed["b1_risk"].to_numpy(dtype=float) - truth)
        arm_error = np.abs(changed["agent_prediction"].to_numpy(dtype=float) - truth)
        helped = int((arm_error < base_error).sum())
        hurt = int((arm_error > base_error).sum())

    report = {
        "EXPLORATORY": True,
        "primary_result_unchanged": (
            "docs/PHASE7_REPORT.md: agent L = 1.6606 vs B1 0.6940, median D = +0.9462. "
            "This comparison cannot replace it."
        ),
        "protocol": {
            "splits": N_SPLITS,
            "seeds": [BASE_SEED + i for i in range(N_SPLITS)],
            "note": "same seeds and machinery as the primary comparison",
            "alpha": ALPHA,
            "minimum_important_difference": MINIMUM_IMPORTANT_DIFFERENCE,
        },
        "v2_behaviour": {
            "in_scope_events": in_scope_total,
            "events_answered": int(len(answered)),
            "events_failed": int(run_report["n_failures"]),
            "answer_coverage": round(coverage, 4),
            "coverage_note": (
                "Events the model failed to answer (all truncated at max_output_tokens) "
                "fall back to B1 unchanged, which is what an operational system would do. "
                "They are counted, not dropped."
            ),
            "events_revised": int(answered["revised"].sum()),
            "revision_rate": round(revision_rate, 4),
            "v1_revision_rate_for_comparison": 0.997,
            "changed_helped": helped,
            "changed_hurt": hurt,
            "win_loss_ratio": round(helped / hurt, 3) if hurt else None,
            "v1_win_loss_ratio_for_comparison": 1.147,
        },
        "v2_vs_b1": paired(train, v2, b1, "v2 vs B1"),
        "v2_vs_v1": paired(train, v2, v1, "v2 vs v1"),
        "v1_vs_b1_rederived": paired(train, v1, b1, "v1 vs B1 (re-derived)"),
        "wall_time_seconds": round(time.perf_counter() - started, 1),
    }

    destination = settings.PROCESSED_DIR / "exploratory_v2_comparison.json"
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")

    behaviour = report["v2_behaviour"]
    print("EXPLORATORY — the primary result in PHASE7_REPORT.md is unchanged.\n")
    print(
        f"v2 revision rate: {100 * behaviour['revision_rate']:.1f}% "
        f"({behaviour['events_revised']} of {behaviour['events_answered']}) "
        f"— v1 was 99.7%"
    )
    print(
        f"v2 win/loss on changed answers: {behaviour['changed_helped']}/"
        f"{behaviour['changed_hurt']} = {behaviour['win_loss_ratio']} — v1 was 1.147\n"
    )
    for key in ("v2_vs_b1", "v2_vs_v1", "v1_vs_b1_rederived"):
        block = report[key]
        print(f"=== {block['comparison']} ===")
        print(
            f"  median D {block['median_D']:+.4f}  "
            f"CI [{block['ci95_median_D'][0]:+.4f}, {block['ci95_median_D'][1]:+.4f}]  "
            f"p = {block['p_value']:.3e}"
        )
        print(
            f"  wins {block['splits_arm_wins']}/{block['usable_splits']}, "
            f"L {block['L_arm_mean']:.4f} vs {block['L_ref_mean']:.4f} | "
            f"F2 {block['f2_arm_mean']:.4f} vs {block['f2_ref_mean']:.4f} | "
            f"MSE_HR {block['mse_arm_mean']:.4f} vs {block['mse_ref_mean']:.4f}"
        )
    print(f"\n-> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
