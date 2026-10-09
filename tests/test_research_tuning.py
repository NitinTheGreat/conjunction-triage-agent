import numpy as np
import pandas as pd
import pytest
from sklearn.exceptions import ConvergenceWarning

from research.history import Event
from research.simulation_regimes import fit_arm, scenario_folds
from research.tuning_stability import sample_scenarios


def test_scenario_subsets_are_stratified_reproducible_and_vary_by_seed():
    cohort = pd.DataFrame({'series_id': [f's{i}' for i in range(100)],
                           'final_risk': np.where(np.arange(100) < 20, -5., -9.)})
    a = sample_scenarios(cohort, .8, 31)
    pd.testing.assert_frame_equal(a, sample_scenarios(cohort, .8, 31))
    assert len(a) == 80 and (a.final_risk >= -6).sum() == 16 and a.series_id.is_unique
    assert set(a.series_id) != set(sample_scenarios(cohort, .8, 32).series_id)
    pd.testing.assert_frame_equal(cohort, sample_scenarios(cohort, 1., 31))
    # All variants inherit a scenario's membership and inner fold.
    frame = pd.concat([a.assign(condition=c) for c in ('a', 'b')], ignore_index=True)
    frame['y'] = (frame.final_risk >= -6).astype(int)
    for train, valid in scenario_folds(frame, 3, 31):
        assert not set(frame.series_id.iloc[train]) & set(frame.series_id.iloc[valid])
        assert (frame.iloc[valid].groupby('series_id').size() == 2).all()


def test_nonconverged_candidate_cannot_silently_enter_tuning():
    rng = np.random.default_rng(11)
    X = rng.normal(size=(90, 1))
    frame = pd.DataFrame({'series_id': [f's{i}' for i in range(90)],
                         'y': (X[:, 0] + rng.normal(size=90)*.3 > 0).astype(int),
                         'event_weight': 1.})
    events = [Event(s, np.empty((0, 0))) for s in frame.series_id]
    with pytest.raises(ConvergenceWarning):
        fit_arm(frame, events, X, 'latest', scenario_folds(frame, 3, 3), [1000.], 3,
                max_iter=1, require_convergence=True)
