# Track R analysis specification (V02 §3 draft for V03)

**Status: complete V02 specification, 10 October 2026.** Every section is filled
from development evidence. V03 transcribes it into the frozen `protocol.json`; this
document becomes immutable only through that freeze. The scientific reservation
remains ungenerated.

## 1. Population, unit and estimands

- **Population:** latent encounter-plane scenarios from the V03-fixed simulator
  configuration, sampled with the enriched synthetic mixture (unweighted). It is
  a stress population, not operational prevalence or workload.
- **Unit:** the whole latent scenario. All reuse variants of a scenario share its
  observation bank and final-risk label. No message, variant or prediction row is
  an independent unit.
- **Primary estimand P1** ([primary contrast](primary_contrast.md)): the
  scenario-mean degradation contrast of `singleton` minus `latest_metadata` at
  `overlap_90` versus `no_reuse`, using clipped log loss (1e-6).
- **Confirmatory secondary estimands:** S1, S5, S2 and S3, as defined there and
  with the hypotheses in §5. S6 and S4 are exploratory.
- **Averaging:** every estimand is averaged over the K independent training banks
  of §3 as well as over scenarios.

## 2. Information flow and split roles

| Stage | Data | May use labels? | Fixed by |
|---|---|---|---|
| Protocol choices | Exposed development banks (pilot, cadence, sensitivity runs) | Yes; exposed | Before V03 freeze |
| Model selection (C) | Inner 3-fold whole-scenario CV within each scientific training bank | Training labels only | Frozen code and grid |
| Monotone calibration and 95% training-recall threshold | Selected inner-OOF predictions of the same training bank | Training labels only | Frozen code |
| Refit | Full training bank at the selected C | Training labels only | Frozen code |
| Scientific evaluation | Scientific evaluation bank | Labels joined only after predictions and model hashes are written | Frozen run script |

Required checks before V04:
- **Two-phase evaluation:** predictions and fitted-model hashes are written
  before evaluation labels are read.
- **Label-insensitivity:** shuffling evaluation labels changes no saved
  prediction, model or threshold.
- **Selection reuse:** selected OOF predictions are reused for selection,
  calibration and thresholding. That reuse is a declared limitation; it does not
  certify risk.

These checks are implemented in `research/track_r_scientific.py` (`25d4854`):
- Phase 2 writes `sealed_labels.parquet`, `predictions_unlabeled.parquet` and
  `phase2_commit.json` before any label is joined.
- `tests/test_research_track_r_scientific.py` permutes the generator's labels and
  confirms the phase-2 predictions are identical.

## 3. Training-bank design and what the interval covers

**Decision: a procedure-level estimand.** The scientific run fits the frozen
procedure on **K = 10 independently generated training banks** of 1,000
scenarios each, generated under the scientific configuration with seeds added
to the reservation before any generation. All banks are evaluated on the same
**n = 5,000** scientific evaluation scenarios. Each contrast is averaged over
banks and scenarios. Its interval includes both evaluation-scenario and
training-bank variation (§4).

**Evidence.** Run `sensitivity_20261010_v1` and the
[sensitivity summary](../results/sensitivity_2026-10-10/report.md) used six
independent isotropic training banks and a fresh 2,000-scenario evaluation bank:

- **P1 bank means:** 0.051-0.074, between-bank SD 0.0080. The earlier
  overlapping trials (SD 0.0022) understated this by a factor of about 3.6.
- **Two-way components for P1:** scenario 0.1224, bank 6.1e-5, interaction 0.0052.
- **Projected P1 SE at n = 5,000:** 0.0093 with one bank, 0.0061 with five, and
  0.0055 with ten. Conditioning on a single fitted bank would report 0.0051,
  understating the procedure-level SE by about 45%.
- **Method contrasts:** for S2 and S3 the bank component dominates. With one
  bank, a conditional SE (0.0011 and 0.0007) would understate the procedure-level
  SE (0.0039 and 0.0033) by a factor of 3.5-5. With ten banks the procedure-level
  SEs are 0.0015 and 0.0011.

**Train in-configuration.** Training banks use the scientific configuration
rather than transferring isotropic-trained models. Transfer mixed configuration
shift into the reuse contrast: isotropic-trained P1 was 0.106 under doubled
noise versus 0.048 native, and -0.131 under shared bias versus +0.020 native.
Transfer is not part of V04.

