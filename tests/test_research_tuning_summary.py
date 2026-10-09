import pandas as pd
import pytest

from research.summarize_tuning import stability_tables


def example_metrics():
    rows = []
    for seed in (1, 2, 3):
        for condition in ('no_reuse', 'overlap_90'):
            for arm in ('grouped', 'latest_metadata'):
                value = .2
                if arm == 'grouped' and condition == 'overlap_90':
                    value += {1: -.02, 2: .01, 3: .04}[seed]
                rows.append(dict(seed=seed, training_fraction=.8, regime='matched_mixture',
                    bank='software', condition=condition, arm=arm, n=1000, positives=194,
                    log_loss=value, brier=.1, reviewed=300, fn=4))
    return pd.DataFrame(rows)


def test_seed_ranges_retain_sign_reversal_and_do_not_triple_sample_count():
    ranges, comparisons = stability_tables(example_metrics())
    assert (ranges.evaluation_scenarios == 1000).all()
    assert (ranges.evaluation_positives == 194).all()
    assert (ranges.training_repeats == 3).all()
    result = comparisons[comparisons.condition == 'overlap_90'].iloc[0]
    assert result.absolute_difference_min == pytest.approx(-.02)
    assert result.absolute_difference_max == pytest.approx(.04)
    assert result.absolute_difference_mean == pytest.approx(.01)
    assert result.grouped_lower_loss_seeds == 1


def test_inconsistent_evaluation_denominators_are_rejected():
    frame = example_metrics()
    frame.loc[0, 'n'] = 999
    with pytest.raises(ValueError, match='evaluation units'):
        stability_tables(frame)
