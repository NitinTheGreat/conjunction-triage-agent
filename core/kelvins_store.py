"""Read access to the ingested Kelvins CDM series.

Phases 6 and 7 loaded these inside their runner scripts. The API and the MCP server need
the same access, and importing from ``scripts/`` would be a layering inversion, so the
query lives here.

**The 2-day rule is not a parameter.** The task predicts the final risk at TCA from what is
visible at least two days out, so anything closer to TCA is the answer, not evidence.
:func:`load_visible_cdms` applies the cut itself and offers no way to turn it off — a
caller who could pass ``0.0`` would be reading the label while predicting it.

Nothing here is on the Phase 7 frozen manifest; the query it issues is byte-identical to
the one those runners used, and ``tests/test_kelvins_store.py`` holds them together.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from core.config import settings

__all__ = [
    "KelvinsStoreError",
    "VISIBILITY_CUTOFF_DAYS",
    "SPLITS",
    "cdm_path",
    "series_path",
    "load_visible_cdms",
    "load_series",
]

#: CDMs closer to TCA than this are withheld: they are the label, not evidence.
VISIBILITY_CUTOFF_DAYS = 2.0

SPLITS: tuple[str, ...] = ("train", "test")


class KelvinsStoreError(RuntimeError):
    """Raised when the ingested Kelvins store is missing or unusable."""


def _kelvins_dir() -> Path:
    return settings.PROCESSED_DIR / "kelvins"


def _checked(path: Path) -> Path:
    if not path.is_file():
        raise KelvinsStoreError(
            f"{path} is missing; run scripts/ingest_kelvins.py first"
        )
    return path


def cdm_path(split: str) -> Path:
    """Path to one split's CDM table, verified to exist."""
    if split not in SPLITS:
        raise KelvinsStoreError(f"unknown split {split!r}; expected one of {SPLITS}")
    return _checked(_kelvins_dir() / f"cdms_{split}.parquet")


def series_path(split: str) -> Path:
    """Path to one split's per-series table, verified to exist."""
    if split not in SPLITS:
        raise KelvinsStoreError(f"unknown split {split!r}; expected one of {SPLITS}")
    return _checked(_kelvins_dir() / f"series_{split}.parquet")


def _sql_path(path: Path) -> str:
    return str(path).replace("\\", "/").replace("'", "''")


def load_visible_cdms(
    series_ids: list[str], split: str = "test"
) -> dict[str, pd.DataFrame]:
    """The visible CDMs for the given series, grouped by ``series_id``.

    One query for the whole batch rather than one per event, and the result is only the
    requested subset, so nothing approaching the full table becomes resident.
    """
    if not series_ids:
        return {}

    location = _sql_path(cdm_path(split))
    connection = duckdb.connect()
    try:
        connection.execute("set TimeZone = 'UTC'")
        connection.execute("set memory_limit = '2GB'")
        connection.register("wanted", pd.DataFrame({"series_id": series_ids}))
        frame = connection.execute(
            f"""
            select c.* from read_parquet('{location}') c
            join wanted w using (series_id)
            where c.time_to_tca_days >= {VISIBILITY_CUTOFF_DAYS}
            order by c.series_id, c.time_to_tca_days desc
            """
        ).fetchdf()
    finally:
        connection.close()
    return {sid: group for sid, group in frame.groupby("series_id", sort=False)}


def load_series(split: str = "test", limit: int | None = None) -> pd.DataFrame:
    """The per-series summary table for one split."""
    location = _sql_path(series_path(split))
    clause = f" limit {int(limit)}" if limit is not None else ""
    connection = duckdb.connect()
    try:
        connection.execute("set TimeZone = 'UTC'")
        return connection.execute(
            f"select * from read_parquet('{location}'){clause}"
        ).fetchdf()
    finally:
        connection.close()
