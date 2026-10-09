# V02 state-fusion and visible-observation oracle diagnostics

Date: 9 October 2026. Source `fusion_20261009_v1`, reconstruction `fusion_summary_20261009_v1`. **Exposed development evidence; no reserved scientific outcomes generated.** This is a static Gaussian state-estimation diagnostic, separate from class forecasting and orbital operations.

## Design and inputs

Six arms compare latest, a product of message Gaussians, the product with the common prior counted once, basic precision-weighted covariance intersection (CI), the union-of-visible-observations oracle omitting bias, and the same oracle using the known bias covariance. Ordinary controls receive message means/covariances, not observation IDs or latent truth. Only the labeled oracles receive lineage and the bias-aware oracle receives B. The known prior is N(0,2.25 I); observation noise is 0.09 I. Bias stress adds common B=0.01 I but input message covariances omit it.

Preflight reconstructs 138,000 canonical messages from immutable observation windows, checking saved risk, miss distance, sigmas, ordering and availability before fusion. IDs 60-79 occur after the visible cutoff and are forbidden in every state estimate. The lineage union changes by condition (60 no reuse, 35 partial overlap, 15 heavy overlap, 10 solution reissue, 60 cumulative new information/burst reissue). The latest message is matched across the original reuse variants. There are 1,000 latent scenarios per bank; 126,000 arm/condition records do not increase that sample count. Banks are reported separately.

The ordinary product sums precisions and information vectors; the prior-once control subtracts m-1 copies of the common prior precision. The latter recovers the visible oracle under disjoint observations but still double-counts overlapping likelihood information. CI averages precisions on the simplex, minimizing log determinant of its covariance. Exact identical-covariance ties use uniform weights; isotropic inputs select the smallest variance, sharing exact minimum ties. General inputs use the prespecified checked SLSQP solver. This is the basic CI family, not OCI's general optimization framework or a reproduction of its experiments. The implementation contract records formulas, tests and source context.

## Structural collapses and scope

All campaign message covariances are isotropic. Equal-covariance conditions therefore use the declared uniform CI tie rule; cumulative new information selects the latest estimate, which already uses the complete visible union. These are checked identities, not learned overlap detection or evidence of an optimization advantage. The general anisotropic solver is exercised by analytic unit tests only. In solution reissue, CI retains the latest covariance, while a product repeatedly counts the same solution. The separate prior correction isolates shared-prior reuse from observation reuse.

Exact retransmissions are canonicalized with the existing source-time convention for every control. Reissued solutions at distinct publication times remain distinct inputs. CI tie weights can therefore change the mean under unequal repeat counts, even while its covariance stays the same. No unknown-correlation guarantee is transferred to inputs that omit shared-bias covariance.

## State metrics and population

Squared Euclidean state error and covariance trace have units m². The error quadratic form is e'P^-1 e (dimensionless). A nominal Gaussian-reference 95% ellipse uses threshold chi2_2(0.95)=5.991464547108; area is pi*threshold*sqrt(det P), in m². `ellipse_included` counts latent states inside this region. It is an empirical stress diagnostic, not a claim of 95% coverage for the enriched sampling population. All displayed summaries are **unweighted** under the saved mixture; no wide-prior population or operational calibration claim is made.

No fused disk probability or class q is scored here. Latent state error, final recorded-risk forecasting, physical collision occurrence and maneuver utility remain different endpoints. An oracle state improvement does not by itself establish better class forecasting.

### software / no_reuse

| arm | mean_squared_error | mean_quadratic_error | mean_ellipse_area95 | ellipse_included | n_scenarios |
| --- | --- | --- | --- | --- | --- |
| covariance_intersection | 0.003217 | 0.358838 | 0.168730 | 1000 | 1000 |
| gaussian_product | 0.003217 | 2.153026 | 0.028122 | 932 | 1000 |
| latest | 0.018341 | 2.046043 | 0.168730 | 947 | 1000 |
| oracle_bias_aware | 0.003182 | 2.122586 | 0.028215 | 937 | 1000 |
| oracle_unique | 0.003182 | 2.122586 | 0.028215 | 937 | 1000 |
| prior_once_product | 0.003182 | 2.122586 | 0.028215 | 937 | 1000 |

