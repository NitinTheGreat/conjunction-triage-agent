# A01 retrospective real-CDM analysis

Run `real_summary_20261010_v2` from refit `real_retrospective_20261010_v1`. **Exposed retrospective evidence** on the Kelvins
benchmark cohort under the frozen Track R analysis choices ([contract](../../execution/a01_contract.json)).
It is not confirmation, it is not pooled with simulation, and it is not an
operational workload or safety estimate. The label is final recorded log-risk
>= -6, not collision occurrence.

## Inputs

- **Training cohort:** 8,293 events / 66 positives, out-of-fold over the stored 5x3
  nested whole-event folds.
- **Historical test split:** 2,167 / 150, evaluated once with final models selected
  on the full training cohort. Its labels were already exposed but were never used
  for a model choice here.
- **Arms:** `latest`, `latest_metadata`, `singleton` and `grouped`, refitted with the
  frozen six-value C grid and strict convergence. `causal_gbm` OOF predictions are
  reused unchanged as an external reference.
- **Reproduction:** 19/20 arm-folds reproduce
  the earlier narrower-grid run's predictions exactly. Changed folds:
  latest fold 0 (C 10 to 100).

## Label shift between the two exposed sets

The training cohort's positive share is 0.80%;
the historical test split's is 6.92%.
Probabilities calibrated on the training cohort therefore under-predict on the
test split; see the calibration intercepts. Ranking metrics and paired contrasts
are less affected than calibration-in-the-large.

## Discrimination, loss and nominal operating points

Review and miss counts use training-only thresholds at nominal 90/95/99% recall.
They are not population guarantees.

| split | arm | n | positives | log_loss | brier | roc_auc | average_precision | reviewed_90 | missed_90 | reviewed_95 | missed_95 | reviewed_99 | missed_99 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| training_oof | causal_gbm | 8293 | 66 | 0.027217 | 0.006482 | 0.961678 | 0.301060 | 1211 | 4 | 1740 | 3 | 2540 | 3 |
| training_oof | grouped | 8293 | 66 | 0.032863 | 0.007443 | 0.932189 | 0.157886 | 1762 | 7 | 2379 | 3 | 3313 | 2 |
| training_oof | latest | 8293 | 66 | 0.030159 | 0.007120 | 0.957378 | 0.173527 | 825 | 6 | 2176 | 3 | 2948 | 0 |
| training_oof | latest_metadata | 8293 | 66 | 0.029503 | 0.006855 | 0.951206 | 0.250810 | 1437 | 7 | 1895 | 3 | 2330 | 0 |
| training_oof | singleton | 8293 | 66 | 0.032521 | 0.007354 | 0.932591 | 0.154363 | 1746 | 6 | 2380 | 2 | 3232 | 1 |
| historical_test | grouped | 2167 | 150 | 0.230222 | 0.061146 | 0.924799 | 0.558532 | 573 | 13 | 778 | 6 | 841 | 6 |
| historical_test | latest | 2167 | 150 | 0.212689 | 0.056353 | 0.944984 | 0.665077 | 343 | 15 | 599 | 9 | 861 | 6 |
| historical_test | latest_metadata | 2167 | 150 | 0.212645 | 0.056734 | 0.940466 | 0.612657 | 578 | 8 | 624 | 8 | 694 | 8 |
| historical_test | singleton | 2167 | 150 | 0.238952 | 0.061708 | 0.914391 | 0.529734 | 556 | 14 | 733 | 12 | 852 | 7 |

## Calibration

Logistic recalibration of outcomes on logit(q): an intercept of 0 and slope of 1
mean calibrated. Decile reliability bins are in `reliability.csv`.

| split | arm | calibration_intercept | calibration_slope | mean_q_minus_observed |
| --- | --- | --- | --- | --- |
| training_oof | causal_gbm | 0.327682 | 1.111577 | -0.000070 |
| training_oof | grouped | 0.052018 | 1.020879 | 0.000121 |
| training_oof | latest | -0.019762 | 0.993668 | 0.000014 |
| training_oof | latest_metadata | 0.102027 | 1.040767 | 0.000078 |
| training_oof | singleton | 0.271900 | 1.084777 | 0.000032 |
| historical_test | grouped | 2.739018 | 1.158369 | -0.058082 |
| historical_test | latest | 1.269800 | 0.732686 | -0.054915 |
| historical_test | latest_metadata | 1.474806 | 0.799032 | -0.054957 |
| historical_test | singleton | 2.529422 | 1.089488 | -0.058419 |

## Paired event-level contrasts (negative favours the first arm)

Differences are in clipped log loss per event. Intervals:
- `event`: studentized bootstrap over events (B = 9,999);
- `t`: Student t;
- `mission`: mission-cluster bootstrap-t, which allows within-mission dependence;
- `above_floor`: repeated on events whose final log-risk is above the -30 floor.

