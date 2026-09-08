"""End-to-end verification of Phase 11 (rewritten) — the audit corrections.

Prints one pass/fail line per check and exits non-zero if any fails. Every check treats a
*vacuous* pass as a failure.

Check 1 is the load-bearing one, and it is deliberately two-sided. A leakage test that has
only ever been seen to pass has not been shown to detect anything, so it is required to
**fail** on the frozen module and **pass** on the corrected one.

Check 4 is the one that decides how much of the project survives. The Phase 7 primary
compared B1 against the v1 agent; if either had consumed the leaking features, the headline
result would fall with them. That is proven here rather than assumed.

    python scripts/verify_phase11.py
"""

from __future__ import annotations

import argparse
import ast
import json
import logging
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "tests"))

from core.config import settings  # noqa: E402
from verify_phase1 import CheckFailure  # noqa: E402

logging.disable(logging.INFO)

FROZEN_MANIFEST = REPO_ROOT / "docs" / "PHASE7_FROZEN_MANIFEST.md"


def _git(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=REPO_ROOT, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise CheckFailure(f"git {' '.join(arguments)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


# -- 1 ---------------------------------------------------------------------------------

def check_invariance_test_is_two_sided() -> str:
    """The invariance test must fire on the frozen module and be silent on the corrected one."""
    completed = subprocess.run(
        # -v without -q: the per-test names are what distinguishes the firing half of the
        # suite from the passing half, and -q suppresses them.
        [sys.executable, "-m", "pytest", "-v", "--no-header", "tests/test_causal_features.py"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    if completed.returncode != 0:
        tail = (completed.stdout or completed.stderr).strip().splitlines()[-3:]
        raise CheckFailure("the invariance suite failed: " + " | ".join(tail))

    output = completed.stdout
    fires = [line for line in output.splitlines() if "test_the_frozen_module_leaks" in line]
    silent = [
        line for line in output.splitlines()
        if "test_the_causal_module_is_invariant" in line
    ]
    if not fires:
        raise CheckFailure(
            "no test asserts the invariance check FIRES on core/features.py; a leakage "
            "test never seen to fail has not been shown to detect anything"
        )
    if not silent:
        raise CheckFailure("no test asserts the corrected module is invariant")
    passed = re.search(r"(\d+) passed", output)
    if not passed or int(passed.group(1)) < 8:
        raise CheckFailure(f"only {passed.group(1) if passed else 0} invariance tests ran")

    return (
        f"{passed.group(1)} tests: {len(fires)} assert the check fires on "
        f"core/features.py, {len(silent)} assert core/features_causal.py is invariant"
    )


# -- 2 ---------------------------------------------------------------------------------

def check_corrected_module_reads_nothing_inside_the_cutoff() -> str:
    """No corrected feature is computed from a CDM at time_to_tca < 2.

    Checked two ways: statically, that every aggregate in the corrected query sources from
    the visible CTE; and empirically, that the built features carry no evidence of the
    excluded rows.
    """
    from core.evaluation import TASK
    from core.features_causal import (
        FEATURE_COLUMNS_CAUSAL,
        LEAKING_COLUMNS,
        build_dataset_causal,
    )

    cutoff = TASK.input_cutoff_days
    source = (REPO_ROOT / "core" / "features_causal.py").read_text(encoding="utf-8")
    # The one place `cdm` may be read directly is the eligibility selector, which defines
    # the cohort and never becomes a feature.
    if "from cdm c join elig" not in source:
        raise CheckFailure("the corrected query no longer restricts features to the vis CTE")
    if "from vis" not in source and "from ranked" not in source:
        raise CheckFailure("the corrected query does not aggregate over the visible CTE")

    for column in LEAKING_COLUMNS:
        if column in FEATURE_COLUMNS_CAUSAL:
            raise CheckFailure(f"{column} survived into the corrected feature list")

    parts = []
    for split in ("train", "test"):
        frame = build_dataset_causal(split)
        if frame.empty:
            raise CheckFailure(f"{split}: no events built")
        worst = float(frame["latest_time_to_tca"].min())
        if worst < cutoff:
            raise CheckFailure(
                f"{split}: a visible CDM sits at {worst:.4f} days, inside the {cutoff}-day cutoff"
            )
        earliest = float(frame["last_visible_days"].min())
        if earliest < cutoff:
            raise CheckFailure(
                f"{split}: last_visible_days reaches {earliest:.4f}, inside the cutoff"
            )
        parts.append(f"{split} {len(frame):,} events, min visible ttc {worst:.4f} d")

    return (
        f"{len(FEATURE_COLUMNS_CAUSAL)} corrected features, none from inside the "
        f"{cutoff}-day cutoff; " + "; ".join(parts)
    )


# -- 3 ---------------------------------------------------------------------------------

def check_frozen_artefacts_untouched() -> str:
    """Every Phase 7 frozen artefact still hashes to its manifest blob."""
    if not FROZEN_MANIFEST.is_file():
        raise CheckFailure(f"{FROZEN_MANIFEST} is missing")
    rows = re.findall(
        r"^\|\s*`([^`]+)`\s*\|\s*`([0-9a-f]+)`\s*\|\s*`([0-9a-f]+)`\s*\|",
        FROZEN_MANIFEST.read_text(encoding="utf-8"), re.MULTILINE,
    )
    if not rows:
        raise CheckFailure("the manifest lists no artefacts (trivial pass guard)")

    drifted = []
    for path, _last_commit, blob in rows:
        target = REPO_ROOT / path
        if not target.is_file():
            drifted.append(f"{path}: missing from the tree")
            continue
        current = _git("hash-object", path)
        if not current.startswith(blob):
            drifted.append(f"{path}: blob {current[:12]}, manifest says {blob}")
    if drifted:
        raise CheckFailure(
            "frozen artefacts have drifted, so the published Phase 7 result is no longer "
            "reproducible byte-for-byte: " + "; ".join(drifted)
        )
    return f"{len(rows)} frozen artefacts match their manifest blob hashes exactly"


# -- 4 ---------------------------------------------------------------------------------

def check_b1_and_agent_are_independent_of_the_leak() -> str:
    """The Phase 7 primary compared B1 against v1. Neither may touch a leaking feature.

    Proven three ways, because this decides how much of the project survives:

    1. **Statically**, that no leaking column name appears in the agent's prompt
       construction or in B1's definition.
    2. **By mutation**, that ``latest_risk`` -- which *is* B1 -- does not move when
       post-cutoff data changes.
    3. **Structurally**, that the agent's evidence comes from a CDM loader which applies
       the 2-day cutoff and offers no way to disable it.
    """
    from core.features_causal import LEAKING_COLUMNS
    from core.kelvins_store import VISIBILITY_CUTOFF_DAYS, load_visible_cdms

    # 1 -- static
    offenders = []
    for relative in ("agent/triage_agent.py", "core/kelvins_store.py"):
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        for column in LEAKING_COLUMNS:
            if column in source:
                offenders.append(f"{relative} mentions {column}")
    if offenders:
        raise CheckFailure("; ".join(offenders))

    # 2 -- by mutation: B1 is latest_risk, and it must be invariant.
    from test_causal_features import MUTATIONS, NOISE_TOLERANCE, _build, _reading_from
    from core.features import build_dataset

    root = Path(tempfile.mkdtemp(prefix="phase11-check4-"))
    try:
        base = root / "base"
        (base / "kelvins").mkdir(parents=True)
        for name in ("cdms_train.parquet", "series_train.parquet"):
            shutil.copy(settings.PROCESSED_DIR / "kelvins" / name, base / "kelvins" / name)
        with _reading_from(base):
            cohort = build_dataset("train", eligible_only=True)["series_id"].astype(str).tolist()[:300]
        cdms = pd.read_parquet(base / "kelvins" / "cdms_train.parquet")

        for label, mutation in MUTATIONS.items():
            directory = root / f"m_{label}"
            (directory / "kelvins").mkdir(parents=True)
            mutation(cdms).to_parquet(directory / "kelvins" / "cdms_train.parquet")
            shutil.copy(
                base / "kelvins" / "series_train.parquet",
                directory / "kelvins" / "series_train.parquet",
            )
            before = _build("frozen", base, cohort, ["latest_risk"])
            after = _build("frozen", directory, cohort, ["latest_risk"])
            left = before["latest_risk"].to_numpy(dtype=np.float64)
            right = after["latest_risk"].to_numpy(dtype=np.float64)
            if not np.allclose(left, right, rtol=NOISE_TOLERANCE, atol=0.0, equal_nan=True):
                raise CheckFailure(
                    f"B1's prediction (latest_risk) moved under mutation {label!r}; the "
                    "Phase 7 primary would fall with the leak"
                )
    finally:
        shutil.rmtree(root, ignore_errors=True)

    # 3 -- structural: the agent's evidence loader enforces the cutoff and cannot be told not to.
    loader_source = (REPO_ROOT / "core" / "kelvins_store.py").read_text(encoding="utf-8")
    tree = ast.parse(loader_source)
    signature = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "load_visible_cdms"
    )
    argument_names = [a.arg for a in signature.args.args]
    if any("cutoff" in name for name in argument_names):
        raise CheckFailure(
            "load_visible_cdms takes a cutoff argument; a caller could read the label"
        )
    sample = load_visible_cdms(cohort[:20], "train")
    if not sample:
        raise CheckFailure("the CDM loader returned nothing (trivial pass guard)")
    for series_id, frame in sample.items():
        if float(frame["time_to_tca_days"].min()) < VISIBILITY_CUTOFF_DAYS:
            raise CheckFailure(f"{series_id}: the loader returned a post-cutoff CDM")

    return (
        f"no leaking column appears in the agent or the CDM loader; B1's latest_risk is "
        f"invariant under all {len(MUTATIONS)} mutations; the loader enforces the "
        f"{VISIBILITY_CUTOFF_DAYS}-day cutoff with no parameter to disable it"
    )


# -- 5 ---------------------------------------------------------------------------------

def check_screener_catches_the_counterexample() -> str:
    """The corrected screener keeps an interval the old prefilter discarded."""
    from orbital.propagate import (
        candidate_indices,
        max_relative_speed_over_interval,
        swept_separation_lower_bound,
    )

    ranges = np.array([1200.0, 420.0, 420.0, 1200.0])
    speeds = np.full(4, 14.0)
    radii = np.full(4, 7000.0)

    interior = np.flatnonzero(
        (ranges[1:-1] <= ranges[:-2]) & (ranges[1:-1] <= ranges[2:])
    ) + 1
    old_keeps = [int(i) for i in interior if ranges[i] < 10.0 * 5]
    if old_keeps:
        raise CheckFailure(
            "the old prefilter no longer discards the counterexample; the regression this "
            "guards has changed shape"
        )

    kept = candidate_indices(ranges, speeds, radii, 60.0, 10.0)
    if not kept:
        raise CheckFailure("the corrected screener also discards the counterexample")

    # And the bound must be a genuine lower bound, or rejecting on it is unsound.
    rng = np.random.default_rng(3)
    worst = 0.0
    for _ in range(2000):
        speed, step = rng.uniform(0.5, 16.0), rng.uniform(1.0, 300.0)
        closest_at, miss = rng.uniform(-1.0, 1.0) * step, rng.uniform(0.0, 50.0)
        times = np.linspace(0.0, step, 1001)
        truth = float(np.min(np.hypot(miss, speed * (times - closest_at))))
        bound = swept_separation_lower_bound(
            float(np.hypot(miss, speed * -closest_at)),
            float(np.hypot(miss, speed * (step - closest_at))), speed, step,
        )
        worst = max(worst, bound - truth)
    if worst > 1e-9:
        raise CheckFailure(f"the bound exceeded the true minimum by {worst:.3e} km")

    speed = max_relative_speed_over_interval(14.0, 14.0, 7000.0, 60.0)
    bound = swept_separation_lower_bound(420.0, 420.0, speed, 60.0)
    return (
        f"the old 5x prefilter keeps nothing; the swept bound keeps {kept} "
        f"(bound {bound:.1f} km <= 10 km) and never exceeds the true minimum over 2,000 "
        "random crossings"
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
        passed.append(f"phase{phase} {match.group(1)}/{match.group(2)}" if match else f"phase{phase}")
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
        ("the invariance test fires on the frozen module and passes on the corrected one",
         check_invariance_test_is_two_sided),
        ("no corrected feature reads inside the 2-day cutoff",
         check_corrected_module_reads_nothing_inside_the_cutoff),
        ("the Phase 7 frozen artefacts are byte-identical to the manifest",
         check_frozen_artefacts_untouched),
        ("B1 and the v1 agent are provably independent of the leaking features",
         check_b1_and_agent_are_independent_of_the_leak),
        ("the corrected screener catches the counterexample",
         check_screener_catches_the_counterexample),
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
