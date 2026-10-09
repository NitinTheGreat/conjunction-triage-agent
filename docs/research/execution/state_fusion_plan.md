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


## Implementation contract recorded before bank evaluation

Implemented six arms: `latest`, `gaussian_product`, `prior_once_product`,
`covariance_intersection`, `oracle_unique`, `oracle_bias_aware`. Ordinary fusion
functions accept only message means/covariances. Only the separate oracle
function receives observation windows and the known bias model. The prior is
N(0, 2.25 I); noise covariance is 0.09 I. Original generator source and input
hashes must agree with the cadence/truth manifests.

For each message let J_i=P_i^-1 and h_i=J_i*m_i. The ordinary product uses
J=sum J_i and h=sum h_i. The prior-once control uses
J=sum J_i-(m-1)I/2.25, with the same h because the prior mean is zero.
Nonpositive or asymmetric matrices fail the run. CI uses
J=sum w_i J_i, h=sum w_i h_i, w_i>=0, sum w_i=1, minimizing log(det(J^-1)).
Identical covariance inputs have uniform weights. For isotropic inputs, give
equal weight to exactly tied smallest variances and zero to others. General
inputs use SLSQP, uniform initialization, ftol=1e-12, at most 1,000 iterations,
simplex feasibility tolerance 1e-10 and convex simplex optimality gap <=1e-7.
Failures are errors, not silent switches to a different method. Record every
weight vector and branch. This is basic precision-weighted CI, not OCI's SDP
or a claim of globally optimal fusion over every possible estimator family.

The [OCI v2 primary paper](https://arxiv.org/html/2603.16768v2), checked again
9 October 2026, distinguishes basic unknown-correlation CI from more general
information structures and discusses the role of covariance assumptions. This
implementation applies the simple CI family as a diagnostic; it does not
reproduce that paper's algorithm or transfer its guarantees to misspecified
shared-bias inputs. No third-party implementation was copied.

Preflight reconstructs all canonical messages across all three exposed banks
before any fused-state outcome is computed. It checks saved risk, miss distance,
six sigmas, message/lineage ordering, source solution IDs and observation
availability. IDs >=60 fail; exact retransmissions are canonicalized under the
existing source-time convention. The future 20 observations do not enter any
state estimate. Latent arrays are aligned by the unchanged original cohort order.

Report squared Euclidean state error (m^2), error quadratic form (dimensionless),
covariance trace (m^2), and Gaussian-reference 95% ellipse area/inclusion.
The reference ellipse is e'P^-1 e <= chi2_2(0.95); its area is
pi*chi2_2(0.95)*sqrt(det P). This is a diagnostic of nominal Gaussian uncertainty,
not a claim that the enriched stress population has 95% Bayesian coverage.
Use unweighted stress summaries only in this campaign; the wide-prior target
and importance-weighted inference remain unclaimed. No fused Pc or class q is
scored in these state tables.

Prespecified descriptive contrasts: each other arm versus latest; product,
prior-once product and CI versus the bias-aware oracle; prior-once product versus
ordinary product; bias-aware versus bias-omitting oracle. Retain all conditions.
Use the same 2,000 scenario-multinomial bootstrap resamples across all arms and
conditions within each bank (base seed 20261040, bank offset in recorded order).
Report marginal percentile intervals, without multiplicity correction or
confirmatory significance claims. Include absolute squared error, quadratic
error, ellipse inclusion/area and squared-error degradation from no reuse.
Do not pool messages, conditions or banks to increase independent case counts.

Focused implementation tests: **19 passed** in 2.78 seconds. Checks include an
analytic anisotropic CI example, disjoint-observation prior correction, shared
bias versus full-joint Gaussian conditioning, invalid inputs/failed optimizer,
message reconstruction, exact replay/order invariance and mutation of all later
observations to NaN without changing a visible-state estimate.
