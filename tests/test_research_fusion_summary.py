import pandas as pd
import pytest

from research.state_fusion import FUSION_ARMS
from research.summarize_fusion import paired_state_contrasts


def example():
    rows = []
    for i in range(4):
        for arm in FUSION_ARMS:
            for condition in ('no_reuse', 'overlap_90'):
                value = .1*(i+1)
                if arm == 'gaussian_product' and condition == 'overlap_90':
                    value += [-.1, 0, .1, .2][i]
                rows.append(dict(bank='software', series_id=str(i), arm=arm, condition=condition,
                    squared_error=value, quadratic_error=value*10, ellipse_area95=.2, ellipse_contains95=True))
    return pd.DataFrame(rows)


def test_bootstrap_pairs_cases_and_is_row_order_invariant_without_inflating_n():
    frame = example()
    result = paired_state_contrasts(frame, repeats=100, seed=52)
    pd.testing.assert_frame_equal(result, paired_state_contrasts(frame.sample(frac=1., random_state=1), 100, 52))
    assert set(result.n_independent_scenarios_assumed) == {4}
    chosen = result[(result.arm == 'gaussian_product') & (result.comparator == 'latest') &
                    (result.condition == 'overlap_90') & (result.metric == 'squared_error')].iloc[0]
    assert chosen.difference == pytest.approx(.05)
    assert chosen.ci95_low < chosen.difference < chosen.ci95_high
    no_reuse = result[(result.condition == 'no_reuse') & (result.metric == 'squared_error_degradation')]
    assert (no_reuse[['difference', 'ci95_low', 'ci95_high']] == 0).all().all()


def test_missing_paired_state_case_fails():
    with pytest.raises(ValueError, match='Incomplete paired'):
        paired_state_contrasts(example().iloc[1:], repeats=100)
