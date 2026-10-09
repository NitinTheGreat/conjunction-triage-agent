"""Corrected official-score comparator: cross-fit classifier AND value regressor."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier,HistGradientBoostingRegressor
from research.artifacts import ROOT,Run,read_table,write_table,write_json
from research.evaluate import folds
from research.metrics import official_metrics
from core.features_causal import FEATURE_COLUMNS_CAUSAL
from core.kelvins_metric import kelvins_score


def classifier(seed):
    return HistGradientBoostingClassifier(max_iter=250,learning_rate=.06,min_samples_leaf=20,
        l2_regularization=1.,class_weight='balanced',early_stopping=False,random_state=seed)


def regressor(seed):
    return HistGradientBoostingRegressor(max_iter=200,learning_rate=.05,min_samples_leaf=5,
        l2_regularization=1.,early_stopping=False,random_state=seed)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data-run',required=True,type=Path);p.add_argument('--run-id',required=True)
    args=p.parse_args();data=args.data_run.resolve()
    if json.loads((data/'manifest.json').read_text())['status']!='complete':raise ValueError('Incomplete data run')
    config={'seed':20261009,'outer_folds':5,'inner_folds':3,'features':list(FEATURE_COLUMNS_CAUSAL),
            'protocol':'new retrospective five-fold campaign; not completion of historical 50-resplit pilot',
            'both_stages_cross_fitted':True,'threshold_grid':'training OOF score quantiles 0.8..0.9995 (60) plus review-all',
            'classifier_calibrated':False,'threshold_objective':'official L, not class-probability calibration',
            'test_used':False}
    with Run(args.run_id,'corrected_official_score',config,[data/'manifest.json',data/'causal_features_train.parquet']) as run:
        run.access('Kelvins eligible train labels','corrected nested official-score benchmark','exposed retrospective')
        frame=read_table(data/'causal_features_train.parquet');X=frame[list(FEATURE_COLUMNS_CAUSAL)].to_numpy(float)
        truth=frame.final_risk.to_numpy();y=(truth>=-6).astype(int);seed=config['seed']
        outer=folds(y,5,seed);split_rows=[]; inner={}
        for k,(train,test) in enumerate(outer):
            inner[k]=folds(y[train],3,seed+k+1)
            split_rows.extend({'series_id':frame.series_id.iloc[i],'outer_fold':k,'inner_fold':-1,'role':'outer_evaluation'} for i in test)
            for j,(_,valid) in enumerate(inner[k]):
                split_rows.extend({'series_id':frame.series_id.iloc[train[i]],'outer_fold':k,'inner_fold':j,'role':'inner_validation_both_stages'} for i in valid)
        write_table(run.path/'splits.parquet',pd.DataFrame(split_rows))
        outputs=[];selections=[]
        for k,(train,test) in enumerate(outer):
            q=np.full(len(train),np.nan);value=np.full(len(train),np.nan)
            for j,(fit,valid) in enumerate(inner[k]):
                fit_ids,valid_ids=train[fit],train[valid]
                c=classifier(seed+100*k+j).fit(X[fit_ids],y[fit_ids])
                positive_ids=fit_ids[y[fit_ids]==1]
                r=regressor(seed+100*k+j).fit(X[positive_ids],truth[positive_ids])
                q[valid]=c.predict_proba(X[valid_ids])[:,1];value[valid]=r.predict(X[valid_ids])
            assert np.isfinite(q).all() and np.isfinite(value).all()
            candidates=np.unique(np.r_[0.,np.quantile(q,np.linspace(.8,.9995,60))])
            scores=[kelvins_score(truth[train],np.where(q>=t,np.clip(value,-6,0),-30.)).score for t in candidates]
            chosen=min(range(len(candidates)),key=lambda i:(scores[i],candidates[i]));threshold=float(candidates[chosen])
            c=classifier(seed+100*k).fit(X[train],y[train]);positive_ids=train[y[train]==1]
            r=regressor(seed+100*k).fit(X[positive_ids],truth[positive_ids])
            qt=c.predict_proba(X[test])[:,1];vt=r.predict(X[test]);pred=np.where(qt>=threshold,np.clip(vt,-6,0),-30.)
            b4=HistGradientBoostingRegressor(max_iter=300,learning_rate=.06,max_leaf_nodes=31,min_samples_leaf=20,
                l2_regularization=1.,early_stopping=False,random_state=seed+100*k).fit(X[train],truth[train]).predict(X[test])
            out=pd.DataFrame({'series_id':frame.series_id.iloc[test].to_numpy(),'outer_fold':k,'final_risk':truth[test],
                              'B1':frame.latest_risk.iloc[test].to_numpy(),'B4_causal':b4,'B5_crossfit':pred,
                              'classifier_score_uncalibrated':qt,'value_prediction':vt,'threshold':threshold})
            outputs.append(out);write_table(run.path/f'predictions_fold{k}.parquet',out)
            oof=pd.DataFrame({'series_id':frame.series_id.iloc[train].to_numpy(),'classifier_oof':q,'regressor_oof':value})
            write_table(run.path/f'threshold_oof_fold{k}.parquet',oof)
            selections.append({'fold':k,'threshold':threshold,'inner_L':float(scores[chosen]),'outer_B5':official_metrics(truth[test],pred)})
            print('two-stage fold',k,selections[-1],flush=True)
        result=pd.concat(outputs,ignore_index=True);write_table(run.path/'predictions.parquet',result)
        write_json(run.path/'metrics.json',{'cohort':'exposed train, one OOF prediction per event','n':len(result),
            'models':{arm:official_metrics(result.final_risk.to_numpy(),result[arm].to_numpy()) for arm in ('B1','B4_causal','B5_crossfit')},
            'folds':selections,'infinite_fold_scores_retained':True})


if __name__=='__main__':main()
