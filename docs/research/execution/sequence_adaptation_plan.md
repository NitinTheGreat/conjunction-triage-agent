# Completed V02 step: a bounded sequence-family adaptation

Prepared 9 October 2026. **Completed and audited 10 October 2026: 304 fits, 16 selected models and 224,000 new forecasts.**
See [results](../results/sequence_2026-10-10/report.md) and [verification](sequence_verification.json).
See [fixed implementation contract](sequence_contract.md) and [synthetic evidence](sequence_preflight.json).
This follows the [V01 compatibility decision](closest_work_comparison.md).
It adapts an accessible LSTM family to the final recorded-risk class; it will not
reproduce Pinto's next-message MSE experiment or establish state-of-the-art status.

## Start with the environment and compute budget

Before the 9 October preflight, `importlib.util.find_spec('torch')` returned
`None`. PyTorch 2.14.1+cpu is now installed through the separate
`requirements-sequence.txt`; the historical requirements file is unchanged.
Official Windows/Python compatibility, exact wheel hashes, package versions and
installation/verification commands are recorded in the linked preflight and
contract. Preserve those records and the frozen files when reproducing this run.
No paid inference or GPU service was used.

Before using study labels, run a tiny synthetic tensor/masking benchmark to
estimate runtime. Then record architecture, optimizer, grid, epochs, precision,
seeds and failure policy in a dated implementation contract. Prefer a fixed-epoch
grid to avoid another early-stopping split. If early stopping is introduced, its
validation cases must come from the fitting portion of each inner fold, not the
inner-OOF cases later used for calibration. Do not choose the budget from exposed
evaluation performance or call equal candidate counts equal compute cost.

## Proposed comparison and boundaries

Implement two input-matched arms: a history LSTM and the same LSTM family given
only the latest visible message. The latter helps separate nonlinear readout
capacity from historical information. Keep the existing latest-metadata,
singleton, grouping, thinning and covariance-proxy controls in the result tables.
Name the smaller capacity and changed final-class loss explicitly; no published
headline score transfers to this task.

Use the common visible allowlist, exact-replay canonicalization, chronological
ordering and training-only preprocessing. Preserve missingness and categorical
age semantics. Mask padding in the recurrent calculation/readout, not merely in
the final loss. No event identifier, final-risk label, future message, total
future message count or oracle observation ID may enter a feature tensor.

Retain the same exposed scenario subsets and whole-scenario folds across both
regimes and both new arms. A scenario contributes one total objective unit even
when represented by several history variants. Tune each arm within those folds,
then use its selected OOF scores for the existing monotone calibration and
nominal threshold procedure. Record that calibration/threshold reuse and its
limits; no risk guarantee follows. Model initialization/minibatch seeds and
determinism settings must be saved because these fits are stochastic.

Use the previous model results only when their source inputs, folds and budgets
remain compatible. Never give only the proposed history method more trials or
select a favorable seed. Distinguish the full-data reference from the three
overlapping 800-scenario subsets. Retain all bias/reuse/new-information conditions.

## Acceptance checklist

- [x] Record an exact compatible local dependency version and pass an import,
  tensor and deterministic CPU smoke test without touching study outcomes.
- [x] Run the synthetic timing benchmark and commit the fixed training/budget
  contract before the first study fit. Record how its tuning budget differs
  from the logistic family, even if candidate counts match.
- [x] Implement history and latest-only tensor construction, chronological
  ordering, padding masks and training-only preprocessing.
- [x] Test padding invariance, exact replay/order invariance, future-message
  mutations, loss weighting, finite outputs, deterministic evaluation, and
  separation of fit/OOF/calibration cases. Save model metadata and checkpoints
  without pickling unaudited third-party source.
- [x] Complete the declared regime/trial grid, save candidate OOF scores,
  selected models, seeds, thresholds, failures and per-fit runtime. Do not
  silently omit failed configurations or call partial output a completed study.
- [x] Reconstruct predictions and compare paired absolute/degradation loss,
  Brier score and review/miss counts with all applicable saved controls. Keep
  adverse bias results, training sensitivity and capacity limitations explicit.
- [x] Export compact evidence, update reports/manuscript/handoff, and commit
  completed stages using the requested identity. Leave the scientific bank
  unopened and V02 unchecked until remaining criteria pass.

After this adaptation, complete observable-provenance component ablations and
precision planning. State-fusion/oracle diagnostics do not replace those class
forecasting experiments. The campaign `sequence_20261010_v1` and reconstruction
`sequence_summary_20261010_v1` are complete. Exact commands and limitations are
in [V02 development](v02_development.md). These run IDs are exclusive; do not
rerun them or overwrite their artifacts. Next follow the
[observable-provenance component plan](provenance_component_plan.md), then resolve
tuning adequacy and precision. All 16 neural selections hit the epoch ceiling;
eight hit maximum width. Scientific outcomes remain reserved and ungenerated.