**Runtime estimate** (anisotropic generation at 0.095 s per scenario):
- generation of 15,000 scenarios: about 24 minutes;
- 40 model selections: about 13 minutes;
- 40 evaluations on 35,000 sequences: about 10 minutes;
- total: about 45-75 minutes.

The C grid stays as declared: in every sensitivity configuration, the C=100 to
1000 inner-OOF gain was at most 0.00061 (below the 0.001 tolerance), with at most
192 iterations.

## 4. Interval method

**Primary: the studentized bootstrap (bootstrap-t).** It resamples whole
evaluation scenarios with B = 9,999 and a seed fixed at freeze. With mean m and
standard error se, lower = m - q(0.975) se and upper = m - q(0.025) se, where
q(p) are quantiles of (m* - m)/se* over the resamples. The Student t interval is
reported alongside as a sensitivity analysis. One-sided p-values for the Holm
family come from inverting the same studentized bootstrap distribution.

**Why.** Per-scenario contrasts are strongly right-skewed (P1 skewness 4.5). The
bootstrap-t's one-sided coverage error is O(1/n), versus O(1/sqrt n) for t (Hall
1988, as summarized by Owen, arXiv:2508.10083). Development validation used the
reference-trial distribution, with nominal rate 0.025 per side:

| Contrast | n | Replicates | t: false low / high | bootstrap-t: false low / high | Run |
|---|---:|---:|---|---|---|
| P1 | 1,000 | 4,000 | 0.0145 / 0.0428 | 0.0250 / 0.0295 | `interval_validation_20261010_v1` |
| P1 | 5,000 | 4,000 | 0.0205 / 0.0340 | 0.0260 / 0.0288 | `interval_validation_20261010_v2` |
| S6 | 1,000 | 4,000 | 0.0170 / 0.0438 | 0.0322 / 0.0248 | v1 |
| S1 | 1,000 | 4,000 | 0.0192 / 0.0315 | 0.0308 / 0.0325 | v1 |

Monte Carlo SE is 0.0025 per side at 4,000 replicates. A separate t-only check
with 40,000 replicates gave P1 coverage of 0.950 at n = 5,000 (0.020 / 0.030) and
0.945 at n = 1,000. The v1 n = 5,000 rows used only 1,500 replicates and are
noisier, so the v2 run supersedes them.

For right-skewed P1 and S6, the t interval's upper bound was anti-conservative.
That bound drives the "not material" decision. The bootstrap-t balanced both
sides. For S1, whose skew runs opposite to its effect, the bootstrap-t was
slightly above nominal on both sides at n = 1,000 (about 2.4 Monte Carlo SEs);
S1 is secondary and its t interval is reported too.

Both intervals were validated only against the development distribution. A
different shape in the scientific configuration remains a stated limitation,
and §8's boundary-null checks must be repeated on the runner's own output
before V04.

**Multi-bank form used for every confirmatory contrast (K = 10).**
`research.track_r_analysis.bank_combined_interval` combines two parts:
- the scenario component: the bootstrap-t above, applied to bank-averaged
  per-scenario contrasts;
- the bank component: t(K-1) times the SD of the K bank means divided by sqrt(K).

The two half-widths are added in quadrature separately for each side, so the
skew asymmetry is kept. One-sided p-values for Holm invert this interval by
bisection (`combined_one_sided_p`). The primary decision applies the margin rule
to the same interval.

**Validation:** `bank_interval_validation_20261010_v1`,
[bundle](../results/bank_intervals_2026-10-10/report.md). Designs were simulated
from the isotropic development components (empirical scenario effects, normal
bank effects with the moment SD, empirical residuals), 1,000 replicates each:

| Contrast | K, n | Bank-combined: coverage (low / high errors) | Scenario-only: coverage |
|---|---|---|---|
| P1 | 10, 5,000 | 0.962 (0.021 / 0.017) | 0.929 |
| P1 | 5, 5,000 | 0.966 (0.018 / 0.016) | 0.900 |
| S2 | 10, 5,000 | 0.963 (0.019 / 0.018) | 0.749 |
| S6 | 10, 5,000 | 0.956 (0.024 / 0.020) | 0.783 |

Across all nine designs the bank-combined coverage is 0.950-0.966, slightly
conservative. Inference conditional on the fitted banks under-covers, worst for
small method contrasts (as low as 0.660). The normal bank-effect shape is an
assumption that six development banks cannot test. The decision rules therefore
use the combined interval, and the conditional scenario-only interval is
reported only as a sensitivity analysis labelled "conditional on these fitted
models".

