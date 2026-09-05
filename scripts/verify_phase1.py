"""End-to-end verification of Phase 1.

Prints one pass/fail line per check and exits non-zero if any check fails. Checks are
written to fail loudly on a *trivial* pass too -- a check that loaded zero records or
scanned zero files is reported as a failure, not a success.

Run from the repo root::

    python scripts/verify_phase1.py
    python scripts/verify_phase1.py --skip-checksums   # skip the 620 MB rehash
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import math
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable, Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

PASS = "PASS"
FAIL = "FAIL"

#: Directories never scanned for source or imports.
EXCLUDED_DIRS = {".venv", ".git", "__pycache__", "node_modules", ".pytest_cache"}

#: import name -> distribution name as it appears in requirements.txt
IMPORT_TO_DISTRIBUTION = {
    "dotenv": "python-dotenv",
    # `from google import genai` comes from the google-genai distribution.
    "google": "google-genai",
    "yaml": "pyyaml",
    "sklearn": "scikit-learn",
    "dateutil": "python-dateutil",
}

#: Packages defined inside this repo; they are not third-party dependencies.
FIRST_PARTY = {"core", "data", "agent", "orbital", "scripts", "tests", "legacy"}


def _local_module_names() -> set[str]:
    """Modules that live in this repo and are imported by sibling path insertion.

    Scripts add ``scripts/`` to ``sys.path`` and import each other by bare name
    (``import run_baselines``). Those are first-party by definition; without this they
    would be reported as undeclared third-party dependencies.
    """
    names = set(FIRST_PARTY)
    for directory in (REPO_ROOT, REPO_ROOT / "scripts", REPO_ROOT / "tests"):
        if not directory.is_dir():
            continue
        for path in directory.glob("*.py"):
            names.add(path.stem)
        for path in directory.iterdir():
            if path.is_dir() and (path / "__init__.py").is_file():
                names.add(path.name)
    return names


class CheckFailure(AssertionError):
    """Raised by a check to report a specific, named failure."""


# --------------------------------------------------------------------------------------
# check 1 -- imports
# --------------------------------------------------------------------------------------

def check_imports() -> str:
    """core.schema and core.config import cleanly."""
    import core.config as config
    import core.schema as schema

    if not hasattr(schema, "ConjunctionEvent"):
        raise CheckFailure("core.schema does not define ConjunctionEvent")
    if not hasattr(config, "settings"):
        raise CheckFailure("core.config does not define `settings`")
    if schema.PC_FLOOR != 1e-10:
        raise CheckFailure(f"PC_FLOOR is {schema.PC_FLOOR!r}, expected 1e-10")
    return "core.schema and core.config import cleanly; PC_FLOOR = 1e-10"


# --------------------------------------------------------------------------------------
# check 2 -- round-trip on real fixture rows
# --------------------------------------------------------------------------------------

def _load_fixture_events() -> list:
    import pandas as pd

    from core.schema import ConjunctionEvent, EventSource

    sources = {
        "ivv_spherical_head50.csv": EventSource.TRACSS_SPHERICAL,
        "ivv_sfsh_head50.csv": EventSource.TRACSS_SFSH,
    }
    fixtures_dir = REPO_ROOT / "tests" / "fixtures"
    events = []
    for filename, source in sources.items():
        path = fixtures_dir / filename
        if not path.is_file():
            raise CheckFailure(
                f"missing fixture {path.name}; run scripts/build_fixtures.py"
            )
        frame = pd.read_csv(path)
        if frame.empty:
            raise CheckFailure(f"fixture {path.name} has zero data rows")
        for row in frame.to_dict(orient="records"):
            events.append(ConjunctionEvent.from_ivv_row(row, source))
    if not events:
        raise CheckFailure("no events loaded from fixtures (trivial pass guard)")
    return events


def check_round_trip() -> str:
    """A real fixture row round-trips to_dict -> from_dict with every field identical."""
    import numpy as np

    from core.schema import ConjunctionEvent

    events = _load_fixture_events()
    if len(events) < 100:
        raise CheckFailure(f"expected >= 100 fixture events, loaded {len(events)}")

    for event in events:
        restored = ConjunctionEvent.from_dict(event.to_dict())
        if restored != event:
            raise CheckFailure(f"{event.event_id}: round-trip is not identical")
        if restored.to_dict() != event.to_dict():
            raise CheckFailure(f"{event.event_id}: round-tripped dict differs")
        if restored.tca != event.tca or restored.tca.utcoffset() is None:
            raise CheckFailure(f"{event.event_id}: tca lost its timezone")
        for label, a, b in (
            ("object1", event.object1, restored.object1),
            ("object2", event.object2, restored.object2),
        ):
            if not np.array_equal(a.covariance, b.covariance):
                raise CheckFailure(f"{event.event_id}: {label} covariance changed")

    censored = sum(1 for e in events if e.pc_is_floored)
    if censored == 0 or censored == len(events):
        raise CheckFailure(
            f"fixtures are degenerate: {censored}/{len(events)} censored; "
            "expected a mix so the pc_is_floored flag is actually exercised"
        )
    return (
        f"{len(events)} fixture events round-trip exactly "
        f"(covariance + tz-aware tca preserved); {censored} censored, "
        f"{len(events) - censored} not"
    )


# --------------------------------------------------------------------------------------
# check 3 -- covariance
# --------------------------------------------------------------------------------------

def check_covariances() -> str:
    """Reconstructed covariance matrices are symmetric and positive-semidefinite."""
    import numpy as np

    events = _load_fixture_events()
    checked = 0
    worst = math.inf
    for event in events:
        for label, state in (("object1", event.object1), ("object2", event.object2)):
            cov = state.covariance
            if cov is None:
                raise CheckFailure(f"{event.event_id}: {label} has no covariance")
            if cov.shape != (3, 3):
                raise CheckFailure(f"{event.event_id}: {label} covariance {cov.shape}")
            if not np.array_equal(cov, cov.T):
                raise CheckFailure(f"{event.event_id}: {label} not symmetric")
            smallest = float(np.min(np.linalg.eigvalsh(cov)))
            if smallest < -1e-10:
                raise CheckFailure(
                    f"{event.event_id}: {label} not PSD (min eigenvalue {smallest:.6g})"
                )
            worst = min(worst, smallest)
            checked += 1

    if checked != 2 * len(events):
        raise CheckFailure(f"checked {checked} covariances, expected {2 * len(events)}")
    return (
        f"{checked} covariances symmetric and positive-semidefinite "
        f"(smallest eigenvalue seen: {worst:.6g})"
    )


# --------------------------------------------------------------------------------------
# check 4 -- validate() rejects malformed input
# --------------------------------------------------------------------------------------

def check_validation_rejects() -> str:
    """validate() raises on each deliberately malformed input."""
    import copy

    import numpy as np

    from core.schema import SchemaValidationError

    good = _load_fixture_events()[0]

    def naive_tca(event):
        event.tca = event.tca.replace(tzinfo=None)

    def negative_miss(event):
        event.miss_distance_km = -1.0

    def pc_above_one(event):
        event.pc, event.pc_is_floored = 1.5, False

    def pc_below_zero(event):
        event.pc, event.pc_is_floored = -0.5, False

    def non_finite_position(event):
        event.object1.position_km = (math.inf, 0.0, 0.0)

    def non_finite_velocity(event):
        event.object2.velocity_kms = (0.0, math.nan, 0.0)

    def asymmetric_covariance(event):
        cov = event.object1.covariance.copy()
        cov[0, 1] = cov[1, 0] + 5.0
        event.object1.covariance = cov

    def indefinite_covariance(event):
        event.object1.covariance = np.array(
            [[1.0, 2.0, 0.0], [2.0, 1.0, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64
        )

    def contradictory_floor_flag(event):
        event.pc, event.pc_is_floored = 1e-3, True

    mutations: dict[str, Callable] = {
        "naive tca": naive_tca,
        "negative miss distance": negative_miss,
        "pc > 1": pc_above_one,
        "pc < 0": pc_below_zero,
        "non-finite position": non_finite_position,
        "non-finite velocity": non_finite_velocity,
        "asymmetric covariance": asymmetric_covariance,
        "indefinite covariance": indefinite_covariance,
        "contradictory pc_is_floored": contradictory_floor_flag,
    }

    good.validate()  # the unmutated record must pass, or the check is meaningless

    for name, mutate in mutations.items():
        broken = copy.deepcopy(good)
        mutate(broken)
        try:
            broken.validate()
        except SchemaValidationError:
            continue
        raise CheckFailure(f"validate() accepted a record with: {name}")

    return f"validate() rejected all {len(mutations)} malformed inputs and accepted a real one"


# --------------------------------------------------------------------------------------
# check 5 -- pytest
# --------------------------------------------------------------------------------------

def check_pytest() -> str:
    """pytest passes."""
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    tail = (completed.stdout or completed.stderr).strip().splitlines()
    summary = tail[-1] if tail else "(no output)"
    if completed.returncode != 0:
        raise CheckFailure(f"pytest exited {completed.returncode}: {summary}")
    if re.search(r"\bno tests ran\b", summary, re.IGNORECASE):
        raise CheckFailure("pytest collected no tests (trivial pass guard)")
    match = re.search(r"(\d+) passed", summary)
    if not match or int(match.group(1)) == 0:
        raise CheckFailure(f"pytest reported no passing tests: {summary}")
    return f"pytest: {summary}"


# --------------------------------------------------------------------------------------
# check 6 -- imports vs requirements.txt
# --------------------------------------------------------------------------------------

def _iter_python_files() -> Iterable[Path]:
    """Python files git tracks, which is what "the repository's code" means.

    Scanning the whole working tree instead swept in untracked scratch -- a report
    renderer someone had left under docs/research/ pulled pymupdf and reportlab into the
    check and failed it, though neither is a dependency of anything in the repository.
    requirements.txt has to cover what is committed, not whatever happens to be sitting on
    disk. Falls back to a tree walk outside a git checkout.
    """
    listing = subprocess.run(
        ["git", "ls-files", "*.py"], cwd=REPO_ROOT, capture_output=True, text=True
    )
    if listing.returncode == 0 and listing.stdout.strip():
        candidates = [REPO_ROOT / line for line in listing.stdout.strip().splitlines()]
    else:
        candidates = list(REPO_ROOT.rglob("*.py"))

    for path in candidates:
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if path.is_file():
            yield path


def _top_level_imports(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        raise CheckFailure(f"{path.relative_to(REPO_ROOT)} does not parse: {exc}")

    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:  # ignore relative imports
                names.add(node.module.split(".")[0])
    return names


def check_requirements_cover_imports() -> str:
    """Every third-party module imported anywhere in the repo appears in requirements."""
    requirements_path = REPO_ROOT / "requirements.txt"
    if not requirements_path.is_file():
        raise CheckFailure("requirements.txt is missing")

    declared: set[str] = set()
    for line in requirements_path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            declared.add(re.split(r"[=<>!~\[]", line, maxsplit=1)[0].strip().lower())
    if not declared:
        raise CheckFailure("requirements.txt declares no packages")

    files = list(_iter_python_files())
    if not files:
        raise CheckFailure("no Python files found to scan (trivial pass guard)")

    stdlib = set(sys.stdlib_module_names)
    first_party = _local_module_names()
    imported: dict[str, set[Path]] = {}
    for path in files:
        for name in _top_level_imports(path):
            if name in stdlib or name in first_party:
                continue
            imported.setdefault(name, set()).add(path)

    missing = []
    for name, paths in sorted(imported.items()):
        distribution = IMPORT_TO_DISTRIBUTION.get(name, name).lower()
        if distribution not in declared:
            where = ", ".join(
                sorted(str(p.relative_to(REPO_ROOT)) for p in paths)
            )
            missing.append(f"{name} (imported by {where})")
    if missing:
        raise CheckFailure("imported but not in requirements.txt: " + "; ".join(missing))

    used = {
        IMPORT_TO_DISTRIBUTION.get(name, name).lower() for name in imported
    }
    unused = sorted(declared - used - {"pytest"})  # pytest is invoked, not imported
    note = f"; declared but unused: {', '.join(unused)}" if unused else ""
    return (
        f"{len(files)} files scanned, {len(imported)} third-party imports "
        f"all declared in requirements.txt{note}"
    )


# --------------------------------------------------------------------------------------
# check 7 -- dataset integrity
# --------------------------------------------------------------------------------------

def _sha256(path: Path, chunk_size: int = 1 << 20) -> str:
    """Hash a file in 1 MiB chunks -- never loads a 450 MB CSV into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_dataset_unmodified() -> str:
    """No file under dataset/ has changed since MANIFEST.md was written."""
    manifest_path = REPO_ROOT / "dataset" / "MANIFEST.md"
    if not manifest_path.is_file():
        raise CheckFailure("dataset/MANIFEST.md is missing")

    pattern = re.compile(
        r"^\|\s*`([^`]+)`\s*\|\s*([\d,]+)\s*\|[^|]*\|\s*`([0-9a-f]{64})`\s*\|"
    )
    entries: list[tuple[str, int, str]] = []
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line.strip())
        if match:
            entries.append(
                (match.group(1), int(match.group(2).replace(",", "")), match.group(3))
            )

    if not entries:
        raise CheckFailure("no checksum rows parsed from MANIFEST.md (trivial pass guard)")

    problems = []
    for filename, expected_size, expected_hash in entries:
        path = REPO_ROOT / "dataset" / filename
        if not path.is_file():
            problems.append(f"{filename}: missing from dataset/")
            continue
        actual_size = path.stat().st_size
        if actual_size != expected_size:
            problems.append(
                f"{filename}: {actual_size} bytes, manifest says {expected_size}"
            )
            continue
        actual_hash = _sha256(path)
        if actual_hash != expected_hash:
            problems.append(f"{filename}: sha256 {actual_hash[:16]}... != manifest")

    if problems:
        raise CheckFailure("; ".join(problems))
    return f"{len(entries)} dataset files match MANIFEST.md size and sha256"


