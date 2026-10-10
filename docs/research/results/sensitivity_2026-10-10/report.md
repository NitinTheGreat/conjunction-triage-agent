# V02 development sensitivity and independent training banks

Date: 10 October 2026. Source `sensitivity_20261010_v1`; summary `sensitivity_summary_20261010_v1`. **Exposed development
evidence generated under the committed [sensitivity contract](../../execution/sensitivity_contract.md).
The candidate scientific configuration and the scientific reservation were not
generated.** Decisions that use this evidence are recorded in
`docs/research/execution/analysis_specification.md`.

## Banks

Fresh development banks per configuration (training banks of
1,000, evaluation banks of 2,000 scenarios). The enriched
synthetic prevalence is not operational prevalence.

| configuration | role | banks | scenarios | positives | prevalence |
| --- | --- | --- | --- | --- | --- |
| aniso2 | evaluation | 1 | 2000 | 356 | 0.178000 |
| aniso2 | training | 2 | 2000 | 355 | 0.177500 |
| aniso8 | evaluation | 1 | 2000 | 254 | 0.127000 |
| aniso8 | training | 2 | 2000 | 296 | 0.148000 |
| bias | evaluation | 1 | 2000 | 622 | 0.311000 |
| bias | training | 2 | 2000 | 658 | 0.329000 |
| iso | evaluation | 1 | 2000 | 374 | 0.187000 |
| iso | training | 6 | 6000 | 1126 | 0.187667 |
| noise2 | evaluation | 1 | 2000 | 478 | 0.239000 |
| noise2 | training | 2 | 2000 | 506 | 0.253000 |

Selections at the upper C boundary, by configuration and arm (two banks per
configuration; six for `iso`):

| configuration | grouped | latest_metadata | oracle_lineage_weight | singleton |
| --- | --- | --- | --- | --- |
| aniso2 | 2 | 2 | 2 | 2 |
| aniso8 | 0 | 0 | 0 | 0 |
| bias | 1 | 1 | 2 | 0 |
| iso | 1 | 2 | 1 | 2 |
| noise2 | 0 | 2 | 0 | 0 |

## P1 on every independent training bank

P1 is the degradation of singleton relative to latest_metadata at 90% overlap,
evaluated on the configuration's own evaluation bank. Intervals are t-intervals
over evaluation scenarios, conditional on the fitted bank. `reuse_new_misses_arm`
counts positives missed under overlap but reviewed without reuse.

| training_configuration | training_bank | mean | se | lower95 | upper95 | reuse_new_misses_arm | positives |
| --- | --- | --- | --- | --- | --- | --- | --- |
| aniso2 | sens_aniso2_t1 | 0.077370 | 0.008784 | 0.060144 | 0.094596 | 21 | 356 |
| aniso2 | sens_aniso2_t2 | 0.079275 | 0.009021 | 0.061584 | 0.096966 | 23 | 356 |
| aniso8 | sens_aniso8_t1 | 0.064119 | 0.007565 | 0.049282 | 0.078955 | 17 | 254 |
| aniso8 | sens_aniso8_t2 | 0.054184 | 0.006669 | 0.041105 | 0.067262 | 16 | 254 |
| bias | sens_bias_t1 | 0.020031 | 0.004332 | 0.011536 | 0.028526 | 8 | 622 |
| bias | sens_bias_t2 | 0.020431 | 0.004287 | 0.012023 | 0.028839 | 13 | 622 |
| iso | sens_iso_t1 | 0.074355 | 0.008590 | 0.057509 | 0.091201 | 39 | 374 |
| iso | sens_iso_t2 | 0.051202 | 0.006659 | 0.038143 | 0.064261 | 20 | 374 |
| iso | sens_iso_t3 | 0.068967 | 0.007967 | 0.053343 | 0.084592 | 28 | 374 |
| iso | sens_iso_t4 | 0.070142 | 0.008284 | 0.053896 | 0.086388 | 35 | 374 |
| iso | sens_iso_t5 | 0.064762 | 0.008296 | 0.048492 | 0.081033 | 25 | 374 |
| iso | sens_iso_t6 | 0.063997 | 0.007987 | 0.048335 | 0.079660 | 30 | 374 |
| noise2 | sens_noise2_t1 | 0.043742 | 0.006535 | 0.030926 | 0.056558 | 25 | 478 |
| noise2 | sens_noise2_t2 | 0.052316 | 0.007327 | 0.037946 | 0.066686 | 21 | 478 |

