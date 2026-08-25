"""End-to-end verification of Phase 9 — the working system.

Prints one pass/fail line per check and exits non-zero if any fails. Every check treats a
*vacuous* pass as a failure: an empty tool list, a zero-row comparison and a manifest with
no artefacts all fail rather than passing quietly.

Phase 9 is engineering, so most of these check that a claim made in code is true of the
code — that the API really refuses to guess a covariance frame, that the MCP descriptions
really carry their units, that the frozen Phase 7 artefacts really were not touched.

    python scripts/verify_phase9.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from core.config import settings  # noqa: E402
from verify_phase1 import CheckFailure  # noqa: E402

# Importing the MCP SDK installs a rich logging handler and puts the root logger at
# INFO, after which every TestClient request prints three wrapped lines and buries the
# check output. Naming the httpx logger is not enough -- the records arrive under
# several names -- so INFO and below is disabled outright for this run. WARNING and
# above still print, which is what would actually indicate a problem.
logging.disable(logging.INFO)


def _git(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=REPO_ROOT, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise CheckFailure(f"git {' '.join(arguments)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


# -- 1 ---------------------------------------------------------------------------------

def check_sgp4_reference() -> str:
    """SGP4 reproduces the published Vallado state, and the reference is not self-made."""
    from orbital.propagate import REFERENCE_CASE, verify_reference_case

    report = verify_reference_case()
    if not report["within_tolerance"]:
        raise CheckFailure(
            f"position residual {report['position_residual_km']:.6f} km exceeds the "
            f"{report['tolerance_km']} km tolerance"
        )
    if "Vallado" not in REFERENCE_CASE["source"]:
        raise CheckFailure("the reference case does not name a published source")
    if report["position_residual_km"] == 0.0:
        raise CheckFailure(
            "a residual of exactly zero suggests the expected values were taken from our "
            "own output rather than from the published answer"
        )
    return (
        f"{report['case']}: position residual {report['position_residual_m']:.6f} m, "
        f"velocity residual {report['velocity_residual_mm_s']:.4f} mm/s"
    )


# -- 2 ---------------------------------------------------------------------------------

def check_pc_reproduction() -> str:
    """The Pc gate ran on at least 10,000 events and agrees with the published column."""
    found = []
    for source in ("sfsh", "spherical"):
        path = settings.PROCESSED_DIR / f"pc_validation_{source}.json"
        if not path.is_file():
            continue
        report = json.loads(path.read_text(encoding="utf-8"))
        if report["sampled"] < 10_000:
            raise CheckFailure(
                f"{source}: only {report['sampled']} events sampled; the gate requires "
                "at least 10,000"
            )
        comparable = report["comparable"]
        if comparable < 1000:
            raise CheckFailure(
                f"{source}: only {comparable} comparable events (trivial pass guard)"
            )
        if report["censored_excluded"] == 0:
            raise CheckFailure(
                f"{source}: no censored rows were excluded, which cannot be right for a "
                "column with a 1e-10 floor -- the exclusion is probably not happening"
            )
        agreement = report["agreement"]
        if agreement["within_factor_10"] < 0.99:
            raise CheckFailure(
                f"{source}: only {100 * agreement['within_factor_10']:.2f}% agree within "
                "an order of magnitude"
            )
        median = report["log10_ratio_ours_over_theirs"]["median"]
        found.append(
            f"{source}: n={comparable:,} median log10 ratio {median:+.2e}, "
            f"{100 * agreement['within_0.1_percent']:.2f}% within 0.1%, "
            f"{report['censored_excluded']:,} censored excluded"
        )
    if not found:
        raise CheckFailure(
            "no pc_validation_*.json; run scripts/validate_pc.py --sample 10000"
        )
    return "; ".join(found)


# -- 3 ---------------------------------------------------------------------------------

def check_frame_choice_is_not_cosmetic() -> str:
    """The covariance frame changes the answer, so nothing may default it.

    If the two readings agreed, requiring the argument would be pedantry. They do not, by
    six orders of magnitude, which is what makes a silent default a correctness bug.
    """
    from orbital.pc import pc_from_states

    r1 = np.array([7000.0, 0.0, 0.0])
    v1 = np.array([0.0, 7.5, 0.0])
    r2 = r1 + np.array([0.2, 0.1, 0.3])
    v2 = np.array([2.0, 3.0, 6.5])
    covariance = np.diag([1e-4, 4.0, 1e-4])

    as_uvw = pc_from_states(r1, v1, covariance, r2, v2, covariance,
                            hbr1_m=10.0, hbr2_m=10.0, covariance_frame="uvw")
    as_eci = pc_from_states(r1, v1, covariance, r2, v2, covariance,
                            hbr1_m=10.0, hbr2_m=10.0, covariance_frame="eci")
    ratio = as_uvw.pc / as_eci.pc
    if ratio < 1e3:
        raise CheckFailure(
            f"the two frames differ by only {ratio:.3g}x here; this check is not "
            "exercising the transform"
        )

    # And the API must require the field rather than defaulting it.
    from api.models import PcRequest

    field = PcRequest.model_fields["covariance_frame"]
    if not field.is_required():
        raise CheckFailure("api.models.PcRequest.covariance_frame has a default")

    from mcp_server.server import server

    tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}
    required = tools["compute_pc"].input_schema.get("required") or []
    if "covariance_frame" not in required:
        raise CheckFailure("the MCP compute_pc tool does not require covariance_frame")

    return (
        f"uvw/eci differ by {ratio:.3g}x on one geometry; required with no default in "
        "both the API model and the MCP tool schema"
    )


# -- 4 ---------------------------------------------------------------------------------

def check_api_surface_and_errors() -> str:
    """Every endpoint exists, and no failure path returns a bare 500."""
    from fastapi.testclient import TestClient

    from api.main import app

    client = TestClient(app, raise_server_exceptions=False)
    schema = client.get("/openapi.json").json()
    expected = {"/health", "/pc", "/screen", "/events", "/triage"}
    if set(schema["paths"]) != expected:
        raise CheckFailure(
            f"endpoints are {sorted(schema['paths'])}, expected {sorted(expected)}"
        )

    # Each of these must come back structured, with a stable code, not as a stack trace.
    probes = [
        ("POST", "/pc", {"object1": {"position_km": [1, 2, 3]}}, "invalid_request"),
        ("POST", "/pc", {
            "object1": {"position_km": [7000, 0, 0], "velocity_kms": [0, 7.5, 0],
                        "covariance": [[-4, 0, 0], [0, 4, 0], [0, 0, 0.02]],
                        "hard_body_radius_m": 5},
            "object2": {"position_km": [7000, 0, 0.4], "velocity_kms": [0, 0, 7.5],
                        "covariance": [[0.02, 0, 0], [0, 9, 0], [0, 0, 0.03]],
                        "hard_body_radius_m": 3},
            "covariance_frame": "uvw"}, "pc_undefined"),
        ("POST", "/screen", {
            "object1": {"line1": "1 " + "x" * 60, "line2": "2 " + "y" * 60},
            "object2": {"line1": "1 " + "x" * 60, "line2": "2 " + "y" * 60},
            "start_utc": "2026-01-01T00:00:00Z", "stop_utc": "2026-01-01T01:00:00Z"},
         None),
        ("POST", "/triage", {"series_ids": [f"s{i}" for i in range(40)]},
         "invalid_request"),
    ]

    for method, path, body, expected_code in probes:
        response = client.request(method, path, json=body)
        if response.status_code == 500:
            raise CheckFailure(f"{method} {path} returned a bare 500")
        payload = response.json()
        if "error" not in payload or "detail" not in payload:
            raise CheckFailure(f"{method} {path} returned an unstructured body: {payload}")
        if expected_code and payload["error"] != expected_code:
            raise CheckFailure(
                f"{method} {path} returned {payload['error']!r}, expected {expected_code!r}"
            )

    health = client.get("/health").json()
    if health["checks"]["sgp4"]["ok"] is not True:
        raise CheckFailure("/health reports SGP4 unavailable, which needs no data or key")

    return (
        f"{len(expected)} endpoints documented; {len(probes)} failure paths all returned "
        "a structured error, none a bare 500"
    )


# -- 5 ---------------------------------------------------------------------------------

def check_mcp_tools_state_their_units() -> str:
    """The four tools exist and every description carries its units and caveats.

    A tool description is the only briefing the calling model gets before it chooses
    arguments, so a missing unit is a defect rather than a documentation gap.
    """
    from mcp_server.server import server

    tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}
    expected = {"fetch_conjunctions", "compute_pc", "get_object_metadata", "triage_events"}
    if set(tools) != expected:
        raise CheckFailure(f"tools are {sorted(tools)}, expected {sorted(expected)}")

    required = {
        "compute_pc": ["km^2", "METRES", "J2000/ECI", "covariance_frame"],
        "fetch_conjunctions": ["km", "km/s", "metres", "1e-10", "upper bounds"],
        "get_object_metadata": ["metres", "censored"],
        "triage_events": ["The agent LOST.", "1.6606", "0.6940", "baseline_risk"],
    }
    for name, tokens in required.items():
        description = tools[name].description or ""
        missing = [token for token in tokens if token not in description]
        if missing:
            raise CheckFailure(f"{name} description omits {missing}")

    instructions = server.instructions or ""
    for token in ("1e-10", "upper bound", "UVW"):
        if token not in instructions:
            raise CheckFailure(f"server instructions omit {token!r}")

    return (
        f"{len(tools)} tools; all descriptions state their units, the censoring floor and "
        "the frame requirement, and triage_events leads with the loss"
    )


# -- 6 ---------------------------------------------------------------------------------

def check_censoring_is_never_silently_averaged() -> str:
    """Everything that serves `pc` marks or excludes the floor.

    A censored value is an upper bound. Any surface that hands one out without saying so
    invites a consumer to average it into a number that means nothing.
    """
    from mcp_server.server import fetch_conjunctions, server  # noqa: F401
    from core.store import StoreError, store

    try:
        store.available()
    except StoreError as exc:
        raise CheckFailure(f"the ingested benchmark is required for this check: {exc}")

    # The MCP tool excludes censored rows by default.
    default = fetch_conjunctions(source="sfsh", limit=25)
    if not default.get("ok"):
        raise CheckFailure(f"fetch_conjunctions failed: {default}")
    if not default["events"]:
        raise CheckFailure("fetch_conjunctions returned no events (trivial pass guard)")
    censored = [event for event in default["events"] if event["pc_is_floored"]]
    if censored:
        raise CheckFailure(
            f"{len(censored)} censored events returned by default from fetch_conjunctions"
        )

    # And when they are asked for, every one is flagged.
    included = fetch_conjunctions(source="spherical", limit=50, exclude_floored=False)
    if not all("pc_is_floored" in event for event in included["events"]):
        raise CheckFailure("an event was returned with no pc_is_floored flag")

    # The API marks rather than hides.
    from fastapi.testclient import TestClient

    from api.main import app

    client = TestClient(app, raise_server_exceptions=False)
    body = client.get("/events", params={"source": "sfsh", "limit": 20}).json()
    if not all("pc_is_floored" in event for event in body["events"]):
        raise CheckFailure("/events returned an event with no pc_is_floored flag")
    if not any("floor" in caveat for caveat in body["provenance"]["caveats"]):
        raise CheckFailure("/events provenance does not mention the censoring floor")

    # The Pc gate excludes them from its ratio statistics.
    report = json.loads(
        (settings.PROCESSED_DIR / "pc_validation_sfsh.json").read_text(encoding="utf-8")
    )
    if report["comparable"] + report["censored_excluded"] > report["sampled"]:
        raise CheckFailure("the censored rows were counted inside the comparable set")

    return (
        f"MCP excludes censored rows by default and flags them when asked; /events flags "
        f"every row and says so in its provenance; the Pc gate excluded "
        f"{report['censored_excluded']:,} of {report['sampled']:,} from its ratios"
    )


# -- 7 ---------------------------------------------------------------------------------

def check_frozen_manifest_untouched() -> str:
    """Phase 9 did not modify anything the published result depends on."""
    manifest_path = REPO_ROOT / "docs" / "PHASE7_FROZEN_MANIFEST.md"
    if not manifest_path.is_file():
        raise CheckFailure("docs/PHASE7_FROZEN_MANIFEST.md is missing")

    rows = re.findall(
        r"^\|\s*`([^`]+)`\s*\|\s*`([0-9a-f]+)`\s*\|\s*`([0-9a-f]+)`\s*\|",
        manifest_path.read_text(encoding="utf-8"), re.MULTILINE,
    )
    if not rows:
        raise CheckFailure("the manifest lists no artefacts (trivial pass guard)")

    changed = []
    for path, _last_commit, blob in rows:
        if not (REPO_ROOT / path).is_file():
            changed.append(f"{path}: missing from the tree")
            continue
        current = _git("hash-object", path)
        if not current.startswith(blob):
            changed.append(f"{path}: blob {current[:12]}, manifest says {blob}")

    if changed:
        raise CheckFailure(
            "frozen artefacts were modified, so the published result is no longer "
            "reproducible byte-for-byte: " + "; ".join(changed)
        )

    # viz/ is the Phase 3 milestone; the Phase 9 frontend is a copy, not an edit.
    # Anchored to the first phase9 commit rather than to a date, so the check cannot
    # pass vacuously by looking at an empty window.
    if not (REPO_ROOT / "frontend" / "index.html").is_file():
        raise CheckFailure("frontend/index.html is missing")

    phase9_commits = _git("log", "--format=%H", "--grep=^phase9\\.").splitlines()
    if not phase9_commits:
        raise CheckFailure("no phase9 commits found (trivial pass guard)")
    first_phase9 = phase9_commits[-1]
    viz_changes = _git("log", "--oneline", f"{first_phase9}^..HEAD", "--", "viz/")
    if viz_changes:
        raise CheckFailure(f"viz/ was modified during Phase 9:\n{viz_changes}")

    return (
        f"{len(rows)} frozen artefacts match their recorded blob hashes; viz/ untouched "
        "and frontend/ is a separate copy"
    )


# -- 8 ---------------------------------------------------------------------------------

def check_reproduce_and_tests() -> str:
    """`reproduce.py --check` runs clean, and the offline suite passes."""
    completed = subprocess.run(
        [sys.executable, "scripts/reproduce.py", "--check", "--fast"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    if completed.returncode != 0:
        tail = (completed.stdout or completed.stderr).strip().splitlines()[-3:]
        raise CheckFailure("reproduce.py --check failed: " + " | ".join(tail))
    if "PHASE 7 HEADLINE" not in completed.stdout:
        raise CheckFailure("reproduce.py --check did not print the headline table")
    if "B1_latest_cdm" not in completed.stdout:
        raise CheckFailure("the headline table has no baseline row")

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

    return f"reproduce.py --check printed the headline table; pytest: {line}"


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()

    checks: list[tuple[str, Callable[[], str]]] = [
        ("SGP4 reproduces the published reference state", check_sgp4_reference),
        ("Pc reproduces the TraCSS column on >= 10,000 events", check_pc_reproduction),
        ("the covariance frame is required, and matters", check_frame_choice_is_not_cosmetic),
        ("every API endpoint exists and no path returns a bare 500", check_api_surface_and_errors),
        ("MCP tool descriptions state their units and caveats", check_mcp_tools_state_their_units),
        ("censored values are never served unmarked", check_censoring_is_never_silently_averaged),
        ("the Phase 7 frozen manifest is untouched", check_frozen_manifest_untouched),
        ("reproduce.py --check and the offline suite pass", check_reproduce_and_tests),
    ]

    print(f"Phase 9 verification -- {REPO_ROOT}\n")
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
        print(f"{failures} FAILED -- Phase 9 is not complete.")
        return 1
    print("Phase 9 verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
