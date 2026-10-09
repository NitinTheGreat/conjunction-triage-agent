"""Reconstruct component candidates, selected forecasts and paired mechanisms."""
from __future__ import annotations

import argparse
from itertools import product
import json
from pathlib import Path
import shutil

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone

from research.artifacts import ROOT, Run, read_table, sha256, write_json
from research.component_campaign import attach_events, prepare_banks, references, validate_splits
from research.components import ARMS, ComponentTransformer, kept_columns
from research.metrics import class_metrics, loss
from research.models import MonotonePlatt, policy_threshold
from research.simulation_regimes import scenario_folds, training_rows
from research.summarize_pilot import audit_run, table
from research.summarize_tuning import stability_tables
from research.tuning_stability import evaluate_arm


def paired_comparisons(predictions, arms=ARMS):
    """Absolute/degradation differences; conditional-positive denominator for misses."""
    rows=[]
    for key,g in predictions.groupby(['seed','training_fraction','regime','bank']):
        y=g.groupby('series_id').y
        if (y.nunique()!=1).any():raise ValueError('Paired label mismatch')
        y=y.first()
        g=g.assign(brier=np.square(g.q-g.y),reviewed=g.review95.astype(float),
                   missed=(g.y.eq(1)&~g.review95.astype(bool)).astype(float))
        pivots={m:g.pivot(index='series_id',columns=['arm','condition'],values=m) for m in ('log_loss','brier','reviewed','missed')}
        if any(p.isna().any().any() for p in pivots.values()):raise ValueError('Incomplete paired cases')
        for arm in arms:
            for comparator in sorted(set(g.arm)-{arm}):
                for condition in sorted(g.condition.unique()):
                    row=dict(zip(['seed','training_fraction','regime','bank'],key),arm=arm,comparator=comparator,
                        condition=condition,evaluation_scenarios=len(y),positives=int(y.sum()))
                    for metric,p in pivots.items():
                        absolute=p[arm,condition]-p[comparator,condition]
                        degradation=absolute-(p[arm,'no_reuse']-p[comparator,'no_reuse'])
                        if metric=='missed':absolute,degradation=absolute[y.eq(1)],degradation[y.eq(1)]
                        row.update({f'{metric}_absolute_difference':float(absolute.mean()),f'{metric}_absolute_paired_sd':float(absolute.std(ddof=1)),
                            f'{metric}_degradation_difference':float(degradation.mean()),f'{metric}_degradation_paired_sd':float(degradation.std(ddof=1))})
                    rows.append(row)
    contrasts=pd.DataFrame(rows);ranges=[];keys=['regime','bank','arm','comparator','condition']
    for key,g in contrasts[contrasts.training_fraction<1].groupby(keys):
        if not g.seed.is_unique or g.evaluation_scenarios.nunique()!=1:raise ValueError('Invalid trial units')
        row=dict(zip(keys,key),training_repeats=len(g),evaluation_scenarios=int(g.evaluation_scenarios.iloc[0]),
                 component_lower_loss_seeds=int((g.log_loss_absolute_difference < -1e-12).sum()))
        for metric in ('log_loss','brier','reviewed','missed'):
            for contrast in ('absolute','degradation'):
                name=f'{metric}_{contrast}_difference'
                for stat in ('mean','min','max'):row[f'{name}_{stat}']=float(getattr(g[name],stat)())
        ranges.append(row)
    return contrasts,pd.DataFrame(ranges)


def verify_transform(actual,expected):
    assert actual.arm==expected.arm and actual.base.mode==expected.base.mode
    np.testing.assert_array_equal(actual.columns,kept_columns(expected.arm))
    for owner,attributes in [('imputer',('statistics_',)),('scaler',('center_','scale_'))]:
        for attribute in attributes:
            np.testing.assert_array_equal(getattr(getattr(actual.base,owner),attribute),getattr(getattr(expected.base,owner),attribute))


