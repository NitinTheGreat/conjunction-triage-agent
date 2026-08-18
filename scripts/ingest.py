"""Chunked ingestion of the IV&V benchmark CSVs into parquet.

Every row is converted through :meth:`ConjunctionEvent.from_ivv_row` and then
:meth:`validate`. A row that fails either is written to
``processed/rejects_<source>.csv`` with its CSV line number and the exact error message
-- never dropped silently.

Covariances are stored as six flat columns per object rather than serialised arrays:
parquet handles flat numeric columns far better, and `core.schema` already knows how to
rebuild the symmetric 3x3 from them.

The source CSVs are opened read-only and never modified.

**Idempotent and resumable.** Each chunk is written to a staging part file; a re-run
skips parts that already exist and then rewrites the single output file from the parts.
Re-running therefore cannot duplicate rows.

    python scripts/ingest.py                 # ingest both files
    python scripts/ingest.py --source sfsh   # just one
    python scripts/ingest.py --force         # discard staging and start over
    python scripts/ingest.py --limit 5000    # smoke test on the first N rows
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Iterator

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import settings  # noqa: E402
from core.schema import (  # noqa: E402
    ConjunctionEvent,
    EventSource,
    SchemaValidationError,
)

#: Rows per chunk. Small enough that a chunk plus its converted events stays well under
#: a few hundred MB; large enough that per-chunk pandas overhead stays negligible.
CHUNK_SIZE = 50_000

SOURCES: dict[str, tuple[str, EventSource]] = {
    "spherical": (
        "IVV_Releasable_Dataset_Spherical_DefaultHBR.csv",
        EventSource.TRACSS_SPHERICAL,
    ),
    "sfsh": (
        "IVV_Releasable_Dataset_SFSH_DiscreteHBR.csv",
        EventSource.TRACSS_SFSH,
    ),
}

#: Explicit dtypes. Two real hazards this closes:
#:  * chunk-to-chunk drift -- `dilution` was observed parsing as int64 in chunks with no
#:    NULLs and float64 in chunks with them;
#:  * silent identifier corruption -- if any chunk of `obj1`/`conj_id` inferred float64,
#:    `str(value)` would yield "59208.0" instead of "59208".
#: Identifier columns are int64 (verified null-free across both full files); every other
#: numeric column is float64 so a NULL becomes NaN and is rejected per-row rather than
#: aborting the whole run.
ID_COLUMNS = ["run_id", "conj_id", "obj1", "obj2"]
TEXT_COLUMNS = ["epoch", "obj1_filename", "obj2_filename"]
FLOAT_COLUMNS = [
    "met_criteria1", "met_criteria2", "min_range", "Vrel", "prob", "dilution",
    "mdistance", "jdate",
    *[f"{axis}{i}" for i in (1, 2) for axis in ("x", "y", "z")],
    *[f"v{axis}{i}" for i in (1, 2) for axis in ("x", "y", "z")],
    *[f"local_{axis}{i}" for i in (1, 2) for axis in ("x", "y", "z")],
    *[f"c{i}_{e}" for i in (1, 2) for e in ("11", "12", "13", "22", "23", "33")],
]
DTYPES: dict[str, Any] = (
    {c: "int64" for c in ID_COLUMNS}
    | {c: "float64" for c in FLOAT_COLUMNS}
    | {c: "string" for c in TEXT_COLUMNS}
)

COVARIANCE_ELEMENTS = ("11", "12", "13", "22", "23", "33")

PARQUET_SCHEMA = pa.schema(
    [
        ("event_id", pa.string()),
        ("run_id", pa.int64()),
        ("conj_id", pa.string()),
        ("source", pa.string()),
        ("provenance", pa.string()),
        ("source_line", pa.int64()),
        ("tca", pa.timestamp("us", tz="UTC")),
        ("jdate", pa.float64()),
        ("miss_distance_km", pa.float64()),
        ("relative_speed_kms", pa.float64()),
        ("mahalanobis_distance", pa.float64()),
        ("dilution", pa.float64()),
        ("pc", pa.float64()),
        ("pc_is_floored", pa.bool_()),
    ]
    + [
        field
        for i in (1, 2)
        for field in [
            (f"obj{i}_catalog_id", pa.string()),
            (f"obj{i}_x", pa.float64()),
            (f"obj{i}_y", pa.float64()),
            (f"obj{i}_z", pa.float64()),
            (f"obj{i}_vx", pa.float64()),
            (f"obj{i}_vy", pa.float64()),
            (f"obj{i}_vz", pa.float64()),
            (f"obj{i}_local_x", pa.float64()),
            (f"obj{i}_local_y", pa.float64()),
            (f"obj{i}_local_z", pa.float64()),
            *[(f"obj{i}_c_{e}", pa.float64()) for e in COVARIANCE_ELEMENTS],
            (f"obj{i}_hbr_m", pa.float64()),
            (f"obj{i}_met_criteria", pa.bool_()),
            (f"obj{i}_source_filename", pa.string()),
        ]
    ]
)


def event_to_row(event: ConjunctionEvent, source_line: int) -> dict[str, Any]:
    """Flatten an event into one parquet row, covariances as six columns per object."""
    row: dict[str, Any] = {
        "event_id": event.event_id,
        "run_id": event.run_id,
        "conj_id": event.conj_id,
        "source": event.source.value,
        "provenance": event.provenance,
        "source_line": source_line,
        "tca": event.tca,
        "jdate": event.jdate,
        "miss_distance_km": event.miss_distance_km,
        "relative_speed_kms": event.relative_speed_kms,
        "mahalanobis_distance": event.mahalanobis_distance,
        "dilution": event.dilution,
        "pc": event.pc,
        "pc_is_floored": event.pc_is_floored,
    }
    for index, state in ((1, event.object1), (2, event.object2)):
        prefix = f"obj{index}"
        row[f"{prefix}_catalog_id"] = state.catalog_id
        for axis, value in zip("xyz", state.position_km or (None,) * 3):
            row[f"{prefix}_{axis}"] = value
        for axis, value in zip("xyz", state.velocity_kms or (None,) * 3):
            row[f"{prefix}_v{axis}"] = value
        for axis, value in zip("xyz", state.local_position_km or (None,) * 3):
            row[f"{prefix}_local_{axis}"] = value
        cov = state.covariance
        upper = {
            "11": (0, 0), "12": (0, 1), "13": (0, 2),
            "22": (1, 1), "23": (1, 2), "33": (2, 2),
        }
        for element, (i, j) in upper.items():
            row[f"{prefix}_c_{element}"] = None if cov is None else float(cov[i, j])
        row[f"{prefix}_hbr_m"] = state.hbr_m
        row[f"{prefix}_met_criteria"] = state.met_criteria
        row[f"{prefix}_source_filename"] = state.source_filename
    return row


def iter_chunks(path: Path, limit: int | None) -> Iterator[pd.DataFrame]:
    """Yield chunks of the CSV with explicit dtypes. The file is never read whole."""
    reader = pd.read_csv(path, dtype=DTYPES, chunksize=CHUNK_SIZE, nrows=limit)
    yield from reader


def ingest_source(
    key: str, force: bool = False, limit: int | None = None
) -> dict[str, Any]:
    """Convert one CSV to parquet, logging every rejected row. Returns a summary."""
    filename, source = SOURCES[key]
    csv_path = settings.DATASET_DIR / filename
    if not csv_path.is_file():
        raise FileNotFoundError(csv_path)

    settings.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    staging = settings.PROCESSED_DIR / f"_staging_{key}"
    if force and staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=True)

    output = settings.PROCESSED_DIR / f"{key}.parquet"
    rejects_path = settings.PROCESSED_DIR / f"rejects_{key}.csv"
    reject_rows: list[dict[str, Any]] = []

    started = time.perf_counter()
    rows_in = rows_out = 0
    # CSV line numbers are 1-based and include the header, so the first data row is 2.
    line = 2

    for index, chunk in enumerate(iter_chunks(csv_path, limit)):
        part = staging / f"part_{index:05d}.parquet"
        chunk_start_line = line
        line += len(chunk)
        rows_in += len(chunk)

        # Rejects are persisted next to their part. Without this, a resumed run would
        # skip the part and silently lose its rejects, under-reporting the reject count
        # and breaking the rows_in = rows_out + rejected identity.
        part_rejects = part.with_suffix(".rejects.json")

        if part.exists() and part_rejects.exists() and not force:
            rows_out += pq.ParquetFile(part).metadata.num_rows
            reject_rows.extend(json.loads(part_rejects.read_text(encoding="utf-8")))
            print(f"  [{key}] part {index:05d} exists, skipping", flush=True)
            continue

        records: list[dict[str, Any]] = []
        chunk_rejects: list[dict[str, Any]] = []
        for offset, raw in enumerate(chunk.to_dict(orient="records")):
            source_line = chunk_start_line + offset
            try:
                event = ConjunctionEvent.from_ivv_row(
                    raw, source, provenance=f"{filename}#L{source_line}"
                )
                event.validate()
            except SchemaValidationError as exc:
                chunk_rejects.append(
                    {
                        "source_line": source_line,
                        "conj_id": int(raw["conj_id"]),
                        "obj1": int(raw["obj1"]),
                        "obj2": int(raw["obj2"]),
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
                continue
            records.append(event_to_row(event, source_line))

        table = pa.Table.from_pylist(records, schema=PARQUET_SCHEMA)
        # Write to a temp name then rename, so an interrupted run never leaves a
        # half-written part that a resume would mistake for complete. The rejects land
        # first, so a part file always implies its rejects are already on disk.
        part_rejects.write_text(json.dumps(chunk_rejects), encoding="utf-8")
        temp = part.with_suffix(".parquet.tmp")
        pq.write_table(table, temp, compression="zstd")
        temp.replace(part)
        reject_rows.extend(chunk_rejects)
        rows_out += len(records)

        print(
            f"  [{key}] part {index:05d}: {rows_in:,} read, {rows_out:,} kept, "
            f"{len(reject_rows):,} rejected",
            flush=True,
        )

    # Stream the parts into one file, one row group at a time -- never all in memory.
    parts = sorted(staging.glob("part_*.parquet"))
    if not parts:
        raise RuntimeError(f"{key}: no parts were produced")
    temp_output = output.with_suffix(".parquet.tmp")
    writer = pq.ParquetWriter(temp_output, PARQUET_SCHEMA, compression="zstd")
    try:
        for part in parts:
            writer.write_table(pq.read_table(part, schema=PARQUET_SCHEMA))
    finally:
        writer.close()
    temp_output.replace(output)

    if reject_rows:
        with rejects_path.open("w", encoding="utf-8", newline="") as handle:
            fieldnames = ["source_line", "conj_id", "obj1", "obj2", "error_type", "error"]
            writer_csv = csv.DictWriter(handle, fieldnames=fieldnames)
            writer_csv.writeheader()
            writer_csv.writerows(reject_rows)
    elif rejects_path.exists():
        rejects_path.unlink()

    shutil.rmtree(staging, ignore_errors=True)

    elapsed = time.perf_counter() - started

    if rows_out + len(reject_rows) != rows_in:
        raise RuntimeError(
            f"{key}: {rows_in} rows read but {rows_out} kept + {len(reject_rows)} "
            "rejected -- rows have been lost; refusing to report success"
        )

    return {
        "source": key,
        "csv": filename,
        "rows_in": rows_in,
        "rows_out": rows_out,
        "rejected": len(reject_rows),
        "reject_rate_pct": round(100 * len(reject_rows) / max(rows_in, 1), 6),
        "parquet": str(output.relative_to(settings.repo_root)),
        "parquet_bytes": output.stat().st_size,
        "elapsed_seconds": round(elapsed, 1),
        "chunk_size": CHUNK_SIZE,
    }


def _peak_memory_mb() -> float:
    import psutil

    info = psutil.Process().memory_info()
    return getattr(info, "peak_wset", info.rss) / 1024**2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=sorted(SOURCES), help="ingest only this one")
    parser.add_argument("--force", action="store_true", help="discard staging parts")
    parser.add_argument("--limit", type=int, help="only the first N rows (smoke test)")
    args = parser.parse_args()

    keys = [args.source] if args.source else list(SOURCES)
    summaries = []
    for key in keys:
        print(f"ingesting {key} ...", flush=True)
        summary = ingest_source(key, force=args.force, limit=args.limit)
        summaries.append(summary)
        print(
            f"  done: {summary['rows_out']:,} rows -> {summary['parquet']} "
            f"({summary['parquet_bytes'] / 1024**2:.1f} MB) in "
            f"{summary['elapsed_seconds']}s, {summary['rejected']:,} rejected",
            flush=True,
        )

    report = {
        "chunk_size": CHUNK_SIZE,
        "peak_memory_mb": round(_peak_memory_mb(), 1),
        "sources": summaries,
    }
    destination = settings.PROCESSED_DIR / "ingest_report.json"
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\npeak memory {report['peak_memory_mb']} MB -> {destination}")

    total_rejected = sum(s["rejected"] for s in summaries)
    if total_rejected == 0:
        print(
            "\nWARNING: zero rejects across the whole dataset. That is suspicious "
            "rather than reassuring -- verify validate() is actually being called."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
