"""Offline tests for the Phase 2 ingestion, HBR join and profiling logic.

Runs against ``tests/fixtures/`` and small in-memory DuckDB tables — never ``dataset/``,
never the network.

Note the profiling and sampling logic moved from Python helpers to SQL expressions during
the Phase 2 DuckDB rewrite. These tests exercise the SQL, which is where the behaviour now
lives.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from core.schema import ConjunctionEvent, EventSource  # noqa: E402

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
    """`load_hbr_table` returns a (DataFrame, stats) pair used for a DuckDB join."""

    def _write(self, tmp_path: Path, rows: str) -> Path:
        path = tmp_path / "sv.csv"
        path.write_text("catalog_num,HBR" + chr(10) + rows, encoding="utf-8")
        return path

    def test_returns_a_frame_keyed_by_string_catalog_id(self, tmp_path) -> None:
        source = self._write(tmp_path, "5,0.0825" + chr(10) + "11,0.254" + chr(10))
        lookup, stats = join_hbr.load_hbr_table(source)
        assert list(lookup.columns) == ["catalog_id", "hbr_m"]
        assert dict(zip(lookup["catalog_id"], lookup["hbr_m"])) == {
            "5": 0.0825, "11": 0.254,
        }
        assert stats["unique_catalog_num"] == 2
        assert stats["hbr_unit"] == "m"

    def test_catalog_id_is_string_so_it_joins_against_the_schema(self, tmp_path) -> None:
        """catalog_id is text in the schema; an integer key would never match."""
        lookup, _ = join_hbr.load_hbr_table(self._write(tmp_path, "5,0.0825" + chr(10)))
        assert all(isinstance(v, str) for v in lookup["catalog_id"])

    def test_collapses_exact_duplicates(self, tmp_path) -> None:
        rows = ("5,0.0825" + chr(10)) * 3
        lookup, stats = join_hbr.load_hbr_table(self._write(tmp_path, rows))
        assert len(lookup) == 1
        assert stats["exact_duplicate_rows_collapsed"] == 2

    def test_raises_on_conflicting_hbr_rather_than_guessing(self, tmp_path) -> None:
        rows = "5,0.0825" + chr(10) + "5,9.9" + chr(10)
        with pytest.raises(ValueError, match="conflicting"):
            join_hbr.load_hbr_table(self._write(tmp_path, rows))

    def test_raises_on_null_hbr(self, tmp_path) -> None:
        with pytest.raises(ValueError, match="nulls"):
            join_hbr.load_hbr_table(self._write(tmp_path, "5," + chr(10)))

    def test_spherical_default_matches_the_users_guide(self) -> None:
        assert join_hbr.SPHERICAL_DEFAULT_HBR_M == 0.5


# --------------------------------------------------------------------------------------
# the SQL expressions -- exercised against a small in-memory table, no dataset needed
# --------------------------------------------------------------------------------------

@pytest.fixture
def tiny_table():
    """A handful of rows covering every classification branch."""
    import duckdb

    connection = duckdb.connect()
    connection.execute("set TimeZone = 'UTC'")
    connection.execute(
        """
        create table t as select * from (values
          (1e-3,  false, 300.0),
          (1e-4,  false, 600.0),
          (1e-5,  false, 900.0),
          (1e-7,  false, 3000.0),
          (1e-9,  false, 40000.0),
          (1e-10, true,  700.0),
          (null,  false, 700.0)
        ) v(pc, pc_is_floored, obj1_alt)
        """
    )
    yield connection
    connection.close()


class TestPcClassificationSql:
    """`PC_CLASS_SQL` is the single definition of the Pc classes; check every branch."""

    def _classify(self, connection) -> list[str]:
        return [
            row[0]
            for row in connection.execute(
                f"select {sampling.PC_CLASS_SQL} from t"
            ).fetchall()
        ]

    def test_every_branch_is_reachable(self, tiny_table) -> None:
        assert self._classify(tiny_table) == [
            "action", "action", "near_threshold", "moderate", "low", "censored", "null",
        ]

    def test_floor_is_censored_not_low(self, tiny_table) -> None:
        """A floored value must never be ranked as a low probability."""
        assert self._classify(tiny_table)[5] == "censored"

    def test_null_is_its_own_class(self, tiny_table) -> None:
        assert self._classify(tiny_table)[6] == "null"

    def test_altitude_bands(self, tiny_table) -> None:
        sql = sampling.ALTITUDE_BAND_SQL.replace(sampling.ALTITUDE_SQL, "obj1_alt")
        bands = [row[0] for row in tiny_table.execute(f"select {sql} from t").fetchall()]
        assert bands[:5] == ["<500", "500-800", "800-2000", ">=2000", ">=2000"]

    def test_dilution_sql_covers_both_states_and_null(self) -> None:
        for token in ("diluted", "robust", "unknown"):
            assert token in sampling.DILUTION_SQL


class TestProfilingConstants:
    def test_action_threshold_is_the_operational_one(self) -> None:
        assert profiling.ACTION_THRESHOLD_PC == 1e-4

    def test_earth_radius_is_consistent_across_modules(self) -> None:
        assert profiling.EARTH_RADIUS_KM == 6378.137
        assert sampling.EARTH_RADIUS_KM == profiling.EARTH_RADIUS_KM

    def test_altitude_sql_is_magnitude_minus_earth_radius(self, tiny_table) -> None:
        tiny_table.execute(
            "create table p as select 7000.0 obj1_x, 0.0 obj1_y, 0.0 obj1_z"
        )
        value = tiny_table.execute(
            f"select {profiling.ALTITUDE_SQL.format(i=1)} from p"
        ).fetchone()[0]
        assert value == pytest.approx(7000.0 - 6378.137)

    def test_trace_sql_sums_the_diagonal(self, tiny_table) -> None:
        tiny_table.execute(
            "create table c as select 1.0 obj1_c_11, 2.0 obj1_c_22, 4.0 obj1_c_33"
        )
        value = tiny_table.execute(
            f"select {profiling.TRACE_SQL.format(i=1)} from c"
        ).fetchone()[0]
        assert value == pytest.approx(7.0)
