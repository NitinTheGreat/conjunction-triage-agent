"""Tests for the MCP server's tools and, above all, their descriptions.

A tool description is the entire briefing the calling model gets before it chooses
arguments. If it omits a unit or a frame, the model will guess, and for covariance frames a
wrong guess produces a confident answer that is wrong by orders of magnitude with no error
anywhere. So the descriptions are asserted here as functional requirements rather than
treated as prose.

Offline: the tools are called directly, and ``triage_events`` only along the paths that
return before any LLM call. ``mcp_server/verify_client.py`` covers the protocol itself
against a live client.
"""

from __future__ import annotations

import asyncio

import pytest

from core.store import StoreError, store
from mcp_server.server import (
    compute_pc,
    fetch_conjunctions,
    get_object_metadata,
    server,
    triage_events,
)


def _benchmark_available() -> bool:
    try:
        store.available()
    except StoreError:
        return False
    return True


needs_benchmark = pytest.mark.skipif(
    not _benchmark_available(), reason="ingested benchmark not present"
)


@pytest.fixture(scope="module")
def tools():
    return {tool.name: tool for tool in asyncio.run(server.list_tools())}


VALID_PC_ARGS = dict(
    position1_km=[7000.0, 0.0, 0.0],
    velocity1_kms=[0.0, 7.5, 0.0],
    covariance1=[[0.01, 0, 0], [0, 4.0, 0], [0, 0, 0.02]],
    hbr1_m=5.0,
    position2_km=[7000.0, 0.0, 0.4],
    velocity2_kms=[0.0, 0.0, 7.5],
    covariance2=[[0.02, 0, 0], [0, 9.0, 0], [0, 0, 0.03]],
    hbr2_m=3.0,
    covariance_frame="uvw",
)


# -- the tool surface ---------------------------------------------------------------------


def test_exactly_the_four_tools_are_exposed(tools):
    assert set(tools) == {
        "fetch_conjunctions", "compute_pc", "get_object_metadata", "triage_events"
    }


@pytest.mark.parametrize("name,tokens", [
    ("compute_pc", ["km^2", "METRES", "J2000/ECI", "kilometres per second"]),
    ("fetch_conjunctions", ["km", "km/s", "metres", "1e-10"]),
    ("get_object_metadata", ["metres", "censored"]),
    ("triage_events", ["log10", "-7.0"]),
])
def test_descriptions_state_units_and_frames(tools, name, tokens):
    description = tools[name].description or ""
    missing = [token for token in tokens if token not in description]
    assert not missing, f"{name} description omits {missing}"


def test_compute_pc_requires_the_covariance_frame(tools):
    """No default. A model that can omit it will, and the answer will be silently wrong."""
    schema = tools["compute_pc"].input_schema
    assert "covariance_frame" in schema["required"]
    assert schema["properties"]["covariance_frame"]["enum"] == ["uvw", "eci"]


def test_triage_description_leads_with_the_agent_losing(tools):
    """Anything choosing between the agent and the baseline must see this first."""
    description = tools["triage_events"].description
    assert "The agent LOST." in description
    assert "1.6606" in description and "0.6940" in description
    assert "baseline_risk" in description


def test_server_instructions_warn_about_censoring_and_frames():
    instructions = server.instructions or ""
    assert "1e-10" in instructions
    assert "upper bound" in instructions
    assert "UVW" in instructions


# -- compute_pc ---------------------------------------------------------------------------


def test_compute_pc_returns_a_probability_and_both_conditioning_reports():
    result = compute_pc(**VALID_PC_ARGS)
    assert result["ok"] is True
    assert 0.0 <= result["pc"] <= 1.0
    assert result["miss_distance_km"] == pytest.approx(0.4, abs=1e-9)
    assert result["combined_hard_body_radius_m"] == 8.0
    assert set(result["conditioning"]) == {"combined_3d", "encounter_plane_2d"}
    assert "Alfano" in result["provenance"]["method"]


def test_compute_pc_returns_a_structured_error_rather_than_raising():
    """A raise would surface to the model as a transport failure with no explanation."""
    result = compute_pc(**{**VALID_PC_ARGS,
                           "covariance1": [[-4.0, 0, 0], [0, 4.0, 0], [0, 0, 0.02]]})
    assert result["ok"] is False
    assert "not repairable" in result["error"]
    assert "hint" in result


