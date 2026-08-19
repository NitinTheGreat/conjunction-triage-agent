"""Join hard-body radius onto both objects of every ingested event.

The two answer keys do **not** use the same HBR, and the Users Guide is explicit about
it, so a single naive join by ``catalog_num`` would misrepresent one of them:

* **Spherical** run -- "Use a constant HBR of 0.5 m for probability of collision
  calculation". Every object gets 0.5 m regardless of what the mappings file says.
* **SFSH** run -- "Use HBR values (per-object) as provided in the input mappings file".

Both are recorded, so nothing is lost:

* ``objN_hbr_m``          -- the HBR that actually produced that file's ``prob`` column.
* ``objN_hbr_catalog_m``  -- the per-object value from the mappings file, for every
  source, ``NULL`` when the object is absent from the file.
* ``objN_hbr_source``     -- ``"spherical_default"``, ``"screening_volumes"``, or
  ``"unmatched"``.

Unmatched objects are left ``NULL`` and counted. They are never filled with a default:
a silently substituted HBR would propagate into every later collision-probability
computation as a plausible-looking wrong number.

The join runs inside DuckDB, so nothing is materialised in Python. Idempotent: it
rewrites each file from the source columns every time. ``dataset/`` is read-only.

    python scripts/join_hbr.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import settings  # noqa: E402
from core.store import store  # noqa: E402

SCREENING_VOLUMES = "AerospaceIVVDataset_20251009a_Size_ScreeningVolumes.csv"

#: Users Guide, Screening Volume section: "a CSieve run was conducted using a spherical
#: screening volume of 10 km and a default HBR of 0.5m".
SPHERICAL_DEFAULT_HBR_M = 0.5

#: HBR is in **metres**. Confirmed against catalogue 5 (Vanguard 1), a 16.5 cm sphere,
#: whose tabulated HBR is 0.0825 -- exactly its radius in metres.
HBR_UNIT = "m"

ADDED_COLUMNS = ("hbr_catalog_m", "hbr_source")


def load_hbr_table(path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Load catalogue -> HBR (metres), collapsing exact duplicate rows.

    Raises if a catalogue number carries genuinely conflicting HBR values, rather than
    silently picking one.
    """
    if not path.is_file():
        raise FileNotFoundError(path)

    frame = pd.read_csv(
        path,
        usecols=["catalog_num", "HBR"],
        dtype={"catalog_num": "int64", "HBR": "float64"},
    )
    if frame["HBR"].isna().any():
        raise ValueError(f"{path.name}: HBR column contains nulls")

    conflicting = frame.groupby("catalog_num")["HBR"].nunique()
    conflicts = conflicting[conflicting > 1]
    if len(conflicts):
        raise ValueError(
            f"{path.name}: {len(conflicts)} catalogue numbers have conflicting HBR "
            f"values, e.g. {conflicts.index[:5].tolist()}; refusing to guess"
        )

    deduplicated = frame.drop_duplicates(subset="catalog_num").copy()
    deduplicated["catalog_id"] = deduplicated["catalog_num"].astype(str)
    lookup = deduplicated[["catalog_id", "HBR"]].rename(columns={"HBR": "hbr_m"})

    stats = {
        "rows": len(frame),
        "unique_catalog_num": len(lookup),
        "exact_duplicate_rows_collapsed": len(frame) - len(lookup),
        "hbr_unit": HBR_UNIT,
        "hbr_min": float(frame["HBR"].min()),
        "hbr_max": float(frame["HBR"].max()),
        "hbr_median": float(frame["HBR"].median()),
    }
    return lookup, stats


