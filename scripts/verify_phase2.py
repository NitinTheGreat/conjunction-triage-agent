"""End-to-end verification of Phase 2.

Prints one pass/fail line per check and exits non-zero if any fails. Every check treats
a *vacuous* pass -- zero rows, zero files, zero strata -- as a failure.

    python scripts/verify_phase2.py
    python scripts/verify_phase2.py --skip-checksums
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from core.config import settings  # noqa: E402
from core.schema import (  # noqa: E402
    PC_FLOOR,
    ConjunctionEvent,
    EventSource,
    ObjectState,
)
from verify_phase1 import CheckFailure, check_dataset_unmodified  # noqa: E402

SOURCES = {
    "spherical": ("IVV_Releasable_Dataset_Spherical_DefaultHBR.csv", 913_330),
    "sfsh": ("IVV_Releasable_Dataset_SFSH_DiscreteHBR.csv", 283_595),
}

#: Seed for the random row-level checks. Reported so a failure is reproducible.
SEED = 20260818
ROUND_TRIP_SAMPLE = 1000
COVARIANCE_ELEMENTS = ("11", "12", "13", "22", "23", "33")


def _parquet(key: str) -> Path:
    path = settings.PROCESSED_DIR / f"{key}.parquet"
    if not path.is_file():
        raise CheckFailure(f"{path.name} missing; run scripts/ingest.py")
    return path


def _reject_count(key: str) -> int:
    path = settings.PROCESSED_DIR / f"rejects_{key}.csv"
    if not path.is_file():
        return 0
    return len(pd.read_csv(path))


# -- 1 ---------------------------------------------------------------------------------

def check_row_counts() -> str:
    """Parquet row counts equal source CSV data rows minus rejects."""
    parts = []
    for key, (_, expected_rows) in SOURCES.items():
        rows = pq.ParquetFile(_parquet(key)).metadata.num_rows
        rejects = _reject_count(key)
        if rows == 0:
            raise CheckFailure(f"{key}: parquet has zero rows")
        if rows + rejects != expected_rows:
            raise CheckFailure(
                f"{key}: {rows} parquet + {rejects} rejects != {expected_rows} CSV rows"
            )
        parts.append(f"{key} {rows:,}+{rejects}={expected_rows:,}")
    return "; ".join(parts)


# -- 2 ---------------------------------------------------------------------------------

def check_random_row_matches_csv() -> str:
    """A random parquet row matches its CSV source line field for field."""
    rng = np.random.default_rng(SEED)
    checked = 0
    for key, (filename, _) in SOURCES.items():
        table = pq.ParquetFile(_parquet(key))
        total = table.metadata.num_rows
        target = int(rng.integers(0, total))

        # Walk batches to the target row without materialising the file.
        offset = 0
        row = None
        for batch in table.iter_batches(batch_size=50_000):
            if offset + batch.num_rows > target:
                row = batch.slice(target - offset, 1).to_pylist()[0]
                break
            offset += batch.num_rows
        if row is None:
            raise CheckFailure(f"{key}: could not reach row {target}")

        line = row["source_line"]
        csv_path = settings.DATASET_DIR / filename
        header = pd.read_csv(csv_path, nrows=0).columns.tolist()
        raw = pd.read_csv(
            csv_path, skiprows=line - 1, nrows=1, header=None, names=header
        ).iloc[0]

        comparisons = [
            ("min_range", row["miss_distance_km"]),
            ("Vrel", row["relative_speed_kms"]),
            ("mdistance", row["mahalanobis_distance"]),
            ("prob", row["pc"]),
            ("jdate", row["jdate"]),
            ("x1", row["obj1_x"]), ("y1", row["obj1_y"]), ("z1", row["obj1_z"]),
            ("vx2", row["obj2_vx"]),
            ("local_y1", row["obj1_local_y"]),
        ]
        for column, got in comparisons:
            want = raw[column]
            if pd.isna(want) and got is None:
                continue
            if got is None or not np.isclose(float(want), float(got), rtol=0, atol=0):
                raise CheckFailure(
                    f"{key} line {line}: {column} CSV={want!r} parquet={got!r}"
                )
        for element in COVARIANCE_ELEMENTS:
            want = float(raw[f"c1_{element}"])
            got = float(row[f"obj1_c_{element}"])
            if want != got:
                raise CheckFailure(f"{key} line {line}: c1_{element} {want} != {got}")
        if str(raw["conj_id"]) != row["conj_id"]:
            raise CheckFailure(f"{key} line {line}: conj_id mismatch")
        if str(raw["obj1"]) != row["obj1_catalog_id"]:
            raise CheckFailure(f"{key} line {line}: obj1 mismatch")
        if str(raw["epoch"]) != row["tca"].strftime("%Y-%m-%d %H:%M:%S.%f"):
            raise CheckFailure(f"{key} line {line}: epoch/tca mismatch")
        checked += 1

    if checked != len(SOURCES):
        raise CheckFailure("no rows compared")
    return f"{checked} random rows match their CSV source line exactly (seed {SEED})"


# -- 3 ---------------------------------------------------------------------------------

def check_covariances() -> str:
    """Covariances rebuilt from parquet are symmetric and positive-semidefinite."""
    total = 0
    worst = np.inf
    for key in SOURCES:
        columns = [f"obj{i}_c_{e}" for i in (1, 2) for e in COVARIANCE_ELEMENTS]
        for batch in pq.ParquetFile(_parquet(key)).iter_batches(
            batch_size=100_000, columns=columns
        ):
            frame = batch.to_pandas()
            for index in (1, 2):
                stacked = np.empty((len(frame), 3, 3), dtype=np.float64)
                get = lambda e: frame[f"obj{index}_c_{e}"].to_numpy(dtype=np.float64)  # noqa: E731
                stacked[:, 0, 0] = get("11")
                stacked[:, 0, 1] = stacked[:, 1, 0] = get("12")
                stacked[:, 0, 2] = stacked[:, 2, 0] = get("13")
                stacked[:, 1, 1] = get("22")
                stacked[:, 1, 2] = stacked[:, 2, 1] = get("23")
                stacked[:, 2, 2] = get("33")

                if not np.array_equal(stacked, stacked.transpose(0, 2, 1)):
                    raise CheckFailure(f"{key}: a covariance is not symmetric")
                eigenvalues = np.linalg.eigvalsh(stacked)
                smallest = eigenvalues[:, 0]
                scale = np.maximum(1.0, np.abs(eigenvalues).max(axis=1))
                if (smallest < -1e-10 * scale).any():
                    bad = int((smallest < -1e-10 * scale).sum())
                    raise CheckFailure(f"{key}: {bad} covariances are not PSD")
                worst = min(worst, float(smallest.min()))
                total += len(frame)

    if total == 0:
        raise CheckFailure("zero covariances checked")
    return f"{total:,} covariances symmetric and PSD (smallest eigenvalue {worst:.6g})"


# -- 4 ---------------------------------------------------------------------------------

def check_censoring_flag() -> str:
    """pc_is_floored agrees with pc on every row."""
    total = censored = 0
    for key in SOURCES:
        for batch in pq.ParquetFile(_parquet(key)).iter_batches(
            batch_size=200_000, columns=["pc", "pc_is_floored"]
        ):
            frame = batch.to_pandas()
            pc = frame["pc"].to_numpy(dtype=np.float64)
            flag = frame["pc_is_floored"].fillna(False).to_numpy(dtype=bool)
            expected = (~np.isnan(pc)) & (pc <= PC_FLOOR)
            if not np.array_equal(flag, expected):
                raise CheckFailure(
                    f"{key}: {int((flag != expected).sum())} rows disagree with pc"
                )
            total += len(frame)
            censored += int(expected.sum())

    if total == 0:
        raise CheckFailure("zero rows checked")
    if censored == 0 or censored == total:
        raise CheckFailure(
            f"degenerate censoring: {censored}/{total}; the flag is not discriminating"
        )
    return f"{total:,} rows agree; {censored:,} censored ({100 * censored / total:.2f}%)"


# -- 5 ---------------------------------------------------------------------------------

def check_hbr_totals() -> str:
    """HBR matched + unmatched equals the total object-slot count."""
    report_path = settings.PROCESSED_DIR / "hbr_report.json"
    if not report_path.is_file():
        raise CheckFailure("hbr_report.json missing; run scripts/join_hbr.py")
    report = json.loads(report_path.read_text(encoding="utf-8"))

    joins = report.get("joins") or []
    if not joins:
        raise CheckFailure("hbr_report.json records no joins")

    parts = []
    for join in joins:
        rows = pq.ParquetFile(_parquet(join["source"])).metadata.num_rows
        slots = 2 * rows
        if join["object_slots"] != slots:
            raise CheckFailure(
                f"{join['source']}: report says {join['object_slots']} slots, "
                f"parquet implies {slots}"
            )
        if join["matched"] + join["unmatched"] != slots:
            raise CheckFailure(
                f"{join['source']}: {join['matched']} + {join['unmatched']} != {slots}"
            )
        if join["matched"] == 0:
            raise CheckFailure(f"{join['source']}: zero HBR matches")
        parts.append(
            f"{join['source']} {join['matched']:,}+{join['unmatched']:,}={slots:,}"
        )
    return "; ".join(parts)


# -- 6 ---------------------------------------------------------------------------------

def check_viz_sample() -> str:
    """The viz sample covers every declared stratum with a non-zero count."""
    manifest_path = settings.PROCESSED_DIR / "sample_strata.json"
    sample_path = settings.PROCESSED_DIR / "sample_for_viz.parquet"
    if not manifest_path.is_file() or not sample_path.is_file():
        raise CheckFailure("viz sample missing; run scripts/sample_for_viz.py")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    declared = manifest.get("strata_counts") or {}
    if not declared:
        raise CheckFailure("sample_strata.json declares no strata")

    table = pq.read_table(sample_path)
    if table.num_rows == 0:
        raise CheckFailure("viz sample is empty")

    actual = pd.Series(table.column("stratum").to_pylist()).value_counts().to_dict()
    empty = [s for s, c in declared.items() if c == 0]
    if empty:
        raise CheckFailure(f"declared strata with zero count: {empty}")
    missing = sorted(set(declared) - set(actual))
    if missing:
        raise CheckFailure(f"declared but absent from the sample: {missing}")
    for stratum, count in declared.items():
        if actual.get(stratum, 0) != count:
            raise CheckFailure(
                f"{stratum}: manifest says {count}, sample has {actual.get(stratum, 0)}"
            )

    classes = {s.split("|")[1] for s in actual}
    if "action" not in classes:
        raise CheckFailure("sample contains no high-probability (action) events")
    return (
        f"{table.num_rows:,} events across {len(actual)} strata, "
        f"{len(classes)} pc classes including 'action'"
    )


# -- 7 / 8 -----------------------------------------------------------------------------

def check_pytest() -> str:
    """pytest passes."""
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    lines = (completed.stdout or completed.stderr).strip().splitlines()
    summary = lines[-1] if lines else "(no output)"
    if completed.returncode != 0:
        raise CheckFailure(f"pytest exited {completed.returncode}: {summary}")
    match = re.search(r"(\d+) passed", summary)
    if not match or int(match.group(1)) == 0:
        raise CheckFailure(f"pytest reported no passing tests: {summary}")
    return f"pytest: {summary}"


# -- 9 (addition) ----------------------------------------------------------------------

def check_random_round_trip() -> str:
    """A random 1,000-row sample per file round-trips to_dict -> from_dict exactly.

    Phase 1 only proved the schema on the first 50 contiguous rows of each file. This
    draws from the whole file, which is what constraint 7 asks for.
    """
    rng = np.random.default_rng(SEED)
    checked = 0
    for key in SOURCES:
        table = pq.ParquetFile(_parquet(key))
        total = table.metadata.num_rows
        wanted = set(rng.choice(total, size=min(ROUND_TRIP_SAMPLE, total), replace=False).tolist())

        offset = 0
        for batch in table.iter_batches(batch_size=100_000):
            rows = [i - offset for i in wanted if offset <= i < offset + batch.num_rows]
            if rows:
                for record in batch.take(rows).to_pylist():
                    event = _event_from_parquet_row(record)
                    event.validate()
                    if ConjunctionEvent.from_dict(event.to_dict()) != event:
                        raise CheckFailure(f"{key}: {event.event_id} failed round-trip")
                    checked += 1
            offset += batch.num_rows

    expected = sum(min(ROUND_TRIP_SAMPLE, pq.ParquetFile(_parquet(k)).metadata.num_rows) for k in SOURCES)
    if checked != expected:
        raise CheckFailure(f"round-tripped {checked} rows, expected {expected}")
    return f"{checked:,} randomly drawn rows round-trip exactly (seed {SEED})"


def _event_from_parquet_row(record: dict) -> ConjunctionEvent:
    """Rebuild a ConjunctionEvent from one flat parquet row."""
    def state(index: int) -> ObjectState:
        prefix = f"obj{index}"
        cov = np.array(
            [
                [record[f"{prefix}_c_11"], record[f"{prefix}_c_12"], record[f"{prefix}_c_13"]],
                [record[f"{prefix}_c_12"], record[f"{prefix}_c_22"], record[f"{prefix}_c_23"]],
                [record[f"{prefix}_c_13"], record[f"{prefix}_c_23"], record[f"{prefix}_c_33"]],
            ],
            dtype=np.float64,
        )
        return ObjectState(
            catalog_id=record[f"{prefix}_catalog_id"],
            position_km=(record[f"{prefix}_x"], record[f"{prefix}_y"], record[f"{prefix}_z"]),
            velocity_kms=(record[f"{prefix}_vx"], record[f"{prefix}_vy"], record[f"{prefix}_vz"]),
            local_position_km=(
                record[f"{prefix}_local_x"],
                record[f"{prefix}_local_y"],
                record[f"{prefix}_local_z"],
            ),
            covariance=cov,
            hbr_m=record.get(f"{prefix}_hbr_m"),
            met_criteria=record.get(f"{prefix}_met_criteria"),
            source_filename=record.get(f"{prefix}_source_filename"),
        )

    return ConjunctionEvent(
        event_id=record["event_id"],
        run_id=record["run_id"],
        conj_id=record["conj_id"],
        source=EventSource(record["source"]),
        provenance=record["provenance"],
        tca=record["tca"],
        jdate=record["jdate"],
        miss_distance_km=record["miss_distance_km"],
        relative_speed_kms=record["relative_speed_kms"],
        mahalanobis_distance=record["mahalanobis_distance"],
        dilution=record["dilution"],
        pc=record["pc"],
        pc_is_floored=record["pc_is_floored"],
        object1=state(1),
        object2=state(2),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-checksums", action="store_true")
    args = parser.parse_args()

    checks: list[tuple[str, Callable[[], str]]] = [
        ("parquet row counts = CSV rows - rejects", check_row_counts),
        ("a random parquet row matches its CSV line", check_random_row_matches_csv),
        ("parquet covariances are symmetric and PSD", check_covariances),
        ("pc_is_floored agrees with pc on every row", check_censoring_flag),
        ("HBR matched + unmatched = object slots", check_hbr_totals),
        ("viz sample covers every declared stratum", check_viz_sample),
        (
            "dataset/ checksums still match MANIFEST.md",
            (lambda: "checksums SKIPPED") if args.skip_checksums else check_dataset_unmodified,
        ),
        ("pytest passes", check_pytest),
        ("random 1,000-row schema round-trip (addition)", check_random_round_trip),
    ]

    print(f"Phase 2 verification -- {REPO_ROOT}\n")
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
        print(f"{failures} FAILED -- Phase 2 is not complete.")
        return 1
    print("Phase 2 verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
