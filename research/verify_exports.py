"""Verify compact result bundles using only Python's standard library."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path


def verify_bundle(directory: Path) -> dict:
    directory = directory.resolve()
    provenance = json.loads((directory/'provenance.json').read_text(encoding='utf-8'))
    if 'runs' in provenance:
        entries = [(name, value['sha256']) for run in provenance['runs']
                   for name, value in run['artifacts'].items()]
    elif 'artifacts' in provenance:
        entries = list(provenance['artifacts'].items())
    else:
        raise ValueError('Unknown provenance format')
    if not entries or len({name for name, _ in entries}) != len(entries):
        raise ValueError('Empty or duplicate artifact inventory')
    size = 0
    for name, expected in entries:
        path = (directory/name).resolve()
        if directory not in path.parents:
            raise ValueError('Artifact path escapes its bundle')
        payload = path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != expected:
            raise ValueError(f'Artifact checksum mismatch: {name}')
        size += len(payload)
    return {'bundle': directory.name, 'status': 'pass', 'artifacts_verified': len(entries),
            'bytes_verified': size}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('docs/research/results'))
    args = parser.parse_args()
    manifests = sorted(args.root.rglob('provenance.json'))
    if not manifests:
        raise ValueError('No compact result bundles found')
    results = [verify_bundle(path.parent) for path in manifests]
    print(json.dumps({'status': 'pass', 'bundles': results,
        'scope': 'Content consistency against committed provenance; no retraining or independent scientific validation.'}, indent=2))


if __name__ == '__main__':
    main()
