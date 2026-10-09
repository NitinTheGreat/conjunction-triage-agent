# V02 cadence and training-regime development results

Date: 9 October 2026. Source runs: `cadence_20261009_v1`, `regimes_20261009_v1`; synthesis: `regimes_summary_20261009_v1`. This is **exposed development evidence**, not a frozen or independent scientific test. V02 remains incomplete.

## Design and construction checks

The same 1,000 latent scenarios in each first-pilot bank were reused: development has 180 positives, software 194 and shared-bias stress 326. Their observation arrays and final labels were not regenerated. The new cadence has unequal short clusters and long gaps. A burst-reissue condition repeats six solutions at ten publication times without new observations. Latest messages remain matched across reuse conditions; age categories are recomputed at publication time.

Before fitting, 128 development scenarios were checked without using labels. All 128 produced nonuniform fixed-time summaries. Thinning retained 3-4 of six ordinary messages, or 5-6 of ten burst messages. Change selection reduced every ten-message burst to six solutions. These are construction distinctions, not claims that every fitted control must predict differently. Actual maximum differences from singleton predictions are saved in `control_prediction_differences.json`.

## Training and evaluation

Nine arms are evaluated under two regimes. `no_reuse_only` uses one history per scenario. `matched_mixture` uses six histories per scenario: no reuse, 50%/90% overlap, solution reissue, cumulative new information and burst reissue. Exact replay is an evaluation/property control, not extra training weight.

All variants stay in one of the same three inner scenario folds. Each latent scenario has total logistic objective weight one, distributed across variants and candidate partitions. Both regimes therefore have 1,000 objective units, although the mixture has 6,000 rows. Imputation and scaling remain training-only; they are unweighted transformations of the training messages/design rows. C is chosen from 0.01, 0.1, 1 and 10 using inner out-of-fold loss. Calibration and the nominal 95% recall threshold use the selected inner predictions; evaluation uses different exposed scenarios. The mixture threshold targets its uniform condition mixture, not 95% recall within every condition.

The latest-metadata arm closes the extra-field mismatch in the first simulation pilot. All nine arms pass exact-replay equality; both latest-message baselines give equal outputs when their latest input is unchanged. No model failed, and 252,000 event/arm/condition/regime prediction rows are retained. Variant rows are not independent scenarios.

**Tuning limitation:** 18/18 fits selected the upper C-grid boundary (10). Before final model selection, V02 should assess a common expanded grid using development-only data and an equal budget for every relevant arm. This pilot does not establish that any arm is optimally tuned.

## Absolute class log loss

Lower is better. Labels are final recorded synthetic risk classes; scores are class probabilities, not physical collision probabilities. Synthetic prevalence is deliberately enriched; these are unweighted stress-distribution results. Tables show selected conditions; `metrics.csv` contains all conditions, Brier/AP/AUC and explicit review/miss counts.

### matched_mixture / bias_stress
| arm | no_reuse | overlap_90 | burst_reissue | new_information |
| --- | --- | --- | --- | --- |
| change | 0.831086 | 0.731486 | 0.830794 | 1.851553 |
| fixed | 0.802538 | 0.731121 | 0.743250 | 1.811818 |
| grouped | 0.839349 | 0.720409 | 0.757069 | 1.913822 |
| ignore_updates | 0.520760 | 0.475492 | 0.520760 | 0.520760 |
| latest | 0.440483 | 0.440483 | 0.440483 | 2.097890 |
| latest_metadata | 0.518935 | 0.518935 | 0.518935 | 1.482932 |
| random | 0.772725 | 0.722330 | 0.746976 | 1.867515 |
| singleton | 0.820323 | 0.729039 | 0.810084 | 1.838590 |
| thin | 0.748610 | 0.680494 | 0.721480 | 1.782868 |
### matched_mixture / software
| arm | no_reuse | overlap_90 | burst_reissue | new_information |
| --- | --- | --- | --- | --- |
| change | 0.105691 | 0.174223 | 0.105669 | 0.063297 |
| fixed | 0.107636 | 0.175127 | 0.111364 | 0.063429 |
| grouped | 0.105258 | 0.175018 | 0.107293 | 0.065947 |
| ignore_updates | 0.156603 | 0.171011 | 0.156603 | 0.156603 |
| latest | 0.183812 | 0.183812 | 0.183812 | 0.155132 |
| latest_metadata | 0.184606 | 0.184606 | 0.184606 | 0.062765 |
| random | 0.110051 | 0.176238 | 0.111075 | 0.063696 |
| singleton | 0.107189 | 0.174735 | 0.106277 | 0.063393 |
| thin | 0.129927 | 0.176448 | 0.135521 | 0.063930 |
### no_reuse_only / bias_stress
| arm | no_reuse | overlap_90 | burst_reissue | new_information |
| --- | --- | --- | --- | --- |
| change | 1.452196 | 1.312574 | 2.397425 | 2.659712 |
| fixed | 1.453624 | 0.192095 | 0.628317 | 2.636400 |
| grouped | 1.478864 | 1.462713 | 0.812917 | 2.734506 |
| ignore_updates | 0.578494 | 0.530479 | 0.578494 | 0.578494 |
| latest | 0.560463 | 0.560463 | 0.560463 | 2.329992 |
| latest_metadata | 0.478078 | 0.478078 | 0.478078 | 1.549784 |
| random | 1.399544 | 0.941684 | 1.248563 | 2.700181 |
| singleton | 1.452196 | 1.312574 | 1.480372 | 2.659712 |
| thin | 1.175848 | 0.161462 | 1.031978 | 2.425768 |
### no_reuse_only / software
| arm | no_reuse | overlap_90 | burst_reissue | new_information |
| --- | --- | --- | --- | --- |
| change | 0.085627 | 0.241370 | 0.491396 | 0.211563 |
| fixed | 0.087365 | 1.346852 | 0.604202 | 0.202567 |
| grouped | 0.084898 | 0.260376 | 0.365631 | 0.239609 |
| ignore_updates | 0.156189 | 0.173508 | 0.156189 | 0.156189 |
| latest | 0.186236 | 0.186236 | 0.186236 | 0.196998 |
| latest_metadata | 0.182786 | 0.182786 | 0.182786 | 0.096437 |
| random | 0.088816 | 0.301604 | 0.098107 | 0.230152 |
| singleton | 0.085627 | 0.241370 | 0.091177 | 0.211563 |
| thin | 0.125184 | 1.124703 | 0.218947 | 0.155866 |

