"""End-to-end verification of Phase 4.

Prints one pass/fail line per check and exits non-zero if any fails. Every check treats a
*vacuous* pass — zero rows, zero events, zero files — as a failure.

    python scripts/verify_phase4.py
    python scripts/verify_phase4.py --skip-checksums
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

import duckdb
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from core.config import settings  # noqa: E402
from core.schema import KELVINS_PC_FLOOR  # noqa: E402
from verify_phase1 import CheckFailure  # noqa: E402

KELVINS_DIR = "kelvins"
#: split -> (source csv, expected rows, expected events)
EXPECTED = {
    "train": ("train_data.csv", 162_634, 13_154),
    "test": ("test_data.csv", 24_484, 2_167),
}
CHUNK_BYTES = 1 << 20


def _sql(path: Path) -> str:
    return str(path).replace("\\", "/").replace("'", "''")


def _connect() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect()
    connection.execute("set TimeZone = 'UTC'")
    connection.execute("set memory_limit = '1GB'")
    return connection


def _processed(name: str) -> Path:
    path = settings.PROCESSED_DIR / KELVINS_DIR / name
    if not path.is_file():
        raise CheckFailure(f"{path} missing; run scripts/ingest_kelvins.py")
    return path


def _source(name: str) -> Path:
    path = settings.DATASET_DIR / KELVINS_DIR / name
    if not path.is_file():
        raise CheckFailure(f"{path} missing; run scripts/fetch_kelvins.py")
    return path


def _reject_count(split: str) -> int:
    path = settings.PROCESSED_DIR / KELVINS_DIR / f"rejects_{split}.csv"
    if not path.is_file():
        return 0
    return len(pd.read_csv(path))


# -- 1 ---------------------------------------------------------------------------------

def check_download_checksums() -> str:
    """Downloaded files match the recorded SHA-256 checksums."""
    provenance = settings.PROCESSED_DIR / "kelvins_provenance.json"
    if not provenance.is_file():
        raise CheckFailure("processed/kelvins_provenance.json missing")
    record = json.loads(provenance.read_text(encoding="utf-8"))

    entries = record.get("files") or []
    if not entries:
        raise CheckFailure("provenance records no files (trivial pass guard)")

    manifest = (settings.DATASET_DIR / "MANIFEST.md").read_text(encoding="utf-8")
    problems = []
    for entry in entries:
        path = settings.DATASET_DIR / KELVINS_DIR / entry["filename"]
        if not path.is_file():
            problems.append(f"{entry['filename']}: missing")
            continue
        if path.stat().st_size != entry["bytes"]:
            problems.append(f"{entry['filename']}: size differs")
            continue
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(CHUNK_BYTES), b""):
                digest.update(chunk)
        if digest.hexdigest() != entry["sha256"]:
            problems.append(f"{entry['filename']}: sha256 differs")
        elif entry["sha256"] not in manifest:
            problems.append(f"{entry['filename']}: checksum absent from MANIFEST.md")

    if problems:
        raise CheckFailure("; ".join(problems))
    return f"{len(entries)} Kelvins files match their SHA-256 and appear in MANIFEST.md"


# -- 2 ---------------------------------------------------------------------------------

def check_counts() -> str:
    """Ingested CDM and event counts match the source exactly, minus recorded rejects."""
    connection = _connect()
    parts = []
    try:
        for split, (csv_name, expected_rows, expected_events) in EXPECTED.items():
            source_rows = int(
                connection.execute(
                    f"select count(*) from read_csv_auto('{_sql(_source(csv_name))}')"
                ).fetchone()[0]
            )
            if source_rows != expected_rows:
                raise CheckFailure(
                    f"{split}: source has {source_rows} rows, expected {expected_rows}"
                )
            cdms = int(
                connection.execute(
                    f"select count(*) from read_parquet('{_sql(_processed(f'cdms_{split}.parquet'))}')"
                ).fetchone()[0]
            )
            series = int(
                connection.execute(
                    f"select count(*) from read_parquet('{_sql(_processed(f'series_{split}.parquet'))}')"
                ).fetchone()[0]
            )
            if cdms == 0 or series == 0:
                raise CheckFailure(f"{split}: ingested zero rows")
            rejects = _reject_count(split)
            if cdms + rejects != source_rows:
                raise CheckFailure(
                    f"{split}: {cdms} CDMs + {rejects} rejects != {source_rows} source rows"
                )
            if series != expected_events:
                raise CheckFailure(
                    f"{split}: {series} series, expected {expected_events}"
                )
            parts.append(f"{split} {cdms:,}+{rejects}={source_rows:,}, {series:,} series")
    finally:
        connection.close()
    return "; ".join(parts)


# -- 3 ---------------------------------------------------------------------------------

def check_random_cdm_matches_source() -> str:
    """A random ingested CDM matches its source row field for field."""
    rng = np.random.default_rng(20260819)
    connection = _connect()
    checked = 0
    try:
        for split, (csv_name, _, _) in EXPECTED.items():
            frame = connection.execute(
                f"select * from read_parquet('{_sql(_processed(f'cdms_{split}.parquet'))}')"
                f" using sample 1 rows (reservoir, {int(rng.integers(1, 10**6))})"
            ).fetchdf()
            if frame.empty:
                raise CheckFailure(f"{split}: could not sample a CDM")
            row = frame.iloc[0].to_dict()

            raw = connection.execute(
                f"select * from read_csv_auto('{_sql(_source(csv_name))}') "
                f"where event_id = {int(row['kelvins_event_id'])} "
                f"and abs(time_to_tca - {row['time_to_tca_days']!r}) < 1e-12"
            ).fetchdf()
            if len(raw) != 1:
                raise CheckFailure(
                    f"{split}: {len(raw)} source rows match event "
                    f"{row['kelvins_event_id']} at t={row['time_to_tca_days']}"
                )
            source = raw.iloc[0].to_dict()

            comparisons = [
                ("miss_distance", row["miss_distance_km"] * 1000.0),
                ("relative_speed", row["relative_speed_kms"] * 1000.0),
                ("mahalanobis_distance", row["mahalanobis_distance"]),
                ("risk", row["risk_log10"]),
                ("max_risk_scaling", row["max_risk_scaling"]),
                ("F10", row["F10"]), ("AP", row["AP"]),
            ]
            for column, got in comparisons:
                want = source[column]
                if pd.isna(want) and (got is None or pd.isna(got)):
                    continue
                if not np.isclose(float(want), float(got), rtol=1e-12, atol=0):
                    raise CheckFailure(
                        f"{split} event {row['kelvins_event_id']}: {column} "
                        f"source={want!r} ingested={got!r}"
                    )
            # pc must be the linear form of the source's log10 risk
            if not np.isclose(float(row["pc"]), 10.0 ** float(source["risk"]), rtol=1e-9):
                raise CheckFailure(f"{split}: pc is not 10**risk")
            # covariance must rebuild from the source sigmas
            expected_c11 = (float(source["t_sigma_r"]) / 1000.0) ** 2
            if not np.isclose(float(row["target_c_11"]), expected_c11, rtol=1e-9):
                raise CheckFailure(f"{split}: target_c_11 does not match t_sigma_r^2")
            checked += 1
    finally:
        connection.close()

    if checked != len(EXPECTED):
        raise CheckFailure("no CDMs compared")
    return f"{checked} random CDMs match their source row field for field"


# -- 4 ---------------------------------------------------------------------------------

def check_series_ordering() -> str:
    """Every event series is ordered by descending time_to_tca."""
    connection = _connect()
    total = 0
    try:
        for split in EXPECTED:
            path = _sql(_processed(f"cdms_{split}.parquet"))
            bad = int(
                connection.execute(
                    f"""
                    select count(*) from (
                      select series_id, time_to_tca_days,
                             lag(time_to_tca_days) over (
                               partition by series_id order by cdm_index
                             ) as previous
                      from read_parquet('{path}')
                    ) where previous is not null and time_to_tca_days > previous
                    """
                ).fetchone()[0]
            )
            if bad:
                raise CheckFailure(f"{split}: {bad} CDMs are out of order")
            # cdm_index must be a dense 0..n-1 sequence within each series
            gaps = int(
                connection.execute(
                    f"""
                    select count(*) from (
                      select series_id, max(cdm_index) mx, count(*) n
                      from read_parquet('{path}') group by 1
                    ) where mx <> n - 1
                    """
                ).fetchone()[0]
            )
            if gaps:
                raise CheckFailure(f"{split}: {gaps} series have gaps in cdm_index")
            total += int(
                connection.execute(
                    f"select count(distinct series_id) from read_parquet('{path}')"
                ).fetchone()[0]
            )
    finally:
        connection.close()

    if total == 0:
        raise CheckFailure("zero series checked")
    return f"{total:,} series ordered by descending time_to_tca with dense indices"


# -- 5 ---------------------------------------------------------------------------------

def check_label_distribution() -> str:
    """The ingested label distribution matches the source."""
    connection = _connect()
    try:
        # train labels come from the final CDM of each event in the source
        source = connection.execute(
            f"""
            with f as (
              select *, row_number() over (
                partition by event_id order by time_to_tca asc
              ) rn
              from read_csv_auto('{_sql(_source("train_data.csv"))}')
            )
            select count(*) n, count(*) filter (where risk >= -6) ge6,
                   count(*) filter (where risk >= -4) ge4,
                   count(*) filter (where risk <= -30) floored
            from f where rn = 1
            """
        ).fetchone()
        ingested = connection.execute(
            f"""
            select count(*) n,
                   count(*) filter (where final_risk_log10 >= -6) ge6,
                   count(*) filter (where final_risk_log10 >= -4) ge4,
                   count(*) filter (where final_risk_is_floored) floored
            from read_parquet('{_sql(_processed("series_train.parquet"))}')
            """
        ).fetchone()
        if tuple(int(v) for v in source) != tuple(int(v) for v in ingested):
            raise CheckFailure(
                f"train label distribution differs: source {source} vs ingested {ingested}"
            )

        # test labels come from the withheld private file
        private = connection.execute(
            f"""
            select count(*) n, count(*) filter (where true_risk >= -6) ge6,
                   count(*) filter (where true_risk >= -4) ge4,
                   count(*) filter (where true_risk <= -30) floored
            from read_csv_auto('{_sql(_source("test_data_private.csv"))}')
            """
        ).fetchone()
        ingested_test = connection.execute(
            f"""
            select count(*) n,
                   count(*) filter (where final_risk_log10 >= -6) ge6,
                   count(*) filter (where final_risk_log10 >= -4) ge4,
                   count(*) filter (where final_risk_is_floored) floored
            from read_parquet('{_sql(_processed("series_test.parquet"))}')
            """
        ).fetchone()
        if tuple(int(v) for v in private) != tuple(int(v) for v in ingested_test):
            raise CheckFailure(
                f"test label distribution differs: private {private} vs "
                f"ingested {ingested_test}"
            )
        if int(source[1]) == 0:
            raise CheckFailure("no above-threshold labels at all (trivial pass guard)")
    finally:
        connection.close()

    return (
        f"train {int(source[0]):,} labels ({int(source[1])} >= -6, {int(source[2])} >= -4); "
        f"test {int(private[0]):,} labels from the withheld file "
        f"({int(private[1])} >= -6, {int(private[2])} >= -4)"
    )


# -- 6 ---------------------------------------------------------------------------------

def check_splits_disjoint() -> str:
    """Train and test series are disjoint.

    Kelvins ``event_id`` restarts at 0 in each split, so the *raw* ids overlap entirely.
    Disjointness is a property of the split-qualified ``series_id``, and this check
    asserts both facts so the raw-id trap is documented rather than hidden.
    """
    connection = _connect()
    try:
        overlap_series = int(
            connection.execute(
                f"""
                select count(*) from (
                  select distinct series_id from read_parquet('{_sql(_processed("series_train.parquet"))}')
                ) t join (
                  select distinct series_id from read_parquet('{_sql(_processed("series_test.parquet"))}')
                ) s using (series_id)
                """
            ).fetchone()[0]
        )
        if overlap_series:
            raise CheckFailure(f"{overlap_series} series_id values appear in both splits")

        overlap_raw = int(
            connection.execute(
                f"""
                select count(*) from (
                  select distinct kelvins_event_id from read_parquet('{_sql(_processed("series_train.parquet"))}')
                ) t join (
                  select distinct kelvins_event_id from read_parquet('{_sql(_processed("series_test.parquet"))}')
                ) s using (kelvins_event_id)
                """
            ).fetchone()[0]
        )
        if overlap_raw == 0:
            raise CheckFailure(
                "raw event_ids do not overlap, contradicting the documented per-split "
                "indexing — the ingestion may have rewritten them"
            )
    finally:
        connection.close()
    return (
        f"0 series_id collisions; {overlap_raw:,} raw event_id collisions as expected "
        "(ids restart per split, so raw ids must never be used as a key)"
    )


# -- 7 ---------------------------------------------------------------------------------

def check_tracss_unchanged() -> str:
    """The TraCSS parquet is unchanged by this phase (regression guard)."""
    from core.store import store

    expected = {"spherical": 913_292, "sfsh": 283_568}
    for source, rows in expected.items():
        actual = store.count(source)
        if actual != rows:
            raise CheckFailure(f"{source}: {actual:,} rows, expected {rows:,}")

    censored = int(
        store.scalar(
            "select count(*) from (select pc_is_floored from spherical "
            "union all select pc_is_floored from sfsh) where pc_is_floored"
        )
    )
    if censored != 724_121:
        raise CheckFailure(f"TraCSS censored count changed: {censored:,} vs 724,121")
    return f"TraCSS unchanged: {sum(expected.values()):,} rows, {censored:,} censored"


# -- 8 ---------------------------------------------------------------------------------

def check_pytest() -> str:
    """pytest passes."""
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    lines = (completed.stdout or completed.stderr).strip().splitlines()
    line = lines[-1] if lines else "(no output)"
    if completed.returncode != 0:
        raise CheckFailure(f"pytest exited {completed.returncode}: {line}")
    match = re.search(r"(\d+) passed", line)
    if not match or int(match.group(1)) == 0:
        raise CheckFailure(f"pytest reported no passing tests: {line}")
    return f"pytest: {line}"


# -- 9 (addition) ----------------------------------------------------------------------

def check_floor_handling() -> str:
    """The Kelvins floor is applied per source, not the TraCSS one."""
    connection = _connect()
    try:
        row = connection.execute(
            f"""
            select count(*) total,
                   count(*) filter (where pc_is_floored) floored,
                   count(*) filter (where pc_is_floored and risk_log10 > -30) wrong_flag,
                   count(*) filter (where not pc_is_floored and risk_log10 <= -30) missed,
                   count(*) filter (where not pc_is_floored and pc <= 1e-10) below_tracss
            from read_parquet('{_sql(_processed("cdms_train.parquet"))}')
            """
        ).fetchone()
    finally:
        connection.close()
    total, floored, wrong, missed, below_tracss = (int(v) for v in row)
    if wrong or missed:
        raise CheckFailure(
            f"floor flag inconsistent: {wrong} flagged above -30, {missed} unflagged at -30"
        )
    if floored == 0 or floored == total:
        raise CheckFailure(f"degenerate censoring: {floored}/{total}")
    if below_tracss == 0:
        raise CheckFailure(
            "no uncensored record sits below the TraCSS floor, so this check cannot "
            "demonstrate that the per-source floor is actually being applied"
        )
    return (
        f"{floored:,}/{total:,} floored at {KELVINS_PC_FLOOR:g}; {below_tracss:,} records "
        f"sit below the TraCSS floor yet are correctly uncensored"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-checksums", action="store_true")
    args = parser.parse_args()

    checks: list[tuple[str, Callable[[], str]]] = [
        (
            "downloaded files match the recorded checksums",
            (lambda: "checksums SKIPPED") if args.skip_checksums else check_download_checksums,
        ),
        ("ingested counts match the source minus rejects", check_counts),
        ("a random CDM matches its source row", check_random_cdm_matches_source),
        ("every series is correctly ordered", check_series_ordering),
        ("label distribution matches the source", check_label_distribution),
        ("train and test series are disjoint", check_splits_disjoint),
        ("TraCSS parquet unchanged by this phase", check_tracss_unchanged),
        ("pytest passes", check_pytest),
        ("per-source Pc floor applied correctly (addition)", check_floor_handling),
    ]

    print(f"Phase 4 verification -- {REPO_ROOT}\n")
    failures = 0
    for number, (title, check) in enumerate(checks, start=1):
        try:
            detail = check()
        except Exception as exc:
            failures += 1
            print(f"[FAIL] {number}. {title}")
            print(f"        {type(exc).__name__}: {exc}")
        else:
            print(f"[PASS] {number}. {title}")
            print(f"        {detail}")

    total = len(checks)
    print(f"\n{total - failures}/{total} checks passed.")
    if failures:
        print(f"{failures} FAILED -- Phase 4 is not complete.")
        return 1
    print("Phase 4 verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
