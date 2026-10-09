"""Controlled 2D observation-window experiment, not an orbital Pc pipeline."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.polynomial.legendre import leggauss
from scipy.integrate import quad
from scipy.special import ndtr
from scipy.stats import ncx2,multivariate_normal

from research.artifacts import ROOT,Run,write_json,write_table
from research.data import RAW_FIELDS

RADIUS=.02
PRIOR_VARIANCE=2.25
NOISE_VARIANCE=.09
CONDITIONS=('no_reuse','overlap_50','overlap_90','solution_reissue','exact_replay','new_information')


def posterior(observations, noise_covariance, common_bias_covariance=None):
    """Joint Gaussian oracle: covariance of the sample mean is R/n+B."""
    n=len(observations)
    if not n:raise ValueError('At least one observation required')
    B=np.zeros((2,2)) if common_bias_covariance is None else common_bias_covariance
    information=np.linalg.inv(noise_covariance/n+B)
    covariance=np.linalg.inv(np.eye(2)/PRIOR_VARIANCE+information)
    mean=covariance@information@np.mean(observations,axis=0)
    return mean,covariance


def disk_probability(mean,covariance,radius=RADIUS):
    if np.allclose(covariance,np.eye(2)*covariance[0,0],rtol=1e-12,atol=1e-15):
        scale=covariance[0,0]
        return float(ncx2.cdf(radius**2/scale,2,np.dot(mean,mean)/scale))
    # Fixed product quadrature for non-isotropic configurations.
    nodes,weights=leggauss(40)
    r=(nodes+1)*radius/2;theta=(nodes+1)*np.pi
    xx=np.stack([r[:,None]*np.cos(theta)[None,:],r[:,None]*np.sin(theta)[None,:]],axis=-1)
    density=multivariate_normal.pdf(xx,mean=mean,cov=covariance)
    return float(np.sum(density*r[:,None]*weights[:,None]*weights[None,:])*radius/2*np.pi)


def disk_probability_check(mean,covariance,radius=RADIUS):
    """Independent Cartesian conditional-normal quadrature."""
    sx=np.sqrt(covariance[0,0]); beta=covariance[1,0]/covariance[0,0]
    sy=np.sqrt(covariance[1,1]-covariance[1,0]**2/covariance[0,0])
    def integrand(x):
        h=np.sqrt(max(0,radius**2-x*x)); conditional=mean[1]+beta*(x-mean[0])
        normal=np.exp(-.5*((x-mean[0])/sx)**2)/(np.sqrt(2*np.pi)*sx)
        return normal*(ndtr((h-conditional)/sy)-ndtr((-h-conditional)/sy))
    return float(quad(integrand,-radius,radius,epsabs=1e-12,epsrel=1e-8,limit=200)[0])


def windows(condition):
    if condition in ('no_reuse','exact_replay'): return [np.arange(start,start+10) for start in range(0,60,10)]
    if condition=='overlap_50':return [np.arange(start,start+10) for start in range(25,55,5)]
    if condition=='overlap_90':return [np.arange(start,start+10) for start in range(45,51)]
    if condition=='solution_reissue':return [np.arange(50,60) for _ in range(6)]
    if condition=='new_information':return [np.arange(stop) for stop in range(10,61,10)]
    raise ValueError(condition)


def generate_bank(n,seed,bank,shared_bias=False):
    rng=np.random.default_rng(seed)
    messages=[];lineage=[];cohort=[];states=[];observations_all=[]
    R=np.eye(2)*NOISE_VARIANCE
    B=np.eye(2)*(.01 if shared_bias else 0.)
    # First 60 observations exist before the earliest visible message; later 20
    # become available inside the two-day cutoff and only define final labels.
    availability=np.r_[np.linspace(8.,6.1,60),np.linspace(1.,.1,20)]
    for i in range(n):
        sid=f'{bank}:{i:05d}'
        enriched=rng.random()<.3
        x=rng.normal(0,.12 if enriched else 1.5,size=2)
        bias=rng.multivariate_normal(np.zeros(2),B)
        obs=x+bias+rng.multivariate_normal(np.zeros(2),R,size=80)
        final_mean,final_covariance=posterior(obs,R,B)
        final_risk=float(np.log10(max(disk_probability(final_mean,final_covariance),1e-30)))
        target_density=multivariate_normal.pdf(x,cov=np.eye(2)*PRIOR_VARIANCE)
        proposal_density=.7*target_density+.3*multivariate_normal.pdf(x,cov=np.eye(2)*.12**2)
        cohort.append({'series_id':sid,'final_risk':final_risk,'mission_id':bank,
                       'sampling_weight_to_wide_gaussian':float(target_density/proposal_density),
                       'enriched_component':enriched,'shared_bias':shared_bias})
        states.append(x);observations_all.append(obs)
        for condition in CONDITIONS:
            for j,(indices,tau) in enumerate(zip(windows(condition),np.linspace(6.,2.,6))):
                assert np.all(availability[indices]>=tau)
                # Experimental estimator ignores shared bias; final-label oracle does not.
                mean,covariance=posterior(obs[indices],R)
                pc=disk_probability(mean,covariance)
                row={name:0. for name in RAW_FIELDS}
                row.update(series_id=sid,condition=condition,risk=float(np.log10(max(pc,1e-30))),
                           time_to_tca=float(tau),miss_distance=float(np.linalg.norm(mean)),relative_speed=0.)
                age=float(availability[indices].min()-tau)
                bounds=(0.,1.) if age<1 else ((1.,2.) if age<2 else (2.,180.))
                for role in ('t','c'):
                    row[f'{role}_sigma_r']=float(np.sqrt(covariance[0,0]/2))
                    row[f'{role}_sigma_t']=float(np.sqrt(covariance[1,1]/2))
                    row[f'{role}_sigma_n']=0.
                    row[f'{role}_obs_available']=60.
                    row[f'{role}_obs_used']=float(len(indices))
                    row[f'{role}_actual_od_span']=float(np.ptp(availability[indices]))
                    row[f'{role}_recommended_od_span']=1.
                    row[f'{role}_residuals_accepted']=100.
                    row[f'{role}_weighted_rms']=float(np.sqrt(np.mean((obs[indices]-mean)**2)/NOISE_VARIANCE))
                    row[f'{role}_time_lastob_end'],row[f'{role}_time_lastob_start']=bounds
                messages.append(row)
                lineage.append({'series_id':sid,'condition':condition,'message_index':j,
                                'observation_ids':json.dumps(indices.tolist()),'available_at_tca_days':float(tau),
                                'source_solution_id':','.join(map(str,indices))})
                if condition=='exact_replay':messages.extend([row.copy(),row.copy()])
    return pd.DataFrame(cohort),pd.DataFrame(messages),pd.DataFrame(lineage),np.asarray(states),np.asarray(observations_all)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--n',type=int,default=1000)
    args=parser.parse_args()
    cfg={'n_per_bank':args.n,'seed_development':20261010,'seed_software_validation':20261011,
         'sampling':'0.3*N(0,0.12^2 I)+0.7*N(0,1.5^2 I); unweighted stress results are not operational prevalence',
         'wide_population_weights_saved':True,'conditions':list(CONDITIONS),'radius_m':RADIUS,
         'model':'static 2D encounter plane; no validated dynamics/OD system',
         'unit_note':'internally consistent metres; physical scale is a synthetic design choice',
         'latest_window_identical_across_overlap_conditions':True,'final_observation_bank_size':80}
    with Run(args.run_id,'simulation_software_pilot',cfg) as run:
        write_json(run.path/'reservation.json',{'written_before_generation':True,
            'development':{'seed':20261010,'ids':f'development:00000..{args.n-1:05d}'},
            'software_validation':{'seed':20261011,'ids':f'software:00000..{args.n-1:05d}'},
            'scientific_reserved':{'seed':20261012,'ids':'scientific:00000..04999','generated':False,
                'candidate_unseen_configuration':'anisotropic observation noise variance ratio 4, rotated 30 degrees',
                'sample_size_and_configuration_freeze':'V03 still required before generation/evaluation'},
            'rule':'whole latent scenarios; all message/window variants stay in the same bank'})
        checks=[]
        for mean,covariance in [(np.array([.01,.01]),np.eye(2)*.01),
                               (np.array([.2,.02]),np.eye(2)*.002),
                               (np.array([.03,-.02]),np.array([[.01,.003],[.003,.02]]))]:
            a=disk_probability(mean,covariance);b=disk_probability_check(mean,covariance)
            if not np.isclose(a,b,rtol=1e-6,atol=1e-11):raise ValueError('Probability integration check failed')
            checks.append({'main':a,'independent':b,'absolute_difference':abs(a-b)})
        counts={}
        for bank,seed,bias in [('development',20261010,False),('software',20261011,False),('bias_stress',20261013,True)]:
            run.access(bank,'software and mechanism pilot; not scientific confirmation','generated development/exploratory outcomes')
            cohort,messages,ids,states,observations=generate_bank(args.n,seed,bank,bias)
            write_table(run.path/f'cohort_{bank}.parquet',cohort)
            write_table(run.path/f'messages_{bank}.parquet',messages)
            write_table(run.path/f'lineage_{bank}.parquet',ids)
            np.savez_compressed(run.path/f'truth_{bank}.npz',states=states,observations=observations)
            counts[bank]={'scenarios':len(cohort),'positives':int((cohort.final_risk>=-6).sum()),'messages':len(messages)}
            print(bank,counts[bank],flush=True)
        write_json(run.path/'validation.json',{'integration_checks':checks,'banks':counts,
                   'scientific_bank_generated':False,'limitations':['No orbital dynamics validation','Simulated conditional mechanism only','Enriched synthetic prevalence']})


if __name__=='__main__':main()
