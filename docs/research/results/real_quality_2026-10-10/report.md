# A01 addendum: OD-quality strata (post hoc, exploratory)

Run `real_quality_20261010_v1` from `real_retrospective_20261010_v1`. **Added after the main A01 results were
visible** to cover quality sensitivity, which the A01 contract omitted. Strata come
from each event's latest visible message:
- missing chaser OD fields;
- tertiles of chaser weighted RMS, with training cut points 1.599 and
  2.13 applied unchanged to the test split.

Differences are clipped log loss per event; negative favours the first arm.
Intervals are event-level studentized bootstraps for strata of at least 30 events.
Exposed evidence; nothing here is confirmatory.

| split | id | arm | comparator | stratum | events | positives | mean | lower | upper |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| training_oof | R1 | singleton | latest_metadata | rms tertile 1 | 2733 | 11 | 0.002260 | 0.000297 | 0.006128 |
| training_oof | R1 | singleton | latest_metadata | rms tertile 2 | 2957 | 22 | 0.002908 | 0.001182 | 0.005458 |
| training_oof | R1 | singleton | latest_metadata | rms tertile 3 | 2603 | 33 | 0.003940 | -0.000475 | 0.008062 |
| training_oof | R2 | grouped | singleton | rms tertile 1 | 2733 | 11 | 0.000058 | -0.000255 | 0.000542 |
| training_oof | R2 | grouped | singleton | rms tertile 2 | 2957 | 22 | 0.000556 | -0.000386 | 0.004742 |
| training_oof | R2 | grouped | singleton | rms tertile 3 | 2603 | 33 | 0.000397 | -0.000776 | 0.001920 |
| training_oof | R3 | latest_metadata | latest | rms tertile 1 | 2733 | 11 | -0.000251 | -0.002904 | 0.004233 |
| training_oof | R3 | latest_metadata | latest | rms tertile 2 | 2957 | 22 | -0.000681 | -0.004037 | 0.002318 |
| training_oof | R3 | latest_metadata | latest | rms tertile 3 | 2603 | 33 | -0.001053 | -0.006353 | 0.002520 |
| historical_test | R1 | singleton | latest_metadata | rms tertile 1 | 712 | 27 | 0.005498 | -0.021875 | 0.023638 |
| historical_test | R1 | singleton | latest_metadata | rms tertile 2 | 724 | 43 | 0.038076 | 0.015601 | 0.086645 |
| historical_test | R1 | singleton | latest_metadata | rms tertile 3 | 731 | 80 | 0.034920 | 0.001215 | 0.058423 |
| historical_test | R2 | grouped | singleton | rms tertile 1 | 712 | 27 | -0.001562 | -0.004037 | 0.000521 |
| historical_test | R2 | grouped | singleton | rms tertile 2 | 724 | 43 | -0.016588 | -0.174466 | -0.001333 |
| historical_test | R2 | grouped | singleton | rms tertile 3 | 731 | 80 | -0.007930 | -0.014136 | -0.002868 |
| historical_test | R3 | latest_metadata | latest | rms tertile 1 | 712 | 27 | 0.006244 | -0.013496 | 0.029891 |
| historical_test | R3 | latest_metadata | latest | rms tertile 2 | 724 | 43 | 0.010109 | -0.000466 | 0.022662 |
| historical_test | R3 | latest_metadata | latest | rms tertile 3 | 731 | 80 | -0.016224 | -0.036621 | -0.000662 |
