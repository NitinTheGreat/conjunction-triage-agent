"""Shared pytest fixtures.

The suite reads **only** from ``tests/fixtures/``, never from ``dataset/``. That keeps it
fast, offline, and runnable on a machine that does not have the 620 MB benchmark. See
``scripts/build_fixtures.py`` for how the fixtures are produced.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from core.schema import ConjunctionEvent, EventSource

FIXTURES_DIR = Path(__file__).parent / "fixtures"

#: fixture file -> the EventSource it represents
FIXTURE_SOURCES = {
    "ivv_spherical_head50.csv": EventSource.TRACSS_SPHERICAL,
    "ivv_sfsh_head50.csv": EventSource.TRACSS_SFSH,
}


def _load_rows(filename: str) -> list[dict[str, Any]]:
    """Read a fixture CSV into a list of plain dicts."""
    path = FIXTURES_DIR / filename
    if not path.is_file():
        raise FileNotFoundError(
            f"missing fixture {path}; regenerate with scripts/build_fixtures.py"
        )
    frame = pd.read_csv(path)
    if frame.empty:
        raise AssertionError(f"fixture {filename} contains no data rows")
    return frame.to_dict(orient="records")


@pytest.fixture(scope="session")
def sfsh_rows() -> list[dict[str, Any]]:
    """All 50 rows of the SFSH discrete-HBR fixture."""
    return _load_rows("ivv_sfsh_head50.csv")


@pytest.fixture(scope="session")
def spherical_rows() -> list[dict[str, Any]]:
    """All 50 rows of the spherical default-HBR fixture."""
    return _load_rows("ivv_spherical_head50.csv")


@pytest.fixture(scope="session")
def all_rows(
    sfsh_rows: list[dict[str, Any]], spherical_rows: list[dict[str, Any]]
) -> list[tuple[dict[str, Any], EventSource]]:
    """Every fixture row paired with its source, for exhaustive parametrised checks."""
    return [(row, EventSource.TRACSS_SFSH) for row in sfsh_rows] + [
        (row, EventSource.TRACSS_SPHERICAL) for row in spherical_rows
    ]


@pytest.fixture
def sample_row(sfsh_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """One real benchmark row, copied so a test may mutate it freely."""
    return copy.deepcopy(sfsh_rows[0])


@pytest.fixture
def sample_event(sample_row: dict[str, Any]) -> ConjunctionEvent:
    """A valid :class:`ConjunctionEvent` built from a real benchmark row."""
    return ConjunctionEvent.from_ivv_row(sample_row, EventSource.TRACSS_SFSH)
