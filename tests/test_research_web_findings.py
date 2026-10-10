import pandas as pd

import research.web_findings as wf


def test_committed_findings_export_matches_a_fresh_build():
    data = wf.build()
    assert wf.DEFAULT_OUT.read_text(encoding='utf-8') == wf.render(data), 'Run python -m research.web_findings'


def test_findings_export_agrees_with_the_register_and_the_window_design():
    data = wf.build()
    register = pd.read_csv(wf.ROOT / 'docs/research/claims/claim_evidence.csv').set_index('id').expected
    misses = data['scientific']['misses']
    assert (misses['new'], misses['recovered'], misses['positives']) == (register['V16'], register['V17'], register['V18'])
    p1 = next(item for item in data['scientific']['decisions'] if item['id'] == 'P1')
    assert abs(p1['mean'] - register['V01']) < 1e-6 and abs(p1['lower'] - register['V02']) < 1e-6
    conditions = {item['key']: item for item in data['design']['conditions']}
    assert {tuple(item['windows'][-1]) for key, item in conditions.items() if key != 'new_information'} == {tuple(range(50, 60))}
    assert conditions['overlap_90']['unique_observations'] == 15 and conditions['overlap_90']['message_observation_pairs'] == 60
    assert data['design']['observations_total'] == 80 and len(data['design']['availability_days']) == 80