## Persistence across configurations

Counts are training banks; margin 0.02 nats. Descriptive development
evidence: each configuration has only two banks except `iso`.

| training_configuration | id | estimand | banks | mean_min | mean_max | lower_above_margin | lower_above_zero | upper_below_zero | positives |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| aniso2 | P1 | degradation | 2 | 0.077370 | 0.079275 | 2 | 2 | 0 | 356 |
| aniso2 | S1 | absolute | 2 | -0.003441 | -0.001745 | 0 | 0 | 0 | 356 |
| aniso2 | S2 | degradation | 2 | -0.001632 | -0.001488 | 0 | 0 | 0 | 356 |
| aniso2 | S3 | degradation | 2 | 0.004225 | 0.006077 | 0 | 2 | 0 | 356 |
| aniso2 | S5 | degradation | 2 | 0.092795 | 0.094513 | 2 | 2 | 0 | 356 |
| aniso2 | S6 | absolute | 2 | 0.011774 | 0.013701 | 0 | 2 | 0 | 356 |
| aniso8 | P1 | degradation | 2 | 0.054184 | 0.064119 | 2 | 2 | 0 | 254 |
| aniso8 | S1 | absolute | 2 | -0.006579 | -0.000437 | 0 | 0 | 0 | 254 |
| aniso8 | S2 | degradation | 2 | 0.000880 | 0.001503 | 0 | 0 | 0 | 254 |
| aniso8 | S3 | degradation | 2 | 0.002217 | 0.004314 | 0 | 2 | 0 | 254 |
| aniso8 | S5 | degradation | 2 | 0.065110 | 0.078404 | 2 | 2 | 0 | 254 |
| aniso8 | S6 | absolute | 2 | 0.004347 | 0.013848 | 0 | 1 | 0 | 254 |
| bias | P1 | degradation | 2 | 0.020031 | 0.020431 | 0 | 2 | 0 | 622 |
| bias | S1 | absolute | 2 | -0.008761 | -0.007918 | 0 | 0 | 2 | 622 |
| bias | S2 | degradation | 2 | 0.000390 | 0.001959 | 0 | 0 | 0 | 622 |
| bias | S3 | degradation | 2 | 0.000180 | 0.001136 | 0 | 0 | 0 | 622 |
| bias | S5 | degradation | 2 | 0.029589 | 0.030714 | 0 | 2 | 0 | 622 |
| bias | S6 | absolute | 2 | 0.001522 | 0.001640 | 0 | 0 | 0 | 622 |
| iso | P1 | degradation | 6 | 0.051202 | 0.074355 | 6 | 6 | 0 | 374 |
| iso | S1 | absolute | 6 | -0.005885 | 0.004875 | 0 | 0 | 0 | 374 |
| iso | S2 | degradation | 6 | -0.002482 | 0.007573 | 0 | 1 | 0 | 374 |
| iso | S3 | degradation | 6 | -0.003221 | 0.005528 | 0 | 5 | 1 | 374 |
| iso | S5 | degradation | 6 | 0.059954 | 0.093215 | 6 | 6 | 0 | 374 |
| iso | S6 | absolute | 6 | 0.002867 | 0.023078 | 0 | 4 | 0 | 374 |
| noise2 | P1 | degradation | 2 | 0.043742 | 0.052316 | 2 | 2 | 0 | 478 |
| noise2 | S1 | absolute | 2 | -0.006758 | -0.001821 | 0 | 0 | 0 | 478 |
| noise2 | S2 | degradation | 2 | -0.002115 | 0.002077 | 0 | 0 | 0 | 478 |
| noise2 | S3 | degradation | 2 | 0.000858 | 0.003103 | 0 | 1 | 0 | 478 |
| noise2 | S5 | degradation | 2 | 0.054752 | 0.065570 | 2 | 2 | 0 | 478 |
| noise2 | S6 | absolute | 2 | 0.004251 | 0.011433 | 0 | 1 | 0 | 478 |

