import json

import numpy as np
import pandas as pd
import pytest

from research.components import (ARMS, ComponentTransformer, LineageEvent,
    kept_columns, lineage_events, lineage_weights)
from research.data import AGE_FIELDS, OD_FIELDS, RAW_FIELDS, visible_records
from research.history import Event, HistoryTransformer, PHI_NAMES, canonicalize, events_from_frame, partitions, phi


def event(identity='x', times=(6., 5.9, 5.75, 3.5, 2.1, 2.)):
    raw = np.ones((len(times), len(RAW_FIELDS)))
    raw[:, 0] = np.linspace(-9, -5, len(times)); raw[:, 1] = times
    raw[:, 2] = np.arange(len(times))*10.
    for role in ('t', 'c'):
        raw[:, RAW_FIELDS.index(f'{role}_time_lastob_end')] = [0, 1, 2, 0, 1, np.nan][:len(times)]
        raw[:, RAW_FIELDS.index(f'{role}_time_lastob_start')] = [1, 2, 180, 1, 2, np.nan][:len(times)]
    return Event(identity, canonicalize(raw))


@pytest.mark.parametrize('arm,mode,width', [('grouped_no_age','grouped',90),
    ('grouped_no_od_readout','grouped',74), ('fixed_no_od','fixed',74)])
def test_removed_columns_and_retained_design_exactly_match_archived_base(arm,mode,width):
    events=[event()]
    expected=HistoryTransformer(mode).fit(events).transform(events)
    actual=ComponentTransformer(arm).fit(events).transform(events)
    assert actual[0].shape[1] == width
    np.testing.assert_array_equal(actual[0], expected[0][:,kept_columns(arm)])
    np.testing.assert_array_equal(actual[1],expected[1]);np.testing.assert_array_equal(actual[2],expected[2])
    assert np.bincount(actual[1],weights=actual[2])[0] == pytest.approx(1.)
    d=len(PHI_NAMES)
    fields=[i for i,n in enumerate(PHI_NAMES) if '_age_' in n] if arm=='grouped_no_age' else [PHI_NAMES.index(n) for n in OD_FIELDS]
    for offset in (0,d,2*d,3*d+2):
        assert not set(offset+i for i in fields)&set(kept_columns(arm))
    assert {3*d,3*d+1} <= set(kept_columns(arm))


def test_age_changes_never_change_groups_and_removed_age_cannot_change_readout():
    e=event(); changed=event();changed.raw[:,[RAW_FIELDS.index(n) for n in AGE_FIELDS]]=999.
    transform=ComponentTransformer('grouped_no_age').fit([e])
    for a,b in zip(transform.transform([e]),transform.transform([changed])):np.testing.assert_array_equal(a,b)
    base=HistoryTransformer('grouped').fit([e])
    assert not np.array_equal(base.transform([e])[0],base.transform([changed])[0])
    z=base.scaler.transform(base.imputer.transform(phi(e.raw)))
    assert [p.tolist() for p in partitions(e,z,'grouped')]==[p.tolist() for p in partitions(changed,z,'grouped')]


def test_od_readout_removal_retains_grouping_but_fixed_no_od_ignores_od_after_canonicalization():
    e=event();changed=event()
    for i,name in enumerate(OD_FIELDS):changed.raw[:,RAW_FIELDS.index(name)]=np.arange(6)*(10+i)
    for arm in ('grouped_no_od_readout','fixed_no_od'):
        t=ComponentTransformer(arm).fit([e]); a=t.transform([e]);b=t.transform([changed])
        if arm=='fixed_no_od':
            for x,y in zip(a,b):np.testing.assert_array_equal(x,y)
            # Fitting unused OD scales also cannot alter retained columns.
            for x,y in zip(a,ComponentTransformer(arm).fit([changed]).transform([changed])):np.testing.assert_array_equal(x,y)
        else:
            assert a[0].shape!=b[0].shape or not np.array_equal(a[0],b[0])


@pytest.mark.parametrize('windows,expected', [(((0,1),(2,3)),[.5,.5]),
    (((0,1),(0,1)),[.5,.5]), (((0,1),(0,1),(2,3)),[.25,.25,.5]),
    (((0,1),(1,2)),[.5,.5]), (((0,),(0,1)),[.25,.75])])
def test_oracle_allocations_analytic(windows,expected):
    np.testing.assert_allclose(lineage_weights(windows),expected,atol=1e-15,rtol=0)


@pytest.mark.parametrize('windows', [(), ((),), ((0,0),), ((-1,),), ((60,),), ((1.5,),), ((True,),)])
def test_oracle_rejects_invalid_or_future_observation_ids(windows):
    with pytest.raises(ValueError):lineage_weights(windows)


