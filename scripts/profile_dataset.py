"""Statistical profile of the full ingested benchmark.

Writes ``processed/profile.json`` and prints a readable summary.

**Censoring is respected everywhere.** ``pc`` is censored at 1e-10: that value is a
bound, not a measurement. Every ``pc`` statistic here is computed over the *uncensored*
population only, and the censored count is always reported alongside it. Mixing the two
would put a large fraction of records at an identical fictitious value and quietly
distort every distribution statistic.

Note the 1e-10 floor is an **inference from the data**, not something the Users Guide
documents. The guide only states that Pc may be NULL when covariance is non-positive-
definite.

``dilution`` is a documented covariance-quality flag (1 = diluted, unreliable Pc;
0 = robust), so pc statistics are additionally broken out by it.

Everything is aggregated inside DuckDB over all 1,196,860 rows -- these are
**population** statistics, not sample statistics.

    python scripts/profile_dataset.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import settings  # noqa: E402
from core.schema import PC_FLOOR  # noqa: E402
from core.store import store  # noqa: E402

#: Equatorial radius, km (WGS-84). Altitude here is |r| - Re, a spherical approximation
#: adequate for bucketing orbital regimes; it is NOT a geodetic altitude.
EARTH_RADIUS_KM = 6378.137

#: Operational manoeuvre-decision threshold widely used by satellite operators.
ACTION_THRESHOLD_PC = 1e-4

#: SQL for the largest eigenvalue of a symmetric 3x3 is impractical; the covariance
#: *trace* is used as the uncertainty magnitude in aggregate statistics instead. It is
#: an upper bound on the largest eigenvalue and within a factor of 3 of it, which is
#: ample for a distribution overview. The exact largest eigenvalue is computed per event
#: in the viz export, where the row count is small.
TRACE_SQL = "(obj{i}_c_11 + obj{i}_c_22 + obj{i}_c_33)"

ALTITUDE_SQL = (
    "sqrt(obj{i}_x*obj{i}_x + obj{i}_y*obj{i}_y + obj{i}_z*obj{i}_z) - "
    f"{EARTH_RADIUS_KM}"
)


def _quantile_sql(column: str, source: str, where: str = "true") -> str:
    return f"""
    select
      count({column})                         as count,
      min({column})                           as min,
      quantile_cont({column}, 0.25)           as q1,
      median({column})                        as median,
      quantile_cont({column}, 0.75)           as q3,
      max({column})                           as max,
      avg({column})                           as mean
    from {source} where {where}
    """


def quantiles(source: str, column: str, where: str = "true") -> dict[str, Any]:
    frame = store.query(_quantile_sql(column, source, where))
    row = frame.iloc[0].to_dict()
    if not row["count"]:
        return {"count": 0, "note": "no finite values"}
    return {k: (int(v) if k == "count" else float(v)) for k, v in row.items()}


def decade_histogram(source: str, column: str, where: str = "true") -> dict[str, int]:
    """Count values per power-of-ten decade, e.g. '1e-09..1e-08'."""
    frame = store.query(
        f"""
        select floor(log10({column}))::int as decade, count(*) as n
        from {source}
        where {where} and {column} is not null and {column} > 0
        group by 1 order by 1
        """
    )
    return {
        f"1e{int(d):+03d}..1e{int(d) + 1:+03d}": int(n)
        for d, n in zip(frame["decade"], frame["n"])
    }


def profile_source(key: str) -> dict[str, Any]:
    """Profile one ingested file, entirely in SQL."""
    total = store.count(key)

    counts = store.query(
        f"""
        select
          count(*) filter (where pc_is_floored and pc is not null)      as censored,
          count(*) filter (where not pc_is_floored and pc is not null)  as uncensored,
          count(*) filter (where pc is null)                            as pc_null
        from {key}
        """
    ).iloc[0]
    censored, uncensored, pc_null = (int(counts[c]) for c in ("censored", "uncensored", "pc_null"))

    live = "not pc_is_floored and pc is not null"
    above = int(
        store.scalar(
            f"select count(*) from {key} where {live} and pc >= {ACTION_THRESHOLD_PC}"
        )
    )

    # pc broken out by the documented covariance-quality flag.
    by_dilution = {}
    for label, predicate in (("robust", "dilution = 0"), ("diluted", "dilution = 1")):
        by_dilution[label] = {
            "events": int(store.scalar(f"select count(*) from {key} where {predicate}")),
            "censored": int(
                store.scalar(
                    f"select count(*) from {key} where {predicate} and pc_is_floored"
                )
            ),
            "uncensored_stats": quantiles(key, "pc", f"{predicate} and {live}"),
            "above_action_threshold": int(
                store.scalar(
                    f"select count(*) from {key} where {predicate} and {live} "
                    f"and pc >= {ACTION_THRESHOLD_PC}"
                )
            ),
        }

    # NULL is counted explicitly rather than via group-by: a NaN group key would
    # stringify to "nan" and sit alongside a separate "NULL" entry, double-counting it.
    dilution_counts = {
        str(row["dilution"]): int(row["n"])
        for _, row in store.query(
            f"select dilution, count(*) as n from {key} "
            "where dilution is not null group by 1 order by 1"
        ).iterrows()
    }
    dilution_counts["NULL"] = int(
        store.scalar(f"select count(*) from {key} where dilution is null")
    )

    altitude_union = " union all ".join(
        f"select {ALTITUDE_SQL.format(i=i)} as altitude_km from {key}" for i in (1, 2)
    )
    altitude_bands = store.query(
        f"""
        select
          count(*) filter (where altitude_km < 200)                              as "<200 km (decaying)",
          count(*) filter (where altitude_km >= 200 and altitude_km < 500)       as "200-500 km",
          count(*) filter (where altitude_km >= 500 and altitude_km < 800)       as "500-800 km",
          count(*) filter (where altitude_km >= 800 and altitude_km < 1200)      as "800-1200 km",
          count(*) filter (where altitude_km >= 1200 and altitude_km < 2000)     as "1200-2000 km",
          count(*) filter (where altitude_km >= 2000 and altitude_km < 35000)    as "2000-35000 km (MEO)",
          count(*) filter (where altitude_km >= 35000)                           as ">=35000 km (GEO+)"
        from ({altitude_union})
        """
    ).iloc[0].to_dict()

    altitude_stats = store.query(
        f"""select count(*) as count, min(altitude_km) as min,
                   quantile_cont(altitude_km, 0.25) as q1, median(altitude_km) as median,
                   quantile_cont(altitude_km, 0.75) as q3, max(altitude_km) as max,
                   avg(altitude_km) as mean
            from ({altitude_union})"""
    ).iloc[0].to_dict()

    trace_union = " union all ".join(
        f"select {TRACE_SQL.format(i=i)} as trace from {key}" for i in (1, 2)
    )
    trace_stats = store.query(
        f"""select count(*) as count, min(trace) as min,
                   quantile_cont(trace, 0.25) as q1, median(trace) as median,
                   quantile_cont(trace, 0.75) as q3, max(trace) as max, avg(trace) as mean
            from ({trace_union})"""
    ).iloc[0].to_dict()
    trace_decades = {
        f"1e{int(d):+03d}..1e{int(d) + 1:+03d}": int(n)
        for d, n in store.query(
            f"select floor(log10(trace))::int as d, count(*) as n "
            f"from ({trace_union}) where trace > 0 group by 1 order by 1"
        ).itertuples(index=False)
    }

    null_counts = {}
    for column in ("pc", "dilution", "mahalanobis_distance", "relative_speed_kms",
                   "jdate", "obj1_hbr_m", "obj2_hbr_m"):
        n = int(store.scalar(f"select count(*) from {key} where {column} is null"))
        if n:
            null_counts[column] = n

    return {
        "source": key,
        "scope": "FULL POPULATION (all ingested rows for this file)",
        "events": total,
        "pc": {
            "censored_at_floor": censored,
            "censored_pct": round(100 * censored / max(total, 1), 3),
            "uncensored": uncensored,
            "uncensored_pct": round(100 * uncensored / max(total, 1), 3),
            "null": pc_null,
            "floor": PC_FLOOR,
            "floor_is_documented": False,
            "floor_note": (
                "The 1e-10 floor is INFERRED from the data. The Users Guide does not "
                "document it; it only states Pc may be NULL when covariance is "
                "non-positive-definite."
            ),
            "uncensored_stats": quantiles(key, "pc", live),
            "uncensored_decades": decade_histogram(key, "pc", live),
            "note": (
                "All pc statistics are over the UNCENSORED population only. Censored "
                "records sit at the floor and are bounds, not values."
            ),
        },
        "pc_by_dilution": by_dilution,
        "operational_threshold": {
            "threshold": ACTION_THRESHOLD_PC,
            "events_above": above,
            "events_above_pct_of_total": round(100 * above / max(total, 1), 6),
        },
        "miss_distance_km": quantiles(key, "miss_distance_km"),
        "relative_speed_kms": quantiles(key, "relative_speed_kms"),
        "mahalanobis_distance": quantiles(key, "mahalanobis_distance"),
        "dilution_values": dilution_counts,
        "altitude_km": {
            "stats": {k: (int(v) if k == "count" else float(v)) for k, v in altitude_stats.items()},
            "bands_object_slots": {k: int(v) for k, v in altitude_bands.items()},
            "note": "spherical |r| - 6378.137 km, both objects pooled; not geodetic",
        },
        "covariance_trace_km2": {
            "stats": {k: (int(v) if k == "count" else float(v)) for k, v in trace_stats.items()},
            "decades": trace_decades,
            "note": "trace = c11+c22+c33, an upper bound on the largest eigenvalue",
        },
        "null_counts": null_counts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=list(store.available()))
    args = parser.parse_args()

    keys = [args.source] if args.source else store.available()
    profiles = {key: profile_source(key) for key in keys}
    profiles["_meta"] = {
        "scope": "FULL POPULATION",
        "total_events": sum(p["events"] for p in profiles.values() if isinstance(p, dict) and "events" in p),
        "pc_floor": PC_FLOOR,
        "pc_floor_is_documented": False,
        "action_threshold": ACTION_THRESHOLD_PC,
        "earth_radius_km": EARTH_RADIUS_KM,
    }

    destination = settings.PROCESSED_DIR / "profile.json"
    destination.write_text(json.dumps(profiles, indent=2), encoding="utf-8")

    for key in keys:
        profile = profiles[key]
        pc = profile["pc"]
        print(f"\n=== {key}: {profile['events']:,} events (FULL POPULATION) ===")
        print(
            f"  pc: {pc['censored_at_floor']:,} censored ({pc['censored_pct']}%), "
            f"{pc['uncensored']:,} uncensored ({pc['uncensored_pct']}%), "
            f"{pc['null']:,} null"
        )
        stats = pc["uncensored_stats"]
        if stats.get("count"):
            print(
                f"  uncensored pc: min {stats['min']:.3e}, median {stats['median']:.3e}, "
                f"max {stats['max']:.3e}"
            )
        threshold = profile["operational_threshold"]
        print(
            f"  pc >= {threshold['threshold']:.0e}: {threshold['events_above']:,} events "
            f"({threshold['events_above_pct_of_total']}%)"
        )
        for name in ("miss_distance_km", "relative_speed_kms", "mahalanobis_distance"):
            s = profile[name]
            if s.get("count"):
                print(
                    f"  {name}: min {s['min']:.4g}, q1 {s['q1']:.4g}, "
                    f"median {s['median']:.4g}, q3 {s['q3']:.4g}, max {s['max']:.4g}"
                )
        print(f"  dilution: {profile['dilution_values']}")
        for label, block in profile["pc_by_dilution"].items():
            print(
                f"    {label}: {block['events']:,} events, "
                f"{block['above_action_threshold']:,} above 1e-4"
            )
        print(f"  altitude bands: {profile['altitude_km']['bands_object_slots']}")

    print(f"\n-> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
