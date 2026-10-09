# V02 covariance-proxy comparator and ablation

Date: 9 October 2026. Source `covariance_20261009_v1`; controls `tuning_20261009_v1`; reconstruction `covariance_summary_20261009_v1`. **Exploratory development evidence; V02 remains open.** Reserved scientific scenarios remain ungenerated.

## Method and comparison contract

`covariance_trend` fits an unweighted straight line to log diagonal volume versus normalized elapsed visible publication time, then normalizes inverse fitted-volume weights. `covariance_direct` directly normalizes inverse volumes. The volume proxy is `(t_sigma_r²+c_sigma_r²)*(t_sigma_t²+c_sigma_t²)`. Log arithmetic avoids overflow. Both retain the singleton feature width, latest features, canonical message count, missingness, preprocessing and calibrated logistic readout.

This is an aligned radial/tangential diagonal approximation. The simulator has zero normal sigmas; the real allowlist lacks full encounter-plane geometry and correlations. It is **not a reproduction** of Sanchez et al.'s covariance weighting, Dempster–Shafer inference, a physical collision-probability estimator, or an independent-information count. See the compatibility review and saved implementation plan for the input mapping and limitations.

Both modes use uniform weights for invalid/negative sigmas, a nonpositive combined variance, invalid time, fewer than two distinct times, or a log-volume range <=1e-12. Individual zero sigmas are permitted if their combined variance is positive. Infinite source fields are rejected by the common canonicalizer before fitting. No outcome or learned imputation changes message precision weights.

The 16 new models share all four training trials, both regimes, C=[0.01, 0.1, 1.0, 10.0, 100.0, 1000.0], three scenario folds and a 10,000-iteration cap with the 72 archived control models. All candidate/final fits passed convergence checks; 8/16 new selections remain at the upper C boundary. Compatibility checks require unchanged data/shared fitting code and exactly unchanged legacy history syntax after removing the two new-mode additions. Cohort and fold tables match the saved reference. No control receives a new tuning opportunity.

## Construction diagnostics before fitting

All three exposed banks and seven conditions were inspected before the first fit, producing 42,000 event/mode diagnostic rows. Every constant-covariance condition reduces exactly to uniform message weighting. Cumulative new-information histories have nonuniform weights. `weight_diagnostics.csv` includes every bank, condition, mode, reason and concentration range. Inverse squared-weight concentration is only a descriptive weight statistic; it is not an effective number of independent observations.

For no-reuse-only training, both approximations reproduce saved singleton selected C, OOF predictions, thresholds and constant-condition forecasts for every trial. Under matched training, new-information histories have changed weighted summaries, so refitted coefficients can change predictions even on constant-covariance evaluation prefixes. Equal feature weights alone do not imply equal fitted predictors across different training designs.

## Full-data reference results

These are the common 1,000-scenario training reference. Each evaluation bank contains 1,000 scenarios: software has 194 positives, bias stress 326. Counts are per bank/condition; enriched synthetic prevalence is not operational workload. Forecast `q` targets final recorded risk class, not collision occurrence. A nominal 95% training-recall threshold is not an evaluation guarantee.

### Matched training / software / overlap_90

| arm | log_loss | brier | reviewed | fn |
| --- | --- | --- | --- | --- |
| change | 0.171251 | 0.055850 | 263 | 9 |
| covariance_direct | 0.172675 | 0.056107 | 263 | 9 |
| covariance_trend | 0.172379 | 0.056128 | 263 | 9 |
| fixed | 0.174403 | 0.057190 | 261 | 10 |
| grouped | 0.173125 | 0.056989 | 262 | 10 |
| ignore_updates | 0.170019 | 0.055330 | 268 | 6 |
| latest | 0.182685 | 0.061805 | 282 | 8 |
| latest_metadata | 0.182578 | 0.061495 | 260 | 16 |
| random | 0.173164 | 0.056853 | 263 | 9 |
| singleton | 0.170962 | 0.055843 | 262 | 9 |
| thin | 0.174332 | 0.057741 | 261 | 10 |

### Matched training / software / new_information

| arm | log_loss | brier | reviewed | fn |
| --- | --- | --- | --- | --- |
| change | 0.066654 | 0.019971 | 206 | 8 |
| covariance_direct | 0.062217 | 0.019499 | 208 | 8 |
| covariance_trend | 0.062395 | 0.019583 | 210 | 7 |
| fixed | 0.064882 | 0.019468 | 209 | 7 |
| grouped | 0.066160 | 0.019874 | 206 | 8 |
| ignore_updates | 0.157324 | 0.052030 | 266 | 6 |
| latest | 0.147452 | 0.045261 | 161 | 36 |
| latest_metadata | 0.062295 | 0.019166 | 213 | 7 |
| random | 0.068958 | 0.020313 | 203 | 10 |
| singleton | 0.063820 | 0.019244 | 209 | 8 |
| thin | 0.064944 | 0.020262 | 206 | 10 |

### Matched training / bias_stress / overlap_90

| arm | log_loss | brier | reviewed | fn |
| --- | --- | --- | --- | --- |
| change | 0.725023 | 0.143503 | 199 | 127 |
| covariance_direct | 0.727452 | 0.143356 | 195 | 131 |
| covariance_trend | 0.713091 | 0.143215 | 197 | 129 |
| fixed | 0.740573 | 0.146049 | 192 | 134 |
| grouped | 0.723325 | 0.145226 | 192 | 134 |
| ignore_updates | 0.491554 | 0.123397 | 221 | 105 |
| latest | 0.410870 | 0.110220 | 223 | 103 |
| latest_metadata | 0.497310 | 0.128359 | 209 | 117 |
| random | 0.740622 | 0.144601 | 193 | 133 |
| singleton | 0.699166 | 0.143171 | 195 | 131 |
| thin | 0.681503 | 0.141194 | 192 | 134 |

