"""Reconstruct both-stage threshold selection and final scores without fitting."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
from core.kelvins_metric import kelvins_score
from research.artifacts import Run, read_table, write_json
from research.metrics import official_metrics
from research.summarize_pilot import audit_run


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--data', type=Path, required=True)
    p.add_argument('--run-id', required=True)
    args = p.parse_args()
    source, data = args.source.resolve(), args.data.resolve()
    audit = audit_run(source)
    with Run(args.run_id, 'two_stage_reconstruction', vars(args) | {
        'source': str(source), 'data': str(data)},
        [source/'manifest.json', data/'causal_features_train.parquet']) as run:
        predictions = read_table(source/'predictions.parquet')
        split = read_table(source/'splits.parquet')
        truth = read_table(data/'causal_features_train.parquet').set_index('series_id').final_risk
        metrics = json.loads((source/'metrics.json').read_text())
        assert predictions.series_id.is_unique and set(predictions.series_id) == set(truth.index)
        checks = []
        for k, g in predictions.groupby('outer_fold'):
            oof = read_table(source/f'threshold_oof_fold{k}.parquet')
            iv = split[(split.outer_fold == k) & (split.inner_fold >= 0)]
            assert oof.series_id.is_unique and iv.series_id.is_unique
            assert set(oof.series_id) == set(iv.series_id)
            assert not set(oof.series_id) & set(g.series_id)
            assert set(oof.series_id) | set(g.series_id) == set(truth.index)
            yt = truth.loc[oof.series_id].to_numpy()
            q, v = oof.classifier_oof.to_numpy(), oof.regressor_oof.to_numpy()
            candidates = np.unique(np.r_[0., np.quantile(q, np.linspace(.8,.9995,60))])
            scores = [kelvins_score(yt, np.where(q >= t, np.clip(v,-6,0), -30.)).score for t in candidates]
            chosen = min(range(len(candidates)), key=lambda i:(scores[i],candidates[i]))
            threshold = float(candidates[chosen])
            assert (g.threshold == threshold).all()
            calculated = np.where(g.classifier_score_uncalibrated >= threshold,
                                  np.clip(g.value_prediction,-6,0), -30.)
            np.testing.assert_array_equal(calculated, g.B5_crossfit)
            checks.append({'fold': int(k), 'threshold': threshold, 'inner_L': float(scores[chosen]),
                           'both_stage_oof_coverage_and_outer_disjointness': True})
        for arm in ('B1','B4_causal','B5_crossfit'):
            assert official_metrics(predictions.final_risk.to_numpy(), predictions[arm].to_numpy()) == metrics['models'][arm]
        write_json(run.path/'verification.json', {'status':'pass', 'source_audit':audit,
            'folds': checks, 'n_events':len(predictions), 'metrics_reconstructed':True,
            'scope':'Artifact reconstruction and fold audit; not an independent scientific review or retraining.'})
        print('PASS: all five thresholds, OOF boundaries and three aggregate official scores reconstructed.')


if __name__ == '__main__':
    main()
