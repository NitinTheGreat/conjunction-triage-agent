"""Static Gaussian fusion diagnostics; no class forecasting or orbital geometry."""
from __future__ import annotations

import numpy as np
from scipy.optimize import minimize
from scipy.stats import chi2

from research.simulation import NOISE_VARIANCE, PRIOR_VARIANCE, posterior

ELLIPSE95 = float(chi2.ppf(.95, df=2))
FUSION_ARMS = ('latest', 'gaussian_product', 'prior_once_product',
               'covariance_intersection', 'oracle_unique', 'oracle_bias_aware')


def check_spd(matrix):
    matrix = np.asarray(matrix, dtype=float)
    if matrix.shape != (2, 2) or not np.isfinite(matrix).all():
        raise ValueError('Expected a finite 2x2 covariance/precision')
    if not np.allclose(matrix, matrix.T, rtol=0, atol=1e-12):
        raise ValueError('Matrix must be symmetric')
    try:
        np.linalg.cholesky(matrix)
    except np.linalg.LinAlgError as error:
        raise ValueError('Matrix must be positive definite') from error
    return matrix


def ci_weights(covariances):
    """Minimize log(det P_CI) on the simplex, failing on solver/KKT violations.

    Exact identical covariances get uniform weights. Isotropic inputs get equal
    weights on exactly tied minimum-variance matrices and zero on others. Other
    inputs use SLSQP with a uniform start; their numeric weights are recorded.
    This is basic precision-weighted CI, not the more general OCI SDP.
    """
    covariance = np.asarray([check_spd(p) for p in covariances])
    if not len(covariance):
        raise ValueError('At least one estimate required')
    n = len(covariance)
    if all(np.array_equal(p, covariance[0]) for p in covariance):
        return np.full(n, 1/n), 'identical_covariance_uniform', 0.
    if all(np.array_equal(p, np.eye(2)*p[0, 0]) for p in covariance):
        tied = covariance[:, 0, 0] == covariance[:, 0, 0].min()
        return tied.astype(float)/tied.sum(), 'isotropic_minimum_equal_ties', 0.
    precision = np.linalg.inv(covariance)

    def objective(w):
        information = np.einsum('i,ijk->jk', w, precision)
        sign, determinant = np.linalg.slogdet(information)
        if sign <= 0:
            raise ValueError('Nonpositive CI information determinant')
        inverse = np.linalg.inv(information)
        gradient = -np.einsum('ij,kji->k', inverse, precision)
        return -determinant, gradient

    fitted = minimize(objective, np.full(n, 1/n), jac=True, method='SLSQP',
        bounds=[(0., 1.)]*n, constraints={'type': 'eq', 'fun': lambda w: w.sum()-1,
                                        'jac': lambda w: np.ones(n)},
        options={'maxiter': 1000, 'ftol': 1e-12})
    w = fitted.x
    if (not fitted.success or not np.isfinite(w).all() or w.min() < -1e-10 or
            abs(w.sum()-1) > 1e-10):
        raise RuntimeError('CI optimization failed; no silent fallback')
    w = np.maximum(w, 0); w /= w.sum()
    _, gradient = objective(w)
    gap = float(np.dot(w, gradient)-gradient.min())
    if gap > 1e-7:
        raise RuntimeError('CI simplex optimality gap exceeds tolerance')
    return w, 'slsqp_uniform_start', gap


def fuse_gaussians(means, covariances):
    """Ordinary controls receive Gaussian estimates only, never lineage/truth."""
    means = np.asarray(means, dtype=float)
    covariance = np.asarray([check_spd(p) for p in covariances])
    if means.shape != (len(covariance), 2) or not len(means) or not np.isfinite(means).all():
        raise ValueError('Expected one finite 2D mean per covariance')
    precision = np.linalg.inv(covariance)
    information = np.einsum('nij,nj->ni', precision, means)

    def estimate(J, h):
        P = np.linalg.inv(check_spd(J))
        return P @ h, P

    product_J = precision.sum(axis=0)
    w, method, gap = ci_weights(covariance)
    result = {'latest': (means[-1].copy(), covariance[-1].copy()),
        'gaussian_product': estimate(product_J, information.sum(axis=0)),
        'prior_once_product': estimate(product_J-(len(means)-1)*np.eye(2)/PRIOR_VARIANCE,
                                       information.sum(axis=0)),
        'covariance_intersection': estimate(np.einsum('i,ijk->jk', w, precision), w @ information)}
    return result, {'weights': w.tolist(), 'method': method, 'optimality_gap': gap}


def visible_union(windows, visible_count=60):
    if not windows:
        raise ValueError('At least one visible observation window required')
    validated = []
    for ids in windows:
        a = np.asarray(ids)
        if a.ndim != 1 or not len(a) or a.dtype.kind not in 'iu':
            raise ValueError('Observation IDs must be a nonempty integer sequence')
        if len(np.unique(a)) != len(a):
            raise ValueError('Repeated observation ID within one window')
        if a.min() < 0 or a.max() >= visible_count:
            raise ValueError('Observation outside visible boundary')
        validated.append(a)
    return np.unique(np.concatenate(validated))


def oracle_estimates(observations, windows, shared_bias):
    ids = visible_union(windows)
    observed = np.asarray(observations, dtype=float)[ids]
    if observed.shape != (len(ids), 2) or not np.isfinite(observed).all():
        raise ValueError('Invalid visible observations')
    noise = np.eye(2)*NOISE_VARIANCE
    bias = np.eye(2)*(.01 if shared_bias else 0.)
    return {'oracle_unique': posterior(observed, noise),
            'oracle_bias_aware': posterior(observed, noise, bias)}, ids


def state_metrics(mean, covariance, truth):
    covariance = check_spd(covariance)
    error = np.asarray(mean)-np.asarray(truth)
    if error.shape != (2,) or not np.isfinite(error).all():
        raise ValueError('Expected finite 2D state error')
    quadratic = float(error @ np.linalg.solve(covariance, error))
    return {'squared_error': float(error @ error), 'quadratic_error': quadratic,
            'covariance_trace': float(np.trace(covariance)),
            'ellipse_area95': float(np.pi*ELLIPSE95*np.sqrt(np.linalg.det(covariance))),
            'ellipse_contains95': quadratic <= ELLIPSE95}
