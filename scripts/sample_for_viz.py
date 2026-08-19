"""Build a stratified ~2,000-event sample for the Phase 3 visualisation.

Phase 3 cannot render 1.2 M events. This selects a sample that spans the *interesting*
range rather than the typical one, so the visualisation exercises the extremes.

Selection rule (fully deterministic given ``--seed``)
----------------------------------------------------
1. Every ingested event is assigned a **pc class** -- the primary stratum, because
   collision probability is what triage is about, and because censoring makes a naive
   random sample mostly floor values:

   ``action`` (pc >= 1e-4), ``near_threshold`` (1e-6 <= pc < 1e-4),
   ``moderate`` (1e-8 <= pc < 1e-6), ``low`` (floor < pc < 1e-8),
   ``censored`` (pc <= 1e-10, a bound not a value), ``null`` (pc not computable).

2. Crossed with **dilution** -- a documented covariance-quality flag (1 = diluted,
   unreliable Pc; 0 = robust). Sampling across it keeps both trustworthy and
   untrustworthy records visible, which matters because 304 of the 305 events above the
   action threshold are diluted.

3. And an **altitude band** from the primary object, so the sample spans orbital
   regimes: ``<500``, ``500-800``, ``800-2000``, ``>=2000`` km.

4. Rare cells -- above all ``action`` -- are taken in full first, so the high-risk tail
   is never diluted away by the floor population. Remaining capacity is spread evenly
   over the larger cells.

5. Within a cell, rows are ordered by ``miss_distance_km`` and picked at evenly spaced
   rank positions, which guarantees a miss-distance spread inside every stratum instead
   of relying on chance.

Writes ``processed/sample_for_viz.parquet`` with a ``stratum`` column, plus
``processed/sample_strata.json`` recording the rule, the seed and every cell count.

    python scripts/sample_for_viz.py --target 2000 --seed 20260819
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import settings  # noqa: E402
from core.schema import PC_FLOOR  # noqa: E402
from core.store import store  # noqa: E402

EARTH_RADIUS_KM = 6378.137

PC_CLASS_SQL = f"""
case
  when pc is null                     then 'null'
  when pc_is_floored                  then 'censored'
  when pc >= 1e-4                     then 'action'
  when pc >= 1e-6                     then 'near_threshold'
  when pc >= 1e-8                     then 'moderate'
  else                                     'low'
end
"""

ALTITUDE_SQL = (
    f"sqrt(obj1_x*obj1_x + obj1_y*obj1_y + obj1_z*obj1_z) - {EARTH_RADIUS_KM}"
)

ALTITUDE_BAND_SQL = f"""
case
  when ({ALTITUDE_SQL}) < 500   then '<500'
  when ({ALTITUDE_SQL}) < 800   then '500-800'
  when ({ALTITUDE_SQL}) < 2000  then '800-2000'
  else                               '>=2000'
end
"""

DILUTION_SQL = """
case
  when dilution is null then 'unknown'
  when dilution = 1     then 'diluted'
  else                       'robust'
