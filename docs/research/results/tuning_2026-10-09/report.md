# V02 expanded tuning and training-subset sensitivity

Date: 9 October 2026. Runs: `tuning_20261009_v1`, prior reference `regimes_20261009_v1`, reconstruction `tuning_summary_20261009_v1`. **Exploratory development evidence; V02 remains open.** No reserved scientific scenarios were generated or inspected.

## What was varied

Every predictor uses C in [0.01, 0.1, 1.0, 10.0, 100.0, 1000.0] and a common 10,000-iteration cap. There are nine predictors, two training regimes, and four trials: the full 1,000-scenario reference at seed 20261022, then three stratified 800-scenario subsets at seeds [20261031, 20261032, 20261033]. The smaller subsets each have 144 positives; the original development bank has 180. They are overlapping selections from the same bank, not new independent cohorts. Changing a deterministic solver seed alone would not establish training variability.

The same scenarios, inner folds and candidate grid are used across predictors and regimes within each trial. All history variants of a scenario stay together. Each selected scenario contributes one total objective unit. Calibration and the nominal recall threshold use selected inner-OOF predictions; their reuse is recorded and no risk certificate is claimed. All 72 fits converged, with a maximum observed 262 iterations. Source checkpoints retain models, selected-C OOF predictions and aggregate candidate losses. 1,008,000 evaluation rows refer to the same 1,000 scenarios per exposed evaluation bank, repeated across configurations.

## Tuning boundary

25/72 selected fits still choose the upper C boundary. Interior choices show where the old cap of 10 constrained selection. Boundary choices remain a limitation; extending a finite grid does not prove optimal tuning. The larger optimizer cap is shared by all arms. Do not describe the change as a new model or a scientific confirmation.

| regime | arm | fits | min_C | max_C | upper_boundary_fits |
| --- | --- | --- | --- | --- | --- |
| matched_mixture | change | 4 | 100.000000 | 100.000000 | 0 |
| matched_mixture | fixed | 4 | 100.000000 | 1000.000000 | 1 |
| matched_mixture | grouped | 4 | 100.000000 | 100.000000 | 0 |
| matched_mixture | ignore_updates | 4 | 10.000000 | 100.000000 | 0 |
| matched_mixture | latest | 4 | 100.000000 | 1000.000000 | 3 |
| matched_mixture | latest_metadata | 4 | 100.000000 | 1000.000000 | 2 |
| matched_mixture | random | 4 | 100.000000 | 100.000000 | 0 |
| matched_mixture | singleton | 4 | 100.000000 | 100.000000 | 0 |
| matched_mixture | thin | 4 | 100.000000 | 100.000000 | 0 |
| no_reuse_only | change | 4 | 1000.000000 | 1000.000000 | 4 |
| no_reuse_only | fixed | 4 | 100.000000 | 1000.000000 | 2 |
| no_reuse_only | grouped | 4 | 100.000000 | 1000.000000 | 3 |
| no_reuse_only | ignore_updates | 4 | 10.000000 | 100.000000 | 0 |
| no_reuse_only | latest | 4 | 100.000000 | 1000.000000 | 3 |
| no_reuse_only | latest_metadata | 4 | 100.000000 | 1000.000000 | 1 |
| no_reuse_only | random | 4 | 100.000000 | 100.000000 | 0 |
| no_reuse_only | singleton | 4 | 1000.000000 | 1000.000000 | 4 |
| no_reuse_only | thin | 4 | 100.000000 | 1000.000000 | 2 |

`reference_grid_change.csv` compares the new full-data trial with the preceding campaign on identical evaluation cells. It separates the common-grid/optimizer-cap change from the smaller training subsets. Each cell includes previous/new log loss, Brier score, review count and missed-positive count. Do not attribute the difference between 1,000-scenario and 800-scenario training solely to a random seed.

## Descriptive sensitivity ranges

The mean/min/max columns summarize the **three equal-size training subsets only**. Full-data loss is displayed separately. Ranges are not confidence intervals; three overlapping subsets are insufficient for a precise training-uncertainty estimate. Miss counts are out of 194 software positives or 326 bias-stress positives, not out of repeated prediction rows. The synthetic prevalence is enriched and unweighted; it is not an operational workload estimate.

