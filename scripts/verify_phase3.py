"""End-to-end verification of Phase 3.

Prints one pass/fail line per check and exits non-zero if any fails. Every check treats a
*vacuous* pass -- zero events, zero files, zero strata -- as a failure.

    python scripts/verify_phase3.py
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from core.schema import PC_FLOOR  # noqa: E402
from verify_phase1 import CheckFailure  # noqa: E402

VIZ = REPO_ROOT / "viz"
EVENTS_PATH = VIZ / "data" / "events.json"
SUMMARY_PATH = VIZ / "data" / "summary.json"

EARTH_RADIUS_KM = 6378.137
ACTION_THRESHOLD = 1e-4
#: Anything above this is reported as an outlier rather than dropped. Well beyond GEO.
IMPLAUSIBLE_ALTITUDE_KM = 50_000

_cache: dict[str, Any] = {}


def events() -> list[dict[str, Any]]:
    if "events" not in _cache:
        if not EVENTS_PATH.is_file():
            raise CheckFailure(f"{EVENTS_PATH} missing; run scripts/export_viz_data.py")
        _cache["events"] = json.loads(EVENTS_PATH.read_text(encoding="utf-8"))
    return _cache["events"]


def summary() -> dict[str, Any]:
    if "summary" not in _cache:
        if not SUMMARY_PATH.is_file():
            raise CheckFailure(f"{SUMMARY_PATH} missing; run scripts/export_viz_data.py")
        _cache["summary"] = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    return _cache["summary"]


# -- 1 ---------------------------------------------------------------------------------

def check_events_parse() -> str:
    """events.json parses and its count equals the viz sample row count."""
    data = events()
    if not isinstance(data, list) or not data:
        raise CheckFailure("events.json is not a non-empty list")

    strata_path = REPO_ROOT / "processed" / "sample_strata.json"
    if not strata_path.is_file():
        raise CheckFailure("processed/sample_strata.json missing; run Phase 2 sampling")
    manifest = json.loads(strata_path.read_text(encoding="utf-8"))

    expected = manifest["selected"]
    excluded = sum((summary()["sample"].get("excluded_unrenderable") or {}).values())
    if len(data) + excluded != expected:
        raise CheckFailure(
            f"events.json has {len(data)} events + {excluded} excluded, "
            f"but the sample holds {expected}"
        )
    if summary()["sample"]["events"] != len(data):
        raise CheckFailure("summary.json disagrees with events.json on the sample size")
    return f"{len(data):,} events, matching the Phase 2 sample ({excluded} excluded)"


# -- 2 ---------------------------------------------------------------------------------

def check_positions_finite() -> str:
    """Every event has both objects with finite positions."""
    bad = []
    for event in events():
        if len(event.get("objects", [])) != 2:
            bad.append(f"{event.get('event_id')}: not exactly 2 objects")
            continue
        for index, obj in enumerate(event["objects"], start=1):
            position = obj.get("position_km")
            if not position or len(position) != 3:
                bad.append(f"{event['event_id']} obj{index}: no position")
            elif not all(isinstance(v, (int, float)) and math.isfinite(v) for v in position):
                bad.append(f"{event['event_id']} obj{index}: non-finite {position}")
    if bad:
        raise CheckFailure(f"{len(bad)} problems, e.g. {bad[:3]}")
    return f"{len(events()):,} events x 2 objects all have finite 3-vector positions"


# -- 3 ---------------------------------------------------------------------------------

def check_altitudes() -> str:
    """Derived altitudes are physically plausible; outliers are reported, not dropped."""
    negative = []
    extreme = []
    mismatched = []
    lowest = math.inf
    highest = -math.inf

    for event in events():
        for index, obj in enumerate(event["objects"], start=1):
            altitude = obj["altitude_km"]
            recomputed = math.dist((0, 0, 0), obj["position_km"]) - EARTH_RADIUS_KM
            if abs(recomputed - altitude) > 0.01:
                mismatched.append(f"{event['event_id']} obj{index}")
            if altitude < 0:
                negative.append(f"{event['event_id']} obj{index}: {altitude:.1f} km")
            if altitude > IMPLAUSIBLE_ALTITUDE_KM:
                extreme.append(f"{event['event_id']} obj{index}: {altitude:.0f} km")
            lowest = min(lowest, altitude)
            highest = max(highest, altitude)

    if mismatched:
        raise CheckFailure(
            f"{len(mismatched)} altitudes disagree with |position| - Re, "
            f"e.g. {mismatched[:3]}"
        )
    if negative:
        raise CheckFailure(f"{len(negative)} negative altitudes, e.g. {negative[:3]}")

    note = ""
    if extreme:
        note = (
            f"; REPORTED (not dropped): {len(extreme)} above "
            f"{IMPLAUSIBLE_ALTITUDE_KM:,} km, e.g. {extreme[:2]}"
        )
    return f"altitudes span {lowest:,.1f} to {highest:,.1f} km, none negative{note}"


# -- 4 ---------------------------------------------------------------------------------

def check_censoring_present() -> str:
    """Censored and uncensored events are both present, with counts."""
    censored = [e for e in events() if e["pc_is_floored"]]
    uncensored = [e for e in events() if not e["pc_is_floored"] and e["pc"] is not None]

    if not censored:
        raise CheckFailure("no censored events in the export")
    if not uncensored:
        raise CheckFailure("no uncensored events in the export")
    for event in censored:
        if event["pc"] is not None and event["pc"] > PC_FLOOR:
            raise CheckFailure(
                f"{event['event_id']} flagged censored but pc={event['pc']} > {PC_FLOOR}"
            )
    return f"{len(censored):,} censored and {len(uncensored):,} uncensored, flags consistent"


# -- 5 ---------------------------------------------------------------------------------

def check_dilution_present() -> str:
    """Both dilution values are present, with counts."""
    robust = sum(1 for e in events() if e["dilution"] == 0)
    diluted = sum(1 for e in events() if e["dilution"] == 1)
    unknown = sum(1 for e in events() if e["dilution"] is None)
    if not robust:
        raise CheckFailure("no robust (dilution = 0) events in the export")
    if not diluted:
        raise CheckFailure("no diluted (dilution = 1) events in the export")
    return f"{robust:,} robust, {diluted:,} diluted, {unknown:,} unknown"


# -- 6 ---------------------------------------------------------------------------------

def check_colour_branches() -> str:
    """Every colour-encoding branch in the UI has at least one event exercising it.

    Mirrors `pcColour` and the ring marker in viz/app.js. A branch with no data would
    mean the legend documents something the viewer can never see.
    """
    branches = {
        "ramp low (pc < 1e-8)": 0,
        "ramp mid (1e-8 <= pc < 1e-6)": 0,
        "ramp high (1e-6 <= pc < 1e-4)": 0,
        "ramp top (pc >= 1e-4)": 0,
        "censored (flat grey, off-ramp)": 0,
        "null pc (flat violet)": 0,
        "dilution ring": 0,
    }
    for event in events():
        pc = event["pc"]
        if pc is None:
            branches["null pc (flat violet)"] += 1
        elif event["pc_is_floored"]:
            branches["censored (flat grey, off-ramp)"] += 1
        elif pc < 1e-8:
            branches["ramp low (pc < 1e-8)"] += 1
        elif pc < 1e-6:
            branches["ramp mid (1e-8 <= pc < 1e-6)"] += 1
        elif pc < ACTION_THRESHOLD:
            branches["ramp high (1e-6 <= pc < 1e-4)"] += 1
        else:
            branches["ramp top (pc >= 1e-4)"] += 1
        if event["dilution"] == 1:
            branches["dilution ring"] += 1

    empty = [name for name, count in branches.items() if count == 0]
    if empty:
        raise CheckFailure(f"colour branches with no events: {empty}")
    return "; ".join(f"{name.split(' (')[0]} {count}" for name, count in branches.items())


# -- 7 ---------------------------------------------------------------------------------

#: A URL only matters if the browser would fetch it. Attribute and import positions are
#: fetches; a bare URL inside a comment (three.js cites a paper) is not.
_FETCHING_PATTERNS = (
    re.compile(r"""\b(?:src|href)\s*=\s*["']?(https?://[^"'\s>]+)""", re.I),
    re.compile(r"""\b(?:import|from)\s*\(?\s*["'](https?://[^"']+)["']""", re.I),
    re.compile(r"""\b(?:fetch|importScripts|XMLHttpRequest)\s*\(\s*["'](https?://[^"']+)""", re.I),
    re.compile(r"""url\(\s*["']?(https?://[^"')]+)""", re.I),
    re.compile(r"""@import\s+["'](https?://[^"']+)""", re.I),
)


