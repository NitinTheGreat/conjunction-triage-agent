import numpy as np
import pandas as pd
import pytest

import research.claim_register as cr


def register(**changes):
    base = {'id': 'C1', 'claim': 'x', 'evidence_type': 'exposed development simulation', 'source': 'bundle/t.csv',
            'selector': "group=='a'", 'column': 'v', 'statistic': 'min', 'expected': 1.0, 'tolerance': 1e-9, 'status': 'regenerated'}
    return pd.DataFrame([{**base, **changes}])


@pytest.fixture
def root(tmp_path):
    (tmp_path / 'bundle').mkdir()
    pd.DataFrame({'group': ['a', 'a', 'b'], 'v': [1.0, 2.0, 5.0]}).to_csv(tmp_path / 'bundle/t.csv', index=False)
    return tmp_path


def test_regenerated_claims_must_match_the_bundle(root):
    assert cr.verify(register(), root)[0]['status'] == 'regenerated'
    assert cr.verify(register(statistic='count', expected=2.0), root)[0]['actual'] == 2.0
    with pytest.raises(ValueError, match='differs'):
        cr.verify(register(expected=1.5), root)
    with pytest.raises(ValueError, match='exactly one'):
        cr.verify(register(statistic='value'), root)
    with pytest.raises(ValueError, match='no rows'):
        cr.verify(register(selector="group=='z'"), root)


def test_pending_and_documented_rows_are_checked(root):
    pending = register(evidence_type='pending scientific evaluation', status='pending', source=np.nan, expected=np.nan)
    assert cr.verify(pending, root)[0]['status'] == 'pending'
    with pytest.raises(ValueError, match='pending'):
        cr.verify(register(evidence_type='pending scientific evaluation', status='pending'), root)
    assert cr.verify(register(status='documented', evidence_type='protocol'), root)[0]['status'] == 'documented'
    with pytest.raises(ValueError, match='missing'):
        cr.verify(register(status='documented', evidence_type='protocol', source='nope.json'), root)
    with pytest.raises(ValueError, match='evidence type'):
        cr.verify(register(evidence_type='confirmed'), root)
