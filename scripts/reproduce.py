"""One command from a clean clone to the Phase 7 headline table.

    python scripts/reproduce.py

What it does, in order: checks the environment, checks the datasets, builds every derived
artefact that is missing, and prints the table. Stages whose outputs already exist are
skipped, so re-running is cheap and the first run is the slow one.

Two things it deliberately will not do
--------------------------------------
**It will not download the data.** The TraCSS benchmark is 620 MB and the Kelvins archive
comes from a Zenodo record that needs accepting terms. Both are placed by hand, and this
script tells you exactly where and prints the checksums it expects. Fetching them silently
would put an unverified file where a verified one belongs.

**It will not re-run the agent unless you ask.** ``--with-agent`` re-runs the LLM arm, which
needs an API key and costs roughly $7. Without it the agent row is reported as *not
reproduced here* rather than filled in from a previous run's artefact. A table that cannot
tell a fresh number from an inherited one is not a reproduction.

Modes
-----
``--check``       verify what exists and print the table; build nothing
``--with-agent``  also re-run the agent arm (needs a credential, spends money)
``--fast``        skip the 620 MB dataset re-hash and the Pc gate
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.config import settings  # noqa: E402

PYTHON = sys.executable

DATASET_FILES = (
    "IVV_Releasable_Dataset_Spherical_DefaultHBR.csv",
    "IVV_Releasable_Dataset_SFSH_DiscreteHBR.csv",
    "AerospaceIVVDataset_20251009a_Size_ScreeningVolumes.csv",
    "Conjunction_Screening_Testset_Users_Guide.pdf",
)


@dataclass
class Stage:
    """One step of the pipeline: what it produces, and how to produce it."""

    name: str
    outputs: tuple[str, ...]
    command: Optional[list[str]]
    note: str = ""
    #: Stages that cost money or need a credential are opt-in.
    costs_money: bool = False

    def satisfied(self) -> bool:
        return all((settings.PROCESSED_DIR / out).exists() for out in self.outputs)

    def missing(self) -> list[str]:
        return [out for out in self.outputs if not (settings.PROCESSED_DIR / out).exists()]


STAGES: tuple[Stage, ...] = (
    Stage(
        "ingest TraCSS",
        ("spherical.parquet", "sfsh.parquet"),
        [PYTHON, "scripts/ingest.py"],
        "913k + 284k events, chunked; ~10 minutes on a cold run",
    ),
    Stage(
        "join hard-body radii",
        ("hbr_report.json",),
        [PYTHON, "scripts/join_hbr.py"],
        "spherical uses the 0.5 m Users Guide default; SFSH uses per-object volumes",
    ),
    Stage(
        "profile the benchmark",
        ("profile.json",),
        [PYTHON, "scripts/profile_dataset.py"],
    ),
    Stage(
        "ingest Kelvins",
        ("kelvins/cdms_train.parquet", "kelvins/cdms_test.parquet",
         "kelvins/series_train.parquet", "kelvins/series_test.parquet"),
        [PYTHON, "scripts/ingest_kelvins.py"],
        "the CDM series the task is defined on",
    ),
    Stage(
        "fit and score the baselines",
        ("baseline_results.json", "baseline_predictions.parquet"),
        [PYTHON, "scripts/run_baselines.py"],
        "B1-B5 on the train split; this is where the number to beat comes from",
    ),
    Stage(
        "reproduce the TraCSS Pc column",
        ("pc_validation_sfsh.json",),
        [PYTHON, "scripts/validate_pc.py", "--sample", "10000", "--source", "sfsh"],
        "the Phase 9 validation gate; ~20 seconds",
    ),
    Stage(
        "run the agent on the test split",
        ("agent_predictions_test.parquet",),
        [PYTHON, "scripts/run_agent_test.py"],
        "~2,167 events, one LLM call per in-scope event, roughly $7",
        costs_money=True,
    ),
    Stage(
        "score the held-out test set",
        ("test_results.json",),
        None,  # command chosen at run time: --skip-agent when the agent was not re-run
        "the single frozen evaluation",
    ),
    Stage(
        "export the frontend table",
        ("../frontend/data/phase7_results.json",),
        [PYTHON, "scripts/export_frontend_data.py"],
    ),
)


# ------------------------------------------------------------------------------------
# checks
# ------------------------------------------------------------------------------------

def check_environment() -> list[str]:
    """Interpreter and packages. Returns a list of problems, empty when fine."""
    problems: list[str] = []
    print("== environment ==")
    print(f"  python {sys.version.split()[0]}  ({sys.executable})")
    if sys.version_info < (3, 11):
        problems.append(f"python {sys.version_info.major}.{sys.version_info.minor} is too old; 3.11+ required")

    required = {}
    for line in (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if "==" in line:
            name, version = line.split("==", 1)
            required[name.strip()] = version.strip()

    import importlib.metadata as metadata

    mismatched, absent = [], []
    for name, expected in required.items():
        try:
            installed = metadata.version(name)
        except metadata.PackageNotFoundError:
            absent.append(name)
            continue
        if installed != expected:
            mismatched.append(f"{name} {installed} (pinned {expected})")

    print(f"  {len(required) - len(absent)}/{len(required)} pinned packages installed")
    if absent:
        problems.append(f"not installed: {', '.join(absent)} -- run pip install -r requirements.txt")
    if mismatched:
        # A version drift is worth saying out loud but is not fatal; the pins record what
        # the published numbers were produced with.
        print(f"  version drift: {'; '.join(mismatched)}")
    return problems


def check_datasets(fast: bool) -> list[str]:
    """Presence, and optionally checksums, of the read-only inputs."""
    problems: list[str] = []
    print("\n== datasets ==")

    dataset_dir = REPO_ROOT / "dataset"
    missing = [name for name in DATASET_FILES if not (dataset_dir / name).is_file()]
    if missing:
        problems.append(
            "missing from dataset/: " + ", ".join(missing) + "\n"
            "    The TraCSS IV&V files are not in the repository (620 MB, CC0-1.0).\n"
            "    Place them in dataset/ and check them against dataset/MANIFEST.md."
        )
    else:
        total = sum((dataset_dir / name).stat().st_size for name in DATASET_FILES)
        print(f"  TraCSS: {len(DATASET_FILES)} files, {total / 1024**2:.0f} MB")

    kelvins = dataset_dir / "kelvins"
    if not (kelvins / "train_data.csv").is_file():
        problems.append(
            "missing dataset/kelvins/train_data.csv\n"
            "    Fetch it with: python scripts/fetch_kelvins.py  (Zenodo record 4463683)"
        )
    else:
        print(f"  Kelvins: {len(list(kelvins.glob('*.csv')))} CSV files")

    if not fast and not missing:
        print("  re-hashing against MANIFEST.md ...", flush=True)
        result = subprocess.run(
            [PYTHON, "scripts/verify_phase1.py"],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        if result.returncode != 0:
            problems.append("verify_phase1.py failed; run it directly for the detail")
        else:
            print("  checksums match")
    return problems


# ------------------------------------------------------------------------------------
# running
# ------------------------------------------------------------------------------------

def run_stage(stage: Stage, command: list[str]) -> bool:
    print(f"\n-> {stage.name}")
    if stage.note:
        print(f"   {stage.note}")
    print(f"   {' '.join(command)}", flush=True)
    started = time.perf_counter()
    result = subprocess.run(command, cwd=REPO_ROOT)
    elapsed = time.perf_counter() - started
    if result.returncode != 0:
        print(f"   FAILED after {elapsed:.0f}s (exit {result.returncode})")
        return False
    print(f"   done in {elapsed:.0f}s")
    return True


def build(check_only: bool, with_agent: bool, fast: bool) -> tuple[bool, set[str]]:
    """Bring every stage up to date. Returns (ok, names of stages this run built)."""
    print("\n== pipeline ==")
    built: set[str] = set()

    for stage in STAGES:
        if fast and stage.name.startswith("reproduce the TraCSS"):
            print(f"  [skip] {stage.name} (--fast)")
            continue

        if stage.satisfied():
            print(f"  [have] {stage.name}")
            if stage.costs_money:
                # The artefact exists from an earlier run. That is fine for scoring, but it
                # is not something this invocation reproduced, and the table must say so.
                print("         (from a previous run -- not reproduced by this invocation)")
            continue

        if stage.costs_money and not with_agent:
            print(f"  [skip] {stage.name} -- needs --with-agent (a credential, and ~$7)")
            continue

        if check_only:
            print(f"  [MISSING] {stage.name}: {', '.join(stage.missing())}")
            continue

        command = stage.command
        if command is None:
            # The evaluation: score the agent only if its predictions exist.
            agent_available = (settings.PROCESSED_DIR / "agent_predictions_test.parquet").exists()
            command = [PYTHON, "scripts/evaluate_test.py"]
            if not agent_available:
                command.append("--skip-agent")
                print("  note: no agent predictions, so the agent arm will not be scored")

        if not run_stage(stage, command):
            return False, built
        built.add(stage.name)

    return True, built


# ------------------------------------------------------------------------------------
# the table
# ------------------------------------------------------------------------------------

def print_headline(built: set[str]) -> bool:
    """Print the table, saying for every row whether this invocation produced it.

    The distinction is the whole point of the script. An artefact left over from an earlier
    run scores identically and tells you nothing about whether the pipeline still works, so
    the two are never merged into one unlabelled column.
    """
    scored_here = "score the held-out test set" in built
    agent_ran = "run the agent on the test split" in built
    source = settings.PROCESSED_DIR / "test_results.json"
    if not source.is_file():
        print("\nNo test_results.json -- the evaluation has not been run.")
        return False

    results = json.loads(source.read_text(encoding="utf-8"))
    arms = results["arms"]

    print("\n" + "=" * 74)
    print("PHASE 7 HEADLINE -- the single held-out evaluation")
    print("=" * 74)
    print(f"{results.get('test_events', '?')} test events, "
          f"{results.get('test_high_risk', '?')} truly high-risk "
          f"({results.get('test_high_risk_pct', '?')}%)")
    print("Official Kelvins metric L = MSE_HR / F2. Lower is better.\n")

    order = ["B1_latest_cdm", "B2b_constant_minus5", "B3_linear_extrapolation",
             "B4_gbm_regressor", "B5_two_stage_gbm", "agent"]
    print(f"  {'arm':28s} {'L':>10s} {'MSE_HR':>9s} {'F2':>8s}   source")
    print("  " + "-" * 70)
    for name in order:
        block = arms.get(name)
        if block is None or "official" not in block:
            if name == "agent":
                print(f"  {'agent':28s} {'not reproduced':>10s}"
                      "                     re-run with --with-agent")
            continue
        official = block["official"]
        if name == "agent":
            provenance = "recomputed here" if agent_ran else "from an earlier run"
        else:
            provenance = "recomputed here" if scored_here else "from an earlier run"
        print(f"  {name:28s} {official['L']:10.4f} {official['mse_hr']:9.4f} "
              f"{official['f2']:8.4f}   {provenance}")

    comparison = arms.get("agent_vs_b1")
    if comparison:
        low, high = comparison["ci95"]
        print(f"\n  agent - B1: median {comparison['median']:+.4f}, "
              f"95% CI [{low:+.4f}, {high:+.4f}], "
              f"agent ahead in {100 * comparison['fraction_favouring_arm']:.1f}% of "
              f"{comparison['resamples']:,} resamples")

    b1 = arms.get("B1_latest_cdm", {}).get("official", {}).get("L")
    agent = arms.get("agent", {}).get("official", {}).get("L")
    if b1 is not None and agent is not None:
        print(f"\n  The agent scored {agent / b1:.1f}x worse than the one-line baseline. "
              "That is the result.")
    print("\n  Published reference: B1 should land on LRP 0.694 and the constant -5 arm on "
          "CRP 2.500\n  (arXiv:2008.03069, Table 3). Both matching is what licenses the rest "
          "of the table.")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true",
                        help="verify and report; build nothing")
    parser.add_argument("--with-agent", action="store_true",
                        help="also re-run the LLM arm (needs a credential, costs ~$7)")
    parser.add_argument("--fast", action="store_true",
                        help="skip the dataset re-hash and the Pc gate")
    args = parser.parse_args()

    started = time.perf_counter()
    print("ConjunctionTriage -- reproduce the published result")
    print(f"repository: {REPO_ROOT}\n")

    problems = check_environment() + check_datasets(args.fast)
    if problems:
        print("\n== blocked ==")
        for problem in problems:
            print(f"  - {problem}")
        print("\nFix the above and re-run. Nothing was built.")
        return 1

    ok, built = build(args.check, args.with_agent, args.fast)
    if not ok:
        print("\nA stage failed. Nothing further was attempted.")
        return 1

    if not print_headline(built):
        return 1

    print(f"\ntotal {time.perf_counter() - started:.0f}s")
    if not args.with_agent:
        print("The agent arm was not re-run. Add --with-agent to reproduce it end to end.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
