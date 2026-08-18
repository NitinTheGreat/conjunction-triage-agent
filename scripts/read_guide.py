"""Extract the text of the TraCSS Conjunction Screening Testset Users Guide.

Phase 1 deliberately left several field semantics uninterpreted (`dilution`, the
`epoch` timezone, the difference between the two IV&V files). This script pulls the
guide's text so those questions can be answered from the source rather than guessed.

``dataset/`` is opened read-only. Output goes to ``processed/users_guide.txt``.

    python scripts/read_guide.py                 # extract to processed/
    python scripts/read_guide.py --search prob   # show context around a term
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import settings  # noqa: E402

GUIDE_FILENAME = "Conjunction_Screening_Testset_Users_Guide.pdf"
OUTPUT_NAME = "users_guide.txt"


def extract_text(pdf_path: Path) -> list[str]:
    """Return the text of each page. Raises if the PDF is missing or yields nothing."""
    from pypdf import PdfReader

    if not pdf_path.is_file():
        raise FileNotFoundError(f"Users Guide not found: {pdf_path}")

    reader = PdfReader(str(pdf_path))
    pages = [(page.extract_text() or "") for page in reader.pages]

    if not pages:
        raise ValueError(f"{pdf_path.name}: no pages found")
    if not any(page.strip() for page in pages):
        raise ValueError(
            f"{pdf_path.name}: extracted zero characters across {len(pages)} pages; "
            "the PDF may be scanned images rather than text"
        )
    return pages


def search(pages: list[str], term: str, context: int = 320) -> list[tuple[int, str]]:
    """Find ``term`` (case-insensitive) and return (page number, surrounding text)."""
    hits: list[tuple[int, str]] = []
    pattern = re.compile(re.escape(term), re.IGNORECASE)
    for number, text in enumerate(pages, start=1):
        for match in pattern.finditer(text):
            start = max(0, match.start() - context // 2)
            end = min(len(text), match.end() + context // 2)
            hits.append((number, text[start:end].replace("\n", " ")))
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--search", help="print context around every match of this term")
    parser.add_argument("--context", type=int, default=320)
    args = parser.parse_args()

    pdf_path = settings.DATASET_DIR / GUIDE_FILENAME
    pages = extract_text(pdf_path)
    total_chars = sum(len(p) for p in pages)

    if args.search:
        hits = search(pages, args.search, args.context)
        print(f"{len(hits)} hit(s) for {args.search!r} in {len(pages)} pages\n")
        for number, snippet in hits:
            print(f"--- p.{number} ---\n{snippet}\n")
        return 0

    settings.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    destination = settings.PROCESSED_DIR / OUTPUT_NAME
    with destination.open("w", encoding="utf-8", newline="\n") as handle:
        for number, text in enumerate(pages, start=1):
            handle.write(f"\n===== PAGE {number} =====\n{text}\n")

    print(f"{len(pages)} pages, {total_chars:,} characters -> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
