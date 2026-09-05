"""Confirm or refute the three-part diagnosis of why the agent lost. No LLM calls.

Nothing is built on this diagnosis until it has been checked. Each of the three claimed
failures is stated as something that could come out false, and §3 in particular is designed
so that a refutation is visible rather than absorbed.

    python scripts/diagnose_failure.py

A note on the test split
------------------------
§3 reads **test labels**, to compare the agent's disposition across the two prevalences.
That is analysis of the already-published Phase 7 artefact, not a new scoring run: no arm is
scored, and no number produced here may be used to fit or tune anything. The Phase 11
pre-registration records that, and ``verify_phase11.py`` check 3 asserts the hybrid's
decision threshold was selected without any test label.
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

from core.config import settings  # noqa: E402
from core.features import build_dataset  # noqa: E402
from core.kelvins_metric import (  # noqa: E402
    BETA,
    CLIP_EPSILON,
    HIGH_RISK_THRESHOLD,
    kelvins_score,
)
from run_baselines import stratified_split  # noqa: E402

BASE_SEED = 20260819
N_SPLITS = 50
VALIDATION_FRACTION = 0.25

#: The only two values a cost-aware action space can emit. Anything else changes MSE_HR
#: without changing the classification, which §1 tests the consequences of.
CLIP_FLOOR = HIGH_RISK_THRESHOLD - CLIP_EPSILON


def _peak_memory_mb() -> float:
    import psutil

    info = psutil.Process().memory_info()
    return getattr(info, "peak_wset", info.rss) / 1024**2


def _clip(values: np.ndarray) -> np.ndarray:
    return np.where(values < HIGH_RISK_THRESHOLD, CLIP_FLOOR, values)


def load_arms() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Train and test events, each joined to the cached v1 predictions."""
    train = build_dataset("train")
    predictions = pd.read_parquet(settings.PROCESSED_DIR / "agent_predictions.parquet")
    train = train.merge(
        predictions[["series_id", "agent_prediction", "agent_analysed", "will_collapse",
                     "confidence", "n_citations", "in_scope"]],
        on="series_id", how="left", validate="one_to_one",
    )

    test = build_dataset("test")
    test_predictions = pd.read_parquet(
        settings.PROCESSED_DIR / "agent_predictions_test.parquet"
    )
    # The test artefact has its label columns stripped -- that was the Phase 7 guard against
    # the agent reading the answer while predicting. Labels come from build_dataset here.
    test = test.merge(
        test_predictions[["series_id", "agent_prediction", "agent_analysed",
                          "will_collapse", "confidence", "n_citations", "in_scope"]],
        on="series_id", how="left", validate="one_to_one",
    )
    for frame in (train, test):
        frame["agent_analysed"] = frame["agent_analysed"].fillna(False).astype(bool)
        frame["in_scope"] = frame["in_scope"].fillna(False).astype(bool)
        frame["effective"] = np.where(
            frame["agent_analysed"], frame["agent_prediction"], frame["latest_risk"]
        )
    return train, test


# ------------------------------------------------------------------------------------
# (a) action space
# ------------------------------------------------------------------------------------

def classify_revisions(frame: pd.DataFrame) -> pd.Series:
    """Every revision as one of three kinds, by what it does to the -6 threshold."""
    baseline_high = frame["latest_risk"] >= HIGH_RISK_THRESHOLD
    agent_high = frame["effective"] >= HIGH_RISK_THRESHOLD
    moved = np.abs(frame["effective"] - frame["latest_risk"]) > 1e-12

    kind = pd.Series("none", index=frame.index, dtype=object)
    kind[moved & baseline_high & ~agent_high] = "downgrade_across"
    kind[moved & ~baseline_high & agent_high] = "upgrade_across"
    kind[moved & (baseline_high == agent_high)] = "value_change_no_crossing"
    return kind


