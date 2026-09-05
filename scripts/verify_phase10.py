"""End-to-end verification of Phase 10 — the variance result.

Prints one pass/fail line per check and exits non-zero if any fails. Every check treats a
*vacuous* pass as a failure: an empty sweep, a zero-row comparison and an all-NaN fit all
raise rather than passing quietly.

The two endpoint checks (2 and 3) are what make the sweep believable. If gating everything
off does not reproduce B1 exactly, and gating everything on does not reproduce the published
Phase 6 agent score exactly, then the gate is not a faithful re-expression of the original
run and nothing in between it means anything.

    python scripts/verify_phase10.py
"""

from __future__ import annotations

import argparse
import json
import logging
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
from verify_phase1 import CheckFailure  # noqa: E402

logging.disable(logging.INFO)

#: Published in docs/PHASE6_REPORT.md and processed/comparison_results.json.
PUBLISHED_B1_L = 0.8654
PUBLISHED_AGENT_L = 2.1444
PUBLISHED_FLIP_RATE = 0.0603

#: Anchor Var(L) values, from the three-run self-consistency measurements.
ANCHORS = {"v1": 0.254903, "v2": 4.59779e-07}
#: The Phase 10 section 6 exploratory arms, on a second vendor. Checked when the artefact is
#: present -- these were measured after the derivation was written, so they test it out of
#: sample, and the second vendor reverses the rate-to-variance ordering.
SECOND_MODEL_ANCHORS = {"v1": 1.38660e-04, "v2": 8.97150e-03}
#: The derivation is checked to a factor rather than a percentage: these span five orders
#: of magnitude, and a variance estimated from three runs has 2 degrees of freedom, whose
#: own 95% interval already spans roughly a factor of five.
ANCHOR_TOLERANCE = 1.5


def _sweep() -> pd.DataFrame:
    path = settings.PROCESSED_DIR / "sweep_results.parquet"
    if not path.is_file():
        raise CheckFailure(f"{path} is missing; run scripts/sweep_intervention.py")
    frame = pd.read_parquet(path)
    if frame.empty:
        raise CheckFailure("the sweep produced no rows (trivial pass guard)")
    return frame


# -- 1 ---------------------------------------------------------------------------------

def check_no_api_calls() -> str:
    """The sweep replays cached predictions and must not be able to call a model.

    Checked two ways, because either alone is weak: statically, that the sweep and the fit
    never import an LLM client at all; and dynamically, that a real replay leaves the
    client's own call counter at zero.
    """
    offenders = []
    for name in ("sweep_intervention.py", "fit_variance_model.py"):
        source = (REPO_ROOT / "scripts" / name).read_text(encoding="utf-8")
        for marker in ("LLMClient", "import anthropic", "from google", "import openai"):
            if marker in source:
                offenders.append(f"{name} references {marker}")
    if offenders:
        raise CheckFailure("; ".join(offenders))

    meta_path = settings.PROCESSED_DIR / "sweep_meta.json"
    if not meta_path.is_file():
        raise CheckFailure("processed/sweep_meta.json is missing")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("api_calls") != 0:
        raise CheckFailure(f"the sweep recorded {meta.get('api_calls')} API calls")

    # Dynamic: replay a handful of cached responses and confirm nothing went out.
    from agent.llm import LLMClient
    from agent.triage_agent import PROMPT_VERSION, SCOPE_THRESHOLD, TriageAgent
    from core.features import build_dataset
    from core.kelvins_store import load_visible_cdms

    events = build_dataset("train")
    subsample = events[events["latest_risk"] >= SCOPE_THRESHOLD].head(5)
    cdms = load_visible_cdms(subsample["series_id"].tolist(), "train")
    client = LLMClient(prompt_version=PROMPT_VERSION, offline=True)
    agent = TriageAgent(client=client)
    replayed = 0
    for _, row in subsample.iterrows():
        frame = cdms.get(str(row["series_id"]))
        if frame is None or frame.empty:
            continue
        agent.analyse(str(row["series_id"]), frame, row, salt="consistency-0")
        replayed += 1
    if replayed == 0:
        raise CheckFailure("nothing was replayed (trivial pass guard)")
    if client.calls_made != 0:
        raise CheckFailure(f"the offline client made {client.calls_made} API calls")

    return (
        f"no LLM client is referenced by the sweep or the fit; {replayed} responses "
        f"replayed with calls_made = 0 and {client.cache_hits} cache hits"
    )


# -- 2 ---------------------------------------------------------------------------------

