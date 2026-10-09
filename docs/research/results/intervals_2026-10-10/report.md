# Interval-method validation under right skew

Run `interval_validation_20261010_v1`. Development per-scenario contrasts from the reference training
trial (exposed banks). Each outer replicate draws n scenarios with replacement
from the 1,000 development values; the truth is their mean. `false_low_side` is
P(lower bound > truth) and `false_high_side` is P(upper bound < truth); each is
nominally 0.025. A confirmation decision uses the lower bound and a
"not material" decision the upper bound. The bootstrap-t uses 999 inner
resamples here; the scientific analysis would use more.

| id | skewness | method | n | outer_replicates | false_low_side | false_high_side | coverage | median_half_width | mc_se_one_side_at_nominal |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P1 | 4.476490 | t | 1000 | 4000 | 0.014500 | 0.042750 | 0.942750 | 0.020945 | 0.002469 |
| P1 | 4.476490 | bootstrap_t | 1000 | 4000 | 0.025000 | 0.029500 | 0.945500 | 0.021187 | 0.002469 |
| P1 | 4.476490 | percentile | 1000 | 4000 | 0.018750 | 0.039000 | 0.942250 | 0.020755 | 0.002469 |
| P1 | 4.476490 | t | 5000 | 1500 | 0.026667 | 0.040667 | 0.932667 | 0.009395 | 0.004031 |
| P1 | 4.476490 | bootstrap_t | 5000 | 1500 | 0.031333 | 0.034000 | 0.934667 | 0.009394 | 0.004031 |
| P1 | 4.476490 | percentile | 5000 | 1500 | 0.028667 | 0.038667 | 0.932667 | 0.009349 | 0.004031 |
| S1 | 3.415811 | t | 1000 | 4000 | 0.019250 | 0.031500 | 0.949250 | 0.015279 | 0.002469 |
| S1 | 3.415811 | bootstrap_t | 1000 | 4000 | 0.030750 | 0.032500 | 0.936750 | 0.015305 | 0.002469 |
| S1 | 3.415811 | percentile | 1000 | 4000 | 0.024250 | 0.033750 | 0.942000 | 0.015166 | 0.002469 |
| S1 | 3.415811 | t | 5000 | 1500 | 0.025333 | 0.022667 | 0.952000 | 0.006878 | 0.004031 |
| S1 | 3.415811 | bootstrap_t | 5000 | 1500 | 0.032000 | 0.023333 | 0.944667 | 0.006867 | 0.004031 |
| S1 | 3.415811 | percentile | 5000 | 1500 | 0.028667 | 0.024000 | 0.947333 | 0.006841 | 0.004031 |
| S6 | 4.924114 | t | 1000 | 4000 | 0.017000 | 0.043750 | 0.939250 | 0.009621 | 0.002469 |
| S6 | 4.924114 | bootstrap_t | 1000 | 4000 | 0.032250 | 0.024750 | 0.943000 | 0.009796 | 0.002469 |
| S6 | 4.924114 | percentile | 1000 | 4000 | 0.024500 | 0.039000 | 0.936500 | 0.009553 | 0.002469 |
| S6 | 4.924114 | t | 5000 | 1500 | 0.022000 | 0.030667 | 0.947333 | 0.004321 | 0.004031 |
| S6 | 4.924114 | bootstrap_t | 5000 | 1500 | 0.026667 | 0.025333 | 0.948000 | 0.004325 | 0.004031 |
| S6 | 4.924114 | percentile | 5000 | 1500 | 0.022667 | 0.028667 | 0.948667 | 0.004304 | 0.004031 |

Location equivariance makes these rates apply at any decision boundary reached by
shifting the distribution. They do not cover shape changes in an unseen
configuration.
