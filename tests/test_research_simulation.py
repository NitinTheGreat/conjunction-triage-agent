import numpy as np
from research.simulation import posterior,windows,disk_probability,disk_probability_check,generate_bank


def test_posterior_equals_full_joint_gaussian_update_with_shared_bias():
    obs=np.array([[.1,.3],[.2,.1],[-.1,.2]])
    R=np.diag([.09,.16]);B=np.eye(2)*.02
    mean,cov=posterior(obs,R,B)
    H=np.tile(np.eye(2),(len(obs),1))
    joint=np.kron(np.eye(len(obs)),R)+np.kron(np.ones((len(obs),len(obs))),B)
    truth=np.linalg.inv(np.eye(2)/2.25+H.T@np.linalg.solve(joint,H))
    np.testing.assert_allclose(cov,truth)
    np.testing.assert_allclose(mean,truth@H.T@np.linalg.solve(joint,obs.ravel()))


def test_window_overlap_and_integration():
    for name,expected in [('no_reuse',0),('overlap_50',5),('overlap_90',9),('solution_reissue',10)]:
        w=windows(name)
        assert len(set(w[0])&set(w[1]))==expected
        assert list(w[-1])==list(range(50,60))
    for covariance in [np.eye(2)*.01,np.array([[.01,.003],[.003,.02]])]:
        assert np.isclose(disk_probability(np.array([.01,.02]),covariance),
                          disk_probability_check(np.array([.01,.02]),covariance),rtol=1e-6)


def test_scenario_labels_and_latest_update_are_coupled_across_reuse():
    cohort,messages,lineage,states,observations=generate_bank(2,7,'test')
    assert len(cohort)==2 and observations.shape==(2,80,2)
    assert set(lineage.series_id)==set(cohort.series_id)
    for sid,g in messages.groupby('series_id'):
        rows=g[(g.time_to_tca==2)&g.condition.isin(['no_reuse','overlap_50','overlap_90','solution_reissue'])]
        assert rows.risk.nunique()==1 and rows.miss_distance.nunique()==1
        assert len(g[g.condition=='exact_replay'])==3*len(g[g.condition=='no_reuse'])