| split | id | arm | comparator | events | positives | mean | event_lower | event_upper | mission_lower | mission_upper | missions | above_floor_events | above_floor_mean | above_floor_lower | above_floor_upper |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| training_oof | R1 | singleton | latest_metadata | 8293 | 66 | 0.003018 | 0.001346 | 0.004782 | 0.000571 | 0.006215 | 19 | 1455 | 0.014107 | 0.004575 | 0.023543 |
| training_oof | R2 | grouped | singleton | 8293 | 66 | 0.000342 | -0.000165 | 0.001327 | -0.000369 | 0.001235 | 19 | 1455 | -0.000382 | -0.002443 | 0.001712 |
| training_oof | R3 | latest_metadata | latest | 8293 | 66 | -0.000656 | -0.002761 | 0.001311 | -0.003068 | 0.001206 | 19 | 1455 | -0.000298 | -0.011908 | 0.010866 |
| training_oof | R4 | causal_gbm | latest_metadata | 8293 | 66 | -0.002286 | -0.004445 | -0.000310 | -0.004889 | 0.000074 | 19 | 1455 | -0.013873 | -0.025990 | -0.002935 |
| historical_test | R1 | singleton | latest_metadata | 2167 | 150 | 0.026307 | 0.011349 | 0.042525 | 0.004452 | 0.057576 | 18 | 494 | 0.115612 | 0.052067 | 0.185361 |
| historical_test | R2 | grouped | singleton | 2167 | 150 | -0.008731 | -0.031977 | -0.003171 | -0.045912 | -0.001608 | 18 | 494 | -0.038231 | -0.139366 | -0.013812 |
| historical_test | R3 | latest_metadata | latest | 2167 | 150 | -0.000044 | -0.010058 | 0.010126 | -0.014308 | 0.022266 | 18 | 494 | 0.000444 | -0.044543 | 0.045816 |

Leave-one-mission-out range of each contrast's mean:

| split | id | missions | mean_without_min | mean_without_max |
| --- | --- | --- | --- | --- |
| historical_test | R1 | 18 | 0.018516 | 0.032125 |
| historical_test | R2 | 18 | -0.009969 | -0.004454 |
| historical_test | R3 | 18 | -0.006537 | 0.002846 |
| training_oof | R1 | 19 | 0.002198 | 0.003838 |
| training_oof | R2 | 19 | 0.000071 | 0.000503 |
| training_oof | R3 | 19 | -0.001222 | -0.000163 |
| training_oof | R4 | 19 | -0.003055 | -0.001514 |

## Censoring

82.5% of training events have final log-risk at the -30 floor, which is
treated as censored. The binary label is unaffected because -30 lies far below
the -6 threshold, but these events dominate the loss averages. Every positive
lies above the floor. Floor share by mission:

| mission_id | events | positives | at_floor |
| --- | --- | --- | --- |
| 1 | 1333 | 10 | 1165 |
| 10 | 48 | 0 | 41 |
| 13 | 3 | 0 | 0 |
| 14 | 4 | 1 | 3 |
| 15 | 1292 | 11 | 1089 |
| 16 | 49 | 1 | 23 |
| 18 | 82 | 3 | 67 |
| 19 | 495 | 1 | 417 |
| 2 | 1153 | 13 | 972 |
| 20 | 19 | 2 | 8 |
| 22 | 11 | 0 | 4 |
| 23 | 13 | 0 | 4 |
| 24 | 13 | 0 | 8 |
| 3 | 331 | 9 | 253 |
| 4 | 201 | 5 | 154 |
| 5 | 1274 | 6 | 1039 |
| 6 | 558 | 3 | 400 |
| 7 | 1169 | 1 | 965 |
| 9 | 245 | 0 | 226 |

## Missed positives at the nominal 95% training-recall threshold

| split | arm | missed_at_95 |
| --- | --- | --- |
| historical_test | grouped | 6 |
| historical_test | latest | 9 |
| historical_test | latest_metadata | 8 |
| historical_test | singleton | 12 |
| training_oof | causal_gbm | 3 |
| training_oof | grouped | 3 |
| training_oof | latest | 3 |
| training_oof | latest_metadata | 3 |
| training_oof | singleton | 2 |

`missed_positives.csv` lists each missed event with its mission, latest risk,
final risk and q.

## Limits

- Exposed data: the training cohort shaped every development choice, and the
  historical test labels have long been public.
- Retrospective cohort selection uses future records (eligibility); see Report 1.
- Missions are few and unbalanced (19 in training). The mission-cluster interval
  has few clusters and treats missions as exchangeable.
- Public CDMs carry no observation lineage, so the simulation's reuse contrasts
  (P1) cannot be measured here. R1/R2 are absolute comparisons only.
