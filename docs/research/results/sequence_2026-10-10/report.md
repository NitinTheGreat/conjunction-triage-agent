# V02 sequence-family adaptation and latest-only capacity control

Date: 10 October 2026. Source `sequence_20261010_v1`; reconstruction `sequence_summary_20261010_v1`.
**Exploratory exposed-bank results. V02 remains open; scientific reservation unopened.**

## Method and fixed budget

The [committed contract](../../execution/sequence_contract.md) precedes the first
study fit. Both arms use two unidirectional LSTM layers, dropout 0.2, a final-valid-state
linear readout and BCE. Widths 8/16/32 crossed with 20/60 fixed epochs give six
candidates per arm. Adam uses learning rate .003, gradient norm cap 5, batch size
256, CPU float32 and deterministic algorithms. The 60-dimensional per-message
input contains the common phi fields and missing flags; age codes are categorical.
Packed sequences exclude padding inside recurrence. Chronological ordering and
exact-replay canonicalization precede feature construction. No future rows, IDs,
final labels or oracle lineage enter the input.

The history arm receives the full visible prefix; `lstm_latest` receives only its
last message. Both use training-prefix-only median/robust scaling to match the
preprocessing policy; consequently the latest arm uses training-history distribution
statistics, but no earlier messages from an evaluation event. Checkpoint audit
refits every preprocessor using exactly its fitting rows.

This is a smaller-capacity final-class adaptation of an accessible sequence family,
not Pinto's next-CDM MSE experiment, a published score reproduction or a SOTA claim.
Six candidates match the logistic/proxy candidate count but not their capacity,
optimizer or compute budget. There is no early stopping or outcome-based grid
change. 304 declared fits completed; 16/16
selections use the maximum epoch budget and 8/16
use maximum width. Fixed-epoch training does not establish optimizer convergence.
`candidate_scores.csv` and `fit_records.csv` retain every candidate score and
fit runtime/seed; local checkpoints also retain every epoch's training loss.

All variants of a scenario remain together in the three inner folds. Each scenario
contributes objective weight one across its variants. Selected inner OOF scores
are reused for monotone Platt calibration and the nominal 95% training-recall
threshold; this reuse can be optimistic and supplies no risk guarantee. The same
1,000-scenario reference and three overlapping 800-scenario subsets, regimes and
fold assignments are shared with the 88 archived control models. Control reuse
passes data/source/fold compatibility checks; controls receive no new tuning.

## Full-data reference

Each evaluation bank contains 1,000 paired scenarios: software has 194 positives,
bias stress 326. These enriched, unweighted synthetic banks do not estimate
operational prevalence or workload. Forecast q means final recorded-risk class,
not physical collision probability or a maneuver decision. All conditions and
both regimes, including adverse cases, remain in `metrics.csv`.

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
| lstm_history | 0.173154 | 0.057174 | 259 | 11 |
| lstm_latest | 0.190712 | 0.063700 | 264 | 11 |
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
| lstm_history | 0.109397 | 0.033612 | 252 | 3 |
| lstm_latest | 0.083539 | 0.023089 | 226 | 1 |
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
| lstm_history | 0.498648 | 0.140406 | 199 | 127 |
| lstm_latest | 0.478717 | 0.133654 | 211 | 115 |
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
| lstm_history | 0.812824 | 0.164588 | 166 | 160 |
| lstm_latest | 0.873985 | 0.182408 | 155 | 171 |
| random | 1.989641 | 0.194067 | 134 | 192 |
| singleton | 1.796076 | 0.187380 | 138 | 188 |
| thin | 1.781638 | 0.187241 | 139 | 187 |

## Training sensitivity and paired endpoints

The three 800-scenario subsets overlap; neither these trials nor the repeated
1,456,000 prediction rows are independent replications. Ranges below are
descriptive, not confidence intervals. Negative loss differences favor the named
neural arm. A count of three lower-loss trials is not a significance test.

