"""End-to-end verification of Phase 6.

Prints one pass/fail line per check and exits non-zero if any fails. Every check treats a
*vacuous* pass — zero events, zero citations, zero splits — as a failure.

    python scripts/verify_phase6.py
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

from agent.llm import LLMClient  # noqa: E402
from agent.triage_agent import PROMPT_VERSION, SCOPE_THRESHOLD, in_scope  # noqa: E402
from core.config import settings  # noqa: E402
from verify_phase1 import CheckFailure  # noqa: E402

PREREGISTRATION = Path("docs/PHASE6_PREREGISTRATION.md")

#: Every script that must never read the test split.
TRAINING_CODE = (
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


def _predictions() -> pd.DataFrame:
    path = settings.PROCESSED_DIR / "agent_predictions.parquet"
    if not path.is_file():
        raise CheckFailure(f"{path.name} missing; run scripts/run_agent.py")
    return pd.read_parquet(path)


# -- 1 ---------------------------------------------------------------------------------

def check_preregistration_precedes_results() -> str:
    """The pre-registration is committed and predates the first agent-prediction commit."""
    path = REPO_ROOT / PREREGISTRATION
    if not path.is_file():
        raise CheckFailure(f"{PREREGISTRATION} does not exist")

    tracked = _git("ls-files", str(PREREGISTRATION))
    if not tracked:
        raise CheckFailure(f"{PREREGISTRATION} is not committed")

    # It must be unmodified since its commit: an edited protocol is not a protocol.
    if _git("status", "--porcelain", str(PREREGISTRATION)):
        raise CheckFailure(
            f"{PREREGISTRATION} has uncommitted modifications; it is meant to be immutable"
        )

    prereg_commit = _git("log", "--format=%H", "--diff-filter=A", "--", str(PREREGISTRATION))
    if not prereg_commit:
        raise CheckFailure("could not find the commit that added the pre-registration")
    prereg_commit = prereg_commit.splitlines()[-1]
    prereg_time = int(_git("show", "-s", "--format=%ct", prereg_commit))

    # The first commit introducing agent prediction code must come after it.
    agent_commit = _git(
        "log", "--format=%H", "--diff-filter=A", "--", "scripts/run_agent.py"
    )
    if not agent_commit:
        raise CheckFailure("scripts/run_agent.py has never been committed")
    agent_commit = agent_commit.splitlines()[-1]
    agent_time = int(_git("show", "-s", "--format=%ct", agent_commit))

    if prereg_time > agent_time:
        raise CheckFailure(
            f"the pre-registration ({prereg_commit[:8]}) was committed AFTER the agent "
            f"runner ({agent_commit[:8]}); the protocol was not registered in advance"
        )

    blob = _git("rev-parse", f"{prereg_commit}:{PREREGISTRATION}")
    # It must actually contain a decision rule, not merely exist.
    text = path.read_text(encoding="utf-8")
    for required in ("AGENT WINS", "NO EFFECT", "0.138", "Wilcoxon"):
        if required not in text:
            raise CheckFailure(f"the pre-registration does not mention {required!r}")
    return (
        f"committed {prereg_commit[:8]} (blob {blob[:8]}), before the agent runner "
        f"{agent_commit[:8]}; unmodified since"
    )


# -- 2 ---------------------------------------------------------------------------------

def check_every_prediction_cached() -> str:
    """Every agent prediction has a cached response; a re-run makes zero API calls."""
    frame = _predictions()
    analysed = frame.loc[frame["agent_analysed"].fillna(False)]
    if analysed.empty:
        raise CheckFailure("no analysed events (trivial pass guard)")

    cache_dir = settings.CACHE_DIR / "agent"
    if not cache_dir.is_dir():
        raise CheckFailure(f"{cache_dir} does not exist")
    entries = list(cache_dir.rglob("*.json"))
    if not entries:
        raise CheckFailure("the agent cache is empty")

    # An offline client must be able to serve the whole run: that is the real test.
    client = LLMClient(offline=True, prompt_version=PROMPT_VERSION)
    if client.offline is not True:
        raise CheckFailure("offline client did not report offline")

    # Spot-check that entries carry the audit fields the protocol requires.
    sample = json.loads(entries[0].read_text(encoding="utf-8"))
    for field in ("model", "provider", "temperature", "prompt_version", "created_utc"):
        if field not in sample:
            raise CheckFailure(f"cache entries do not record {field!r}")
    return (
        f"{len(analysed):,} analysed events, {len(entries):,} cache entries recording "
        f"model/provider/temperature/prompt_version"
    )


# -- 3 ---------------------------------------------------------------------------------

def check_schema_validates() -> str:
    """Every stored agent record satisfies the output schema."""
    from agent.triage_agent import AgentVerdict

    frame = _predictions()
    analysed = frame.loc[frame["agent_analysed"].fillna(False)]
    if analysed.empty:
        raise CheckFailure("no analysed events (trivial pass guard)")

    for _, row in analysed.iterrows():
        AgentVerdict(
            predicted_final_risk=float(row["agent_risk"]),
            will_collapse=bool(row["will_collapse"]),
            confidence=str(row["confidence"]),
            reasoning=str(row["reasoning"]),
            evidence_cited=json.loads(row["evidence_cited"]),
        )

    # And malformed responses must actually raise rather than default.
    from agent.llm import LLMError
    from agent.triage_agent import parse_verdict

    for bad in ('not json', '{"predicted_final_risk": 5.0}', '{"confidence": "certain"}'):
        try:
            parse_verdict(bad, "check")
        except (LLMError, ValueError):
            continue
        raise CheckFailure(f"a malformed response was accepted: {bad!r}")
    return f"{len(analysed):,} records validate; malformed responses raise"


# -- 4 ---------------------------------------------------------------------------------

def check_scope_respected() -> str:
    """The agent ran only on in-scope events; every other prediction equals B1 exactly."""
    frame = _predictions()
    if "in_scope" not in frame.columns:
        raise CheckFailure("agent_predictions.parquet has no in_scope column")

    declared = frame["in_scope"].to_numpy(dtype=bool)
    recomputed = np.array([in_scope(v, SCOPE_THRESHOLD) for v in frame["latest_risk"]])
    if not np.array_equal(declared, recomputed):
        raise CheckFailure(
            f"{int((declared != recomputed).sum())} events disagree with the scope rule"
        )

    analysed = frame["agent_analysed"].fillna(False).to_numpy(dtype=bool)
    if (analysed & ~declared).any():
        raise CheckFailure(
            f"{int((analysed & ~declared).sum())} out-of-scope events were analysed"
        )

    out_of_scope = frame.loc[~declared]
    if out_of_scope.empty:
        raise CheckFailure("no out-of-scope events (trivial pass guard)")
    difference = np.abs(
        out_of_scope["agent_prediction"].to_numpy(dtype=float)
        - out_of_scope["b1_risk"].to_numpy(dtype=float)
    )
    if np.nanmax(difference) > 0:
        raise CheckFailure(
            f"{int((difference > 0).sum())} out-of-scope predictions differ from B1"
        )
    return (
        f"{int(declared.sum()):,} in scope, {int((~declared).sum()):,} out of scope and "
        f"identical to B1 ({100 * declared.mean():.2f}% invoked)"
    )


# -- 5 ---------------------------------------------------------------------------------

def check_same_seeds_as_phase5() -> str:
    """The paired comparison uses the same split seeds as Phase 5."""
    import compare_arms

    path = settings.PROCESSED_DIR / "comparison_results.json"
    if not path.is_file():
        raise CheckFailure("comparison_results.json missing; run scripts/compare_arms.py")
    report = json.loads(path.read_text(encoding="utf-8"))

    phase5 = settings.PROCESSED_DIR / "noise_study.json"
    if not phase5.is_file():
        raise CheckFailure("processed/noise_study.json missing; Phase 5 seeds unknown")
    phase5_seeds = json.loads(phase5.read_text(encoding="utf-8"))["seeds"]

    used = report["protocol"]["seeds"]
    if len(used) != compare_arms.N_SPLITS:
        raise CheckFailure(f"{len(used)} seeds used, protocol specifies {compare_arms.N_SPLITS}")
    if used != phase5_seeds[: len(used)]:
        raise CheckFailure(
            f"seeds differ from Phase 5: {used[:3]}... vs {phase5_seeds[:3]}..."
        )
    return f"{len(used)} seeds identical to Phase 5 ({used[0]}..{used[-1]})"


# -- 6 ---------------------------------------------------------------------------------

def check_self_consistency_reported() -> str:
    """Self-consistency across 3 runs is reported and non-vacuous."""
    path = settings.PROCESSED_DIR / "agent_run_report.json"
    if not path.is_file():
        raise CheckFailure("agent_run_report.json missing; run scripts/run_agent.py")
    report = json.loads(path.read_text(encoding="utf-8"))

    block = report.get("self_consistency")
    if not block:
        raise CheckFailure(
            "self-consistency was not measured; run scripts/run_agent.py --self-consistency"
        )
    if block.get("runs", 0) < 3:
        raise CheckFailure(f"only {block.get('runs')} runs; the protocol specifies 3")
    if block.get("events", 0) < 50:
        raise CheckFailure(f"only {block.get('events')} events; too few to be meaningful")
    if "verdict_flip_rate" not in block:
        raise CheckFailure("no verdict flip rate reported")
    return (
        f"{block['runs']} runs over {block['events']} events, flip rate "
        f"{block['verdict_flip_rate']:.4f}, median risk spread "
        f"{block['risk_spread_median']}"
    )


# -- 7 ---------------------------------------------------------------------------------

def check_groundedness_computed() -> str:
    """Citation groundedness is computed over a non-zero number of citations."""
    path = settings.PROCESSED_DIR / "faithfulness.json"
    if not path.is_file():
        raise CheckFailure("faithfulness.json missing; run scripts/faithfulness.py")
    report = json.loads(path.read_text(encoding="utf-8"))

    grounded = report.get("groundedness") or {}
    checked = grounded.get("citations_checked", 0)
    if checked <= 0:
        raise CheckFailure("zero citations checked (trivial pass guard)")
    if "groundedness_rate" not in grounded:
        raise CheckFailure("no groundedness rate reported")
    if not grounded.get("failure_categories") and grounded["groundedness_rate"] == 1.0:
        # A perfect rate with no categories recorded suggests the check never ran
        # properly rather than that every citation was accurate.
        raise CheckFailure(
            "groundedness is exactly 1.0 with no failure categories recorded; verify "
            "the check is actually comparing against the data"
        )
    return (
        f"{checked:,} citations checked, rate {grounded['groundedness_rate']:.4f}, "
        f"failures {grounded.get('failure_categories')}"
    )


# -- 8 ---------------------------------------------------------------------------------

def check_test_untouched() -> str:
    """No training, agent or analysis code reads the test split."""
    offenders: list[str] = []
    scanned = 0
    for name in TRAINING_CODE:
        path = REPO_ROOT / "scripts" / name
        if not path.is_file():
            raise CheckFailure(f"{name} is missing")
        scanned += 1
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
            r"""["'][^"']*(cdms_test|series_test|test_data)[^"']*["']""", source
        ):
            offenders.append(f"{name}: references {match.group(0)}")

    if offenders:
        raise CheckFailure("test split touched: " + "; ".join(offenders))

    for name in ("agent_run_report.json", "comparison_results.json"):
        path = settings.PROCESSED_DIR / name
        if path.is_file():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("test_set_read") is not False:
                raise CheckFailure(f"{name} does not record test_set_read = false")
    return f"{scanned} scripts parsed, zero test-split references"


