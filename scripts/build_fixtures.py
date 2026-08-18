"""Regenerate the offline test fixtures from the benchmark CSVs.

Copies the header plus the first N data rows of each IV&V file into ``tests/fixtures/``
so the test suite runs on any machine, offline, in milliseconds, without touching the
620 MB dataset.

Lines are copied **verbatim as text** rather than round-tripped through pandas, so the
original numeric literals are preserved exactly and no float reformatting can silently
change a value.

``dataset/`` is opened read-only and is never modified. Run from the repo root::

    python scripts/build_fixtures.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import settings  # noqa: E402

#: Rows of real data to keep in each fixture. Enough to exercise parsing and to contain
#: both floored and unfloored `prob` values; small enough to commit.
N_ROWS = 50

#: source filename in dataset/ -> fixture filename in tests/fixtures/
FILES = {
    "IVV_Releasable_Dataset_Spherical_DefaultHBR.csv": "ivv_spherical_head50.csv",
    "IVV_Releasable_Dataset_SFSH_DiscreteHBR.csv": "ivv_sfsh_head50.csv",
}


def extract_head(source: Path, destination: Path, n_rows: int = N_ROWS) -> int:
    """Copy ``source``'s header plus its first ``n_rows`` data lines to ``destination``.

    Reads lazily line by line -- the source file is never loaded into memory. Returns
    the number of data rows written. Raises if the source is short or malformed.
    """
    if not source.is_file():
        raise FileNotFoundError(f"benchmark file not found: {source}")

    lines: list[str] = []
    with source.open("r", encoding="utf-8", newline="") as handle:
        for line in handle:
            lines.append(line.rstrip("\r\n"))
            if len(lines) > n_rows:  # header + n_rows
                break

    if len(lines) < 2:
        raise ValueError(f"{source.name}: fewer than 2 lines; cannot build a fixture")

    header_columns = lines[0].split(",")
    for offset, row in enumerate(lines[1:], start=1):
        found = len(row.split(","))
        if found != len(header_columns):
            raise ValueError(
                f"{source.name} line {offset + 1}: {found} fields, "
                f"header has {len(header_columns)}"
            )

    destination.parent.mkdir(parents=True, exist_ok=True)
    # Explicit "\n": the default on Windows would be CRLF, making the committed
    # fixtures differ byte-wise from those generated on Linux.
    with destination.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")

    return len(lines) - 1


def main() -> int:
    fixtures_dir = settings.FIXTURES_DIR
    for source_name, fixture_name in FILES.items():
        written = extract_head(
            settings.DATASET_DIR / source_name, fixtures_dir / fixture_name
        )
        print(f"{fixture_name}: {written} data rows from {source_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
