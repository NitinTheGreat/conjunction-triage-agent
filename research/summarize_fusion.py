"""Reconstruct state-fusion outcomes and descriptive scenario-paired intervals."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

import numpy as np
import pandas as pd

from research.artifacts import ROOT, Run, read_table, sha256, write_json
from research.fusion_campaign import BANKS, reconstruct_bank, evaluate_prepared
from research.state_fusion import ELLIPSE95, FUSION_ARMS
from research.summarize_pilot import audit_run, table

PAIRS = (tuple((a, 'latest') for a in FUSION_ARMS if a != 'latest') +
         tuple((a, 'oracle_bias_aware') for a in ('gaussian_product', 'prior_once_product', 'covariance_intersection')) +
         (('prior_once_product', 'gaussian_product'), ('oracle_bias_aware', 'oracle_unique')))
ENDPOINTS = ('squared_error', 'quadratic_error', 'ellipse_contains95', 'ellipse_area95', 'squared_error_degradation')


def aggregate_states(frame):
    return frame.groupby(['bank', 'condition', 'arm'], as_index=False).agg(
        n_scenarios=('series_id', 'size'), visible_unique_observations=('visible_unique_observations', 'first'),
        messages=('messages', 'first'), mean_squared_error=('squared_error', 'mean'),
        mean_quadratic_error=('quadratic_error', 'mean'), mean_covariance_trace=('covariance_trace', 'mean'),
        mean_ellipse_area95=('ellipse_area95', 'mean'), ellipse_included=('ellipse_contains95', 'sum'),
        ellipse_inclusion_fraction=('ellipse_contains95', 'mean'))


def paired_state_contrasts(frame, repeats=2000, seed=20261040):
    """One common scenario bootstrap per bank; never pool condition replicates."""
    if repeats < 2 or not set(frame.bank) <= set(BANKS):
        raise ValueError('Expected supported banks and at least two bootstrap replicates')
    rows = []
    for bank_index, bank in enumerate(BANKS):
        g = frame[frame.bank == bank]
        if g.empty:
            continue
        pivots = {metric: g.pivot(index='series_id', columns=['arm', 'condition'], values=metric).astype(float)
                  for metric in ENDPOINTS if metric != 'squared_error_degradation'}
        expected = {(arm, condition) for arm in FUSION_ARMS for condition in g.condition.unique()}
        if ('no_reuse' not in set(g.condition) or any(set(p.columns) != expected or p.isna().any().any() for p in pivots.values())):
            raise ValueError('Incomplete paired scenario coverage')
        n = len(next(iter(pivots.values())))
        if n < 2:
            raise ValueError('At least two independent scenarios required')
        columns, contrasts = [], []
        for arm, comparator in PAIRS:
            for condition in sorted(g.condition.unique()):
                for metric in ENDPOINTS:
                    p = pivots['squared_error' if metric == 'squared_error_degradation' else metric]
                    difference = p[arm, condition]-p[comparator, condition]
                    if metric == 'squared_error_degradation':
                        difference = difference-(p[arm, 'no_reuse']-p[comparator, 'no_reuse'])
                    columns.append((arm, comparator, condition, metric))
                    contrasts.append(difference.to_numpy())
        values = np.column_stack(contrasts)
        rng = np.random.default_rng(seed+bank_index)
        # Multinomial counts are equivalent to sampling n paired scenario rows.
        resamples = rng.multinomial(n, np.full(n, 1/n), size=repeats).astype(float)/n
        bootstrap = resamples @ values
        low, high = np.quantile(bootstrap, [.025, .975], axis=0)
        for j, (arm, comparator, condition, metric) in enumerate(columns):
            rows.append({'bank': bank, 'condition': condition, 'arm': arm, 'comparator': comparator,
                'metric': metric, 'difference': float(values[:, j].mean()),
                'paired_sd': float(values[:, j].std(ddof=1)), 'ci95_low': float(low[j]), 'ci95_high': float(high[j]),
                'n_independent_scenarios_assumed': n, 'bootstrap_replicates': repeats, 'bootstrap_seed': seed+bank_index})
    return pd.DataFrame(rows)


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
    assert manifest['kind'] == 'state_fusion_development'
    config = manifest['config']
    cadence, truth_source = Path(config['source']), Path(config['truth_source'])
    input_audits = [audit_run(cadence), audit_run(truth_source)]
    for name in ('state_fusion.py', 'fusion_campaign.py', 'simulation.py', 'history.py', 'data.py'):
        assert sha256(ROOT/'research'/name) == manifest['code_sha256'][f'research/{name}']
    with Run(args.run_id, 'state_fusion_reconstruction', {'source': str(source)},
             [source/'manifest.json', cadence/'manifest.json', truth_source/'manifest.json']) as run:
        state_frames, ci_frames, reconstruction = [], [], []
        seen = set()
        for bank in config['banks']:
            cohort = read_table(cadence/f'cohort_{bank}.parquet')
            pd.testing.assert_frame_equal(cohort, read_table(truth_source/f'cohort_{bank}.parquet'))
            assert not seen & set(cohort.series_id)
            seen.update(cohort.series_id)
            with np.load(truth_source/f'truth_{bank}.npz', allow_pickle=False) as truth:
                messages, prepared = reconstruct_bank(cohort, read_table(cadence/f'messages_{bank}.parquet'),
                    read_table(cadence/f'lineage_{bank}.parquet'), truth['states'], truth['observations'], bank)
            pd.testing.assert_frame_equal(messages, read_table(source/f'message_states_{bank}.parquet'),
                                          check_exact=True)
            regenerated, ci = evaluate_prepared(prepared)
            saved = read_table(source/f'estimates_{bank}.parquet')
            pd.testing.assert_frame_equal(regenerated, saved, check_exact=True)
            pd.testing.assert_frame_equal(ci, read_table(source/f'ci_{bank}.parquet'), check_exact=True)
            assert not saved.duplicated(['series_id', 'condition', 'arm']).any()
            expected = {(sid, condition, arm) for sid in cohort.series_id
                        for condition in config['conditions'] for arm in FUSION_ARMS}
            assert set(saved[['series_id', 'condition', 'arm']].itertuples(index=False, name=None)) == expected
            state_frames.append(saved); ci_frames.append(ci)
            reconstruction.append({'bank': bank, 'scenarios': len(cohort), 'canonical_messages': len(messages),
                                   'estimate_rows': len(saved), 'all_values_exactly_reconstructed': True})
            print('AUDITED', bank, len(saved), 'state rows', flush=True)
        states, ci = pd.concat(state_frames, ignore_index=True), pd.concat(ci_frames, ignore_index=True)
        metrics = aggregate_states(states)
        contrasts = paired_state_contrasts(states, config['bootstrap']['replicates'], config['bootstrap']['seed'])
        counts = ci.assign(nonzero_weights=ci.weights.map(lambda value: int((np.asarray(json.loads(value)) > 0).sum())))
        ci_summary = counts.groupby(['bank', 'condition', 'method'], as_index=False).agg(
            scenarios=('series_id', 'size'), messages=('messages', 'first'),
            visible_unique_observations=('visible_unique_observations', 'first'),
            nonzero_weights_min=('nonzero_weights', 'min'), nonzero_weights_max=('nonzero_weights', 'max'),
            maximum_optimality_gap=('optimality_gap', 'max'))
        metrics.to_csv(run.path/'metrics.csv', index=False)
        contrasts.to_csv(run.path/'paired_contrasts.csv', index=False)
        ci_summary.to_csv(run.path/'ci_diagnostics.csv', index=False)
        pd.DataFrame(reconstruction).to_csv(run.path/'reconstruction.csv', index=False)
        audit = {'source_run': source_audit, 'input_runs': input_audits, 'banks': reconstruction,
            'all_state_estimates_and_metrics_exactly_reconstructed': True,
            'original_messages_risk_distance_and_sigmas_reconstructed': True,
            'visible_observation_boundary_max_id': 59, 'replay_disjoint_prior_once_and_oracle_identities': 'pass',
            'all_ci_weights_and_diagnostics_reconstructed': True, 'ellipse_chi2_reference_threshold': ELLIPSE95,
            'bootstrap': config['bootstrap'], 'scientific_bank_opened': False,
            'limits': 'Same-workflow reconstruction, not independent scientific review. Unweighted enriched static stress population, not real operational calibration; no class-forecast efficacy.'}
        write_json(run.path/'audit.json', audit)
        sections = []
        for bank in ('software', 'bias_stress'):
            for condition in ('no_reuse', 'overlap_90', 'solution_reissue', 'new_information', 'burst_reissue'):
                g = metrics[(metrics.bank == bank) & (metrics.condition == condition)]
                sections += [f'### {bank} / {condition}', '', table(g, ['arm', 'mean_squared_error',
                    'mean_quadratic_error', 'mean_ellipse_area95', 'ellipse_included', 'n_scenarios']), '']
        shown = contrasts[(contrasts.bank.isin(['software', 'bias_stress'])) &
            (contrasts.condition.isin(['overlap_90', 'solution_reissue', 'new_information'])) &
            (contrasts.comparator == 'latest') & (contrasts.metric == 'squared_error')]
        report = f'''# V02 state-fusion and visible-observation oracle diagnostics

Date: 9 October 2026. Source `{source.name}`, reconstruction `{args.run_id}`. **Exposed development evidence; no reserved scientific outcomes generated.** This is a static Gaussian state-estimation diagnostic, separate from class forecasting and orbital operations.

## Design and inputs

Six arms compare latest, a product of message Gaussians, the product with the common prior counted once, basic precision-weighted covariance intersection (CI), the union-of-visible-observations oracle omitting bias, and the same oracle using the known bias covariance. Ordinary controls receive message means/covariances, not observation IDs or latent truth. Only the labeled oracles receive lineage and the bias-aware oracle receives B. The known prior is N(0,2.25 I); observation noise is 0.09 I. Bias stress adds common B=0.01 I but input message covariances omit it.

Preflight reconstructs {sum(r['canonical_messages'] for r in reconstruction):,} canonical messages from immutable observation windows, checking saved risk, miss distance, sigmas, ordering and availability before fusion. IDs 60-79 occur after the visible cutoff and are forbidden in every state estimate. The lineage union changes by condition (60 no reuse, 35 partial overlap, 15 heavy overlap, 10 solution reissue, 60 cumulative new information/burst reissue). The latest message is matched across the original reuse variants. There are 1,000 latent scenarios per bank; {len(states):,} arm/condition records do not increase that sample count. Banks are reported separately.

The ordinary product sums precisions and information vectors; the prior-once control subtracts m-1 copies of the common prior precision. The latter recovers the visible oracle under disjoint observations but still double-counts overlapping likelihood information. CI averages precisions on the simplex, minimizing log determinant of its covariance. Exact identical-covariance ties use uniform weights; isotropic inputs select the smallest variance, sharing exact minimum ties. General inputs use the prespecified checked SLSQP solver. This is the basic CI family, not OCI's general optimization framework or a reproduction of its experiments. The implementation contract records formulas, tests and source context.

## Structural collapses and scope

All campaign message covariances are isotropic. Equal-covariance conditions therefore use the declared uniform CI tie rule; cumulative new information selects the latest estimate, which already uses the complete visible union. These are checked identities, not learned overlap detection or evidence of an optimization advantage. The general anisotropic solver is exercised by analytic unit tests only. In solution reissue, CI retains the latest covariance, while a product repeatedly counts the same solution. The separate prior correction isolates shared-prior reuse from observation reuse.

Exact retransmissions are canonicalized with the existing source-time convention for every control. Reissued solutions at distinct publication times remain distinct inputs. CI tie weights can therefore change the mean under unequal repeat counts, even while its covariance stays the same. No unknown-correlation guarantee is transferred to inputs that omit shared-bias covariance.

## State metrics and population

Squared Euclidean state error and covariance trace have units m². The error quadratic form is e'P^-1 e (dimensionless). A nominal Gaussian-reference 95% ellipse uses threshold chi2_2(0.95)={ELLIPSE95:.12f}; area is pi*threshold*sqrt(det P), in m². `ellipse_included` counts latent states inside this region. It is an empirical stress diagnostic, not a claim of 95% coverage for the enriched sampling population. All displayed summaries are **unweighted** under the saved mixture; no wide-prior population or operational calibration claim is made.

No fused disk probability or class q is scored here. Latent state error, final recorded-risk forecasting, physical collision occurrence and maneuver utility remain different endpoints. An oracle state improvement does not by itself establish better class forecasting.

{chr(10).join(sections)}
## Paired descriptive uncertainty

Differences are arm minus comparator; lower squared error favors the arm. All arms/conditions share the same 2,000 scenario-multinomial bootstrap resamples within each bank, with base seed 20261040 and the recorded bank offset. Intervals are marginal percentile summaries of these exposed scenarios, without multiplicity adjustment or a confirmatory significance claim. There are no training repetitions in this deterministic diagnostic. Repeated messages, conditions and methods are not new independent units.

{table(shown, ['bank', 'condition', 'arm', 'difference', 'ci95_low', 'ci95_high', 'n_independent_scenarios_assumed'])}

The complete CSV retains all ten prespecified arm/comparator pairs, all seven conditions, all three banks and five endpoints, including paired squared-error degradation relative to no reuse. Ellipse inclusion differences are probability-point fractions; a higher inclusion fraction can simply reflect a much larger uncertainty region. Assess error, area and inclusion together. These intervals are descriptive, not a safety certificate or a primary scientific test.

## Verification and next work

All saved state means/covariances, errors, metrics and CI weights were reconstructed exactly from the original visible observations; source/input/output/archive hashes and case coverage passed. Disjoint-prior-once recovery, replay invariance, bias-free oracle equality and cumulative-information CI/latest/oracle collapses pass. Fixed analytic tests separately check anisotropic CI and full-joint shared-bias conditioning. This is artifact reconstruction within the same workflow, not A03 independent scientific review.

The result bundle contains aggregate metrics, paired contrasts, CI branches/ties, reconstruction counts and an audit with byte hashes. Bulk state/message records and exact source archives remain local/ignored. The study is a static toy model with enriched sampling and exposed outcomes. It does not complete the sequence adaptation, observable-provenance component ablations, independent training-bank uncertainty or precision planning. V02 and scientific freeze V03 remain open. Preserve negative results and structural collapses when choosing the eventual paper claim.
'''
        (run.path/'report.md').write_text(report, encoding='utf-8')
    args.export.mkdir(parents=True, exist_ok=False)
    names = ('report.md', 'metrics.csv', 'paired_contrasts.csv', 'ci_diagnostics.csv', 'reconstruction.csv', 'audit.json')
    provenance = {'run_id': args.run_id, 'source_runs': [source.name],
                  'manifest_sha256': sha256(run.path/'manifest.json'), 'artifacts': {}}
    for name in names:
        shutil.copyfile(run.path/name, args.export/name)
        provenance['artifacts'][name] = sha256(run.path/name)
    write_json(args.export/'provenance.json', provenance)
    print('Exported reconstructed state-fusion results:', args.export, flush=True)


if __name__ == '__main__':
    main()
