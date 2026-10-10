# Track R scientific evaluation (V04)

Run `track_r_scientific_20261010_v1`, reported by `track_r_report_20261010_v1`. **Confirmatory evaluation under the frozen
protocol** ([protocol](../../execution/track_r_protocol.json), canonical SHA-256
`69040e6bcf48416541a712250f3463c136b1b0e27fa513c4c650751fd30d13ca`), in the held-out simulator configuration (noise variance ratio 4
rotated 30 degrees). There are 10 independent training banks of
1,000 scenarios and 5,000 evaluation scenarios.
This is a controlled static encounter-plane simulation: not orbital validation,
not operational evidence, and never pooled with the retrospective real-data (A01)
results. The user authorized the run, and the pre-run independent analysis check
was waived ([authorization](../../execution/track_r_authorization.json)).

Integrity checks:
- the unlabelled predictions match their phase-2 commit hash;
- every result in `analysis.json` reconstructs exactly from the labelled
  predictions, using the frozen functions and seeds.

## Primary result (P1)

**Decision: material degradation confirmed.**

| Quantity | Value |
|---|---|
| Estimate (mean over 10 banks x 5,000 scenarios) | 0.062764 |
| Bank-combined 95% interval (frozen) | [0.052596, 0.073727] |
| Margin | 0.02 |
| Scenario-only bootstrap-t interval (conditional on these fits; sensitivity) | [0.053436, 0.072952] |
| Student t interval (scenario component; sensitivity) | [0.053119, 0.072409] |
| Bank SE / scenario SE | 0.001789 / 0.004920 |
| One-sided p (H0: P1 <= 0.02) | 0.0001 |

The rule was: confirm if the lower bound exceeds the margin, not material if the
upper bound falls below it, otherwise inconclusive.

## Confirmatory secondary family (Holm, one-sided familywise 0.05)

| id | arm | comparator | condition | estimand | null | mean | lower | upper | p_value | holm_rejected |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S1 | singleton | latest_metadata | overlap_90 | absolute | -0.020000 | -0.003871 | -0.010535 | 0.003514 | 0.000100 | True |
| S2 | grouped | singleton | overlap_90 | degradation | -0.010000 | 0.000680 | -0.001248 | 0.002611 | 0.000100 | True |
| S3 | oracle_lineage_weight | singleton | overlap_90 | degradation | -0.010000 | 0.002275 | 0.000058 | 0.004540 | 0.000100 | True |
| S5 | singleton | latest_metadata | solution_reissue | degradation | 0.020000 | 0.077262 | 0.065776 | 0.089697 | 0.000100 | True |

## Exploratory

| id | arm | comparator | condition | estimand | mean | lower | upper | scenario_lower | scenario_upper |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S6 | singleton | latest_metadata | solution_reissue | absolute | 0.010627 | 0.005017 | 0.016581 | 0.006548 | 0.015168 |

Reuse-induced misses for the history arm (positives missed under 90% overlap but
reviewed without reuse), pooled over banks: 599 new and
33 recovered among 7,700 positive
bank-scenario pairs. The new-miss rate is 0.0778, with an
exact 95% interval of [0.0719, 0.0840] and an
exact McNemar p of 1.55e-135. Banks share scenarios, so the pooled count
is descriptive.

## Prespecified diagnostics

- **Integration check** (label-free) on the scientific noise covariance: worst
  relative difference 1.75e-07.
- **Grid-edge selections** (C = 1000; a search limit, not a failure):
  18 of 40 models.
  The largest observed iteration count was 269 against a cap of
  10,000.

## Absolute losses (mean over banks and scenarios)

The enriched stress population is unweighted; review fractions are not
operational workload.

| arm | condition | rows | banks | mean_log_loss | brier | roc_auc | mean_review_fraction | miss_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| grouped | new_information | 50000 | 10 | 0.047818 | 0.014453 | 0.997672 | 0.161560 | 0.043117 |
| grouped | no_reuse | 50000 | 10 | 0.081882 | 0.023977 | 0.994514 | 0.199200 | 0.016623 |
| grouped | overlap_90 | 50000 | 10 | 0.145326 | 0.045831 | 0.976157 | 0.197180 | 0.094545 |
| grouped | solution_reissue | 50000 | 10 | 0.159901 | 0.050669 | 0.971819 | 0.199900 | 0.102727 |
| latest_metadata | new_information | 50000 | 10 | 0.042151 | 0.013192 | 0.997934 | 0.169700 | 0.022208 |
| latest_metadata | no_reuse | 50000 | 10 | 0.148566 | 0.048523 | 0.972807 | 0.227360 | 0.047013 |
| latest_metadata | overlap_90 | 50000 | 10 | 0.148566 | 0.048523 | 0.972807 | 0.227360 | 0.047013 |
| latest_metadata | solution_reissue | 50000 | 10 | 0.148566 | 0.048523 | 0.972807 | 0.227360 | 0.047013 |
| oracle_lineage_weight | new_information | 50000 | 10 | 0.045483 | 0.013939 | 0.997831 | 0.162560 | 0.041688 |
| oracle_lineage_weight | no_reuse | 50000 | 10 | 0.079990 | 0.023341 | 0.995015 | 0.200980 | 0.013766 |
| oracle_lineage_weight | overlap_90 | 50000 | 10 | 0.145029 | 0.045845 | 0.976328 | 0.201220 | 0.086104 |
| oracle_lineage_weight | solution_reissue | 50000 | 10 | 0.159637 | 0.050737 | 0.971739 | 0.201800 | 0.098831 |
| singleton | new_information | 50000 | 10 | 0.047060 | 0.014419 | 0.997640 | 0.164240 | 0.037792 |
| singleton | no_reuse | 50000 | 10 | 0.081931 | 0.024015 | 0.994602 | 0.201700 | 0.013896 |
| singleton | overlap_90 | 50000 | 10 | 0.144695 | 0.045900 | 0.976119 | 0.201180 | 0.087403 |
| singleton | solution_reissue | 50000 | 10 | 0.159193 | 0.050878 | 0.971647 | 0.205360 | 0.090779 |

Full per-arm, per-condition and per-bank tables, calibration and per-bank
contrasts are in the bundle.

## Post-hoc coverage check (not part of the decision)

Designs simulated from the observed scientific P1 components (bank SD
0.005562, scenario variance 0.120485) with 400 replicates:

| method | banks | scenarios | replicates | false_low_side | false_high_side | coverage | median_half_width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| bank_combined | 10 | 5000 | 400 | 0.027500 | 0.017500 | 0.955000 | 0.010418 |
| scenario_only | 10 | 5000 | 400 | 0.042500 | 0.027500 | 0.930000 | 0.009644 |

## Limits

- **Simulator:** static two-dimensional encounter-plane model with a synthetic
  label (final reported-risk class), not collision occurrence.
- **Implementations:** bounded logistic implementations, a declared C grid and
  selected-OOF calibration reuse; no risk certification.
- **Review:** the independent pre-run check was waived; the A03 independent
  review is still required.
