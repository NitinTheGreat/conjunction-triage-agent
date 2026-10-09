# V02 precision planning: candidate scientific contrasts

Date: 10 October 2026. Run `precision_planning_20261010_v2`. **Development planning on exposed banks.
No model was fitted, no scenario was generated and the scientific reservation
(seed 20261012, IDs scientific:00000..04999) was not opened.** The chosen primary
contrast and its rationale are recorded separately in
`docs/research/execution/primary_contrast.md`.

## Inputs and reconciliation

All four class-forecast source runs pass manifest, input and archived-source
checks. The planning table recomputes 2,560 matched-training paired contrasts
(training trial x bank x condition x arm pair x estimand) from audited per-scenario
predictions (clipped log loss at 1e-6; review at the nominal 95% training-recall
threshold). Every overlapping row of the committed paired-contrast exports
reconciles:

| bundle | estimand | rows | max_mean_difference | max_sd_difference | max_miss_difference |
| --- | --- | --- | --- | --- | --- |
| covariance_2026-10-09 | absolute | 160 | 0.000000 | 0.000000 | nan |
| covariance_2026-10-09 | degradation | 160 | 0.000000 | 0.000000 | nan |
| sequence_2026-10-10 | absolute | 160 | 0.000000 | 0.000000 | 0.000000 |
| sequence_2026-10-10 | degradation | 160 | 0.000000 | 0.000000 | nan |
| components_2026-10-10 | absolute | 320 | 0.000000 | 0.000000 | 0.000000 |
| components_2026-10-10 | degradation | 320 | 0.000000 | 0.000000 | nan |

Each row records its exact scenario set by first/last ID and a SHA-256 of the
sorted IDs (2 distinct scenario sets for 2 banks).
Each bank has 1,000 evaluation scenarios, the independent unit. The three
800-scenario training subsets overlap the full-reference cohort; the four trials
describe training sensitivity, not independent replication.

## What the development banks show

Singleton history summary minus latest-message metadata, software bank, matched
training (range over the four training trials). Negative absolute values favor the
history model. Degradation is the change relative to no reuse.

| estimand | condition | trial_min | trial_max |
| --- | --- | --- | --- |
| absolute | burst_reissue | -0.083744 | -0.080573 |
| absolute | new_information | 0.001332 | 0.009290 |
| absolute | overlap_50 | -0.066794 | -0.065316 |
| absolute | overlap_90 | -0.011616 | -0.009278 |
| absolute | solution_reissue | 0.016337 | 0.023028 |
| degradation | burst_reissue | 0.000319 | 0.001218 |
| degradation | new_information | 0.082401 | 0.093484 |
| degradation | overlap_50 | 0.015352 | 0.018877 |
| degradation | overlap_90 | 0.069578 | 0.074915 |
| degradation | solution_reissue | 0.097531 | 0.104096 |

Latest-message arms are exactly invariant to every reuse condition because the
latest window is matched by construction, so a degradation contrast against
them equals the history model's own reuse-induced loss change.

## Candidate contrasts and normal-approximation sample sizes

`planning_sd` is the largest paired SD over the four trials. `n_half_width_h`
gives scenarios for a two-sided 95% interval of half-width h. `n_power90_effectS_marginM`
gives scenarios for 90% probability that the lower bound exceeds margin M when
the true contrast is S times the development reference effect (in its observed
direction); `inf` means that effect does not exceed the margin.

| id | contrast | reference_mean | trial_mean_min | trial_mean_max | planning_sd | skewness_reference | positives_reference |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P1 | singleton vs latest_metadata, degradation, overlap_90, software | 0.069578 | 0.069578 | 0.074915 | 0.363051 | 4.476490 | 194 |
| S1 | singleton vs latest_metadata, absolute, overlap_90, software | -0.011616 | -0.011616 | -0.009278 | 0.267362 | 3.415811 | 194 |
| S2 | grouped vs singleton, degradation, overlap_90, software | 0.003306 | -0.001545 | 0.003306 | 0.062139 | 1.113025 | 194 |
| S3 | oracle_lineage_weight vs singleton, degradation, overlap_90, software | 0.004574 | 0.002167 | 0.007285 | 0.062003 | 2.656490 | 194 |
| S4 | singleton vs latest_metadata, degradation, overlap_90, bias_stress | -0.108096 | -0.192713 | -0.047212 | 1.419178 | -3.257457 | 326 |
| S5 | singleton vs latest_metadata, degradation, solution_reissue, software | 0.097531 | 0.097531 | 0.104096 | 0.455161 | 4.485254 | 194 |
| S6 | singleton vs latest_metadata, absolute, solution_reissue, software | 0.016337 | 0.016337 | 0.023028 | 0.189943 | 4.924114 | 194 |

| id | n_half_width_0.01 | n_half_width_0.02 | n_power90_effect1_margin0 | n_power90_effect1_margin0.02 | n_power90_effect0.5_margin0 | n_power90_effect0.5_margin0.01 | n_power90_effect0.5_margin0.02 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P1 | 5064 | 1266 | 287 | 564.000000 | 1145 | 2254.000000 | 6333.000000 |
| S1 | 2746 | 687 | 5567 | inf | 22268 | inf | inf |
| S2 | 149 | 38 | 3714 | inf | 14854 | inf | inf |
| S3 | 148 | 37 | 1931 | inf | 7724 | inf | inf |
| S4 | 77370 | 19343 | 1812 | 2727.000000 | 7245 | 10908.000000 | 18256.000000 |
| S5 | 7959 | 1990 | 229 | 363.000000 | 916 | 1449.000000 | 2631.000000 |
| S6 | 1386 | 347 | 1421 | inf | 5682 | inf | inf |

## Resampling check of the t-interval for P1