def check_zero_rate_is_the_baseline() -> str:
    """At rate 0 the gated arm is B1 exactly, and its variance is exactly zero."""
    from core.features import build_dataset
    from core.kelvins_metric import kelvins_score
    from run_baselines import stratified_split
    from sweep_intervention import (
        BASE_SEED, VALIDATION_FRACTION, load_interventions, prepare_split, score_split,
    )

    frame = _sweep()
    zero = frame[np.isclose(frame["achieved_rate"], 0.0)]
    if zero.empty:
        raise CheckFailure("the sweep has no rate-0 row")
    if len(zero) != 3:
        raise CheckFailure(f"expected one rate-0 row per family, found {len(zero)}")

    for _, row in zero.iterrows():
        if row["var_L"] != 0.0:
            raise CheckFailure(
                f"{row['family']}: Var(L) at rate 0 is {row['var_L']}, not exactly 0"
            )
        if abs(row["mean_L"] - PUBLISHED_B1_L) > 5e-4:
            raise CheckFailure(
                f"{row['family']}: L at rate 0 is {row['mean_L']:.4f}, published B1 is "
                f"{PUBLISHED_B1_L}"
            )

    # And byte-identical predictions, not merely an equal score.
    interventions = load_interventions()
    train = build_dataset("train")
    for offset in (0, 11, 37):
        seed = BASE_SEED + offset
        split = prepare_split(seed, train, interventions)
        _, validation = stratified_split(train, seed, VALIDATION_FRACTION)
        truth = validation["final_risk"].to_numpy(dtype=np.float64)
        baseline = validation["latest_risk"].to_numpy(dtype=np.float64)
        reference = kelvins_score(truth, baseline)
        loss, mse, f2, terms = score_split(split, np.empty(0, dtype=np.int64))
        if terms["n_accepted"] != 0:
            raise CheckFailure(f"seed {seed}: the empty gate accepted something")
        if abs(loss - reference.score) > 1e-12 or abs(mse - reference.mse_hr) > 1e-12:
            raise CheckFailure(f"seed {seed}: the empty gate does not reproduce B1")

    return (
        f"all three families give L = {PUBLISHED_B1_L} and Var(L) = 0 exactly at rate 0; "
        "the empty gate reproduces B1 to 1e-12 on 3 seeds"
    )


# -- 3 ---------------------------------------------------------------------------------

def check_full_rate_is_the_published_run() -> str:
    """At rate 1.0 the gated arm is the original v1 run, and L matches Phase 6."""
    from core.features import build_dataset
    from core.kelvins_metric import kelvins_score
    from run_baselines import stratified_split
    from sweep_intervention import (
        BASE_SEED, VALIDATION_FRACTION, build_gates, load_interventions,
        prepare_split, score_split,
    )

    frame = _sweep()
    full = frame[np.isclose(frame["achieved_rate"], 1.0)]
    if len(full) != 3:
        raise CheckFailure(f"expected one rate-1 row per family, found {len(full)}")

    for _, row in full.iterrows():
        if abs(row["mean_L"] - PUBLISHED_AGENT_L) > 5e-4:
            raise CheckFailure(
                f"{row['family']}: L at rate 1 is {row['mean_L']:.4f}, Phase 6 published "
                f"{PUBLISHED_AGENT_L}"
            )
        if row["var_L"] != 0.0:
            raise CheckFailure(f"{row['family']}: Var(L) at rate 1 is not exactly 0")

    # Every family must select the identical full set, and it must reproduce the agent arm.
    interventions = load_interventions()
    train = build_dataset("train")
    gates = build_gates(interventions)
    n = len(interventions)
    selections = [
        sorted(gate.draw(n, np.random.default_rng(1)).tolist()) for gate in gates
    ]
    if any(selection != selections[0] for selection in selections[1:]):
        raise CheckFailure("the three families select different sets at rate 1")

    agent_by_id = dict(zip(interventions["series_id"], interventions["agent_prediction"]))
    for offset in (0, 11, 37):
        seed = BASE_SEED + offset
        split = prepare_split(seed, train, interventions)
        _, validation = stratified_split(train, seed, VALIDATION_FRACTION)
        truth = validation["final_risk"].to_numpy(dtype=np.float64)
        predictions = np.array([
            agent_by_id.get(sid, latest)
            for sid, latest in zip(validation["series_id"], validation["latest_risk"])
        ], dtype=np.float64)
        reference = kelvins_score(truth, predictions)
        loss, _, _, terms = score_split(split, np.arange(n))
        if terms["n_accepted"] != len(split.positions):
            raise CheckFailure(f"seed {seed}: the full gate did not accept everything")
        if abs(loss - reference.score) > 1e-12:
            raise CheckFailure(
                f"seed {seed}: the full gate gives {loss:.6f}, the original run "
                f"{reference.score:.6f}"
            )

    return (
        f"all three families give L = {PUBLISHED_AGENT_L}, matching the published Phase 6 "
        "L_arm_mean; the full gate reproduces the original v1 predictions to 1e-12"
    )


