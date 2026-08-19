"""Tests for the Kelvins additions to the canonical schema.

All synthetic — no dataset, no network.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from core.schema import (
    KELVINS_PC_FLOOR,
    PC_FLOOR,
    SOURCE_PC_FLOOR,
    ConjunctionEvent,
    ConjunctionEventSeries,
    EventSource,
    SchemaValidationError,
    conjunction_event_from_kelvins_row,
)


def kelvins_row(**overrides):
    """A minimal but complete Kelvins CDM row."""
    row = {
        "event_id": 0,
        "time_to_tca": 3.5,
        "mission_id": 5,
        "risk": -7.0,
        "miss_distance": 14923.0,       # metres
        "relative_speed": 13792.0,      # m/s
        "mahalanobis_distance": 2.5,
        "c_object_type": "DEBRIS",
        "t_span": 5.0,
        "c_span": 2.0,
    }
    for prefix in ("t", "c"):
        row[f"{prefix}_sigma_r"] = 10.0
        row[f"{prefix}_sigma_t"] = 100.0
        row[f"{prefix}_sigma_n"] = 5.0
        row[f"{prefix}_ct_r"] = 0.1
        row[f"{prefix}_cn_r"] = 0.0
        row[f"{prefix}_cn_t"] = -0.2
    row.update(overrides)
    return row


# --------------------------------------------------------------------------------------
# per-source floors
# --------------------------------------------------------------------------------------

class TestPerSourceFloor:
    def test_the_two_datasets_have_different_floors(self) -> None:
        assert PC_FLOOR == 1e-10
        assert KELVINS_PC_FLOOR == 1e-30
        assert SOURCE_PC_FLOOR[EventSource.TRACSS_SFSH] == PC_FLOOR
        assert SOURCE_PC_FLOOR[EventSource.KELVINS] == KELVINS_PC_FLOOR

    def test_live_sources_have_no_floor(self) -> None:
        assert SOURCE_PC_FLOOR[EventSource.CELESTRAK] is None
        assert SOURCE_PC_FLOOR[EventSource.SPACETRACK] is None

    def test_no_floor_means_nothing_is_censored(self) -> None:
        assert ConjunctionEvent.compute_pc_is_floored(1e-40, None) is False

    def test_a_value_below_the_tracss_floor_is_not_floored_for_kelvins(self) -> None:
        """The exact hazard the per-source floor exists to prevent."""
        pc = 1e-12
        assert ConjunctionEvent.compute_pc_is_floored(pc, PC_FLOOR) is True
        assert ConjunctionEvent.compute_pc_is_floored(pc, KELVINS_PC_FLOOR) is False

    def test_event_resolves_its_floor_from_its_source(self) -> None:
        event = conjunction_event_from_kelvins_row(kelvins_row(), "p", "train:0")
        assert event.pc_floor == KELVINS_PC_FLOOR


# --------------------------------------------------------------------------------------
# the Kelvins CDM constructor
# --------------------------------------------------------------------------------------

class TestKelvinsRow:
    def test_risk_is_log10_and_becomes_a_linear_pc(self) -> None:
        event = conjunction_event_from_kelvins_row(kelvins_row(risk=-7.0), "p", "train:0")
        assert event.pc == pytest.approx(1e-7)

    def test_floor_is_detected_at_minus_thirty(self) -> None:
        event = conjunction_event_from_kelvins_row(kelvins_row(risk=-30.0), "p", "train:0")
        assert event.pc == pytest.approx(1e-30)
        assert event.pc_is_floored is True

    def test_units_are_converted_to_the_schema(self) -> None:
        event = conjunction_event_from_kelvins_row(kelvins_row(), "p", "train:0")
        assert event.miss_distance_km == pytest.approx(14.923)
        assert event.relative_speed_kms == pytest.approx(13.792)

    def test_no_absolute_epoch_but_a_relative_one(self) -> None:
        event = conjunction_event_from_kelvins_row(kelvins_row(), "p", "train:0")
        assert event.tca is None
        assert event.time_to_tca_days == pytest.approx(3.5)
        event.validate()

    def test_positions_are_absent_because_kelvins_is_anonymised(self) -> None:
        event = conjunction_event_from_kelvins_row(kelvins_row(), "p", "train:0")
        assert event.object1.position_km is None
        assert event.object2.velocity_kms is None

    def test_covariance_is_symmetric_and_in_km2(self) -> None:
        event = conjunction_event_from_kelvins_row(kelvins_row(), "p", "train:0")
        cov = event.object1.covariance
        assert cov.shape == (3, 3)
        assert np.array_equal(cov, cov.T)
        # sigma_r = 10 m -> 1e-4 km^2
        assert cov[0, 0] == pytest.approx((10.0 / 1000.0) ** 2)
        assert cov[1, 1] == pytest.approx((100.0 / 1000.0) ** 2)

    def test_covariance_off_diagonal_uses_the_correlation(self) -> None:
        event = conjunction_event_from_kelvins_row(kelvins_row(), "p", "train:0")
        cov = event.object1.covariance
        expected = 0.1 * (10.0 / 1000.0) * (100.0 / 1000.0)
        assert cov[0, 1] == pytest.approx(expected)

    def test_missing_covariance_leaves_none_rather_than_zero(self) -> None:
        event = conjunction_event_from_kelvins_row(
            kelvins_row(c_sigma_r=None), "p", "train:0"
        )
        assert event.object2.covariance is None
        event.validate()

    def test_object_type_is_carried_into_the_catalog_id(self) -> None:
        event = conjunction_event_from_kelvins_row(kelvins_row(), "p", "train:0")
        assert "DEBRIS" in event.object2.catalog_id

    def test_missing_risk_raises_rather_than_defaulting(self) -> None:
        row = kelvins_row()
        del row["risk"]
        with pytest.raises(SchemaValidationError, match="risk"):
            conjunction_event_from_kelvins_row(row, "p", "train:0")

    def test_round_trips(self) -> None:
        event = conjunction_event_from_kelvins_row(kelvins_row(), "p", "train:0")
        assert ConjunctionEvent.from_dict(event.to_dict()) == event


# --------------------------------------------------------------------------------------
# the series container
# --------------------------------------------------------------------------------------

def series(times=(5.0, 3.0, 1.0), **overrides):
    events = [
        conjunction_event_from_kelvins_row(kelvins_row(time_to_tca=t), "p", "train:0")
        for t in times
    ]
    kwargs = {
        "series_id": "train:0",
        "source": EventSource.KELVINS,
        "provenance": "train_data.csv",
        "split": "train",
        "events": events,
        "final_risk_log10": -7.0,
    }
    kwargs.update(overrides)
    return ConjunctionEventSeries(**kwargs)


class TestSeries:
    def test_valid_series(self) -> None:
        s = series()
        s.validate()
        assert s.cdm_count == 3

    def test_final_event_is_closest_to_tca(self) -> None:
        s = series()
        assert s.final_event.time_to_tca_days == 1.0

    def test_final_pc_is_derived_from_the_label(self) -> None:
        assert series(final_risk_log10=-6.0).final_pc == pytest.approx(1e-6)
        assert series(final_risk_log10=None).final_pc is None

    def test_rejects_an_empty_series(self) -> None:
        with pytest.raises(SchemaValidationError, match="no CDMs"):
            series(events=[]).validate()

    def test_rejects_out_of_order_cdms(self) -> None:
        """An unordered series would silently corrupt any trend computed over it."""
        with pytest.raises(SchemaValidationError, match="not ordered"):
            series(times=(1.0, 3.0, 5.0)).validate()

    def test_rejects_a_mixed_source_series(self) -> None:
        s = series()
        s.events[1].source = EventSource.TRACSS_SFSH
        with pytest.raises(SchemaValidationError, match="source"):
            s.validate()

    def test_rejects_a_cdm_with_no_relative_time(self) -> None:
        s = series()
        s.events[1].time_to_tca_days = None
        with pytest.raises(SchemaValidationError):
            s.validate()

    def test_rejects_non_finite_label(self) -> None:
        with pytest.raises(SchemaValidationError, match="final_risk_log10"):
            series(final_risk_log10=math.inf).validate()

    def test_round_trips_exactly(self) -> None:
        s = series()
        assert ConjunctionEventSeries.from_dict(s.to_dict()) == s

    def test_series_id_is_split_qualified(self) -> None:
        """Kelvins event_id restarts at 0 per split; a raw id would merge train and test."""
        assert series().series_id.startswith("train:")