def check_no_external_urls() -> str:
    """No file under viz/ references an external URL in a fetching position."""
    if not VIZ.is_dir():
        raise CheckFailure("viz/ does not exist")

    files = [
        p for p in VIZ.rglob("*")
        if p.is_file() and p.suffix.lower() in {".html", ".js", ".css", ".json", ".svg"}
    ]
    if not files:
        raise CheckFailure("no viz files scanned (trivial pass guard)")

    fetching: list[str] = []
    benign: list[str] = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        relative = path.relative_to(REPO_ROOT)
        for pattern in _FETCHING_PATTERNS:
            for match in pattern.finditer(text):
                # The SVG XML namespace is an identifier, never fetched.
                if match.group(1).startswith("http://www.w3.org/"):
                    continue
                fetching.append(f"{relative}: {match.group(1)[:70]}")
        for match in re.finditer(r"https?://[^\s\"'`)<>]+", text):
            url = match.group(0)
            if url.startswith("http://www.w3.org/"):
                continue
            benign.append(f"{relative}: {url[:60]}")

    if fetching:
        raise CheckFailure(f"external fetches found: {fetching[:5]}")

    note = ""
    if benign:
        note = (
            f"; {len(benign)} non-fetching URL mention(s) in comments, e.g. "
            f"{benign[0]}"
        )
    return f"{len(files)} viz files scanned, zero external fetches{note}"


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

