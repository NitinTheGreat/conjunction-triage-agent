"""Fixed-budget component ablations on immutable exposed scenario folds."""
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

from research.artifacts import ROOT, RUN_ROOT, Run, read_table, sha256, write_json, write_table
from research.components import ARMS, ComponentTransformer, lineage_events, lineage_weights
from research.covariance_campaign import check_reference
from research.data import visible_records
from research.history import events_from_frame
from research.metrics import class_metrics, loss
from research.models import MonotonePlatt, ProbabilityModel, policy_threshold
from research.simulation_regimes import scenario_folds, training_rows
from research.summarize_pilot import audit_run
from research.tuning_stability import evaluate_arm, sample_scenarios

CONTRACT = ROOT/'docs/research/execution/component_contract.json'


def validate_splits(frame, events, splits):
    if len(frame) != len(events) or any(str(s) != e.identity for s,e in zip(frame.series_id,events)):
        raise ValueError('Training row/event mismatch')
    if frame.duplicated(['series_id','condition']).any():raise ValueError('Repeated scenario variant')
    g=frame.groupby('series_id')
    if (g.y.nunique()!=1).any() or g.size().nunique()!=1 or not np.isin(frame.y,[0,1]).all():
        raise ValueError('Consistent binary labels and equal variants required')
    if not np.isfinite(frame.event_weight).all() or np.any(frame.event_weight<=0) or not np.allclose(g.event_weight.sum(),1.,atol=1e-12,rtol=0):
        raise ValueError('Expected one objective unit per scenario')
    coverage=np.zeros(len(frame),dtype=int)
    for fit,valid in splits:
        if (not len(fit) or not len(valid) or len(set(fit))!=len(fit) or len(set(valid))!=len(valid)
                or set(fit)&set(valid) or set(fit)|set(valid)!=set(range(len(frame)))):
            raise ValueError('Invalid fit/OOF partition')
        if set(frame.iloc[fit].series_id)&set(frame.iloc[valid].series_id):raise ValueError('Scenario leakage')
        if frame.iloc[fit].y.nunique()!=2:raise ValueError('Both fitting classes required')
        coverage[valid]+=1
    if not np.all(coverage==1):raise ValueError('Incomplete/repeated OOF coverage')


def fit_component(frame, events, arm, splits, grid, seed, directory, prefix, max_iter=10000):
    validate_splits(frame,events,splits)
    start=time.perf_counter();y=frame.y.to_numpy();weights=frame.event_weight.to_numpy()
    X=np.array([[e.raw[-1,0]] for e in events]);oof={c:np.full(len(frame),np.nan) for c in grid};records=[]

    def fit_one(c, fit, valid, fold, transform, prepared, prepared_valid):
        name=f'{prefix}_c{c:g}_fold{fold}';fit_seed=seed if fold=='refit' else seed+fold
        record={'arm':arm,'C':c,'fold':fold,'seed':fit_seed,'status':'running',
            'fit_rows':len(fit),'valid_rows':len(valid),'fit_scenarios':int(frame.iloc[fit].series_id.nunique()),
            'valid_scenarios':int(frame.iloc[valid].series_id.nunique()),'max_iter':max_iter}
        write_json(directory/f'fit_{name}.json',record);clock=time.perf_counter()
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error',ConvergenceWarning)
                model=ProbabilityModel(arm,c,fit_seed,max_iter=max_iter).fit(X[fit],y[fit],
                    [events[i] for i in fit],prepared=(transform,*prepared),event_weights=weights[fit])
            iterations=int(model.model[-1].n_iter_.max())
            if iterations>=max_iter:raise RuntimeError('Iteration cap reached')
            joblib.dump(model,directory/f'model_{name}.joblib')
            q=model.predict(X[valid],[events[i] for i in valid],prepared=prepared_valid) if len(valid) else None
            if q is not None:
                write_table(directory/f'validation_{name}.parquet',frame.iloc[valid].assign(row_index=valid,raw_oof=q))
            record.update(status='complete',iterations=iterations,seconds=time.perf_counter()-clock,
                design_rows=len(prepared[0]),design_columns=prepared[0].shape[1],
                objective_weight_sum=float(np.sum(prepared[2]*weights[fit][prepared[1]])))
            write_json(directory/f'fit_{name}.json',record);records.append(record)
            return model,q
        except Exception as exc:
            record.update(status='failed',failure_type=type(exc).__name__,seconds=time.perf_counter()-clock)
            write_json(directory/f'fit_{name}.json',record)
            raise

    for k,(fit,valid) in enumerate(splits):
        ef,ev=[events[i] for i in fit],[events[i] for i in valid]
        transform=ComponentTransformer(arm).fit(ef);prepared=transform.transform(ef);pv=transform.transform(ev)
        for c in grid:
            _,q=fit_one(c,fit,valid,k,transform,prepared,pv);oof[c][valid]=q
    if any(not np.isfinite(q).all() for q in oof.values()):raise ValueError('Incomplete OOF output')
    scores={c:float(np.average(loss(y,q),weights=weights)) for c,q in oof.items()}
    chosen=min(grid,key=lambda c:(scores[c],c))
    write_table(directory/f'candidates_{prefix}.parquet',pd.concat([frame.assign(C=c,raw_oof=q) for c,q in oof.items()],ignore_index=True))
    calibration=MonotonePlatt().fit(oof[chosen],y);threshold=policy_threshold(calibration.predict(oof[chosen]),y,.95)
    transform=ComponentTransformer(arm).fit(events)
    model,_=fit_one(chosen,np.arange(len(frame)),np.array([],dtype=int),'refit',transform,transform.transform(events),None)
    selection={'arm':arm,'C':chosen,'inner_scores':{str(c):v for c,v in scores.items()},
        'calibration_slope':calibration.slope,'calibration_intercept':calibration.intercept,'threshold95':threshold,
        'training_scenarios':int(frame.series_id.nunique()),'training_variant_rows':len(frame),
        'objective_weight_sum':float(weights.sum()),'completed_training_fits':len(records),
        'maximum_observed_iterations':max(r['iterations'] for r in records),'seconds':time.perf_counter()-start,
        'checkpoint':f'model_{prefix}_c{chosen:g}_foldrefit.joblib'}
    return {'model':model,'calibration':calibration,'threshold95':threshold},selection


