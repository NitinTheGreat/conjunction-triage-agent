# Bank-combined interval validation

Run `bank_interval_validation_20261010_v1` from `sensitivity_20261010_v1` (`iso` own-configuration predictions,
six independent training banks). Designs are simulated from the measured
components: empirical scenario effects, normal bank effects with the moment SD,
and empirical interaction residuals. The truth is the development grand mean.
Nominal error is 0.025 per side; Monte Carlo SE about 0.005 at 1,000 replicates.

| id | banks | scenarios | grand_mean | bank_sd | var_scenario | var_interaction |
| --- | --- | --- | --- | --- | --- | --- |
| P1 | 6 | 2000 | 0.065571 | 0.007827 | 0.122447 | 0.005166 |
| S2 | 6 | 2000 | 0.001170 | 0.003712 | 0.003606 | 0.001997 |
| S6 | 6 | 2000 | 0.012214 | 0.008224 | 0.020615 | 0.005257 |

| id | method | banks | scenarios | replicates | false_low_side | false_high_side | coverage | median_half_width |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P1 | bank_combined | 10 | 5000 | 1000 | 0.021000 | 0.017000 | 0.962000 | 0.011210 |
| P1 | scenario_only | 10 | 5000 | 1000 | 0.036000 | 0.035000 | 0.929000 | 0.009729 |
| P1 | bank_combined | 5 | 5000 | 1000 | 0.018000 | 0.016000 | 0.966000 | 0.013345 |
| P1 | scenario_only | 5 | 5000 | 1000 | 0.053000 | 0.047000 | 0.900000 | 0.009739 |
| P1 | bank_combined | 10 | 2000 | 1000 | 0.027000 | 0.022000 | 0.951000 | 0.016413 |
| P1 | scenario_only | 10 | 2000 | 1000 | 0.037000 | 0.030000 | 0.933000 | 0.015406 |
| S2 | bank_combined | 10 | 5000 | 1000 | 0.019000 | 0.018000 | 0.963000 | 0.003130 |
| S2 | scenario_only | 10 | 5000 | 1000 | 0.136000 | 0.115000 | 0.749000 | 0.001755 |
| S2 | bank_combined | 5 | 5000 | 1000 | 0.021000 | 0.018000 | 0.961000 | 0.004640 |
| S2 | scenario_only | 5 | 5000 | 1000 | 0.183000 | 0.157000 | 0.660000 | 0.001805 |
| S2 | bank_combined | 10 | 2000 | 1000 | 0.025000 | 0.025000 | 0.950000 | 0.003857 |
| S2 | scenario_only | 10 | 2000 | 1000 | 0.072000 | 0.080000 | 0.848000 | 0.002797 |
| S6 | bank_combined | 10 | 5000 | 1000 | 0.024000 | 0.020000 | 0.956000 | 0.006986 |
| S6 | scenario_only | 10 | 5000 | 1000 | 0.117000 | 0.100000 | 0.783000 | 0.004097 |
| S6 | bank_combined | 5 | 5000 | 1000 | 0.017000 | 0.022000 | 0.961000 | 0.010171 |
| S6 | scenario_only | 5 | 5000 | 1000 | 0.170000 | 0.158000 | 0.672000 | 0.004134 |
| S6 | bank_combined | 10 | 2000 | 1000 | 0.018000 | 0.020000 | 0.962000 | 0.008718 |
| S6 | scenario_only | 10 | 2000 | 1000 | 0.059000 | 0.061000 | 0.880000 | 0.006510 |

`scenario_only` is the bootstrap-t on bank-averaged contrasts without the bank
term, that is, inference conditional on the fitted banks. Normal bank effects
are an assumption; six development banks cannot check their shape.