end
"""

#: Classes guaranteed to be taken in full first: rare, and exactly what the
#: visualisation needs to show.
PRIORITY_CLASSES = ("action", "near_threshold", "null")


def build_index(connection) -> None:
    """Materialise a small stratification index: one row per event, six columns."""
    unions = " union all ".join(
        f"""
        select
          '{source}'            as source,
          event_id,
          row_number() over ()  as row_index,
          {PC_CLASS_SQL}        as pc_class,
          {DILUTION_SQL}        as dilution_class,
          {ALTITUDE_BAND_SQL}   as altitude_band,
          miss_distance_km
        from {source}
        """
        for source in store.available()
    )
    connection.execute(f"create temp table idx as {unions}")
    connection.execute(
        "alter table idx add column stratum varchar"
    )
    connection.execute(
        "update idx set stratum = source || '|' || pc_class || '|' || "
        "dilution_class || '|' || altitude_band"
    )


def allocate(sizes: dict[str, int], target: int) -> dict[str, int]:
    """Give rare, high-value strata their full size first, then spread the rest."""
    quotas: dict[str, int] = {}
    remaining = target

    priority = sorted(s for s in sizes if s.split("|")[1] in PRIORITY_CLASSES)
    cap = max(1, 3 * target // max(len(sizes), 1))
    for stratum in priority:
        take = min(sizes[stratum], cap, remaining)
        if take > 0:
            quotas[stratum] = take
            remaining -= take

    others = sorted(s for s in sizes if s not in quotas)
    while remaining > 0 and others:
        share = max(1, remaining // len(others))
        progressed = False
        for stratum in list(others):
            if remaining <= 0:
                break
            room = sizes[stratum] - quotas.get(stratum, 0)
            if room <= 0:
                others.remove(stratum)
                continue
            take = min(share, room, remaining)
            quotas[stratum] = quotas.get(stratum, 0) + take
            remaining -= take
            progressed = progressed or take > 0
        if not progressed:
            break
    return {k: v for k, v in quotas.items() if v > 0}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20260819)
    args = parser.parse_args()

    connection = store.connect()
    try:
        connection.execute(f"select setseed({(args.seed % 1000) / 1000.0})")
        build_index(connection)

        sizes = {
            row[0]: int(row[1])
            for row in connection.execute(
                "select stratum, count(*) from idx group by 1"
            ).fetchall()
        }
        if not sizes:
            raise RuntimeError("stratification produced no cells")

        quotas = allocate(sizes, args.target)
        if not quotas:
            raise RuntimeError("allocation produced no quotas")

        quota_values = ", ".join(
            f"('{stratum}', {quota})" for stratum, quota in sorted(quotas.items())
        )
        connection.execute(
            f"create temp table quota as "
            f"select * from (values {quota_values}) t(stratum, n)"
        )

        # Bucket each rank into one of `quota` equal buckets and keep the first row of
        # each bucket: deterministic, and spreads miss distance across every cell.
        connection.execute(
            """
            create temp table picked as
            select source, event_id, stratum
            from (
              select idx.source, idx.event_id, idx.stratum,
                     row_number() over (
                       partition by idx.stratum
                       order by idx.miss_distance_km, idx.event_id
                     ) as rank,
                     count(*) over (partition by idx.stratum) as cell_size,
                     q.n as quota
              from idx join quota q on q.stratum = idx.stratum
            )
            qualify row_number() over (
              partition by stratum, least(
                quota - 1,
                -- integer bucket index; DuckDB's `/` is float division, which would
                -- give a near-unique bucket per rank and select almost every row.
                cast(floor(((rank - 1) * quota)::double / cell_size) as bigint)
              )
              order by rank
            ) = 1
            """
        )

        counts = {
            row[0]: int(row[1])
            for row in connection.execute(
                "select stratum, count(*) from picked group by 1 order by 1"
            ).fetchall()
        }
        selected_total = sum(counts.values())
        if selected_total == 0:
            raise RuntimeError("no rows selected; refusing to write an empty sample")

        destination = settings.PROCESSED_DIR / "sample_for_viz.parquet"
        location = str(destination).replace("\\", "/").replace("'", "''")
        union = " union all ".join(
            f"select e.*, p.stratum from {source} e "
            f"join picked p on p.event_id = e.event_id and p.source = '{source}'"
            for source in store.available()
        )
        connection.execute(
            f"copy ({union}) to '{location}' (format parquet, compression zstd)"
        )

        population = {
            row[0]: int(row[1])
            for row in connection.execute(
                "select stratum, count(*) from idx group by 1 order by 1"
            ).fetchall()
        }
    finally:
        connection.close()

    manifest = {
        "target": args.target,
        "selected": selected_total,
        "seed": args.seed,
        "pc_floor": PC_FLOOR,
        "pc_floor_is_documented": False,
        "pc_classes": {
            "action": "pc >= 1e-4",
            "near_threshold": "1e-6 <= pc < 1e-4",
            "moderate": "1e-8 <= pc < 1e-6",
            "low": "1e-10 < pc < 1e-8",
            "censored": "pc <= 1e-10 (a bound, not a measurement)",
            "null": "pc not computable (non-PSD covariance)",
        },
        "dilution_classes": {
            "robust": "dilution = 0 (covariance trustworthy)",
            "diluted": "dilution = 1 (covariance diluted, Pc unreliable)",
            "unknown": "dilution NULL",
        },
        "altitude_bands_km": ["<500", "500-800", "800-2000", ">=2000"],
        "altitude_definition": "|r| of object 1 minus 6378.137 km (spherical, not geodetic)",
        "priority_classes_taken_first": list(PRIORITY_CLASSES),
        "within_cell_rule": (
            "ranked by miss_distance_km then event_id, bucketed into `quota` equal "
            "buckets, first row of each bucket kept"
        ),
        "strata_counts": dict(sorted(counts.items())),
        "population_by_stratum": population,
    }
    (settings.PROCESSED_DIR / "sample_strata.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    print(f"selected {selected_total:,} events across {len(counts)} strata (seed {args.seed})")
    for stratum, count in sorted(counts.items()):
        print(f"  {stratum:52s} {count:5d} / {population[stratum]:,}")
    print(f"-> {settings.PROCESSED_DIR / 'sample_for_viz.parquet'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
