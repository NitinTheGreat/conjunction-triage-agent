"""Offline tests for the Phase 2 ingestion, HBR join and profiling helpers.

Runs against ``tests/fixtures/``, never ``dataset/``, and needs no network.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from core.schema import PC_FLOOR, ConjunctionEvent, EventSource  # noqa: E402

try:
    # Not `pytest.importorskip`: that only skips on ModuleNotFoundError, and a machine
    # policy blocking pyarrow's _parquet DLL raises a plain ImportError instead.
    import pyarrow.parquet as pq  # noqa: F401
except ImportError as exc:  # pragma: no cover - environment-dependent
    pytest.skip(f"pyarrow parquet unavailable: {exc}", allow_module_level=True)

import ingest  # noqa: E402
import join_hbr  # noqa: E402
import profile_dataset as profiling  # noqa: E402
import sample_for_viz as sampling  # noqa: E402


# --------------------------------------------------------------------------------------
# flattening events to parquet rows
# --------------------------------------------------------------------------------------

class TestEventToRow:
    def test_covariance_becomes_six_flat_columns(self, sample_event) -> None:
        row = ingest.event_to_row(sample_event, source_line=42)
        cov = sample_event.object1.covariance
        assert row["obj1_c_11"] == cov[0, 0]
        assert row["obj1_c_12"] == cov[0, 1]
        assert row["obj1_c_13"] == cov[0, 2]
        assert row["obj1_c_22"] == cov[1, 1]
        assert row["obj1_c_23"] == cov[1, 2]
        assert row["obj1_c_33"] == cov[2, 2]

    def test_identifiers_stay_strings(self, sample_event) -> None:
        """Guards the float-inference hazard that would render '59208' as '59208.0'."""
        row = ingest.event_to_row(sample_event, source_line=1)
        assert isinstance(row["conj_id"], str) and "." not in row["conj_id"]
        assert isinstance(row["obj1_catalog_id"], str)
        assert "." not in row["obj1_catalog_id"]

    def test_source_line_is_preserved(self, sample_event) -> None:
        assert ingest.event_to_row(sample_event, source_line=12345)["source_line"] == 12345

    def test_row_matches_the_declared_parquet_schema(self, sample_event) -> None:
        import pyarrow as pa

        row = ingest.event_to_row(sample_event, source_line=2)
        table = pa.Table.from_pylist([row], schema=ingest.PARQUET_SCHEMA)
        assert table.num_rows == 1
        assert set(row) == set(ingest.PARQUET_SCHEMA.names)

    def test_round_trips_back_through_the_schema(self, sample_event) -> None:
        import verify_phase2

        row = ingest.event_to_row(sample_event, source_line=2)
        row["tca"] = sample_event.tca
        rebuilt = verify_phase2._event_from_parquet_row(row)
        assert rebuilt.pc == sample_event.pc
        assert rebuilt.tca == sample_event.tca
        assert np.array_equal(
            rebuilt.object1.covariance, sample_event.object1.covariance
        )


# --------------------------------------------------------------------------------------
# dtype policy
# --------------------------------------------------------------------------------------

class TestDtypePolicy:
    def test_identifier_columns_are_integers(self) -> None:
        for column in ingest.ID_COLUMNS:
            assert ingest.DTYPES[column] == "int64", f"{column} must not infer float"

    def test_nullable_metrics_are_floats(self) -> None:
        """prob/dilution/mdistance carry NULLs and must not be read as int."""
        for column in ("prob", "dilution", "mdistance"):
            assert ingest.DTYPES[column] == "float64"

    def test_explicit_dtypes_read_fixture_consistently(self) -> None:
        path = Path(__file__).parent / "fixtures" / "ivv_sfsh_head50.csv"
        frame = pd.read_csv(path, dtype=ingest.DTYPES)
        assert frame["obj1"].dtype == np.int64
        assert frame["conj_id"].dtype == np.int64
        assert str(frame["prob"].dtype) == "float64"
        event = ConjunctionEvent.from_ivv_row(
            frame.iloc[0].to_dict(), EventSource.TRACSS_SFSH
        )
        assert "." not in event.object1.catalog_id


# --------------------------------------------------------------------------------------
# HBR join
# --------------------------------------------------------------------------------------

class TestHbrLoader:
    def _write(self, tmp_path: Path, rows: str) -> Path:
        path = tmp_path / "sv.csv"
        path.write_text("catalog_num,HBR\n" + rows, encoding="utf-8")
        return path

    def test_loads_and_keys_by_string_catalog_id(self, tmp_path) -> None:
        lookup, stats = join_hbr.load_hbr_table(self._write(tmp_path, "5,0.0825\n11,0.254\n"))
        assert lookup == {"5": 0.0825, "11": 0.254}
        assert stats["unique_catalog_num"] == 2
        assert stats["hbr_unit"] == "m"

    def test_collapses_exact_duplicates(self, tmp_path) -> None:
        lookup, stats = join_hbr.load_hbr_table(
            self._write(tmp_path, "5,0.0825\n5,0.0825\n5,0.0825\n")
        )
        assert lookup == {"5": 0.0825}
        assert stats["exact_duplicate_rows_collapsed"] == 2

    def test_raises_on_conflicting_hbr_rather_than_guessing(self, tmp_path) -> None:
        with pytest.raises(ValueError, match="conflicting"):
            join_hbr.load_hbr_table(self._write(tmp_path, "5,0.0825\n5,9.9\n"))

    def test_raises_on_null_hbr(self, tmp_path) -> None:
        with pytest.raises(ValueError, match="nulls"):
            join_hbr.load_hbr_table(self._write(tmp_path, "5,\n"))

    def test_spherical_default_matches_the_users_guide(self) -> None:
        assert join_hbr.SPHERICAL_DEFAULT_HBR_M == 0.5


# --------------------------------------------------------------------------------------
# profiling helpers -- censoring must never be averaged over
# --------------------------------------------------------------------------------------

class TestProfilingHelpers:
    def test_decade_histogram_buckets_by_power_of_ten(self) -> None:
        histogram = profiling.decade_histogram(np.array([2e-9, 3e-9, 5e-8]))
        assert histogram == {"1e-09..1e-08": 2, "1e-08..1e-07": 1}

    def test_decade_histogram_ignores_non_positive_and_nan(self) -> None:
        assert profiling.decade_histogram(np.array([0.0, -1.0, np.nan])) == {}

    def test_quantiles_reports_empty_rather_than_nan(self) -> None:
        assert profiling.quantiles(np.array([np.nan, np.nan]))["count"] == 0

    def test_quantiles_are_correct(self) -> None:
        stats = profiling.quantiles(np.arange(1.0, 101.0))
        assert stats["min"] == 1.0 and stats["max"] == 100.0
        assert stats["median"] == pytest.approx(50.5)

    def test_largest_eigenvalue_is_vectorised_and_correct(self) -> None:
        batch = {
            "obj1_c_11": np.array([4.0]), "obj1_c_12": np.array([0.0]),
            "obj1_c_13": np.array([0.0]), "obj1_c_22": np.array([9.0]),
            "obj1_c_23": np.array([0.0]), "obj1_c_33": np.array([1.0]),
        }
        assert profiling.largest_eigenvalues(batch, 1)[0] == pytest.approx(9.0)


class TestPcClassification:
    def test_floor_is_classified_as_censored_not_low(self) -> None:
        classes = sampling.classify_pc(
            np.array([PC_FLOOR]), np.array([True])
        )
        assert classes[0] == "censored"

    def test_thresholds(self) -> None:
        pc = np.array([1e-3, 1e-4, 1e-5, 1e-7, 1e-9, np.nan])
        floored = np.zeros(pc.shape, dtype=bool)
        classes = sampling.classify_pc(pc, floored)
        assert list(classes) == [
            "action", "action", "near_threshold", "moderate", "low", "null",
        ]

    def test_altitude_bands(self) -> None:
        bands = sampling.band_altitude(np.array([300.0, 600.0, 1500.0, 36000.0]))
        assert list(bands) == ["<500", "500-800", "800-2000", ">=2000"]

    def test_spread_pick_covers_the_miss_distance_range(self) -> None:
        frame = pd.DataFrame(
            {"row_index": np.arange(100), "miss_distance_km": np.arange(100.0)}
        )
        picked = sampling.spread_pick(frame, 10, np.random.default_rng(0))
        assert len(picked) == 10
        assert picked.min() == 0 and picked.max() == 99

    def test_spread_pick_returns_all_when_quota_exceeds_cell(self) -> None:
        frame = pd.DataFrame({"row_index": np.arange(3), "miss_distance_km": [1.0, 2.0, 3.0]})
        assert len(sampling.spread_pick(frame, 10, np.random.default_rng(0))) == 3