### Matched training / bias_stress / new_information

| arm | log_loss | brier | reviewed | fn |
| --- | --- | --- | --- | --- |
| change | 1.897669 | 0.190110 | 137 | 189 |
| covariance_direct | 1.865558 | 0.189339 | 137 | 189 |
| covariance_trend | 1.821654 | 0.187771 | 138 | 188 |
| fixed | 1.844736 | 0.189007 | 138 | 188 |
| grouped | 1.918247 | 0.191077 | 136 | 190 |
| ignore_updates | 0.534645 | 0.142099 | 185 | 141 |
| latest | 2.011054 | 0.232400 | 99 | 227 |
| latest_metadata | 1.532965 | 0.182516 | 141 | 185 |
| random | 1.989641 | 0.194067 | 134 | 192 |
| singleton | 1.796076 | 0.187380 | 138 | 188 |
| thin | 1.781638 | 0.187241 | 139 | 187 |

## Training-subset sensitivity

The three additional trials each use 800 scenarios/144 positives from the same development bank. They overlap and are not independent training-bank replications. `loss_ranges.csv` gives mean/min/max over these three trials only, separate from the full-data reference. Ranges are not confidence intervals. All 1,232,000 combined prediction rows repeatedly evaluate the same scenarios; they do not increase the independent case count.

Differences below are proxy minus comparator; negative favors the proxy. The count records how many of the three subset trials have strictly lower loss, not a significance test. Every condition, regime and control (including direct-versus-trend) is retained in the CSV exports.

| bank | condition | arm | comparator | absolute_difference_mean | absolute_difference_min | absolute_difference_max | proxy_lower_loss_seeds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| bias_stress | new_information | covariance_direct | grouped | -0.038281 | -0.072340 | -0.020559 | 3 |
| bias_stress | overlap_90 | covariance_direct | grouped | 0.007932 | -0.005513 | 0.028956 | 1 |
| bias_stress | new_information | covariance_direct | latest_metadata | 0.320040 | 0.279015 | 0.401188 | 0 |
| bias_stress | overlap_90 | covariance_direct | latest_metadata | 0.235513 | 0.221878 | 0.257761 | 0 |
| bias_stress | new_information | covariance_direct | singleton | 0.043216 | -0.015280 | 0.078492 | 1 |
| bias_stress | overlap_90 | covariance_direct | singleton | 0.010455 | -0.001369 | 0.029639 | 1 |
| bias_stress | new_information | covariance_trend | grouped | -0.044705 | -0.088491 | 0.009661 | 2 |
| bias_stress | overlap_90 | covariance_trend | grouped | 0.002593 | -0.020238 | 0.047968 | 2 |
| bias_stress | new_information | covariance_trend | latest_metadata | 0.313617 | 0.213372 | 0.483190 | 0 |
| bias_stress | overlap_90 | covariance_trend | latest_metadata | 0.230173 | 0.201285 | 0.276773 | 0 |
| bias_stress | new_information | covariance_trend | singleton | 0.036792 | -0.000110 | 0.066721 | 1 |
| bias_stress | overlap_90 | covariance_trend | singleton | 0.005115 | -0.021962 | 0.022108 | 1 |
| software | new_information | covariance_direct | grouped | -0.003986 | -0.007485 | -0.002154 | 3 |
| software | overlap_90 | covariance_direct | grouped | 0.000272 | -0.000801 | 0.001236 | 1 |
| software | new_information | covariance_direct | latest_metadata | 0.001981 | 0.000265 | 0.005348 | 0 |
| software | overlap_90 | covariance_direct | latest_metadata | -0.008734 | -0.009684 | -0.007762 | 3 |
| software | new_information | covariance_direct | singleton | -0.002164 | -0.003942 | -0.001067 | 3 |
| software | overlap_90 | covariance_direct | singleton | 0.001144 | -0.000080 | 0.001995 | 1 |
| software | new_information | covariance_trend | grouped | -0.002641 | -0.003623 | -0.001821 | 3 |
| software | overlap_90 | covariance_trend | grouped | 0.000332 | -0.001883 | 0.003068 | 2 |
| software | new_information | covariance_trend | latest_metadata | 0.003326 | 0.000104 | 0.009210 | 0 |
| software | overlap_90 | covariance_trend | latest_metadata | -0.008673 | -0.010766 | -0.005929 | 3 |
| software | new_information | covariance_trend | singleton | -0.000819 | -0.001229 | -0.000080 | 3 |
| software | overlap_90 | covariance_trend | singleton | 0.001204 | -0.001162 | 0.003349 | 1 |

`paired_contrasts.csv` retains scenario-paired means and standard deviations for absolute loss and no-reuse-to-condition degradation separately in each trial. These support later precision work; no sample size or primary scientific comparison is selected here. Do not pool trial repeats to claim more independent positives or turn exploratory comparisons into confirmatory tests.

## Reconstruction and remaining work

The audit verifies immutable inputs, archived sources and outputs; every prediction case/label and class metric; new selected-OOF losses and thresholds; and all 224,000 new forecast probabilities recomputed from their saved models. Weight diagnostics also reconstruct from the visible prefixes. This is artifact verification, not A03 independent scientific review. Compact artifacts retain exact bytes and provenance; model/prediction/source archives stay local and ignored.

This completes the covariance-proxy comparison and direct-weighting ablation on the exposed simulation design. It does not implement the sequence adaptation, provenance-component/oracle ablations, state-fusion diagnostics, independent training-bank uncertainty, or precision design. Real-data proxy evaluation is not claimed. Those limits and remaining grid-boundary choices must be addressed before V03 freezes the scientific study. Preserve unfavorable and collapsed-control results.