## 5. Decision rules and multiplicity

- **Primary P1** (margin 0.02 nats; two-sided 95% interval [L, U]):
  - L > 0.02: material reuse degradation is confirmed;
  - U < 0.02: degradation is not material;
  - otherwise: inconclusive.
  Also report whether L > 0. P1 is tested alone at the 5% level and is never
  replaced by a secondary contrast.
- **Confirmatory secondary family (Holm, familywise one-sided alpha 0.05,
  m = 4),** tested whatever P1's outcome:

  | ID | Null hypothesis | Rejection supports |
  |---|---|---|
  | S1 | Absolute singleton minus latest_metadata at overlap_90 <= -0.02 | History keeps less than 0.02 nats of advantage under heavy overlap |
  | S5 | Degradation at solution_reissue <= 0.02 | Material degradation under solution reissue |
  | S2 | grouped minus singleton degradation <= -0.01 | Grouping does not reduce degradation by more than 0.01 |
  | S3 | oracle_lineage_weight minus singleton degradation <= -0.01 | Privileged lineage weighting does not reduce it by more than 0.01 |

  **Margins:**
  - S1 reuses the 0.02 materiality scale. Independent development banks show
    S1 near zero (-0.009 to +0.005 in every configuration), so the original
    "history still wins" direction is replaced by this bound on the remaining
    advantage.
  - delta_m = 0.01 for S2 and S3 is half the P1 margin, about 15% of the observed
    degradation. Smaller reductions are not called meaningful.
  - Each one-sided p-value inverts the §4 bank-combined interval.

  **Approximate power** at K = 10 and n = 5,000 (isotropic components; Holm
  worst-case one-sided 0.01 for secondaries, 0.025 for P1):

  | ID | SE | Power at isotropic mean | Halfway to null | At smallest native non-bias mean |
  |---|---:|---:|---:|---:|
  | P1 | 0.0055 | 1.000 | 0.984 | 0.990 |
  | S1 | 0.0036 | 1.000 | 0.728 | 0.914 |
  | S5 | 0.0064 | 1.000 | 0.984 | 0.999 |
  | S2 | 0.0015 | 1.000 | 0.932 | 0.998 |
  | S3 | 0.0011 | 1.000 | 1.000 | 1.000 |

- **Moved to exploratory:** S6, whether history becomes worse than latest-only
  under solution reissue. Its effect is small and variable: 0.003-0.023 across
  isotropic banks and 0.004-0.014 in other configurations. Power would be 0.31
  halfway to its null and 0.07 at the smallest native mean, so it is reported
  with its interval but not tested.
- **Not confirmatory:** S6 and S4 (shared bias: P1 +0.020 with bias-matched
  training), new-information controls, other arms and conditions, miss and
  review endpoints, and calibration summaries. They are reported in full,
  without adjustment, and labelled as exploratory or descriptive.

## 6. Endpoints reported regardless of outcome

- Absolute and degradation losses for every arm and condition, Brier scores and
  calibration summaries.
- **Reuse-induced misses** (positives missed under overlap but reviewed without
  reuse) with an exact Clopper-Pearson interval, plus the paired new and
  recovered miss counts.
- Review counts, labelled as enriched stress-population quantities.
- Null, inconclusive and adverse results, given the same prominence as
  favorable ones.

## 7. Failures, missing values and deviations

- **Stopping:** any convergence warning, nonfinite value, failed invariance check
  (exact replay, matched latest message) or plan/output mismatch stops the run.
  Partial records are kept. A rerun gets a new run ID under the unchanged
  protocol, and the failure is reported.
- **No dropping:** no scenario, bank, arm or candidate is dropped. Evaluation
  failures count as failures, not missing data.
- **Amendments:** each one is recorded with its date, its reason and whether
  scientific outcomes were visible. Outcome-visible amendments cannot change the
  primary contrast, margin, decision rule, sample size or interval method.

## 8. Analysis-owner checks before V04

These follow Report 2's freeze checklist. Rerun the decision rule on simulated
boundary-null data (truth exactly at each margin) and zero-discordance miss
cases, and confirm that the error rates match §4. Have a second reviewer
reproduce the primary computation from saved predictions. Same-workflow
reconstruction does not count as independent A03 review.