def action_space_analysis(train: pd.DataFrame) -> dict[str, Any]:
    """What each class of revision did to MSE_HR, F2 and L, applied on its own."""
    kinds = classify_revisions(train)
    truth = train["final_risk"].to_numpy(dtype=np.float64)
    baseline = train["latest_risk"].to_numpy(dtype=np.float64)
    effective = train["effective"].to_numpy(dtype=np.float64)

    reference = kelvins_score(truth, baseline)
    classes: dict[str, Any] = {}

    for name in ("downgrade_across", "upgrade_across", "value_change_no_crossing"):
        mask = (kinds == name).to_numpy()
        count = int(mask.sum())
        if count == 0:
            classes[name] = {"count": 0}
            continue

        # Apply only this class of revision, leaving every other event on the baseline.
        isolated = baseline.copy()
        isolated[mask] = effective[mask]
        score = kelvins_score(truth, isolated)

        high_risk = truth >= HIGH_RISK_THRESHOLD
        on_high_risk = int((mask & high_risk).sum())
        classes[name] = {
            "count": count,
            "on_true_high_risk": on_high_risk,
            "on_true_low_risk": count - on_high_risk,
            "correct": (
                # A downgrade is correct on a truly low-risk event; an upgrade on a truly
                # high-risk one; a value change has no classification content at all.
                count - on_high_risk if name == "downgrade_across"
                else on_high_risk if name == "upgrade_across" else None
            ),
            "L": float(score.score),
            "delta_L": float(score.score - reference.score),
            "delta_mse_hr": float(score.mse_hr - reference.mse_hr),
            "delta_f2": float(score.f2 - reference.f2),
            "net_effect": (
                "harmful" if score.score > reference.score
                else "helpful" if score.score < reference.score else "neutral"
            ),
        }

    everything = kelvins_score(truth, effective)
    total = float(everything.score - reference.score)
    for block in classes.values():
        if block.get("count"):
            block["share_of_total_harm"] = (
                block["delta_L"] / total if total else float("nan")
            )
    return {
        "population": "train, all 8,293 events; B1 elsewhere",
        "baseline": {
            "L": float(reference.score), "mse_hr": float(reference.mse_hr),
            "f2": float(reference.f2),
        },
        "agent_all_revisions": {
            "L": float(everything.score), "delta_L": float(everything.score - reference.score),
            "mse_hr": float(everything.mse_hr), "f2": float(everything.f2),
        },
        "by_class": classes,
        "revisions_total": int((kinds != "none").sum()),
    }


# ------------------------------------------------------------------------------------
# (b) cost asymmetry
# ------------------------------------------------------------------------------------