### software / overlap_90

| arm | mean_squared_error | mean_quadratic_error | mean_ellipse_area95 | ellipse_included | n_scenarios |
| --- | --- | --- | --- | --- | --- |
| covariance_intersection | 0.014655 | 1.634811 | 0.168730 | 969 | 1000 |
| gaussian_product | 0.014655 | 9.808867 | 0.028122 | 458 | 1000 |
| latest | 0.018341 | 2.046043 | 0.168730 | 947 | 1000 |
| oracle_bias_aware | 0.012420 | 2.075583 | 0.112636 | 935 | 1000 |
| oracle_unique | 0.012420 | 2.075583 | 0.112636 | 935 | 1000 |
| prior_once_product | 0.014665 | 9.782998 | 0.028215 | 454 | 1000 |

### software / solution_reissue

| arm | mean_squared_error | mean_quadratic_error | mean_ellipse_area95 | ellipse_included | n_scenarios |
| --- | --- | --- | --- | --- | --- |
| covariance_intersection | 0.018341 | 2.046043 | 0.168730 | 947 | 1000 |
| gaussian_product | 0.018341 | 12.276261 | 0.028122 | 386 | 1000 |
| latest | 0.018341 | 2.046043 | 0.168730 | 947 | 1000 |
| oracle_bias_aware | 0.018341 | 2.046043 | 0.168730 | 947 | 1000 |
| oracle_unique | 0.018341 | 2.046043 | 0.168730 | 947 | 1000 |
| prior_once_product | 0.018381 | 12.262237 | 0.028215 | 390 | 1000 |

### software / new_information

| arm | mean_squared_error | mean_quadratic_error | mean_ellipse_area95 | ellipse_included | n_scenarios |
| --- | --- | --- | --- | --- | --- |
| covariance_intersection | 0.003182 | 2.122586 | 0.028215 | 937 | 1000 |
| gaussian_product | 0.003918 | 9.151791 | 0.008058 | 457 | 1000 |
| latest | 0.003182 | 2.122586 | 0.028215 | 937 | 1000 |
| oracle_bias_aware | 0.003182 | 2.122586 | 0.028215 | 937 | 1000 |
| oracle_unique | 0.003182 | 2.122586 | 0.028215 | 937 | 1000 |
| prior_once_product | 0.003918 | 9.142901 | 0.008065 | 459 | 1000 |

### software / burst_reissue

| arm | mean_squared_error | mean_quadratic_error | mean_ellipse_area95 | ellipse_included | n_scenarios |
| --- | --- | --- | --- | --- | --- |
| covariance_intersection | 0.003857 | 0.430293 | 0.168730 | 1000 | 1000 |
| gaussian_product | 0.003857 | 4.302932 | 0.016873 | 753 | 1000 |
| latest | 0.018341 | 2.046043 | 0.168730 | 947 | 1000 |
| oracle_bias_aware | 0.003182 | 2.122586 | 0.028215 | 937 | 1000 |
| oracle_unique | 0.003182 | 2.122586 | 0.028215 | 937 | 1000 |
| prior_once_product | 0.003829 | 4.256129 | 0.016934 | 753 | 1000 |

### bias_stress / no_reuse

| arm | mean_squared_error | mean_quadratic_error | mean_ellipse_area95 | ellipse_included | n_scenarios |
| --- | --- | --- | --- | --- | --- |
| covariance_intersection | 0.023448 | 2.615727 | 0.168730 | 904 | 1000 |
| gaussian_product | 0.023448 | 15.694360 | 0.028122 | 292 | 1000 |
| latest | 0.038707 | 4.318030 | 0.168730 | 765 | 1000 |
| oracle_bias_aware | 0.023424 | 2.047299 | 0.215361 | 955 | 1000 |
| oracle_unique | 0.023562 | 15.718697 | 0.028215 | 290 | 1000 |
| prior_once_product | 0.023562 | 15.718697 | 0.028215 | 290 | 1000 |

### bias_stress / overlap_90

