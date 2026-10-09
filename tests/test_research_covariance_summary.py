import pandas as pd
import pytest

from research.summarize_covariance import proxy_comparisons


def predictions():
    rows = []
    for seed in (1, 2, 3):
        for scenario in range(4):
            for arm in ('covariance_trend', 'covariance_direct', 'singleton'):
                for condition in ('no_reuse', 'overlap_90'):
                    value = .2 + .01*scenario
                    if arm == 'covariance_trend' and condition == 'overlap_90':
                        value += {1: -.03, 2: .01, 3: .02}[seed] + .001*scenario
                    rows.append(dict(seed=seed, training_fraction=.8, regime='matched_mixture',
                        bank='software', series_id=str(scenario), arm=arm, condition=condition, log_loss=value))
    return pd.DataFrame(rows)


def test_paired_proxy_ranges_keep_reversals_and_do_not_multiply_case_count():
    contrasts, ranges = proxy_comparisons(predictions())
    assert set(contrasts.evaluation_scenarios) == {4}
    assert set(ranges.evaluation_scenarios) == {4}
    assert set(ranges.training_repeats) == {3}
    row = ranges[(ranges.arm == 'covariance_trend') & (ranges.comparator == 'singleton') &
                 (ranges.condition == 'overlap_90')].iloc[0]
    assert row.absolute_difference_min == pytest.approx(-.0285)
    assert row.absolute_difference_max == pytest.approx(.0215)
    assert row.proxy_lower_loss_seeds == 1
    assert row.degradation_difference_mean == pytest.approx(row.absolute_difference_mean)


def test_incomplete_scenario_pairing_fails_instead_of_silently_averaging():
    with pytest.raises(ValueError, match='Incomplete paired'):
        proxy_comparisons(predictions().iloc[1:])