def test_compute_pc_rejects_a_malformed_covariance():
    result = compute_pc(**{**VALID_PC_ARGS, "covariance1": [[1.0, 0.0], [0.0, 1.0]]})
    assert result["ok"] is False


def test_compute_pc_answer_depends_on_the_declared_frame():
    body = dict(
        position1_km=[7000.0, 0.0, 0.0], velocity1_kms=[0.0, 7.5, 0.0],
        covariance1=[[1e-4, 0, 0], [0, 4.0, 0], [0, 0, 1e-4]], hbr1_m=10.0,
        position2_km=[7000.2, 0.1, 0.3], velocity2_kms=[2.0, 3.0, 6.5],
        covariance2=[[1e-4, 0, 0], [0, 4.0, 0], [0, 0, 1e-4]], hbr2_m=10.0,
    )
    as_uvw = compute_pc(**body, covariance_frame="uvw")["pc"]
    as_eci = compute_pc(**body, covariance_frame="eci")["pc"]
    assert as_uvw / as_eci > 1e6


# -- fetch_conjunctions -------------------------------------------------------------------


@needs_benchmark
def test_fetch_returns_events_with_the_censoring_flag():
    result = fetch_conjunctions(source="sfsh", limit=5)
    assert result["ok"] is True
    assert result["returned"] == 5
    assert all("pc_is_floored" in event for event in result["events"])


@needs_benchmark
def test_fetch_excludes_censored_values_by_default():
    """The default matters: a model that averages floored values gets a meaningless number."""
    result = fetch_conjunctions(source="sfsh", limit=20)
    assert not any(event["pc_is_floored"] for event in result["events"])


@needs_benchmark
def test_fetch_can_include_censored_values_when_asked():
    result = fetch_conjunctions(source="spherical", limit=20, exclude_floored=False)
    assert result["total_matching"] > fetch_conjunctions(
        source="spherical", limit=1, exclude_floored=True
    )["total_matching"]


@needs_benchmark
def test_fetch_result_is_strictly_valid_json():
    """NaN and Infinity are not JSON.

    ``json.dumps`` emits them as bare ``NaN``/``Infinity`` tokens by default, which some
    clients reject outright and others silently coerce. ``allow_nan=False`` is the check
    that they never reach the wire; missing values are converted to null upstream.
    """
    import json

    result = fetch_conjunctions(source="sfsh", limit=50, exclude_floored=False)
    json.dumps(result, allow_nan=False)  # raises ValueError if any NaN survived


def test_fetch_rejects_an_unknown_source():
    result = fetch_conjunctions(source="kelvins", limit=5)
    assert result["ok"] is False


# -- get_object_metadata ------------------------------------------------------------------


@needs_benchmark
def test_object_metadata_separates_censored_from_measured_events():
    catalog = fetch_conjunctions(source="sfsh", limit=1)["events"][0]["object1"]["catalog_id"]
    result = get_object_metadata(catalog_id=catalog, source="sfsh")
    assert result["ok"] is True
    assert result["events"] == result["censored_events"] + result["uncensored_events"]
    assert result["hard_body_radius_m"] > 0
    assert "upper bounds" in result["censoring_note"]


@needs_benchmark
def test_object_metadata_refuses_an_unknown_id_rather_than_inventing_one():
    result = get_object_metadata(catalog_id="000000000", source="sfsh")
    assert result["ok"] is False
    assert "does not appear" in result["error"]


# -- triage_events ------------------------------------------------------------------------


def test_triage_reports_unknown_series_without_calling_the_model():
    """An unknown id must come back as an error, never as a fabricated verdict."""
    result = triage_events(series_ids=["no-such-series-99999"], split="test")
    if result.get("ok"):
        verdict = result["verdicts"][0]
        assert verdict.get("error")
        assert "agent_risk" not in verdict
    else:
        # No credential or no ingested Kelvins store; either is a clean refusal.
        assert result["error"]


def test_triage_provenance_carries_the_loss():
    from api.provenance import SOURCES

    assert "THE AGENT LOST." in SOURCES["triage"]["caveats"][0]
