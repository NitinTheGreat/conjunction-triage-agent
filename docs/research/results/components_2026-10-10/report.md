# V02 observable-provenance components and oracle weighting

Date: 10 October 2026. Source `components_20261010_v1`; reconstruction `components_summary_20261010_v1`.
**Exposed development results; V02 remains open and scientific outcomes remain reserved.**

## Contract and interventions

The [component contract](../../execution/component_contract.md) was committed
before fitting. Four new arms share the archived logistic readout, six C values,
three whole-scenario folds, four training trials and two regimes. There are
32 selected models and 608 fits; every fit passed the strict
convergence policy. Maximum observed iterations: 235.
14/32 selections reach the upper C boundary.
This is a bounded implementation comparison, not proof of optimal tuning.
Each ablation is retuned: observed differences include changes in selected C and
fitted coefficients, and do not identify a causal field effect in a fixed model.

`grouped_no_age` removes all eight categorical age bins from latest, mean,
variance and missingness summaries, reducing 122 columns to 90. Groups are
unchanged: the existing grouping rule uses OD and time, not age categories.
`grouped_no_od_readout` removes all twelve OD fields from those four blocks,
leaving 74 columns, while retaining OD-based grouping. `fixed_no_od` uses the
existing time-only fixed family and the same 74-column readout. It excludes OD
after common full-record canonicalization; arbitrary raw OD changes could still
affect upstream exact deduplication/tie ordering. These are conditional feature
interventions, not claims of independence from every trace of source metadata.

The existing singleton removes grouping, and existing fixed retains OD readout
with time-only groups. No new labels are assigned to identical archived controls.
All preprocessing is training-only; columnwise unused preprocessing values do
not affect retained columns. The final readout scaler is refitted on retained
design rows. One scenario contributes total objective weight one across its
variants and partition rows. The model takes the maximum partition probability.
Selected inner OOF is reused for tuning, monotone calibration and the nominal
95% training-recall threshold; there is no independent risk certification.

## Oracle definition and checks

`oracle_lineage_weight` changes only singleton mean/variance weights. Each unique
visible observation allocates one unit equally among messages containing it;
normalize by the visible union size. Equal allocations within 1e-14 use exact
archived uniform arithmetic. Latest features, time span, canonical message count
and missingness remain unchanged; no IDs or union-size predictor is added.
This is a privileged descriptive weighting rule, not posterior fusion, effective
sample size, a real-data method or a bound on attainable class performance.

All 21,000 scenario/condition lineage cases and 138,000 canonical
messages match audited publication order and visible observation IDs 0–59.
The earlier state reconstruction is reused under unchanged source/input hashes;
no new observation-state reconstruction or future-observation access is claimed.
No-reuse, exact replay and solution-reissue allocations are uniform; partial
overlap, cumulative information and burst reissue are nonuniform. For all four
no-reuse training trials, oracle selected C, OOF, threshold and predictions on
uniform-allocation conditions exactly match the saved singleton model.

Burst publication still changes time/age summaries and message count, so these
weights do not promise burst-invariant forecasts. `lineage_diagnostics.csv`
retains all condition/bank weight ranges; its unique counts are diagnostics only.

## Full-reference results

The reference uses 1,000 development scenarios. Each evaluation bank has 1,000
paired scenarios, with 194 software positives or 326 shared-bias positives.
These are enriched, unweighted synthetic stress populations, not operational
prevalence or workload estimates. q predicts final recorded-risk class, not
collision occurrence. Existing 104 selected models are reused after compatibility
checks; all 136 models' stored class metrics and case identities are verified.

### Matched training / software / overlap_90

| arm | log_loss | brier | reviewed | fn |
| --- | --- | --- | --- | --- |
| change | 0.171251 | 0.055850 | 263 | 9 |
| covariance_direct | 0.172675 | 0.056107 | 263 | 9 |
| covariance_trend | 0.172379 | 0.056128 | 263 | 9 |
| fixed | 0.174403 | 0.057190 | 261 | 10 |
| fixed_no_od | 0.175940 | 0.057591 | 261 | 10 |
| grouped | 0.173125 | 0.056989 | 262 | 10 |
| grouped_no_age | 0.171808 | 0.056630 | 262 | 10 |
| grouped_no_od_readout | 0.175086 | 0.057490 | 261 | 10 |
| ignore_updates | 0.170019 | 0.055330 | 268 | 6 |
| latest | 0.182685 | 0.061805 | 282 | 8 |
| latest_metadata | 0.182578 | 0.061495 | 260 | 16 |
| lstm_history | 0.173154 | 0.057174 | 259 | 11 |
| lstm_latest | 0.190712 | 0.063700 | 264 | 11 |
| oracle_lineage_weight | 0.171105 | 0.055667 | 262 | 9 |
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
| fixed_no_od | 0.064415 | 0.019373 | 210 | 7 |
| grouped | 0.066160 | 0.019874 | 206 | 8 |
| grouped_no_age | 0.065214 | 0.019630 | 207 | 8 |
| grouped_no_od_readout | 0.065364 | 0.019677 | 207 | 8 |
| ignore_updates | 0.157324 | 0.052030 | 266 | 6 |
| latest | 0.147452 | 0.045261 | 161 | 36 |
| latest_metadata | 0.062295 | 0.019166 | 213 | 7 |
| lstm_history | 0.109397 | 0.033612 | 252 | 3 |
| lstm_latest | 0.083539 | 0.023089 | 226 | 1 |
| oracle_lineage_weight | 0.063212 | 0.019796 | 208 | 8 |
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
| fixed_no_od | 0.747734 | 0.146518 | 194 | 132 |
| grouped | 0.723325 | 0.145226 | 192 | 134 |
| grouped_no_age | 0.716817 | 0.145459 | 191 | 135 |
| grouped_no_od_readout | 0.735636 | 0.146252 | 193 | 133 |
| ignore_updates | 0.491554 | 0.123397 | 221 | 105 |
| latest | 0.410870 | 0.110220 | 223 | 103 |
| latest_metadata | 0.497310 | 0.128359 | 209 | 117 |
| lstm_history | 0.498648 | 0.140406 | 199 | 127 |
| lstm_latest | 0.478717 | 0.133654 | 211 | 115 |
| oracle_lineage_weight | 0.736039 | 0.145584 | 195 | 131 |
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
| fixed_no_od | 1.832973 | 0.188306 | 138 | 188 |
| grouped | 1.918247 | 0.191077 | 136 | 190 |
| grouped_no_age | 1.888231 | 0.190474 | 136 | 190 |
| grouped_no_od_readout | 1.898923 | 0.190497 | 137 | 189 |
| ignore_updates | 0.534645 | 0.142099 | 185 | 141 |
| latest | 2.011054 | 0.232400 | 99 | 227 |
| latest_metadata | 1.532965 | 0.182516 | 141 | 185 |
| lstm_history | 0.812824 | 0.164588 | 166 | 160 |
| lstm_latest | 0.873985 | 0.182408 | 155 | 171 |
| oracle_lineage_weight | 1.867092 | 0.189165 | 137 | 189 |
| random | 1.989641 | 0.194067 | 134 | 192 |
| singleton | 1.796076 | 0.187380 | 138 | 188 |
| thin | 1.781638 | 0.187241 | 139 | 187 |