def check_dataset_manifest_present() -> str:
    """Lightweight stand-in for check 7 when --skip-checksums is passed."""
    manifest_path = REPO_ROOT / "dataset" / "MANIFEST.md"
    if not manifest_path.is_file():
        raise CheckFailure("dataset/MANIFEST.md is missing")
    return "MANIFEST.md present (checksums SKIPPED by --skip-checksums)"


# --------------------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-checksums",
        action="store_true",
        help="skip rehashing the 620 MB dataset in check 7",
    )
    args = parser.parse_args()

    checks: list[tuple[str, Callable[[], str]]] = [
        ("core.schema and core.config import cleanly", check_imports),
        ("fixture events round-trip to_dict -> from_dict", check_round_trip),
        ("covariances are symmetric and positive-semidefinite", check_covariances),
        ("validate() rejects malformed input", check_validation_rejects),
        ("pytest passes", check_pytest),
        ("requirements.txt covers every import", check_requirements_cover_imports),
        (
            "dataset/ is unmodified",
            check_dataset_manifest_present if args.skip_checksums else check_dataset_unmodified,
        ),
    ]

    print(f"Phase 1 verification -- {REPO_ROOT}\n")
    failures = 0
    for number, (title, check) in enumerate(checks, start=1):
        try:
            detail = check()
        except Exception as exc:  # a check must never abort the run
            failures += 1
            print(f"[{FAIL}] {number}. {title}")
            print(f"        {type(exc).__name__}: {exc}")
        else:
            print(f"[{PASS}] {number}. {title}")
            print(f"        {detail}")

    total = len(checks)
    print(f"\n{total - failures}/{total} checks passed.")
    if failures:
        print(f"{failures} FAILED -- Phase 1 is not complete.")
        return 1
    print("Phase 1 verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