def minimum_downgrade_precision(
    frame: pd.DataFrame, label: str
) -> dict[str, Any]:
    """The precision at which one more downgrade stops being net-harmful.

    Marginal analysis on the actual operating point. A single downgrade is either correct
    (a true low-risk event leaves the predicted-positive set: FP falls by one, MSE_HR
    untouched because the event is not in the high-risk set) or incorrect (a true high-risk
    event: TP falls, FN rises, *and* its squared error grows from near zero to (t + 6.001)^2).

    Both terms of L = MSE_HR / F2 move against an incorrect downgrade, so the break-even
    precision is strictly higher than the F2-only condition p > 1 - F2/5.
    """
    truth = frame["final_risk"].to_numpy(dtype=np.float64)
    baseline = _clip(frame["latest_risk"].to_numpy(dtype=np.float64))
    high_risk = truth >= HIGH_RISK_THRESHOLD
    predicted_high = baseline >= HIGH_RISK_THRESHOLD

    tp = int(np.sum(high_risk & predicted_high))
    fp = int(np.sum(~high_risk & predicted_high))
    fn = int(np.sum(high_risk & ~predicted_high))
    n_star = int(high_risk.sum())
    mse = float(np.sum((truth[high_risk] - baseline[high_risk]) ** 2) / n_star)
    denominator = (1 + BETA**2) * tp + BETA**2 * fn + fp
    f2 = (1 + BETA**2) * tp / denominator if denominator else 0.0
    loss = mse / f2 if f2 else float("inf")

    # A correct downgrade: one FP removed.
    f2_correct = (1 + BETA**2) * tp / (denominator - 1)
    delta_correct = mse / f2_correct - loss

    # An incorrect downgrade: the mean penalty over the true high-risk events that are
    # currently predicted high, since those are the ones a downgrade can hit.
    at_risk = high_risk & predicted_high
    penalty = float(np.mean(
        (truth[at_risk] - CLIP_FLOOR) ** 2 - (truth[at_risk] - baseline[at_risk]) ** 2
    )) if at_risk.any() else 0.0
    f2_incorrect = (
        (1 + BETA**2) * (tp - 1)
        / ((1 + BETA**2) * (tp - 1) + BETA**2 * (fn + 1) + fp)
    )
    delta_incorrect = (mse + penalty / n_star) / f2_incorrect - loss

    # E[dL] = p * delta_correct + (1-p) * delta_incorrect < 0
    spread = delta_incorrect - delta_correct
    p_min = delta_incorrect / spread if spread > 0 else float("nan")

    return {
        "population": label,
        "n_events": int(len(frame)),
        "n_star_true_high_risk": n_star,
        "prevalence": float(high_risk.mean()),
        "confusion_at_baseline": {"tp": tp, "fp": fp, "fn": fn},
        "baseline": {"L": loss, "mse_hr": mse, "f2": f2},
        "mean_mse_penalty_of_an_incorrect_downgrade": penalty,
        "delta_L_correct_downgrade": delta_correct,
        "delta_L_incorrect_downgrade": delta_incorrect,
        "harm_to_benefit_ratio": (
            abs(delta_incorrect / delta_correct) if delta_correct else float("inf")
        ),
        "minimum_downgrade_precision": p_min,
        "f2_only_condition": 1 - f2 / (1 + BETA**2),
        "note": (
            "The F2-only condition p > 1 - F2/5 ignores MSE_HR. Since an incorrect "
            "downgrade also enlarges the squared error, the true break-even precision is "
            "higher."
        ),
    }


# ------------------------------------------------------------------------------------
# (c) base-rate shift
# ------------------------------------------------------------------------------------

def downgrade_behaviour(frame: pd.DataFrame, label: str) -> dict[str, Any]:
    """The agent's downgrade disposition, in prevalence-free and prevalence-bound terms."""
    scope = frame[frame["agent_analysed"]].copy()
    truth_high = (scope["final_risk"] >= HIGH_RISK_THRESHOLD).to_numpy()
    baseline_high = (scope["latest_risk"] >= HIGH_RISK_THRESHOLD).to_numpy()
    agent_high = (scope["effective"] >= HIGH_RISK_THRESHOLD).to_numpy()
    downgraded = baseline_high & ~agent_high

    # Only events the baseline calls high-risk can be downgraded at all.
    eligible = baseline_high
    correct = downgraded & ~truth_high
    incorrect = downgraded & truth_high

    n_down = int(downgraded.sum())
    prevalence = float(truth_high.mean())
    # The prevalence that governs downgrade precision is the one among events the baseline
    # actually calls high-risk -- only those can be downgraded. Using the in-scope
    # prevalence instead would mix in events that were never eligible, and the
    # prevalence-shift prediction below would be comparing incompatible quantities.
    eligible_prevalence = (
        float(truth_high[eligible].mean()) if eligible.any() else float("nan")
    )
    # Prevalence-free: what the agent does given the truth. These are the disposition.
    sensitivity = (
        float(np.sum(correct) / np.sum(eligible & ~truth_high))
        if np.any(eligible & ~truth_high) else float("nan")
    )
    leakage = (
        float(np.sum(incorrect) / np.sum(eligible & truth_high))
        if np.any(eligible & truth_high) else float("nan")
    )
    return {
        "population": label,
        "in_scope_analysed": int(len(scope)),
        "in_scope_high_risk": int(truth_high.sum()),
        "in_scope_prevalence": prevalence,
        "eligible_for_downgrade": int(eligible.sum()),
        "eligible_prevalence": eligible_prevalence,
        "eligible_high_risk": int(np.sum(eligible & truth_high)),
        "downgrades": n_down,
        "downgrade_rate": n_down / int(eligible.sum()) if eligible.any() else float("nan"),
        "downgrade_precision": float(np.sum(correct) / n_down) if n_down else float("nan"),
        "downgrade_recall_on_true_low_risk": sensitivity,
        # P(downgrade | truly high-risk) -- the disposition's error rate on the class that
        # must not be downgraded. Prevalence-free, so it is comparable across populations.
        "downgrade_rate_on_true_high_risk": leakage,
        "downgrade_rate_on_true_low_risk": sensitivity,
    }


