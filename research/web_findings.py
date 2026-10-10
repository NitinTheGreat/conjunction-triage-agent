"""Export the paper's findings for the web app's findings page.

Reads committed result bundles, the frozen protocol, the claim register and the
simulator's window definitions, and writes one deterministic JSON file with the
SHA-256 of every input. Nothing here fits a model or reads a local run directory,
so a clone regenerates the page data exactly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from research.simulation import windows

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / 'docs/research/results'
DEFAULT_OUT = ROOT / 'web/public/data/paper_findings.json'
CONDITIONS = (
    ('no_reuse', 'No reuse', 'Each message is computed from ten observations that no other message uses.'),
    ('overlap_50', '50% overlap', 'Each window shares five of its ten observations with the previous one.'),
    ('overlap_90', '90% overlap', 'Each window shares nine of its ten observations with the previous one.'),
    ('solution_reissue', 'Solution reissue', 'The same ten-observation solution is published six times.'),
    ('new_information', 'New information', 'Each message adds ten new observations to everything seen before.'),
)
ARM_LABELS = {'singleton': 'History summary', 'latest_metadata': 'Latest message', 'grouped': 'Grouped history',
              'oracle_lineage_weight': 'Lineage-weighted history', 'latest': 'Latest risk', 'causal_gbm': 'Gradient boosting'}


def rounded(value, digits: int = 6):
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return None
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    return float(f'{float(value):.{digits}g}')


class Inputs:
    """Read committed files and remember their hashes."""
    def __init__(self):
        self.hashes: dict[str, str] = {}

    def path(self, relative: str) -> Path:
        path = ROOT / relative
        self.hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        return path

    def csv(self, relative: str) -> pd.DataFrame:
        return pd.read_csv(self.path(relative))

    def json(self, relative: str):
        return json.loads(self.path(relative).read_text(encoding='utf-8'))


def design() -> dict:
    availability = np.r_[np.linspace(8., 6.1, 60), np.linspace(1., .1, 20)]
    conditions = []
    for key, label, note in CONDITIONS:
        sets = [w.tolist() for w in windows(key)]
        pairs = sum(len(w) for w in sets)
        unique = len(set().union(*map(set, sets)))
        conditions.append({'key': key, 'label': label, 'note': note, 'windows': sets,
                           'message_observation_pairs': pairs, 'unique_observations': unique})
    return {'observations_total': 80, 'observations_visible': 60,
            'availability_days': [rounded(x, 4) for x in availability],
            'message_times_days': [6.0, 5.9, 5.75, 3.5, 2.09, 2.0],
            'replay_note': 'Exact replay sends each no-reuse message three times; burst reissue repeats them 2, 1, 3, 1, 2 and 1 times at new publication times.',
            'conditions': conditions}


def scientific(read: Inputs) -> dict:
    base = 'docs/research/results/track_r_scientific_2026-10-10/'
    decisions = read.csv(base + 'decisions.csv')
    order = ['P1', 'S5', 'S1', 'S2', 'S3', 'S6']
    rows = []
    for cid in order:
        row = decisions[decisions.id == cid].iloc[0]
        rows.append({'id': cid, 'role': row['role'], 'arm': row.arm, 'comparator': row.comparator, 'condition': row.condition,
                     'estimand': row.estimand, 'mean': rounded(row['mean']), 'lower': rounded(row.lower), 'upper': rounded(row.upper),
                     'scenario_lower': rounded(row.scenario_lower), 'scenario_upper': rounded(row.scenario_upper),
                     'null': rounded(row['null']) if pd.notna(row['null']) else None,
                     'p_value': rounded(row.p_value) if pd.notna(row.p_value) else None,
                     'holm_rejected': bool(row.holm_rejected) if pd.notna(row.holm_rejected) else None,
                     'decision': row.decision if isinstance(row.decision, str) else None})
    per_bank = read.csv(base + 'per_bank_losses.csv')
    losses = []
    for (arm, condition), g in per_bank.groupby(['arm', 'condition'], sort=True):
        losses.append({'arm': arm, 'condition': condition, 'mean': rounded(g.log_loss.mean()), 'min': rounded(g.log_loss.min()),
                       'max': rounded(g.log_loss.max()), 'missed': int(g.missed.sum()), 'positives': int(g.positives.sum())})
    absolute = read.csv(base + 'losses.csv')
    rates = [{'arm': r.arm, 'condition': r.condition, 'miss_rate': rounded(r.miss_rate), 'review_fraction': rounded(r.mean_review_fraction),
              'roc_auc': rounded(r.roc_auc)} for r in absolute.itertuples(index=False)]
    contrasts = read.csv(base + 'bank_contrasts.csv')
    banks = {cid: [{'bank': r.training_bank, 'mean': rounded(r.mean)} for r in g.itertuples(index=False)]
             for cid, g in contrasts.groupby('id', sort=True)}
    p1 = contrasts[contrasts.id == 'P1']
    misses = {'new': int(p1.reuse_new_misses_arm.sum()), 'recovered': int(p1.reuse_recovered_misses_arm.sum()),
              'positives': int(p1.positives.sum())}
    selections = read.csv(base + 'selections.csv')
    audit = read.json(base + 'audit.json')
    return {'decisions': rows, 'losses': losses, 'rates': rates, 'banks': banks, 'misses': misses,
            'selections': {'models': len(selections), 'at_upper_C': int(selections.at_upper_C.sum()),
                           'max_iterations': int(selections.maximum_iterations.max())},
            'labelled_rows': audit['labelled_rows'], 'bank_sd': rounded(audit['scientific_components_P1']['bank_sd'])}


def development(read: Inputs) -> dict:
    base = 'docs/research/results/sensitivity_2026-10-10/'
    frame = read.csv(base + 'bank_contrasts.csv')
    native = frame[(frame.id == 'P1') & (frame.training_configuration == frame.evaluation_configuration)]
    names = {'iso': 'Isotropic', 'aniso2': 'Anisotropy 2', 'aniso8': 'Anisotropy 8', 'noise2': 'Doubled noise', 'bias': 'Shared bias'}
    banks = [{'configuration': names[r.training_configuration], 'key': r.training_configuration, 'bank': r.training_bank,
              'mean': rounded(r.mean), 'lower': rounded(r.lower95), 'upper': rounded(r.upper95)}
             for r in native.itertuples(index=False)]
    order = list(names)
    banks.sort(key=lambda item: (order.index(item['key']), item['bank']))
    transfer = read.csv(base + 'transfer.csv')
    bias = transfer[(transfer.evaluation_configuration == 'bias') & (transfer.id == 'P1')].iloc[0]
    return {'p1_banks': banks, 'bias_transfer_mean': rounded(bias.transfer_mean)}


def real(read: Inputs) -> dict:
    base = 'docs/research/results/real_2026-10-10/'
    contrasts = read.csv(base + 'contrasts.csv')
    rows = [{'split': r.split, 'id': r.id, 'arm': r.arm, 'comparator': r.comparator, 'mean': rounded(r.mean),
             'event_lower': rounded(r.event_lower), 'event_upper': rounded(r.event_upper),
             'mission_lower': rounded(r.mission_lower), 'mission_upper': rounded(r.mission_upper),
             'missions': int(r.missions), 'events': int(r.events), 'positives': int(r.positives)}
            for r in contrasts.itertuples(index=False)]
    metrics = read.csv(base + 'metrics.csv')
    metric_rows = [{'split': r.split, 'arm': r.arm, 'n': int(r.n), 'positives': int(r.positives), 'log_loss': rounded(r.log_loss),
                    'roc_auc': rounded(r.roc_auc), 'reviewed_95': int(r.reviewed_95), 'missed_95': int(r.missed_95)}
                   for r in metrics.itertuples(index=False)]
    frontiers = read.csv(base + 'frontiers.csv')
    curves = {}
    for (split, arm), g in frontiers.groupby(['split', 'arm'], sort=True):
        g = g.sort_values('review_fraction')
        curves.setdefault(split, {})[arm] = [[rounded(f, 4), int(m)] for f, m in zip(g.review_fraction, g.missed)]
    summary = read.json('docs/research/results/pilot_2026-10-09/data_20261009_v2__data_summary.json')
    cohort = {split: {'raw_events': summary[split]['raw_events'], 'eligible_events': summary[split]['eligible_events'],
                      'positives': summary[split]['high_risk_eligible']} for split in ('train', 'test')}
    return {'contrasts': rows, 'metrics': metric_rows, 'frontiers': curves, 'cohort': cohort}


def build() -> dict:
    read = Inputs()
    protocol = read.json('docs/research/execution/track_r_protocol.json')
    freeze = read.json('docs/research/execution/track_r_freeze.json')
    register = read.csv('docs/research/claims/claim_evidence.csv')
    data = {
        'generated_by': 'research/web_findings.py',
        'protocol': {'sha256': freeze['protocol_sha256'], 'git_head_at_freeze': freeze['git_head_at_freeze'],
                     'frozen_utc': freeze['created_utc'], 'claim': protocol['claim'], 'configuration': protocol['configuration'],
                     'training_banks': protocol['independent_training_banks'], 'training_scenarios': protocol['training_scenarios'],
                     'evaluation_scenarios': protocol['evaluation_scenarios'], 'margin': protocol['analysis']['margin'],
                     'bootstrap_resamples': protocol['analysis']['bootstrap_resamples'], 'label': protocol['label'],
                     'population': protocol['population'], 'pinned_files': len(protocol['code_blob_ids'])},
        'design': design(),
        'scientific': scientific(read),
        'development': development(read),
        'real': real(read),
        'arms': ARM_LABELS,
        'register': [{'id': r.id, 'evidence_type': r.evidence_type, 'claim': r.claim, 'value': rounded(r.expected)}
                     for r in register.itertuples(index=False) if r.status == 'regenerated'],
    }
    data['inputs_sha256'] = dict(sorted(read.hashes.items()))
    return data


def render(data: dict) -> str:
    return json.dumps(data, indent=1, ensure_ascii=False, allow_nan=False) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(build()), encoding='utf-8', newline='\n')
    print('WROTE', args.out)


if __name__ == '__main__':
    main()