# -- 4 ---------------------------------------------------------------------------------

def check_flip_rate_is_invariant() -> str:
    """The verdict flip rate is a model quantity; no gate setting may move it."""
    frame = _sweep()
    unique = frame["verdict_flip_rate"].unique()
    if len(unique) != 1:
        raise CheckFailure(f"the flip rate varies across the sweep: {unique}")
    if abs(float(unique[0]) - PUBLISHED_FLIP_RATE) > 1e-9:
        raise CheckFailure(
            f"the sweep records a flip rate of {unique[0]}, Phase 6 measured "
            f"{PUBLISHED_FLIP_RATE}"
        )

    # Invariance must hold because the gate cannot see a verdict, not merely because the
    # recorded constant happens to be copied to every row.
    source = (REPO_ROOT / "scripts" / "sweep_intervention.py").read_text(encoding="utf-8")
    body = source.split("VERDICT_FLIP_RATE = ")[-1]
    for column in ("will_collapse", "decision", "confidence_flip"):
        if re.search(rf'\[["\']{column}["\']\]', body):
            raise CheckFailure(f"the sweep reads {column}, so the gate could affect it")

    levels = json.loads(
        (settings.PROCESSED_DIR / "three_levels.json").read_text(encoding="utf-8")
    )
    v1 = levels["v1"]["level_2_decision_instability"]["verdict_flip_rate"]
    v2 = levels["v2"]["level_2_decision_instability"]["verdict_flip_rate"]

    return (
        f"constant at {PUBLISHED_FLIP_RATE} across all {len(frame)} sweep rows, and no "
        f"verdict column is read downstream of the gate; measured independently at "
        f"{v1} (v1) and {v2} (v2)"
    )


# -- 5 ---------------------------------------------------------------------------------

def check_derivation_reproduces_both_anchors() -> str:
    """The delta-method form must land on both observed Var(L) values."""
    from core.kelvins_metric import CLIP_EPSILON, HIGH_RISK_THRESHOLD, kelvins_score

    path = settings.PROCESSED_DIR / "replayed_runs.parquet"
    if not path.is_file():
        raise CheckFailure(f"{path} is missing; run scripts/replay_runs.py")
    replayed = pd.read_parquet(path)

    def clip(values: np.ndarray) -> np.ndarray:
        return np.where(values < HIGH_RISK_THRESHOLD,
                        HIGH_RISK_THRESHOLD - CLIP_EPSILON, values)

    lines = []
    for prompt, expected in ANCHORS.items():
        subset = replayed[replayed["prompt"] == prompt]
        runs = sorted(subset["run"].unique())
        common = sorted(set.intersection(
            *[set(subset[subset["run"] == r]["series_id"]) for r in runs]
        ))
        if len(common) < 100:
            raise CheckFailure(f"{prompt}: only {len(common)} common events")

        mses, f2s, losses = [], [], []
        for run in runs:
            block = (
                subset[(subset["run"] == run) & subset["series_id"].isin(common)]
                .set_index("series_id").loc[common]
            )
            truth = block["final_risk"].to_numpy(dtype=np.float64)
            score = kelvins_score(truth, block["effective_prediction"].to_numpy(np.float64))
            mses.append(score.mse_hr)
            f2s.append(score.f2)
            losses.append(score.score)

        mses, f2s, losses = map(np.asarray, (mses, f2s, losses))
        observed = float(np.var(losses, ddof=1))
        if abs(observed - expected) > 0.02 * max(expected, 1e-9) + 1e-9:
            raise CheckFailure(
                f"{prompt}: replay gives Var(L) = {observed:.6g}, the report records "
                f"{expected:.6g}"
            )

        mean_mse, mean_f2 = float(mses.mean()), float(f2s.mean())
        predicted = (
            float(np.var(mses, ddof=1)) / mean_f2**2
            + (mean_mse / mean_f2**2) ** 2 * float(np.var(f2s, ddof=1))
            - 2 * (mean_mse / mean_f2**3) * float(np.cov(mses, f2s, ddof=1)[0, 1])
        )
        if predicted <= 0:
            raise CheckFailure(f"{prompt}: the derivation predicts a non-positive variance")
        ratio = observed / predicted
        if not (1 / ANCHOR_TOLERANCE <= ratio <= ANCHOR_TOLERANCE):
            raise CheckFailure(
                f"{prompt}: observed/predicted = {ratio:.3f}, outside the stated "
                f"tolerance of {ANCHOR_TOLERANCE}x"
            )
        lines.append(f"{prompt}: predicted {predicted:.4g}, observed {observed:.4g}, "
                     f"ratio {ratio:.3f}")

    # The second vendor, when it has been run. Same formula, same tolerance.
    second = settings.PROCESSED_DIR / "EXPLORATORY_second_model_runs.parquet"
    if second.is_file():
        runs = pd.read_parquet(second)
        for prompt, expected in SECOND_MODEL_ANCHORS.items():
            subset = runs[runs["prompt"] == prompt]
            if subset.empty:
                continue
            ids = sorted(set.intersection(
                *[set(subset[subset["run"] == r]["series_id"]) for r in (0, 1, 2)]
            ))
            mses, f2s, losses = [], [], []
            for run in (0, 1, 2):
                block = (
                    subset[(subset["run"] == run) & subset["series_id"].isin(ids)]
                    .set_index("series_id").loc[ids]
                )
                score = kelvins_score(
                    block["final_risk"].to_numpy(dtype=np.float64),
                    block["effective_prediction"].to_numpy(dtype=np.float64),
                )
                mses.append(score.mse_hr)
                f2s.append(score.f2)
                losses.append(score.score)
            mses, f2s, losses = map(np.asarray, (mses, f2s, losses))
            observed = float(np.var(losses, ddof=1))
            mean_mse, mean_f2 = float(mses.mean()), float(f2s.mean())
            predicted = (
                float(np.var(mses, ddof=1)) / mean_f2**2
                + (mean_mse / mean_f2**2) ** 2 * float(np.var(f2s, ddof=1))
                - 2 * (mean_mse / mean_f2**3) * float(np.cov(mses, f2s, ddof=1)[0, 1])
            )
            if abs(observed - expected) > 0.02 * expected:
                raise CheckFailure(
                    f"second model {prompt}: Var(L) = {observed:.6g}, the report records "
                    f"{expected:.6g}"
                )
            ratio = observed / predicted if predicted > 0 else float("inf")
            if not (1 / ANCHOR_TOLERANCE <= ratio <= ANCHOR_TOLERANCE):
                raise CheckFailure(
                    f"second model {prompt}: observed/predicted = {ratio:.3f}, outside "
                    f"the {ANCHOR_TOLERANCE}x tolerance"
                )
            lines.append(f"opus-4.6 {prompt}: predicted {predicted:.4g}, observed "
                         f"{observed:.4g}, ratio {ratio:.3f}")

    return "; ".join(lines) + f" (tolerance {ANCHOR_TOLERANCE}x)"


