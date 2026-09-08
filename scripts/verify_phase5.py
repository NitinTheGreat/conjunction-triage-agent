"""End-to-end verification of Phase 5.

Prints one pass/fail line per check and exits non-zero if any fails. Every check treats a
*vacuous* pass — zero events, zero features, zero comparisons — as a failure.

    python scripts/verify_phase5.py
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from core.config import settings  # noqa: E402
from core.evaluation import (  # noqa: E402
    TASK,
    classification_metrics,
    ndcg,
    precision_at_k,
    regression_metrics,
    spearman,
)
from core.features import FEATURE_COLUMNS, build_dataset  # noqa: E402
from core.kelvins_metric import (  # noqa: E402
    HIGH_RISK_THRESHOLD,
    clip_predictions,
    kelvins_score,
)
from verify_phase1 import CheckFailure  # noqa: E402

#: Code that must never touch the test split.
TRAINING_CODE = ("run_baselines.py", "error_analysis.py")


# -- 1 ---------------------------------------------------------------------------------

def check_official_metric() -> str:
    """The official metric reproduces a hand-computed value on a synthetic case.

    Four events, two of them truly high-risk::

        truth  = [-5.0, -7.0, -4.0, -10.0]
        pred   = [-5.5, -5.0, -4.0, -20.0]  ->  clipped [-5.5, -5.0, -4.0, -6.001]

    true high = [T, F, T, F];  predicted high = [T, T, T, F]
    tp = 2, fp = 1, fn = 0  ->  precision 2/3, recall 1  ->  F2 = 5pr/(4p+r) = 10/11
    MSE_HR over the two true high-risk events = (0.5^2 + 0^2) / 2 = 0.125
    L = 0.125 / (10/11) = 0.1375
    """
    truth = np.array([-5.0, -7.0, -4.0, -10.0])
    predictions = np.array([-5.5, -5.0, -4.0, -20.0])

    clipped = clip_predictions(predictions)
    if not np.isclose(clipped[3], -6.001):
        raise CheckFailure(f"clipping wrong: got {clipped[3]}, expected -6.001")

    result = kelvins_score(truth, predictions)
    expected_f2 = 10 / 11
    expected_mse = 0.125
    expected_l = expected_mse / expected_f2

    for label, got, want in (
        ("F2", result.f2, expected_f2),
        ("MSE_HR", result.mse_hr, expected_mse),
        ("L", result.score, expected_l),
    ):
        if not np.isclose(got, want, rtol=1e-12, atol=0):
            raise CheckFailure(f"{label}: got {got!r}, hand-computed {want!r}")
    return (
        f"hand-computed case exact: F2={expected_f2:.6f}, MSE_HR={expected_mse}, "
        f"L={expected_l:.6f}"
    )


# -- 2 ---------------------------------------------------------------------------------

def check_degenerate_behaviour() -> str:
    """Metrics behave correctly on perfect, random and constant predictions."""
    rng = np.random.default_rng(20260819)
    truth = np.concatenate([rng.uniform(-30, -6.5, 900), rng.uniform(-6, -3, 100)])

    perfect = kelvins_score(truth, truth)
    if perfect.score != 0.0:
        raise CheckFailure(f"perfect prediction scored {perfect.score}, expected 0")
    if not np.isclose(perfect.f2, 1.0):
        raise CheckFailure(f"perfect prediction F2 = {perfect.f2}, expected 1")

    if not np.isclose(spearman(truth, truth), 1.0):
        raise CheckFailure("spearman of a perfect ranking is not 1")
    if not np.isclose(spearman(truth, -truth), -1.0):
        raise CheckFailure("spearman of a reversed ranking is not -1")
    if not np.isclose(ndcg(truth, truth), 1.0):
        raise CheckFailure("NDCG of a perfect ranking is not 1")

    shuffled = rng.permutation(truth)
    random_rho = spearman(truth, shuffled)
    if abs(random_rho) > 0.15:
        raise CheckFailure(f"random ranking scored rho={random_rho:.3f}, expected ~0")

    if precision_at_k(truth, truth, 10) != 1.0:
        raise CheckFailure("precision@10 of a perfect ranking is not 1")
    if precision_at_k(truth, -truth, 10) != 0.0:
        raise CheckFailure("precision@10 of a reversed ranking is not 0")

    # A constant prediction has no ranking information: rho is undefined, not zero.
    constant = spearman(truth, np.zeros_like(truth))
    if not np.isnan(constant):
        raise CheckFailure(f"constant prediction gave rho={constant}, expected NaN")

    # Predicting everything low-risk means F2 = 0 and an infinite score.
    all_low = kelvins_score(truth, np.full(truth.size, -30.0))
    if all_low.f2 != 0.0 or np.isfinite(all_low.score):
        raise CheckFailure(
            f"all-low-risk prediction scored {all_low.score} with F2={all_low.f2}; "
            "expected F2=0 and an infinite score"
        )
    return (
        f"perfect L=0 F2=1; reversed rho=-1; random rho={random_rho:+.4f}; "
        "constant rho undefined; all-low-risk L=inf"
    )


# -- 3 ---------------------------------------------------------------------------------

def check_counterfactual_invariance() -> str:
    """Post-cutoff data must not move a model input. Run the actual invariance test.

    Added in Phase 11 after an external audit. ``check_no_leakage`` below checks the
    *timing* of the latest visible CDM and the *names* of the label columns, and both were
    satisfied while ``n_cdms_total`` and ``last_cdm_days`` were aggregating over the entire
    sequence and being returned as features. Neither a timing check nor a name check can
    see that; only mutating the future and watching the inputs can.

    Delegates to ``tests/test_causal_features.py`` rather than reimplementing it, so the
    guard and the test cannot drift apart.
    """
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "tests/test_causal_features.py"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    lines = (completed.stdout or completed.stderr).strip().splitlines()
    summary = lines[-1] if lines else "(no output)"
    if completed.returncode != 0:
        raise CheckFailure(f"the counterfactual invariance test failed: {summary}")
    match = re.search(r"(\d+) passed", summary)
    if not match or int(match.group(1)) < 8:
        raise CheckFailure(
            f"only {match.group(1) if match else 0} invariance tests ran; expected the "
            "full both-directions suite"
        )
    return (
        f"{match.group(1)} counterfactual invariance tests pass: the test fires on "
        "core/features.py and is silent on core/features_causal.py"
    )


def check_no_leakage() -> str:
    """No feature is computed from a CDM inside the 2-day cutoff.

    Kept exactly as Phase 5 wrote it. It is necessary and was never sufficient: see
    ``check_counterfactual_invariance``, which catches what this cannot.
    """
    cutoff = TASK.input_cutoff_days
    parts = []
    for split in ("train", "test"):
        frame = build_dataset(split)
        if frame.empty:
            raise CheckFailure(f"{split}: no events built")

        violations = int((frame["latest_time_to_tca"] < cutoff).sum())
        if violations:
            raise CheckFailure(
                f"{split}: {violations} events have a visible CDM inside {cutoff} days"
            )
        if float(frame["latest_time_to_tca"].min()) < cutoff:
            raise CheckFailure(f"{split}: minimum visible time_to_tca is below the cutoff")

        # The label must never appear among the features.
        for column in FEATURE_COLUMNS:
            if column in {"final_risk", "final_risk_is_floored", "is_high_risk"}:
                raise CheckFailure(f"{split}: label column {column} is exposed as a feature")

        # The label genuinely differs from the latest visible risk, or the task is trivial.
        identical = float(np.mean(
            np.isclose(frame["final_risk"], frame["latest_risk"])
        ))
        if identical > 0.99:
            raise CheckFailure(
                f"{split}: {identical:.1%} of labels equal the latest visible risk — "
                "the label may have leaked into the input window"
            )
        parts.append(
            f"{split} {len(frame):,} events, min visible ttc "
            f"{frame['latest_time_to_tca'].min():.4f}d, "
            f"{identical:.1%} labels equal latest"
        )
    return "; ".join(parts)


# -- 4 ---------------------------------------------------------------------------------

def check_splits_disjoint() -> str:
    """Train and validation splits are disjoint by series_id."""
    from run_baselines import stratified_split

    train = build_dataset("train")
    checked = 0
    for seed in (20260819, 20260820, 20260821):
        fit, validation = stratified_split(train, seed, 0.25)
        overlap = set(fit["series_id"]) & set(validation["series_id"])
        if overlap:
            raise CheckFailure(f"seed {seed}: {len(overlap)} series_id in both splits")
        if len(fit) + len(validation) != len(train):
            raise CheckFailure(f"seed {seed}: splits do not partition the train set")
        if validation["is_high_risk"].sum() == 0:
            raise CheckFailure(f"seed {seed}: validation has no high-risk events")
        checked += 1
    if checked == 0:
        raise CheckFailure("no splits checked")
    return f"{checked} seeds: partitions are disjoint and each holds high-risk events"


# -- 5 ---------------------------------------------------------------------------------

def check_test_untouched() -> str:
    """No training or selection code path reads the test split.

    Checked statically by parsing the training scripts for any call that names the test
    split, and dynamically by confirming the recorded results say it was not read.
    """
    offenders: list[str] = []
    for name in TRAINING_CODE:
        path = REPO_ROOT / "scripts" / name
        if not path.is_file():
            raise CheckFailure(f"{name} is missing")
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            function = node.func
            called = getattr(function, "id", None) or getattr(function, "attr", None)
            if called not in {"build_dataset", "eligibility_report"}:
                continue
            for argument in list(node.args) + [kw.value for kw in node.keywords]:
                if isinstance(argument, ast.Constant) and argument.value == "test":
                    offenders.append(f"{name}:{node.lineno} {called}('test')")
        # A direct read of the test parquet would bypass build_dataset entirely.
        for match in re.finditer(r"""["'][^"']*(cdms_test|series_test|test_data)[^"']*["']""", source):
            offenders.append(f"{name}: references {match.group(0)}")

    if offenders:
        raise CheckFailure("training code touches the test split: " + "; ".join(offenders))

    results = settings.PROCESSED_DIR / "baseline_results.json"
    if not results.is_file():
        raise CheckFailure("baseline_results.json missing; run scripts/run_baselines.py")
    recorded = json.loads(results.read_text(encoding="utf-8"))
    if recorded.get("test_set_read") is not False:
        raise CheckFailure("baseline_results.json does not record test_set_read = false")
    return (
        f"{len(TRAINING_CODE)} training scripts parsed, zero references to the test "
        "split; results record test_set_read = false"
    )