## Does matched training repair the new-information control?

bias_stress: matched training lowers new-information loss for 9/9 arms. software: matched training lowers new-information loss for 8/9 arms. Negative contrasts below favor matched training. These comparisons are paired by scenario and conditional on the two fitted models; they do not include training-seed variability or multiplicity correction.

| bank | arm | matched_minus_shifted | ci_low | ci_high |
| --- | --- | --- | --- | --- |
| bias_stress | change | -0.808159 | -0.948023 | -0.664991 |
| software | change | -0.148266 | -0.207590 | -0.090299 |
| bias_stress | fixed | -0.824582 | -0.965966 | -0.682639 |
| software | fixed | -0.139138 | -0.195573 | -0.083703 |
| bias_stress | grouped | -0.820684 | -0.963234 | -0.671793 |
| software | grouped | -0.173662 | -0.239143 | -0.109381 |
| bias_stress | ignore_updates | -0.057734 | -0.068332 | -0.047469 |
| software | ignore_updates | 0.000414 | -0.001647 | 0.002287 |
| bias_stress | latest | -0.232102 | -0.268658 | -0.195767 |
| software | latest | -0.041866 | -0.053195 | -0.030736 |
| bias_stress | latest_metadata | -0.066852 | -0.086556 | -0.046019 |
| software | latest_metadata | -0.033672 | -0.046352 | -0.020818 |
| bias_stress | random | -0.832665 | -0.972885 | -0.685186 |
| software | random | -0.166456 | -0.228671 | -0.106342 |
| bias_stress | singleton | -0.821122 | -0.963645 | -0.675610 |
| software | singleton | -0.148170 | -0.207317 | -0.090350 |
| bias_stress | thin | -0.642900 | -0.746512 | -0.533627 |
| software | thin | -0.091936 | -0.131228 | -0.053716 |

A decrease in loss under matched training diagnoses sensitivity to the training regime. It does not prove that grouping is superior, that all additional observations improve every learned forecast, or that the simulator captures operational dynamics. Compare absolute loss against latest-metadata and simple controls before attributing a benefit to dependence treatment. The oracle state-error improvement documented in the original synthesis remains a separate physical-information diagnostic.

## Interpretation and remaining work

The repair removes the pilot's construction-level control collapse and explicitly tests the prior training-distribution mismatch. All positive, negative and null comparisons remain in the exported tables. The original pilot is preserved; this revision was informed by it and must not be called confirmation.

Next V02 work: covariance-proxy and sequence-family adaptations with declared budgets, separate state-fusion/unique-observation-oracle diagnostics, component/provenance ablations, training-seed sensitivity, and precision planning. V03 must then select and freeze one justified primary comparison before accessing the reserved scientific scenarios. Seed 20261012 and the reserved scientific bank remain unopened.

## Reconstruction

`research.summarize_regimes` checks completed source manifests and hashes, prediction coverage/labels, scenario folds and weights, all saved class metrics and all 18 training thresholds. It does not retrain or open new outcomes. `audit.json` records the checks. This is same-assistant artifact reconstruction, not the independent scientific review required by A03.

The compact export has original artifact hashes and source run IDs. Raw data, PDFs, predictions, models, source archives and process logs remain local/ignored. Existing binaries and predictions must be transferred separately for exact reproduction on another machine.