## Training-bank versus evaluation variance (`iso`, six independent banks)

Two-way random-effects decomposition of per-scenario contrasts (scenarios x
banks, one value per cell). `var_bank` is variation of the bank-level contrast
across independently generated training banks beyond scenario noise;
`var_interaction` is scenario-specific disagreement between banks.

| id | grand_mean | bank_means_sd | var_scenario | var_bank | var_interaction | bank_truncated | evaluation_se_one_bank_n2000 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P1 | 0.065571 | 0.007990 | 0.122447 | 0.000061 | 0.005166 | False | 0.011183 |
| S1 | 0.001030 | 0.004387 | 0.055295 | 0.000017 | 0.004587 | False | 0.006848 |
| S2 | 0.001170 | 0.003844 | 0.003606 | 0.000014 | 0.001997 | False | 0.004072 |
| S3 | 0.003054 | 0.003304 | 0.000787 | 0.000010 | 0.001461 | False | 0.003363 |
| S5 | 0.076755 | 0.011851 | 0.132731 | 0.000136 | 0.008171 | False | 0.014381 |
| S6 | 0.012214 | 0.008382 | 0.020615 | 0.000068 | 0.005257 | False | 0.008976 |

Projected standard error of the bank-averaged contrast for designs with K
independent training banks sharing n evaluation scenarios. `conditional_on_fit_se`
omits the bank component, so it describes those K fitted models rather than
the training procedure:

| id | independent_training_banks | evaluation_scenarios | projected_se | projected_half_width | conditional_on_fit_se |
| --- | --- | --- | --- | --- | --- |
| P1 | 1 | 2000 | 0.011183 | 0.021919 | 0.007988 |
| P1 | 1 | 5000 | 0.009315 | 0.018258 | 0.005052 |
| P1 | 3 | 2000 | 0.009083 | 0.017803 | 0.007879 |
| P1 | 3 | 5000 | 0.006727 | 0.013185 | 0.004983 |
| P1 | 5 | 2000 | 0.008602 | 0.016860 | 0.007857 |
| P1 | 5 | 5000 | 0.006078 | 0.011914 | 0.004970 |
| P1 | 10 | 2000 | 0.008222 | 0.016116 | 0.007841 |
| P1 | 10 | 5000 | 0.005542 | 0.010863 | 0.004959 |
| S2 | 1 | 2000 | 0.004072 | 0.007980 | 0.001674 |
| S2 | 1 | 5000 | 0.003860 | 0.007565 | 0.001059 |
| S2 | 3 | 2000 | 0.002594 | 0.005084 | 0.001461 |
| S2 | 3 | 5000 | 0.002334 | 0.004574 | 0.000924 |
| S2 | 5 | 2000 | 0.002181 | 0.004275 | 0.001415 |
| S2 | 5 | 5000 | 0.001886 | 0.003696 | 0.000895 |
| S2 | 10 | 2000 | 0.001811 | 0.003550 | 0.001379 |
| S2 | 10 | 5000 | 0.001462 | 0.002866 | 0.000872 |
| S3 | 1 | 2000 | 0.003363 | 0.006591 | 0.001060 |
| S3 | 1 | 5000 | 0.003261 | 0.006391 | 0.000670 |
| S3 | 3 | 2000 | 0.002008 | 0.003935 | 0.000798 |
| S3 | 3 | 5000 | 0.001910 | 0.003744 | 0.000505 |
| S3 | 5 | 2000 | 0.001605 | 0.003146 | 0.000735 |
| S3 | 5 | 5000 | 0.001501 | 0.002942 | 0.000465 |
| S3 | 10 | 2000 | 0.001219 | 0.002388 | 0.000683 |
| S3 | 10 | 5000 | 0.001098 | 0.002152 | 0.000432 |
| S6 | 1 | 2000 | 0.008976 | 0.017592 | 0.003597 |
| S6 | 1 | 5000 | 0.008532 | 0.016724 | 0.002275 |
| S6 | 3 | 2000 | 0.005807 | 0.011383 | 0.003344 |
| S6 | 3 | 5000 | 0.005198 | 0.010187 | 0.002115 |
| S6 | 5 | 2000 | 0.004935 | 0.009673 | 0.003291 |
| S6 | 5 | 5000 | 0.004226 | 0.008283 | 0.002082 |
| S6 | 10 | 2000 | 0.004163 | 0.008160 | 0.003251 |
| S6 | 10 | 5000 | 0.003315 | 0.006498 | 0.002056 |