# -- 6 ---------------------------------------------------------------------------------

def check_earlier_phases_still_pass() -> str:
    """No Phase 10 change may break an earlier phase's verification."""
    passed = []
    for phase in (1, 2, 3, 4, 5, 6, 7, 9):
        script = REPO_ROOT / "scripts" / f"verify_phase{phase}.py"
        if not script.is_file():
            continue
        completed = subprocess.run(
            [sys.executable, str(script)], cwd=REPO_ROOT, capture_output=True, text=True
        )
        if completed.returncode != 0:
            tail = (completed.stdout or completed.stderr).strip().splitlines()[-2:]
            raise CheckFailure(f"verify_phase{phase} failed: {' | '.join(tail)}")
        match = re.search(r"(\d+)/(\d+) checks passed", completed.stdout)
        passed.append(f"phase{phase} {match.group(0).split()[0]}" if match else f"phase{phase}")
    if len(passed) < 8:
        raise CheckFailure(f"only {len(passed)} earlier phases ran (trivial pass guard)")
    return "; ".join(passed)


# -- 7 ---------------------------------------------------------------------------------

def check_pytest() -> str:
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"], cwd=REPO_ROOT, capture_output=True, text=True
    )
    lines = (completed.stdout or completed.stderr).strip().splitlines()
    line = lines[-1] if lines else "(no output)"
    if completed.returncode != 0:
        raise CheckFailure(f"pytest exited {completed.returncode}: {line}")
    match = re.search(r"(\d+) passed", line)
    if not match or int(match.group(1)) == 0:
        raise CheckFailure(f"pytest reported no passing tests: {line}")
    return f"pytest: {line}"


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()

    checks: list[tuple[str, Callable[[], str]]] = [
        ("the sweep made zero API calls", check_no_api_calls),
        ("rate 0 is B1 exactly, with Var(L) = 0", check_zero_rate_is_the_baseline),
        ("rate 100 is the published v1 run exactly", check_full_rate_is_the_published_run),
        ("the verdict flip rate is invariant to the gate", check_flip_rate_is_invariant),
        ("the derivation reproduces every anchor", check_derivation_reproduces_both_anchors),
        ("every earlier phase still verifies", check_earlier_phases_still_pass),
        ("pytest passes", check_pytest),
    ]

    print(f"Phase 10 verification -- {REPO_ROOT}\n")
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
        print(f"{failures} FAILED -- Phase 10 is not complete.")
        return 1
    print("Phase 10 verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
