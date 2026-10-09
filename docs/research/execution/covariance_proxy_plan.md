# Next V02 step: covariance-proxy comparator

Prepared 9 October 2026 from the inspected implementation and the
[closest-work method notes](closest_work_comparison.md). **Design only: this
comparator has not been implemented or evaluated.** Preserve the current nine-arm
campaign and its tuning results as a separate development experiment.

## Concrete issue to resolve first

The current simulator has two state dimensions. It exports positive radial and
tangential sigma components but sets both normal sigma components to zero
(`research/simulation.py`). Multiplying all three diagonal variance components
would therefore give zero for every message. It would be a broken comparator,
not an informative negative result.

The real-data allowlist has six marginal sigmas but no complete encounter-plane
covariance transformation. A determinant of those marginal components is not the
combined encounter-plane determinant in Sanchez et al. Do not describe the
following approximation as a reproduction of the paper or as Dempster–Shafer
inference.

## Proposed, testable approximation

Use the explicitly named **radial/tangential diagonal-volume trend proxy**:

1. Canonicalize the visible prefix with the existing replay/order convention.
2. For each message, calculate `v_r = t_sigma_r^2 + c_sigma_r^2` and
   `v_t = t_sigma_t^2 + c_sigma_t^2`. Define `log_volume = log(v_r) + log(v_t)`.
   This assumes aligned diagonal coordinates for the proxy. Real object RTN
   frames need not coincide, and normal uncertainty/correlations are omitted.
3. Use elapsed publication time from the oldest to latest visible message,
   scaled to [0, 1]. Fit a straight line to log volume versus this elapsed time
   within that prefix. Normalize inverse fitted-volume weights using a stable
   exponential calculation. This log-linear fit is an explicitly changed
   weighting rule, not an asserted transcription of the published estimator.
4. Use these weights for the existing history mean and variance summaries,
   retaining the latest-message features and training-only preprocessing.
   Produce one summary per event, with total scenario objective weight one.
   Define the count feature consistently with the singleton comparator.
5. For fewer than two distinct times, a constant volume, or any missing,
   nonfinite or nonpositive required variance, use uniform weights for the
   whole prefix. Save reason counts. Do not impute a covariance and then claim
   physically meaningful precision weights. Squaring a negative sigma must not
   silently turn it into a valid input: reject it or use the declared fallback.

The inverse fitted weights are a predictive representation only. They do not
estimate the number of independent observations, supply an iid confidence
bound, or certify a physical collision probability. Publication time is visible;
future messages and oracle observation IDs must never enter this comparator.

## Acceptance checklist and expected evidence

- [ ] Implement the proxy in a separate, clearly named module or transformer
  mode. Record exact field mapping and fallback semantics before model fitting.
- [ ] Check analytic equal-volume and exponential-volume examples, finite
  normalized weights, common sigma-unit rescaling, tied times, missing/invalid
  sigmas, and single-message prefixes. Equal covariance must produce uniform
  pooling; it cannot identify repeated data by itself.
- [ ] Check exact replay/order invariance, post-cutoff mutation invariance and
  training-only preprocessing. Use existing fold and scenario-weight contracts.
- [ ] Audit weight distributions and fallback counts on the **exposed** banks
  before evaluating predictive loss. Existing overlap/reissue windows have
  constant nominal covariance, so several conditions should collapse to uniform
  pooling by construction. New-information histories can vary in covariance.
- [ ] Add a direct inverse-volume ablation to distinguish the proposed fitted
  trend from direct weighting, plus the existing uniform/singleton control.
  Keep the feature/readout and preprocessing contracts comparable.
- [ ] Evaluate under the same two training regimes, common C grid, convergence
  policy, scenario folds, subsets, calibration and endpoints. Record any compute
  deviation explicitly. Reuse compatible saved comparator results only after
  checking hashes, data, folds and budgets; do not train just the new method on
  favorable cases.
- [ ] Export all conditions, fallback diagnostics, selected parameters and
  paired absolute-loss/degradation comparisons. Report an exact collapse to
  uniform pooling or a worse result without treating it as a software failure.
- [ ] Update the V02 record and root handoff, run relevant checks, and commit
  only completed code, tests and compact evidence under the requested identity.

No production runner command exists for this task yet. Start by reading
`research/history.py`, `research/simulation.py`, `research/simulation_regimes.py`
and this plan. State-fusion/oracle diagnostics and the sequence-family
adaptation remain separate subsequent steps. Keep the reserved scientific bank
unopened until V03.


## Implementation contract recorded before fitting

The implemented modes are `covariance_trend` and `covariance_direct` in
`research/covariance_proxy.py`, used only by new branches of the history
transformer. Feature width, count (= canonical message count), missingness
features, preprocessing and one total scenario objective weight match singleton
pooling. The trend is an unweighted least-squares log-volume slope against
normalized elapsed publication time; direct weighting uses negative log volume.
Both normalize with a shifted exponential. A common sigma-unit change cancels.
No covariance imputation or outcome-dependent weighting is introduced.

Fallback precedence is invalid/negative sigma, zero combined radial or tangential
variance, invalid time, fewer than two distinct times, then log-volume range at
most 1e-12. Fallback weights are exactly uniform. An individual zero sigma is
allowed if the paired combined variance stays positive. Normal sigmas are not
used. The upstream canonicalizer rejects infinite source values; the numerical
helper additionally defines a uniform fallback for standalone nonfinite inputs.

The runner `research.covariance_campaign` takes `--source`, `--reference` and
`--run-id`. It inherits all four trials, both regimes, the six-candidate C grid,
three folds and 10,000-iteration cap from the completed tuning reference. This
adds 16 models and 224,000 predictions on the same exposed evaluation cases.
It verifies source hashes, unchanged shared fitting modules and exact legacy
history syntax after removing only the new-mode import/guard. It reconstructs
and compares every cohort/fold membership with the reference before fitting.
The nine archived control arms are reused with their existing tuning budgets;
no new control scores or extra independent cases are created.

Before the first fit, save per-event and aggregate weight diagnostics for all
three exposed banks/seven conditions. Require constant-volume conditions to be
exactly uniform and new-information conditions to have nonuniform weights.
Inverse squared-weight concentration is descriptive, not an effective number
of independent observations. For no-reuse-only training, also require selected
C, OOF predictions, threshold and constant-condition evaluation predictions to
match the saved singleton model. Under matched training, differing weighted
new-information training rows can change fitted coefficients even when an
evaluation prefix has constant covariance; do not demand equal predictions there.

Focused validation before the campaign: 19 tests passed in 5.66 seconds, covering
the new numerical/information-boundary checks and existing model/regime tests.
The run manifest must still complete and its artifacts reconstruct before the
evaluation/export acceptance boxes can be checked.
