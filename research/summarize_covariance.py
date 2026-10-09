"""Audit covariance approximations and compare with immutable control predictions."""
from __future__ import annotations

import argparse
from itertools import product
import json
from pathlib import Path
import shutil

import joblib
import numpy as np
import pandas as pd

from research.artifacts import ROOT, Run, read_table, sha256, write_json
from research.covariance_campaign import check_reference, weight_diagnostics
from research.covariance_proxy import PROXY_ARMS
from research.history import events_from_frame
from research.metrics import class_metrics, loss
from research.models import policy_threshold
from research.summarize_pilot import audit_run, table
from research.summarize_tuning import stability_tables


def proxy_comparisons(predictions):
    """Paired cases within a trial; descriptive ranges across overlapping subsets."""
    rows = []
    for (seed, fraction, regime, bank), g in predictions.groupby(['seed', 'training_fraction', 'regime', 'bank']):
        p = g.pivot(index='series_id', columns=['arm', 'condition'], values='log_loss')
        if p.isna().any().any():
            raise ValueError('Incomplete paired scenario coverage')
        for arm in PROXY_ARMS:
            for comparator in sorted(set(g.arm)-{arm}):
                for condition in sorted(g.condition.unique()):
                    absolute = p[arm, condition]-p[comparator, condition]
                    degradation = absolute-(p[arm, 'no_reuse']-p[comparator, 'no_reuse'])
                    rows.append({'seed': seed, 'training_fraction': fraction, 'regime': regime, 'bank': bank,
                        'arm': arm, 'comparator': comparator, 'condition': condition, 'evaluation_scenarios': len(p),
                        'absolute_difference': float(absolute.mean()), 'absolute_paired_sd': float(absolute.std(ddof=1)),
                        'degradation_difference': float(degradation.mean()),
                        'degradation_paired_sd': float(degradation.std(ddof=1))})
    contrasts = pd.DataFrame(rows)
    ranges = []
    keys = ['regime', 'bank', 'arm', 'comparator', 'condition']
    for key, g in contrasts[contrasts.training_fraction < 1].groupby(keys):
        if not g.seed.is_unique or g.evaluation_scenarios.nunique() != 1:
            raise ValueError('Inconsistent repeated evaluation units')
        row = dict(zip(keys, key), training_repeats=len(g), evaluation_scenarios=int(g.evaluation_scenarios.iloc[0]),
                   proxy_lower_loss_seeds=int((g.absolute_difference < -1e-12).sum()))
        for metric in ('absolute_difference', 'degradation_difference'):
            row.update({f'{metric}_mean': float(g[metric].mean()), f'{metric}_min': float(g[metric].min()),
                        f'{metric}_max': float(g[metric].max())})
        ranges.append(row)
    return contrasts, pd.DataFrame(ranges)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--export', type=Path, required=True)
    args = parser.parse_args()
    if args.export.exists():
        raise FileExistsError('Use a new export destination')
    source = args.source.resolve()
    source_audit = audit_run(source)
    manifest = json.loads((source/'manifest.json').read_text())
    assert manifest['kind'] == 'covariance_proxy_development'
    config = manifest['config']
    reference, cadence = Path(config['reference']), Path(config['source'])
    _, compatibility = check_reference(cadence, reference)
    for name in ('history.py', 'covariance_proxy.py', 'models.py'):
        assert sha256(ROOT/'research'/name) == manifest['code_sha256'][f'research/{name}']
    with Run(args.run_id, 'covariance_proxy_reconstruction', {'source': str(source)},
             [source/'manifest.json', reference/'manifest.json', cadence/'manifest.json']) as run:
        new = read_table(source/'predictions.parquet')
        old = read_table(reference/'predictions.parquet')
        combined = pd.concat([old, new], ignore_index=True)
        assert not combined.duplicated(['seed', 'regime', 'arm', 'bank', 'condition', 'series_id']).any()
        conditions = json.loads((cadence/'manifest.json').read_text())['config']['conditions']
        seeds = [t['seed'] for t in config['trials']]
        arms = config['reused_control_arms']+config['arms']
        expected_cells = set(product(seeds, config['regimes'], arms, ('software', 'bias_stress'), conditions))
        assert set(combined[['seed', 'regime', 'arm', 'bank', 'condition']].itertuples(index=False, name=None)) == expected_cells
        fractions = {t['seed']: t['fraction'] for t in config['trials']}
        np.testing.assert_array_equal(combined.training_fraction, combined.seed.map(fractions))
        assert np.isfinite(combined.q).all() and combined.q.between(0, 1).all()
        banks = {}
        for bank in ('development', 'software', 'bias_stress'):
            c = read_table(cadence/f'cohort_{bank}.parquet')
            messages = read_table(cadence/f'messages_{bank}.parquet')
            for condition, group in messages.groupby('condition', sort=True):
                ev = events_from_frame(group, c.series_id.tolist())
                banks[bank, condition] = c, ev, np.array([[e.raw[-1, 0]] for e in ev])
            if bank != 'development':
                truth = c.set_index('series_id').final_risk
                for _, group in combined[combined.bank == bank].groupby(['seed', 'regime', 'arm', 'condition']):
                    assert set(group.series_id) == set(truth.index)
                    np.testing.assert_array_equal(group.y, (truth.loc[group.series_id] >= -6).astype(int))
        raw_diagnostics, diagnostics = weight_diagnostics(banks)
        pd.testing.assert_frame_equal(raw_diagnostics, read_table(source/'weight_diagnostics.parquet'))
        pd.testing.assert_frame_equal(diagnostics, pd.read_csv(source/'weight_diagnostics.csv'), check_dtype=False, atol=1e-12, rtol=1e-12)
        diagnostics.to_csv(run.path/'weight_diagnostics.csv', index=False)
        selections = json.loads((source/'selections.json').read_text())
        control_selections = json.loads((reference/'selections.json').read_text())
        expected_models = set(product(seeds, config['regimes'], PROXY_ARMS))
        assert len(selections) == len(expected_models)
        assert {(s['seed'], s['regime'], s['arm']) for s in selections} == expected_models
        profiles, selected, equivalences = [], [], []
        for selection in selections:
            seed, regime, arm = selection['seed'], selection['regime'], selection['arm']
            prefix = f'seed{seed}_{regime}_{arm}'
            f = read_table(source/f'training_seed{seed}_{regime}.parquet')
            pd.testing.assert_frame_equal(f, read_table(reference/f'training_seed{seed}_{regime}.parquet'))
            assert (f.groupby('series_id').inner_fold.nunique() == 1).all()
            np.testing.assert_allclose(f.groupby('series_id').event_weight.sum(), 1.)
            oof = read_table(source/f'oof_{prefix}.parquet')
            pd.testing.assert_frame_equal(oof.drop(columns='raw_oof'), f)
            fitted = joblib.load(source/f'model_{prefix}.joblib')
            q = fitted['calibration'].predict(oof.raw_oof.to_numpy())
            assert policy_threshold(q, oof.y.to_numpy(), .95) == fitted['threshold95'] == selection['threshold95']
            scores = {float(c): v for c, v in selection['inner_scores'].items()}
            assert sorted(scores) == config['C']
            assert min(scores, key=lambda c: (scores[c], c)) == selection['C']
            assert np.isclose(np.average(loss(oof.y.to_numpy(), oof.raw_oof.to_numpy()), weights=f.event_weight),
                              scores[selection['C']], atol=1e-14, rtol=0)
            assert selection['convergence_required'] and selection['maximum_observed_iterations'] < config['max_iter']
            assert selection['training_fraction'] == fractions[seed]
            saved = new[(new.seed == seed) & (new.regime == regime) & (new.arm == arm)]
            assert (saved.threshold95 == selection['threshold95']).all()
            if regime == 'no_reuse_only':
                control = next(s for s in control_selections if s['seed'] == seed and
                               s['regime'] == regime and s['arm'] == 'singleton')
                assert selection['C'] == control['C']
                assert abs(selection['threshold95']-control['threshold95']) < 1e-12
                np.testing.assert_allclose(oof.raw_oof,
                    read_table(reference/f'oof_seed{seed}_{regime}_singleton.parquet').raw_oof, rtol=0, atol=1e-12)
                a = saved[saved.condition != 'new_information'].sort_values(['bank', 'condition', 'series_id'])
                b = old[(old.seed == seed) & (old.regime == regime) & (old.arm == 'singleton') &
                        (old.condition != 'new_information')].sort_values(['bank', 'condition', 'series_id'])
                np.testing.assert_allclose(a.q, b.q, rtol=0, atol=1e-12)
                equivalences.append({'seed': seed, 'arm': arm, 'singleton_oof_and_constant_condition_predictions': 'pass'})
            for (bank, condition), group in saved.groupby(['bank', 'condition']):
                c, events, X = banks[bank, condition]
                q = fitted['calibration'].predict(fitted['model'].predict(X, events))
                np.testing.assert_allclose(group.set_index('series_id').loc[c.series_id].q, q, rtol=0, atol=1e-12)
            selected.append({k: v for k, v in selection.items() if k != 'inner_scores'})
            profiles.extend({'seed': seed, 'regime': regime, 'arm': arm, 'C': c, 'inner_oof_log_loss': value,
                             'selected': c == selection['C']} for c, value in scores.items())
        keys = ['seed', 'training_fraction', 'regime', 'arm', 'bank', 'condition']
        assert equivalences == json.loads((source/'equivalence.json').read_text())
        rows = []
        for key, g in combined.groupby(keys):
            np.testing.assert_allclose(g.log_loss, loss(g.y.to_numpy(), g.q.to_numpy()), rtol=0, atol=1e-14)
            np.testing.assert_array_equal(g.review95, g.q >= g.threshold95)
            rows.append(dict(zip(keys, key), **class_metrics(g.y.to_numpy(), g.q.to_numpy(), g.review95.to_numpy())))
        metrics = pd.DataFrame(rows)
        for path, arm_set in ((source, PROXY_ARMS), (reference, config['reused_control_arms'])):
            saved = pd.read_csv(path/'metrics.csv')
            actual = metrics[metrics.arm.isin(arm_set)]
            pd.testing.assert_frame_equal(actual.sort_values(keys).reset_index(drop=True)[saved.columns],
                saved.sort_values(keys).reset_index(drop=True), check_dtype=False, atol=1e-12, rtol=1e-12)
        for (_, _, arm, _), group in combined.groupby(['seed', 'regime', 'arm', 'bank']):
            q = group.pivot(index='series_id', columns='condition', values='q')
            np.testing.assert_allclose(q.no_reuse, q.exact_replay, rtol=0, atol=1e-12)
        contrasts, ranges = proxy_comparisons(combined)
        loss_ranges, _ = stability_tables(metrics)
        for name, frame in (('metrics', metrics), ('selections', pd.DataFrame(selected)),
                            ('candidate_scores', pd.DataFrame(profiles)), ('paired_contrasts', contrasts),
                            ('comparison_ranges', ranges), ('loss_ranges', loss_ranges)):
            frame.to_csv(run.path/f'{name}.csv', index=False)
        audit = {'source_run': source_audit, 'compatibility': compatibility,
            'selected_new_models': len(selections), 'new_prediction_rows': len(new), 'combined_prediction_rows': len(combined),
            'all_new_predictions_reconstructed_from_models': True, 'all_class_metrics_reconstructed': True,
            'all_new_oof_losses_and_thresholds_reconstructed': True, 'weight_diagnostics_reconstructed': True,
            'same_reference_folds_and_scenario_weights': True, 'replay_invariance_reconstructed': True,
            'no_reuse_singleton_equivalences_reconstructed': equivalences,
            'scientific_bank_opened': False,
            'limits': 'Exposed paired scenarios; three overlapping training subsets; no independent scientific replication or published-method reproduction.'}
        write_json(run.path/'audit.json', audit)
        write_json(run.path/'compatibility.json', compatibility)
        reference_seed = next(t['seed'] for t in config['trials'] if t['fraction'] == 1.)
        full = metrics[metrics.seed == reference_seed]
        upper = sum(s['C'] == max(config['C']) for s in selections)
        sections = []
        for bank, condition in product(('software', 'bias_stress'), ('overlap_90', 'new_information')):
            g = full[(full.regime == 'matched_mixture') & (full.bank == bank) & (full.condition == condition)]
            sections += [f'### Matched training / {bank} / {condition}', '',
                table(g, ['arm', 'log_loss', 'brier', 'reviewed', 'fn']), '']
        comparisons = ranges[(ranges.regime == 'matched_mixture') &
            ranges.condition.isin(['overlap_90', 'new_information']) & ranges.comparator.isin(['singleton', 'grouped', 'latest_metadata'])]
        report = f'''# V02 covariance-proxy comparator and ablation

Date: 9 October 2026. Source `{source.name}`; controls `{reference.name}`; reconstruction `{args.run_id}`. **Exploratory development evidence; V02 remains open.** Reserved scientific scenarios remain ungenerated.

## Method and comparison contract

`covariance_trend` fits an unweighted straight line to log diagonal volume versus normalized elapsed visible publication time, then normalizes inverse fitted-volume weights. `covariance_direct` directly normalizes inverse volumes. The volume proxy is `(t_sigma_r²+c_sigma_r²)*(t_sigma_t²+c_sigma_t²)`. Log arithmetic avoids overflow. Both retain the singleton feature width, latest features, canonical message count, missingness, preprocessing and calibrated logistic readout.

This is an aligned radial/tangential diagonal approximation. The simulator has zero normal sigmas; the real allowlist lacks full encounter-plane geometry and correlations. It is **not a reproduction** of Sanchez et al.'s covariance weighting, Dempster–Shafer inference, a physical collision-probability estimator, or an independent-information count. See the compatibility review and saved implementation plan for the input mapping and limitations.

Both modes use uniform weights for invalid/negative sigmas, a nonpositive combined variance, invalid time, fewer than two distinct times, or a log-volume range <=1e-12. Individual zero sigmas are permitted if their combined variance is positive. Infinite source fields are rejected by the common canonicalizer before fitting. No outcome or learned imputation changes message precision weights.

The {len(selections)} new models share all four training trials, both regimes, C={config['C']}, three scenario folds and a {config['max_iter']:,}-iteration cap with the 72 archived control models. All candidate/final fits passed convergence checks; {upper}/{len(selections)} new selections remain at the upper C boundary. Compatibility checks require unchanged data/shared fitting code and exactly unchanged legacy history syntax after removing the two new-mode additions. Cohort and fold tables match the saved reference. No control receives a new tuning opportunity.

## Construction diagnostics before fitting

All three exposed banks and seven conditions were inspected before the first fit, producing {len(raw_diagnostics):,} event/mode diagnostic rows. Every constant-covariance condition reduces exactly to uniform message weighting. Cumulative new-information histories have nonuniform weights. `weight_diagnostics.csv` includes every bank, condition, mode, reason and concentration range. Inverse squared-weight concentration is only a descriptive weight statistic; it is not an effective number of independent observations.

For no-reuse-only training, both approximations reproduce saved singleton selected C, OOF predictions, thresholds and constant-condition forecasts for every trial. Under matched training, new-information histories have changed weighted summaries, so refitted coefficients can change predictions even on constant-covariance evaluation prefixes. Equal feature weights alone do not imply equal fitted predictors across different training designs.

## Full-data reference results

These are the common 1,000-scenario training reference. Each evaluation bank contains 1,000 scenarios: software has 194 positives, bias stress 326. Counts are per bank/condition; enriched synthetic prevalence is not operational workload. Forecast `q` targets final recorded risk class, not collision occurrence. A nominal 95% training-recall threshold is not an evaluation guarantee.

{chr(10).join(sections)}
## Training-subset sensitivity

The three additional trials each use 800 scenarios/144 positives from the same development bank. They overlap and are not independent training-bank replications. `loss_ranges.csv` gives mean/min/max over these three trials only, separate from the full-data reference. Ranges are not confidence intervals. All {len(combined):,} combined prediction rows repeatedly evaluate the same scenarios; they do not increase the independent case count.

Differences below are proxy minus comparator; negative favors the proxy. The count records how many of the three subset trials have strictly lower loss, not a significance test. Every condition, regime and control (including direct-versus-trend) is retained in the CSV exports.

{table(comparisons, ['bank', 'condition', 'arm', 'comparator', 'absolute_difference_mean', 'absolute_difference_min', 'absolute_difference_max', 'proxy_lower_loss_seeds'])}

`paired_contrasts.csv` retains scenario-paired means and standard deviations for absolute loss and no-reuse-to-condition degradation separately in each trial. These support later precision work; no sample size or primary scientific comparison is selected here. Do not pool trial repeats to claim more independent positives or turn exploratory comparisons into confirmatory tests.

## Reconstruction and remaining work

The audit verifies immutable inputs, archived sources and outputs; every prediction case/label and class metric; new selected-OOF losses and thresholds; and all {len(new):,} new forecast probabilities recomputed from their saved models. Weight diagnostics also reconstruct from the visible prefixes. This is artifact verification, not A03 independent scientific review. Compact artifacts retain exact bytes and provenance; model/prediction/source archives stay local and ignored.

This completes the covariance-proxy comparison and direct-weighting ablation on the exposed simulation design. It does not implement the sequence adaptation, provenance-component/oracle ablations, state-fusion diagnostics, independent training-bank uncertainty, or precision design. Real-data proxy evaluation is not claimed. Those limits and remaining grid-boundary choices must be addressed before V03 freezes the scientific study. Preserve unfavorable and collapsed-control results.
'''
        (run.path/'report.md').write_text(report, encoding='utf-8')
    args.export.mkdir(parents=True, exist_ok=False)
    names = ('report.md', 'metrics.csv', 'selections.csv', 'candidate_scores.csv', 'paired_contrasts.csv',
             'comparison_ranges.csv', 'loss_ranges.csv', 'weight_diagnostics.csv', 'audit.json', 'compatibility.json')
    provenance = {'run_id': args.run_id, 'source_runs': [source.name, reference.name],
                  'manifest_sha256': sha256(run.path/'manifest.json'), 'artifacts': {}}
    for name in names:
        shutil.copyfile(run.path/name, args.export/name)
        provenance['artifacts'][name] = sha256(run.path/name)
    write_json(args.export/'provenance.json', provenance)
    print('Exported audited covariance-proxy results:', args.export, flush=True)


if __name__ == '__main__':
    main()