def join_file(key: str, lookup: pd.DataFrame) -> dict[str, Any]:
    """Rewrite one parquet file with HBR columns populated. Returns match statistics."""
    path = store.path(key)
    is_spherical = key == "spherical"

    connection = store.connect()
    try:
        connection.register("hbr", lookup)

        base = [
            c for c in store.columns(key)
            if not any(c.endswith(f"_{added}") for added in ADDED_COLUMNS)
        ]
        # objN_hbr_m is recomputed, so drop the ingested (all-NULL) version too.
        carried = [c for c in base if c not in ("obj1_hbr_m", "obj2_hbr_m")]

        if is_spherical:
            # The spherical answer key was produced with a flat 0.5 m HBR.
            hbr_expressions = [
                f"{SPHERICAL_DEFAULT_HBR_M} as obj{i}_hbr_m" for i in (1, 2)
            ] + [
                f"'spherical_default' as obj{i}_hbr_source" for i in (1, 2)
            ]
        else:
            hbr_expressions = [
                f"h{i}.hbr_m as obj{i}_hbr_m" for i in (1, 2)
            ] + [
                f"case when h{i}.hbr_m is null then 'unmatched' "
                f"else 'screening_volumes' end as obj{i}_hbr_source"
                for i in (1, 2)
            ]

        select = ", ".join(
            [f"e.{c}" for c in carried]
            + [f"h{i}.hbr_m as obj{i}_hbr_catalog_m" for i in (1, 2)]
            + hbr_expressions
        )
        joined = (
            f"select {select} from {key} e "
            "left join hbr h1 on e.obj1_catalog_id = h1.catalog_id "
            "left join hbr h2 on e.obj2_catalog_id = h2.catalog_id"
        )

        stats = connection.execute(
            f"""
            select
              count(*)                                             as events,
              count(obj1_hbr_catalog_m)                            as matched_obj1,
              count(obj2_hbr_catalog_m)                            as matched_obj2,
              count(*) - count(obj1_hbr_catalog_m)                 as unmatched_obj1,
              count(*) - count(obj2_hbr_catalog_m)                 as unmatched_obj2
            from ({joined})
            """
        ).fetchone()

        unmatched_ids = connection.execute(
            f"""
            select distinct catalog_id from (
              select obj1_catalog_id as catalog_id, obj1_hbr_catalog_m as hbr from ({joined})
              union all
              select obj2_catalog_id, obj2_hbr_catalog_m from ({joined})
            ) where hbr is null
            """
        ).fetchdf()["catalog_id"].tolist()

        # Write via a temp file: duckdb cannot read and overwrite the same parquet.
        temp = path.with_suffix(".parquet.tmp")
        location = str(temp).replace("\\", "/").replace("'", "''")
        connection.execute(
            f"copy ({joined}) to '{location}' (format parquet, compression zstd)"
        )
    finally:
        connection.close()

    temp.replace(path)

    events, matched1, matched2, unmatched1, unmatched2 = (int(v) for v in stats)
    slots = 2 * events
    if matched1 + matched2 + unmatched1 + unmatched2 != slots:
        raise RuntimeError(f"{key}: match/miss counts do not sum to {slots}")

    return {
        "source": key,
        "events": events,
        "object_slots": slots,
        "matched": matched1 + matched2,
        "unmatched": unmatched1 + unmatched2,
        "matched_pct": round(100 * (matched1 + matched2) / max(slots, 1), 4),
        "matched_obj1": matched1,
        "matched_obj2": matched2,
        "unmatched_obj1": unmatched1,
        "unmatched_obj2": unmatched2,
        "distinct_unmatched_catalog_ids": len(unmatched_ids),
        "unmatched_examples": sorted(unmatched_ids)[:15],
        "hbr_applied": (
            f"constant {SPHERICAL_DEFAULT_HBR_M} m (Users Guide spherical default)"
            if is_spherical
            else "per-object from ScreeningVolumes; unmatched left NULL"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=list(store.available()))
    args = parser.parse_args()

    lookup, stats = load_hbr_table(settings.DATASET_DIR / SCREENING_VOLUMES)
    print(
        f"ScreeningVolumes: {stats['rows']:,} rows, "
        f"{stats['unique_catalog_num']:,} unique catalogue numbers "
        f"({stats['exact_duplicate_rows_collapsed']} exact duplicates collapsed), "
        f"HBR {stats['hbr_min']}-{stats['hbr_max']} {HBR_UNIT}"
    )

    keys = [args.source] if args.source else store.available()
    summaries = [join_file(key, lookup) for key in keys]
    for summary in summaries:
        print(
            f"  [{summary['source']}] {summary['events']:,} events, "
            f"{summary['matched']:,}/{summary['object_slots']:,} object slots matched "
            f"({summary['matched_pct']}%), {summary['unmatched']:,} unmatched across "
            f"{summary['distinct_unmatched_catalog_ids']} distinct catalogue ids"
        )

    report = {"screening_volumes": stats, "joins": summaries}
    destination = settings.PROCESSED_DIR / "hbr_report.json"
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"-> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
