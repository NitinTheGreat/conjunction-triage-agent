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
