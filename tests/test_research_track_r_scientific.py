import json
import shutil

import numpy as np
import pandas as pd
import pytest

import research.track_r_scientific as tr
from research.artifacts import Run, read_table
from research.sensitivity_banks import cadence_bank as real_cadence_bank

CONDITIONS = ['no_reuse', 'overlap_50', 'overlap_90', 'solution_reissue', 'new_information', 'burst_reissue']


def protocol():
    contrasts = [
        {'id': 'P1', 'arm': 'singleton', 'comparator': 'latest_metadata', 'condition': 'overlap_90', 'estimand': 'degradation', 'null': .02, 'alternative': 'greater'},
        {'id': 'S1', 'arm': 'singleton', 'comparator': 'latest_metadata', 'condition': 'overlap_90', 'estimand': 'absolute', 'null': -.02, 'alternative': 'greater'},
        {'id': 'S5', 'arm': 'singleton', 'comparator': 'latest_metadata', 'condition': 'solution_reissue', 'estimand': 'degradation', 'null': .02, 'alternative': 'greater'},
        {'id': 'S2', 'arm': 'grouped', 'comparator': 'singleton', 'condition': 'overlap_90', 'estimand': 'degradation', 'null': -.01, 'alternative': 'greater'},
        {'id': 'S3', 'arm': 'oracle_lineage_weight', 'comparator': 'singleton', 'condition': 'overlap_90', 'estimand': 'degradation', 'null': -.01, 'alternative': 'greater'},
        {'id': 'S6', 'arm': 'singleton', 'comparator': 'latest_metadata', 'condition': 'solution_reissue', 'estimand': 'absolute', 'null': None, 'alternative': None},
    ]
    return {'status': 'draft', 'configuration': {'eigenvalues': [.144, .036], 'rotation_degrees': 30., 'shared_bias_variance': 0.},
            'independent_training_banks': 2,
            'training_banks': [{'bank': 'trdev_t1', 'seed': 20261401}, {'bank': 'trdev_t2', 'seed': 20261402}],
            'evaluation_bank': {'bank': 'trdev_eval', 'seed': 20261400},
            'training_scenarios': 45, 'evaluation_scenarios': 40, 'conditions': CONDITIONS,
            'arms': ['singleton', 'latest_metadata', 'grouped', 'oracle_lineage_weight'], 'C': [1., 100.],
            'inner_folds': 3, 'max_iter': 10000, 'integration_seed': 20261499,
            'analysis': {'primary': 'P1', 'margin': .02, 'alpha': .05, 'bootstrap_resamples': 199, 'bootstrap_seed': 5,
                         'contrasts': contrasts, 'confirmatory_secondary': ['S1', 'S5', 'S2', 'S3']},
            'code_blob_ids': {}}


def write_protocol(tmp_path, value):
    path = tmp_path / 'protocol.json'
    path.write_text(json.dumps(value), encoding='utf-8')
    return path


@pytest.fixture(scope='module')
def completed(tmp_path_factory):
    tmp = tmp_path_factory.mktemp('track_r')
    p = tr.load_protocol(write_protocol(tmp, protocol()), require_frozen=False)
    with Run('dev_run', 'track_r_scientific_test', {'test': True}, base=tmp) as run:
        models = tr.phase_train(p, run, None)
        tr.phase_predict(p, run, None, models)
        results = tr.phase_analyse(p, run)
    return p, run, models, results


def test_three_phase_run_produces_every_prespecified_result(completed):
    p, run, models, results = completed
    assert set(results) == {c['id'] for c in p['analysis']['contrasts']}
    assert results['P1']['decision'] in {'material_degradation_confirmed', 'not_material', 'inconclusive'}
    assert all('holm_rejected' in results[k] for k in p['analysis']['confirmatory_secondary'])
    assert 'p_value' not in results['S6'] and results['P1']['banks'] == 2
    commit = json.loads((run.path / 'phase2_commit.json').read_text())
    assert commit['labels_read'] is False and commit['rows'] == 2 * 4 * 40 * 7
    labelled = read_table(run.path / 'predictions_labelled.parquet')
    assert labelled.y.notna().all() and labelled.training_bank.nunique() == 2


def test_predictions_do_not_depend_on_evaluation_labels(completed, tmp_path, monkeypatch):
    p, run, models, _ = completed

    def shuffled(n, seed, bank, noise, bias, access=None):
        cohort, messages, lineage = real_cadence_bank(n, seed, bank, noise, bias, access)
        cohort = cohort.assign(final_risk=np.random.default_rng(0).permutation(cohort.final_risk.to_numpy()))
        return cohort, messages, lineage
    monkeypatch.setattr(tr, 'cadence_bank', shuffled)
    with Run('shuffled', 'track_r_scientific_test', {'test': True}, base=tmp_path) as other:
        shutil.copyfile(run.path / 'model_hashes.json', other.path / 'model_hashes.json')
        tr.phase_predict(p, other, None, models)
    a = read_table(run.path / 'predictions_unlabeled.parquet')
    b = read_table(other.path / 'predictions_unlabeled.parquet')
    pd.testing.assert_frame_equal(a, b)
    assert not read_table(run.path / 'sealed_labels.parquet').equals(read_table(other.path / 'sealed_labels.parquet'))


def test_frozen_protocol_requirements_and_reserved_identities(tmp_path):
    path = write_protocol(tmp_path, protocol())
    with pytest.raises(ValueError, match='frozen'):
        tr.load_protocol(path, require_frozen=True)
    reserved = protocol()
    reserved['training_banks'][0] = {'bank': 'scitrain01', 'seed': 20261301}
    p = tr.load_protocol(write_protocol(tmp_path, reserved), require_frozen=False)
    with Run('refused', 'track_r_scientific_test', {'test': True}, base=tmp_path) as run, pytest.raises(ValueError, match='reservation'):
        tr.phase_train(p, run, None)
    bad = protocol()
    bad['independent_training_banks'] = 3
    with pytest.raises(ValueError, match='inconsistent'):
        tr.load_protocol(write_protocol(tmp_path, bad), require_frozen=False)


def test_blob_ids_match_committed_git_objects():
    import subprocess
    from research.artifacts import ROOT
    committed = subprocess.check_output(['git', 'rev-parse', 'HEAD:research/metrics.py'], cwd=ROOT, text=True).strip()
    assert tr.blob_id(ROOT / 'research/metrics.py') == committed


def test_freeze_builder_matches_the_runner_and_reservation():
    from research.freeze_track_r import build_protocol
    from research.sensitivity_banks import RESERVED_PREFIXES, RESERVED_SEEDS
    p = build_protocol('0' * 40, {}, 'b' * 40)
    assert p['status'] == 'frozen' and p['independent_training_banks'] == 10 and p['evaluation_scenarios'] == 5000
    assert {b['seed'] for b in p['training_banks']} | {p['evaluation_bank']['seed']} <= RESERVED_SEEDS
    assert all(b['bank'].startswith(RESERVED_PREFIXES) for b in p['training_banks'])
    ids = {c['id'] for c in p['analysis']['contrasts']}
    assert set(p['analysis']['confirmatory_secondary']) <= ids and p['analysis']['primary'] in ids
    assert [c for c in p['analysis']['contrasts'] if c['id'] == 'S6'][0]['null'] is None
