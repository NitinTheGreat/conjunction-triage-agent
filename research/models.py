"""Small-data final-class models. q is never interpreted as physical Pc."""
from __future__ import annotations
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit,logit
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from research.history import HistoryTransformer


class ProbabilityModel:
    def __init__(self, arm: str, parameter: float, seed: int):
        self.arm,self.parameter,self.seed=arm,parameter,seed
        self.history = None

    def fit(self, X, y, events, prepared=None):
        owners = np.arange(len(y)); weights = np.ones(len(y))
        if prepared is not None:
            self.history,X,owners,weights=prepared
        elif self.arm not in ('latest','causal_logistic','causal_gbm'):
            self.history=HistoryTransformer(self.arm).fit(events)
            X,owners,weights=self.history.transform(events)
        elif self.arm=='latest':X=X[:,[0]]
        if self.arm=='causal_gbm':
            self.model=HistGradientBoostingClassifier(max_iter=100,max_leaf_nodes=7,l2_regularization=self.parameter,
                                                      early_stopping=False,random_state=self.seed)
            self.model.fit(X,y)
        else:
            self.model=make_pipeline(SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True),
                StandardScaler(),LogisticRegression(C=self.parameter,solver='lbfgs',max_iter=2000,random_state=self.seed))
            self.model.fit(X,y[owners],logisticregression__sample_weight=weights)
        return self

    def predict(self,X,events,prepared=None):
        owners=np.arange(len(X))
        if prepared is not None:X,owners,_=prepared
        elif self.history:X,owners,_=self.history.transform(events)
        elif self.arm=='latest':X=X[:,[0]]
        probabilities=self.model.predict_proba(X)[:,1]
        result=np.full(len(events),-np.inf)
        np.maximum.at(result,owners,probabilities)
        if not np.isfinite(result).all():raise ValueError('Missing/nonfinite model output')
        return result


class MonotonePlatt:
    def fit(self, probability,y):
        x=logit(np.clip(probability,1e-6,1-1e-6))
        def objective(v):
            z=v[0]*x+v[1]
            loss=np.mean(np.logaddexp(0,z)-y*z)
            residual=expit(z)-y
            return loss,np.array([np.mean(residual*x),np.mean(residual)])
        fit=minimize(objective,[1.,0.],jac=True,method='L-BFGS-B',bounds=[(0.,None),(None,None)],
                     options={'maxiter':1000,'ftol':1e-12})
        if not fit.success:raise RuntimeError('Calibration optimization did not converge')
        self.slope,self.intercept=map(float,fit.x)
        return self

    def predict(self,p):
        return expit(self.slope*logit(np.clip(p,1e-6,1-1e-6))+self.intercept)


def policy_threshold(q,y,recall):
    if not np.any(y==1):raise ValueError('Threshold selection requires positive training events')
    candidates=np.unique(np.r_[0.,np.quantile(q,np.linspace(0,1,101))])
    valid=[t for t in candidates if np.mean(q[y==1]>=t)>=recall]
    # Maximize deferral; tie toward more review (smaller threshold).
    return float(min(valid,key=lambda t:(-np.mean(q<t),t)))