4000 resamples of n scenarios from the reference trial's per-scenario P1
differences, oriented in the development effect direction. Columns give the
probability that the lower 95% bound exceeds the margin (0 or 0.02) when the true
contrast is the development effect, half of it, or exactly the margin
(`boundary_null`, a false confirmation rate with nominal value 0.025).

| n | boundary_null_m0.02 | development_effect_m0 | development_effect_m0.02 | half_effect_m0 | half_effect_m0.02 | coverage | half_width_median | half_width_p95 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 500 | 0.008750 | 0.999750 | 0.956750 | 0.647500 | 0.111500 | 0.944250 | 0.029539 | 0.035633 |
| 1000 | 0.010000 | 1.000000 | 1.000000 | 0.939000 | 0.231750 | 0.951250 | 0.020903 | 0.023924 |
| 2000 | 0.013500 | 1.000000 | 1.000000 | 0.999250 | 0.485750 | 0.952750 | 0.014827 | 0.016276 |
| 3000 | 0.019500 | 1.000000 | 1.000000 | 1.000000 | 0.676250 | 0.946250 | 0.012139 | 0.013133 |
| 5000 | 0.016250 | 1.000000 | 1.000000 | 1.000000 | 0.884000 | 0.955250 | 0.009393 | 0.009973 |

Across all candidates and sample sizes at their boundary nulls:

| id | coverage_min | coverage_max | false_confirm_max | false_dismiss_max |
| --- | --- | --- | --- | --- |
| P1 | 0.944250 | 0.955250 | 0.019500 | 0.047000 |
| S1 | 0.944500 | 0.948500 | 0.037500 | 0.025500 |
| S2 | 0.947750 | 0.953000 | 0.025500 | 0.031500 |
| S3 | 0.946000 | 0.955500 | 0.023250 | 0.035750 |
| S4 | 0.938000 | 0.951750 | 0.021000 | 0.045750 |
| S5 | 0.937500 | 0.954250 | 0.021250 | 0.047250 |
| S6 | 0.936750 | 0.950750 | 0.020750 | 0.051000 |

`false_dismiss` is the probability that the upper bound falls below a margin equal
to the truth (nominal 0.025). Right-skewed differences make the upper bound
anti-conservative at small n and the lower bound conservative. The final interval
method belongs to the §3 analysis specification.

## Miss endpoints

Miss contrasts use positive scenarios only. For degradation candidates, the
endpoint is reuse-induced new misses of the history arm (missed under the
condition but reviewed without reuse); the latest-message comparator cannot change.
The Clopper-Pearson column is the one-sided 95% upper bound at the development
rate; the last columns give the probability that it falls below each margin.

| id | endpoint | development_new_misses | development_recovered_misses | planned_scenarios | expected_positives | expected_upper_bound_at_development_rate | p_upper_bound_below_0.01 | p_upper_bound_below_0.05 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P1 | reuse-induced new misses of arm (condition versus no reuse) | 8 | 0 | 1000 | 194 | 0.073174 | 0.000000 | 0.086000 |
| P1 | reuse-induced new misses of arm (condition versus no reuse) | 8 | 0 | 5000 | 970 | 0.053344 | 0.000000 | 0.340000 |
| S1 | new misses versus comparator at condition | 2 | 9 | 1000 | 194 | 0.032095 | 0.000000 | 0.947250 |
| S1 | new misses versus comparator at condition | 2 | 9 | 5000 | 970 | 0.017424 | 0.035750 | 1.000000 |
| S6 | new misses versus comparator at condition | 2 | 0 | 1000 | 194 | 0.032095 | 0.000000 | 0.942500 |
| S6 | new misses versus comparator at condition | 2 | 0 | 5000 | 970 | 0.017424 | 0.022500 | 1.000000 |

The bound is the exact one-sided Clopper-Pearson limit, `Beta^-1(0.95; k+1, n-k)`
(Clopper and Pearson, Biometrika 26:404-413, 1934), as specified in Report 2
§7.2. The tests check its zero-failure identity, `1 - 0.05^(1/n)`.

These are not noninferiority endpoints. Reuse produces new misses in development,
so the informative quantity is the estimated reuse-induced miss rate and its
interval, reported secondarily. The nominal training-recall threshold is not a
miss guarantee.

## Training sensitivity versus evaluation precision

| id | trials | mean_of_trials | between_trial_sd | within_trial_se_median | evaluation_se_n5000 |
| --- | --- | --- | --- | --- | --- |
| P1 | 4 | 0.071960 | 0.002211 | 0.011172 | 0.004996 |
| S1 | 4 | -0.010312 | 0.001074 | 0.008164 | 0.003651 |
| S2 | 4 | 0.000968 | 0.002360 | 0.001790 | 0.000801 |
| S3 | 4 | 0.005053 | 0.002223 | 0.001364 | 0.000610 |
| S4 | 4 | -0.110411 | 0.060704 | 0.035737 | 0.015982 |
| S5 | 4 | 0.100980 | 0.002687 | 0.013639 | 0.006099 |
| S6 | 4 | 0.018708 | 0.003026 | 0.005103 | 0.002282 |

The between-trial SD comes from overlapping subsets of one development bank, so it
understates variation across independent training banks. It is nevertheless
comparable to the evaluation SE expected at 5,000 scenarios. §3 must decide
whether inference is conditional on one fitted model or averages over independent
training banks.

## Limits

- Development banks are exposed and isotropic; the candidate scientific
  configuration is anisotropic. Effects and SDs may change (§4).
- Resampling treats the 1,000 development scenarios as the population; it checks
  approximation quality, not scientific coverage.
- Enriched synthetic prevalence (software 19.4%, bias 32.6%) is not operational
  workload; review and miss rates are stress-population quantities.
- Same-workflow analysis, not independent A03 review.