# -- 6 ---------------------------------------------------------------------------------

def check_single_cdm_indicator() -> str:
    """Single-CDM events carry a missing indicator rather than an imputed zero."""
    parts = []
    for split in ("train", "test"):
        frame = build_dataset(split)
        single = frame["has_trend"] == 0
        count = int(single.sum())
        if count == 0:
            raise CheckFailure(f"{split}: no single-CDM events found (trivial pass guard)")
        if int((frame.loc[single, "n_cdms_input"] != 1).sum()):
            raise CheckFailure(f"{split}: has_trend=0 does not mean exactly one CDM")

        for column in ("slope_risk", "delta_risk", "std_risk"):
            values = frame.loc[single, column]
            if not values.isna().all():
                zeros = int((values == 0).sum())
                raise CheckFailure(
                    f"{split}: {column} is not NaN for all single-CDM events "
                    f"({zeros} are exactly 0 — an imputed zero asserts stability)"
                )
        # And the indicator must be informative, not constant.
        if int((frame["has_trend"] == 1).sum()) == 0:
            raise CheckFailure(f"{split}: has_trend is constant")
        parts.append(f"{split} {count} single-CDM events, slopes NaN")
    return "; ".join(parts)


# -- 7 ---------------------------------------------------------------------------------

def check_censoring_handled() -> str:
    """Censored and uncensored events are treated distinctly by the metrics."""
    truth = np.array([-30.0, -30.0, -30.0, -5.0, -4.0])
    predictions = np.array([-30.0, -20.0, -10.0, -5.0, -4.0])

    regression = regression_metrics(truth, predictions)
    if regression["n_censored"] != 3 or regression["n_uncensored"] != 2:
        raise CheckFailure(
            f"censored split wrong: {regression['n_censored']} censored, "
            f"{regression['n_uncensored']} uncensored, expected 3 and 2"
        )
    # The uncensored predictions are exact, so RMSE over uncensored must be 0 while the
    # all-inclusive figure is not — proving the two are genuinely computed separately.
    if regression["rmse_uncensored"] != 0.0:
        raise CheckFailure(
            f"RMSE over uncensored events is {regression['rmse_uncensored']}, expected 0"
        )
    if regression["rmse_all_including_censored"] == 0.0:
        raise CheckFailure(
            "RMSE including censored events is 0, so censoring is not being separated"
        )

    # The official metric must ignore censored events entirely in its regression term.
    baseline = kelvins_score(truth, predictions)
    moved = predictions.copy()
    moved[0] = -12.0  # change a censored event's prediction only
    after = kelvins_score(truth, moved)
    if not np.isclose(baseline.mse_hr, after.mse_hr):
        raise CheckFailure("MSE_HR changed when only a censored prediction moved")
    return (
        f"3 censored / 2 uncensored separated; RMSE(uncensored)=0 while "
        f"RMSE(all)={regression['rmse_all_including_censored']:.3f}; MSE_HR ignores "
        "censored events"
    )