def check_population_vs_sample() -> str:
    """summary.json separates population from sample and does not conflate them."""
    data = summary()
    population = data.get("population", {})
    sample = data.get("sample", {})
    if not population.get("events") or not sample.get("events"):
        raise CheckFailure("summary.json is missing population or sample counts")
    if population["events"] <= sample["events"]:
        raise CheckFailure("population is not larger than the sample")
    if data["constants"].get("pc_floor_is_documented") is not False:
        raise CheckFailure(
            "summary.json must record that the pc floor is NOT documented"
        )
    if "warning" not in sample:
        raise CheckFailure("summary.json sample block carries no representativeness warning")

    # The sample must over-represent the action class, or the 3D view shows nothing useful.
    sample_action = sum(1 for e in events() if e["pc"] is not None and e["pc"] >= ACTION_THRESHOLD)
    population_action = population["above_action_threshold"]
    if sample_action == 0:
        raise CheckFailure("no above-threshold events in the sample")
    sample_rate = sample_action / sample["events"]
    population_rate = population_action / population["events"]
    return (
        f"population {population['events']:,} vs sample {sample['events']:,}; "
        f"action events over-sampled {sample_rate / population_rate:.0f}x "
        f"({sample_action} of {sample['events']:,} against {population_action} of "
        f"{population['events']:,})"
    )


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()

    checks: list[tuple[str, Callable[[], str]]] = [
        ("events.json parses and matches the sample count", check_events_parse),
        ("every event has two objects with finite positions", check_positions_finite),
        ("derived altitudes are physically plausible", check_altitudes),
        ("censored and uncensored both present", check_censoring_present),
        ("both dilution values present", check_dilution_present),
        ("every colour branch is exercised", check_colour_branches),
        ("no external URLs under viz/", check_no_external_urls),
        ("pytest passes", check_pytest),
        ("population and sample are kept distinct (addition)", check_population_vs_sample),
    ]

    print(f"Phase 3 verification -- {REPO_ROOT}\n")
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
        print(f"{failures} FAILED -- Phase 3 is not complete.")
        return 1
    print("Phase 3 verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
