import numpy as np
import pandas as pd
import pytest
from research.data import RAW_FIELDS, visible_records, prospective_membership


def fixture():
    frame = pd.DataFrame({c: [1., 2., 3., 4.] for c in RAW_FIELDS})
    frame['series_id'] = ['train:1'] * 4
    frame['time_to_tca'] = [4., 2., 1., -0.1]
    frame['risk'] = [-7., -6.5, -5., -4.]
    frame['final_risk'] = -4.
    return frame


def test_future_mutation_and_membership_are_separate():
    frame = fixture(); reference = visible_records(frame)
    future = frame.time_to_tca < 2
    mutated = frame.copy(); mutated.loc[future, 'risk'] = 42
    mutated.loc[future, 't_obs_used'] = 1e9
    for variant in (mutated, frame.loc[~future], pd.concat([frame, frame.loc[future]])):
        pd.testing.assert_frame_equal(reference, visible_records(variant))
        assert prospective_membership(frame) == prospective_membership(variant)
    assert 'final_risk' not in reference
    # Positive falsification control: a deliberately full-sequence count changes.
    assert len(frame) != len(frame.loc[~future])


def test_cutoff_ties_missing_and_order():
    frame = fixture(); frame.loc[1, 't_obs_used'] = np.nan
    extra = frame.iloc[[1]].copy(); extra['risk'] = -6.4
    tied = pd.concat([frame, extra], ignore_index=True)
    pd.testing.assert_frame_equal(visible_records(tied), visible_records(tied.iloc[::-1]))
    assert len(visible_records(tied)) == 3
    assert visible_records(tied).t_obs_used.isna().sum() == 2
    with pytest.raises(ValueError):
        visible_records(frame.drop(columns=['c_obs_used']))
