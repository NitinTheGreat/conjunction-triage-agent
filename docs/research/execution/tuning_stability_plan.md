# V02 common-grid and training-subset sensitivity plan

Recorded 9 October 2026 before the expanded-grid outcomes. This is a development
plan informed by prior pilot results, not a registered scientific protocol.

- Keep all nine predictors and both existing training regimes.
- Use the same C grid for every fit: 0.01, 0.1, 1, 10, 100, 1000.
- Use three inner whole-scenario folds, training-only preprocessing, and the
  existing inner-OOF calibration/threshold procedure.
- Increase the common optimizer cap to 10,000 iterations. A convergence warning
  fails the run; do not silently drop a candidate, predictor or seed.
- Reference trial: all 1,000 development scenarios, seed 20261022, matching the
  preceding regime experiment's fold seed.
- Sensitivity trials: seeds 20261031, 20261032 and 20261033, each selecting 80%
  within each development class without replacement (800 scenarios/144 positives).
  Use the same selected scenarios and folds across predictors and regimes.
- Keep total objective weight one per selected scenario. Variants remain in the
  same fold. Repeated subsets do not create new independent positives.
- Evaluate every fit on the same exposed software/bias banks and seven conditions.
  Preserve exact replay and matched-latest-input checks.

The planned campaign has 72 selected models and 1,008,000 prediction rows. Full
OOF candidate scores, selected C, folds, models, thresholds and convergence
diagnostics must be retained. Source/run hashes precede fitting.

Report the full-data grid change separately from variability among the three
equal-size subsets. Report ranges and paired differences, not a confidence
interval inferred from three overlapping training sets. This studies sensitivity
to scenario membership and tuning folds; it is neither independent training-bank
replication nor optimizer randomness. The three subsets have correlated data.

Compare all losses and review/miss counts, including unfavorable findings. Count
remaining grid-boundary selections; do not declare optimal tuning merely because
the grid was expanded. Do not select a primary scientific condition from whichever
development comparison looks best. Scientific seed 20261012 and reserved
scenarios stay unopened. V02 comparator/ablation/precision work remains pending.
