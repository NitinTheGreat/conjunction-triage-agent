import numpy as np

from research.history import Event
from research.models import ProbabilityModel
from research.simulation import generate_bank
from research.simulation_v2 import repair_bank
from research.simulation_regimes import training_rows, scenario_folds, fit_arm


def test_duplicate_training_variants_do_not_change_objective_strength():
    # Holding the observations fixed, introducing two half-weight copies must
    # not silently halve regularization by doubling the total objective weight.
    X = np.linspace(-3, 3, 40)[:, None]
    y = ((np.arange(40) % 5) == 0).astype(int)
    events = [Event(str(i), np.empty((0, 0))) for i in range(len(X))]
    single = ProbabilityModel('latest', .1, 4).fit(X, y, events)
    duplicated = ProbabilityModel('latest', .1, 4).fit(
        np.tile(X, (2, 1)), np.tile(y, 2), events+events,
        event_weights=np.full(2*len(X), .5))
    np.testing.assert_allclose(single.predict(X, events), duplicated.predict(X, events), atol=1e-10, rtol=1e-10)


def test_variant_folds_and_nested_fit_keep_whole_scenarios_together():
    cohort, messages, lineage, _, _ = generate_bank(36, 712, 'fold_test')
    # Test labels ensure both classes without claiming synthetic efficacy.
    cohort['final_risk'] = np.where(np.arange(len(cohort)) % 3 == 0, -5., -9.)
    messages, _ = repair_bank(messages, lineage)
    frame, events, X = training_rows(cohort, messages, ('no_reuse', 'new_information', 'burst_reissue'))
    splits = scenario_folds(frame, 3, 4)
    covered = []
    for fit, valid in splits:
        assert not set(frame.series_id.iloc[fit]) & set(frame.series_id.iloc[valid])
        assert (frame.iloc[valid].groupby('series_id').size() == 3).all()
        covered.extend(valid)
    assert sorted(covered) == list(range(len(frame)))
    np.testing.assert_allclose(frame.groupby('series_id').event_weight.sum(), 1.)
    for arm in ('latest_metadata', 'grouped'):
        saved, selection, q = fit_arm(frame, events, X, arm, splits, [.1], 7)
        assert np.isfinite(q).all() and selection['training_scenarios'] == 36
        assert np.isclose(selection['objective_weight_sum'], 36)
        assert np.isfinite(saved['calibration'].predict(saved['model'].predict(X, events))).all()
