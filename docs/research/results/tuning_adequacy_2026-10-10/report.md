# V02 tuning adequacy: budget inventory and candidate profiles

Date: 10 October 2026. Run `tuning_adequacy_20261010_v2`. Sources: `tuning_20261009_v1`, `covariance_20261009_v1`, `components_20261010_v1`, `sequence_20261010_v1`.
**Exposed development evidence only. No model was fitted, no evaluation forecast was
used, and the scientific bank was not generated.** The tuning decision that uses
this evidence is recorded separately in `docs/research/execution/tuning_decision.md`.

## Scope and checks

All four source runs pass manifest, input and archived-source checks before
reading. The inventory covers 17 class-forecast arms, 136 selected models,
816 candidate scores and 912 per-fit records. Every recorded
selection is re-derived from its candidate scores with the campaign tie rule
(smaller C; for LSTM smaller width, then fewer epochs). For the 48 models
whose runs saved every candidate's OOF predictions (component and sequence runs),
all candidate scores are recomputed from scenario-level predictions; for the other
88, the selected candidate's score is recomputed from its saved OOF predictions.
The largest absolute difference is 5.6e-17. All candidate scores also
match the committed compact exports. Per-fold scores use each run's saved
whole-scenario inner-fold membership (1128 rows in `fold_scores.csv`). The six
state-estimation arms have a different target and are excluded.

## Inventory

`readout` columns are the summary design width before imputer missingness
indicators. Each selection uses six candidates, three whole-scenario inner folds
and one refit (19 fits); every arm has four training trials x two regimes.

| arm | family | partition_or_input | readout_columns_or_parameters | selected_settings | failed_fits | maximum_observed_iterations | fold_scores | selection_seconds_total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| change | logistic | one partition of OD/log-risk change messages | 122 | C=100: 4; C=1000: 4 | 0 | 119.000000 | selected candidate only | 32.533256 |
| fixed | logistic | <=8 time-gap-only partitions; maximum score | 122 | C=100: 5; C=1000: 3 | 0 | 262.000000 | selected candidate only | 137.844813 |
| grouped | logistic | <=8 label-free OD/time partitions; maximum score | 122 | C=100: 5; C=1000: 3 | 0 | 240.000000 | selected candidate only | 96.107540 |
| ignore_updates | logistic | first visible message only | 122 | C=10: 3; C=100: 5 | 0 | 31.000000 | selected candidate only | 20.198873 |
| latest | logistic | none | 1 | C=100: 2; C=1000: 6 | 0 | 16.000000 | selected candidate only | 2.325265 |
| latest_metadata | logistic | none | 60 | C=100: 5; C=1000: 3 | 0 | 28.000000 | selected candidate only | 11.487916 |
| random | logistic | grouped family with hashed random membership | 122 | C=100: 8 | 0 | 222.000000 | selected candidate only | 183.715317 |
| singleton | logistic | one partition | 122 | C=100: 4; C=1000: 4 | 0 | 207.000000 | selected candidate only | 57.209625 |
| thin | logistic | one partition after >=6 h thinning | 122 | C=100: 6; C=1000: 2 | 0 | 160.000000 | selected candidate only | 30.121339 |
| covariance_direct | logistic | one partition; direct inverse-volume weights | 122 | C=100: 4; C=1000: 4 | 0 | 141.000000 | selected candidate only | 40.346585 |
| covariance_trend | logistic | one partition; fitted log-volume trend weights | 122 | C=100: 4; C=1000: 4 | 0 | 125.000000 | selected candidate only | 40.496416 |
| fixed_no_od | logistic | time-only partitions after canonicalization | 74 | C=100: 4; C=1000: 4 | 0 | 235.000000 | all candidates | 120.364906 |
| grouped_no_age | logistic | grouped partitions | 90 | C=100: 5; C=1000: 3 | 0 | 89.000000 | all candidates | 77.550686 |
| grouped_no_od_readout | logistic | grouped partitions (OD still forms groups) | 74 | C=100: 5; C=1000: 3 | 0 | 224.000000 | all candidates | 82.359720 |
| oracle_lineage_weight | logistic | one partition; privileged visible-lineage weights | 122 | C=100: 4; C=1000: 4 | 0 | 128.000000 | all candidates | 100.017838 |
| lstm_history | LSTM | visible canonical message sequence | parameters [2825, 7185, 20513] | h=16,e=60: 3; h=32,e=60: 3; h=8,e=60: 2 | 0 | nan | all candidates | 1066.191404 |
| lstm_latest | LSTM | latest message only | parameters [2825, 7185, 20513] | h=16,e=60: 1; h=32,e=60: 5; h=8,e=60: 2 | 0 | nan | all candidates | 426.517305 |

