# Next V02 step: state fusion and unique-observation diagnostics

Prepared 9 October 2026. **Completed on the exposed simulation banks.** The original design and pre-evaluation contract below are retained; completion evidence follows. This extends
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

- [x] Define all formulas, CI objective/tie/failure rules and diagnostic units
  before inspecting comparative results. Preserve exact-replay canonicalization.
- [x] Test scalar/diagonal analytic examples, positive definiteness, identical
  inputs, disjoint-window recovery with the prior counted once, exact replay,
  and a shared-bias oracle against the existing joint-Gaussian calculation.
- [x] Prove visible-only union construction and fail on a later observation ID.
  Reconstruct original messages before interpreting any fusion output.
- [x] Save one state-error/covariance record per scenario, condition and arm.
  Report mean squared state error, error quadratic form, uncertainty area and
  clearly defined ellipse inclusion. Keep disk probability and class `q` in
  separate tables; a larger covariance need not imply a larger disk probability.
- [x] Report all overlap/reissue/new-information and bias conditions, including
  collapsed controls. Pair uncertainty by latent scenario and avoid treating
  messages/variants as new samples. This is exploratory exposed-bank evidence.
- [x] Audit calculations from saved inputs, export compact tables with hashes,
  update the three reports/root handoff, and commit completed work using the
  requested identity.

The fusion runner and reconstruction CLI now exist (commands below). Implementation started with `research/simulation.py`,
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


## Completed evidence and conclusions

Runs `fusion_20261009_v1` and `fusion_summary_20261009_v1` are complete.
[Generated result tables](../results/fusion_2026-10-09/report.md),
[reconstruction audit](../results/fusion_2026-10-09/audit.json),
[verification](fusion_verification.json). The audit exactly reconstructs all
138,000 canonical message records, 126,000 state-estimate records and 21,000
CI weight vectors from the immutable source observations. There are 1,000
independent latent scenarios per bank, not 126,000 independent outcomes.

Software-bank solution reissue leaves the ordinary product's state mean equal
to latest/CI but shrinks its ellipse area sixfold. Gaussian-reference ellipse
inclusion is 386/1,000 for the product and 947/1,000 for latest/CI. Under heavy
overlap, CI squared state error is 0.014655 m^2 versus latest 0.018341 and the
unique-observation oracle 0.012420. The CI-minus-latest paired difference is
-0.003686, with a descriptive percentile interval [-0.004487, -0.002900].
The product has the same mean/error as CI there but a smaller covariance.
These are known information-reuse behaviors reproduced in this controlled model,
not a new CI method or proof of class-forecast efficacy.

For cumulative new information, CI exactly reduces to latest and the bias-omitting
visible-union oracle. On bias stress, their nominal-ellipse inclusion is only
290/1,000, versus 955/1,000 for the oracle supplied with the correct shared-bias
covariance. Their mean squared errors are 0.023562 and 0.023424 respectively.
The oracle's extra information is explicit; it is not an available operational
input. All oracles here retain the working wide Gaussian prior: they are
information/lineage oracles, not proven Bayes-optimal estimators for the enriched
mixture used to sample latent states.

All seven conditions and three banks remain in the exports. The 1,050 contrast
rows use scenario-paired, common bootstrap resampling; intervals are descriptive
and marginal, without a multiplicity or safety guarantee. All production CI
cases take analytic isotropic/tie branches. The general anisotropic optimizer
passes unit examples only; no anisotropic scientific bank was opened.

Commands executed successfully (these run IDs/export paths now exist):

```powershell
.\.venv\Scripts\python.exe -m research.fusion_campaign --source processed/research/cadence_20261009_v1 --truth-source processed/research/simulation_20261009_v1 --run-id fusion_20261009_v1
.\.venv\Scripts\python.exe -m research.summarize_fusion --source processed/research/fusion_20261009_v1 --run-id fusion_summary_20261009_v1 --export docs/research/results/fusion_2026-10-09
.\.venv\Scripts\python.exe -m research.verify_exports --root docs/research/results
```

LOKY_MAX_CPU_COUNT, OMP_NUM_THREADS and MKL_NUM_THREADS were each set to 2 for
these processes. Full suite: **392 passed, 1 skipped** in 59.53 seconds. Five
compact bundles / 47 artifact files pass byte checks. Original 12 raw/data-manifest,
45 historical and eight frozen files retain their hashes. All milestone jobs
have exited; the reserved scientific bank remains ungenerated. This is a
same-workflow reconstruction, not A03 independent scientific review.

Next follow the [sequence-family adaptation plan](sequence_adaptation_plan.md),
starting with dependency and compute-budget preflight. Observable-provenance
component ablations and precision planning also remain. State diagnostics do
not complete those class-forecasting tasks or V02.