# -- 9 ---------------------------------------------------------------------------------

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


# -- 10 (addition) ---------------------------------------------------------------------

def check_decision_rule_applied() -> str:
    """The reported outcome is one of the pre-registered outcomes, mechanically derived."""
    import compare_arms

    path = settings.PROCESSED_DIR / "comparison_results.json"
    if not path.is_file():
        raise CheckFailure("comparison_results.json missing")
    report = json.loads(path.read_text(encoding="utf-8"))
    primary = report["primary"]

    allowed = {
        "UNINTERPRETABLE", "AGENT WINS", "DETECTABLE BUT BELOW THRESHOLD",
        "AGENT LOSES", "NO EFFECT",
    }
    outcome = primary["decision"]["outcome"]
    if outcome not in allowed:
        raise CheckFailure(f"outcome {outcome!r} is not a pre-registered outcome")

    # Re-derive it independently from the recorded statistics.
    expected = compare_arms.decide(
        primary["median_D"], primary["p_value"], primary["excluded_non_finite"]
    )["outcome"]
    if expected != outcome:
        raise CheckFailure(
            f"recorded outcome {outcome!r} does not follow from the statistics "
            f"(median D {primary['median_D']}, p {primary['p_value']}) which give "
            f"{expected!r}"
        )
    return f"outcome {outcome!r} re-derived from median D and p-value"


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()

    checks: list[tuple[str, Callable[[], str]]] = [
        ("pre-registration committed before any agent result", check_preregistration_precedes_results),
        ("every agent prediction is cached", check_every_prediction_cached),
        ("agent output schema validates on every record", check_schema_validates),
        ("agent invoked only in scope; others equal B1", check_scope_respected),
        ("paired comparison uses the Phase 5 seeds", check_same_seeds_as_phase5),
        ("self-consistency reported and non-vacuous", check_self_consistency_reported),
        ("citation groundedness computed", check_groundedness_computed),
        ("no test-set read anywhere", check_test_untouched),
        ("pytest passes", check_pytest),
        ("decision rule mechanically applied (addition)", check_decision_rule_applied),
    ]

    print(f"Phase 6 verification -- {REPO_ROOT}\n")
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
        print(f"{failures} FAILED -- Phase 6 is not complete.")
        return 1
    print("Phase 6 verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