### Matched training / software / overlap_90
| arm | full_data_loss | log_loss_mean | log_loss_min | log_loss_max | fn_min | fn_max |
| --- | --- | --- | --- | --- | --- | --- |
| change | 0.171251 | 0.174220 | 0.173873 | 0.174693 | 9.000000 | 12.000000 |
| fixed | 0.174403 | 0.174017 | 0.173223 | 0.175256 | 9.000000 | 10.000000 |
| grouped | 0.173125 | 0.174595 | 0.173500 | 0.175339 | 9.000000 | 11.000000 |
| ignore_updates | 0.170019 | 0.171339 | 0.170405 | 0.171882 | 3.000000 | 6.000000 |
| latest | 0.182685 | 0.183412 | 0.182325 | 0.184181 | 7.000000 | 8.000000 |
| latest_metadata | 0.182578 | 0.183600 | 0.182497 | 0.184223 | 12.000000 | 15.000000 |
| random | 0.173164 | 0.174746 | 0.174018 | 0.176113 | 6.000000 | 11.000000 |
| singleton | 0.170962 | 0.173723 | 0.173220 | 0.174618 | 9.000000 | 11.000000 |
| thin | 0.174332 | 0.174802 | 0.173697 | 0.175822 | 9.000000 | 9.000000 |
### Matched training / software / new_information
| arm | full_data_loss | log_loss_mean | log_loss_min | log_loss_max | fn_min | fn_max |
| --- | --- | --- | --- | --- | --- | --- |
| change | 0.066654 | 0.066824 | 0.063126 | 0.073535 | 7.000000 | 11.000000 |
| fixed | 0.064882 | 0.065432 | 0.064096 | 0.067967 | 5.000000 | 9.000000 |
| grouped | 0.066160 | 0.068138 | 0.064222 | 0.075943 | 8.000000 | 12.000000 |
| ignore_updates | 0.157324 | 0.157164 | 0.156360 | 0.157615 | 4.000000 | 4.000000 |
| latest | 0.147452 | 0.148457 | 0.141262 | 0.152458 | 33.000000 | 36.000000 |
| latest_metadata | 0.062295 | 0.062171 | 0.061640 | 0.063109 | 4.000000 | 7.000000 |
| random | 0.068958 | 0.067762 | 0.063739 | 0.074951 | 5.000000 | 12.000000 |
| singleton | 0.063820 | 0.066316 | 0.062972 | 0.072400 | 5.000000 | 12.000000 |
| thin | 0.064944 | 0.066097 | 0.064341 | 0.068151 | 7.000000 | 10.000000 |
### Matched training / bias_stress / overlap_90
| arm | full_data_loss | log_loss_mean | log_loss_min | log_loss_max | fn_min | fn_max |
| --- | --- | --- | --- | --- | --- | --- |
| change | 0.725023 | 0.766099 | 0.741167 | 0.803426 | 135.000000 | 144.000000 |
| fixed | 0.740573 | 0.723027 | 0.699145 | 0.739404 | 124.000000 | 133.000000 |
| grouped | 0.723325 | 0.731768 | 0.729544 | 0.735302 | 128.000000 | 134.000000 |
| ignore_updates | 0.491554 | 0.449082 | 0.417322 | 0.481899 | 94.000000 | 100.000000 |
| latest | 0.410870 | 0.417247 | 0.396668 | 0.429576 | 95.000000 | 103.000000 |
| latest_metadata | 0.497310 | 0.504188 | 0.497131 | 0.508936 | 110.000000 | 112.000000 |
| random | 0.740622 | 0.736129 | 0.690987 | 0.770357 | 123.000000 | 135.000000 |
| singleton | 0.699166 | 0.729245 | 0.694391 | 0.761162 | 124.000000 | 140.000000 |
| thin | 0.681503 | 0.670569 | 0.649163 | 0.688538 | 125.000000 | 127.000000 |
### Matched training / bias_stress / new_information
| arm | full_data_loss | log_loss_mean | log_loss_min | log_loss_max | fn_min | fn_max |
| --- | --- | --- | --- | --- | --- | --- |
| change | 1.897669 | 1.884810 | 1.797601 | 2.052600 | 188.000000 | 192.000000 |
| fixed | 1.844736 | 1.829377 | 1.753061 | 1.922585 | 185.000000 | 189.000000 |
| grouped | 1.918247 | 1.930359 | 1.861655 | 2.058361 | 188.000000 | 191.000000 |
| ignore_updates | 0.534645 | 0.490767 | 0.460467 | 0.525677 | 127.000000 | 136.000000 |
| latest | 2.011054 | 2.035607 | 1.996967 | 2.069794 | 221.000000 | 227.000000 |
| latest_metadata | 1.532965 | 1.572038 | 1.562081 | 1.584833 | 178.000000 | 185.000000 |
| random | 1.989641 | 1.922227 | 1.821630 | 2.070830 | 187.000000 | 193.000000 |
| singleton | 1.796076 | 1.848862 | 1.762604 | 2.001301 | 183.000000 | 193.000000 |
| thin | 1.781638 | 1.772588 | 1.714080 | 1.813139 | 182.000000 | 187.000000 |

