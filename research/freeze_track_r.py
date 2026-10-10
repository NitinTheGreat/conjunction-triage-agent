"""Write the frozen Track R protocol, reservation manifest and freeze record (V03).

Transcribes the V02 analysis specification into machine-readable form and pins
every research module by git blob id. Refuses to overwrite, to run with
uncommitted research code, or to run after any reserved bank exists. Generates no
scenario and reads no outcome.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import subprocess

from research.artifacts import ROOT, RUN_ROOT, utc, write_json
from research.sensitivity_banks import RESERVED_PREFIXES, RESERVED_SEEDS
from research.track_r_scientific import FREEZE, PROTOCOL, blob_id, load_protocol, protocol_hash

RESERVATION = ROOT / 'docs/research/execution/track_r_reservation.json'
SPECIFICATION = ROOT / 'docs/research/execution/analysis_specification.md'
CONDITIONS = ['no_reuse', 'overlap_50', 'overlap_90', 'solution_reissue', 'new_information', 'burst_reissue']
CONTRASTS = [
    {'id': 'P1', 'role': 'primary', 'arm': 'singleton', 'comparator': 'latest_metadata', 'condition': 'overlap_90',
     'estimand': 'degradation', 'null': 0.02, 'alternative': 'greater'},
    {'id': 'S1', 'role': 'confirmatory_secondary', 'arm': 'singleton', 'comparator': 'latest_metadata', 'condition': 'overlap_90',
     'estimand': 'absolute', 'null': -0.02, 'alternative': 'greater'},
    {'id': 'S5', 'role': 'confirmatory_secondary', 'arm': 'singleton', 'comparator': 'latest_metadata', 'condition': 'solution_reissue',
     'estimand': 'degradation', 'null': 0.02, 'alternative': 'greater'},
    {'id': 'S2', 'role': 'confirmatory_secondary', 'arm': 'grouped', 'comparator': 'singleton', 'condition': 'overlap_90',
     'estimand': 'degradation', 'null': -0.01, 'alternative': 'greater'},
    {'id': 'S3', 'role': 'confirmatory_secondary', 'arm': 'oracle_lineage_weight', 'comparator': 'singleton', 'condition': 'overlap_90',
     'estimand': 'degradation', 'null': -0.01, 'alternative': 'greater'},
    {'id': 'S6', 'role': 'exploratory', 'arm': 'singleton', 'comparator': 'latest_metadata', 'condition': 'solution_reissue',
     'estimand': 'absolute', 'null': None, 'alternative': None},
]


def build_protocol(git_head: str, code: dict[str, str], specification_blob: str) -> dict:
    banks = [{'bank': f'scitrain{k:02d}', 'seed': 20261300 + k} for k in range(1, 11)]
    return {
        'version': 1, 'status': 'frozen', 'track': 'R (narrowed robustness/measurement benchmark)',
        'claim': ('With the latest message and the final-risk label fixed, 90% observation-ID overlap between successive '
                  'windows degrades a history-summary logistic forecaster (singleton) by more than 0.02 nats of clipped '
                  'log loss relative to the reuse-invariant latest-message comparator, averaged over independent training '
                  'banks and scenarios, in the held-out simulator configuration.'),
        'population': 'Unweighted enriched latent encounter-plane scenarios (30% near-miss component); not operational prevalence.',
        'unit': 'whole latent scenario; all reuse variants share its observation bank and label',
        'label': 'final recorded log10 risk >= -6 from the full unique-observation posterior (not physical collision occurrence)',
        'configuration': {'eigenvalues': [0.144, 0.036], 'rotation_degrees': 30.0, 'shared_bias_variance': 0.0,
                          'note': 'Unexposed candidate: noise variance ratio 4 rotated 30 degrees, trace 0.18; bracketed by development ratios 2 and 8.'},
        'independent_training_banks': len(banks), 'training_banks': banks,
        'evaluation_bank': {'bank': 'scientific', 'seed': 20261012, 'ids': 'scientific:00000..04999'},
        'training_scenarios': 1000, 'evaluation_scenarios': 5000,
        'regime': 'matched_mixture', 'conditions': CONDITIONS, 'evaluation_conditions': 'all seven, including exact_replay',
        'arms': ['singleton', 'latest_metadata', 'grouped', 'oracle_lineage_weight'],
        'C': [0.01, 0.1, 1.0, 10.0, 100.0, 1000.0], 'inner_folds': 3, 'max_iter': 10000,
        'selection_and_calibration': ('Minimum weighted inner-OOF clipped log loss (1e-6), ties to smaller C; monotone Platt on '
                                      'selected OOF; nominal 95% training-recall threshold; refit on the full training bank.'),
        'integration_seed': 20261390,
        'analysis': {
            'primary': 'P1', 'margin': 0.02, 'alpha': 0.05, 'clipping': 1e-6,
            'interval': ('bank-combined studentized bootstrap: bootstrap-t over scenarios of bank-averaged contrasts, '
                         'combined in quadrature per side with t(K-1) x SD(bank means)/sqrt(K)'),
            'bootstrap_resamples': 9999, 'bootstrap_seed': 20261391,
            'primary_rule': {'material_degradation_confirmed': 'lower > margin', 'not_material': 'upper < margin',
                             'inconclusive': 'otherwise'},
            'contrasts': CONTRASTS, 'confirmatory_secondary': ['S1', 'S5', 'S2', 'S3'],
            'multiplicity': 'P1 alone at two-sided 95%; Holm step-down at familywise one-sided 0.05 over the secondary family',
            'reported_regardless': ['absolute and degradation losses for every arm and condition', 'Brier and calibration summaries',
                                    'reuse-induced misses with exact intervals', 'review counts', 'scenario-only conditional intervals as sensitivity'],
        },
        'failure_policy': ('Any convergence warning, nonfinite value, failed integration check, failed exact-replay or latest-message '
                           'invariance, or plan/output mismatch stops the run; records are retained; no scenario, bank, arm or '
                           'candidate is dropped; a rerun uses a new run ID under the unchanged protocol and is reported.'),
        'amendment_policy': ('Amendments are recorded with date, reason and outcome visibility; amendments made after scientific '
                             'outcomes are visible cannot change the primary contrast, margin, rule, sample size or interval method.'),
        'analysis_specification': {'path': 'docs/research/execution/analysis_specification.md', 'blob_id': specification_blob},
        'evidence_runs': ['tuning_adequacy_20261010_v2', 'precision_planning_20261010_v2', 'interval_validation_20261010_v1',
                          'interval_validation_20261010_v2', 'sensitivity_20261010_v1', 'sensitivity_summary_20261010_v1',
                          'bank_interval_validation_20261010_v1'],
        'git_head_at_freeze': git_head,
        'environment': {'python': platform.python_version(), 'platform': platform.platform()},
        'code_blob_ids': code,
    }


def reserved_bank_files() -> list[str]:
    hits = []
    for directory in RUN_ROOT.iterdir():
        if directory.is_dir():
            hits += [str(p) for p in directory.glob('*') if any(f'{prefix}' in p.name for prefix in ('scientific', 'scitrain'))]
    return hits


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    for path in (PROTOCOL, FREEZE, RESERVATION):
        if path.exists():
            raise FileExistsError(path)
    dirty = subprocess.check_output(['git', 'status', '--porcelain', '--', 'research', 'tests', str(SPECIFICATION)], cwd=ROOT, text=True)
    if dirty.strip():
        raise ValueError(f'Commit research code, tests and the specification before freezing:\n{dirty}')
    existing = reserved_bank_files()
    if existing:
        raise ValueError(f'Reserved banks already exist: {existing[:5]}')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    modules = sorted(p for p in (ROOT / 'research').rglob('*.py'))
    code = {p.relative_to(ROOT).as_posix(): blob_id(p) for p in modules}
    for name in ('requirements.txt', 'requirements-sequence.txt'):
        code[name] = blob_id(ROOT / name)
    protocol = build_protocol(head, code, blob_id(SPECIFICATION))
    seeds = {b['seed'] for b in protocol['training_banks']} | {protocol['evaluation_bank']['seed']}
    if not seeds <= RESERVED_SEEDS or not all(b['bank'].startswith(RESERVED_PREFIXES) for b in protocol['training_banks']):
        raise ValueError('Protocol banks must be reserved in the generator')
    write_json(PROTOCOL, protocol)
    load_protocol(PROTOCOL, require_frozen=False)
    write_json(RESERVATION, {
        'created_utc': utc(), 'written_before_generation': True,
        'scientific_evaluation': {'seed': 20261012, 'ids': 'scientific:00000..04999', 'generated': False},
        'scientific_training': {'seeds': sorted(b['seed'] for b in protocol['training_banks']),
                                'banks': [b['bank'] for b in protocol['training_banks']], 'ids': 'scitrainKK:00000..00999',
                                'generated': False},
        'access_rule': ('Only research.track_r_scientific may generate these banks, through ReservedAccess derived from the '
                        'committed frozen protocol whose canonical hash matches track_r_freeze.json.'),
        'prior_label_free_contact': ('One numerical-integration accuracy check (300 random posteriors, seed 11) used the '
                                     'scientific noise covariance; no scenario, label or model was involved.')})
    write_json(FREEZE, {
        'created_utc': utc(), 'protocol': 'docs/research/execution/track_r_protocol.json',
        'protocol_sha256': protocol_hash(PROTOCOL), 'git_head_at_freeze': head,
        'reservation': 'docs/research/execution/track_r_reservation.json',
        'scientific_outcomes_accessed': False, 'reserved_bank_files_found': 0,
        'pending_before_v04': ['independent analysis-owner reproduction of the decision rule on boundary-null and zero-discordance cases',
                               "user authorization to generate and evaluate the reserved scientific banks"],
        'statement': 'Frozen before any scientific scenario or outcome existed. V04 must not change any frozen item.'})
    print('FROZEN', protocol_hash(PROTOCOL), flush=True)


if __name__ == '__main__':
    main()
