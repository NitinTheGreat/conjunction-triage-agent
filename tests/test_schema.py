"""Tests for the canonical :mod:`core.schema` record type.

Everything here runs against committed fixtures, offline.
"""

from __future__ import annotations

import copy
import dataclasses
import math
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
import pytest

from core.schema import (
    PC_FLOOR,
    ConjunctionEvent,
    EventSource,
    ObjectState,
    SchemaValidationError,
)


# --------------------------------------------------------------------------------------
# construction from real benchmark rows
# --------------------------------------------------------------------------------------

class TestFromIvvRow:
    def test_builds_from_every_fixture_row(self, all_rows) -> None:
        """All 100 fixture rows parse and validate. Guards against a trivial pass."""
        assert len(all_rows) == 100, "fixtures should supply 50 rows per file"
        for row, source in all_rows:
            event = ConjunctionEvent.from_ivv_row(row, source)
            event.validate()

    def test_maps_identity_and_encounter_fields(self, sample_row) -> None:
        event = ConjunctionEvent.from_ivv_row(sample_row, EventSource.TRACSS_SFSH)

        assert event.run_id == int(sample_row["run_id"])
        assert event.conj_id == str(sample_row["conj_id"])
        assert event.source is EventSource.TRACSS_SFSH
        assert event.event_id == f"TRACSS_SFSH:{event.run_id}:{event.conj_id}"
        assert event.miss_distance_km == pytest.approx(sample_row["min_range"])
        assert event.relative_speed_kms == pytest.approx(sample_row["Vrel"])
        assert event.mahalanobis_distance == pytest.approx(sample_row["mdistance"])
        assert event.object1.catalog_id == str(sample_row["obj1"])
        assert event.object2.catalog_id == str(sample_row["obj2"])

    def test_provenance_defaults_to_source_file_and_is_overridable(
        self, sample_row
    ) -> None:
        default = ConjunctionEvent.from_ivv_row(sample_row, EventSource.TRACSS_SFSH)
        assert default.provenance == "IVV_Releasable_Dataset_SFSH_DiscreteHBR.csv"

        explicit = ConjunctionEvent.from_ivv_row(
            sample_row, EventSource.TRACSS_SFSH, provenance="tests/fixtures/x.csv#0"
        )
        assert explicit.provenance == "tests/fixtures/x.csv#0"

    def test_tca_is_timezone_aware_utc(self, sample_event) -> None:
        assert sample_event.tca.tzinfo is not None
        assert sample_event.tca.utcoffset() == timedelta(0)

    def test_missing_column_raises_naming_the_column(self, sample_row) -> None:
        """Fail loud: a missing column must raise, not default."""
        del sample_row["min_range"]
        with pytest.raises(SchemaValidationError, match="min_range"):
            ConjunctionEvent.from_ivv_row(sample_row, EventSource.TRACSS_SFSH)

    def test_unparseable_value_raises(self, sample_row) -> None:
        sample_row["min_range"] = "not-a-number"
        with pytest.raises(SchemaValidationError, match="min_range"):
            ConjunctionEvent.from_ivv_row(sample_row, EventSource.TRACSS_SFSH)

    def test_unparseable_epoch_raises(self, sample_row) -> None:
        sample_row["epoch"] = "the day before yesterday"
        with pytest.raises(SchemaValidationError, match="epoch"):
            ConjunctionEvent.from_ivv_row(sample_row, EventSource.TRACSS_SFSH)


# --------------------------------------------------------------------------------------
# covariance reconstruction
# --------------------------------------------------------------------------------------

class TestCovariance:
    def test_reconstructs_symmetric_3x3(self, sample_event) -> None:
        for state in (sample_event.object1, sample_event.object2):
            cov = state.covariance
            assert isinstance(cov, np.ndarray)
            assert cov.shape == (3, 3)
            assert cov.dtype == np.float64
            assert np.array_equal(cov, cov.T), "covariance must be exactly symmetric"

    def test_mirrors_the_upper_triangle_into_the_expected_layout(
        self, sample_row
    ) -> None:
        """The six c1_* values must land in the documented positions."""
        state = ObjectState.from_ivv_row(sample_row, 1)
        cov = state.covariance
        expected = {
            (0, 0): "c1_11", (0, 1): "c1_12", (0, 2): "c1_13",
            (1, 1): "c1_22", (1, 2): "c1_23", (2, 2): "c1_33",
        }
        for (i, j), column in expected.items():
            assert cov[i, j] == pytest.approx(float(sample_row[column]))
            assert cov[j, i] == pytest.approx(float(sample_row[column]))

    def test_every_fixture_covariance_is_symmetric_and_psd(self, all_rows) -> None:
        checked = 0
        for row, source in all_rows:
            event = ConjunctionEvent.from_ivv_row(row, source)
            for state in (event.object1, event.object2):
                cov = state.covariance
                assert np.array_equal(cov, cov.T)
                assert np.min(np.linalg.eigvalsh(cov)) >= -1e-10
                checked += 1
        assert checked == 200, "expected two covariances per event"


