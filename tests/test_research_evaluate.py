import numpy as np
import pandas as pd
from research.artifacts import Run,read_table
from research.data import RAW_FIELDS
from research.history import Event,canonicalize
from research.evaluate import nested_evaluate


def test_nested_runner_complete_coverage_and_disjoint_model_selection(tmp_path):
    rng=np.random.default_rng(67);events=[];rows=[]
    for i in range(40):
        raw=np.ones((3,len(RAW_FIELDS)))
        raw[:,1]=[4.,3.,2.]
        raw[:,0]=rng.normal(-5.5 if i%4==0 else -9.,.4,size=3)
        sid=f'fixture:{i}'
        events.append(Event(sid,canonicalize(raw)))
        rows.append({'series_id':sid,'latest_risk':raw[-1,0],'final_risk':-5. if i%4==0 else -9.,'mission_id':'fixture'})
    frame=pd.DataFrame(rows)
    config={'cv':{'seed':6,'outer_folds':2,'inner_folds':2},'model':{'logistic_C':[.1]},'policy':{'nominal_recall':[.95]}}
    with Run('nested_fixture','software_test',config,base=tmp_path) as run:
        metrics=nested_evaluate(frame,events,['latest_risk'],['latest','grouped'],config,run)
    predictions=read_table(run.path/'predictions.parquet');splits=read_table(run.path/'splits.parquet')
    for arm,g in predictions.groupby('arm'):
        assert len(g)==40 and g.series_id.is_unique and g.y.sum()==10
        assert metrics[arm]['95']['positives']==10
        assert np.isfinite(g.q).all()
    for k,g in splits.groupby('outer_fold'):
        held=set(g[g.role=='outer_evaluation'].series_id)
        inner=set(g[g.role=='inner_validation'].series_id)
        assert not held&inner and held|inner==set(frame.series_id)
    # Model state and calibration fitted within each outer training population.
    assert len(list(run.path.glob('model_*.joblib')))==4
