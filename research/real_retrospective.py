"""A01 retrospective real-CDM refit under the frozen Track R analysis choices.

Refits the protocol-family arms on the exposed Kelvins training cohort with the
frozen C grid, iteration cap and strict convergence, using exactly the stored
outer/inner folds of the earlier nested run. Final models selected on the full
training cohort are evaluated once on the exposed historical test split. Every
result is exposed retrospective evidence.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import time
import warnings

import joblib
import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning

from core.features_causal import FEATURE_COLUMNS_CAUSAL
from research.artifacts import ROOT, RUN_ROOT, Run, read_table, sha256, write_json, write_table
from research.evaluate import folds
from research.history import HistoryTransformer, events_from_frame
from research.metrics import loss
from research.models import MonotonePlatt, ProbabilityModel, policy_threshold

CONTRACT = ROOT / 'docs/research/execution/a01_contract.json'
RECALLS = (0.9, 0.95, 0.99)
FINAL_FOLD_SEED = 20261108


def load_contract(path: Path = CONTRACT, require_committed: bool = True) -> dict:
    contract = json.loads(path.read_text(encoding='utf-8'))
    if require_committed:
        committed = subprocess.check_output(['git', 'show', f'HEAD:{path.relative_to(ROOT).as_posix()}'], cwd=ROOT)
        if contract['status'] != 'fixed_before_fitting' or json.loads(committed) != contract:
            raise ValueError('A01 requires the committed fixed contract')
    return contract


def stored_folds(y: np.ndarray, ids: np.ndarray, splits: pd.DataFrame, seed: int):
    """Regenerate the nested folds and require equality with the stored split table."""
    outer = folds(y, 5, seed)
    inner = {k: folds(y[train], 3, seed + k + 1) for k, (train, _) in enumerate(outer)}
    rows = []
    for k, (train, test) in enumerate(outer):
        rows.extend((str(ids[i]), k, -1, 'outer_evaluation') for i in test)
        for j, (_, validation) in enumerate(inner[k]):
            rows.extend((str(ids[train[i]]), k, j, 'inner_validation') for i in validation)
    regenerated = pd.DataFrame(rows, columns=['series_id', 'outer_fold', 'inner_fold', 'role'])
    stored = splits[['series_id', 'outer_fold', 'inner_fold', 'role']].astype({'series_id': str})
    if not regenerated.reset_index(drop=True).equals(stored.reset_index(drop=True)):
        raise ValueError('Regenerated folds differ from the stored split table')
    return outer, inner


def fit_strict(arm, C, seed, X, y, events, max_iter, prepared=None):
    with warnings.catch_warnings():
        warnings.simplefilter('error', ConvergenceWarning)
        model = ProbabilityModel(arm, C, seed, max_iter=max_iter).fit(X, y, events, prepared)
    return model, int(np.max(model.model[-1].n_iter_))


def select(arm, X, y, events, train, inner, grid, seed, max_iter):
    """Inner-CV selection, monotone calibration and training-only thresholds for one training set."""
    oof = {c: np.full(len(train), np.nan) for c in grid}
    iterations = []
    for j, (fit, validation) in enumerate(inner):
        ii, jj = train[fit], train[validation]
        fit_events, val_events = [events[i] for i in ii], [events[i] for i in jj]
        prepared = prepared_val = None
        if arm != 'latest':
            history = HistoryTransformer(arm).fit(fit_events)
            prepared = (history, *history.transform(fit_events))
            prepared_val = history.transform(val_events)
        for c in grid:
            model, n_iter = fit_strict(arm, c, seed + j, X[ii], y[ii], fit_events, max_iter, prepared)
            oof[c][validation] = model.predict(X[jj], val_events, prepared_val)
            iterations.append(n_iter)
    if any(not np.isfinite(q).all() for q in oof.values()):
        raise ValueError('Incomplete inner OOF coverage')
    scores = {c: float(loss(y[train], q).mean()) for c, q in oof.items()}
    chosen = min(grid, key=lambda c: (scores[c], c))
    calibrator = MonotonePlatt().fit(oof[chosen], y[train])
    q_train = calibrator.predict(oof[chosen])
    thresholds = {f'{int(round(100 * r))}': policy_threshold(q_train, y[train], r) for r in RECALLS}
    model, n_iter = fit_strict(arm, chosen, seed, X[train], y[train], [events[i] for i in train], max_iter)
    iterations.append(n_iter)
    return model, calibrator, thresholds, {'C': chosen, 'inner_log_loss': {str(c): v for c, v in scores.items()},
                                           'calibration_slope': calibrator.slope, 'calibration_intercept': calibrator.intercept,
                                           'maximum_iterations': max(iterations), 'thresholds': thresholds}


def predict_frame(model, calibrator, thresholds, X, events, ids, final_risk, y, arm, extra):
    raw = model.predict(X, events)
    q = calibrator.predict(raw)
    out = pd.DataFrame({'series_id': ids, 'arm': arm, 'final_risk': final_risk, 'y': y, 'q': q, 'raw_score': raw, **extra})
    for key, threshold in thresholds.items():
        out[f'threshold_{key}'], out[f'review_{key}'] = threshold, q >= threshold
    if not np.isfinite(out.q).all():
        raise ValueError('Nonfinite prediction')
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    contract = load_contract()
    data, reference = RUN_ROOT / contract['data_run'], RUN_ROOT / contract['reference_run']
    for path in (data, reference):
        if json.loads((path / 'manifest.json').read_text(encoding='utf-8'))['status'] != 'complete':
            raise ValueError(f'Incomplete input run {path.name}')
    inputs = [CONTRACT, data / 'causal_features_train.parquet', data / 'causal_features_test.parquet',
              data / 'visible_train.parquet', data / 'visible_test.parquet', reference / 'splits.parquet',
              reference / 'predictions.parquet']
    config = {**contract, 'contract_sha256': sha256(CONTRACT),
              'contract_commit': subprocess.check_output(['git', 'log', '-1', '--format=%H', '--', str(CONTRACT)], cwd=ROOT, text=True).strip()}
    with Run(args.run_id, 'real_retrospective_refit', config, inputs) as run:
        run.access('eligible Kelvins training outcomes', 'A01 nested refit under frozen choices', 'exposed retrospective')
        run.access('historical Kelvins test outcomes', 'A01 single evaluation of final models', 'exposed; never used for model choice in this project')
        frame = read_table(data / 'causal_features_train.parquet')
        test = read_table(data / 'causal_features_test.parquet')
        events = events_from_frame(read_table(data / 'visible_train.parquet'), frame.series_id.tolist())
        test_events = events_from_frame(read_table(data / 'visible_test.parquet'), test.series_id.tolist())
        columns = ['latest_risk', *[c for c in FEATURE_COLUMNS_CAUSAL if c != 'latest_risk']]
        X, X_test = frame[columns].to_numpy(float), test[columns].to_numpy(float)
        y = (frame.final_risk.to_numpy() >= -6).astype(int)
        y_test = (test.final_risk.to_numpy() >= -6).astype(int)
        ids = frame.series_id.to_numpy()
        if (len(frame), int(y.sum()), len(test), int(y_test.sum())) != (8293, 66, 2167, 150):
            raise ValueError('Cohort counts differ from the audited benchmark')
        seed = 20261009
        outer, inner = stored_folds(y, ids, read_table(reference / 'splits.parquet'), seed)
        grid, max_iter = contract['C'], contract['max_iter']
        oof_rows, test_rows, selections = [], [], []
        for arm in contract['arms']:
            for k, (train, held) in enumerate(outer):
                clock = time.perf_counter()
                model, calibrator, thresholds, record = select(arm, X, y, events, train, inner[k], grid, seed + 100 * k, max_iter)
                oof_rows.append(predict_frame(model, calibrator, thresholds, X[held], [events[i] for i in held], ids[held],
                                              frame.final_risk.to_numpy()[held], y[held], arm, {'outer_fold': k}))
                selections.append({'arm': arm, 'fold': k, **record, 'seconds': time.perf_counter() - clock})
                print('OOF', arm, k, 'C', record['C'], flush=True)
            everything = np.arange(len(frame))
            final_inner = folds(y, 3, FINAL_FOLD_SEED)
            model, calibrator, thresholds, record = select(arm, X, y, events, everything, final_inner, grid, FINAL_FOLD_SEED, max_iter)
            joblib.dump({'model': model, 'calibrator': calibrator, 'thresholds': thresholds, 'columns': columns},
                        run.path / f'final_model_{arm}.joblib')
            test_rows.append(predict_frame(model, calibrator, thresholds, X_test, test_events, test.series_id.to_numpy(),
                                           test.final_risk.to_numpy(), y_test, arm, {'outer_fold': -1}))
            selections.append({'arm': arm, 'fold': 'final', **record})
            print('FINAL', arm, 'C', record['C'], flush=True)
        oof, held_out = pd.concat(oof_rows, ignore_index=True), pd.concat(test_rows, ignore_index=True)
        if len(oof) != 4 * 8293 or len(held_out) != 4 * 2167:
            raise ValueError('Prediction counts disagree with the plan')
        write_table(run.path / 'oof_predictions.parquet', oof)
        write_table(run.path / 'test_predictions.parquet', held_out)
        write_json(run.path / 'selections.json', selections)
        old = read_table(reference / 'predictions.parquet')
        reproduced = []
        for (arm, k), g in oof.groupby(['arm', 'outer_fold']):
            previous = json.loads((reference / f'selection_{arm}_fold{k}.json').read_text())['parameter']
            current = next(s['C'] for s in selections if s['arm'] == arm and s['fold'] == k)
            prior = old[(old.arm == arm) & (old.outer_fold == k)].set_index('series_id').q
            same = bool(current == previous and np.array_equal(g.set_index('series_id').q.reindex(prior.index).to_numpy(), prior.to_numpy()))
            reproduced.append({'arm': arm, 'fold': int(k), 'previous_C': previous, 'C': current, 'identical_predictions': same})
        write_json(run.path / 'reference_reproduction.json', reproduced)
    print('COMPLETE', args.run_id, flush=True)


if __name__ == '__main__':
    main()
