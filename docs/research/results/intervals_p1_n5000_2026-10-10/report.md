# Interval-method validation under right skew

Run `interval_validation_20261010_v2`. Development per-scenario contrasts from the reference training
trial (exposed banks). Each outer replicate draws n scenarios with replacement
from the 1,000 development values; the truth is their mean. `false_low_side` is
P(lower bound > truth) and `false_high_side` is P(upper bound < truth); each is
nominally 0.025. A confirmation decision uses the lower bound and a
"not material" decision the upper bound. The bootstrap-t uses 999 inner
resamples here; the scientific analysis would use more.

| id | skewness | method | n | outer_replicates | false_low_side | false_high_side | coverage | median_half_width | mc_se_one_side_at_nominal |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P1 | 4.476490 | t | 5000 | 4000 | 0.020500 | 0.034000 | 0.945500 | 0.009396 | 0.002469 |
| P1 | 4.476490 | bootstrap_t | 5000 | 4000 | 0.026000 | 0.028750 | 0.945250 | 0.009378 | 0.002469 |
| P1 | 4.476490 | percentile | 5000 | 4000 | 0.023500 | 0.034000 | 0.942500 | 0.009339 | 0.002469 |

Location equivariance makes these rates apply at any decision boundary reached by
shifting the distribution. They do not cover shape changes in an unseen
configuration.
