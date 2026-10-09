import json

import pytest

import research.sensitivity_campaign as sc
from research.artifacts import Run


def contract():
    return sc.load_contract(require_committed=False)


def test_bank_plan_fixes_unique_fresh_seeds_and_matches_the_contract_counts():
    c = contract()
    plan = sc.bank_plan(c)
    training = [p for p in plan if p['role'] == 'training']
    assert len(training) == sum(s['training_banks'] for s in c['configurations'].values()) == 14
    assert len({p['seed'] for p in plan}) == len(plan) and 20261012 not in {p['seed'] for p in plan}
    assert all(not p['bank'].startswith('scientific') for p in plan)
    models = len(training) * len(c['arms'])
    assert models == c['planned_selected_models'] and models * (len(c['C']) * c['inner_folds'] + 1) == c['planned_training_fits']
    transfer = sum(s['training_banks'] for n, s in c['configurations'].items() if n == c['transfer_source']) * len(c['arms'])
    evaluations = models + transfer * (len(c['configurations']) - 1)
    assert evaluations * c['evaluation_scenarios'] * 7 == c['planned_prediction_rows']


def test_campaign_requires_a_fixed_committed_contract(tmp_path):
    draft = dict(contract(), status='draft')
    path = tmp_path / 'contract.json'
    path.write_text(json.dumps(draft), encoding='utf-8')
    with pytest.raises(ValueError, match='fixed'):
        sc.load_contract(path, require_committed=True)
    bad = dict(contract(), conditions=['no_reuse'])
    path.write_text(json.dumps(bad), encoding='utf-8')
    with pytest.raises(ValueError, match='regime'):
        sc.load_contract(path, require_committed=False)


def test_reserved_seed_in_a_plan_is_refused():
    c = contract()
    c = {**c, 'seed_base': 20261012 - 10 * 0 - 1}
    with pytest.raises(ValueError, match='reservation'):
        sc.bank_plan(c)


def test_small_preflight_runs_every_arm_and_integration_check(tmp_path):
    c = contract()
    small = {**c, 'C': [1.0, 100.0], 'configurations': {k: c['configurations'][k] for k in ('iso', 'aniso8')}}
    with Run('preflight_test', 'sensitivity_preflight', {'test': True}, base=tmp_path) as run:
        result = sc.preflight(small, run, scenarios=2, fit_scenarios=45)
    assert set(result['integration']) == {'iso', 'aniso8'} and set(result['fit_seconds']) == set(c['arms'])
    assert all(v['max_rel_difference'] < 1e-6 for v in result['integration'].values())
