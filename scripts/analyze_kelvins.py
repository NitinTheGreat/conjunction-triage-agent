"""Structural analysis of the ESA Kelvins Collision Avoidance Challenge dataset.

This is the deciding analysis for Phase 4: it establishes whether Kelvins can support a
triage-ranking benchmark, which TraCSS demonstrably cannot.

Everything is aggregated inside DuckDB straight off the CSVs, so no file is ever loaded
into memory. Writes ``processed/kelvins_structure.json``.

    python scripts/analyze_kelvins.py
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import settings  # noqa: E402

KELVINS_DIR = "kelvins"
TRAIN = "train_data.csv"
TEST = "test_data.csv"
TEST_PRIVATE = "test_data_private.csv"

#: Operational manoeuvre-decision threshold. Kelvins `risk` is log10(Pc), so 1e-4 is -4.
ACTION_THRESHOLD_LOG10 = -4.0


def _peak_memory_mb() -> float:
    import psutil

    info = psutil.Process().memory_info()
    return getattr(info, "peak_wset", info.rss) / 1024**2


def sql_path(name: str) -> str:
    path = settings.DATASET_DIR / KELVINS_DIR / name
    if not path.is_file():
        raise FileNotFoundError(f"{path}; run scripts/fetch_kelvins.py first")
    return str(path).replace("\\", "/").replace("'", "''")


def connect() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect()
    connection.execute("set TimeZone = 'UTC'")
    for alias, filename in (("train", TRAIN), ("test", TEST), ("test_private", TEST_PRIVATE)):
        try:
            location = sql_path(filename)
        except FileNotFoundError:
            continue
        connection.execute(
            f"create view {alias} as select * from read_csv_auto('{location}')"
        )
    return connection


def column_inventory(connection, table: str) -> list[dict[str, Any]]:
    """Name, dtype, null count and range for every column."""
    describe = connection.execute(f"describe select * from {table}").fetchall()
    total = int(connection.execute(f"select count(*) from {table}").fetchone()[0])

    inventory = []
    for name, dtype, *_ in describe:
        quoted = f'"{name}"'
        nulls = int(
            connection.execute(
                f"select count(*) from {table} where {quoted} is null"
            ).fetchone()[0]
        )
        entry: dict[str, Any] = {
            "column": name,
            "dtype": dtype,
            "nulls": nulls,
            "null_pct": round(100 * nulls / max(total, 1), 4),
        }
        if dtype.upper() in {"DOUBLE", "BIGINT", "INTEGER", "FLOAT", "DECIMAL"}:
            row = connection.execute(
                f"select min({quoted}), max({quoted}), count(distinct {quoted}) "
                f"from {table}"
            ).fetchone()
            entry.update(
                {"min": row[0], "max": row[1], "distinct": int(row[2])}
            )
        else:
            values = connection.execute(
                f"select {quoted}, count(*) n from {table} where {quoted} is not null "
                f"group by 1 order by n desc limit 12"
            ).fetchall()
            entry["distinct"] = int(
                connection.execute(
                    f"select count(distinct {quoted}) from {table}"
                ).fetchone()[0]
            )
            entry["top_values"] = {str(v): int(n) for v, n in values}
        inventory.append(entry)
    return inventory


def analyse(connection, table: str) -> dict[str, Any]:
    """Everything section 2 of the phase brief asks for, for one split."""
    rows = int(connection.execute(f"select count(*) from {table}").fetchone()[0])
    events = int(
        connection.execute(f"select count(distinct event_id) from {table}").fetchone()[0]
    )
    columns = len(connection.execute(f"describe select * from {table}").fetchall())

    # -- b. CDMs per event ------------------------------------------------------------
    per_event = connection.execute(
        f"""
        select min(n) mn, max(n) mx, median(n) med, avg(n) mean,
               quantile_cont(n, 0.25) q1, quantile_cont(n, 0.75) q3
        from (select event_id, count(*) n from {table} group by 1)
        """
    ).fetchone()
    histogram = {
        str(int(k)): int(v)
        for k, v in connection.execute(
            f"""
            select n, count(*) from (
              select event_id, count(*) n from {table} group by 1
            ) group by 1 order by 1
            """
        ).fetchall()
    }

    # -- c/d. the label ----------------------------------------------------------------
    risk_stats = connection.execute(
        f"""
        select count(risk) n, min(risk) mn, max(risk) mx, median(risk) med,
               quantile_cont(risk, 0.25) q1, quantile_cont(risk, 0.75) q3,
               count(*) filter (where risk is null) as null_count
        from {table}
        """
    ).fetchone()

    risk_histogram = {
        str(int(k)): int(v)
        for k, v in connection.execute(
            f"select floor(risk)::int d, count(*) from {table} "
            f"where risk is not null group by 1 order by 1"
        ).fetchall()
    }

    # Look for a floor / sentinel: a single value carrying an implausible share of mass.
    risk_modes = {
        str(v): int(n)
        for v, n in connection.execute(
            f"select risk, count(*) n from {table} where risk is not null "
            f"group by 1 order by n desc limit 8"
        ).fetchall()
    }

    # -- final-CDM (per-event) label ---------------------------------------------------
    final_cdm = f"""
        select * from (
          select *, row_number() over (
            partition by event_id order by time_to_tca asc
          ) as rn from {table}
        ) where rn = 1
    """
    final_stats = connection.execute(
        f"""
        select count(*) n,
               min(risk) mn, max(risk) mx, median(risk) med,
               count(*) filter (where risk >= {ACTION_THRESHOLD_LOG10}) high,
               count(*) filter (where risk <= -30) at_minus30,
               min(time_to_tca) min_ttc, max(time_to_tca) max_ttc
        from ({final_cdm})
        """
    ).fetchone()

    final_histogram = {
        str(int(k)): int(v)
        for k, v in connection.execute(
            f"select floor(risk)::int d, count(*) from ({final_cdm}) "
            f"where risk is not null group by 1 order by 1"
        ).fetchall()
    }

    # -- e. time structure -------------------------------------------------------------
    time_stats = connection.execute(
        f"""
        select min(time_to_tca) mn, max(time_to_tca) mx, median(time_to_tca) med
        from {table}
        """
    ).fetchone()

    # -- f. covariance -----------------------------------------------------------------
    covariance = connection.execute(
        f"""
        select
          median(t_sigma_r) t_sig_r, median(t_sigma_t) t_sig_t, median(t_sigma_n) t_sig_n,
          median(c_sigma_r) c_sig_r, median(c_sigma_t) c_sig_t, median(c_sigma_n) c_sig_n,
          median(miss_distance) miss,
          median(max_risk_scaling) scaling,
          count(*) filter (where max_risk_scaling > 1) scaling_gt1,
          count(*) filter (where max_risk_scaling <= 1) scaling_le1,
          count(*) filter (where max_risk_scaling is null) scaling_null
        from {table}
        """
    ).fetchone()

    # -- h. object metadata ------------------------------------------------------------
    object_types = {
        str(v): int(n)
        for v, n in connection.execute(
            f"select c_object_type, count(*) n from {table} group by 1 order by n desc"
        ).fetchall()
    }
    missions = {
        str(v): int(n)
        for v, n in connection.execute(
            f"select mission_id, count(*) n from {table} group by 1 order by n desc"
        ).fetchall()
    }

    return {
        "table": table,
        "rows": rows,
        "events": events,
        "columns": columns,
        "cdms_per_event": {
            "min": int(per_event[0]), "max": int(per_event[1]),
            "median": float(per_event[2]), "mean": round(float(per_event[3]), 3),
            "q1": float(per_event[4]), "q3": float(per_event[5]),
            "histogram": histogram,
        },
        "risk_all_cdms": {
            "n": int(risk_stats[0]), "min": float(risk_stats[1]),
            "max": float(risk_stats[2]), "median": float(risk_stats[3]),
            "q1": float(risk_stats[4]), "q3": float(risk_stats[5]),
            "nulls": int(risk_stats[6]),
            "histogram_by_decade": risk_histogram,
            "most_common_values": risk_modes,
        },
        "final_cdm_label": {
            "events": int(final_stats[0]),
            "min": float(final_stats[1]), "max": float(final_stats[2]),
            "median": float(final_stats[3]),
            "above_action_threshold": int(final_stats[4]),
            "above_action_pct": round(100 * int(final_stats[4]) / max(int(final_stats[0]), 1), 4),
            "at_or_below_minus30": int(final_stats[5]),
            "final_time_to_tca_min_days": float(final_stats[6]),
            "final_time_to_tca_max_days": float(final_stats[7]),
            "histogram_by_decade": final_histogram,
        },
        "time_to_tca_days": {
            "min": float(time_stats[0]), "max": float(time_stats[1]),
            "median": float(time_stats[2]),
        },
        "covariance": {
            "median_target_sigma_rtn_m": [float(covariance[i]) for i in range(3)],
            "median_chaser_sigma_rtn_m": [float(covariance[i]) for i in range(3, 6)],
            "median_miss_distance_m": float(covariance[6]),
            "median_max_risk_scaling": float(covariance[7]),
            "max_risk_scaling_gt_1": int(covariance[8]),
            "max_risk_scaling_le_1": int(covariance[9]),
            "max_risk_scaling_null": int(covariance[10]),
        },
        "c_object_type": object_types,
        "mission_id": missions,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", action="store_true", help="include column inventory")
    args = parser.parse_args()

    started = time.perf_counter()
    connection = connect()
    try:
        results: dict[str, Any] = {}
        for table in ("train", "test"):
            print(f"analysing {table} ...", flush=True)
            results[table] = analyse(connection, table)
            summary = results[table]
            print(
                f"  {summary['rows']:,} rows | {summary['events']:,} events | "
                f"{summary['columns']} columns | "
                f"{summary['final_cdm_label']['above_action_threshold']} events "
                f"above 1e-4",
                flush=True,
            )

        # -- i. train/test disjointness -------------------------------------------------
        overlap = int(
            connection.execute(
                "select count(*) from (select distinct event_id from train) t "
                "join (select distinct event_id from test) s using (event_id)"
            ).fetchone()[0]
        )
        results["train_test_overlap_event_ids"] = overlap

        # test_data_private holds the withheld final risks for the test events
        try:
            private_columns = [
                r[0] for r in connection.execute(
                    "describe select * from test_private"
                ).fetchall()
            ]
            private_rows = int(
                connection.execute("select count(*) from test_private").fetchone()[0]
            )
            results["test_private"] = {
                "rows": private_rows,
                "columns": private_columns[:20],
                "column_count": len(private_columns),
            }
        except duckdb.Error as exc:
            results["test_private"] = {"error": str(exc)}

        if args.inventory:
            results["column_inventory"] = column_inventory(connection, "train")
    finally:
        connection.close()

    results["_meta"] = {
        "action_threshold_log10": ACTION_THRESHOLD_LOG10,
        "elapsed_seconds": round(time.perf_counter() - started, 1),
        "peak_memory_mb": round(_peak_memory_mb(), 1),
    }

    settings.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    destination = settings.PROCESSED_DIR / "kelvins_structure.json"
    destination.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(
        f"\nwrote {destination} in {results['_meta']['elapsed_seconds']}s, "
        f"peak memory {results['_meta']['peak_memory_mb']} MB"
    )
    print(f"train/test event_id overlap: {overlap}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
