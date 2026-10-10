import numpy as np
import pandas as pd
import pytest
from sklearn.exceptions import ConvergenceWarning

import research.real_retrospective as rr
from research.evaluate import folds
from research.history import Event


def split_table(y, ids, seed):
    outer = folds(y, 5, seed)
    rows = []
    for k, (train, test) in enumerate(outer):
        rows += [(str(ids[i]), k, -1, 'outer_evaluation') for i in test]
        for j, (_, validation) in enumerate(folds(y[train], 3, seed + k + 1)):
            rows += [(str(ids[train[i]]), k, j, 'inner_validation') for i in validation]
    return pd.DataFrame(rows, columns=['series_id', 'outer_fold', 'inner_fold', 'role'])


def test_stored_folds_must_match_the_split_table_exactly():
    y = np.r_[np.ones(20, int), np.zeros(80, int)]
    ids = np.array([f'e{i}' for i in range(100)])
    table = split_table(y, ids, 7)
    outer, inner = rr.stored_folds(y, ids, table, 7)
    assert len(outer) == 5 and all(len(v) == 3 for v in inner.values())
    with pytest.raises(ValueError, match='differ'):
        rr.stored_folds(y, ids, table.assign(inner_fold=table.inner_fold.where(table.index != 5, 9)), 7)
    with pytest.raises(ValueError, match='differ'):
        rr.stored_folds(y, ids, split_table(y, ids, 8), 7)


def test_strict_fit_turns_nonconvergence_into_failure_and_frames_have_thresholds():
    rng = np.random.default_rng(1)
    X = rng.normal(size=(120, 1))
    y = (X[:, 0] + rng.normal(0, .5, 120) > .8).astype(int)
    events = [Event(f'e{i}', np.empty((0, 0))) for i in range(120)]
    with pytest.raises(ConvergenceWarning):
        rr.fit_strict('latest', 1000., 1, X, y, events, max_iter=1)
    model, n_iter = rr.fit_strict('latest', 1., 1, X, y, events, max_iter=1000)
    from research.models import MonotonePlatt
    calibrator = MonotonePlatt().fit(model.predict(X, events), y)
    frame = rr.predict_frame(model, calibrator, {'95': .2}, X, events, np.arange(120), np.zeros(120), y, 'latest', {'outer_fold': 0})
    assert {'threshold_95', 'review_95'} <= set(frame.columns) and frame.review_95.dtype == bool and n_iter >= 1