# -- 8 ---------------------------------------------------------------------------------

def check_pytest() -> str:
    """pytest passes."""
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    lines = (completed.stdout or completed.stderr).strip().splitlines()
    line = lines[-1] if lines else "(no output)"
    if completed.returncode != 0:
        raise CheckFailure(f"pytest exited {completed.returncode}: {line}")
    match = re.search(r"(\d+) passed", line)
    if not match or int(match.group(1)) == 0:
        raise CheckFailure(f"pytest reported no passing tests: {line}")
    return f"pytest: {line}"


# -- 9 (addition) ----------------------------------------------------------------------

def check_baselines_recorded() -> str:
    """Baseline results exist, cover several seeds, and record their spread."""
    path = settings.PROCESSED_DIR / "baseline_results.json"
    if not path.is_file():
        raise CheckFailure("baseline_results.json missing")
    report = json.loads(path.read_text(encoding="utf-8"))

    if len(report.get("seeds", [])) < 3:
        raise CheckFailure(
            f"only {len(report.get('seeds', []))} seeds; at least 3 are needed to "
            "estimate run-to-run spread"
        )
    summary = report.get("summary") or {}
    if "B1_latest_cdm" not in summary:
        raise CheckFailure("the primary baseline B1 is missing from the results")

    b1 = summary["B1_latest_cdm"]["L"]
    if not np.isfinite(b1["mean"]):
        raise CheckFailure("B1 has no finite score")
    if b1["std"] <= 0:
        raise CheckFailure(
            "B1's spread across seeds is zero, so the noise floor cannot be assessed"
        )
    beaten = [
        name for name, entry in summary.items()
        if name != "B1_latest_cdm" and np.isfinite(entry["L"]["mean"])
        and entry["L"]["mean"] < b1["mean"]
    ]
    return (
        f"{len(report['seeds'])} seeds; B1 L = {b1['mean']:.4f} +/- {b1['std']:.4f}; "
        f"{len(beaten)} baseline(s) beat it"
    )


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()

    checks: list[tuple[str, Callable[[], str]]] = [
        ("official metric reproduces a hand-computed value", check_official_metric),
        ("metrics behave on degenerate inputs", check_degenerate_behaviour),
        ("no feature comes from inside the 2-day cutoff", check_no_leakage),
        ("post-cutoff data cannot move a model input", check_counterfactual_invariance),
        ("train/validation splits are disjoint", check_splits_disjoint),
        ("the test set is not read by training code", check_test_untouched),
        ("single-CDM events carry a missing indicator", check_single_cdm_indicator),
        ("censored and uncensored handled distinctly", check_censoring_handled),
        ("pytest passes", check_pytest),
        ("baseline results record spread across seeds (addition)", check_baselines_recorded),
    ]

    print(f"Phase 5 verification -- {REPO_ROOT}\n")
    failures = 0
    for number, (title, check) in enumerate(checks, start=1):
        try:
            detail = check()
        except Exception as exc:
            failures += 1
            print(f"[FAIL] {number}. {title}")
            print(f"        {type(exc).__name__}: {exc}")
        else:
            print(f"[PASS] {number}. {title}")
            print(f"        {detail}")

    total = len(checks)
    print(f"\n{total - failures}/{total} checks passed.")
    if failures:
        print(f"{failures} FAILED -- Phase 5 is not complete.")
        return 1
    print("Phase 5 verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
