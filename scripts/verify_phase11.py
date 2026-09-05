"""End-to-end verification of Phase 11 — the diagnosis and the hybrid.

Prints one pass/fail line per check and exits non-zero if any fails. Every check treats a
*vacuous* pass as a failure: a missing arm, an empty ablation and an unrun control all raise
rather than passing quietly.

Check 1 is the one that makes the rest worth reading. A pre-registration written after the
result is not a pre-registration, so its commit is compared against the first commit of
``agent/hybrid.py`` by git timestamp and by ancestry.

    python scripts/verify_phase11.py
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

PREREGISTRATION = "docs/PHASE11_PREREGISTRATION.md"
HYBRID_MODULE = "agent/hybrid.py"


def _git(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=REPO_ROOT, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise CheckFailure(f"git {' '.join(arguments)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _results() -> dict:
    path = settings.PROCESSED_DIR / "hybrid_results.json"
    if not path.is_file():
        raise CheckFailure(f"{path} is missing; run scripts/run_hybrid.py")
    report = json.loads(path.read_text(encoding="utf-8"))
    if not report.get("arms"):
        raise CheckFailure("the ablation recorded no arms (trivial pass guard)")
    return report


# -- 1 ---------------------------------------------------------------------------------

def check_preregistration_came_first() -> str:
    """The pre-registration must predate the hybrid, by timestamp and by ancestry."""
    prereg_commit = _git("log", "--format=%H", "--diff-filter=A", "--", PREREGISTRATION)
    hybrid_commit = _git("log", "--format=%H", "--diff-filter=A", "--", HYBRID_MODULE)
    if not prereg_commit:
        raise CheckFailure(f"{PREREGISTRATION} has never been committed")
    if not hybrid_commit:
        raise CheckFailure(f"{HYBRID_MODULE} has never been committed")
    prereg_commit = prereg_commit.splitlines()[-1]
    hybrid_commit = hybrid_commit.splitlines()[-1]

    prereg_time = int(_git("show", "-s", "--format=%ct", prereg_commit))
    hybrid_time = int(_git("show", "-s", "--format=%ct", hybrid_commit))
    if prereg_time >= hybrid_time:
        raise CheckFailure(
            f"the pre-registration ({prereg_commit[:12]}) is not older than the hybrid "
            f"({hybrid_commit[:12]})"
        )

    # Ancestry, because timestamps can be forged and a rebase can reorder them.
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", prereg_commit, hybrid_commit],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    if ancestor.returncode != 0:
        raise CheckFailure(
            f"{prereg_commit[:12]} is not an ancestor of {hybrid_commit[:12]}"
        )

    # And it must not have been edited after the fact.
    revisions = _git("log", "--format=%H", "--", PREREGISTRATION).splitlines()
    if len(revisions) > 1:
        raise CheckFailure(
            f"the pre-registration has {len(revisions)} commits; it is declared immutable"
        )

    return (
        f"pre-registration {prereg_commit[:12]} precedes the hybrid {hybrid_commit[:12]} "
        f"by {hybrid_time - prereg_time}s, is its ancestor, and has never been amended"
    )


# -- 2 ---------------------------------------------------------------------------------

def check_action_space_is_binary() -> str:
    """Every hybrid output is B1's exact value or exactly -6.001. Nothing else."""
    from agent.hybrid import CLIP_FLOOR, ActionSpaceError, enforce_action_space

    baseline = np.array([-5.0, -4.2, -6.5, -3.0], dtype=np.float64)
    enforce_action_space(baseline.copy(), baseline)
    enforce_action_space(np.full_like(baseline, CLIP_FLOOR), baseline)
    mixed = np.array([-5.0, CLIP_FLOOR, -6.5, CLIP_FLOOR])
    enforce_action_space(mixed, baseline)

    for illegal in ([-5.0, -4.9, -6.5, -3.0], [-5.0, -6.0, -6.5, -3.0],
                    [-5.0, np.nan, -6.5, -3.0]):
        try:
            enforce_action_space(np.array(illegal, dtype=np.float64), baseline)
        except ActionSpaceError:
            continue
        raise CheckFailure(f"a third value {illegal} was accepted")

    # And on the arms as actually run: re-fit one split and inspect every prediction.
    from run_hybrid import ARMS, BASE_SEED, VALIDATION_FRACTION, load_joined
    from agent.hybrid import HybridConfig, fit_hybrid
    from run_baselines import stratified_split

    joined = load_joined()
    fit, validation = stratified_split(joined, BASE_SEED, VALIDATION_FRACTION)
    checked = 0
    for name, config in ARMS.items():
        result = fit_hybrid(
            HybridConfig(**{**config.__dict__, "classifier": "gbm"}), fit, validation, BASE_SEED
        )
        values = result.predictions
        reference = validation["latest_risk"].to_numpy(dtype=np.float64)
        legal = (np.abs(values - reference) <= 1e-12) | (np.abs(values - CLIP_FLOOR) <= 1e-12)
        if not legal.all():
            raise CheckFailure(f"{name} emitted {int((~legal).sum())} illegal values")
        checked += len(values)

    return (
        f"{checked:,} live predictions across {len(ARMS)} arms are all either B1's exact "
        "value or -6.001; three classes of third value are rejected, including NaN"
    )


# -- 3 ---------------------------------------------------------------------------------

