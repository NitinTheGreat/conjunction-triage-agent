"""End-to-end verification of Phase 7 — the single final test-set evaluation.

Prints one pass/fail line per check and exits non-zero if any fails. Every check treats a
*vacuous* pass as a failure.

    python scripts/verify_phase7.py
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
from verify_phase1 import CheckFailure  # noqa: E402

#: Code that must never read a test **label**. run_agent_test.py legitimately reads test
#: *features* — that is the Phase 7 evaluation — but must not touch final_risk.
LABEL_FREE_CODE = ("run_agent_test.py",)
#: Code that must not touch the test split at all.
TRAIN_ONLY_CODE = (
    "run_baselines.py", "error_analysis.py", "run_agent.py",
    "compare_arms.py", "faithfulness.py", "agent_error_analysis.py",
)


def _git(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=REPO_ROOT, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise CheckFailure(f"git {' '.join(arguments)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _results() -> dict:
    path = settings.PROCESSED_DIR / "test_results.json"
    if not path.is_file():
        raise CheckFailure("test_results.json missing; run scripts/evaluate_test.py")
    return json.loads(path.read_text(encoding="utf-8"))


# -- 1 ---------------------------------------------------------------------------------

def check_manifest_matches() -> str:
    """The frozen manifest matches the commit hashes actually in the tree."""
    report = _results()
    manifest = report.get("frozen_manifest") or {}
    artefacts = manifest.get("artefacts") or {}
    if not artefacts:
        raise CheckFailure("the manifest records no artefacts (trivial pass guard)")

    mismatched = []
    for path, entry in artefacts.items():
        if not (REPO_ROOT / path).is_file():
            mismatched.append(f"{path}: missing from the tree")
            continue
        current = _git("rev-parse", f"HEAD:{path}")
        if current != entry["blob"]:
            mismatched.append(f"{path}: blob {current[:8]} != recorded {entry['blob'][:8]}")
        if _git("status", "--porcelain", path):
            mismatched.append(f"{path}: has uncommitted changes")

    if mismatched:
        raise CheckFailure("; ".join(mismatched))

    agent = manifest.get("agent") or {}
    for field in ("prompt_version", "scope_threshold", "provider", "model", "temperature"):
        if field not in agent:
            raise CheckFailure(f"the manifest does not record the agent's {field}")
    if agent["temperature"] != 0.0:
        raise CheckFailure(f"temperature {agent['temperature']} is not the frozen 0.0")
    return (
        f"{len(artefacts)} artefacts match HEAD; agent frozen at "
        f"{agent['provider']}/{agent['model']} prompt {agent['prompt_version']} "
        f"scope {agent['scope_threshold']}"
    )


# -- 2 ---------------------------------------------------------------------------------

def check_scored_once() -> str:
    """Each arm was scored exactly once — no repeated-evaluation artefacts on disk."""
    processed = settings.PROCESSED_DIR
    duplicates = sorted(
        p.name for p in processed.glob("test_results*.json") if p.name != "test_results.json"
    ) + sorted(
        p.name for p in processed.glob("test_predictions*.parquet")
        if p.name != "test_predictions.parquet"
    )
    if duplicates:
        raise CheckFailure(
            f"repeated-evaluation artefacts present: {duplicates}; the test set is "
            "scored once"
        )

    report = _results()
    arms = {k: v for k, v in report.get("arms", {}).items() if isinstance(v, dict) and "official" in v}
    if not arms:
        raise CheckFailure("no arms scored (trivial pass guard)")

    predictions_path = processed / "test_predictions.parquet"
    if not predictions_path.is_file():
        raise CheckFailure("test_predictions.parquet missing")
    frame = pd.read_parquet(predictions_path)
    columns = [c for c in frame.columns if c.startswith("pred_")]
    if len(columns) != len(arms):
        raise CheckFailure(
            f"{len(columns)} prediction columns for {len(arms)} scored arms"
        )
    if len(frame) != report["test_events"]:
        raise CheckFailure(
            f"{len(frame)} prediction rows for {report['test_events']} test events"
        )
    return f"{len(arms)} arms, one prediction column each, {len(frame):,} rows"


# -- 3 ---------------------------------------------------------------------------------

def check_no_test_labels_in_training_code() -> str:
    """No training or selection code path reads the test split or its labels."""
    offenders: list[str] = []
    for name in TRAIN_ONLY_CODE:
        path = REPO_ROOT / "scripts" / name
        if not path.is_file():
            raise CheckFailure(f"{name} is missing")
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            called = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if called not in {"build_dataset", "eligibility_report", "load_visible_cdms"}:
                continue
            for argument in list(node.args) + [kw.value for kw in node.keywords]:
                if isinstance(argument, ast.Constant) and argument.value == "test":
                    offenders.append(f"{name}:{node.lineno} {called}('test')")
        for match in re.finditer(
            r"""["'][^"']*(cdms_test|series_test|test_data|_test\.parquet)[^"']*["']""",
            source,
        ):
            offenders.append(f"{name}: references {match.group(0)}")

    # The test-set agent runner may read features but must never read a label.
    for name in LABEL_FREE_CODE:
        path = REPO_ROOT / "scripts" / name
        if not path.is_file():
            raise CheckFailure(f"{name} is missing")
        source = path.read_text(encoding="utf-8")
        for label in ("final_risk", "is_high_risk", "true_risk"):
            if re.search(rf"\b{label}\b", source):
                offenders.append(f"{name}: reads the label {label!r}")

    if offenders:
        raise CheckFailure("; ".join(offenders))
    return (
        f"{len(TRAIN_ONLY_CODE)} train-only scripts touch no test artefact; "
        f"{len(LABEL_FREE_CODE)} test-side script reads no label"
    )