## Does grouping reliably improve on simple controls?

Differences are grouped minus comparator: negative favors grouping. `grouped_lower_loss_seeds` counts the three subset trials; it is not a statistical significance test. All conditions and controls, including the shifted regime, are retained in the companion CSV.

| bank | condition | comparator | absolute_difference_mean | absolute_difference_min | absolute_difference_max | grouped_lower_loss_seeds |
| --- | --- | --- | --- | --- | --- | --- |
| bias_stress | new_information | latest_metadata | 0.358322 | 0.299574 | 0.473529 | 0 |
| bias_stress | new_information | singleton | 0.081497 | 0.057060 | 0.099051 | 0 |
| bias_stress | new_information | thin | 0.157771 | 0.057922 | 0.267815 | 0 |
| bias_stress | overlap_90 | latest_metadata | 0.227580 | 0.221523 | 0.232413 | 0 |
| bias_stress | overlap_90 | singleton | 0.002523 | -0.025860 | 0.035152 | 2 |
| bias_stress | overlap_90 | thin | 0.061199 | 0.046764 | 0.080381 | 0 |
| software | new_information | latest_metadata | 0.005967 | 0.002484 | 0.012833 | 0 |
| software | new_information | singleton | 0.001822 | 0.000672 | 0.003543 | 0 |
| software | new_information | thin | 0.002040 | -0.001578 | 0.007791 | 2 |
| software | overlap_90 | latest_metadata | -0.009005 | -0.009136 | -0.008883 | 3 |
| software | overlap_90 | singleton | 0.000872 | 0.000280 | 0.001615 | 0 |
| software | overlap_90 | thin | -0.000208 | -0.002322 | 0.001248 | 1 |

Absolute loss and overlap-induced degradation are separate endpoints. `grouped_comparisons.csv` also reports the difference in no-reuse-to-condition degradation. A smaller degradation does not guarantee a lower absolute loss. Never pool training subsets, message variants or seeds to increase the independent evaluation count.

## What this permits next

This campaign checks the common tuning range and membership/fold sensitivity for the existing model family. It does not reproduce the covariance-weighting or sequence papers, complete component/oracle ablations, establish a primary comparator, or supply a scientific sample-size calculation. Those are the remaining V02 tasks. Preserve adverse bias-stress and ranking changes; do not select a flattering condition for the paper.

Next implement the explicitly labeled covariance-proxy comparator and ablations with the same fold/budget contract; add state-fusion/oracle diagnostics separately from class forecasting. Use the resulting paired scenario and training-variation evidence for precision planning. V03 must freeze the scientific study before the reserved bank is opened.

## Verification and portability

`audit.json` records source/input/output/archive checksums, full prediction coverage and labels, scenario folds/weights, every class metric, all selected-OOF losses, all 72 thresholds, and equal candidate budgets. The campaign checks replay and matched-latest invariance for every fitted model. This is artifact reconstruction, not A03's independent scientific review.

The compact files preserve source artifact bytes via Git attributes. `provenance.json` maps exports to this reconstruction run. Models, full predictions, datasets and logs remain ignored/local. Exact regeneration requires the run/data transfer described in the root checklist.