Logistic selections used 17.2 minutes of recorded selection time and the
LSTM selections 24.9 minutes, excluding evaluation and reconstruction.

## Grid limits are not optimization failures

No fit failed. The maximum observed L-BFGS iterations are
components_20261010_v1 235, covariance_20261009_v1 141, tuning_20261009_v1 262 against a cap of 10,000, with strict convergence
required. A selection at C=1000 or at 60 epochs is therefore a limit of the declared
search, not a numerical failure, and a converged optimizer does not show that the
search was wide enough.

| family | regime | selections | distinct_profiles | upper_budget_selections | upper_budget_distinct | upper_step_gain_median_at_edge | upper_step_gain_max_all | adjacent_gap_median | selected_fold_loss_range_median |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LSTM | matched_mixture | 8 | 8 | 8 | 8 | 0.020320 | 0.042741 | 0.002960 | 0.024307 |
| LSTM | no_reuse_only | 8 | 8 | 8 | 8 | 0.149803 | 0.167028 | 0.010648 | 0.023239 |
| logistic | matched_mixture | 60 | 60 | 7 | 7 | 0.000181 | 0.000622 | 0.000743 | 0.023450 |
| logistic | no_reuse_only | 60 | 44 | 40 | 24 | 0.004067 | 0.009756 | 0.002789 | 0.033208 |

`upper_step_gain` is the inner-OOF loss of the second-largest budget minus that of
the largest (C=100 to 1000; for LSTM, 20 to 60 epochs at the selected width).
Positive values mean the objective was still improving at the edge. Under
no-reuse training several arms are bitwise identical models;
`distinct_profiles` removes those duplicates. `selected_fold_loss_range` is the
spread of the selected candidate's loss across its three inner folds, a scale for
fold heterogeneity rather than a confidence interval.

## Practical tolerance

The table counts edge selections whose last budget step improved the objective
by more than each tolerance, and selections whose nearest competing candidate is
within it (a flat profile that the development data do not resolve). Tolerances
are shown together because none was fixed before these development results
were seen.

| family | regime | tolerance | selections | edge_step_gain_above_tolerance | distinct_edge_step_gain_above_tolerance | adjacent_gap_below_tolerance |
| --- | --- | --- | --- | --- | --- | --- |
| LSTM | matched_mixture | 0.000500 | 8 | 8 | 8 | 0 |
| LSTM | matched_mixture | 0.001000 | 8 | 8 | 8 | 2 |
| LSTM | matched_mixture | 0.005000 | 8 | 7 | 7 | 5 |
| LSTM | matched_mixture | 0.010000 | 8 | 7 | 7 | 8 |
| LSTM | no_reuse_only | 0.000500 | 8 | 8 | 8 | 0 |
| LSTM | no_reuse_only | 0.001000 | 8 | 8 | 8 | 0 |
| LSTM | no_reuse_only | 0.005000 | 8 | 8 | 8 | 0 |
| LSTM | no_reuse_only | 0.010000 | 8 | 8 | 8 | 3 |
| logistic | matched_mixture | 0.000500 | 60 | 1 | 1 | 21 |
| logistic | matched_mixture | 0.001000 | 60 | 0 | 0 | 38 |
| logistic | matched_mixture | 0.005000 | 60 | 0 | 0 | 60 |
| logistic | matched_mixture | 0.010000 | 60 | 0 | 0 | 60 |
| logistic | no_reuse_only | 0.000500 | 60 | 35 | 19 | 12 |
| logistic | no_reuse_only | 0.001000 | 60 | 29 | 17 | 22 |
| logistic | no_reuse_only | 0.005000 | 60 | 14 | 6 | 43 |
| logistic | no_reuse_only | 0.010000 | 60 | 0 | 0 | 59 |

Matched-mixture logistic models: 7/60 selections reach C=1000,
with a largest last-step gain of 0.000622. No-reuse logistic models:
40/60 reach C=1000 (24 distinct profiles), with a largest
last-step gain of 0.009756. 16/16 LSTM selections use the maximum
60 epochs; median 20-to-60-epoch gains are 0.020320 (matched) and
0.149803 (no reuse).

## Scenario-paired resolution

Only the component and sequence runs saved every candidate's OOF predictions.
Gains below are means over training scenarios of per-scenario objective
differences (each scenario carries weight one), with their paired standard
errors. Candidate predictions within one inner-fold design are correlated, so
these are descriptive resolution checks, not tests. The tuning and covariance
runs saved only selected-C OOF predictions; their step gains are aggregate only.