# --------------------------------------------------------------------------------------
# pc censoring
# --------------------------------------------------------------------------------------

class TestPcCensoring:
    def test_flag_set_at_exactly_the_floor(self, sample_row) -> None:
        sample_row["prob"] = 1e-10
        event = ConjunctionEvent.from_ivv_row(sample_row, EventSource.TRACSS_SFSH)
        assert event.pc == PC_FLOOR
        assert event.pc_is_floored is True

    def test_benchmark_literal_parses_to_exactly_the_floor(self) -> None:
        """The CSV writes the floor as `0.0000000001`; that must be exactly 1e-10."""
        assert float("0.0000000001") == PC_FLOOR

    def test_flag_clear_above_the_floor(self, sample_row) -> None:
        sample_row["prob"] = 1.5e-10
        event = ConjunctionEvent.from_ivv_row(sample_row, EventSource.TRACSS_SFSH)
        assert event.pc_is_floored is False

    def test_flag_set_below_the_floor(self, sample_row) -> None:
        """Nothing below the floor can be a real measurement, so it is censored too."""
        sample_row["prob"] = 1e-12
        event = ConjunctionEvent.from_ivv_row(sample_row, EventSource.TRACSS_SFSH)
        assert event.pc_is_floored is True

    def test_absent_pc_is_none_and_not_floored(self, sample_row) -> None:
        sample_row["prob"] = float("nan")
        event = ConjunctionEvent.from_ivv_row(sample_row, EventSource.TRACSS_SFSH)
        assert event.pc is None
        assert event.pc_is_floored is False

    def test_fixtures_contain_both_censored_and_uncensored_records(
        self, all_rows
    ) -> None:
        """Guards against the censoring tests passing vacuously."""
        flags = [
            ConjunctionEvent.from_ivv_row(row, source).pc_is_floored
            for row, source in all_rows
        ]
        assert any(flags), "no censored records in fixtures"
        assert not all(flags), "no uncensored records in fixtures"


# --------------------------------------------------------------------------------------
# serialisation round-trip
# --------------------------------------------------------------------------------------

class TestRoundTrip:
    def test_round_trip_is_exact(self, sample_event) -> None:
        restored = ConjunctionEvent.from_dict(sample_event.to_dict())
        assert restored == sample_event
        assert restored.to_dict() == sample_event.to_dict()

    def test_round_trip_preserves_every_field(self, sample_event) -> None:
        restored = ConjunctionEvent.from_dict(sample_event.to_dict())
        for f in dataclasses.fields(ConjunctionEvent):
            original, copied = getattr(sample_event, f.name), getattr(restored, f.name)
            if isinstance(original, ObjectState):
                assert copied == original, f"{f.name} differs"
            else:
                assert copied == original, f"{f.name} differs"

    def test_round_trip_preserves_covariance_bit_for_bit(self, sample_event) -> None:
        restored = ConjunctionEvent.from_dict(sample_event.to_dict())
        for a, b in (
            (sample_event.object1, restored.object1),
            (sample_event.object2, restored.object2),
        ):
            assert np.array_equal(a.covariance, b.covariance)
            assert b.covariance.dtype == np.float64

    def test_round_trip_preserves_timezone_and_microseconds(self, sample_event) -> None:
        restored = ConjunctionEvent.from_dict(sample_event.to_dict())
        assert restored.tca == sample_event.tca
        assert restored.tca.tzinfo is not None
        assert restored.tca.utcoffset() == sample_event.tca.utcoffset()
        assert restored.tca.microsecond == sample_event.tca.microsecond

    def test_round_trip_holds_for_every_fixture_row(self, all_rows) -> None:
        for row, source in all_rows:
            event = ConjunctionEvent.from_ivv_row(row, source)
            assert ConjunctionEvent.from_dict(event.to_dict()) == event

    def test_to_dict_is_plain_python(self, sample_event) -> None:
        """No numpy scalars or arrays leak out, so the dict is JSON-serialisable."""
        import json

        payload = sample_event.to_dict()
        json.dumps(payload)  # raises if a numpy type leaked through
        assert isinstance(payload["object1"]["covariance"], list)
        assert all(isinstance(v, float) for r in payload["object1"]["covariance"] for v in r)


# --------------------------------------------------------------------------------------
# validate() -- one test per failure mode
# --------------------------------------------------------------------------------------

