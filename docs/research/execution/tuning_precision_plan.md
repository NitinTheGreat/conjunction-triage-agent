# Next V02 step: tuning adequacy, precision and simulator sensitivity

Prepared 10 October 2026. This is a work plan, not a frozen scientific protocol
or a completed power analysis. The
[component audit](../results/components_2026-10-10/report.md) is complete and
inspected (`components_summary_20261010_v1`), so the decisions below can proceed.
Scientific seed 20261012 and IDs scientific:00000..04999 remain
reserved and ungenerated. V02 remains open.

## 1. Decide what the comparison can support

The completed campaign selection files already establish this starting inventory.
Counts concern selected models, not independent data or all candidate fits.

| Source run | Selected models | Upper grid selections |
|---|---:|---|
| tuning_20261009_v1 | 72 | 25 at C=1000 |
| covariance_20261009_v1 | 16 | 8 at C=1000 |
| components_20261010_v1 | 32 | 14 at C=1000 |
| sequence_20261010_v1 | 16 | 16 at 60 epochs; 8 at width 32 |

Thus 47 of 120 logistic selections reach maximum C. Read each run's
`selections.json` and `completion.json` for the underlying records. This boundary
inventory does not replace the profile, optimization and runtime analysis below.

- [x] Assemble one development inventory for the 17 class-forecast arms: exact
  fields, partition family, capacity, candidate grid, fit count, selected
  settings, fold scores, optimization diagnostics and runtime. Keep the six
  state-estimation arms separate: they have a different target and endpoints.
  **Expected:** a machine-readable inventory and readable tuning report linked
  to existing run manifests; no new fitting is necessary for this first step.
  **Evidence:** run `tuning_adequacy_20261010_v2`,
  [report](../results/tuning_adequacy_2026-10-10/report.md), `inventory.csv`,
  `fold_scores.csv` (1,128 rows; all candidates for 48 models, selected candidate
  for 88 whose runs kept only selected OOF). No fitting.
- [x] Inspect complete OOF candidate profiles and neural training-loss traces.
  Compare the best candidate with adjacent candidates, by training regime and
  subset. Count upper/lower grid selections separately from optimization failures.
  A converged optimizer at C=1000 can still have a limited hyperparameter search;
  reaching a fixed epoch budget is not itself a numerical failure. Flat profiles
  also do not establish equivalence without a stated practical tolerance.
  **Expected:** evidence for which settings are budget-sensitive and where the
  current evidence cannot answer that question.
  **Evidence:** `selection_adequacy.csv`, `paired_steps.csv`, `tolerance_counts.csv`,
  `neural_traces.csv` in the same bundle. Budget binds for no-reuse logistic
  (40/60 at C=1000) and both LSTM regimes; not materially for matched logistic
  (7/60, largest last-step gain 0.000622). Unanswerable from saved artifacts:
  whether wider budgets would change evaluation rankings.
- [x] Record a dated decision: restrict the paper to the declared bounded
  implementations, or perform a further development-only budget extension.
  If extending, commit the candidate grid, included comparator families, folds,
  seeds, failure policy and compute budget before fitting. Apply a consistent
  opportunity to relevant controls; do not expand only a favored method.
  **Expected:** an explicit claim boundary and rationale, not a claim that an
  entire model family has been optimized or disproved.
  **Evidence:** [tuning decision, 10 October 2026](tuning_decision.md): restrict
  to the declared bounded implementations, with regime-specific claim boundaries;
  no extension now. It is reopened if §2 picks a contrast depending on no-reuse
  training or an LSTM arm.

The current direction remains a controlled robustness benchmark. Do not promote
grouping, feature removal, oracle weighting or a neural adaptation to a superior
method merely because one exposed condition has favorable loss. Retain latest
metadata, singleton and ignore-updates in the interpretation. Privileged lineage
weighting is a diagnostic and cannot be the deployable primary method.

## 2. Specify the scientific question before calculating its sample size

- [ ] Choose one primary paired contrast, evaluation distribution and estimand,
  based openly on development evidence. State whether it concerns absolute
  forecast loss or a difference in degradation relative to no reuse. Keep both
  visible in secondary reporting. Fix the reuse condition, training regime,
  target population, clipping and practical effect/precision target.
  **Expected:** a proposed claim with an explicit null/adverse outcome that
  would lead to narrowing or stopping; no outcome-dependent rule to switch the
  primary contrast after opening the scientific bank.