def reconstruct_selection(source,selection,frame,events,splits,grid,max_iter):
    validate_splits(frame,events,splits)
    seed,regime,arm=(selection[k] for k in ('seed','regime','arm'));prefix=f'seed{seed}_{regime}_{arm}'
    assert selection['training_scenarios']==frame.series_id.nunique() and selection['training_variant_rows']==len(frame)
    assert selection['objective_weight_sum']==float(frame.event_weight.sum())
    candidates=read_table(source/f'candidates_{prefix}.parquet')
    assert len(candidates)==len(frame)*len(grid) and set(candidates.C)==set(grid)
    oof={c:np.full(len(frame),np.nan) for c in grid};records=[]
    for k,(fit,valid) in enumerate(splits):
        ef,ev=[events[i] for i in fit],[events[i] for i in valid]
        transform=ComponentTransformer(arm).fit(ef);prepared=transform.transform(ef);pv=transform.transform(ev)
        readout=None
        for c in grid:
            name=f'{prefix}_c{c:g}_fold{k}';model=joblib.load(source/f'model_{name}.joblib')
            record=json.loads((source/f'fit_{name}.json').read_text())
            verify_transform(model.history,transform)
            assert model.arm==arm and model.parameter==c and model.seed==seed+k and model.max_iter==max_iter
            classifier=model.model[-1]
            assert classifier.C==c and classifier.random_state==seed+k and classifier.max_iter==max_iter
            assert np.isfinite(classifier.coef_).all() and np.isfinite(classifier.intercept_).all()
            assert record['status']=='complete' and record['iterations']==int(classifier.n_iter_.max())<max_iter
            assert record['C']==c and record['seed']==seed+k and record['fold']==k
            assert record['fit_rows']==len(fit) and record['valid_rows']==len(valid)
            assert record['fit_scenarios']==frame.iloc[fit].series_id.nunique() and record['valid_scenarios']==frame.iloc[valid].series_id.nunique()
            assert record['design_rows']==len(prepared[0]) and record['design_columns']==prepared[0].shape[1]
            np.testing.assert_allclose(record['objective_weight_sum'],frame.iloc[fit].series_id.nunique(),atol=1e-9,rtol=0)
            if readout is None:readout=clone(model.model[:-1]).fit(prepared[0])
            np.testing.assert_array_equal(model.model[0].statistics_,readout[0].statistics_)
            for attr in ('mean_','var_','scale_'):np.testing.assert_array_equal(getattr(model.model[1],attr),getattr(readout[1],attr))
            q=model.predict(np.zeros((len(valid),1)),ev,prepared=pv)
            recorded=read_table(source/f'validation_{name}.parquet')
            pd.testing.assert_frame_equal(recorded.drop(columns=['raw_oof','row_index']),frame.iloc[valid].reset_index(drop=True))
            np.testing.assert_array_equal(recorded.row_index,valid);np.testing.assert_array_equal(recorded.raw_oof,q)
            oof[c][valid]=q;records.append({'trial_seed':seed,'regime':regime,**record})
    scores={}
    for c,q in oof.items():
        rows=candidates[candidates.C==c].reset_index(drop=True)
        pd.testing.assert_frame_equal(rows.drop(columns=['C','raw_oof']),frame)
        np.testing.assert_array_equal(rows.raw_oof,q)
        scores[str(c)]=float(np.average(loss(frame.y.to_numpy(),q),weights=frame.event_weight))
    assert scores==selection['inner_scores']
    chosen=min(grid,key=lambda c:(scores[str(c)],c));assert chosen==selection['C']
    calibration=MonotonePlatt().fit(oof[chosen],frame.y.to_numpy())
    assert calibration.slope==selection['calibration_slope'] and calibration.intercept==selection['calibration_intercept']
    assert policy_threshold(calibration.predict(oof[chosen]),frame.y.to_numpy(),.95)==selection['threshold95']
    model=joblib.load(source/selection['checkpoint']);transform=ComponentTransformer(arm).fit(events)
    verify_transform(model.history,transform)
    assert model.arm==arm and model.seed==seed and model.parameter==chosen and model.max_iter==max_iter
    record=json.loads((source/selection['checkpoint'].replace('model_','fit_',1).replace('.joblib','.json')).read_text())
    assert record['status']=='complete' and record['seed']==seed and record['C']==chosen and record['fold']=='refit'
    assert record['fit_rows']==len(frame) and record['valid_rows']==0 and record['valid_scenarios']==0
    assert record['fit_scenarios']==frame.series_id.nunique()
    np.testing.assert_allclose(record['objective_weight_sum'],frame.series_id.nunique(),atol=1e-9,rtol=0)
    assert record['iterations']==int(model.model[-1].n_iter_.max())<max_iter
    prepared=transform.transform(events);readout=clone(model.model[:-1]).fit(prepared[0])
    np.testing.assert_array_equal(model.model[0].statistics_,readout[0].statistics_)
    for attr in ('mean_','var_','scale_'):np.testing.assert_array_equal(getattr(model.model[1],attr),getattr(readout[1],attr))
    assert record['design_columns']==prepared[0].shape[1] and record['design_rows']==len(prepared[0])
    records.append({'trial_seed':seed,'regime':regime,**record})
    assert len(records)==selection['completed_training_fits'] and max(r['iterations'] for r in records)==selection['maximum_observed_iterations']
    return {'model':model,'calibration':calibration,'threshold95':selection['threshold95']},records,oof[chosen]


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--run-id',required=True);parser.add_argument('--export',type=Path,required=True);args=parser.parse_args()
    if args.export.exists():raise FileExistsError(args.export)
    source=args.source.resolve();source_audit=audit_run(source);manifest=json.loads((source/'manifest.json').read_text(encoding='utf-8'))
    assert manifest['kind']=='provenance_component_development';config=manifest['config'];paths,compatibility=references(config)
    for name in ('components.py','component_campaign.py','history.py','models.py','data.py','metrics.py'):
        assert sha256(ROOT/'research'/name)==manifest['code_sha256'][f'research/{name}']
    cadence,reference=paths['source_run'],paths['reference_run']
    with Run(args.run_id,'provenance_component_reconstruction',{'source':str(source)},[source/'manifest.json',*[p/'manifest.json' for p in paths.values()]]) as run:
        banks,diagnostics=prepare_banks(cadence)
        pd.testing.assert_frame_equal(diagnostics,read_table(source/'lineage_diagnostics.parquet'))
        diagnostic_summary=diagnostics.groupby(['bank','condition'],as_index=False).agg(cases=('series_id','size'),
            messages=('canonical_messages','sum'),uniform_cases=('uniform','sum'),unique_observations_min=('unique_visible_observations','min'),
            unique_observations_max=('unique_visible_observations','max'),weight_min=('weight_min','min'),weight_max=('weight_max','max'),
            uniform_l1_min=('uniform_l1','min'),uniform_l1_max=('uniform_l1','max'))
        new=read_table(source/'predictions.parquet')
        controls=[read_table(paths[k]/'predictions.parquet') for k in ('reference_run','covariance_run','sequence_run')]
        combined=pd.concat([*controls,new],ignore_index=True)
        selections=json.loads((source/'selections.json').read_text());old_selections=json.loads((reference/'selections.json').read_text())
        assert len(selections)==config['planned_selected_models']
        assert {(s['seed'],s['regime'],s['arm']) for s in selections}==set(product([t['seed'] for t in config['trials']],config['regimes'],ARMS))
        messages=read_table(cadence/'messages_development.parquet');fits=[];profiles=[];equivalences=[]
        for selection in selections:
            seed,regime,arm=(selection[k] for k in ('seed','regime','arm'));cohort=read_table(reference/f'cohort_seed{seed}.parquet')
            frame,_,_=training_rows(cohort,messages,config['regimes'][regime]);splits=scenario_folds(frame,config['inner_folds'],seed)
            membership=frame.assign(inner_fold=-1)
            for k,(_,valid) in enumerate(splits):membership.loc[valid,'inner_fold']=k
            for directory in (reference,source):pd.testing.assert_frame_equal(membership,read_table(directory/f'training_seed{seed}_{regime}.parquet'))
            events=attach_events(frame,banks,arm=='oracle_lineage_weight')
            saved,records,oof=reconstruct_selection(source,selection,frame,events,splits,config['C'],config['max_iter']);fits.extend(records)
            evaluation={key:(value[0],value[2 if arm=='oracle_lineage_weight' else 1],value[3]) for key,value in banks.items() if key[0]!='development'}
            actual=evaluate_arm(saved,evaluation,seed,selection['training_fraction'],regime,arm)
            recorded=new[(new.seed==seed)&(new.regime==regime)&(new.arm==arm)].reset_index(drop=True)
            pd.testing.assert_frame_equal(actual,recorded,check_exact=True)
            if arm=='oracle_lineage_weight' and regime=='no_reuse_only':
                old=next(s for s in old_selections if s['seed']==seed and s['regime']==regime and s['arm']=='singleton')
                assert selection['C']==old['C'] and selection['threshold95']==old['threshold95']
                np.testing.assert_array_equal(oof,read_table(reference/f'oof_seed{seed}_{regime}_singleton.parquet').raw_oof)
                a=actual[actual.condition.isin(['no_reuse','exact_replay','solution_reissue'])].sort_values(['bank','condition','series_id'])
                old_q=controls[0];b=old_q[(old_q.seed==seed)&(old_q.regime==regime)&(old_q.arm=='singleton')&old_q.condition.isin(['no_reuse','exact_replay','solution_reissue'])].sort_values(['bank','condition','series_id'])
                np.testing.assert_array_equal(a.q,b.q);equivalences.append({'seed':seed,'singleton_equivalence':'pass'})
            profiles.extend({'seed':seed,'regime':regime,'arm':arm,'C':float(c),'inner_oof_log_loss':score,'selected':float(c)==selection['C']} for c,score in selection['inner_scores'].items())
            print('RECONSTRUCTED',seed,regime,arm,flush=True)
        assert len(fits)==config['planned_training_fits']==len(list(source.glob('fit_*.json')))==len(list(source.glob('model_*.joblib')))
        assert len(new)==config['planned_prediction_rows']
        keys=['seed','training_fraction','regime','arm','bank','condition'];arms=sorted(combined.arm.unique());assert len(arms)==17
        expected=set(product([t['seed'] for t in config['trials']],config['regimes'],arms,('software','bias_stress'),sorted({c for b,c in banks})))
        assert set(combined[['seed','regime','arm','bank','condition']].itertuples(index=False,name=None))==expected
        assert not combined.duplicated(['seed','regime','arm','bank','condition','series_id']).any()
        np.testing.assert_array_equal(combined.training_fraction,combined.seed.map({t['seed']:t['fraction'] for t in config['trials']}))
        metrics=[]
        for key,g in combined.groupby(keys):
            truth=banks[key[-2],key[-1]][0].set_index('series_id').final_risk
            assert set(g.series_id)==set(truth.index)
            np.testing.assert_array_equal(g.y,(truth.loc[g.series_id]>=-6).astype(int))
            assert np.isfinite(g.q).all() and g.q.between(0,1).all()
            np.testing.assert_allclose(g.log_loss,loss(g.y.to_numpy(),g.q.to_numpy()),atol=1e-14,rtol=0)
            np.testing.assert_array_equal(g.review95,g.q>=g.threshold95)
            metrics.append(dict(zip(keys,key),**class_metrics(g.y.to_numpy(),g.q.to_numpy(),g.review95.to_numpy())))
        metrics=pd.DataFrame(metrics)
        for directory in (source,*[paths[k] for k in ('reference_run','covariance_run','sequence_run')]):
            old=pd.read_csv(directory/'metrics.csv');actual=metrics[metrics.arm.isin(old.arm.unique())]
            pd.testing.assert_frame_equal(actual.sort_values(keys).reset_index(drop=True)[old.columns],old.sort_values(keys).reset_index(drop=True),check_dtype=False,atol=1e-12,rtol=1e-12)
        contrasts,ranges=paired_comparisons(combined);loss_ranges,_=stability_tables(metrics)
        selected=pd.DataFrame([{k:v for k,v in s.items() if k!='inner_scores'} for s in selections])
        for name,data in [('metrics',metrics),('selections',selected),('fit_records',pd.DataFrame(fits)),('candidate_scores',pd.DataFrame(profiles)),
            ('paired_contrasts',contrasts),('comparison_ranges',ranges),('loss_ranges',loss_ranges),('lineage_diagnostics',diagnostic_summary)]:data.to_csv(run.path/f'{name}.csv',index=False)
        audit={'source_run':source_audit,'compatibility':compatibility,'reconstructed_fits':len(fits),
            'reconstructed_candidate_oof_rows':sum(r['valid_rows'] for r in fits),'new_predictions_bitwise_reconstructed':len(new),
            'combined_prediction_rows':len(combined),'all_preprocessors_and_readout_scalers_reconstructed':True,
            'all_candidate_selections_calibration_thresholds_reconstructed':True,'all_combined_metrics_labels_and_case_ids_verified':True,
            'lineage_diagnostic_cases':len(diagnostics),'canonical_message_lineage_rows':int(diagnostics.canonical_messages.sum()),
            'oracle_no_reuse_singleton_equivalences':equivalences,'scientific_bank_opened':False,
            'scope':'Same-workflow reconstruction, not independent A03 review or frozen scientific confirmation.'}
        write_json(run.path/'audit.json',audit)
        sections=[];full=metrics[metrics.training_fraction==1]
        for bank,condition in product(('software','bias_stress'),('overlap_90','new_information')):
            g=full[(full.regime=='matched_mixture')&(full.bank==bank)&(full.condition==condition)]
            sections += [f'### Matched training / {bank} / {condition}','',table(g,['arm','log_loss','brier','reviewed','fn']),'']
        mechanism_pairs={('grouped_no_age','grouped'),('grouped_no_od_readout','grouped'),('fixed_no_od','fixed'),
            ('fixed_no_od','grouped_no_od_readout'),('oracle_lineage_weight','singleton')}
        comparisons=ranges[(ranges.regime=='matched_mixture')&ranges.condition.isin(['overlap_90','new_information'])].copy()
        comparisons=comparisons[[tuple(x) in mechanism_pairs for x in comparisons[['arm','comparator']].itertuples(index=False,name=None)]]
        report=f'''# V02 observable-provenance components and oracle weighting

Date: 10 October 2026. Source `{source.name}`; reconstruction `{args.run_id}`.
**Exposed development results; V02 remains open and scientific outcomes remain reserved.**

## Contract and interventions

The [component contract](../../execution/component_contract.md) was committed
before fitting. Four new arms share the archived logistic readout, six C values,
three whole-scenario folds, four training trials and two regimes. There are
{len(selected)} selected models and {len(fits)} fits; every fit passed the strict
convergence policy. Maximum observed iterations: {max(r['iterations'] for r in fits)}.
{int(selected.C.eq(max(config['C'])).sum())}/32 selections reach the upper C boundary.
This is a bounded implementation comparison, not proof of optimal tuning.
Each ablation is retuned: observed differences include changes in selected C and
fitted coefficients, and do not identify a causal field effect in a fixed model.

`grouped_no_age` removes all eight categorical age bins from latest, mean,
variance and missingness summaries, reducing 122 columns to 90. Groups are
unchanged: the existing grouping rule uses OD and time, not age categories.
`grouped_no_od_readout` removes all twelve OD fields from those four blocks,
leaving 74 columns, while retaining OD-based grouping. `fixed_no_od` uses the
existing time-only fixed family and the same 74-column readout. It excludes OD
after common full-record canonicalization; arbitrary raw OD changes could still
affect upstream exact deduplication/tie ordering. These are conditional feature
interventions, not claims of independence from every trace of source metadata.

The existing singleton removes grouping, and existing fixed retains OD readout
with time-only groups. No new labels are assigned to identical archived controls.
All preprocessing is training-only; columnwise unused preprocessing values do
not affect retained columns. The final readout scaler is refitted on retained
design rows. One scenario contributes total objective weight one across its
variants and partition rows. The model takes the maximum partition probability.
Selected inner OOF is reused for tuning, monotone calibration and the nominal
95% training-recall threshold; there is no independent risk certification.

## Oracle definition and checks

`oracle_lineage_weight` changes only singleton mean/variance weights. Each unique
visible observation allocates one unit equally among messages containing it;
normalize by the visible union size. Equal allocations within 1e-14 use exact
archived uniform arithmetic. Latest features, time span, canonical message count
and missingness remain unchanged; no IDs or union-size predictor is added.
This is a privileged descriptive weighting rule, not posterior fusion, effective
sample size, a real-data method or a bound on attainable class performance.

All {len(diagnostics):,} scenario/condition lineage cases and 138,000 canonical
messages match audited publication order and visible observation IDs 0–59.
The earlier state reconstruction is reused under unchanged source/input hashes;
no new observation-state reconstruction or future-observation access is claimed.
No-reuse, exact replay and solution-reissue allocations are uniform; partial
overlap, cumulative information and burst reissue are nonuniform. For all four
no-reuse training trials, oracle selected C, OOF, threshold and predictions on
uniform-allocation conditions exactly match the saved singleton model.

Burst publication still changes time/age summaries and message count, so these
weights do not promise burst-invariant forecasts. `lineage_diagnostics.csv`
retains all condition/bank weight ranges; its unique counts are diagnostics only.

## Full-reference results

The reference uses 1,000 development scenarios. Each evaluation bank has 1,000
paired scenarios, with 194 software positives or 326 shared-bias positives.
These are enriched, unweighted synthetic stress populations, not operational
prevalence or workload estimates. q predicts final recorded-risk class, not
collision occurrence. Existing 104 selected models are reused after compatibility
checks; all 136 models' stored class metrics and case identities are verified.

{chr(10).join(sections)}
## Component contrasts and training sensitivity

Differences below are component minus named comparator; negative favors the
component. The three 800-scenario training subsets overlap. Their ranges and
lower-loss counts are descriptive, not confidence intervals or significance tests.
The full-reference trial is excluded from these ranges.

{table(comparisons,['bank','condition','arm','comparator','log_loss_absolute_difference_mean','log_loss_absolute_difference_min','log_loss_absolute_difference_max','component_lower_loss_seeds'])}

All arms, seven conditions and both regimes remain in the CSV exports. Paired
absolute and no-reuse-relative degradation differences cover log loss, Brier,
review indicator and missed-positive indicator; misses use the positive-scenario
denominator. Paired standard deviations support later precision planning.
The {len(combined):,} combined prediction rows are repeated scores, not new
independent cases. No confirmatory or multiplicity-adjusted test is claimed.

## Audit and next work

All {len(fits)} fold/refit checkpoints, prefix preprocessors and final readout
scalers were audited, including {sum(r['valid_rows'] for r in fits):,} reconstructed
candidate OOF values. Selected C, calibration and thresholds reproduce. All
{len(new):,} new forecasts reconstruct bitwise in this environment, and all
combined class metrics/labels match their source records. Each failed-fit category
would stop the run; no candidate was dropped. Checkpoints and full predictions
stay local; compact exports carry byte hashes.

This is artifact verification, not independent A03 review. Tuning adequacy,
simulator sensitivity and precision planning remain before V03. Neither a
feature-removal improvement nor privileged lineage weighting automatically proves
a general mechanism, novel method, operational gain or adequate miss control.
The scientific bank has not been generated. Retain null and adverse comparisons.
'''
        (run.path/'report.md').write_text(report,encoding='utf-8')
    args.export.mkdir(parents=True,exist_ok=False)
    names=('report.md','metrics.csv','selections.csv','candidate_scores.csv','fit_records.csv','paired_contrasts.csv',
           'comparison_ranges.csv','loss_ranges.csv','lineage_diagnostics.csv','audit.json')
    provenance={'run_id':args.run_id,'source_runs':[source.name,*[p.name for p in paths.values()]],'manifest_sha256':sha256(run.path/'manifest.json'),'artifacts':{}}
    for name in names:
        shutil.copyfile(run.path/name,args.export/name);provenance['artifacts'][name]=sha256(run.path/name)
    write_json(args.export/'provenance.json',provenance);print('EXPORTED',args.export,flush=True)


if __name__=='__main__':main()
