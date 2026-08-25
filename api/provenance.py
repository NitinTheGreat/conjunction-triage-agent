"""Provenance stamped on every API response.

Why this exists
---------------
A number returned over HTTP loses everything that made it interpretable: which dataset it
came from, which method computed it, whether the value is a measurement or a censoring
floor, and how well the method was checked. This module puts that back on every response
so a caller cannot mistake one for another.

The agent block in particular carries the Phase 7 result *as it actually came out*. The
agent lost to the latest-CDM baseline by 2.4x. An API that served agent predictions without
saying so would be presenting a worse estimator as a product.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent


@lru_cache(maxsize=1)
def code_version() -> str:
    """The git commit the server is running, or ``"unknown"`` off a checkout.

    Cached: it cannot change while the process is alive, and shelling out per request
    would be absurd.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    revision = result.stdout.strip()
    return revision if result.returncode == 0 and revision else "unknown"


#: Per-topic provenance. Keys are stable; callers may branch on them.
SOURCES: dict[str, dict[str, Any]] = {
    "pc": {
        "method": "Alfano (2004) 2D short-encounter probability of collision",
        "reference": (
            "Alfano, S. (2004), A Numerical Implementation of Spherical Object Collision "
            "Probability, Journal of the Astronautical Sciences 53(1), 103-109"
        ),
        "units": {
            "position": "km, J2000/ECI",
            "velocity": "km/s, J2000/ECI",
            "covariance": "km^2, 3x3 position covariance",
            "hard_body_radius": "m",
        },
        "reproduction": (
            "Reproduces the TraCSS `prob` column to a median log10 ratio of -2.4e-06 "
            "over 10,000 random events per source (100% within 0.1%); see "
            "processed/pc_validation_*.json"
        ),
        "caveats": [
            "This is a reproduction of TraCSS's published method, not a validation of Pc "
            "against reality. No collision outcome exists in this dataset.",
            "Covariances must be supplied in each object's own UVW frame or in ECI, and "
            "the frame must be declared. Summing covariances from different local frames "
            "produces a plausible number that is simply wrong.",
            "A non-positive-definite covariance is repaired by eigenvalue flooring, and "
            "the repair is reported in the `conditioning` block. Check it.",
        ],
    },
    "screen": {
        "method": "SGP4 propagation with a two-pass coarse/fine close-approach search",
        "reference": (
            "Vallado, Crawford, Hujsak & Kelso (2006), AIAA 2006-6753; verified against "
            "the satellite 88888 case to a 5 micrometre position residual"
        ),
        "units": {"position": "km, TEME", "velocity": "km/s, TEME", "time": "UTC"},
        "caveats": [
            "States are TEME, the frame SGP4 natively produces -- not J2000. The "
            "difference cancels in relative geometry but not if mixed with another frame.",
            "TLEs must be supplied by the caller. This server never fetches them; "
            "CelesTrak is unreachable from the host it was built on.",
            "Screening accuracy is bounded by TLE accuracy, which is typically kilometres "
            "and is not modelled here. A close approach found this way is a candidate, "
            "not a conjunction assessment.",
        ],
    },
    "events": {
        "dataset": "TraCSS IV&V Releasable Dataset (spherical and SFSH answer keys)",
        "method": "Read-only query over the Phase 2 ingestion",
        "caveats": [
            "`pc` is censored at 1e-10: a value at the floor is an upper bound, not a "
            "measurement. `pc_is_floored` marks them, and 74.7% of the spherical file "
            "and 14.7% of the SFSH file sit on the floor.",
            "A filtered slice is not the population. Distribution statistics taken from "
            "a query result describe the query, not the benchmark.",
        ],
    },
    "triage": {
        "dataset": "ESA Kelvins Collision Avoidance Challenge (CDM series)",
        "method": (
            "LangGraph agent as a corrector on an alert queue, prompt v1, temperature 0"
        ),
        "metric": "Official Kelvins L = MSE_HR / F2, lower is better",
        "caveats": [
            "THE AGENT LOST. On the held-out test set it scored L = 1.6606 against the "
            "latest-CDM baseline's L = 0.6940 -- 2.4x worse. The paired bootstrap "
            "difference was +0.9462, 95% CI [+0.5119, +1.6152], with the agent better in "
            "0.0% of 10,000 resamples.",
            "The baseline that beat it is one line: predict the most recent CDM's risk. "
            "For a production estimate, use that instead.",
            "Predictions are served here because the pipeline is the deliverable, not "
            "because the agent is the better estimator.",
            "Kelvins events are anonymised and time-shifted; they carry no TCA and no "
            "catalogue identity, so a triage result cannot be joined to a real object.",
        ],
        "published_comparison": {
            "our_B1_latest_cdm": 0.6940,
            "published_LRP": 0.694,
            "our_agent": 1.6606,
            "competition_winner": 0.556,
            "reference": "arXiv:2008.03069 (Uriot et al. 2020), Table 3",
        },
    },
}


def provenance(topic: str, **extra: Any) -> dict[str, Any]:
    """Build the provenance block for one topic.

    Raises on an unknown topic rather than returning an empty block: a response with no
    provenance is exactly the failure this module exists to prevent.
    """
    if topic not in SOURCES:
        raise KeyError(f"no provenance defined for {topic!r}; known: {sorted(SOURCES)}")
    block = dict(SOURCES[topic])
    block["code_version"] = code_version()
    block["computed_at"] = datetime.now(timezone.utc).isoformat()
    block.update(extra)
    return block