def lineage_fixture():
    e=event(times=(6.,4.,2.));windows=((0,1),(0,1,2),(0,1,2,3))
    messages=pd.DataFrame(e.raw,columns=RAW_FIELDS).assign(series_id='x')
    lineage=pd.DataFrame([{'series_id':'x','message_index':j,'observation_ids':json.dumps(w),
        'source_solution_id':','.join(map(str,w)),'available_at_tca_days':e.raw[j,1]} for j,w in enumerate(windows)])
    return messages,lineage


def test_lineage_join_canonical_replay_future_exclusion_and_order_validation():
    messages,lineage=lineage_fixture()
    expected=lineage_events(messages,lineage,['x'])[0]
    future=messages.iloc[-1:].copy();future.time_to_tca=.5;future.risk=999.
    later=lineage.iloc[-1:].copy();later.available_at_tca_days=.5;later.message_index=3;later.observation_ids='[60, 79]'
    altered=pd.concat([messages.iloc[::-1],messages,future]).assign(final_risk=123,oracle_hidden=1)
    actual=lineage_events(altered,pd.concat([lineage,later]),['x'])[0]
    np.testing.assert_array_equal(actual.raw,expected.raw);assert actual.windows==expected.windows
    for arm in ARMS:
        t=ComponentTransformer(arm).fit([expected]);state=t.base.imputer.statistics_.copy()
        for x,y in zip(t.transform([expected]),t.transform([actual])):np.testing.assert_array_equal(x,y)
        np.testing.assert_array_equal(state,t.base.imputer.statistics_)
    invalid=lineage.copy();invalid.loc[0,'available_at_tca_days']=5.9
    with pytest.raises(ValueError,match='publication time'):lineage_events(messages,invalid,['x'])
    invalid=lineage.copy();invalid.loc[0,'message_index']=1
    with pytest.raises(ValueError,match='order/cardinality'):lineage_events(messages,invalid,['x'])


def test_oracle_only_changes_mean_variance_and_uniform_exactly_equals_singleton():
    messages,lineage=lineage_fixture();e=lineage_events(messages,lineage,['x'])[0]
    base=HistoryTransformer('singleton').fit([e]).transform([e])
    actual=ComponentTransformer('oracle_lineage_weight').fit([e]).transform([e])
    d=len(PHI_NAMES)
    retained=np.r_[np.arange(d),np.arange(3*d,4*d+2)]
    np.testing.assert_array_equal(actual[0][:,retained],base[0][:,retained])
    assert not np.array_equal(actual[0][:,d:3*d],base[0][:,d:3*d])
    for windows in (((0,1),(2,3),(4,5)),((0,1),(0,1),(0,1))):
        uniform=LineageEvent(e.identity,e.raw,windows)
        result=ComponentTransformer('oracle_lineage_weight').fit([uniform]).transform([uniform])
        for a,b in zip(result,base):np.testing.assert_array_equal(a,b)


def test_ordinary_components_ignore_oracle_windows_and_preprocessor_never_refits_on_prediction():
    messages,lineage=lineage_fixture();e=lineage_events(messages,lineage,['x'])[0]
    changed=LineageEvent('renamed',e.raw,((60,),(60,),(60,)))
    for arm in ARMS[:-1]:
        t=ComponentTransformer(arm).fit([e]);state=t.base.scaler.center_.copy()
        for a,b in zip(t.transform([e]),t.transform([changed])):np.testing.assert_array_equal(a,b)
        np.testing.assert_array_equal(t.base.scaler.center_,state)
    e.raw[0,1]=.5
    with pytest.raises(ValueError,match='visible prefix'):ComponentTransformer('grouped_no_age').fit([e])


def campaign_fixture():
    from research.simulation_regimes import scenario_folds
    frame=pd.DataFrame({'series_id':[str(i) for i in range(12)]*2,'condition':['a']*12+['b']*12,
        'y':list(np.arange(12)%2)*2,'event_weight':.5})
    events=[event(str(i)) for i in range(12)]*2
    return frame,events,scenario_folds(frame,3,123)