- [ ] Inventory scenario-paired endpoint differences from audited predictions.
  Record case IDs, sample size, mean, standard deviation, positive count and
  paired review/miss discordance counts. Recompute these from per-scenario data
  and reconcile with the component/sequence contrast exports.
  **Expected:** a reproducible planning input table. Repeated conditions, model
  predictions and the three overlapping training subsets do not enlarge the
  number of independent evaluation scenarios.
- [ ] Calculate sample-size/precision sensitivity for the chosen loss contrast
  across several practical targets. Treat miss differences separately using
  positive cases and paired discordance; a nominal training recall threshold
  is not a scientific miss guarantee. Verify statistical methods against primary
  methodological sources when implementing the calculation. Include conservative
  alternatives when sparse discordance makes an asymptotic approximation poor.
  **Expected:** a quantitative planning report, assumptions and reproducible
  calculations, with infeasible targets retained rather than silently relaxed.

The earlier 20% review-reduction and one-percentage-point miss-difference targets
belong to conditional Track E. They are not automatic requirements or established
effects for this synthetic Track R benchmark. Synthetic stress cohorts are
enriched and unweighted; their review rates are not operational workload. If a
different target population is intended, specify its sampling/weighting design
and resulting precision before using such language.

## 3. Separate evaluation uncertainty from training and threshold uncertainty

- [ ] State whether inference is conditional on one fitted model or averages
  over independently generated training banks. If the latter is necessary,
  specify independent development training seeds, repetitions and runtime before
  generating them; the existing 800-scenario subsets overlap within one bank.
  **Expected:** a variance decomposition/design rationale and an honest statement
  of which uncertainty the eventual intervals include.
- [ ] Decide how selection, monotone calibration and threshold fitting will be
  separated in the scientific design. Current selected OOF reuse is exploratory;
  retaining it requires an explicit limitation. Risk certification needs its
  own valid calibration design and sample-size argument.
  **Expected:** an information-flow diagram or table, fixed split roles and tests
  that future evaluation labels cannot change model or threshold decisions.
- [ ] Define primary versus secondary comparisons, multiplicity handling,
  missing/failed fits, interval construction and reporting of unfavorable
  results. Preserve all prespecified arms and conditions in the final exports.
  **Expected:** a draft analysis specification suitable for V03, not only a list
  of significant comparisons selected from the development tables.

## 4. Check simulator sensitivity without consuming the scientific reservation

- [ ] Design a small, explicitly exposed development grid covering covariance
  anisotropy/rotation, observation noise and shared bias. Check positive-definite
  covariance and reference integration accuracy analytically/numerically before
  model comparisons. The previously suggested anisotropy 4 / rotation 30 degrees
  is a candidate, not a frozen setting.
- [ ] Estimate runtime and storage from existing manifests, run a limited timing
  check where needed, and commit a bounded development sensitivity contract.
  Use fresh development names/seeds; never scientific seed 20261012.
- [ ] Report which conclusions persist, reverse or remain uncertain across that
  grid. Keep the static two-dimensional simulator's physical limitations visible.
  Do not describe synthetic robustness as validated orbital or operational safety.

**Expected:** sensitivity results with full provenance, numerical checks and a
decision about the final configuration. Merely drafting this grid does not finish
the V02 sensitivity requirement.

## 5. Handoff and acceptance

- [ ] Save the tuning decision, precision report, sensitivity results and proposed
  scientific contrast; update all three reports, manuscript and root checklist.
- [ ] Check V02 only when its acceptance criteria are satisfied. Then prepare a
  reviewable V03 protocol with exact source/configuration hashes, sample sizes,
  seeds, endpoints and failure rules. Keep A03 independent review distinct from
  same-workflow artifact reconstruction.
- [ ] Commit each completed stage under the requested author/committer identity;
  keep checkpoints, full predictions and machine-specific logs local.

Start by inspecting existing artifacts; do not refit completed campaigns. The
verification command already exists:

```powershell
.\.venv\Scripts\python.exe -m research.verify_exports --root docs/research/results
```

The §1 tuning inventory now exists and has run (use a new run ID and export
path for any rerun; both `tuning_adequacy_20261010_v1` and `_v2` exist):

```powershell
.\.venv\Scripts\python.exe -m research.tuning_adequacy --run-id <new_id> --export docs/research/results/<new_bundle>
```

No precision or sensitivity CLI exists yet (§2-§4). Implement one only after
checking the exported schemas and fixing its calculations; do not invent a
command in a handoff. For another machine, transfer the ignored
source run directories and input data as described in the root checklist.
