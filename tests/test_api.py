"""Tests for the HTTP API.

Offline: nothing here reaches the network. ``/triage`` is exercised only along the paths
that reject before any LLM call, so no test can spend money or need a credential.

The endpoints that read the ingested benchmark are skipped when it is absent, rather than
silently passing — the suite must run on a machine without the 620 MB dataset, but it must
not pretend it checked something it did not.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app
from core.store import StoreError, store

client = TestClient(app, raise_server_exceptions=False)


def _benchmark_available() -> bool:
    try:
        store.available()
    except StoreError:
        return False
    return True


needs_benchmark = pytest.mark.skipif(
    not _benchmark_available(), reason="ingested benchmark not present"
)


# A right-angle crossing 400 m apart, with plausible LEO covariances.
PC_BODY = {
    "object1": {
        "position_km": [7000.0, 0.0, 0.0],
        "velocity_kms": [0.0, 7.5, 0.0],
        "covariance": [[0.01, 0.0, 0.0], [0.0, 4.0, 0.0], [0.0, 0.0, 0.02]],
        "hard_body_radius_m": 5.0,
    },
    "object2": {
        "position_km": [7000.0, 0.0, 0.4],
        "velocity_kms": [0.0, 0.0, 7.5],
        "covariance": [[0.02, 0.0, 0.0], [0.0, 9.0, 0.0], [0.0, 0.0, 0.03]],
        "hard_body_radius_m": 3.0,
    },
    "covariance_frame": "uvw",
}


# -- meta ---------------------------------------------------------------------------------


def test_openapi_document_is_generated():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert set(schema["paths"]) == {"/health", "/pc", "/screen", "/events", "/triage"}


def test_health_never_fails_and_reports_each_subsystem():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ok", "degraded"}
    assert set(body["checks"]) == {"tracss_store", "kelvins_store", "sgp4", "llm"}
    # SGP4 needs neither dataset nor credential, so it must be usable everywhere.
    assert body["checks"]["sgp4"]["ok"] is True


def test_health_never_echoes_a_credential_value():
    """The report says whether the key is usable, never what it is."""
    from core.config import LLM_PROVIDERS, settings

    llm = client.get("/health").json()["checks"]["llm"]
    if llm["ok"]:
        secret = settings.llm_api_key()
        assert secret not in str(llm)
    else:
        # The detail names the environment variable; it must not carry a value.
        assert "=" not in llm["detail"]
        assert any(p["env_var"] in llm["detail"] for p in LLM_PROVIDERS.values())


# -- /pc ----------------------------------------------------------------------------------


def test_pc_returns_a_probability_with_full_provenance():
    response = client.post("/pc", json=PC_BODY)
    assert response.status_code == 200
    body = response.json()
    assert 0.0 <= body["pc"] <= 1.0
    assert body["combined_hard_body_radius_m"] == 8.0
    assert body["miss_distance_km"] == pytest.approx(0.4, abs=1e-9)
    assert body["conditioning_2d"]["was_conditioned"] is False
    assert body["conditioning_3d"]["was_conditioned"] is False
    assert "Alfano" in body["provenance"]["method"]
    assert body["provenance"]["units"]["covariance"].startswith("km^2")
    assert any("not a validation" in c for c in body["provenance"]["caveats"])


def test_pc_requires_the_covariance_frame():
    body = {k: v for k, v in PC_BODY.items() if k != "covariance_frame"}
    response = client.post("/pc", json=body)
    assert response.status_code == 422
    assert response.json()["error"] == "invalid_request"


def test_pc_rejects_an_asymmetric_covariance():
    body = {**PC_BODY, "object1": {**PC_BODY["object1"],
            "covariance": [[0.01, 0.5, 0.0], [0.0, 4.0, 0.0], [0.0, 0.0, 0.02]]}}
    response = client.post("/pc", json=body)
    assert response.status_code == 422
    assert "symmetric" in response.json()["detail"]


def test_pc_refuses_a_covariance_that_is_not_one():
    """A grossly negative eigenvalue is a structured refusal, not a number and not a 500."""
    body = {**PC_BODY, "object1": {**PC_BODY["object1"],
            "covariance": [[-4.0, 0.0, 0.0], [0.0, 4.0, 0.0], [0.0, 0.0, 0.02]]}}
    response = client.post("/pc", json=body)
    assert response.status_code == 422
    assert response.json()["error"] == "pc_undefined"
    assert "not repairable" in response.json()["detail"]


def test_pc_answer_changes_with_the_declared_frame():
    """The frame is not cosmetic, so the API must not be allowed to guess it.

    The two objects here are in genuinely different orbital planes, so the in-track-heavy
    covariances rotate very differently and the two readings of the same numbers differ by
    orders of magnitude.
    """
    body = {
        "object1": {
            "position_km": [7000.0, 0.0, 0.0],
            "velocity_kms": [0.0, 7.5, 0.0],
            "covariance": [[1e-4, 0.0, 0.0], [0.0, 4.0, 0.0], [0.0, 0.0, 1e-4]],
            "hard_body_radius_m": 10.0,
        },
        "object2": {
            "position_km": [7000.2, 0.1, 0.3],
            "velocity_kms": [2.0, 3.0, 6.5],
            "covariance": [[1e-4, 0.0, 0.0], [0.0, 4.0, 0.0], [0.0, 0.0, 1e-4]],
            "hard_body_radius_m": 10.0,
        },
        "covariance_frame": "uvw",
    }
    as_uvw = client.post("/pc", json=body).json()["pc"]
    as_eci = client.post("/pc", json={**body, "covariance_frame": "eci"}).json()["pc"]
    assert as_uvw / as_eci > 1e6


def test_pc_rejects_an_unknown_frame():
    response = client.post("/pc", json={**PC_BODY, "covariance_frame": "rtn"})
    assert response.status_code == 422


# -- /screen ------------------------------------------------------------------------------

SCREEN_TLE = {
    "line1": "1 88888U          80275.98708465  .00073094  13844-3  66816-4 0     8",
    "line2": "2 88888  72.8435 115.9689 0086731  52.6988 110.5714 16.05824518   105",
    "name": "vallado-88888",
}


def test_screen_finds_the_degenerate_self_conjunction():
    response = client.post("/screen", json={
        "object1": SCREEN_TLE, "object2": SCREEN_TLE,
        "start_utc": "1980-10-01T23:41:24Z", "stop_utc": "1980-10-02T00:01:24Z",
        "threshold_km": 1.0, "coarse_step_seconds": 60.0, "refine_step_seconds": 5.0,
    })
    assert response.status_code == 200
    body = response.json()
    assert body["count"] >= 1
    assert body["approaches"][0]["miss_distance_km"] == pytest.approx(0.0, abs=1e-9)
    assert body["approaches"][0]["frame"] == "TEME"
    assert any("TEME" in c for c in body["provenance"]["caveats"])


def test_screen_rejects_a_backwards_window():
    response = client.post("/screen", json={
        "object1": SCREEN_TLE, "object2": SCREEN_TLE,
        "start_utc": "1980-10-02T00:00:00Z", "stop_utc": "1980-10-01T00:00:00Z",
    })
    assert response.status_code == 422


def test_screen_refuses_an_absurdly_long_window():
    """TLE accuracy is gone long before 30 days; the API says so instead of serving it."""
    response = client.post("/screen", json={
        "object1": SCREEN_TLE, "object2": SCREEN_TLE,
        "start_utc": "1980-10-01T00:00:00Z", "stop_utc": "1981-10-01T00:00:00Z",
    })
    assert response.status_code == 422
    assert "30" in response.json()["detail"]


def test_screen_rejects_a_malformed_tle():
    response = client.post("/screen", json={
        "object1": {"line1": "1 " + "x" * 60, "line2": "2 " + "y" * 60},
        "object2": SCREEN_TLE,
        "start_utc": "1980-10-01T23:41:24Z", "stop_utc": "1980-10-01T23:51:24Z",
    })
    assert response.status_code == 422
    assert response.json()["error"] in {"propagation_failed", "invalid_request"}


# -- /events ------------------------------------------------------------------------------


@needs_benchmark
def test_events_returns_rows_with_the_censoring_flag():
    response = client.get("/events", params={"source": "sfsh", "limit": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["returned"] == 5
    assert body["total_matching"] > 5
    assert all("pc_is_floored" in event for event in body["events"])
    assert any("censored" in c or "floor" in c for c in body["provenance"]["caveats"])


@needs_benchmark
def test_events_can_exclude_censored_values():
    body = client.get(
        "/events", params={"source": "sfsh", "limit": 20, "exclude_floored": True}
    ).json()
    assert body["returned"] > 0
    assert not any(event["pc_is_floored"] for event in body["events"])


@needs_benchmark
def test_events_pagination_does_not_repeat_rows():
    first = client.get("/events", params={"limit": 5, "offset": 0}).json()["events"]
    second = client.get("/events", params={"limit": 5, "offset": 5}).json()["events"]
    assert {e["event_id"] for e in first}.isdisjoint({e["event_id"] for e in second})


@needs_benchmark
def test_events_rejects_an_unknown_source():
    response = client.get("/events", params={"source": "kelvins"})
    assert response.status_code == 503
    assert response.json()["error"] == "dataset_unavailable"


@needs_benchmark
def test_events_rejects_an_out_of_range_limit():
    assert client.get("/events", params={"limit": 5000}).status_code == 422
    assert client.get("/events", params={"limit": 0}).status_code == 422


@needs_benchmark
def test_events_filter_by_catalog_id_is_not_injectable():
    """The filter is parameterised; a SQL fragment is matched literally, not executed."""
    response = client.get("/events", params={"catalog_id": "1'; drop table sfsh; --"})
    assert response.status_code == 200
    assert response.json()["returned"] == 0
    assert store.count("sfsh") > 0  # the table is still there


# -- /triage ------------------------------------------------------------------------------


def test_triage_rejects_an_oversized_batch_before_spending_anything():
    response = client.post("/triage", json={"series_ids": [f"s{i}" for i in range(40)]})
    assert response.status_code == 422
    assert response.json()["error"] == "invalid_request"


def test_triage_rejects_an_empty_batch():
    assert client.post("/triage", json={"series_ids": []}).status_code == 422


def test_triage_rejects_an_unknown_split():
    response = client.post("/triage", json={"series_ids": ["x"], "split": "validation"})
    assert response.status_code == 422


def test_triage_provenance_leads_with_the_loss():
    """The result the API serves is the one that lost. That has to be in the payload."""
    from api.provenance import SOURCES as PROVENANCE_SOURCES

    caveats = PROVENANCE_SOURCES["triage"]["caveats"]
    assert "THE AGENT LOST." in caveats[0]
    assert "1.6606" in caveats[0] and "0.6940" in caveats[0]