def references(config):
    paths={key:RUN_ROOT/config[key] for key in ('source_run','reference_run','covariance_run','sequence_run','fusion_run')}
    cadence,reference=paths['source_run'].resolve(),paths['reference_run'].resolve()
    old,compatibility=check_reference(cadence,reference)
    for key in ('C','max_iter','inner_folds','trials','regimes'):assert config[key]==old[key],key
    for key,kind in [('covariance_run','covariance_proxy_development'),('sequence_run','sequence_adaptation_development'),('fusion_run','state_fusion_development')]:
        path=paths[key];compatibility[key]=audit_run(path)
        m=json.loads((path/'manifest.json').read_text(encoding='utf-8'));assert m['kind']==kind
        for file in cadence.glob('*.parquet'):assert m['inputs'][str(file)]==sha256(file),file.name
        modules=('history.py','models.py','data.py','metrics.py','simulation_regimes.py')
        if key=='sequence_run':modules+=('sequence_model.py','sequence_campaign.py')
        if key=='covariance_run':modules+=('covariance_proxy.py',)
        if key=='fusion_run':modules=('fusion_campaign.py','state_fusion.py','simulation.py','history.py','data.py')
        for name in modules:assert sha256(ROOT/'research'/name)==m['code_sha256'][f'research/{name}'],name
        if key!='fusion_run':
            for field in ('inner_folds','trials','regimes'):assert m['config'][field]==config[field]
        else:
            assert Path(m['config']['source']).resolve()==cadence
            completion=json.loads((path/'completion.json').read_text())
            assert completion['canonical_messages']==138000
    return paths,compatibility


def prepare_banks(cadence):
    banks={};diagnostics=[]
    for bank in ('development','software','bias_stress'):
        cohort=read_table(cadence/f'cohort_{bank}.parquet')
        messages=read_table(cadence/f'messages_{bank}.parquet');lineage=read_table(cadence/f'lineage_{bank}.parquet')
        for condition,group in messages.groupby('condition',sort=True):
            ev=events_from_frame(visible_records(group),cohort.series_id.tolist())
            oracle=lineage_events(group,lineage[lineage.condition==condition],cohort.series_id.tolist())
            for a,b in zip(ev,oracle):
                np.testing.assert_array_equal(a.raw,b.raw)
                weights=lineage_weights(b.windows)
                uniform=np.array_equal(weights,np.full(len(weights),1./len(weights)))
                if condition in ('no_reuse','exact_replay','solution_reissue'):assert uniform
                if condition in ('overlap_50','overlap_90','new_information','burst_reissue'):assert not uniform
                diagnostics.append({'bank':bank,'condition':condition,'series_id':a.identity,'canonical_messages':len(a.raw),
                    'unique_visible_observations':len(set(i for w in b.windows for i in w)),
                    'uniform':uniform,'weight_min':float(weights.min()),'weight_max':float(weights.max()),
                    'uniform_l1':float(np.abs(weights-1/len(weights)).sum())})
            X=np.array([[e.raw[-1,0]] for e in ev]);banks[bank,condition]=(cohort,ev,oracle,X)
    return banks,pd.DataFrame(diagnostics)