## Transfer of `iso`-trained models

Mean over the iso training banks of each contrast on other configurations'
evaluation banks, next to models trained in that configuration.

| evaluation_configuration | id | transfer_mean | transfer_min | transfer_max | native_mean |
| --- | --- | --- | --- | --- | --- |
| aniso2 | P1 | 0.077323 | 0.064711 | 0.086365 | 0.078323 |
| aniso2 | S1 | -0.000816 | -0.006131 | 0.003124 | -0.002593 |
| aniso2 | S2 | -0.000199 | -0.003640 | 0.003649 | -0.001560 |
| aniso2 | S3 | 0.002553 | -0.003693 | 0.007212 | 0.005151 |
| aniso2 | S5 | 0.091212 | 0.075467 | 0.107233 | 0.093654 |
| aniso2 | S6 | 0.013072 | 0.004626 | 0.023991 | 0.012738 |
| aniso8 | P1 | 0.058745 | 0.050294 | 0.067235 | 0.059151 |
| aniso8 | S1 | 0.003288 | -0.003959 | 0.011718 | -0.003508 |
| aniso8 | S2 | -0.002986 | -0.010203 | 0.002219 | 0.001192 |
| aniso8 | S3 | 0.002735 | -0.005861 | 0.010592 | 0.003266 |
| aniso8 | S5 | 0.071599 | 0.060755 | 0.084271 | 0.071757 |
| aniso8 | S6 | 0.016143 | 0.006501 | 0.026209 | 0.009098 |
| bias | P1 | -0.131468 | -0.251991 | -0.035966 | 0.020231 |
| bias | S1 | 0.197348 | 0.152279 | 0.237939 | -0.008340 |
| bias | S2 | 0.025141 | 0.011597 | 0.049360 | 0.001174 |
| bias | S3 | 0.012418 | -0.022332 | 0.050381 | 0.000658 |
| bias | S5 | -0.189918 | -0.367606 | -0.048975 | 0.030152 |
| bias | S6 | 0.138898 | 0.036664 | 0.204526 | 0.001581 |
| iso | P1 | 0.065571 | 0.051202 | 0.074355 | 0.065571 |
| iso | S1 | 0.001030 | -0.005885 | 0.004875 | 0.001030 |
| iso | S2 | 0.001170 | -0.002482 | 0.007573 | 0.001170 |
| iso | S3 | 0.003054 | -0.003221 | 0.005528 | 0.003054 |
| iso | S5 | 0.076755 | 0.059954 | 0.093215 | 0.076755 |
| iso | S6 | 0.012214 | 0.002867 | 0.023078 | 0.012214 |
| noise2 | P1 | 0.105996 | 0.080776 | 0.123966 | 0.048029 |
| noise2 | S1 | -0.015600 | -0.031627 | -0.001776 | -0.004289 |
| noise2 | S2 | 0.008372 | -0.000421 | 0.022178 | -0.000019 |
| noise2 | S3 | 0.040188 | -0.090629 | 0.117747 | 0.001980 |
| noise2 | S5 | 0.164606 | 0.118613 | 0.189911 | 0.060161 |
| noise2 | S6 | 0.043009 | 0.017009 | 0.056582 | 0.007842 |

## Limits

- Static two-dimensional encounter-plane model; no orbital dynamics or OD
  validation. Configurations are design stresses, not measured sensor behavior.
- Two training banks per non-baseline configuration show direction and rough
  size only. Six banks give a coarse bank-variance estimate; negative moment
  estimates are truncated at zero and flagged.
- All banks here are exposed development data used to choose the V03 design.
- Same-workflow analysis, not independent A03 review.
