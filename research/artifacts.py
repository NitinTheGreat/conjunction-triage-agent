"""Exclusive run directories, strict JSON, and reproducible provenance."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from typing import Any

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = ROOT / 'processed' / 'research'


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value: Any) -> None:
    """Validate before touching the destination; atomic replacement within a run."""
    payload = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n'
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(payload, encoding='utf-8')
    temporary.replace(path)


def sql_path(path: Path) -> str:
    return str(path.resolve()).replace('\\', '/').replace("'", "''")


def write_table(path: Path, frame: pd.DataFrame) -> None:
    if path.exists():
        raise FileExistsError(path)
    with duckdb.connect() as con:
        con.register('output_frame', frame)
        con.execute(f"COPY output_frame TO '{sql_path(path)}' (FORMAT PARQUET)")


def read_table(path: Path) -> pd.DataFrame:
    with duckdb.connect() as con:
        return con.execute(f"SELECT * FROM read_parquet('{sql_path(path)}')").fetchdf()


def code_manifest() -> dict[str, str]:
    files = []
    for directory in ('research', 'core', 'scripts'):
        files.extend((ROOT / directory).rglob('*.py'))
    return {str(p.relative_to(ROOT)).replace('\\', '/'): sha256(p) for p in sorted(files)}


class Run:
    """Never resume from file existence; failed runs receive a new ID on retry."""

    def __init__(self, run_id: str, kind: str, config: dict, inputs=(), base=RUN_ROOT):
        if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,119}', run_id):
            raise ValueError('run_id must be a simple identifier, not a path')
        # Validate before creating a directory.
        json.dumps(config, allow_nan=False)
        self.path = Path(base) / run_id
        self.path.mkdir(parents=True, exist_ok=False)
        self.record = {
            'run_id': run_id, 'kind': kind, 'status': 'planned', 'created_utc': utc(),
            'scientific_status': 'development_or_reconstruction_not_confirmation',
            'command': [sys.executable, *sys.argv], 'working_directory': str(Path.cwd()),
            'pid': os.getpid(), 'python': sys.version, 'config': config,
            'inputs': {str(Path(p)): sha256(Path(p)) for p in inputs},
            'code_sha256': code_manifest(),
            'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            'git_status': subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True),
            'environment': {k: os.environ.get(k) for k in ('LOKY_MAX_CPU_COUNT', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS')},
            'access': [],
        }
        with zipfile.ZipFile(self.path / 'code_snapshot.zip', 'x', compression=zipfile.ZIP_DEFLATED) as archive:
            for source, expected in self.record['code_sha256'].items():
                payload = (ROOT / source).read_bytes()
                if hashlib.sha256(payload).hexdigest() != expected:
                    raise RuntimeError('Source changed while recording the run')
                archive.writestr(source, payload)
            archive.write(ROOT / 'requirements.txt', 'requirements.txt')
        write_json(self.path / 'manifest.json', self.record)

    def __enter__(self):
        self.record.update(status='running', started_utc=utc())
        write_json(self.path / 'manifest.json', self.record)
        return self

    def access(self, source: str, purpose: str, exposure: str):
        self.record['access'].append({'utc': utc(), 'source': source, 'purpose': purpose, 'exposure': exposure})
        write_json(self.path / 'manifest.json', self.record)

    def __exit__(self, exc_type, exc, tb):
        self.record.update(status='failed' if exc_type else 'complete', finished_utc=utc())
        if exc_type:
            # Error category only: exception text could contain provider credentials.
            self.record['failure_type'] = exc_type.__name__
        self.record['artifacts'] = {
            p.name: {'sha256': sha256(p), 'bytes': p.stat().st_size}
            for p in sorted(self.path.iterdir()) if p.is_file() and p.name != 'manifest.json'
        }
        write_json(self.path / 'manifest.json', self.record)
        return False
