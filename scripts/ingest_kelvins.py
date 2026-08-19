"""Chunked ingestion of the ESA Kelvins dataset into parquet.

Every CDM is converted through :func:`conjunction_event_from_kelvins_row` and validated;
every event's CDMs are assembled into a :class:`ConjunctionEventSeries`, which validates
the ordering. A row failing either is written to ``processed/kelvins/rejects_<split>.csv``
with its source line and the exact error — never dropped silently.

Two outputs per split:

* ``cdms_<split>.parquet``   — one row per CDM, flat, in canonical-schema terms.
* ``series_<split>.parquet`` — one row per event: the label, CDM count, and the
  event-level features that only exist across a sequence.

Reading is chunked by event so a whole split is never resident. ``dataset/`` is read-only.

    python scripts/ingest_kelvins.py
    python scripts/ingest_kelvins.py --split train --limit 500
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any, Iterator

import duckdb
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import settings  # noqa: E402
from core.schema import (  # noqa: E402
    KELVINS_PC_FLOOR,
    ConjunctionEventSeries,
    EventSource,
    SchemaValidationError,
    conjunction_event_from_kelvins_row,
)

KELVINS_DIR = "kelvins"
#: split -> (csv filename, filename holding the withheld label or None)
SPLITS: dict[str, tuple[str, str | None]] = {
    "train": ("train_data.csv", None),
    "test": ("test_data.csv", "test_data_private.csv"),
}

#: Events per chunk. A Kelvins event is at most 23 CDMs, so 2,000 events is ~46k rows.
EVENTS_PER_CHUNK = 2_000

#: Cap on DuckDB's working set during ingestion, so a split is streamed rather than
#: held whole. Python itself only ever holds one chunk of events.
DUCKDB_MEMORY_LIMIT = "512MB"

#: log10(Pc) floor. Kelvins clamps `risk` at exactly this value.
RISK_FLOOR_LOG10 = -30.0

CDM_SCHEMA = pa.schema([
    ("series_id", pa.string()),
    ("split", pa.string()),
    ("kelvins_event_id", pa.int64()),
    ("cdm_index", pa.int32()),
    ("source_line", pa.int64()),
    ("source", pa.string()),
    ("provenance", pa.string()),
    ("time_to_tca_days", pa.float64()),
    ("miss_distance_km", pa.float64()),
    ("relative_speed_kms", pa.float64()),
    ("mahalanobis_distance", pa.float64()),
    ("pc", pa.float64()),
    ("risk_log10", pa.float64()),
    ("pc_is_floored", pa.bool_()),
    ("max_risk_estimate", pa.float64()),
    ("max_risk_scaling", pa.float64()),
    ("dilution_derived", pa.int32()),
    ("mission_id", pa.string()),
    ("c_object_type", pa.string()),
    ("F10", pa.float64()), ("AP", pa.float64()),
    ("F3M", pa.float64()), ("SSN", pa.float64()),
] + [
    field
    for prefix, label in (("t", "target"), ("c", "chaser"))
    for field in [
        (f"{label}_span_m", pa.float64()),
        (f"{label}_c_11", pa.float64()), (f"{label}_c_12", pa.float64()),
        (f"{label}_c_13", pa.float64()), (f"{label}_c_22", pa.float64()),
        (f"{label}_c_23", pa.float64()), (f"{label}_c_33", pa.float64()),
        (f"{label}_sigma_max_km", pa.float64()),
    ]
])

SERIES_SCHEMA = pa.schema([
    ("series_id", pa.string()),
    ("split", pa.string()),
    ("kelvins_event_id", pa.int64()),
    ("source", pa.string()),
    ("provenance", pa.string()),
    ("cdm_count", pa.int32()),
    ("final_risk_log10", pa.float64()),
    ("final_pc", pa.float64()),
    ("final_risk_is_floored", pa.bool_()),
    ("label_is_withheld", pa.bool_()),
    ("first_time_to_tca_days", pa.float64()),
    ("last_time_to_tca_days", pa.float64()),
    ("final_miss_distance_km", pa.float64()),
    ("final_relative_speed_kms", pa.float64()),
    ("mission_id", pa.string()),
    ("c_object_type", pa.string()),
    ("any_diluted", pa.bool_()),
])


def sql_path(name: str) -> str:
    path = settings.DATASET_DIR / KELVINS_DIR / name
    if not path.is_file():
        raise FileNotFoundError(f"{path}; run scripts/fetch_kelvins.py first")
    return str(path).replace("\\", "/").replace("'", "''")


def _f(value: Any) -> float | None:
    """Coerce to a plain float, mapping NaN/None to None for parquet nullability."""
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(out) else out


def derived_dilution(max_risk_scaling: float | None) -> int | None:
    """A dilution-equivalent signal derived from ``max_risk_scaling``.

    TraCSS publishes ``dilution`` directly: 1 when the covariance is on the diluted side
    of the Pc-versus-scale-factor curve. Kelvins does not publish that flag, but it does
    publish ``max_risk_scaling`` — the factor the covariance must be scaled by to reach
    maximum Pc. A factor **above 1** means the covariance must be *inflated* to reach the
    peak, so the record sits on the robust side; a factor **at or below 1** means the peak
    lies at or below the current covariance, i.e. it is already diluted.

    This is a derivation, not a published flag, and is named ``dilution_derived`` so it is
    never mistaken for the TraCSS ground-truth column.
    """
    if max_risk_scaling is None:
        return None
    return 0 if max_risk_scaling > 1.0 else 1


def _sigma_max_km(covariance) -> float | None:
    if covariance is None:
        return None
    return float(np.sqrt(np.linalg.eigvalsh(covariance)[-1]))


def iter_event_chunks(
    connection: duckdb.DuckDBPyConnection, view: str, limit: int | None
) -> Iterator[list[dict[str, Any]]]:
    """Yield chunks of rows grouped so no event is ever split across chunks."""
    ids = [
        int(r[0])
        for r in connection.execute(
            f"select distinct event_id from {view} order by event_id"
        ).fetchall()
    ]
    if limit:
        ids = ids[:limit]

    for start in range(0, len(ids), EVENTS_PER_CHUNK):
        block = ids[start:start + EVENTS_PER_CHUNK]
        low, high = block[0], block[-1]
        frame = connection.execute(
            f"select * from {view} "
            f"where event_id between {low} and {high} "
            f"order by event_id, time_to_tca desc"
        ).fetchdf()
        yield frame.to_dict(orient="records")


def ingest_split(split: str, limit: int | None = None) -> dict[str, Any]:
    """Ingest one split into CDM-level and series-level parquet."""
    filename, label_filename = SPLITS[split]
    out_dir = settings.PROCESSED_DIR / KELVINS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    connection = duckdb.connect()
    connection.execute("set TimeZone = 'UTC'")
    # Cap DuckDB's working set so it streams and spills rather than holding the split
    # in memory. CSV reads expose no rowid, so a row number is materialised here to give
    # every reject an exact source line.
    connection.execute(f"set memory_limit = '{DUCKDB_MEMORY_LIMIT}'")
    connection.execute(
        f"create table src as select *, row_number() over () as _rowid "
        f"from read_csv_auto('{sql_path(filename)}')"
    )

    labels: dict[int, float] = {}
    if label_filename:
        connection.execute(
            f"create view lbl as select * from read_csv_auto('{sql_path(label_filename)}')"
        )
        labels = {
            int(e): float(r)
            for e, r in connection.execute(
                "select event_id, true_risk from lbl"
            ).fetchall()
        }

    started = time.perf_counter()
    cdm_rows: list[dict[str, Any]] = []
    series_rows: list[dict[str, Any]] = []
    rejects: list[dict[str, Any]] = []
    rows_in = 0
    series_seen = 0

    for chunk in iter_event_chunks(connection, "src", limit):
        grouped: dict[int, list[dict[str, Any]]] = {}
        for row in chunk:
            grouped.setdefault(int(row["event_id"]), []).append(row)

        for event_id, raw_rows in grouped.items():
            rows_in += len(raw_rows)
            series_id = f"{split}:{event_id}"
            events = []
            local_rejects = 0

            for index, raw in enumerate(raw_rows):
                line = int(raw.get("_rowid", -1)) + 2  # +1 for 0-based, +1 for header
                try:
                    event = conjunction_event_from_kelvins_row(raw, filename, series_id)
                    event.validate()
                except SchemaValidationError as exc:
                    rejects.append({
                        "split": split,
                        "series_id": series_id,
                        "kelvins_event_id": event_id,
                        "cdm_index": index,
                        "source_line": line,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    })
                    local_rejects += 1
                    continue
                events.append((event, raw, line, index))

            if not events:
                continue

            series = ConjunctionEventSeries(
                series_id=series_id,
                source=EventSource.KELVINS,
                provenance=filename,
                split=split,
                events=[e for e, _, _, _ in events],
                mission_id=str(events[0][1].get("mission_id")),
            )

            withheld = label_filename is not None
            if withheld:
                final_risk = labels.get(event_id)
            else:
                final_risk = _f(events[-1][1].get("risk"))
            series.final_risk_log10 = final_risk
            series.final_risk_is_floored = (
                final_risk is not None and final_risk <= RISK_FLOOR_LOG10
            )

            try:
                series.validate()
            except SchemaValidationError as exc:
                rejects.append({
                    "split": split, "series_id": series_id,
                    "kelvins_event_id": event_id, "cdm_index": -1,
                    "source_line": events[0][2],
                    "error_type": type(exc).__name__, "error": str(exc),
                })
                continue

            series_seen += 1
            any_diluted = False

            # cdm_index is renumbered densely over the CDMs actually stored. Taking it
            # from the pre-rejection position would leave gaps wherever a CDM was
            # rejected, so the index would no longer address the stored series.
            # `source_line` preserves traceability back to the original row.
            for index, (event, raw, line, _source_index) in enumerate(events):
                scaling = _f(raw.get("max_risk_scaling"))
                dilution = derived_dilution(scaling)
                any_diluted = any_diluted or dilution == 1
                record: dict[str, Any] = {
                    "series_id": series_id,
                    "split": split,
                    "kelvins_event_id": event_id,
                    "cdm_index": index,
                    "source_line": line,
                    "source": event.source.value,
                    "provenance": event.provenance,
                    "time_to_tca_days": event.time_to_tca_days,
                    "miss_distance_km": event.miss_distance_km,
                    "relative_speed_kms": event.relative_speed_kms,
                    "mahalanobis_distance": event.mahalanobis_distance,
                    "pc": event.pc,
                    "risk_log10": _f(raw.get("risk")),
                    "pc_is_floored": event.pc_is_floored,
                    "max_risk_estimate": _f(raw.get("max_risk_estimate")),
                    "max_risk_scaling": scaling,
                    "dilution_derived": dilution,
                    "mission_id": str(raw.get("mission_id")),
                    "c_object_type": raw.get("c_object_type"),
                    "F10": _f(raw.get("F10")), "AP": _f(raw.get("AP")),
                    "F3M": _f(raw.get("F3M")), "SSN": _f(raw.get("SSN")),
                }
                for state, label in ((event.object1, "target"), (event.object2, "chaser")):
                    cov = state.covariance
                    record[f"{label}_span_m"] = state.hbr_m
                    for name, (i, j) in {
                        "c_11": (0, 0), "c_12": (0, 1), "c_13": (0, 2),
                        "c_22": (1, 1), "c_23": (1, 2), "c_33": (2, 2),
                    }.items():
                        record[f"{label}_{name}"] = None if cov is None else float(cov[i, j])
                    record[f"{label}_sigma_max_km"] = _sigma_max_km(cov)
                cdm_rows.append(record)

            final_event = series.final_event
            series_rows.append({
                "series_id": series_id,
                "split": split,
                "kelvins_event_id": event_id,
                "source": EventSource.KELVINS.value,
                "provenance": filename,
                "cdm_count": series.cdm_count,
                "final_risk_log10": final_risk,
                "final_pc": None if final_risk is None else 10.0 ** final_risk,
                "final_risk_is_floored": series.final_risk_is_floored,
                "label_is_withheld": withheld,
                "first_time_to_tca_days": series.events[0].time_to_tca_days,
                "last_time_to_tca_days": final_event.time_to_tca_days,
                "final_miss_distance_km": final_event.miss_distance_km,
                "final_relative_speed_kms": final_event.relative_speed_kms,
                "mission_id": series.mission_id,
                "c_object_type": events[-1][1].get("c_object_type"),
                "any_diluted": any_diluted,
            })

    connection.close()

    cdm_path = out_dir / f"cdms_{split}.parquet"
    series_path = out_dir / f"series_{split}.parquet"
    pq.write_table(
        pa.Table.from_pylist(cdm_rows, schema=CDM_SCHEMA), cdm_path, compression="zstd"
    )
    pq.write_table(
        pa.Table.from_pylist(series_rows, schema=SERIES_SCHEMA), series_path,
        compression="zstd",
    )

    rejects_path = out_dir / f"rejects_{split}.csv"
    if rejects:
        with rejects_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rejects[0]))
            writer.writeheader()
            writer.writerows(rejects)
    elif rejects_path.exists():
        rejects_path.unlink()

    cdm_rejects = sum(1 for r in rejects if r["cdm_index"] >= 0)
    if len(cdm_rows) + cdm_rejects != rows_in:
        raise RuntimeError(
            f"{split}: {rows_in} rows read but {len(cdm_rows)} kept + {cdm_rejects} "
            "rejected — rows have been lost; refusing to report success"
        )

    return {
        "split": split,
        "csv": filename,
        "rows_in": rows_in,
        "cdms_out": len(cdm_rows),
        "series_out": len(series_rows),
        "rejected": len(rejects),
        "cdm_rejects": cdm_rejects,
        "series_rejects": len(rejects) - cdm_rejects,
        "label_source": label_filename or "final CDM of each series",
        "cdm_parquet_bytes": cdm_path.stat().st_size,
        "series_parquet_bytes": series_path.stat().st_size,
        "elapsed_seconds": round(time.perf_counter() - started, 1),
        "events_per_chunk": EVENTS_PER_CHUNK,
    }


def _peak_memory_mb() -> float:
    import psutil

    info = psutil.Process().memory_info()
    return getattr(info, "peak_wset", info.rss) / 1024**2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=sorted(SPLITS))
    parser.add_argument("--limit", type=int, help="only the first N events")
    args = parser.parse_args()

    splits = [args.split] if args.split else list(SPLITS)
    summaries = []
    for split in splits:
        print(f"ingesting {split} ...", flush=True)
        summary = ingest_split(split, args.limit)
        summaries.append(summary)
        print(
            f"  {summary['rows_in']:,} CDMs -> {summary['cdms_out']:,} kept, "
            f"{summary['series_out']:,} series, {summary['rejected']:,} rejected "
            f"in {summary['elapsed_seconds']}s",
            flush=True,
        )

    report = {
        "pc_floor": KELVINS_PC_FLOOR,
        "risk_floor_log10": RISK_FLOOR_LOG10,
        "peak_memory_mb": round(_peak_memory_mb(), 1),
        "splits": summaries,
    }
    destination = settings.PROCESSED_DIR / KELVINS_DIR / "ingest_report.json"
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\npeak memory {report['peak_memory_mb']} MB -> {destination}")

    if sum(s["rejected"] for s in summaries) == 0:
        print(
            "\nNOTE: zero rejects. That is suspicious rather than reassuring — confirm "
            "validate() is actually being exercised before reporting it."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