| bank | condition | arm | comparator | log_loss_absolute_difference_mean | log_loss_absolute_difference_min | log_loss_absolute_difference_max | neural_lower_loss_seeds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| bias_stress | new_information | lstm_history | covariance_direct | -1.379228 | -1.586824 | -1.200811 | 3 |
| bias_stress | overlap_90 | lstm_history | covariance_direct | -0.297545 | -0.335462 | -0.228685 | 3 |
| bias_stress | new_information | lstm_history | grouped | -1.417509 | -1.659164 | -1.221370 | 3 |
| bias_stress | overlap_90 | lstm_history | grouped | -0.289612 | -0.335107 | -0.199729 | 3 |
| bias_stress | new_information | lstm_history | latest_metadata | -1.059187 | -1.185635 | -0.921796 | 3 |
| bias_stress | overlap_90 | lstm_history | latest_metadata | -0.062032 | -0.113584 | 0.029075 | 2 |
| bias_stress | new_information | lstm_history | lstm_latest | -0.332753 | -0.486444 | -0.165239 | 3 |
| bias_stress | overlap_90 | lstm_history | lstm_latest | 0.015327 | -0.036925 | 0.091853 | 2 |
| bias_stress | new_information | lstm_history | singleton | -1.336012 | -1.602104 | -1.122319 | 3 |
| bias_stress | overlap_90 | lstm_history | singleton | -0.287090 | -0.336832 | -0.225590 | 3 |
| bias_stress | new_information | lstm_latest | covariance_direct | -1.046474 | -1.184809 | -0.854235 | 3 |
| bias_stress | overlap_90 | lstm_latest | covariance_direct | -0.312872 | -0.320538 | -0.298537 | 3 |
| bias_stress | new_information | lstm_latest | grouped | -1.084756 | -1.206754 | -0.874794 | 3 |
| bias_stress | overlap_90 | lstm_latest | grouped | -0.304939 | -0.325054 | -0.291582 | 3 |
| bias_stress | new_information | lstm_latest | latest_metadata | -0.726434 | -0.904892 | -0.575220 | 3 |
| bias_stress | overlap_90 | lstm_latest | latest_metadata | -0.077359 | -0.092641 | -0.062777 | 3 |
| bias_stress | new_information | lstm_latest | lstm_history | 0.332753 | 0.165239 | 0.486444 | 0 |
| bias_stress | overlap_90 | lstm_latest | lstm_history | -0.015327 | -0.091853 | 0.036925 | 1 |
| bias_stress | new_information | lstm_latest | singleton | -1.003259 | -1.118374 | -0.775743 | 3 |
| bias_stress | overlap_90 | lstm_latest | singleton | -0.302417 | -0.317443 | -0.289901 | 3 |
| software | new_information | lstm_history | covariance_direct | 0.096818 | 0.070073 | 0.125455 | 0 |
| software | overlap_90 | lstm_history | covariance_direct | 0.007542 | -0.000700 | 0.013377 | 1 |
| software | new_information | lstm_history | grouped | 0.092832 | 0.067919 | 0.117970 | 0 |
| software | overlap_90 | lstm_history | grouped | 0.007814 | 0.000536 | 0.013758 | 0 |
| software | new_information | lstm_history | latest_metadata | 0.098799 | 0.070402 | 0.130803 | 0 |
| software | overlap_90 | lstm_history | latest_metadata | -0.001192 | -0.008462 | 0.004622 | 1 |
| software | new_information | lstm_history | lstm_latest | 0.076978 | 0.048249 | 0.122137 | 0 |
| software | overlap_90 | lstm_history | lstm_latest | -0.012333 | -0.013610 | -0.010534 | 3 |
| software | new_information | lstm_history | singleton | 0.094654 | 0.068591 | 0.121513 | 0 |
| software | overlap_90 | lstm_history | singleton | 0.008686 | 0.000816 | 0.015373 | 0 |
| software | new_information | lstm_latest | covariance_direct | 0.019840 | 0.003318 | 0.034379 | 0 |
| software | overlap_90 | lstm_latest | covariance_direct | 0.019874 | 0.012910 | 0.023911 | 0 |
| software | new_information | lstm_latest | grouped | 0.015854 | -0.004168 | 0.032061 | 1 |
| software | overlap_90 | lstm_latest | grouped | 0.020146 | 0.014145 | 0.024292 | 0 |
| software | new_information | lstm_latest | latest_metadata | 0.021821 | 0.008666 | 0.034644 | 0 |
| software | overlap_90 | lstm_latest | latest_metadata | 0.011141 | 0.005148 | 0.015156 | 0 |
| software | new_information | lstm_latest | lstm_history | -0.076978 | -0.122137 | -0.048249 | 3 |
| software | overlap_90 | lstm_latest | lstm_history | 0.012333 | 0.010534 | 0.013610 | 0 |
| software | new_information | lstm_latest | singleton | 0.017676 | -0.000624 | 0.033312 | 1 |
| software | overlap_90 | lstm_latest | singleton | 0.021018 | 0.014426 | 0.025906 | 0 |

`paired_contrasts.csv` retains scenario-paired absolute and no-reuse-relative
degradation differences for log loss, Brier score, review indicator and missed
positive indicator. Miss differences are conditional on the bank's positive
scenarios; other endpoints average all 1,000 cases. Paired standard deviations
support later precision planning. No multiplicity-adjusted test or frozen primary
comparison is claimed. `loss_ranges.csv` retains per-arm loss, Brier, review-count
and missed-positive-count ranges over the three subsets separately from the full
reference.

## Verification and next work

All 304 checkpoint metadata/preprocessors and 285,600
candidate OOF values reconstruct; selection, calibration and thresholds reproduce.
All 224,000 new forecasts reconstruct bitwise from selected checkpoints in
this environment. All 104 models' saved prediction metrics and scenario identities
are checked; earlier control models retain their previous audits. Exact replay
and latest-only invariants pass with the declared float32 tolerance. Safe checkpoint
loading uses `weights_only=True`; cross-platform bitwise equality is not promised.

This is artifact verification, not independent A03 scientific review. Observable-
provenance component ablations and precision planning remain before V03. The
scientific seed 20261012 has not been generated, and no real-data neural efficacy
or superior method conclusion follows automatically from these development tables.