| run_id | regime | step | models | gain_median | gain_min | gain_max | se_median | z_min | z_max | positive_gains | larger_better_all_folds | larger_better_no_fold |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| components_20261010_v1 | matched_mixture | upper_C_step | 16 | -0.000756 | -0.002013 | 0.000622 | 0.000638 | -1.885248 | 1.063438 | 1 | 1 | 0 |
| components_20261010_v1 | no_reuse_only | upper_C_step | 16 | 0.003826 | -0.002599 | 0.009756 | 0.004311 | -0.510822 | 2.912367 | 13 | 6 | 0 |
| sequence_20261010_v1 | matched_mixture | epoch_step | 8 | 0.020320 | 0.004388 | 0.042741 | 0.004717 | 1.516959 | 6.678189 | 8 | 6 | 0 |
| sequence_20261010_v1 | matched_mixture | width_step | 8 | -0.001676 | -0.006232 | 0.020116 | 0.002339 | -3.515082 | 3.833759 | 2 | 2 | 1 |
| sequence_20261010_v1 | no_reuse_only | epoch_step | 8 | 0.149803 | 0.058303 | 0.167028 | 0.010744 | 7.026715 | 17.334822 | 8 | 8 | 0 |
| sequence_20261010_v1 | no_reuse_only | width_step | 8 | 0.009352 | -0.010907 | 0.018067 | 0.004679 | -1.934963 | 5.905745 | 6 | 3 | 0 |

`larger_better_all_folds` and `larger_better_no_fold` count models in which the
larger budget has lower loss in all three, or none, of the inner folds.

For the component arms under matched training, the C=100 to 1000 step favors
C=1000 in 1/16 models; the largest paired z in its favor is
1.06. Under no-reuse training it favors C=1000 in
13/16, with z up to 2.91.

## Neural training traces

Traces are minibatch training losses (dropout active), not validation curves.
With batch size 256, no-reuse fits take 3-4 minibatches per epoch
and matched fits 13-24, so equal epochs are unequal optimizer
budgets across regimes.

| regime | arm | hidden | fits | optimizer_steps_median | final_loss_median | relative_drop_last10_median | relative_drop_last10_max | minimum_at_final_epoch |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| matched_mixture | lstm_history | 8 | 14 | 780.000000 | 0.126861 | 0.018835 | 0.169343 | 1 |
| matched_mixture | lstm_history | 16 | 13 | 780.000000 | 0.128077 | 0.000669 | 0.115401 | 0 |
| matched_mixture | lstm_history | 32 | 13 | 780.000000 | 0.122968 | 0.020788 | 0.082126 | 3 |
| matched_mixture | lstm_latest | 8 | 14 | 780.000000 | 0.153751 | 0.009868 | 0.095768 | 1 |
| matched_mixture | lstm_latest | 16 | 13 | 780.000000 | 0.147493 | -0.011114 | 0.024369 | 1 |
| matched_mixture | lstm_latest | 32 | 13 | 780.000000 | 0.146255 | 0.008657 | 0.095316 | 1 |
| no_reuse_only | lstm_history | 8 | 12 | 180.000000 | 0.124781 | 0.147495 | 0.246401 | 7 |
| no_reuse_only | lstm_history | 16 | 14 | 180.000000 | 0.100804 | 0.251114 | 0.631321 | 5 |
| no_reuse_only | lstm_history | 32 | 14 | 180.000000 | 0.094873 | -0.009611 | 0.256553 | 3 |
| no_reuse_only | lstm_latest | 8 | 12 | 180.000000 | 0.228680 | 0.135575 | 0.174876 | 9 |
| no_reuse_only | lstm_latest | 16 | 12 | 180.000000 | 0.186575 | 0.095873 | 0.153964 | 9 |
| no_reuse_only | lstm_latest | 32 | 16 | 180.000000 | 0.169948 | 0.024340 | 0.099188 | 1 |

## What this evidence can and cannot establish

- It shows where the declared budgets bind on the training objective. It does
  not show that a wider grid or longer training would change evaluation-bank
  results, rankings or degradation contrasts; that requires new fits.
- Inner-OOF gains reuse one exposed development bank per trial; the three
  800-scenario subsets overlap the full-reference cohort.
- A flat profile within a tolerance is not evidence of equivalence for
  inference, and no tolerance here was prespecified.
- Neural traces lack validation curves; a training-loss plateau does not exclude
  further out-of-fold change, and continued decrease does not guarantee it.
- This is same-workflow artifact analysis, not independent A03 review.
