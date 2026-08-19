"""Read access to the ingested benchmark, backed by DuckDB.

Why DuckDB rather than ``pyarrow.parquet``: on this host a Windows Application Control
policy blocks pyarrow's ``_parquet`` DLL (it survives a clean reinstall), so
``import pyarrow.parquet`` fails. DuckDB ships its own parquet engine and reads exactly
the same files that ``scripts/ingest.py`` produced, so the stored format is unchanged --
only the reader is.

Queries are pushed down to DuckDB rather than materialised in pandas, which keeps
constraint 1 (never load a full file into memory) satisfied by construction: an
aggregate over 913 k rows streams inside the engine and returns a handful of numbers.

    from core.store import store
    store.count("spherical")
    store.query("select pc from spherical where not pc_is_floored limit 5")
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import duckdb
import pandas as pd

from core.config import settings

__all__ = ["StoreError", "ParquetStore", "store", "SOURCES"]

#: Logical name -> parquet file stem in ``processed/``.
SOURCES: tuple[str, ...] = ("spherical", "sfsh")


class StoreError(RuntimeError):
    """Raised when the ingested store is missing or unusable."""


@dataclass(frozen=True)
class ParquetStore:
    """Thin read-only accessor over the ingested parquet files."""

    directory: Path = settings.PROCESSED_DIR

    # -- paths -------------------------------------------------------------------------

    def path(self, source: str) -> Path:
        """Path to one source's parquet file, verified to exist."""
        if source not in SOURCES:
            raise StoreError(f"unknown source {source!r}; expected one of {SOURCES}")
        path = self.directory / f"{source}.parquet"
        if not path.is_file():
            raise StoreError(f"{path} is missing; run scripts/ingest.py first")
        return path

    def _sql_path(self, source: str) -> str:
        """The file path as a SQL string literal."""
        return str(self.path(source)).replace("\\", "/").replace("'", "''")

    # -- querying ----------------------------------------------------------------------

    def connect(self) -> duckdb.DuckDBPyConnection:
        """A connection with each available source registered as a view."""
        connection = duckdb.connect()
        for source in SOURCES:
            try:
                location = self._sql_path(source)
            except StoreError:
                continue
            connection.execute(
                f"create view {source} as select * from read_parquet('{location}')"
            )
        return connection

    def query(self, sql: str, parameters: Any = None) -> pd.DataFrame:
        """Run a query against the registered views and return a DataFrame."""
        connection = self.connect()
        try:
            relation = connection.execute(sql, parameters) if parameters else connection.execute(sql)
            return relation.fetchdf()
        finally:
            connection.close()

    def scalar(self, sql: str) -> Any:
        """Run a query expected to return exactly one value."""
        connection = self.connect()
        try:
            row = connection.execute(sql).fetchone()
        finally:
            connection.close()
        if row is None:
            raise StoreError(f"query returned no rows: {sql}")
        return row[0]

    # -- convenience -------------------------------------------------------------------

    def count(self, source: str) -> int:
        """Row count of one source."""
        return int(self.scalar(f"select count(*) from {source}"))

    def total_count(self) -> int:
        """Row count across every available source."""
        return sum(self.count(s) for s in self.available())

    def available(self) -> list[str]:
        """Sources whose parquet file is present."""
        found = []
        for source in SOURCES:
            try:
                self.path(source)
            except StoreError:
                continue
            found.append(source)
        if not found:
            raise StoreError(
                f"no ingested parquet files in {self.directory}; run scripts/ingest.py"
            )
        return found

    def columns(self, source: str) -> list[str]:
        """Column names of one source."""
        return list(self.query(f"select * from {source} limit 0").columns)

    def iter_batches(
        self, source: str, columns: str = "*", batch_size: int = 100_000
    ) -> Iterator[pd.DataFrame]:
        """Stream a source in batches, for the rare case that needs row-level Python."""
        total = self.count(source)
        for offset in range(0, total, batch_size):
            yield self.query(
                f"select {columns} from {source} limit {batch_size} offset {offset}"
            )


#: Shared instance.
store = ParquetStore()