def predicted_precision(sensitivity: float, leakage: float, prevalence: float) -> float:
    """Precision implied by a fixed disposition at a different prevalence.

    This is the whole diagnosis in one line: hold the agent's behaviour constant and change
    only the base rate. If the number this returns matches the measured test precision, the
    agent did not get worse -- the population did.
    """
    correct = sensitivity * (1 - prevalence)
    incorrect = leakage * prevalence
    return correct / (correct + incorrect) if (correct + incorrect) > 0 else float("nan")


def prevalence_partition(test: pd.DataFrame, train_prevalence: float) -> dict[str, Any]:
    """Split test by local prevalence and see whether the agent tracks it.

    Test in-scope events are binned by their baseline risk -- which the agent sees and which
    is not a label -- and each bin's high-risk prevalence is measured. If the agent's
    downgrade precision follows the bin prevalence, the diagnosis holds. If precision is
    flat across bins of very different prevalence, it does not, and this is where that would
    show.
    """
    # Only events the baseline calls high-risk. Including the rest would put events that
    # could never be downgraded into the low-prevalence bins, which is what made the first
    # version of this partition show an empty bin rather than a comparison.
    scope = test[
        test["agent_analysed"] & (test["latest_risk"] >= HIGH_RISK_THRESHOLD)
    ].copy()
    scope["truth_high"] = scope["final_risk"] >= HIGH_RISK_THRESHOLD
    scope["downgraded"] = scope["effective"] < HIGH_RISK_THRESHOLD
    edges = np.quantile(scope["latest_risk"], [0, 0.25, 0.5, 0.75, 1.0])
    edges[-1] += 1e-9
    scope["bin"] = pd.cut(scope["latest_risk"], bins=np.unique(edges),
                          include_lowest=True, duplicates="drop")

    bins = []
    for interval, group in scope.groupby("bin", observed=True):
        downgrades = int(group["downgraded"].sum())
        correct = int((group["downgraded"] & ~group["truth_high"]).sum())
        bins.append({
            "baseline_risk_range": str(interval),
            "n": int(len(group)),
            "prevalence": float(group["truth_high"].mean()),
            "downgrades": downgrades,
            "downgrade_precision": correct / downgrades if downgrades else None,
        })

    usable = [b for b in bins if b["downgrade_precision"] is not None and b["downgrades"] >= 5]
    if len(usable) >= 2:
        prevalences = np.array([b["prevalence"] for b in usable])
        precisions = np.array([b["downgrade_precision"] for b in usable])
        correlation = float(np.corrcoef(prevalences, precisions)[0, 1])
    else:
        correlation = float("nan")

    closest = min(bins, key=lambda b: abs(b["prevalence"] - train_prevalence)) if bins else None
    prevalence_span = (
        max(b["prevalence"] for b in usable) - min(b["prevalence"] for b in usable)
        if usable else float("nan")
    )
    return {
        "bins": bins,
        "correlation_prevalence_vs_precision": correlation,
        "expected_sign": "negative",
        "expected_sign_reason": (
            "higher prevalence leaves fewer true low-risk events for a downgrade to catch"
        ),
        "observed_sign": (
            "negative" if correlation < 0 else "positive" if correlation > 0 else "flat"
        ),
        "agrees_with_expectation": bool(correlation < 0),
        "usable_bins": len(usable),
        "prevalence_span_across_usable_bins": prevalence_span,
        "powered": bool(len(usable) >= 3 and prevalence_span > 0.25),
        "caveat": (
            "This within-test partition is underpowered and is NOT the decisive test. Test "
            "eligible events span a narrow prevalence range and each bin carries only "
            "tens of downgrades, so the correlation is dominated by sampling noise. The "
            "cross-population comparison -- train disposition applied at the test "
            "prevalence -- is the test that decides the diagnosis, because it spans a "
            "4.3x prevalence shift rather than a fraction of one."
        ),
        "bin_closest_to_train_prevalence": closest,
        "train_prevalence": train_prevalence,
    }


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    started = time.perf_counter()

    train, test = load_arms()
    print(f"train {len(train):,} events, test {len(test):,} events\n")

    # -- (a) ---------------------------------------------------------------------------
    print("== (a) action space ==")
    action = action_space_analysis(train)
    print(f"  B1 on train: L = {action['baseline']['L']:.4f}")
    print(f"  agent, all {action['revisions_total']} revisions applied: "
          f"L = {action['agent_all_revisions']['L']:.4f} "
          f"({action['agent_all_revisions']['delta_L']:+.4f})")
    for name, block in action["by_class"].items():
        if not block.get("count"):
            print(f"  {name:26s} none")
            continue
        print(f"  {name:26s} n={block['count']:4d}  "
              f"dL = {block['delta_L']:+.4f}  "
              f"dMSE = {block['delta_mse_hr']:+.4f}  dF2 = {block['delta_f2']:+.4f}  "
              f"-> {block['net_effect']}")
        print(f"     {' ':24s} {100 * block['share_of_total_harm']:5.1f}% of the total harm"
              + (f", correct {block['correct']}/{block['count']} "
                 f"({100 * block['correct'] / block['count']:.1f}%)"
                 if block["correct"] is not None else ""))

    # -- (b) ---------------------------------------------------------------------------
    print("\n== (b) cost asymmetry ==")
    thresholds = {}
    for label, frame in (("train", train), ("test", test)):
        block = minimum_downgrade_precision(frame, label)
        thresholds[label] = block
        print(f"  {label}: prevalence {100 * block['prevalence']:.2f}%, "
              f"B1 F2 = {block['baseline']['f2']:.4f}")
        print(f"     one correct downgrade   dL = {block['delta_L_correct_downgrade']:+.6f}")
        print(f"     one incorrect downgrade dL = {block['delta_L_incorrect_downgrade']:+.6f}  "
              f"({block['harm_to_benefit_ratio']:.1f}x the benefit)")
        print(f"     MINIMUM DOWNGRADE PRECISION = "
              f"{100 * block['minimum_downgrade_precision']:.2f}%   "
              f"(F2-only condition would say "
              f"{100 * block['f2_only_condition']:.2f}%)")

    # -- (c) ---------------------------------------------------------------------------
    print("\n== (c) base-rate shift ==")
    behaviour = {
        label: downgrade_behaviour(frame, label)
        for label, frame in (("train", train), ("test", test))
    }
    for label, block in behaviour.items():
        print(f"  {label}: in-scope {block['in_scope_analysed']}, "
              f"high-risk {block['in_scope_high_risk']} "
              f"({100 * block['in_scope_prevalence']:.2f}%)")
        print(f"     eligible for downgrade {block['eligible_for_downgrade']}, of which "
              f"{block['eligible_high_risk']} truly high-risk "
              f"({100 * block['eligible_prevalence']:.2f}%)")
        print(f"     downgrades {block['downgrades']}  "
              f"precision {100 * block['downgrade_precision']:.2f}%")
        print(f"     P(downgrade | truly low-risk)  = "
              f"{100 * block['downgrade_rate_on_true_low_risk']:.2f}%")
        print(f"     P(downgrade | truly high-risk) = "
              f"{100 * block['downgrade_rate_on_true_high_risk']:.2f}%")

    shift = predicted_precision(
        behaviour["train"]["downgrade_rate_on_true_low_risk"],
        behaviour["train"]["downgrade_rate_on_true_high_risk"],
        behaviour["test"]["eligible_prevalence"],
    )
    actual = behaviour["test"]["downgrade_precision"]
    print(f"\n  THE DECISIVE TEST -- hold the train disposition fixed, change only prevalence:")
    print(f"     predicted test precision {100 * shift:.2f}%")
    print(f"     actual    test precision {100 * actual:.2f}%")
    print(f"     absolute difference      {100 * abs(shift - actual):.2f} points")

    partition = prevalence_partition(test, behaviour["train"]["eligible_prevalence"])
    print(f"\n  within test, eligible events only, by baseline-risk quartile:")
    for entry in partition["bins"]:
        precision = ("n/a" if entry["downgrade_precision"] is None
                     else f"{100 * entry['downgrade_precision']:.1f}%")
        print(f"     {entry['baseline_risk_range']:26s} n={entry['n']:3d}  "
              f"prevalence {100 * entry['prevalence']:5.1f}%  "
              f"downgrades {entry['downgrades']:3d}  precision {precision}")
    print(f"     correlation(prevalence, precision) = "
          f"{partition['correlation_prevalence_vs_precision']:+.4f}  "
          f"expected {partition['expected_sign']}, observed "
          f"{partition['observed_sign']}"
          f"{'' if partition['agrees_with_expectation'] else '  <- DISAGREES'}")
    if not partition["powered"]:
        print(f"     underpowered: {partition['usable_bins']} usable bins spanning only "
              f"{100 * partition['prevalence_span_across_usable_bins']:.0f} points of "
              f"prevalence; not the decisive test")

    verdicts = {
        "a_wrong_action_space": (
            "CONFIRMED" if (
                action["by_class"].get("value_change_no_crossing", {}).get("delta_L", 0) > 0
            ) else "REFUTED"
        ),
        "b_cost_asymmetry": (
            "CONFIRMED" if thresholds["train"]["minimum_downgrade_precision"] > 0.5
            else "REFUTED"
        ),
        "c_base_rate_shift": (
            "CONFIRMED" if abs(shift - actual) < 0.10 else "REFUTED"
        ),
    }
    print("\n== verdicts ==")
    for name, verdict in verdicts.items():
        print(f"  {name:24s} {verdict}")

    report = {
        "action_space": action,
        "cost_asymmetry": thresholds,
        "base_rate": {
            "behaviour": behaviour,
            "predicted_test_precision_from_train_disposition": shift,
            "actual_test_precision": actual,
            "absolute_difference": abs(shift - actual),
            "partition": partition,
        },
        "verdicts": verdicts,
        "test_labels_used": (
            "Yes, for diagnosis only. No arm was scored on test here and no number from "
            "this file may be used to fit or tune the hybrid; verify_phase11 check 3 "
            "asserts the decision threshold saw no test label."
        ),
        "elapsed_seconds": round(time.perf_counter() - started, 1),
        "peak_memory_mb": round(_peak_memory_mb(), 1),
    }
    destination = settings.PROCESSED_DIR / "failure_diagnosis.json"
    destination.write_text(json.dumps(report, indent=2, default=float), encoding="utf-8")
    print(f"\npeak memory {report['peak_memory_mb']} MB -> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
