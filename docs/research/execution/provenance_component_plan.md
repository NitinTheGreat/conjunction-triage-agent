# Next V02 step: observable-provenance component ablations

Prepared 10 October 2026 while the fixed sequence campaign runs. **Design work
only; no component-ablation fit or scientific outcome access.** Read the audited
sequence results before fixing this next experiment's machine-readable contract.

## Question and separation of mechanisms

Determine whether any history behavior comes from grouping, age features, OD
features, or privileged knowledge of shared observations. A favorable sequence
or grouping score alone cannot identify which information helped. Preserve the
latest-metadata, singleton, fixed/time-only grouping, thinning, covariance-proxy
and sequence controls, including negative findings.

The present `research.history.partitions` uses the twelve OD fields and visible
publication-time gaps. It **does not use categorical age bins to form groups**.
Age bins enter the predictor through `phi`. Therefore an age-readout ablation
tests age information in the classifier, not an age-based grouping rule. Do not
describe it otherwise in the paper.

## Candidate factorial controls to fix before fitting

1. **Remove grouping:** reuse the audited singleton control. It has one partition
   per event; the grouped arm retains a maximum over its partition family.
   Include the existing fixed/time-only partition family to test the contribution
   of OD-based partition construction with the same available predictor fields.
2. **Remove categorical-age readout:** preserve OD-based partitions and remove
   both roles' eight age-bin feature columns, including the unknown bin. Keep
   the original canonical events, publication-time fields and grouping inputs.
   Do not replace missing age with a fabricated numeric midpoint.
3. **Remove OD readout only:** preserve original OD values solely for partition
   construction but remove their twelve predictor columns and corresponding
   missingness summaries. Name this limited intervention explicitly: OD still
   influences groups, so it is not a complete OD-information removal.
4. **Remove OD entirely:** use a time-only partition family and exclude the OD
   predictor/missingness columns. Compare with both the fixed/time-only control
   and the readout-only ablation. This distinguishes grouping inputs from
   classifier inputs. Keep dimensions/preprocessing choices explicit rather
   than silently reusing fitted coefficients.
5. **Oracle-lineage weighting control:** on simulation only, consider allocation
   of each unique visible observation equally among messages containing it.
   With visible union U and multiplicity m(i), message weight is
   `w(j) = sum(i in window(j), 1/m(i)) / |U|`. The weights sum to one and repeated
   copies divide their contribution. This is a descriptive oracle weighting
   rule, not a posterior fusion equation or proof of effective sample size.
   Retain the same predictor summaries/count definition as the unweighted
   comparator to isolate weights. Never expose observation identifiers or the
   condition name directly to the classifier.

This list is a proposed bounded design, not a completed or registered study.
Before execution, fix exact names, removed columns, family definitions, oracle
weight policy, tuning grid and failure policy. If an arm duplicates an existing
one, establish equality analytically and by construction tests and document the
reuse; do not invent a distinct label to inflate the comparison count.

## Construction and training requirements

- [ ] Audit the current full-report findings and choose the minimal component
  design that answers the remaining mechanism question; save a dated contract.
- [ ] Canonicalize full visible records before feature removal. Otherwise an
  ablation could change exact-replay deduplication as an unintended intervention.
- [ ] Test exact removed-column mappings, unknown/missing-age handling, and the
  distinction between OD readout removal and OD partition removal.
- [ ] Use label-free fixtures to demonstrate which design rows change and which
  remain identical. Include age-bin changes with identical OD values, equal OD
  values with changed time gaps, repeated solutions and new-information windows.
- [ ] For oracle weights, validate source lineage against canonical message
  order and publication availability; reject observation IDs 60–79, empty windows,
  invalid IDs and duplicates within a window. Test no-reuse, exact replay,
  solution reissue and unequal cumulative windows analytically. Mutating future
  observations must have no effect. Keep oracles separately labelled.
- [ ] Use the existing four scenario trials, two regimes and common folds;
  training-only imputation/scaling, scenario weight one and selected-OOF
  calibration/threshold limits remain. Save every candidate score, failure and
  fitted model. Preserve compatibility with all archived controls.
- [ ] Reconstruct all forecasts and paired loss/Brier/review/miss endpoints for
  every condition and bias bank; retain collapsed arms and negative findings.
- [ ] Export compact evidence, update the three reports and root checklist, and
  commit completed stages under the requested identity.

Implement new components in separate research modules where practical. Changing
shared historical feature code requires a narrow equivalence audit before reusing
old controls, and may invalidate their reuse. Keep raw data and frozen files
unchanged. No component runner exists at this planning checkpoint.

## Precision planning follows the component results

Review tuning adequacy before choosing a scientific comparator. Neural selections
at the maximum epoch budget and logistic selections at maximum C are not evidence
of optimal fitting. Use the saved OOF profiles and training-loss traces to decide
whether a further development-only, predeclared budget extension is necessary,
or whether the paper must explicitly restrict its comparison to these bounded
implementations. Do not infer that an entire model family is inferior from one
small fixed grid. Record the decision and compute tradeoff before V03.

After the complete development comparison, choose a defensible primary contrast
and practical effect/precision target. Use paired per-scenario variances and
positive counts, not the repeated prediction-row total or three overlapping
training subsets as independent sample size. Quantify uncertainty conditional on
fitted models separately from training-bank variation. Document the role of
enriched sampling and whether a proposed target distribution needs weighting.

Plan intervals/power for paired loss differences and positive-conditional miss
differences separately; workload and rare-event safety claims need different
denominators. Assess simulator anisotropy/noise sensitivity and runtime before
fixing a new scientific configuration. Existing software/bias/development banks
are exposed; any selection based on them is development. Scientific seed 20261012
and reserved IDs remain ungenerated until V03 freezes all choices. V02 stays
unchecked until both component and precision requirements are satisfied.