def check_threshold_saw_no_test_label() -> str:
    """No test label reached the fitting, the calibration or the threshold."""
    report = _results()
    if report["protocol"].get("test_set_read") is not False:
        raise CheckFailure("the ablation report does not declare test_set_read = False")

    for name in ("run_hybrid.py",):
        source = (REPO_ROOT / "scripts" / name).read_text(encoding="utf-8")
        for marker in ('build_dataset("test")', "build_dataset('test')",
                       "agent_predictions_test", "_test.parquet"):
            if marker in source:
                raise CheckFailure(f"{name} references the test split via {marker!r}")

    module = (REPO_ROOT / HYBRID_MODULE).read_text(encoding="utf-8")
    for marker in ('build_dataset("test")', "agent_predictions_test", "_test.parquet"):
        if marker in module:
            raise CheckFailure(f"{HYBRID_MODULE} references the test split via {marker!r}")

    # The diagnosis DID read test labels, so nothing it produced may reach the hybrid. The
    # check is on the *import graph*, parsed, not on the text: hybrid.py cites the
    # diagnosis in its docstring as motivation, and a substring search flags that as an
    # import. It is not one.
    import ast

    tree = ast.parse(module)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden = {name for name in imported if "diagnose_failure" in name}
    if forbidden:
        raise CheckFailure(
            f"{HYBRID_MODULE} imports {sorted(forbidden)}, which read test labels"
        )

    diagnosis = settings.PROCESSED_DIR / "failure_diagnosis.json"
    if diagnosis.is_file():
        declared = json.loads(diagnosis.read_text(encoding="utf-8")).get("test_labels_used")
        if not declared:
            raise CheckFailure("the diagnosis does not declare its use of test labels")

    return (
        f"neither the hybrid nor its runner references the test split; hybrid.py imports "
        f"{len(imported)} modules, none from the diagnosis, which declares its own "
        "test-label use"
    )


# -- 4 ---------------------------------------------------------------------------------

def check_controls_ran() -> str:
    """H2 (no-LLM) and H4 (permutation) both ran and are reported."""
    report = _results()
    arms = report["arms"]

    h2 = [key for key in arms if key.startswith("H2_calibrated_no_llm")]
    h3 = [key for key in arms if key.startswith("H3_calibrated_with_llm")]
    if not h2:
        raise CheckFailure("H2, the no-LLM control, is not in the report")
    if not h3:
        raise CheckFailure("H3, the full hybrid, is not in the report")

    headline = [key for key in report.get("comparisons", {}) if key.startswith("H3_vs_H2")]
    if not headline:
        raise CheckFailure("the H3-vs-H2 headline comparison is not reported")

    permutation = report.get("H4_permutation_control")
    if not permutation:
        raise CheckFailure("H4, the permutation control, is not in the report")
    if permutation.get("permutations", 0) < 20:
        raise CheckFailure(
            f"H4 ran {permutation.get('permutations')} permutations; the pre-registration "
            "fixed 20"
        )
    if "permutation_p_value" not in permutation:
        raise CheckFailure("H4 reports no permutation p-value")

    return (
        f"H2 ({len(h2)} classifier(s)), H3 ({len(h3)}), {len(headline)} H3-vs-H2 "
        f"comparison(s), and H4 over {permutation['permutations']} permutations "
        f"(p = {permutation['permutation_p_value']:.4f})"
    )


# -- 5 ---------------------------------------------------------------------------------

def check_no_new_api_calls() -> str:
    """The primary arms replay the cache and cannot call a model."""
    for name in ("run_hybrid.py",):
        source = (REPO_ROOT / "scripts" / name).read_text(encoding="utf-8")
        for marker in ("LLMClient", "import anthropic", "from google", "import openai"):
            if marker in source:
                raise CheckFailure(f"{name} references {marker}")
    module = (REPO_ROOT / HYBRID_MODULE).read_text(encoding="utf-8")
    for marker in ("LLMClient", "import anthropic", "from google", "import openai"):
        if marker in module:
            raise CheckFailure(f"{HYBRID_MODULE} references {marker}")

    predictions = settings.PROCESSED_DIR / "agent_predictions.parquet"
    if not predictions.is_file():
        raise CheckFailure(f"{predictions} is missing")
    frame = pd.read_parquet(predictions)
    analysed = int(frame["agent_analysed"].sum())
    if analysed == 0:
        raise CheckFailure("the cached predictions contain no analysed events")

    return (
        f"neither the hybrid nor its runner can construct an LLM client; all {analysed} "
        "LLM outputs come from the Phase 6 cache"
    )


# -- 6 ---------------------------------------------------------------------------------

def check_earlier_phases_still_pass() -> str:
    passed = []
    for phase in (1, 2, 3, 4, 5, 6, 7, 9, 10):
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
    if len(passed) < 9:
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
        ("the pre-registration predates the hybrid", check_preregistration_came_first),
        ("every hybrid output is B1 or -6.001", check_action_space_is_binary),
        ("the threshold saw no test label", check_threshold_saw_no_test_label),
        ("the H2 and H4 controls ran and are reported", check_controls_ran),
        ("the primary arms made zero new API calls", check_no_new_api_calls),
        ("every earlier phase still verifies", check_earlier_phases_still_pass),
        ("pytest passes", check_pytest),
    ]

    print(f"Phase 11 verification -- {REPO_ROOT}\n")
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
        print(f"{failures} FAILED -- Phase 11 is not complete.")
        return 1
    print("Phase 11 verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