def test_component_scenario_folds_and_partition_objective(tmp_path):
    import joblib
    from research.artifacts import read_table
    from research.component_campaign import fit_component,validate_splits
    from research.models import MonotonePlatt,policy_threshold
    frame,events,splits=campaign_fixture();validate_splits(frame,events,splits)
    with pytest.raises(ValueError,match='Scenario leakage'):
        validate_splits(frame,events,[(np.arange(12),np.arange(12,24))])
    with pytest.raises(ValueError,match='OOF coverage'):
        validate_splits(frame,events,splits+[splits[0]])
    saved,selection=fit_component(frame,events,'grouped_no_od_readout',splits,[.1,1.],123,tmp_path,'test')
    assert selection['completed_training_fits']==7
    for path in tmp_path.glob('fit_*.json'):
        record=json.loads(path.read_text());assert record['status']=='complete'
        assert record['objective_weight_sum']==pytest.approx(record['fit_scenarios'])
        assert record['design_columns']==74
    for k,(fit,valid) in enumerate(splits):
        m=joblib.load(tmp_path/f'model_test_c{selection["C"]:g}_fold{k}.joblib')
        q=m.predict(np.zeros((len(valid),1)),[events[i] for i in valid])
        recorded=read_table(tmp_path/f'validation_test_c{selection["C"]:g}_fold{k}.parquet')
        np.testing.assert_array_equal(q,recorded.raw_oof)
        assert set(recorded.series_id).isdisjoint(frame.iloc[fit].series_id)
        transform=ComponentTransformer('grouped_no_od_readout').fit([events[i] for i in fit])
        np.testing.assert_array_equal(m.history.base.imputer.statistics_,transform.base.imputer.statistics_)
    oof=read_table(tmp_path/'candidates_test.parquet');chosen=oof[oof.C==selection['C']]
    calibration=MonotonePlatt().fit(chosen.raw_oof.to_numpy(),frame.y.to_numpy())
    assert selection['calibration_slope']==calibration.slope and selection['calibration_intercept']==calibration.intercept
    assert policy_threshold(calibration.predict(chosen.raw_oof),frame.y.to_numpy(),.95)==selection['threshold95']


def test_component_convergence_warning_records_failure_and_stops(tmp_path,monkeypatch):
    import warnings
    from sklearn.exceptions import ConvergenceWarning
    from research.component_campaign import fit_component
    from research.models import ProbabilityModel
    frame,events,splits=campaign_fixture()
    def fail(*args,**kwargs):warnings.warn('synthetic solver failure',ConvergenceWarning)
    monkeypatch.setattr(ProbabilityModel,'fit',fail)
    with pytest.raises(ConvergenceWarning):fit_component(frame,events,'fixed_no_od',splits,[.1,1.],123,tmp_path,'failure')
    records=list(tmp_path.glob('fit_*.json'));assert len(records)==1
    record=json.loads(records[0].read_text());assert record['status']=='failed' and record['failure_type']=='ConvergenceWarning'


def test_component_reconstruction_checks_all_candidates_and_detects_preprocessor_tampering(tmp_path):
    import joblib
    from research.component_campaign import fit_component
    from research.summarize_components import reconstruct_selection
    frame,events,splits=campaign_fixture();name='seed123_no_reuse_only_grouped_no_age'
    _,selection=fit_component(frame,events,'grouped_no_age',splits,[.1,1.],123,tmp_path,name)
    selection.update(seed=123,regime='no_reuse_only')
    _,records,oof=reconstruct_selection(tmp_path,selection,frame,events,splits,[.1,1.],10000)
    assert len(records)==7 and len(oof)==len(frame)
    path=tmp_path/f'model_{name}_c0.1_fold0.joblib';model=joblib.load(path)
    model.history.base.scaler.center_[0]+=1.;joblib.dump(model,path)
    with pytest.raises(AssertionError):reconstruct_selection(tmp_path,selection,frame,events,splits,[.1,1.],10000)


def test_component_paired_endpoints_use_correct_units_and_reject_missing_cases():
    from research.metrics import loss
    from research.summarize_components import paired_comparisons
    rows=[];y=np.array([0,1,0,1]);a=np.array([.1,.9,.1,.9]);b=np.array([.2,.7,.1,.6])
    for seed in (1,2,3):
        for arm in ('grouped_no_age','grouped'):
            for condition in ('no_reuse','overlap_90'):
                q=a if arm=='grouped_no_age' and condition=='overlap_90' else b
                rows.append(pd.DataFrame({'seed':seed,'training_fraction':.8,'regime':'matched_mixture','bank':'software',
                    'arm':arm,'condition':condition,'series_id':list('abcd'),'y':y,'q':q,'review95':q>=.65,'log_loss':loss(y,q)}))
    frame=pd.concat(rows,ignore_index=True);contrasts,ranges=paired_comparisons(frame,arms=('grouped_no_age',))
    r=contrasts[(contrasts.seed==1)&(contrasts.condition=='overlap_90')].iloc[0]
    assert r.log_loss_absolute_difference==pytest.approx((loss(y,a)-loss(y,b)).mean())
    assert r.log_loss_degradation_difference==pytest.approx(r.log_loss_absolute_difference)
    assert r.missed_absolute_difference==-.5 and r.reviewed_absolute_difference==.25
    assert r.evaluation_scenarios==4 and r.positives==2
    r=ranges[ranges.condition=='overlap_90'].iloc[0]
    assert r.component_lower_loss_seeds==3 and r.training_repeats==3 and r.evaluation_scenarios==4
    with pytest.raises(ValueError,match='Incomplete paired'):paired_comparisons(frame.drop(index=0),arms=('grouped_no_age',))