def attach_events(frame,banks,oracle):
    lookups={condition:{e.identity:e for e in value[2 if oracle else 1]} for (bank,condition),value in banks.items() if bank=='development'}
    return [lookups[r.condition][r.series_id] for r in frame.itertuples(index=False)]


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run-id',required=True);args=parser.parse_args()
    config=json.loads(CONTRACT.read_text(encoding='utf-8'))
    assert config==json.loads(subprocess.check_output(['git','show','HEAD:docs/research/execution/component_contract.json'],cwd=ROOT))
    assert config['arms']==list(ARMS)
    paths,compatibility=references(config);cadence,reference=paths['source_run'],paths['reference_run']
    config={**config,'contract_commit':subprocess.check_output(['git','log','-1','--format=%H','--',str(CONTRACT)],cwd=ROOT,text=True).strip()}
    inputs=[CONTRACT,*[p/'manifest.json' for p in paths.values()],*sorted(cadence.glob('*.parquet')),
            *sorted(reference.glob('cohort_seed*.parquet')),*sorted(reference.glob('training_seed*.parquet'))]
    with Run(args.run_id,'provenance_component_development',config,inputs) as run:
        run.access('exposed development/software/bias banks and audited visible lineage','component ablations and separately labelled oracle weighting','scientific reservation unopened; no future observation access')
        write_json(run.path/'compatibility.json',compatibility)
        banks,diagnostics=prepare_banks(cadence)
        write_table(run.path/'lineage_diagnostics.parquet',diagnostics)
        assert int(diagnostics.canonical_messages.sum())==138000
        write_json(run.path/'preflight.json',{'scenario_condition_cases':len(diagnostics),'canonical_messages':138000,
            'uniform_and_nonuniform_conditions_verified':True,'prior_state_reconstruction_inputs_unchanged':True,'before_first_fit':True})
        print('PREFLIGHT',len(diagnostics),'lineage-weight cases',flush=True)
        messages=read_table(cadence/'messages_development.parquet');development=banks['development','no_reuse'][0]
        outputs=[];selections=[];metrics=[]
        for trial in config['trials']:
            seed,fraction=trial['seed'],trial['fraction'];cohort=read_table(reference/f'cohort_seed{seed}.parquet')
            pd.testing.assert_frame_equal(cohort,sample_scenarios(development,fraction,seed))
            for regime,conditions in config['regimes'].items():
                frame,ev,_=training_rows(cohort,messages,conditions);splits=scenario_folds(frame,config['inner_folds'],seed)
                membership=frame.assign(inner_fold=-1)
                for k,(_,valid) in enumerate(splits):membership.loc[valid,'inner_fold']=k
                pd.testing.assert_frame_equal(membership,read_table(reference/f'training_seed{seed}_{regime}.parquet'))
                write_table(run.path/f'training_seed{seed}_{regime}.parquet',membership)
                for arm in ARMS:
                    prefix=f'seed{seed}_{regime}_{arm}';print('START',prefix,flush=True)
                    events=attach_events(frame,banks,arm=='oracle_lineage_weight')
                    for a,b in zip(events,ev):np.testing.assert_array_equal(a.raw,b.raw)
                    saved,selection=fit_component(frame,events,arm,splits,config['C'],seed,run.path,prefix,config['max_iter'])
                    selection.update(seed=seed,training_fraction=fraction,regime=regime)
                    write_json(run.path/f'selection_{prefix}.json',selection);selections.append(selection)
                    evaluation={key:(value[0],value[2 if arm=='oracle_lineage_weight' else 1],value[3]) for key,value in banks.items() if key[0]!='development'}
                    output=evaluate_arm(saved,evaluation,seed,fraction,regime,arm)
                    write_table(run.path/f'predictions_{prefix}.parquet',output);outputs.append(output)
                    for (bank,condition),g in output.groupby(['bank','condition']):
                        metrics.append({'seed':seed,'training_fraction':fraction,'regime':regime,'arm':arm,'bank':bank,'condition':condition,
                            **class_metrics(g.y.to_numpy(),g.q.to_numpy(),g.review95.to_numpy())})
                    write_json(run.path/'progress.json',{'completed_selected_models':len(selections),'planned_selected_models':32,'last_completed':prefix})
                    print('DONE',prefix,'C',selection['C'],'seconds',round(selection['seconds'],1),flush=True)
        assert len(selections)==config['planned_selected_models']
        assert sum(s['completed_training_fits'] for s in selections)==config['planned_training_fits']
        assert sum(len(p) for p in outputs)==config['planned_prediction_rows']
        write_json(run.path/'selections.json',selections);write_table(run.path/'predictions.parquet',pd.concat(outputs,ignore_index=True))
        pd.DataFrame(metrics).to_csv(run.path/'metrics.csv',index=False)
        write_json(run.path/'completion.json',{'selected_models':len(selections),'training_fits':608,'prediction_rows':448000,
            'maximum_observed_iterations':max(s['maximum_observed_iterations'] for s in selections),
            'upper_C_selections':sum(s['C']==max(config['C']) for s in selections),'scientific_bank_opened':False})


if __name__=='__main__':main()
