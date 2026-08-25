"""Tests for the Kelvins CDM accessor shared by the API and the MCP server.

The point of most of these is the 2-day visibility cutoff. The task is to predict the final
risk at TCA from what is visible at least two days out, so a loader that could be talked
into returning CDMs closer than that would be handing the answer to whatever is predicting.
There is no parameter for it, and this file holds that.

Skipped, not silently passed, when the ingested Kelvins store is absent.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

from core.kelvins_store import (
    SPLITS,
    VISIBILITY_CUTOFF_DAYS,
    KelvinsStoreError,
    cdm_path,
    load_series,
    load_visible_cdms,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _kelvins_available() -> bool:
    try:
        cdm_path("test")
    except KelvinsStoreError:
        return False
    return True


needs_kelvins = pytest.mark.skipif(
    not _kelvins_available(), reason="ingested Kelvins store not present"
)


@pytest.fixture(scope="module")
def sample_series_ids() -> list[str]:
    return load_series("test", limit=6)["series_id"].astype(str).tolist()


def test_unknown_split_raises():
    with pytest.raises(KelvinsStoreError):
        cdm_path("validation")
    assert SPLITS == ("train", "test")


def test_empty_request_returns_nothing_without_touching_the_store():
    assert load_visible_cdms([]) == {}


@needs_kelvins
def test_loads_the_requested_series_and_nothing_else(sample_series_ids):
    loaded = load_visible_cdms(sample_series_ids, "test")
    assert set(loaded).issubset(set(sample_series_ids))
    assert loaded, "no CDMs returned for six real series"


@needs_kelvins
def test_every_returned_cdm_is_at_least_two_days_from_tca(sample_series_ids):
    """The cutoff is the whole reason this function exists. Nothing may cross it."""
    for series_id, frame in load_visible_cdms(sample_series_ids, "test").items():
        assert (frame["time_to_tca_days"] >= VISIBILITY_CUTOFF_DAYS).all(), series_id


@needs_kelvins
def test_cdms_come_back_ordered_from_earliest_to_latest(sample_series_ids):
    for series_id, frame in load_visible_cdms(sample_series_ids, "test").items():
        days = frame["time_to_tca_days"].to_numpy()
        assert (days[:-1] >= days[1:]).all(), series_id


@needs_kelvins
def test_matches_the_query_the_frozen_protocol_ran(sample_series_ids):
    """Phases 6 and 7 loaded CDMs from inside their runner script.

    That script is what produced the published result, so this accessor has to return the
    same rows or the API would be serving the agent different evidence than the evaluation
    gave it. Loaded by path because ``scripts/`` is not an importable package.
    """
    spec = importlib.util.spec_from_file_location(
        "_run_agent_test", REPO_ROOT / "scripts" / "run_agent_test.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    theirs = module.load_visible_cdms(sample_series_ids)
    ours = load_visible_cdms(sample_series_ids, "test")

    assert set(ours) == set(theirs)
    for series_id in ours:
        pd.testing.assert_frame_equal(
            ours[series_id].reset_index(drop=True),
            theirs[series_id].reset_index(drop=True),
        )


@needs_kelvins
def test_unknown_series_are_absent_rather_than_fabricated():
    loaded = load_visible_cdms(["no-such-series-12345"], "test")
    assert loaded == {}
