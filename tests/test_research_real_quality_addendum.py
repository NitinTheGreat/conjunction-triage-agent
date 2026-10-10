import numpy as np
import pandas as pd

import research.real_quality_addendum as rq


def test_latest_quality_uses_the_message_closest_to_tca_and_strata_cover_every_event():
    visible = pd.DataFrame({'series_id': ['a', 'a', 'b', 'c'], 'time_to_tca': [5., 2.5, 3., 2.],
                            'c_weighted_rms': [9., 1., np.nan, 3.], 'c_obs_used': [1., 1., 1., 1.], 'c_actual_od_span': [1., 1., 1., 1.]})
    q = rq.latest_quality(visible).set_index('series_id')
    assert q.loc['a', 'chaser_weighted_rms'] == 1. and q.loc['b', 'chaser_fields_missing'] and not q.loc['c', 'chaser_fields_missing']
    labels = rq.strata(q.reset_index(), np.array([2., 2.5]))
    assert labels['b'] == 'missing chaser OD fields' and labels['a'] == 'rms tertile 1' and labels['c'] == 'rms tertile 3'
