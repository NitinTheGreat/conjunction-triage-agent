# Next V02 step: state fusion and unique-observation diagnostics

Prepared 9 October 2026. **Design only; no fusion campaign has run.** This extends
the [closest-work compatibility decision](closest_work_comparison.md) and keeps
state estimation separate from calibrated final-risk-class forecasting.

## Inputs and boundary

Use the exposed `simulation_20261009_v1` latent states/observations and the
`cadence_20261009_v1` message lineage. Verify both manifests and their relationship.
Reconstruct each visible message's Gaussian mean/covariance from its observation
window using the original estimator; check its saved risk, miss distance and
sigma fields. The static simulation already has common coordinates and epoch.
This does not establish compatible geometry for real CDMs.

Ordinary fusion controls receive only the reconstructed message means/covariances.
Only the explicitly named oracle uses observation IDs and the known shared-bias
model. Use the union of **visible** observation IDs (indices 0-59); observations
60-79 are later and must not enter any visible-state estimate. Final recorded
risk labels may remain reported context, never the fitting target for this
diagnostic. Do not generate the reserved scientific bank.

## Controls to define before evaluation

- Latest visible Gaussian estimate.
- Product of message Gaussians: sum their precision matrices and information
  vectors. Label this an independence approximation/failure control.
- Independence approximation with the common prior counted once. For `m`
  messages, subtract `(m-1)` copies of prior precision from the Gaussian-product
  precision; the current zero-mean prior contributes zero information vector.
  Check positive definiteness. This separates overlap double-counting from
  repeated use of the same prior. Do not claim it resolves shared observations.
- Basic covariance intersection (CI): define its simplex weight objective,
  numerical tolerances and deterministic tie rule in the implementation plan.
  Use precision averaging and the corresponding mean. No unknown-correlation
  protection is claimed when input covariance matrices omit shared bias.
- Unique-visible-observation oracle with the original prior counted once; run
  both bias-omitting and bias-aware versions on the same observation union.
  The latter uses the known `R/n + B` covariance of the sample mean. Its extra
  information is an oracle advantage and must be labeled.

## Important limitations visible before fitting

The existing message covariances are isotropic. For equal message covariance,
the usual covariance-only CI objective cannot identify a preferred weight vector;
a deterministic tie rule must not be sold as learned overlap handling. For the
cumulative new-information histories, the last estimate already uses the full
visible union. Report exact collapses to latest-only/oracle where they occur.
Use fixed anisotropic numerical examples to test the solver; any new anisotropic
**development** campaign requires a separately recorded design. Never consume
the reserved scientific configuration merely to make CI look informative.

The latent sampling law is an enriched Gaussian mixture. Unweighted mean-square
error and ellipse inclusion describe that stress population. They are not a
calibration theorem under the estimator's wide Gaussian prior. If reporting
importance-weighted diagnostics for the wide population, use the saved proposal
weights, identify the estimand and uncertainty method, and retain unweighted
stress results. Do not turn inverse weight concentration into new independent
cases.

## Acceptance checklist and expected evidence

- [ ] Define all formulas, CI objective/tie/failure rules and diagnostic units
  before inspecting comparative results. Preserve exact-replay canonicalization.
- [ ] Test scalar/diagonal analytic examples, positive definiteness, identical
  inputs, disjoint-window recovery with the prior counted once, exact replay,
  and a shared-bias oracle against the existing joint-Gaussian calculation.
- [ ] Prove visible-only union construction and fail on a later observation ID.
  Reconstruct original messages before interpreting any fusion output.
- [ ] Save one state-error/covariance record per scenario, condition and arm.
  Report mean squared state error, error quadratic form, uncertainty area and
  clearly defined ellipse inclusion. Keep disk probability and class `q` in
  separate tables; a larger covariance need not imply a larger disk probability.
- [ ] Report all overlap/reissue/new-information and bias conditions, including
  collapsed controls. Pair uncertainty by latent scenario and avoid treating
  messages/variants as new samples. This is exploratory exposed-bank evidence.
- [ ] Audit calculations from saved inputs, export compact tables with hashes,
  update the three reports/root handoff, and commit completed work using the
  requested identity.

No fusion runner CLI exists yet. Start with `research/simulation.py`,
`research/simulation_v2.py` and the existing Gaussian numerical tests. Sequence
adaptation, provenance-component ablations and precision planning still remain;
this task alone will not complete V02.