## Component contrasts and training sensitivity

Differences below are component minus named comparator; negative favors the
component. The three 800-scenario training subsets overlap. Their ranges and
lower-loss counts are descriptive, not confidence intervals or significance tests.
The full-reference trial is excluded from these ranges.

| bank | condition | arm | comparator | log_loss_absolute_difference_mean | log_loss_absolute_difference_min | log_loss_absolute_difference_max | component_lower_loss_seeds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| bias_stress | new_information | fixed_no_od | fixed | 0.006947 | -0.037576 | 0.029592 | 1 |
| bias_stress | overlap_90 | fixed_no_od | fixed | 0.031376 | 0.028322 | 0.035727 | 0 |
| bias_stress | new_information | fixed_no_od | grouped_no_od_readout | -0.093122 | -0.115332 | -0.080484 | 3 |
| bias_stress | overlap_90 | fixed_no_od | grouped_no_od_readout | 0.002326 | -0.016426 | 0.024178 | 2 |
| bias_stress | new_information | grouped_no_age | grouped | -0.018063 | -0.021140 | -0.016379 | 3 |
| bias_stress | overlap_90 | grouped_no_age | grouped | 0.007963 | -0.009120 | 0.021361 | 1 |
| bias_stress | new_information | grouped_no_od_readout | grouped | -0.000914 | -0.026469 | 0.019181 | 1 |
| bias_stress | overlap_90 | grouped_no_od_readout | grouped | 0.020309 | 0.000453 | 0.044823 | 0 |
| bias_stress | new_information | oracle_lineage_weight | singleton | 0.067412 | 0.022914 | 0.095371 | 0 |
| bias_stress | overlap_90 | oracle_lineage_weight | singleton | 0.037447 | 0.018539 | 0.048732 | 0 |
| software | new_information | fixed_no_od | fixed | 0.000108 | -0.000366 | 0.000507 | 1 |
| software | overlap_90 | fixed_no_od | fixed | 0.003190 | 0.001450 | 0.004344 | 0 |
| software | new_information | fixed_no_od | grouped_no_od_readout | -0.001964 | -0.005211 | -0.000286 | 3 |
| software | overlap_90 | fixed_no_od | grouped_no_od_readout | 0.000528 | -0.001249 | 0.002037 | 1 |
| software | new_information | grouped_no_age | grouped | -0.000863 | -0.001888 | -0.000322 | 3 |
| software | overlap_90 | grouped_no_age | grouped | -0.000689 | -0.001471 | -0.000285 | 3 |
| software | new_information | grouped_no_od_readout | grouped | -0.000634 | -0.002258 | 0.000342 | 1 |
| software | overlap_90 | grouped_no_od_readout | grouped | 0.002084 | 0.001607 | 0.002615 | 0 |
| software | new_information | oracle_lineage_weight | singleton | -0.001046 | -0.002404 | -0.000258 | 3 |
| software | overlap_90 | oracle_lineage_weight | singleton | 0.000230 | -0.001271 | 0.001518 | 1 |

All arms, seven conditions and both regimes remain in the CSV exports. Paired
absolute and no-reuse-relative degradation differences cover log loss, Brier,
review indicator and missed-positive indicator; misses use the positive-scenario
denominator. Paired standard deviations support later precision planning.
The 1,904,000 combined prediction rows are repeated scores, not new
independent cases. No confirmatory or multiplicity-adjusted test is claimed.

## Audit and next work

All 608 fold/refit checkpoints, prefix preprocessors and final readout
scalers were audited, including 571,200 reconstructed
candidate OOF values. Selected C, calibration and thresholds reproduce. All
448,000 new forecasts reconstruct bitwise in this environment, and all
combined class metrics/labels match their source records. Each failed-fit category
would stop the run; no candidate was dropped. Checkpoints and full predictions
stay local; compact exports carry byte hashes.

This is artifact verification, not independent A03 review. Tuning adequacy,
simulator sensitivity and precision planning remain before V03. Neither a
feature-removal improvement nor privileged lineage weighting automatically proves
a general mechanism, novel method, operational gain or adequate miss control.
The scientific bank has not been generated. Retain null and adverse comparisons.
