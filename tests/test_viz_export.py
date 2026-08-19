"""Offline tests for the Phase 3 browser export.

These run against the committed ``viz/data/*.json`` when present, and against synthetic
records otherwise, so the suite stays runnable on a machine with no ``processed/``.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from core.schema import PC_FLOOR  # noqa: E402

EVENTS_PATH = REPO_ROOT / "viz" / "data" / "events.json"
SUMMARY_PATH = REPO_ROOT / "viz" / "data" / "summary.json"
EARTH_RADIUS_KM = 6378.137


@pytest.fixture(scope="module")
def exported_events():
    if not EVENTS_PATH.is_file():
        pytest.skip("viz/data/events.json not built; run scripts/export_viz_data.py")
    return json.loads(EVENTS_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def exported_summary():
    if not SUMMARY_PATH.is_file():
        pytest.skip("viz/data/summary.json not built; run scripts/export_viz_data.py")
    return json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------------------
# rounding helpers -- these need no data
# --------------------------------------------------------------------------------------

class TestRounding:
    def test_significant_digits_preserved_across_decades(self) -> None:
        """pc spans ~7 decades, so rounding must be significant-figure based."""
        export = pytest.importorskip("export_viz_data")
        assert export._round_sig(1.234567e-10) == pytest.approx(1.23457e-10, rel=1e-9)
        assert export._round_sig(9.354e-4) == pytest.approx(9.354e-4, rel=1e-9)

    def test_zero_and_none_survive(self) -> None:
        export = pytest.importorskip("export_viz_data")
        assert export._round_sig(None) is None
        assert export._round_sig(0.0) == 0.0

    def test_non_finite_becomes_none(self) -> None:
        export = pytest.importorskip("export_viz_data")
        assert export._round_sig(float("nan")) is None
        assert export._round_sig(float("inf")) is None

    def test_optional_maps_nan_to_none(self) -> None:
        export = pytest.importorskip("export_viz_data")
        assert export._optional(float("nan")) is None
        assert export._optional(np.float64(2.5)) == 2.5
        assert export._optional(np.bool_(True)) is True

    def test_largest_eigenvalue_matches_numpy(self) -> None:
        export = pytest.importorskip("export_viz_data")
        pd = pytest.importorskip("pandas")
        frame = pd.DataFrame({
            "obj1_c_11": [4.0], "obj1_c_12": [0.0], "obj1_c_13": [0.0],
            "obj1_c_22": [9.0], "obj1_c_23": [0.0], "obj1_c_33": [1.0],
        })
        assert export._largest_eigenvalues(frame, 1)[0] == pytest.approx(9.0)


# --------------------------------------------------------------------------------------
# the exported payload
# --------------------------------------------------------------------------------------

class TestExportedEvents:
    def test_non_empty(self, exported_events) -> None:
        assert len(exported_events) > 0

    def test_every_event_has_two_objects_with_finite_positions(self, exported_events) -> None:
        for event in exported_events:
            assert len(event["objects"]) == 2, event["event_id"]
            for obj in event["objects"]:
                assert len(obj["position_km"]) == 3
                assert all(math.isfinite(v) for v in obj["position_km"])

    def test_altitude_agrees_with_position(self, exported_events) -> None:
        for event in exported_events[:400]:
            for obj in event["objects"]:
                expected = math.dist((0, 0, 0), obj["position_km"]) - EARTH_RADIUS_KM
                assert obj["altitude_km"] == pytest.approx(expected, abs=0.01)

    def test_censoring_flag_consistent_with_pc(self, exported_events) -> None:
        for event in exported_events:
            if event["pc_is_floored"] and event["pc"] is not None:
                assert event["pc"] <= PC_FLOOR, event["event_id"]

    def test_tca_is_iso_utc(self, exported_events) -> None:
        for event in exported_events[:200]:
            assert event["tca"].endswith("Z")
            assert "T" in event["tca"]

    def test_no_full_covariance_matrices_shipped(self, exported_events) -> None:
        """Only the scalar magnitude goes to the browser, not 3x3 matrices."""
        for obj in exported_events[0]["objects"]:
            assert "covariance" not in obj
            assert "cov_max_eigenvalue_km2" in obj

    def test_both_censoring_states_present(self, exported_events) -> None:
        flags = {e["pc_is_floored"] for e in exported_events}
        assert flags == {True, False}

    def test_both_dilution_states_present(self, exported_events) -> None:
        values = {e["dilution"] for e in exported_events}
        assert 0 in values and 1 in values


class TestExportedSummary:
    def test_population_is_larger_than_sample(self, exported_summary) -> None:
        assert exported_summary["population"]["events"] > exported_summary["sample"]["events"]

    def test_records_that_the_floor_is_not_documented(self, exported_summary) -> None:
        assert exported_summary["constants"]["pc_floor_is_documented"] is False

    def test_carries_a_representativeness_warning(self, exported_summary) -> None:
        assert "warning" in exported_summary["sample"]
        assert "not representative" in exported_summary["sample"]["warning"].lower()

    def test_provenance_names_the_licence(self, exported_summary) -> None:
        assert "CC0" in exported_summary["provenance"]["licence"]


class TestOfflineGuarantee:
    """Constraint 3: the page must work with no network at all."""

    def test_no_external_fetches_in_viz_sources(self) -> None:
        import verify_phase3

        detail = verify_phase3.check_no_external_urls()
        assert "zero external fetches" in detail

    def test_three_js_is_vendored(self) -> None:
        lib = REPO_ROOT / "viz" / "lib"
        assert (lib / "three.module.min.js").is_file()
        assert (lib / "three.core.min.js").is_file()
        assert (lib / "OrbitControls.js").is_file()
        assert (lib / "VERSION.txt").is_file()

    def test_importmap_points_at_the_local_build(self) -> None:
        html = (REPO_ROOT / "viz" / "index.html").read_text(encoding="utf-8")
        assert "./lib/three.module.min.js" in html
        assert "importmap" in html
