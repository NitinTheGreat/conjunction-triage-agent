"""Explicit denominators, finite statuses, and paired scenario contrasts."""
from __future__ import annotations
import numpy as np
from sklearn.metrics import average_precision_score,roc_auc_score
from core.kelvins_metric import kelvins_score


def loss(y,q):
    q=np.clip(np.asarray(q,float),1e-6,1-1e-6)
    return -(y*np.log(q)+(1-y)*np.log1p(-q))


def class_metrics(y,q,review):
    y=np.asarray(y,dtype=int); q=np.asarray(q,float); review=np.asarray(review,bool)
    if not np.isfinite(q).all():raise ValueError('Nonfinite q requires explicit failure handling')
    pos=y==1; tp=int((review&pos).sum()); fn=int((~review&pos).sum()); fp=int((review&~pos).sum())
    return {'n':len(y),'positives':int(pos.sum()),'reviewed':int(review.sum()),'tp':tp,'fp':fp,'fn':fn,
            'review_fraction':float(review.mean()),'miss_rate':float(fn/pos.sum()) if pos.any() else None,
            'miss_rate_status':'finite' if pos.any() else 'undefined_no_positives',
            'precision':float(tp/review.sum()) if review.any() else None,
            'brier':float(np.mean((q-y)**2)),'log_loss':float(loss(y,q).mean()),
            'roc_auc':float(roc_auc_score(y,q)) if len(np.unique(y))==2 else None,
            'average_precision':float(average_precision_score(y,q)) if pos.any() else None}


def official_metrics(truth,predicted_logrisk):
    if not np.any(truth>=-6):return {'L':None,'metric_status':'undefined_no_positives'}
    value=kelvins_score(truth,predicted_logrisk).as_dict()
    finite=np.isfinite(value['L'])
    value['metric_status']='finite' if finite else 'infinite_zero_f2'
    if not finite:value['L']=None
    return value


def paired_interval(values,seed=20261009,repeats=2000):
    values=np.asarray(values,float)
    rng=np.random.default_rng(seed)
    means=np.array([rng.choice(values,size=len(values),replace=True).mean() for _ in range(repeats)])
    return {'mean':float(values.mean()),'ci95_percentile':np.quantile(means,[.025,.975]).tolist(),
            'n_independent_units_assumed':len(values),'resamples':repeats,'seed':seed,
            'scope':'descriptive paired event/scenario bootstrap; not a rare-event risk certificate'}
