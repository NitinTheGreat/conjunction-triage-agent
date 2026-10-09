"""Export compact pilot evidence for version control, excluding local run payloads."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
from research.artifacts import ROOT, RUN_ROOT, sha256, write_json

SELECTION = {
    'synthesis_20261009_v1': ('real_cv_metrics.csv', 'two_stage_metrics.csv',
        'simulation_metrics.csv', 'simulation_contrasts.json', 'control_equivalence.json',
        'new_information_state_check.csv', 'real_paired_loss_differences.json',
        'feasibility.json', 'integrity_audit.json'),
    'data_20261009_v2': ('crosswalk_summary.json', 'data_summary.json'),
    'cv_20261009_v2': ('historical_anchors.json',),
    'simulation_20261009_v1': ('reservation.json', 'validation.json'),
    'verify_two_stage_20261009_v1': ('verification.json',),
}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    # Check everything before creating the destination; never overwrite a bundle.
    records, copies = [], []
    for run_id, names in SELECTION.items():
        source = RUN_ROOT / run_id
        manifest = json.loads((source/'manifest.json').read_text())
        if manifest['status'] != 'complete':
            raise ValueError(f'Incomplete run: {run_id}')
        exported = {}
        for name in names:
            artifact = source/name
            digest = sha256(artifact)
            if digest != manifest['artifacts'][name]['sha256']:
                raise ValueError(f'Changed artifact: {run_id}/{name}')
            if artifact.stat().st_size > 1_000_000:
                raise ValueError('Compact evidence must remain below 1 MB per file')
            target = f'{run_id}__{name}'
            exported[target] = {'sha256': digest, 'source_artifact': name}
            copies.append((artifact, target))
        records.append({'run_id': run_id, 'kind': manifest['kind'], 'status': 'complete',
            'scientific_status': manifest['scientific_status'],
            'original_git_head': manifest['git_head'],
            'original_manifest_sha256': sha256(source/'manifest.json'),
            'source_archive_sha256': manifest['artifacts']['code_snapshot.zip']['sha256'],
            'artifacts': exported})
    args.output.mkdir(parents=True, exist_ok=False)
    for source, target in copies:
        shutil.copyfile(source, args.output/target)
    write_json(args.output/'provenance.json', {'schema_version': 1, 'runs': records,
        'scope': 'Compact development evidence; source predictions, models and source archives remain in local ignored run directories.'})
    (args.output/'README.md').write_text('''# First-cycle pilot evidence

These small CSV/JSON files are exact copies of completed local run artifacts.
`provenance.json` records their hashes, source run IDs, original manifest hashes
and source archive hashes. The findings are exploratory, not confirmation.

Regenerate into a new directory from the retained local runs:

```powershell
.\\.venv\\Scripts\\python.exe -m research.export_pilot --output <new-directory>
```

Dataset files, models, predictions, logs, downloaded papers and machine/process
inventories are deliberately absent. A Git clone contains the readable results
and code; exact reconstruction still requires the source data and ignored
`processed/research/` artifacts identified in the checklist. Do not infer that
those files can be redistributed merely because a local run used them.
''', encoding='utf-8')
    print(f'Exported {len(copies)} verified artifacts to {args.output}')


if __name__ == '__main__':
    main()