# -- 4 ---------------------------------------------------------------------------------

def check_eligibility_not_reapplied() -> str:
    """The eligibility filter was NOT reapplied to the pre-filtered test set."""
    from core.features import PRE_FILTERED_SPLITS, build_dataset

    if "test" not in PRE_FILTERED_SPLITS:
        raise CheckFailure("core.features does not mark test as pre-filtered")

    report = _results()
    if report.get("eligibility_filter_reapplied") is not False:
        raise CheckFailure("test_results.json does not record the filter as not reapplied")

    frame = build_dataset("test")
    if len(frame) != report["test_events"]:
        raise CheckFailure(
            f"build_dataset('test') returns {len(frame)} events but the report scored "
            f"{report['test_events']}"
        )
    if len(frame) != 2167:
        raise CheckFailure(
            f"{len(frame)} test events; reapplying the filter would give 0 and the full "
            "set is 2,167"
        )
    return f"{len(frame):,} test events retained; the filter would have rejected all of them"


# -- 5 ---------------------------------------------------------------------------------

def check_bootstrap_recorded() -> str:
    """The bootstrap seed and resample count are recorded."""
    report = _results()
    bootstrap = report.get("bootstrap") or {}
    for field in ("resamples", "seed"):
        if field not in bootstrap:
            raise CheckFailure(f"the bootstrap {field} is not recorded")
    if bootstrap["resamples"] < 1000:
        raise CheckFailure(f"only {bootstrap['resamples']} resamples")

    arms = report.get("arms", {})
    with_ci = [
        name for name, block in arms.items()
        if isinstance(block, dict) and (block.get("bootstrap_L") or {}).get("ci95")
    ]
    if not with_ci:
        raise CheckFailure("no arm carries a bootstrap CI (trivial pass guard)")
    if "measures" not in bootstrap:
        raise CheckFailure(
            "the report does not state what the bootstrap measures; it must distinguish "
            "within-test sampling uncertainty from Phase 5 split variance"
        )
    return (
        f"{bootstrap['resamples']:,} resamples, seed {bootstrap['seed']}, "
        f"{len(with_ci)} arms with a CI"
    )


# -- 6 ---------------------------------------------------------------------------------

def check_leaderboard_attributed() -> str:
    """Every published leaderboard figure cited is attributed to arXiv:2008.03069."""
    report = _results()
    source = report.get("published_leaderboard_source", "")
    if "2008.03069" not in source:
        raise CheckFailure(f"leaderboard source is not attributed: {source!r}")

    published = report.get("published_leaderboard") or {}
    expected = {
        "CRP_baseline_constant_minus5": 2.5,
        "LRP_baseline_latest_risk": 0.694,
        "winner_sesc": 0.556,
        "tenth_spacemeister": 0.649,
    }
    for name, value in expected.items():
        if name not in published:
            raise CheckFailure(f"published figure {name} is missing")
        if published[name]["L"] != value:
            raise CheckFailure(
                f"{name} recorded as {published[name]['L']}, published value is {value}"
            )

    report_path = REPO_ROOT / "docs" / "PHASE7_REPORT.md"
    if report_path.is_file():
        text = report_path.read_text(encoding="utf-8")
        if "2008.03069" not in text:
            raise CheckFailure("PHASE7_REPORT.md cites no source for the leaderboard")
    return f"4 published figures attributed to {source}"


# -- 7 ---------------------------------------------------------------------------------

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


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()

    checks: list[tuple[str, Callable[[], str]]] = [
        ("the frozen manifest matches the tree", check_manifest_matches),
        ("each arm was scored exactly once", check_scored_once),
        ("no training code reads test labels", check_no_test_labels_in_training_code),
        ("the eligibility filter was not reapplied", check_eligibility_not_reapplied),
        ("bootstrap seed and resamples recorded", check_bootstrap_recorded),
        ("leaderboard figures attributed", check_leaderboard_attributed),
        ("pytest passes", check_pytest),
    ]

    print(f"Phase 7 verification -- {REPO_ROOT}\n")
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
        print(f"{failures} FAILED -- Phase 7 is not complete.")
        return 1
    print("Phase 7 verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