| arm | mean_squared_error | mean_quadratic_error | mean_ellipse_area95 | ellipse_included | n_scenarios |
| --- | --- | --- | --- | --- | --- |
| covariance_intersection | 0.035717 | 3.984440 | 0.168730 | 783 | 1000 |
| gaussian_product | 0.035717 | 23.906640 | 0.028122 | 220 | 1000 |
| latest | 0.038707 | 4.318030 | 0.168730 | 765 | 1000 |
| oracle_bias_aware | 0.032837 | 2.066893 | 0.299037 | 935 | 1000 |
| oracle_unique | 0.033040 | 5.521368 | 0.112636 | 675 | 1000 |
| prior_once_product | 0.035945 | 23.979414 | 0.028215 | 218 | 1000 |

### bias_stress / solution_reissue

| arm | mean_squared_error | mean_quadratic_error | mean_ellipse_area95 | ellipse_included | n_scenarios |
| --- | --- | --- | --- | --- | --- |
| covariance_intersection | 0.038707 | 4.318030 | 0.168730 | 765 | 1000 |
| gaussian_product | 0.038707 | 25.908177 | 0.028122 | 200 | 1000 |
| latest | 0.038707 | 4.318030 | 0.168730 | 765 | 1000 |
| oracle_bias_aware | 0.038474 | 2.042023 | 0.354637 | 935 | 1000 |
| oracle_unique | 0.038707 | 4.318030 | 0.168730 | 765 | 1000 |
| prior_once_product | 0.038961 | 25.991357 | 0.028215 | 191 | 1000 |

### bias_stress / new_information

| arm | mean_squared_error | mean_quadratic_error | mean_ellipse_area95 | ellipse_included | n_scenarios |
| --- | --- | --- | --- | --- | --- |
| covariance_intersection | 0.023562 | 15.718697 | 0.028215 | 290 | 1000 |
| gaussian_product | 0.024308 | 56.783976 | 0.008058 | 87 | 1000 |
| latest | 0.023562 | 15.718697 | 0.028215 | 290 | 1000 |
| oracle_bias_aware | 0.023424 | 2.047299 | 0.215361 | 955 | 1000 |
| oracle_unique | 0.023562 | 15.718697 | 0.028215 | 290 | 1000 |
| prior_once_product | 0.024352 | 56.832072 | 0.008065 | 85 | 1000 |

### bias_stress / burst_reissue

| arm | mean_squared_error | mean_quadratic_error | mean_ellipse_area95 | ellipse_included | n_scenarios |
| --- | --- | --- | --- | --- | --- |
| covariance_intersection | 0.024290 | 2.709635 | 0.168730 | 891 | 1000 |
| gaussian_product | 0.024290 | 27.096346 | 0.016873 | 194 | 1000 |
| latest | 0.038707 | 4.318030 | 0.168730 | 765 | 1000 |
| oracle_bias_aware | 0.023424 | 2.047299 | 0.215361 | 955 | 1000 |
| oracle_unique | 0.023562 | 15.718697 | 0.028215 | 290 | 1000 |
| prior_once_product | 0.024426 | 27.151089 | 0.016934 | 194 | 1000 |

## Paired descriptive uncertainty

Differences are arm minus comparator; lower squared error favors the arm. All arms/conditions share the same 2,000 scenario-multinomial bootstrap resamples within each bank, with base seed 20261040 and the recorded bank offset. Intervals are marginal percentile summaries of these exposed scenarios, without multiplicity adjustment or a confirmatory significance claim. There are no training repetitions in this deterministic diagnostic. Repeated messages, conditions and methods are not new independent units.

