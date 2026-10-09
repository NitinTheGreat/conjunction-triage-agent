"""Visible-prefix diagonal-volume approximations, not encounter-plane fusion."""
from __future__ import annotations

import numpy as np

from research.data import RAW_FIELDS

PROXY_ARMS = ('covariance_trend', 'covariance_direct')
SIGMA_FIELDS = ('t_sigma_r', 'c_sigma_r', 't_sigma_t', 'c_sigma_t')
CONSTANT_LOG_TOLERANCE = 1e-12


def covariance_weights(raw, mode):
    """Return message weights and a diagnostic reason; never use learned imputation.

    Input rows must be the visible, canonicalized prefix. Zero individual sigmas
    are allowed if the corresponding combined diagonal variance is positive.
    Infinite source fields are rejected earlier by canonicalize; this numerical
    helper also defines their uniform fallback for standalone diagnostics.
    """
    if mode not in PROXY_ARMS:
        raise ValueError(f'Unknown covariance proxy mode: {mode}')
    raw = np.asarray(raw, dtype=float)
    if raw.ndim != 2 or raw.shape[1] != len(RAW_FIELDS) or not len(raw):
        raise ValueError('Expected a nonempty allowlisted message matrix')
    uniform = np.full(len(raw), 1. / len(raw))
    sigma = raw[:, [RAW_FIELDS.index(name) for name in SIGMA_FIELDS]]
    if not np.isfinite(sigma).all() or (sigma < 0).any():
        return uniform, 'invalid_sigma'
    if ((sigma[:, :2] == 0).all(axis=1) | (sigma[:, 2:] == 0).all(axis=1)).any():
        return uniform, 'nonpositive_variance'
    time = raw[:, RAW_FIELDS.index('time_to_tca')]
    if not np.isfinite(time).all():
        return uniform, 'invalid_time'
    span = float(time.max() - time.min())
    if not np.isfinite(span):
        return uniform, 'invalid_time'
    if span == 0:
        return uniform, 'insufficient_times'
    # Log arithmetic avoids overflow/underflow when common sigma units change.
    with np.errstate(divide='ignore'):
        logs = 2 * np.log(sigma)
    volume = np.logaddexp(logs[:, 0], logs[:, 1]) + np.logaddexp(logs[:, 2], logs[:, 3])
    if np.ptp(volume) <= CONSTANT_LOG_TOLERANCE:
        return uniform, 'constant_volume'
    if mode == 'covariance_trend':
        elapsed = (time.max() - time) / span
        centered = elapsed - elapsed.mean()
        slope = np.dot(centered, volume - volume.mean()) / np.dot(centered, centered)
        log_weight = -slope * elapsed  # The intercept cancels in normalization.
    else:
        log_weight = -volume
    weight = np.exp(log_weight - log_weight.max())
    weight /= weight.sum()
    if not np.isfinite(weight).all():
        raise ValueError('Nonfinite normalized covariance-proxy weights')
    return weight, 'weighted'
