"""Compare the TraCSS and Kelvins conjunction populations in canonical-schema terms.

Both datasets now normalise into the same record type, so their distributions are
directly comparable — which is exactly what makes it possible to say whether anything
learned on one could transfer to the other.

Censoring is respected throughout: the two sources clamp at **different** floors
(TraCSS Pc 1e-10, Kelvins log10(Pc) -30), so censored records are counted separately
per source and never pooled into a shared statistic.

Writes ``processed/dataset_comparison.json``.

    python scripts/compare_datasets.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import settings  # noqa: E402
from core.schema import KELVINS_PC_FLOOR, PC_FLOOR  # noqa: E402

ACTION_THRESHOLD_PC = 1e-4


def sql(path: Path) -> str:
    return str(path).replace("\\", "/").replace("'", "''")


def connect() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect()
    connection.execute("set TimeZone = 'UTC'")
    connection.execute("set memory_limit = '1GB'")

    processed = settings.PROCESSED_DIR
    for alias, relative in (
        ("tracss_sph", "spherical.parquet"),
        ("tracss_sfsh", "sfsh.parquet"),
        ("kelvins_cdm_train", "kelvins/cdms_train.parquet"),
        ("kelvins_cdm_test", "kelvins/cdms_test.parquet"),
        ("kelvins_series_train", "kelvins/series_train.parquet"),
        ("kelvins_series_test", "kelvins/series_test.parquet"),
    ):
        path = processed / relative
        if not path.is_file():
            raise FileNotFoundError(f"{path}; run the phase 2 and 4 ingestion first")
        connection.execute(
            f"create view {alias} as select * from read_parquet('{sql(path)}')"
        )
    connection.execute(
        "create view tracss as "
        "select pc, pc_is_floored, miss_distance_km, relative_speed_kms, "
        "       mahalanobis_distance, dilution, "
        "       sqrt(greatest(obj1_c_11, obj1_c_22, obj1_c_33)) as sigma_proxy_km, "
        "       'spherical' as split from tracss_sph "
        "union all "
        "select pc, pc_is_floored, miss_distance_km, relative_speed_kms, "
        "       mahalanobis_distance, dilution, "
        "       sqrt(greatest(obj1_c_11, obj1_c_22, obj1_c_33)), "
        "       'sfsh' from tracss_sfsh"
    )
    connection.execute(
        "create view kelvins as "
        "select pc, pc_is_floored, miss_distance_km, relative_speed_kms, "
        "       mahalanobis_distance, "
        "       cast(dilution_derived as double) as dilution, "
        "       target_sigma_max_km as sigma_proxy_km, split from kelvins_cdm_train "
        "union all "
        "select pc, pc_is_floored, miss_distance_km, relative_speed_kms, "
        "       mahalanobis_distance, cast(dilution_derived as double), "
        "       target_sigma_max_km, split from kelvins_cdm_test"
    )
    return connection


def distribution(connection, view: str, column: str, where: str = "true") -> dict[str, Any]:
    row = connection.execute(
        f"""
        select count({column}) n, min({column}) mn,
               quantile_cont({column}, 0.25) q1, median({column}) med,
               quantile_cont({column}, 0.75) q3, max({column}) mx, avg({column}) mean
        from {view} where {where}
        """
    ).fetchone()
    if not row[0]:
        return {"count": 0}
    keys = ("count", "min", "q1", "median", "q3", "max", "mean")
    return {k: (int(v) if k == "count" else float(v)) for k, v in zip(keys, row)}


def pc_block(connection, view: str, floor: float) -> dict[str, Any]:
    row = connection.execute(
        f"""
        select count(*) total,
               count(*) filter (where pc_is_floored) censored,
               count(*) filter (where not pc_is_floored and pc is not null) uncensored,
               count(*) filter (where pc is null) pc_null,
               count(*) filter (where not pc_is_floored and pc >= {ACTION_THRESHOLD_PC}) above
        from {view}
        """
    ).fetchone()
    total, censored, uncensored, pc_null, above = (int(v) for v in row)
    return {
        "records": total,
        "floor": floor,
        "censored": censored,
        "censored_pct": round(100 * censored / max(total, 1), 3),
        "uncensored": uncensored,
        "pc_null": pc_null,
        "above_action_threshold": above,
        "above_action_pct": round(100 * above / max(total, 1), 5),
        "uncensored_stats": distribution(
            connection, view, "pc", "not pc_is_floored and pc is not null"
        ),
    }


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    connection = connect()
    try:
        result: dict[str, Any] = {
            "note": (
                "TraCSS rows are independent snapshots; Kelvins rows are CDMs within "
                "event series. CDM-level distributions are therefore not like-for-like "
                "with TraCSS event-level ones, and are labelled accordingly."
            ),
            "tracss": {
                "unit": "one row = one independent conjunction snapshot",
                "pc": pc_block(connection, "tracss", PC_FLOOR),
                "miss_distance_km": distribution(connection, "tracss", "miss_distance_km"),
                "relative_speed_kms": distribution(connection, "tracss", "relative_speed_kms"),
                "mahalanobis_distance": distribution(connection, "tracss", "mahalanobis_distance"),
                "sigma_proxy_km": distribution(connection, "tracss", "sigma_proxy_km"),
                "dilution_counts": {
                    str(k): int(v)
                    for k, v in connection.execute(
                        "select dilution, count(*) from tracss group by 1 order by 1"
                    ).fetchall()
                },
            },
            "kelvins": {
                "unit": "one row = one CDM within an event series",
                "pc": pc_block(connection, "kelvins", KELVINS_PC_FLOOR),
                "miss_distance_km": distribution(connection, "kelvins", "miss_distance_km"),
                "relative_speed_kms": distribution(connection, "kelvins", "relative_speed_kms"),
                "mahalanobis_distance": distribution(connection, "kelvins", "mahalanobis_distance"),
                "sigma_proxy_km": distribution(connection, "kelvins", "sigma_proxy_km"),
                "dilution_derived_counts": {
                    str(k): int(v)
                    for k, v in connection.execute(
                        "select dilution, count(*) from kelvins group by 1 order by 1"
                    ).fetchall()
                },
            },
        }

        # Event-level view of Kelvins: the label, which is the closest analogue of a
        # TraCSS row's pc.
        series = connection.execute(
            """
            select split, count(*) events,
                   count(*) filter (where final_risk_is_floored) censored,
                   count(*) filter (where final_pc >= 1e-4) above_1e4,
                   count(*) filter (where final_risk_log10 >= -6) above_1e6,
                   median(final_risk_log10) median_log10,
                   max(final_risk_log10) max_log10,
                   median(cdm_count) median_cdms
            from (select * from kelvins_series_train union all select * from kelvins_series_test)
            group by 1 order by 1
            """
        ).fetchdf()
        result["kelvins_event_level"] = {
            row["split"]: {
                "events": int(row["events"]),
                "censored_label": int(row["censored"]),
                "censored_pct": round(100 * row["censored"] / row["events"], 2),
                "above_1e-4": int(row["above_1e4"]),
                "above_1e-4_pct": round(100 * row["above_1e4"] / row["events"], 3),
                "above_1e-6": int(row["above_1e6"]),
                "above_1e-6_pct": round(100 * row["above_1e6"] / row["events"], 3),
                "median_log10_risk": float(row["median_log10"]),
                "max_log10_risk": float(row["max_log10"]),
                "median_cdms_per_event": float(row["median_cdms"]),
            }
            for _, row in series.iterrows()
        }
    finally:
        connection.close()

    destination = settings.PROCESSED_DIR / "dataset_comparison.json"
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")

    for name in ("tracss", "kelvins"):
        block = result[name]
        pc = block["pc"]
        print(f"\n=== {name.upper()} ({block['unit']}) ===")
        print(
            f"  records {pc['records']:,} | censored {pc['censored']:,} "
            f"({pc['censored_pct']}%) at floor {pc['floor']:g} | "
            f"above 1e-4: {pc['above_action_threshold']:,} ({pc['above_action_pct']}%)"
        )
        for key in ("miss_distance_km", "relative_speed_kms", "mahalanobis_distance",
                    "sigma_proxy_km"):
            s = block[key]
            if s.get("count"):
                print(
                    f"  {key:22s} min {s['min']:.4g} q1 {s['q1']:.4g} "
                    f"med {s['median']:.4g} q3 {s['q3']:.4g} max {s['max']:.4g}"
                )
    print("\n=== KELVINS EVENT LEVEL (the label) ===")
    for split, block in result["kelvins_event_level"].items():
        print(
            f"  {split}: {block['events']:,} events | censored label "
            f"{block['censored_label']:,} ({block['censored_pct']}%) | "
            f">=1e-4: {block['above_1e-4']} ({block['above_1e-4_pct']}%) | "
            f">=1e-6: {block['above_1e-6']} ({block['above_1e-6_pct']}%)"
        )
    print(f"\n-> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