class TestValidate:
    def test_accepts_a_real_record(self, sample_event) -> None:
        sample_event.validate()

    def test_rejects_naive_tca(self, sample_event) -> None:
        sample_event.tca = sample_event.tca.replace(tzinfo=None)
        with pytest.raises(SchemaValidationError, match="timezone-aware"):
            sample_event.validate()

    def test_rejects_negative_miss_distance(self, sample_event) -> None:
        sample_event.miss_distance_km = -1.0
        with pytest.raises(SchemaValidationError, match="miss_distance_km"):
            sample_event.validate()

    @pytest.mark.parametrize("bad_pc", [-0.1, 1.5])
    def test_rejects_pc_outside_unit_interval(self, sample_event, bad_pc) -> None:
        sample_event.pc = bad_pc
        sample_event.pc_is_floored = ConjunctionEvent.compute_pc_is_floored(bad_pc)
        with pytest.raises(SchemaValidationError, match=r"pc must lie in"):
            sample_event.validate()

    def test_rejects_non_finite_pc(self, sample_event) -> None:
        sample_event.pc = math.inf
        with pytest.raises(SchemaValidationError, match="pc is not finite"):
            sample_event.validate()

    def test_rejects_floored_flag_contradicting_pc(self, sample_event) -> None:
        sample_event.pc = 1e-3
        sample_event.pc_is_floored = True
        with pytest.raises(SchemaValidationError, match="contradicts"):
            sample_event.validate()

    @pytest.mark.parametrize("bad", [math.inf, math.nan, -math.inf])
    def test_rejects_non_finite_position(self, sample_event, bad) -> None:
        x, y, z = sample_event.object1.position_km
        sample_event.object1.position_km = (bad, y, z)
        with pytest.raises(SchemaValidationError, match="position_km is not finite"):
            sample_event.validate()

    @pytest.mark.parametrize("bad", [math.inf, math.nan])
    def test_rejects_non_finite_velocity(self, sample_event, bad) -> None:
        vx, vy, vz = sample_event.object2.velocity_kms
        sample_event.object2.velocity_kms = (vx, bad, vz)
        with pytest.raises(SchemaValidationError, match="velocity_kms is not finite"):
            sample_event.validate()

    def test_rejects_non_symmetric_covariance(self, sample_event) -> None:
        cov = sample_event.object1.covariance.copy()
        cov[0, 1] = cov[1, 0] + 5.0
        sample_event.object1.covariance = cov
        with pytest.raises(SchemaValidationError, match="not symmetric"):
            sample_event.validate()

    def test_rejects_non_positive_semidefinite_covariance(self, sample_event) -> None:
        """Symmetric but indefinite: a negative eigenvalue is physically impossible."""
        cov = np.array(
            [[1.0, 2.0, 0.0], [2.0, 1.0, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64
        )
        assert np.array_equal(cov, cov.T), "the test matrix must be symmetric"
        assert np.min(np.linalg.eigvalsh(cov)) < 0, "the test matrix must be indefinite"
        sample_event.object1.covariance = cov
        with pytest.raises(SchemaValidationError, match="positive-semidefinite"):
            sample_event.validate()

    def test_rejects_wrong_shaped_covariance(self, sample_event) -> None:
        sample_event.object2.covariance = np.eye(2, dtype=np.float64)
        with pytest.raises(SchemaValidationError, match="must be 3x3"):
            sample_event.validate()

    def test_rejects_empty_catalog_id(self, sample_event) -> None:
        sample_event.object1.catalog_id = ""
        with pytest.raises(SchemaValidationError, match="catalog_id"):
            sample_event.validate()

    def test_reports_which_object_failed(self, sample_event) -> None:
        sample_event.object2.catalog_id = ""
        with pytest.raises(SchemaValidationError, match="object2"):
            sample_event.validate()


# --------------------------------------------------------------------------------------
# sparse records from live sources
# --------------------------------------------------------------------------------------

class TestSparseRecords:
    def test_celestrak_shaped_record_without_state_vectors_is_valid(self) -> None:
        """A live source supplies no state vector or covariance; that must still pass."""
        event = ConjunctionEvent(
            event_id="CELESTRAK:0:abc",
            run_id=0,
            conj_id="abc",
            source=EventSource.CELESTRAK,
            provenance="https://celestrak.org/SOCRATES/",
            tca=datetime(2026, 1, 1, tzinfo=timezone.utc),
            jdate=None,
            miss_distance_km=1.234,
            relative_speed_kms=14.2,
            mahalanobis_distance=None,
            dilution=None,
            pc=None,
            pc_is_floored=False,
            object1=ObjectState(catalog_id="25544"),
            object2=ObjectState(catalog_id="00900"),
        )
        event.validate()
        assert event.object1.covariance is None
        assert ConjunctionEvent.from_dict(event.to_dict()) == event