| bank | condition | arm | difference | ci95_low | ci95_high | n_independent_scenarios_assumed |
| --- | --- | --- | --- | --- | --- | --- |
| software | new_information | gaussian_product | 0.000736 | 0.000598 | 0.000880 | 1000 |
| software | overlap_90 | gaussian_product | -0.003686 | -0.004487 | -0.002900 | 1000 |
| software | solution_reissue | gaussian_product | -0.000000 | -0.000000 | 0.000000 | 1000 |
| software | new_information | prior_once_product | 0.000736 | 0.000601 | 0.000879 | 1000 |
| software | overlap_90 | prior_once_product | -0.003676 | -0.004487 | -0.002878 | 1000 |
| software | solution_reissue | prior_once_product | 0.000040 | -0.000026 | 0.000106 | 1000 |
| software | new_information | covariance_intersection | -0.000000 | -0.000000 | 0.000000 | 1000 |
| software | overlap_90 | covariance_intersection | -0.003686 | -0.004487 | -0.002900 | 1000 |
| software | solution_reissue | covariance_intersection | 0.000000 | -0.000000 | 0.000000 | 1000 |
| software | new_information | oracle_unique | 0.000000 | 0.000000 | 0.000000 | 1000 |
| software | overlap_90 | oracle_unique | -0.005921 | -0.006740 | -0.005092 | 1000 |
| software | solution_reissue | oracle_unique | 0.000000 | 0.000000 | 0.000000 | 1000 |
| software | new_information | oracle_bias_aware | 0.000000 | 0.000000 | 0.000000 | 1000 |
| software | overlap_90 | oracle_bias_aware | -0.005921 | -0.006740 | -0.005092 | 1000 |
| software | solution_reissue | oracle_bias_aware | 0.000000 | 0.000000 | 0.000000 | 1000 |
| bias_stress | new_information | gaussian_product | 0.000746 | 0.000371 | 0.001122 | 1000 |
| bias_stress | overlap_90 | gaussian_product | -0.002990 | -0.004201 | -0.001766 | 1000 |
| bias_stress | solution_reissue | gaussian_product | -0.000000 | -0.000000 | 0.000000 | 1000 |
| bias_stress | new_information | prior_once_product | 0.000790 | 0.000407 | 0.001162 | 1000 |
| bias_stress | overlap_90 | prior_once_product | -0.002762 | -0.003963 | -0.001558 | 1000 |
| bias_stress | solution_reissue | prior_once_product | 0.000254 | 0.000154 | 0.000364 | 1000 |
| bias_stress | new_information | covariance_intersection | 0.000000 | -0.000000 | 0.000000 | 1000 |
| bias_stress | overlap_90 | covariance_intersection | -0.002990 | -0.004201 | -0.001766 | 1000 |
| bias_stress | solution_reissue | covariance_intersection | 0.000000 | 0.000000 | 0.000000 | 1000 |
| bias_stress | new_information | oracle_unique | 0.000000 | 0.000000 | 0.000000 | 1000 |
| bias_stress | overlap_90 | oracle_unique | -0.005667 | -0.006958 | -0.004388 | 1000 |
| bias_stress | solution_reissue | oracle_unique | 0.000000 | 0.000000 | 0.000000 | 1000 |
| bias_stress | new_information | oracle_bias_aware | -0.000138 | -0.000247 | -0.000032 | 1000 |
| bias_stress | overlap_90 | oracle_bias_aware | -0.005871 | -0.007176 | -0.004589 | 1000 |
| bias_stress | solution_reissue | oracle_bias_aware | -0.000234 | -0.000381 | -0.000101 | 1000 |

The complete CSV retains all ten prespecified arm/comparator pairs, all seven conditions, all three banks and five endpoints, including paired squared-error degradation relative to no reuse. Ellipse inclusion differences are probability-point fractions; a higher inclusion fraction can simply reflect a much larger uncertainty region. Assess error, area and inclusion together. These intervals are descriptive, not a safety certificate or a primary scientific test.

## Verification and next work

All saved state means/covariances, errors, metrics and CI weights were reconstructed exactly from the original visible observations; source/input/output/archive hashes and case coverage passed. Disjoint-prior-once recovery, replay invariance, bias-free oracle equality and cumulative-information CI/latest/oracle collapses pass. Fixed analytic tests separately check anisotropic CI and full-joint shared-bias conditioning. This is artifact reconstruction within the same workflow, not A03 independent scientific review.

The result bundle contains aggregate metrics, paired contrasts, CI branches/ties, reconstruction counts and an audit with byte hashes. Bulk state/message records and exact source archives remain local/ignored. The study is a static toy model with enriched sampling and exposed outcomes. It does not complete the sequence adaptation, observable-provenance component ablations, independent training-bank uncertainty or precision planning. V02 and scientific freeze V03 remain open. Preserve negative results and structural collapses when choosing the eventual paper claim.
