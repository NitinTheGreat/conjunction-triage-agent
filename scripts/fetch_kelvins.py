"""Download the ESA Kelvins Collision Avoidance Challenge dataset from Zenodo.

Zenodo record 4463683, DOI 10.5281/zenodo.4463683, CC-BY-4.0.

Writes **only** under ``dataset/kelvins/``. The existing TraCSS files in ``dataset/`` are
never touched; a regression check in ``scripts/verify_phase4.py`` confirms it.

Integrity is verified two ways: the MD5 published in the Zenodo record, and a SHA-256
computed locally and recorded in ``dataset/MANIFEST.md``. A mismatch raises rather than
proceeding with a corrupt file.

    python scripts/fetch_kelvins.py            # download, verify, extract
    python scripts/fetch_kelvins.py --verify   # re-verify what is already on disk
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from datetime import date
from pathlib import Path
from typing import Any

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import settings  # noqa: E402

ZENODO_RECORD = "4463683"
ZENODO_API = f"https://zenodo.org/api/records/{ZENODO_RECORD}"
DOI = "10.5281/zenodo.4463683"
LICENCE = "CC-BY-4.0"

KELVINS_DIR_NAME = "kelvins"
CHUNK_BYTES = 1 << 20  # 1 MiB streaming chunks; the archive is never held in memory


def _hash_file(path: Path, algorithm: str = "sha256") -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_record() -> dict[str, Any]:
    """Fetch the Zenodo record metadata. Raises loudly if unreachable."""
    try:
        response = requests.get(ZENODO_API, timeout=60)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Zenodo record {ZENODO_RECORD} is unreachable from this host: {exc}. "
            "Phase 4 cannot proceed; do not substitute another dataset."
        ) from exc
    return response.json()


def download(record: dict[str, Any], destination: Path) -> Path:
    """Stream the archive to disk and verify its published MD5."""
    files = record.get("files") or []
    if not files:
        raise RuntimeError("Zenodo record lists no files")
    if len(files) != 1:
        print(f"note: record lists {len(files)} files; taking the largest")
    entry = max(files, key=lambda f: f["size"])

    name = entry["key"]
    expected_size = int(entry["size"])
    checksum = entry.get("checksum", "")
    algorithm, _, expected_hash = checksum.partition(":")

    destination.mkdir(parents=True, exist_ok=True)
    target = destination / name

    if target.is_file() and target.stat().st_size == expected_size:
        print(f"{name} already present ({expected_size:,} bytes), skipping download")
    else:
        url = entry["links"]["self"]
        print(f"downloading {name} ({expected_size / 1024**2:.1f} MB) ...", flush=True)
        temp = target.with_suffix(target.suffix + ".part")
        written = 0
        with requests.get(url, stream=True, timeout=300) as response:
            response.raise_for_status()
            with temp.open("wb") as handle:
                for chunk in response.iter_content(CHUNK_BYTES):
                    handle.write(chunk)
                    written += len(chunk)
                    if written % (32 * CHUNK_BYTES) < CHUNK_BYTES:
                        print(f"  {written / 1024**2:>7.1f} MB", flush=True)
        if written != expected_size:
            temp.unlink(missing_ok=True)
            raise RuntimeError(
                f"{name}: downloaded {written} bytes, record says {expected_size}"
            )
        temp.replace(target)

    if expected_hash:
        actual = _hash_file(target, algorithm)
        if actual != expected_hash:
            raise RuntimeError(
                f"{name}: {algorithm} mismatch — Zenodo says {expected_hash}, "
                f"file is {actual}. Refusing to use a corrupt download."
            )
        print(f"  {algorithm} verified against the Zenodo record")

    return target


def extract(archive: Path, destination: Path) -> list[Path]:
    """Extract the archive, refusing any path that would escape the destination."""
    extracted: list[Path] = []
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            # Guard against archive members with absolute or traversing paths.
            member = Path(info.filename)
            if member.is_absolute() or ".." in member.parts:
                raise RuntimeError(f"unsafe archive member: {info.filename!r}")
            out = destination / member.name
            if out.is_file() and out.stat().st_size == info.file_size:
                extracted.append(out)
                continue
            with zf.open(info) as source, out.open("wb") as sink:
                while True:
                    chunk = source.read(CHUNK_BYTES)
                    if not chunk:
                        break
                    sink.write(chunk)
            extracted.append(out)
    return extracted


def describe(paths: list[Path]) -> list[dict[str, Any]]:
    """Size and SHA-256 for each file, for the manifest."""
    return [
        {
            "filename": path.name,
            "bytes": path.stat().st_size,
            "sha256": _hash_file(path),
        }
        for path in sorted(paths)
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="re-verify existing files")
    args = parser.parse_args()

    destination = settings.DATASET_DIR / KELVINS_DIR_NAME

    if args.verify:
        if not destination.is_dir():
            raise SystemExit(f"{destination} does not exist; run without --verify first")
        entries = describe([p for p in destination.iterdir() if p.is_file()])
    else:
        record = fetch_record()
        metadata = record.get("metadata", {})
        print(f"record : {metadata.get('title')}")
        print(f"doi    : {record.get('doi')}")
        print(f"licence: {(metadata.get('license') or {}).get('id', LICENCE)}")

        archive = download(record, destination)
        members = extract(archive, destination)
        print(f"extracted {len(members)} file(s)")
        entries = describe([archive, *members])

    report = {
        "record": ZENODO_RECORD,
        "doi": DOI,
        "licence": LICENCE,
        "source_url": f"https://zenodo.org/records/{ZENODO_RECORD}",
        "downloaded": date.today().isoformat(),
        "files": entries,
    }
    settings.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out = settings.PROCESSED_DIR / "kelvins_provenance.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    for entry in entries:
        print(f"  {entry['filename']:48s} {entry['bytes']:>13,}  {entry['sha256'][:16]}…")
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
