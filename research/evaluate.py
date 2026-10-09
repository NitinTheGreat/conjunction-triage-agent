"""Nested development evaluation with stored folds and out-of-fold calibration."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold

from core.features_causal import FEATURE_COLUMNS_CAUSAL,LEAKING_COLUMNS
from research.artifacts import ROOT,Run,read_table,write_json,write_table
from research.history import events_from_frame,HistoryTransformer
from research.models import ProbabilityModel,MonotonePlatt,policy_threshold
from research.metrics import class_metrics,official_metrics,loss


def folds(y,requested,seed):
    count=min(requested,int(np.bincount(y,minlength=2).min()))
    if count<2:raise ValueError('Insufficient class count for grouped event CV')
    return list(StratifiedKFold(count,shuffle=True,random_state=seed).split(np.zeros(len(y)),y))


def nested_evaluate(frame,events,columns,arms,cfg,run):
    assert len(frame)==len(events) and frame.series_id.is_unique
    assert not set(columns)&set((*LEAKING_COLUMNS,'final_risk','n_cdms_series','label'))
    X=frame[columns].to_numpy(float); y=(frame.final_risk.to_numpy()>=-6).astype(int)
    ids=frame.series_id.to_numpy()
    seed=cfg['cv']['seed']
    outer=folds(y,cfg['cv']['outer_folds'],seed)
    inner={k:folds(y[train],cfg['cv']['inner_folds'],seed+k+1) for k,(train,_) in enumerate(outer)}
    split_rows=[]
    for k,(train,test) in enumerate(outer):
        split_rows.extend({'series_id':str(ids[i]),'outer_fold':k,'inner_fold':-1,'role':'outer_evaluation'} for i in test)
        for j,(_,validation) in enumerate(inner[k]):
            split_rows.extend({'series_id':str(ids[train[i]]),'outer_fold':k,'inner_fold':j,'role':'inner_validation'} for i in validation)
    write_table(run.path/'splits.parquet',pd.DataFrame(split_rows))
    write_table(run.path/'cohort.parquet',frame[['series_id','final_risk','mission_id']])
    write_json(run.path/'feature_lineage.json',{'columns':columns,'source':'causal feature allowlist plus raw visible history; see data run lineage',
                                            'forbidden_columns':list(LEAKING_COLUMNS)})
    all_predictions=[]; selections=[]
    for arm in arms:
        for k,(train,test) in enumerate(outer):
            begin=time.perf_counter()
            params=cfg['model']['logistic_C'] if arm!='causal_gbm' else [1.,10.]
            oof={parameter:np.full(len(train),np.nan) for parameter in params}
            for j,(fit,validation) in enumerate(inner[k]):
                ii,jj=train[fit],train[validation]
                train_events=[events[i] for i in ii]; val_events=[events[i] for i in jj]
                prepared=prepared_val=None
                if arm not in ('latest','causal_logistic','causal_gbm'):
                    hist=HistoryTransformer(arm).fit(train_events)
                    prepared=(hist,*hist.transform(train_events)); prepared_val=hist.transform(val_events)
                for parameter in params:
                    model=ProbabilityModel(arm,parameter,seed+100*k+j).fit(X[ii],y[ii],train_events,prepared)
                    oof[parameter][validation]=model.predict(X[jj],val_events,prepared_val)
            scores={p:float(loss(y[train],q).mean()) for p,q in oof.items()}
            if any(not np.isfinite(q).all() for q in oof.values()):raise RuntimeError('Incomplete OOF coverage')
            chosen=min(params,key=lambda p:(scores[p],p))
            calibrator=MonotonePlatt().fit(oof[chosen],y[train])
            q_train=calibrator.predict(oof[chosen])
            model=ProbabilityModel(arm,chosen,seed+100*k).fit(X[train],y[train],[events[i] for i in train])
            raw=model.predict(X[test],[events[i] for i in test]); q=calibrator.predict(raw)
            result=pd.DataFrame({'series_id':ids[test],'outer_fold':k,'arm':arm,'final_risk':frame.final_risk.to_numpy()[test],
                                 'y':y[test],'q':q,'raw_score':raw,'failure':False})
            for recall in cfg['policy']['nominal_recall']:
                threshold=policy_threshold(q_train,y[train],recall)
                key=str(int(round(100*recall)))
                result[f'threshold_{key}']=threshold;result[f'review_{key}']=q>=threshold
            write_table(run.path/f'predictions_{arm}_fold{k}.parquet',result)
            joblib.dump({'model':model,'calibrator':calibrator,'columns':columns},run.path/f'model_{arm}_fold{k}.joblib')
            selection={'arm':arm,'fold':k,'parameter':chosen,'inner_log_loss':{str(p):v for p,v in scores.items()},
                       'calibration_slope':calibrator.slope,'calibration_intercept':calibrator.intercept,
                       'train_n':len(train),'train_positives':int(y[train].sum()),'test_n':len(test),
                       'test_positives':int(y[test].sum()),'elapsed_seconds':time.perf_counter()-begin}
            selections.append(selection);all_predictions.append(result)
            write_json(run.path/f'selection_{arm}_fold{k}.json',selection)
            print(f'{arm} fold {k}: C/L2={chosen}, n={len(test)}, positives={int(y[test].sum())}, seconds={selection["elapsed_seconds"]:.1f}',flush=True)
    predictions=pd.concat(all_predictions,ignore_index=True)
    write_table(run.path/'predictions.parquet',predictions)
    metrics={}
    calibration=[]
    for arm,g in predictions.groupby('arm',sort=False):
        assert len(g)==len(frame) and g.series_id.is_unique
        metrics[arm]={str(int(round(100*r))):class_metrics(g.y.to_numpy(),g.q.to_numpy(),g[f'review_{int(round(100*r))}'].to_numpy())
                      for r in cfg['policy']['nominal_recall']}
        bins=pd.qcut(g.q,5,duplicates='drop')
        for label,b in g.groupby(bins,observed=True):
            calibration.append({'arm':arm,'bin':str(label),'n':len(b),'positives':int(b.y.sum()),'mean_q':float(b.q.mean()),'observed_fraction':float(b.y.mean())})
    write_json(run.path/'metrics.json',{'evidence':'retrospective nested OOF; not independent confirmation',
            'calibration_limit':'pooled inner OOF used for model selection and calibrator/threshold fitting; evaluated only on disjoint outer folds',
            'models':metrics,'hyperparameters':selections})
    write_table(run.path/'calibration.parquet',pd.DataFrame(calibration))
    return metrics


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-run',required=True,type=Path)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--arms',nargs='+')
    args=parser.parse_args()
    data=args.data_run.resolve()
    if json.loads((data/'manifest.json').read_text())['status']!='complete':raise ValueError('Input data run incomplete')
    cfg=json.loads((ROOT/'research/configs/development.json').read_text())
    arms=args.arms or cfg['arms']
    if not set(arms)<=set(cfg['arms']):raise ValueError('Unknown arm')
    cfg['executed_arms']=arms
    inputs=[data/name for name in ('manifest.json','causal_features_train.parquet','causal_features_test.parquet','visible_train.parquet')]
    with Run(args.run_id,'nested_development_evaluation',cfg,inputs) as run:
        run.access('eligible Kelvins training outcomes','nested development CV','exposed retrospective')
        run.access('historical Kelvins test outcomes','B1/constant anchor reconstruction only','already exposed; never used to fit new models')
        frame=read_table(data/'causal_features_train.parquet')
        events=events_from_frame(read_table(data/'visible_train.parquet'),frame.series_id.tolist())
        columns=['latest_risk',*[c for c in FEATURE_COLUMNS_CAUSAL if c!='latest_risk']]
        test=read_table(data/'causal_features_test.parquet')
        anchors={'B1':official_metrics(test.final_risk.to_numpy(),test.latest_risk.to_numpy()),
                 'constant_minus5':official_metrics(test.final_risk.to_numpy(),np.full(len(test),-5.))}
        if not np.isclose(anchors['B1']['L'],.6939612612,atol=1e-9,rtol=0):raise ValueError('B1 anchor mismatch')
        write_json(run.path/'historical_anchors.json',anchors)
        metrics=nested_evaluate(frame,events,columns,arms,cfg,run)
        print(json.dumps(metrics,indent=2),flush=True)


if __name__=='__main__':main()
