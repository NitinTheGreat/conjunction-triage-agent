"""Exploratory mechanism comparison; scientific reserved scenarios remain unopened."""
from __future__ import annotations
import argparse,json,time
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from research.artifacts import ROOT,Run,read_table,write_json,write_table
from research.evaluate import folds
from research.history import events_from_frame,HistoryTransformer
from research.models import ProbabilityModel,MonotonePlatt,policy_threshold
from research.metrics import loss,class_metrics,paired_interval


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--simulation-run',type=Path,required=True);p.add_argument('--run-id',required=True)
    args=p.parse_args();source=args.simulation_run.resolve()
    if json.loads((source/'manifest.json').read_text())['status']!='complete':raise ValueError('Incomplete simulation input')
    cfg={'seed':20261014,'arms':['latest','singleton','fixed','random','thin','change','grouped','ignore_updates'],
         'C':[.01,.1,1.,10.],'inner_folds':3,'training_condition':'no_reuse',
         'evaluation':'exploratory software validation and bias stress; not scientific confirmation',
         'population':'unweighted enriched synthetic stress distribution; no operational workload inference',
         'primary_scientific_condition':'not yet selected/frozen','scientific_bank_opened':False}
    inputs=[source/'manifest.json',*source.glob('*.parquet')]
    with Run(args.run_id,'simulation_mechanism_pilot',cfg,inputs) as run:
        run.access('development/software/bias_stress banks','exploratory mechanism and control comparison','pilot outcomes may inform future design; reserved scientific bank untouched')
        cohort=read_table(source/'cohort_development.parquet')
        messages=read_table(source/'messages_development.parquet')
        ids=cohort.series_id.tolist();y=(cohort.final_risk.to_numpy()>=-6).astype(int)
        events=events_from_frame(messages[messages.condition=='no_reuse'],ids)
        X=np.array([[e.raw[-1,0]] for e in events])
        splits=folds(y,3,cfg['seed'])
        write_table(run.path/'splits.parquet',pd.DataFrame([{'series_id':ids[i],'inner_fold':k,'role':'inner_validation'} for k,(_,v) in enumerate(splits) for i in v]))
        banks={}
        for bank in ('software','bias_stress'):
            c=read_table(source/f'cohort_{bank}.parquet');m=read_table(source/f'messages_{bank}.parquet')
            for condition,g in m.groupby('condition',sort=True):
                ev=events_from_frame(g,c.series_id.tolist());xx=np.array([[e.raw[-1,0]] for e in ev])
                banks[bank,condition]=(c,ev,xx)
        outputs=[];metrics={};selections=[]
        for arm in cfg['arms']:
            start=time.perf_counter();oof={c:np.full(len(y),np.nan) for c in cfg['C']}
            for k,(fit,valid) in enumerate(splits):
                ef=[events[i] for i in fit];ev=[events[i] for i in valid];prepared=pv=None
                if arm!='latest':
                    h=HistoryTransformer(arm).fit(ef);prepared=(h,*h.transform(ef));pv=h.transform(ev)
                for c in cfg['C']:
                    model=ProbabilityModel(arm,c,cfg['seed']+k).fit(X[fit],y[fit],ef,prepared)
                    oof[c][valid]=model.predict(X[valid],ev,pv)
            if any(not np.isfinite(v).all() for v in oof.values()):raise ValueError('Incomplete OOF')
            scores={c:float(loss(y,q).mean()) for c,q in oof.items()};c=min(cfg['C'],key=lambda c:(scores[c],c))
            cal=MonotonePlatt().fit(oof[c],y);threshold=policy_threshold(cal.predict(oof[c]),y,.95)
            model=ProbabilityModel(arm,c,cfg['seed']).fit(X,y,events)
            joblib.dump({'model':model,'calibration':cal,'threshold95':threshold},run.path/f'model_{arm}.joblib')
            for (bank,condition),(cohort_v,ev,xx) in banks.items():
                truth=(cohort_v.final_risk.to_numpy()>=-6).astype(int)
                q=cal.predict(model.predict(xx,ev))
                output=pd.DataFrame({'series_id':cohort_v.series_id,'bank':bank,'condition':condition,'arm':arm,
                    'y':truth,'q':q,'log_loss':loss(truth,q),'review95':q>=threshold,'threshold95':threshold})
                outputs.append(output)
                metrics[f'{arm}/{bank}/{condition}']=class_metrics(truth,q,q>=threshold)
            selections.append({'arm':arm,'C':c,'inner_scores':{str(k):v for k,v in scores.items()},
                               'calibration_slope':cal.slope,'calibration_intercept':cal.intercept,'seconds':time.perf_counter()-start})
            write_json(run.path/f'selection_{arm}.json',selections[-1]);print(arm,'seconds',round(selections[-1]['seconds'],1),flush=True)
        result=pd.concat(outputs,ignore_index=True);write_table(run.path/'predictions.parquet',result)
        contrasts={}
        for bank in ('software','bias_stress'):
            pivot=result[result.bank==bank].pivot(index='series_id',columns=['arm','condition'],values='log_loss')
            for condition in ('overlap_50','overlap_90','solution_reissue','new_information'):
                for baseline in ('latest','singleton','thin','fixed','random'):
                    values=(pivot['grouped',condition]-pivot['grouped','no_reuse'])-(pivot[baseline,condition]-pivot[baseline,'no_reuse'])
                    contrasts[f'{bank}/{condition}/grouped_minus_{baseline}']=paired_interval(values.to_numpy())
            for arm in cfg['arms']:
                if not np.allclose(pivot[arm,'no_reuse'],pivot[arm,'exact_replay'],rtol=0,atol=1e-12):
                    raise ValueError('Replay invariance failed')
        write_json(run.path/'metrics.json',{'models':metrics,'contrasts':contrasts,'selections':selections,
            'evidence':'exploratory; many comparisons; bootstrap conditional on fixed fitted models and independent synthetic scenarios',
            'scientific_reserved_bank_opened':False,'exact_replay_check':'pass all arms'})
        print('Mechanism pilot complete',flush=True)


if __name__=='__main__':main()
