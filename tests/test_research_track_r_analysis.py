import numpy as np
import pytest

import research.track_r_analysis as ta


def test_bootstrap_interval_and_p_values_agree_with_the_margin_decision():
    x = np.random.default_rng(1).exponential(.07, size=2000)
    r = ta.studentized_bootstrap(x, 1999, 5)
    assert r['lower'] < r['mean'] < r['upper'] and r['t_lower'] < r['mean'] < r['t_upper']
    for margin in (0.0, .02, r['lower'] - 1e-9, r['upper'] + 1e-9, .2):
        decision = ta.primary_decision(r, margin)
        p_greater, p_less = ta.one_sided_p(r, margin, 'greater'), ta.one_sided_p(r, margin, 'less')
        if decision == 'material_degradation_confirmed':
            assert p_greater <= .025 + 1 / 2000
        elif decision == 'not_material':
            assert p_less <= .025 + 1 / 2000
        else:
            assert p_greater > .025 - 1 / 2000 and p_less > .025 - 1 / 2000
    assert ta.primary_decision(r, 0.0) == 'material_degradation_confirmed'
    assert ta.primary_decision(r, .2) == 'not_material'
    with pytest.raises(ValueError):
        ta.one_sided_p(r, 0.0, 'two-sided')


def test_bootstrap_is_reproducible_and_rejects_degenerate_input():
    x = np.random.default_rng(2).normal(size=300)
    a, b = ta.studentized_bootstrap(x, 499, 9), ta.studentized_bootstrap(x, 499, 9)
    assert a['lower'] == b['lower'] and np.array_equal(a['t_star'], b['t_star'])
    with pytest.raises(ValueError):
        ta.studentized_bootstrap(np.ones(20), 99, 1)
    with pytest.raises(ValueError):
        ta.studentized_bootstrap([0., np.nan, 1.], 99, 1)


def test_boundary_null_false_confirmation_is_near_nominal_for_a_skewed_contrast():
    """Report 2 freeze check: truth exactly at the margin."""
    rng = np.random.default_rng(11)
    margin, n, hits, reps = .02, 400, 0, 400
    for k in range(reps):
        sample = rng.exponential(1., size=n) - 1. + margin  # right-skewed, mean exactly at the margin
        hits += ta.primary_decision(ta.studentized_bootstrap(sample, 499, 1000 + k), margin) == 'material_degradation_confirmed'
    assert hits / reps < .05


def test_holm_step_down_and_validation():
    assert ta.holm({'a': .001, 'b': .02, 'c': .04}) == {'a': True, 'b': True, 'c': True}
    assert ta.holm({'a': .001, 'b': .03, 'c': .04}) == {'a': True, 'b': False, 'c': False}
    assert ta.holm({'a': .2, 'b': .001}) == {'b': True, 'a': False}
    with pytest.raises(ValueError):
        ta.holm({'a': 1.5})


def test_exact_miss_summaries_handle_zero_discordance_and_no_positives():
    s = ta.reuse_miss_summary(0, 0, 970)
    assert s['new_miss_rate'] == 0 and s['new_miss_rate_lower95'] == 0 and s['exact_mcnemar_p'] == 1.0
    assert s['new_miss_rate_upper95'] == pytest.approx(1 - .025 ** (1 / 970))
    s = ta.reuse_miss_summary(8, 0, 194)
    assert s['exact_mcnemar_p'] == pytest.approx(2 * .5 ** 8) and 0 < s['new_miss_rate_lower95'] < 8 / 194 < s['new_miss_rate_upper95']
    assert ta.reuse_miss_summary(1, 0, 0) == {'status': 'undefined_no_positives'}
    with pytest.raises(ValueError):
        ta.clopper_pearson(3, 2)


def test_bank_combined_interval_reduces_to_scenario_bootstrap_and_widens_with_bank_spread():
    rng = np.random.default_rng(21)
    scenario = rng.exponential(.07, size=1500)
    same = np.column_stack([scenario] * 4)
    r = ta.bank_combined_interval(same, 999, 3)
    single = ta.studentized_bootstrap(scenario, 999, 3)
    assert r['bank_se'] == 0 and r['lower'] == pytest.approx(single['lower']) and r['upper'] == pytest.approx(single['upper'])
    spread = same + np.array([-.01, 0., .005, .01])
    wide = ta.bank_combined_interval(spread, 999, 3)
    assert wide['lower'] < r['lower'] + .00125 and wide['upper'] - wide['lower'] > r['upper'] - r['lower']
    with pytest.raises(ValueError):
        ta.bank_combined_interval(scenario[:, None], 99, 1)


def test_combined_p_values_cross_alpha_at_the_interval_bounds():
    rng = np.random.default_rng(22)
    d = rng.exponential(.07, size=(1200, 1)) + rng.normal(0, .004, size=(1, 5)) + rng.normal(0, .02, size=(1200, 5))
    r = ta.bank_combined_interval(d, 1999, 4)
    assert ta.combined_one_sided_p(r, r['lower'] - 1e-6, 'greater') <= .025 + 1e-4
    assert ta.combined_one_sided_p(r, r['lower'] + 1e-4, 'greater') > .025
    assert ta.combined_one_sided_p(r, r['upper'] + 1e-6, 'less') <= .025 + 1e-4
    assert ta.combined_one_sided_p(r, r['mean'] + 1, 'greater') == 1.0
    with pytest.raises(ValueError):
        ta.combined_one_sided_p(r, 0., 'both')
