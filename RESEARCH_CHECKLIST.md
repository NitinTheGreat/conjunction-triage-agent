# Research execution checklist and assistant handoff

**Project:** ConjunctionTriage  
**Created:** 6 October 2026; **last checkpoint:** 10 October 2026
**Purpose:** carry the project from the research reports to a defensible paper, with work resumable by Codex, Claude Code, or another coding assistant using this file and the repository.

This is the live execution record. Update it as work happens. Checked preparation tasks describe work already evidenced in the repository; unchecked implementation and experiment tasks remain to be done. A completed task can produce a negative or inconclusive finding. A checkbox does not mean that the proposed method succeeded or that a paper is accepted.

## 1. Resume here

| Field | Current checkpoint — replace after each work session |
|---|---|
| NOW | **A01 COMPLETE** (exposed retrospective real-CDM analysis). V03 is frozen (`8903632`). V04 is still awaiting user authorization and an independent analysis check. |
| NEXT | **USER DECISION REQUIRED before V04:** (1) authorize generating and evaluating the reserved scientific banks (irreversible: it consumes the holdout); (2) arrange an independent check of the frozen decision rule on boundary-null and zero-discordance cases, or record an explicit waiver. Then run V04 with the command below. |
| Active task / owner | V04 BLOCKED on user authorization (by design). A02 can be drafted for every claim except the V04 outcome; A03, W02-W04 follow V04. |
| Selected direction | **Track R, narrowed:** controlled robustness/measurement benchmark. Grouping remains a candidate and may be discarded if simpler controls explain results. |
| Conditional extension | **Track E:** independent real-data efficacy, only after access and statistical requirements pass. |
| Research blockers | None preventing V01/V02 preparation. Full methods for some close papers and independent operational data remain unavailable; no novelty or real efficacy claim is established. |
| Current machine | Windows, PowerShell; repository at `F:\conjunction-triage`; Python environment at `.venv\Scripts\python.exe`. Paths elsewhere in this file are relative to the repository root. |
| HEAD when this checklist was created | `89d7f2efb8bf135e02fa51760e0ed3bb33a105c9`; working tree contains pre-existing modifications and untracked files. |
| Latest validation | After freeze: full suite 479 passed / 1 skipped (111.72 s). 13 bundles / 105 artifacts pass. 12 raw, 45 historical and 8 frozen files unchanged. Frozen protocol accepted by the runner. |
| New scientific runs | Development runs this session: tuning_adequacy_20261010_v2, precision_planning_20261010_v2, interval_validation_20261010_v1/v2, sensitivity_preflight_20261010_v1, sensitivity_20261010_v1, sensitivity_summary_20261010_v1 and bank_interval_validation_20261010_v1. No frozen scientific evaluation. |
| Scientific holdout status | Seed 20261012 / scientific:00000..04999 reserved **but not generated**. Training-bank seeds 20261301-20261310 and the `scitrain` prefix are also reserved in code. Candidate configuration: ratio 4, rotated 30 degrees (unexposed). Kelvins and all development banks are exposed. |
| Running jobs / processes | None for this project. |
| Next executable command | After authorization only: `.\.venv\Scripts\python.exe -m research.track_r_scientific --run-id track_r_scientific_20261010_v1`, with LOKY_MAX_CPU_COUNT, OMP_NUM_THREADS and MKL_NUM_THREADS set to 2. Expected runtime 45-75 min. |

### Copy this into the next assistant

```text
Read RESEARCH_CHECKLIST.md in this repository, starting with "Resume here".
Continue the first ready unchecked task, respecting its dependencies and the
current checkpoint. Use the linked reports for scientific details. Inspect
the existing work and artifacts before implementing or rerunning anything.
Preserve pre-existing changes, raw data, frozen files, and historical outputs.
Complete a useful bounded task, run the relevant checks, and update this file
with evidence paths, commands, results, and the exact next step. Mark a task
complete only when its acceptance criteria pass. If interrupted, record the
partial state and any active process/run IDs. Continue authorized local work
without asking me to repeat the project history. Record new instructions or
decisions here so the following assistant can resume from disk.
```

Use that same prompt when switching assistants in the same folder. If moving to a new machine or checkout, complete the transfer checklist in section 9 first. The chat transcript is useful background; the files and saved artifacts must be sufficient to resume.

## 2. Read the right source, then act

| Source | Read it for |
|---|---|
| [Report 1 — evidence audit](docs/research/2026-10-06/01_EVIDENCE_AUDIT_AND_CURRENT_RESULTS.md) | What is measured, superseded, incomplete, or unavailable; raw-data overlap and acquisition requirements. |
| [Report 2 — experiments and analysis](docs/research/2026-10-06/02_PUBLICATION_EXPERIMENTS_AND_ANALYSIS_PLAN.md) | Method definitions, folds, calibration, simulator, estimands, statistical rules, and artifact schemas. |
| [Report 3 — paper roadmap](docs/research/2026-10-06/03_RESEARCH_DIRECTION_AND_PAPER_ROADMAP.md) | Novelty, ten-day pilot, route decisions, manuscript structure, figures, and venue fit. |
| [Deep literature review](docs/research/2026-10-06/_support/DEEP_LITERATURE_REVIEW.md) | Closest papers, access limits, and what must be compared before making novelty claims. |
| [Primary source ledger](docs/research/2026-10-06/_support/primary_source_ledger.json) and [bibliography](docs/research/2026-10-06/_support/references.bib) | Verified identities and evidence levels; a starting bibliography, not a complete final manuscript bibliography. |
| [Methods-source notes](docs/research/2026-10-06/_support/deep_methods_sources.md) | Statistical assumptions and distinctions between calibration, risk certification, and efficacy. |
| [Data-source notes](docs/research/2026-10-06/_support/deep_data_sources.md) | Public versus request-only data, field semantics, and unresolved access questions. |
| [Earlier verification record](docs/research/2026-10-06/_support/verification_record.json) | Exact historical commands, test outcomes, and Windows CPU-detection workaround. |
| [Frozen manifest](docs/PHASE7_FROZEN_MANIFEST.md) and [Phase 11 erratum](docs/PHASE11_ERRATUM.md) | Files to preserve and claims that cannot support the new paper. |

At a fresh handoff, read this file and the relevant report sections. Do not repeat the entire literature review or rerun all historical experiments merely because the assistant changed. If new evidence changes the design, record the decision and update the affected report; do not silently maintain contradictory protocols.

### Facts the next assistant must retain

- The label is **final recorded CDM risk**, with high risk defined by final log-risk at least −6. A probability of that class is not physical collision probability, actual collision occurrence, or maneuver necessity.
- The primary real-data horizon is two days before TCA. All features, preprocessing, calibration, thresholds, and prompts must obey their declared information boundary.
- The eligible training population has **8,293 events / 66 high-risk events**; the historical test has **2,167 / 150**. These differ from the raw file populations. Extra resplits or messages do not create new independent positives.
- Historical B1 loss is **0.6939612612**; the frozen v1 LLM loss is **1.6606049431** on saved predictions. They are reproduction anchors, not targets that a new method must beat to justify every possible paper.
- `n_cdms_total` and `last_cdm_days` leak future information in the historical feature builder. Affected B4/B5, space-weather ablations, and the Phase 11 hybrid comparison are superseded.
- `processed/corrected_results.json` is a **two-split pilot**, not a completed corrected campaign. `core/features_causal.py` corrects model inputs but still uses retrospective cohort eligibility.
- The raw Kelvins archive overlaps the existing event universe. It is not a fresh external holdout. OD signatures and coarse age bins are proxies; they do not reveal true observation lineage.
- Track R can yield a bounded method, robustness benchmark, or identification-limit paper. Track E's proposed **20% review reduction / one-percentage-point miss-difference margin** is a conditional design target, not a ten-day pilot requirement or established guarantee.
- The literature already contains sequence forecasting, uncertainty estimation, conservative evidence fusion, and LLM interfaces. Exact replay invariance alone is insufficient novelty.

### Working boundaries

Keep `dataset/` read-only and preserve all eight files in the frozen manifest. Put new logic in new modules and new experiment outputs in a new run directory. Inspect legacy scripts before executing them: `scripts/rerun_corrected.py` overwrites the pilot artifact, its `--test` reads exposed labels, and `scripts/run_hybrid.py` uses contaminated features. `scripts/reproduce.py --check` checks historical infrastructure; it does not run the proposed research programme.

Preserve pre-existing changes. At creation, modified tracked files included `.gitignore`, `Dockerfile`, `README.md`, `api/main.py`, and several `frontend/` files; untracked research, demo, corrected-run, and web files also existed. Capture the actual list in P01. Do not reset, clean, stash, or commit unrelated changes to make the tree look tidy.

The default work is local and offline. No new paid inference campaign, external provider contact, data-access form submission, or paper submission has been authorized in the current record. If those become necessary, prepare the concrete request/run/package first and record the user's authorization when obtained. Local preparation and Track R progress can continue meanwhile. Keep secrets out of this file and exported logs.

## 3. How to use the checkboxes

- `[ ]` means not complete. Put `READY`, `IN PROGRESS`, `BLOCKED`, or `DEFERRED` in a task's evidence note when useful; leave its box unchecked.
- `[x]` means its deliverable and acceptance checks exist. Add an evidence entry with paths, run IDs, and validation results when checking it.
- Optional tasks may remain unchecked with a reason. A negative result can complete an experiment task; it cannot check a superiority claim.
- If a completed task is invalidated, reopen it and record why. Retain the earlier evidence and failed attempts.
- The task ID is the stable reference across assistants. A proposed path below is a design target until created; do not treat a filename's existence as proof of a completed run.

### Preparation already complete

- [x] **PRE01 — audit existing results.** Expected: an evidence inventory and corrected claim boundaries. Evidence: [Report 1](docs/research/2026-10-06/01_EVIDENCE_AUDIT_AND_CURRENT_RESULTS.md) and [saved numerical audit](docs/research/2026-10-06/_support/audit_results.json).
- [x] **PRE02 — perform the deeper literature review.** Expected: primary sources, closest comparisons, access limits, and a narrower novelty hypothesis. Evidence: the linked deep review, source ledger, and bibliography. Unavailable full methods remain a follow-up in V01.
- [x] **PRE03 — audit raw-data overlap and provenance proxies.** Expected: reproducible overlap/age/signature counts. Evidence: [audit script](docs/research/2026-10-06/_support/deep_data_audit.py) and [results](docs/research/2026-10-06/_support/deep_data_audit.json). A full-column crosswalk remains D01.
- [x] **PRE04 — define the research protocol and roadmap.** Expected: proposed methods, endpoints, stages, and paper routes. Evidence: Reports 2 and 3. These documents are **not** a frozen scientific protocol or completed experiment.
- [x] **PRE05 — record the earlier environment verification.** Expected: exact commands and outcomes with limitations. Evidence: the linked verification record. Do not claim those checks were rerun in a later session.
- [x] **PRE06 — prepare the persistent execution/handoff file.** Expected: task IDs, outputs, acceptance criteria, resume prompt, and checkpoint templates. Evidence: this file; local links and task references checked on creation.

## 4. Set up a reproducible working area

Supporting documents now exist in `docs/research/execution/`. Completed and failed run directories are under `processed/research/`; consult each manifest before use.

- [x] **P01 — capture workspace and environment.** Depends on: preparation above. **Do:** inspect applicable repository instructions, Git state, Python/dependency versions, data/artifact presence, and relevant active jobs. **Expected:** `docs/research/execution/workspace_snapshot.md`, including dirty-file ownership/unknown ownership and required local files. **Done when:** another assistant can identify this exact starting state without guessing or viewing credentials.

- [x] **P02 — establish run and checkpoint conventions.** Depends on: P01. **Do:** establish the versioned run layout and checkpoint conventions; define unique run IDs and `planned/running/complete/failed` statuses. Save commands, configs, seeds, logs, hashes, and failure reasons. **Expected:** `run_contract.md` under the execution directory and a small example run manifest. **Done when:** incomplete output cannot be mistaken for a completed result, and existing output is never silently overwritten. Existing reports stay in their dated directory.

- [x] **P03 — verify the usable local environment.** Depends on: P01–P02. **Do:** run relevant existing checks, use the documented CPU workaround where needed, and independently confirm frozen working-file hashes. **Expected:** exact commands, exit codes, durations, and check results in a new verification log. **Done when:** failures are resolved or specifically bounded; historical learned-model checks are not misrepresented as valid scientific comparisons. Record the environment snapshot used by future runs.

- [x] **P04 — translate the research question into a development configuration.** Depends on: P02. **Do:** encode Track R, target, horizon, cohort definition, arm roles, failure policy, and artifact fields from Report 2. **Expected:** versioned development config and a claim/evidence inventory. **Done when:** pilot versus scientific evaluation is explicit and no configuration calls exposed Kelvins outcomes a fresh holdout. This is a development configuration; scientific freeze is V03.

## 5. First ten working days: data, controls, and mechanism pilot

The day ranges are planning estimates, not promised runtimes. Save partial progress between tasks rather than waiting for an entire stage to finish.

### Data and information boundary — approximately days 1–4

- [x] **D01 — finish the raw/split crosswalk and data dictionary.** Depends on: P02, P04. **Do:** build on PRE03; reconcile the 203 train and 24 test rows unmatched by the normalized nine-field fingerprint, with full-column tolerances and ambiguity reporting. **Expected:** crosswalk, source hashes, cohort-flow counts, units, missingness, and known/unknown field semantics. **Done when:** mismatches are explained or retained explicitly as unresolved; age bins are not turned into invented timestamps and event IDs are not used as calendar order.

- [x] **D02 — implement the visible-prefix provenance extractor.** Depends on: D01. **Do:** preserve raw last-observation age fields and OD metadata in a new versioned schema, alongside availability and missingness flags. **Expected:** new extraction module and a compact sample plus extraction manifest. **Done when:** every feature has source/unit/availability/proxy status, and extraction leaves raw and frozen artifacts unchanged. Unresolved semantics remain categorical or unknown.

- [x] **D03 — separate cohort inclusion from feature availability.** Depends on: D02. **Do:** implement the named retrospective benchmark cohort and specify prediction-time inclusion for any prospective cohort. **Expected:** cohort table with inclusion/exclusion reasons, visible prefix, label status, and counts. **Done when:** eligibility that depends on future records is explicitly labeled retrospective, and missing future labels cannot silently remove cases from a prospective population.

- [x] **D04 — prove the feature boundary with falsification tests.** Depends on: D02–D03. **Do:** mutate, append, and remove post-cutoff rows while holding membership fixed; cover ties, ordering, duplicates, and missing inputs. Separately test membership. **Expected:** focused tests and a saved audit. **Done when:** new inputs/policies stay invariant, while the known contaminated implementation is detected. A passing ordinary fit test is insufficient.

### Baseline runner and minimal comparators — approximately days 3–8

- [x] **B01 — implement the paper runner and fixed development partitions.** Depends on: P03–P04, D03–D04. **Do:** save event-grouped outer/inner folds and keep all prefixes/copies together; implement training-only preprocessing, model selection, calibration, and threshold selection. Start from Report 2's five outer / three inner folds, reducing only with a documented class-count reason. **Expected:** runner, `splits.parquet`, arm registry, and per-event prediction schema. **Done when:** a small run completes end to end, split leakage checks pass, and failures/undefined metrics remain visible.

- [x] **B02 — reproduce simple anchors and fit clean simple classifiers.** Depends on: B01. **Do:** verify B1 and constant-score anchors, then run calibrated latest risk, latest risk plus audited metadata, regularized logistic regression, and causal gradient boosting. **Expected:** predictions, class counts, calibration summaries, metrics, runtimes, and component scores. **Done when:** anchor discrepancies are explained before comparing new models, and each classifier uses the same allowed information and folds. Do not derive official log-risk as `log10(q)`.

- [x] **B03 — add matched history controls.** Depends on: B02. **Do:** implement exact deduplication, fixed thinning, change-based pooling, singleton/fixed/random grouping controls, and an ignore-updates arm with matched downstream modeling. **Expected:** baseline configurations, invariance checks, and paired predictions. **Done when:** representation changes are isolated from capacity, tuning, calibration, and extra-field advantages; genuinely new similar measurements are not declared duplicate ground truth.

- [x] **B04 — implement the corrected two-stage comparator.** Depends on: B01–B02. **Do:** cross-fit both the classifier and value regressor during threshold selection; keep official-score and final-class endpoints distinct. **Expected:** new versioned corrected results and predictions, preserving the old pilot. **Done when:** the declared run grid is complete, both stages obey fold boundaries, fit seeds are recorded, and metrics regenerate from predictions. This may continue after the initial pilot if it is not needed for its selected endpoint.

### First proposed method — approximately days 5–8

- [x] **M01 — implement the transparent partition-summary model.** Depends on: D04, B03. **Do:** follow Report 2 §5.1: canonicalization, at most eight label-free partitions, equal total training weight per event, one shared regularized logistic model, and calibration of the maximum partition score. **Expected:** a new method module, configuration, and per-partition diagnostic outputs. **Done when:** construction is deterministic, fitting stays inside training data, missing provenance stays explicit, and the displayed score range is described as sensitivity rather than coverage.

- [x] **M02 — test method properties and run a bounded development comparison.** Depends on: M01. **Do:** check exact replay invariance, ordering rules, unknown fields, and no-future-information behavior; compare on fixed development folds with simple controls. **Expected:** focused property tests, paired predictions, preliminary loss/calibration/workload/miss tables, and failure cases. **Done when:** all planned pilot arms and failed variants are retained; a tiny favorable split is not treated as confirmation.

### Known-lineage mechanism harness — approximately days 5–8, can run alongside baseline work

- [x] **S01 — implement the small linear-Gaussian harness.** Depends on: P02, P04. **Do:** use Report 2 §6.1's common-epoch encounter-plane model, immutable observation IDs, and explicit observation windows. Keep one complete unique-observation bank and final label across variants of a latent scenario. **Expected:** generator, scenario manifest, window membership, and synthetic labels. **Done when:** repeated publication, partial overlap, and genuinely new observations can be distinguished by construction. Describe it as a controlled geometry model, not a validated operational orbit simulator.

- [x] **S02 — partition scenarios and validate the harness independently.** Depends on: S01. **Do:** assign scenario banks before producing model-training variants; isolate development/software-validation banks and reserve scientific scenario IDs/seeds/configurations. Validate Gaussian calculations and disk-probability integration independently. Add new-information positive controls and bias/correlated-noise stress cases with a correctly specified oracle. **Expected:** fixed manifests, numerical checks, and an access ledger. **Done when:** variants never cross partitions, latent truth is separated from final reported-risk labels, and reserved scientific outcomes have not guided development. Mark any accidentally inspected bank exposed and replace it before claiming a fresh evaluation.

- [x] **S03 — test the proposed mechanism on development scenarios.** Depends on: S02, B03, M02. **Do:** compare no reuse, partial overlap, exact replay, and genuinely new observations, with matched labels/scenarios and simple controls. **Expected:** absolute losses, paired loss-degradation contrasts, calibration/decision diagnostics, and failure explanations. **Done when:** any proposed advantage survives relevant simple controls, or its absence is documented. Passing duplicate invariance alone does not establish a contribution.

### First decision — approximately days 9–10

- [x] **F01 — prepare the feasibility decision.** Depends on: results or documented infeasibility from D01–D04, B02–B03, M02, S03. **Do:** summarize data identifiability, mechanism evidence, close-method access, runtime, and realistic data/precision needs. **Expected:** `docs/research/execution/feasibility_decision.md` with **proceed / narrow / stop**, including alternatives tried. **Done when:** the recommendation is supported by saved evidence and specifies one falsifiable next claim. A blocked experiment can justify narrowing/stopping; it remains unchecked. No positive result is required to complete this decision task.

- [x] **F02 — record the chosen paper route and revise the backlog.** Depends on: F01. **Do:** retain Track R if justified, narrow to a benchmark/identification finding, or select the separate LLM-evaluation fallback. Record the user's latest direction when supplied. **Expected:** decision entry here, revised primary question, explicitly deferred tasks, and updated downstream dependencies. **Done when:** the checkpoint names the next ready task and the selected route has a defensible evaluation. For the LLM fallback, identify the required completed L01/L02 evidence that replaces V04/A01 as input to A02; retain A02, A03, and the paper tasks. Define any additional protocol/replication work before running it. If the method route stops, leave its later boxes deferred; do not force a success story.

## 6. Complete the scientific study after the pilot

V01–V04 and A01 describe the Track R study. Proceed with them when F02 retains a compatible claim; otherwise record their replacements or deferred status. A02 and A03 are shared requirements for every paper route. Adapt dependencies openly for a narrower claim rather than silently changing their meaning.

- [x] **V01 — resolve the closest-work comparison.** Depends on: F02; literature acquisition may start earlier. **Do:** inspect enough accessible full methods/code for the relevant Sánchez weighting/classification approach, a strong sequence/ensemble family, and applicable fusion alternatives. Track TimeQuery, Ouari, the TCN–Transformer, and AMOS fusion work without mixing their targets. **Expected:** compatibility table with dataset, label, horizon, split, inputs, calibration, metric, and reproduced/adapted/approximate/discussion-only status. **Done when:** the selected comparison is justified and remaining inaccessible details explicitly limit claims. Do not stall all local work while waiting for a paper.

- [x] **V02 — complete strong comparators, ablations, and precision planning.** Depends on: F02, B04, V01. **Do:** implement feasible close comparators; remove grouping/age/OD components separately; compare oracle versus observed provenance only where lineage is known. Use development results for sample-size and runtime planning. **Expected:** development comparison package, tuning budgets, simulator sensitivity plan, and precision/power report. **Done when:** the study size and primary comparator are justified, all arms share an honest evaluation, and ineffective complexity is not retained solely for a headline. **Evidence (complete 10 October 2026):**
- **Comparators:** the comparison package (tuning, covariance, sequence, fusion and component bundles).
- **Tuning:** the [tuning decision](docs/research/execution/tuning_decision.md).
- **Primary contrast:** the [primary contrast](docs/research/execution/primary_contrast.md) and [precision report](docs/research/results/precision_2026-10-10/report.md).
- **Sensitivity:** the [sensitivity results](docs/research/results/sensitivity_2026-10-10/report.md), with independent training banks and four alternative configurations.
- **Specification:** the [analysis specification](docs/research/execution/analysis_specification.md), covering K = 10 banks, n = 5,000, the validated bank-combined interval and Holm.
- **Verification:** [verification](docs/research/execution/v02_completion_verification.json).

Grouping, oracle weighting and the neural arms are retained only as secondary or bounded comparisons.

- [x] **V03 — freeze the scientific Track R protocol.** Depends on: V02, S02. **Do:** fix one primary method, comparator, overlap/noise condition, sample size, scenario partition, clipped log-loss rule, paired contrast, uncertainty procedure, secondary analyses, failure policy, and all software/configuration hashes. **Expected:** immutable `protocol.json`, reservation/access manifest, and freeze record. **Done when:** the freeze precedes scientific outcome access and every item in Report 2's freeze checklist is addressed. A draft document or timestamp alone does not satisfy this task. **Evidence (frozen 10 October 2026, commit `8903632`):** [protocol](docs/research/execution/track_r_protocol.json) (canonical SHA-256 `69040e6b...`, 45 files pinned by git blob id), [reservation](docs/research/execution/track_r_reservation.json), [freeze record](docs/research/execution/track_r_freeze.json), [outcome](docs/research/execution/v03_freeze_plan.md). No scientific scenario exists. Report 2's separate-analysis-owner check is not satisfied by this assistant and is recorded as a V04 precondition, not claimed.

- [ ] **V04 — run the held-out scientific simulation evaluation.** Depends on: V03. **Do:** execute the frozen run; retain all scenarios, failures, and planned secondary conditions. Compare the overlap-induced change in loss for method versus comparator, with absolute loss and new-information controls. **Expected:** complete run manifest, predictions, scenario-level paired analysis, intervals, and deviation log. **Done when:** all planned outputs are traceable and the conclusion follows the frozen rule. Do not tune on these outcomes and keep calling them untouched.

- [x] **A01 — finalize retrospective real-CDM analysis.** Depends on: V03, B04. **Do:** generate the selected real-data comparisons, calibration, workload/miss frontiers, censoring diagnostics, and mission/quality sensitivity under the frozen analysis choices. **Expected:** separate retrospective tables and failure analysis. **Done when:** exposed-data results are labeled as such and are not pooled with simulation or new-real-cohort confirmation into an ambiguous test score. **Evidence (10 October 2026):**
- [contract](docs/research/execution/a01_contract.json);
- refit `real_retrospective_20261010_v1` (frozen C grid, stored folds, 19/20 arm-folds reproduce earlier predictions);
- [report](docs/research/results/real_2026-10-10/report.md): metrics, calibration, frontiers, paired contrasts with event and mission-cluster intervals, leave-one-mission-out, censoring and missed-positive listing;
- post-hoc [quality strata](docs/research/results/real_quality_2026-10-10/report.md).

All results are labelled exposed and are separate from simulation. Main result: the history summary is worse than latest-message metadata (R1 +0.0030 out-of-fold, +0.026 historical test).

- [ ] **A02 — assemble a claim-to-evidence register.** Depends on: V04 and A01 for Track R, or the completed alternative study explicitly selected in F02. **Do:** map each proposed abstract/result/conclusion claim to its experiment, metric, cohort, interval, limitations, and source. **Expected:** `claim_evidence.csv` or equivalent structured table. **Done when:** null, negative, and inconclusive findings are included, all quantitative claims regenerate, and no statement exceeds its evidence type.

- [ ] **A03 — perform independent reproduction and claim review.** Depends on: A02. **Do:** have another assistant/reviewer reconstruct key tables from saved artifacts; obtain domain/statistical scrutiny where needed. **Expected:** reproduction instructions, discrepancy log, and review resolutions. **Done when:** independent reconstruction agrees within declared tolerances and unresolved scientific limitations are stated. Changing assistants alone is not independent scientific validation; log what was actually checked.

## 7. Turn completed evidence into the paper

- [x] **W01 — draft the manuscript skeleton and related work.** Depends on: F02; can proceed alongside later experiments. **Do:** write question, task definition, data provenance, nearest-work comparison, methods outline, and empty result tables. **Expected:** manuscript source under a clearly chosen `paper/` directory, plus bibliography and supplement outline. **Done when:** every intended result has a defined artifact source and all placeholders are visibly incomplete. Never fill them with anticipated scores.

- [ ] **W02 — generate paper figures and tables.** Depends on: A02. **Do:** script the cohort-flow, task/mechanism diagram, primary comparison, workload/miss frontier, controlled-overlap response, and ablation/failure figures relevant to the final claim. **Expected:** plotting/table scripts and standalone exports with run IDs and captions. **Done when:** plots regenerate from saved data, intervals/counts are shown, and no favorable values are manually patched.

- [ ] **W03 — finish results, limitations, and the submission draft.** Depends on: W01–W02, A03. **Do:** write only supported results; reconcile abstract, conclusion, supplement, README-facing claims, and errata while preserving frozen history. Choose a venue by the actual contribution and verify its current author requirements. **Expected:** complete manuscript and supplement, limitations, data/code availability, and disclosure statements. **Done when:** reviewers can distinguish retrospective, simulated, and independently confirmed findings, and no placeholder or unsupported novelty/performance claim remains.

- [ ] **W04 — prepare the reproducibility and submission package.** Depends on: W03. **Do:** package permitted code/configs/predictions, checksums, environment instructions, citations, and generated figures; prepare author/venue checklist and cover letter. **Expected:** reviewable release/submission bundle and a final handoff checkpoint. **Done when:** a clean reconstruction path is documented, redistribution permissions are respected, and human authors have a concrete package to review. External upload/submission is a separate action requiring the user's instruction; acceptance is not a checkbox under our control.

## 8. Conditional branches — not prerequisites for finishing Track R

### Track E: independent real-data efficacy

- [ ] **E01 — establish external-cohort feasibility.** Depends on: F02. **Do:** prepare a bounded provider request using Report 1's data contract; identify complete event histories, label rules, overlap checks, permissions, and a custodian. Contact providers only with recorded authorization. **Expected:** access decision and verified sample/schema. **Done when:** real availability and suitability are established, not merely a promising URL. Otherwise mark blocked/deferred and continue Track R.

- [ ] **E02 — demonstrate statistical feasibility and freeze the efficacy protocol.** Depends on: E01, V02. **Do:** simulate the actual paired workload/miss analysis using plausible prevalence, discordance, dependence, and missingness; fix margins, thresholds, sample size, and inference before evaluation. Protect new outcomes. **Expected:** power/precision report and immutable Track E protocol. **Done when:** independent positive counts support the chosen claim and calibration, optional certification, and evaluation are not double-counted. The existing 66 training positives do not certify a 1% miss rate.

- [ ] **E03 — evaluate the sequestered real cohort.** Depends on: E02. **Do:** run the frozen policies once under the recorded access rule, including unresolved cases as review. **Expected:** paired predictions/counts, review reduction, miss difference, valid uncertainty, and access/deviation logs. **Done when:** both prespecified efficacy requirements are assessed without changing margins or thresholds after seeing results. A failed or inconclusive test is a completed evaluation, not an efficacy success.

- [ ] **E04 — integrate the external finding with bounded claims.** Depends on: E03, A02. **Do:** update manuscript tables and limitations for the actual result. **Expected:** revised claim/evidence register and paper sections. **Done when:** no claim of collision prevention, maneuver safety, or analyst time savings is inferred solely from final-risk labels and review counts.

### Optional LLM/intervention study

- [ ] **L01 — complete a matched offline intervention analysis if selected.** Depends on: F02, B01–B04. **Do:** use causal features, common event IDs/action semantics, explicit failure handling, and matched no-LLM/permutation controls. **Expected:** separate exploratory run and intervention/stability report. **Done when:** old unequal cohorts and superseded hybrid results cannot drive the conclusion; cached-output analysis is not described as fresh inference.

- [ ] **L02 — conduct a fresh repeated-call study only if needed and authorized.** Depends on: L01 and a justified budget/precision plan. **Do:** freeze provider/model/prompt configuration, matched inputs, independent repetitions, request/cache identity, retries, and cost caps. **Expected:** fresh request manifest, saved responses, failure-inclusive predictions, and correctly scoped variability estimates. **Done when:** event sampling, provider variation, and repeated-call uncertainty are separated. Keep this deferred if it does not answer the chosen paper question.

## 9. Switching assistants or machines without losing work

### At every session boundary

- [ ] Record active/completed task IDs and update **NOW / NEXT / BLOCKED** at the top.
- [ ] Add an evidence entry: changed files, run ID, exact command, exit code, output path, key result, and unresolved issue.
- [ ] Check completed tasks only after their acceptance criteria pass; label partial runs incomplete.
- [ ] Record any holdout/label access and whether it affected method choices.
- [ ] Record long-running process ID, start time, command, log path, completed partitions, and whether it is still alive. A tool-session handle alone may not transfer to another assistant.
- [ ] Save the next concrete action and executable command, or state that a referenced command still needs implementation. Do not invent a CLI for planned code.
- [ ] Capture the current Git diff/status summary. Preserve work in the shared folder; if switching folders/machines, verify the transfer below.

Reset these session-boundary boxes for the next work session after recording its checkpoint; the numbered research-task boxes retain their state.

### If the next assistant uses the same repository folder

Keep this file, uncommitted changes, and local artifacts in place, then use the resume prompt. Inspect whether any job is still running before starting another copy. No special assistant-specific memory file is required by this workflow.

### If moving to another machine, clone, or worktree

- [ ] Transfer the current source **and relevant uncommitted/untracked files**, including this checklist and the three reports; verify destination HEAD and working changes.
- [ ] Inventory and transfer/reacquire required data from `dataset/`, historical/new results from `processed/`, and needed response caches from `cache/`. These directories are ignored by Git; a clone alone is insufficient. Do not automatically publish them or assume redistribution rights.
- [ ] Compare source/destination manifests and hashes for the artifacts used by the selected task. Include the exact saved responses needed to avoid paid regeneration.
- [ ] Preserve original run manifests. Some reconstruction inputs use absolute Windows paths; retain the original layout or implement and verify an explicit relocation map before full reconstruction on another machine. Do not rewrite hashed manifests merely to make paths resolve. Compact export verification below is independent of those paths.
- [ ] Recreate the Python environment from recorded requirements and versions; do not copy a Windows virtual environment to another OS. Record any dependency changes rather than silently upgrading.
- [ ] Configure credentials separately only when the selected task needs them; do not copy secret values into Markdown, commits, or the research bundle.
- [ ] Run a small artifact-read/metric reconstruction check before resuming larger computations. Confirm the intended output namespace and scientific holdout status.

### Startup commands that exist today

PowerShell, from the existing Windows workspace:

```powershell
Set-Location -LiteralPath 'F:\conjunction-triage'
Get-Content -Encoding UTF8 RESEARCH_CHECKLIST.md
git status --short
git rev-parse HEAD
.\.venv\Scripts\python.exe --version
```

Verify the committed compact result bundles without datasets, models or numerical dependencies:

```powershell
python -m research.verify_exports --root docs/research/results
```

This checks file bytes against the committed provenance manifests. It does not retrain models or independently validate the science. Full reconstruction still needs the ignored data/run transfer above.

For P03 or relevant validation after changes, the earlier successful Windows test configuration was:

```powershell
$env:LOKY_MAX_CPU_COUNT = '2'
.\.venv\Scripts\python.exe -m pytest -q --tb=short --no-showlocals
```

That environment variable applies to the current PowerShell process and its children. Record or restore an existing value if needed. Start with focused tests for the changed code; run the full suite at appropriate milestones, not on every assistant switch. The earlier 337-pass count is a reference, not a promise about a later environment.

An optional historical infrastructure check, after inspecting its source and confirming required local artifacts:

```powershell
.\.venv\Scripts\python.exe -u scripts/reproduce.py --check
```

Its historical learned-model headline remains superseded where Report 1 says so. It does not launch the new paper experiments. New runner commands must be added here **after implementation**, with actual tested options. On another OS, resolve the new repository/interpreter paths and use the same recorded configuration rather than copying these Windows paths literally.

## 10. Persistent evidence and decisions

Append concise entries here; place long logs and tables in the run directory and link them. The top checkpoint should always summarize the latest usable state.

### Task evidence template

```text
Task ID / status:
Date / assistant:
Inputs and code/config hashes:
Files created or changed:
Run ID / artifact paths:
Exact command(s), working directory, and relevant non-secret environment:
Exit code / duration / validation result:
Main measured result (or "no scientific result; implementation only"):
Acceptance criteria passed / remaining:
Data/holdout access and deviations:
Running process details or "none":
Next task and exact next command:
```

### Decision log

| Date | Decision | Reason / evidence | Consequence |
|---|---|---|---|
| 2026-10-06 | Default to Track R; keep Track E conditional. | Existing reports identify exposed/overlapping public data and scarce independent positives. | Start P01–P04 and the mechanism pilot; external access does not block all progress. |
| 2026-10-06 | Use one assistant-neutral checklist at repository root. | User requested continuity from Codex to Claude Code. | Update this file and artifact paths after each task; carry the working tree and required local data across any machine change. |
| 2026-10-10 | Continue autonomously; commit as `NitinTheGreat <nitinpandey1304@gmail.com>` with no assistant trailer. | User: "dont stop and dont wait for me to say next. keep going." | Ready tasks proceed without per-step confirmation. Irreversible or outward actions still need explicit authorization. |
| 2026-10-10 | After the V03 freeze, the user said "continue as you see fit". | Interpreted as: proceed with A01. Not taken as authorization to open the reserved scientific holdout. | V04 stays gated on explicit authorization plus an independent analysis check, or a recorded waiver; A01 proceeds. |

### Earlier preparation session

**2026-10-06 — checklist preparation.** Created this file from the three research reports and a read-only repository review. Verified local links and task references. No scientific model training, new research evaluation, paid inference, or external contact was performed. Existing application changes were preserved. **Next: P01**, beginning with the startup commands above and creation of the workspace snapshot.

## 11. What to expect at each milestone

| Milestone | Tangible result | What it lets us conclude |
|---|---|---|
| P01–P04 | Reproducible workspace, run contract, checks, development config | Work can resume from files; no new scientific efficacy claim. |
| D01–D04 and B01–B03 | Audited inputs, leakage guards, clean predictions and controls | The proposed method can be tested on an honest and comparable pipeline. |
| M02, S03, F01–F02 | Pilot tables, controlled examples, and a proceed/narrow/stop decision | Whether the proposed mechanism is worth a full study; a negative decision is useful progress. |
| V04 and A01–A03 | Frozen simulation results, retrospective real-data analysis, independent reconstruction | A bounded robustness/method/measurement finding with stated limitations. |
| E03, if feasible | Protected new-real-cohort paired evaluation | Whether the prespecified real-data efficacy criteria pass in that population. |
| W01–W04 | Manuscript, figures, supplement, reproducibility and submission bundle | A reviewable paper package; publication depends on scientific strength and editorial review. |

The practical first work session is **P01 → P02 → P03 → P04**, stopping at a recorded checkpoint if time or credits run out. The next assistant then continues the first ready unchecked task, using the same evidence rather than restarting the project.

### Execution session - 9 October 2026 (initial checkpoints)

P01-P04 complete: [workspace snapshot](docs/research/execution/workspace_snapshot.md), [run contract](docs/research/execution/run_contract.md), [verification](docs/research/execution/verification_2026-10-09.json), and `research/configs/development.json`. Full initial suite: 337 passed / 1 skipped in 91.20 seconds; four new artifact/data tests pass. New modules preserve historical outputs. Example contract run: `processed/research/contract_20261009_v1/`. Data preparation started with `.venv/Scripts/python.exe -m research.prepare --run-id data_20261009_v1`; results and PID are in its manifest, shell output in the execution log. No new scientific superiority claim.

D01-D04 complete: [data dictionary](docs/research/execution/data_dictionary.md) and `processed/research/data_20261009_v2/`. All 189,285 released input/label rows matched across 102 non-ID columns. Extraction preserves the benchmark cohort of 8,293 training events / 66 positives and 2,167 test events / 150 positives. Four artifact/data tests plus three model-property tests pass; historical causal falsification checks passed in the initial full suite. Current run command: `.venv/Scripts/python.exe -m research.evaluate --data-run processed/research/data_20261009_v2 --run-id cv_20261009_v1`, with LOKY_MAX_CPU_COUNT, OMP_NUM_THREADS, and MKL_NUM_THREADS all set to 2. Source snapshots are stored in data v2 and the CV run.

### Final checkpoint - 9 October 2026

**Outcome: NARROW.** [Feasibility decision](docs/research/execution/feasibility_decision.md). Grouping does not establish superiority on the real cohort, and the simulation advantage over pooling is conditional and fails to beat latest-only in absolute heavy-overlap loss. Preserve these negative/mixed findings. The three main reports now have dated execution updates; their earlier prospective text is not proof of a completed or frozen study.

| Completed task | Evidence and acceptance scope |
|---|---|
| P01-P04 | Snapshot, run contract, process-local environment, initial/full tests and `research/configs/development.json`. Development configuration is not registration. |
| D01-D04 | `research/data.py`, `research/prepare.py`, data v2, data dictionary, 102-column reconciliation and future-message invariance tests. Retrospective cohort selection remains explicit. |
| B01-B03 | `research/evaluate.py`, `models.py`, `history.py`; 55 completed outer-fold fits, saved splits/models/predictions/metrics/calibration. 91,223 event-arm predictions; identical outer folds across 11 arms. Metadata-matched real comparator and all simple controls retained. |
| B04 | `research/two_stage.py`; five-fold corrected campaign; both classifier and value regressor cross-fitted for threshold selection. `verify_two_stage_20261009_v1` reconstructs all thresholds and three aggregate official scores. Historical two-split artifact untouched. |
| M01-M02 | Deterministic <=8 partitions, event weight one, maximum-score calibration, replay/order/missingness/batched-transform tests. Synthesis saves per-partition scores and ranges; ranges are sensitivity, not coverage. All pilot arms retained; grouped loses to simpler real predictors. |
| S01-S02 | `research/simulation.py`; 3,000 independent latent pilot scenarios, immutable observation-window IDs, common labels, separate latent truth, saved proposal weights. Independent integration/full-joint posterior tests. Reserved scientific scenarios unopened. |
| S03 | `research/simulation_pilot.py`; eight arms across six conditions in two evaluation banks. Paired contrasts and absolute loss saved. Identical controls, bias sensitivity and failed forecast positive control documented; a failed advantage is a completed pilot task. |
| F01-F02 | NARROW decision in feasibility JSON/report. Selected benchmark question is falsifiable; V02 must distinguish controls and repair training shift before V03. Track E and L01/L02 remain **DEFERRED**, not prerequisites. |
| W01 | [Manuscript skeleton](paper/manuscript.md), [bibliography](paper/references.bib), supplement outline, artifact mapping and visibly incomplete scientific result tables. Related-work compatibility/novelty still needs V01. |

**Commands executed successfully**, from `F:\conjunction-triage`, using `.venv/Scripts/python.exe`; model/test commands used process-local `LOKY_MAX_CPU_COUNT=2`, `OMP_NUM_THREADS=2`, `MKL_NUM_THREADS=2`:

```powershell
.\.venv\Scripts\python.exe -m research.prepare --run-id data_20261009_v2 --crosswalk-from processed/research/data_20261009_v1
.\.venv\Scripts\python.exe -m research.evaluate --data-run processed/research/data_20261009_v2 --run-id cv_20261009_v2
.\.venv\Scripts\python.exe -m research.two_stage --data-run processed/research/data_20261009_v2 --run-id two_stage_20261009_v1
.\.venv\Scripts\python.exe -m research.simulation --run-id simulation_20261009_v1 --n 1000
.\.venv\Scripts\python.exe -m research.simulation_pilot --simulation-run processed/research/simulation_20261009_v1 --run-id mechanism_20261009_v1
.\.venv\Scripts\python.exe -m research.summarize_pilot --run-id synthesis_20261009_v1
.\.venv\Scripts\python.exe -m research.verify_two_stage --source processed/research/two_stage_20261009_v1 --data processed/research/data_20261009_v2 --run-id verify_two_stage_20261009_v1
.\.venv\Scripts\python.exe -m pytest -q --tb=short --no-showlocals
```

These run IDs already exist and **must not be reused**. Read the completed artifacts to resume; reconstruction needs a new unique ID. No paid inference or external contact occurred. Every source run includes configuration, hashes, access records and a source archive. A later source file may differ from its archived run version; use the archive when reproducing that run.

**Measured results:** real grouped/latest/causal-GBM log loss 0.032863/0.030194/0.027217. At nominal 95% training recall, grouped reviews 2,379/8,293 and misses 3/66; GBM reviews 1,740 and misses 3. These are exposed retrospective estimates, not guaranteed workload/recall. Official train-OOF B1/B4/B5 L=0.803753/34.537411/1.454757. In software simulation, grouping reduces overlap degradation versus singleton pooling by 0.018405, but latest-only has lower absolute heavy-overlap loss. Shared bias changes the comparison. See the report for conditional intervals and full tables.

**Known pilot limitations / next design requirements:** fixed/time/change controls collapse to singleton predictions under regular synthetic cadence; thinning needs informative cadence variation. Include latest-metadata in the simulation comparator set. New-information inputs shift from training windows of 10 to cumulative windows of up to 60; lower oracle state error does not imply calibrated forecast utility. Add matched training and noise conditions, oracle-lineage ablations and training-seed sensitivity. V01 must resolve applicable close-work baselines and V02 must justify a claim and sample size. A03 remains unchecked: same-assistant artifact audits are not independent scientific review.

**Failed runs preserved:** data v1 stopped after an inefficient correlated SQL query; its complete hashed crosswalk was explicitly reused by v2 with a semi-join. CV v1 stopped after four arm families to batch equivalent transformations; v2 completed all arms, with exact batched/separate equality tested. Partial v1 scores are excluded. No scientific outcome bank was opened to choose revisions.

**Final verification:** 349 passed / 1 skipped in 47.40 seconds, exit 0; focused 12 research tests had also passed. [Final test log](docs/research/execution/verification_final_20261009.log). [Synthesis integrity audit](processed/research/synthesis_20261009_v1/integrity_audit.json) verifies all five complete source runs, original input/output/source hashes, fold coverage/disjointness, regenerated class metrics and partition maxima. Twelve raw/data-manifest files, 45 historical artifacts and eight frozen files remain unchanged. Exact B5 score/threshold reconstruction passed separately. No active research process remains; all completed manifests record their start/end times and original PIDs.

**Next handoff:** read the feasibility decision and manuscript skeleton, then complete V01's compatibility table from primary sources. Do not regenerate the reserved scientific bank or treat the manuscript placeholders as results. V02 follow-up is not implemented yet. The working tree remains uncommitted with pre-existing application changes preserved; final status is saved in the execution checkpoint. Cross-machine transfer must include ignored `processed/research/` and required data, not only Git-tracked files.

### Version-control checkpoint - 9 October 2026

User instruction: commit completed work incrementally as `NitinTheGreat <nitinpandey1304@gmail.com>`, with the same committer identity and no assistant attribution/trailers. Keep commits scoped; do not include raw data, binaries, downloaded papers, logs, temporary renderings or unrelated application changes. Do not push unless requested.

Completed commits: `9b441b1` (evidence/literature reports and erratum), `54bd4a3` (research modules, configurations, tests and data/run contracts). This checkpoint adds the small [tracked results bundle](docs/research/results/pilot_2026-10-09/README.md), feasibility report, manuscript and handoff. The bundle contains 15 checksum-verified CSV/JSON artifacts plus provenance; bulk predictions/models and exact source archives remain local and ignored. A clone contains readable results but is not sufficient to reconstruct models without the documented data/run transfer.

Validation before committing implementation: 12 research tests passed in 8.89 seconds; compact export succeeded. The prior full-suite result remains 349 passed / 1 skipped; it was not rerun merely for documentation/commit operations. Existing application edits and September PDF/rendering work are excluded. Local machine snapshots and logs remain available in this workspace, not staged.

V01 has started: an accessible arXiv version of the Sanchez covariance-weighting method was located; publication-version equations and compatible sequence/fusion alternatives are being checked. Source access is not an experimental result and no reserved outcomes have been opened.

### V01 completed and next implementation selected - 9 October 2026

Evidence: [closest-work comparison](docs/research/execution/closest_work_comparison.md), [compatibility CSV](docs/research/execution/closest_work_comparison.csv), [source access/version ledger](docs/research/execution/closest_work_sources.json). Full final Sanchez ASR and AMOS papers and the Pinto sequence paper were retrieved; Kessler source inspected and revision recorded. OCI v2 (1 October 2026) and author repository add recent related work. Ouari/TimeQuery full-method limits remain explicit. No literature method has been numerically reproduced merely by this reading.

V01 acceptance passes: targets, datasets, horizons, splits/calibration knowledge, metric compatibility and adaptation/approximation/discussion status are recorded. The selected V02 set includes a named covariance-proxy approximation, an accessible sequence-family adaptation, and separate fusion diagnostics. Strongest-current-method or field-wide novelty claims remain unsupported. V02 is open, beginning with irregular-cadence/control-distinction tests and a latest-metadata simulation comparator; reserve all scientific outcomes until V03.

Additional completed commits: `5cde0d5` (small results, feasibility, manuscript and handoff), `de99a3d` (byte-exact evidence export across Git checkouts). All 15 evidence blobs were checked against source artifact SHA-256 values directly in the Git index. Source PDFs/code, local logs and machine snapshots stay out of Git. This V01 checkpoint is the next incremental commit; inspect `git log` for its hash. All new commits use the user's requested author and committer; no assistant trailer is added. No push performed.

### V02 cadence and training-regime milestone - 9 October 2026

Completed incremental implementation commits: `2f981d0` (irregular cadence and repeated-solution controls) and `35d2c9c` (whole-scenario folds, objective weights and two-regime runner). The current result/audit checkpoint is a further scoped commit; `git log` gives its hash. Author and committer remain the requested user identity with no assistant trailer.

Evidence: [V02 development record and commands](docs/research/execution/v02_development.md), [generated results](docs/research/results/v02_2026-10-09/report.md), [audit](docs/research/results/v02_2026-10-09/audit.json), [verification](docs/research/execution/v02_verification.json). All three new run manifests are complete. Nine models under each training regime produce 252,000 paired evaluation rows. Each latent scenario has total objective weight one regardless of its number of variants/partitions. Inner folds keep all variants together and use identical scenario assignments across regimes.

Results: matched training lowers new-information loss for 8/9 software-bank arms and 9/9 bias-bank arms. Grouped software loss improves from 0.23961 to 0.06595, but latest-metadata is 0.06276 and singleton 0.06339. Grouped matched heavy-overlap loss is 0.17502 versus singleton 0.17474. Shared bias still causes poor absolute performance. All 18 fits selected C=10, the upper boundary; a common expanded tuning grid and training-seed sensitivity are needed before selecting a final comparison. This does not establish grouping superiority or operational efficacy.

Construction now distinguishes fixed-time, thinning and burst-change controls; original scenarios, numerical observation solutions and labels are retained, with revised publication times/age categories. These are the same exposed pilot scenarios, not additional independent evidence. Exact replay and matched-latest checks pass. Scientific seed 20261012 and reserved scenario outcomes remain unopened.

Validation: 353 passed / 1 skipped in 52.24s, exit 0. All saved class metrics, 18 thresholds, scenario folds, weights and input/output/source hashes reconstructed. Original 12 raw/data-manifest files, 45 historical artifacts and 8 frozen files unchanged. No active research jobs. V02 remains unchecked; A03 independent review remains outstanding. No paid inference, external communication, submission or Git push occurred.


### V02 common-grid and subset milestone - 9 October 2026

Completed implementation commits: `d1faebe` (equal expanded grid, strict
convergence and whole-scenario subsets), `a5144cb` (artifact reconstruction and
portable checksum verification), `0085d22` (next covariance-proxy plan).
The result/report checkpoint is a subsequent scoped commit; inspect `git log`
for its hash. All use `NitinTheGreat <nitinpandey1304@gmail.com>` as author and
committer, with no assistant attribution. No push performed.

Evidence: [generated result report](docs/research/results/tuning_2026-10-09/report.md),
[audit](docs/research/results/tuning_2026-10-09/audit.json),
[verification](docs/research/execution/tuning_verification.json),
[V02 measured conclusions and exact commands](docs/research/execution/v02_development.md).
Both `tuning_20261009_v1` and `tuning_summary_20261009_v1` are complete.
The latter exports nine byte-exact artifacts plus provenance. Full predictions,
72 saved models, selected-C OOF predictions and all aggregate candidate losses
remain in ignored run directories. A clone retains readable results; transfer
local data/runs for complete reconstruction.

The common C grid is [0.01, 0.1, 1, 10, 100, 1000]. All candidate/final logistic
fits completed without convergence warnings; maximum observed iterations 262.
Twenty-five of 72 selections remain at the upper boundary. The full-data
reference uses the preceding 1,000-scenario training cohort/fold seed; three
stratified 800-scenario subsets each contain 144 positives. They overlap and
measure descriptive membership/fold sensitivity, not independent training-bank
replication. All configurations reuse the same 1,000 evaluation scenarios per
bank; 1,008,000 prediction rows do not increase the independent case count.

**Measured outcome: NARROW remains.** Under matched training, grouped software
heavy-overlap loss is 0.173125 versus singleton 0.170962 in the full-data trial;
singleton also wins in all three subsets. Grouping beats latest-metadata on
software heavy overlap but loses to it and singleton on new-information loss
in all three subsets. Under shared bias, heavy-overlap grouped-versus-singleton
ranking reverses across subsets. Full-data grouped new-information bias loss is
1.918247, with 190/326 missed positives. Preserve this failure of the nominal
training-recall target under shift. The full condition/grid-change tables retain
unfavorable comparisons and separate absolute loss from reuse-induced degradation.

Validation: **359 passed / 1 skipped** in 60.13s, exit 0. The existing skip is
credential-presence dependent; no paid inference occurred. All class metrics,
selected-OOF losses, 72 thresholds, scenario labels/folds/weights, replay and
matched-latest checks reconstruct. All three compact bundles pass checksums
(31 artifact files). The 12 raw/data-manifest, 45 historical and eight frozen
files match their original hashes. No milestone process is active. Scientific
seed 20261012 remains reserved and ungenerated. A03 independent review is open.

**Exact next task:** implement the [covariance-proxy comparator and ablation
plan](docs/research/execution/covariance_proxy_plan.md). Its acceptance checklist
starts with equal-volume/exponential-volume examples, missing/invalid-input
handling, unit rescaling and replay/future-message invariance. The simulator's
normal sigmas are zero, so a naive 3D determinant would be identically zero;
real-data sigmas also do not supply a full encounter-plane transformation.
Record the proposed approximation honestly. The sequence, component/oracle and
precision tasks remain after this. V02 stays unchecked; no scientific freeze or
publication claim is implied by this completed substep.


### V02 covariance-proxy milestone - 9 October 2026

Completed implementation commits: `4f5a90b` (two weighting approximations,
validated history integration and equal-budget campaign), `4d955e3` (forecast
reconstruction and scenario-paired comparisons). This evidence/handoff checkpoint
is a further scoped commit; `git log` gives its hash. Author and committer remain
`NitinTheGreat <nitinpandey1304@gmail.com>`, with no assistant attribution. No push.

Evidence: [result report](docs/research/results/covariance_2026-10-09/report.md),
[audit](docs/research/results/covariance_2026-10-09/audit.json),
[verification](docs/research/execution/covariance_verification.json),
[completed acceptance checklist and exact commands](docs/research/execution/covariance_proxy_plan.md).
Runs `covariance_20261009_v1` and `covariance_summary_20261009_v1` are complete.
The export contains ten byte-exact artifacts plus provenance. Full models,
predictions, source archives and logs remain local/ignored; transfer them for
complete reconstruction elsewhere.

The two added arms are `covariance_trend` (inverse fitted log-volume trend) and
`covariance_direct` (direct inverse volume). Both use an explicitly approximate
radial/tangential diagonal variance product and retain singleton's feature/readout
contract. This is not the published Sanchez inference method or a real-CDM
geometry reconstruction. Required invalid inputs have explicit uniform fallback
or upstream rejection; future records do not enter the visible prefix.

Sixteen new fits use exactly the four saved trials, two regimes, six-value C grid,
scenario folds, calibration and threshold rules. Seventy-two control fits are
reused only after data/code/legacy-feature compatibility checks. The combined
1,232,000 prediction rows still concern the same 1,000 scenarios per exposed
bank. The three 800-scenario training subsets overlap; descriptive ranges are
not confidence intervals or independent training-bank replication.

**Measured result:** both proxies beat grouped and singleton software
new-information loss in all three subsets, but latest-metadata beats both in
all three. Full-data trend/direct losses are 0.062395/0.062217 versus grouped
0.066160 and latest-metadata 0.062295. Direct's tiny full-reference advantage
over latest-metadata does not persist across subsets. Singleton has lower
full-reference software heavy-overlap loss than either proxy; subset rankings
against history controls vary. Shared-bias performance remains poor. Keep all
conditions and adverse results; the NARROW benchmark direction remains.

All 42,000 event/mode diagnostic rows reconstruct. Constant-covariance conditions
have exactly uniform weights, and eight no-reuse-only checks reproduce saved
singleton OOF predictions/thresholds/constant-condition forecasts. Matched
training may still change coefficients because new-information summaries are
weighted differently. All new forecasts were recomputed from saved models;
all metrics and 16 selected thresholds/OOF losses reconstruct. Eight of 16 new
fits still select C=1000; maximum observed iterations is 141 with no convergence
failure. The common tuning boundary remains a design limitation before V03.

Validation: **374 passed / 1 skipped** in 71.28 seconds, exit 0. The existing skip
is credential-presence dependent; no paid inference occurred. Four compact
bundles / 41 artifact files pass byte checks. Original 12 raw/data-manifest,
45 historical and eight frozen files match their hashes. No milestone process
is active. Reserved scientific seed 20261012 remains ungenerated. V02 and A03
independent review remain unchecked.

**Exact next step:** implement the [state-fusion and visible-observation-union
plan](docs/research/execution/state_fusion_plan.md). Start with analytic matrix
and observation-boundary tests; distinguish the repeated-prior error from shared
observation reuse. Existing isotropic covariances make some fusion controls
collapse, so document ties and degeneracy explicitly. Keep state error/covariance
diagnostics separate from class-forecast loss. No fusion runner exists yet.
Sequence adaptation, provenance-component ablations and precision work follow.


### V02 state-fusion/oracle milestone - 9 October 2026

Completed implementation commits: `89b67c4` (Gaussian fusion, visible-union
oracles and pre-evaluation contract), `e09458d` (exact reconstruction and paired
scenario intervals). The compact result/documentation checkpoint is a subsequent
scoped commit; inspect `git log` for its hash. Author and committer remain
`NitinTheGreat <nitinpandey1304@gmail.com>`, without assistant attribution. No push.

Evidence: [generated results](docs/research/results/fusion_2026-10-09/report.md),
[audit](docs/research/results/fusion_2026-10-09/audit.json),
[verification](docs/research/execution/fusion_verification.json),
[completed acceptance checklist/formulas/commands](docs/research/execution/state_fusion_plan.md).
Both `fusion_20261009_v1` and `fusion_summary_20261009_v1` are complete. The new
bundle contains six byte-exact artifacts plus provenance. Bulk message/state
records and exact source archives remain in ignored run directories.

All 138,000 canonical messages reconstruct from original observations before
fusion. The audit exactly reproduces all 126,000 six-arm state records and
21,000 CI weight vectors. Only unique visible observation IDs 0-59 enter the
oracles; future IDs fail. Ordinary methods receive only Gaussian estimates,
not lineage or latent states. Each exposed bank still has 1,000 independent
scenarios; messages, conditions and method repeats do not increase that count.

**Measured result:** software solution reissue gives the Gaussian product the
same mean as latest/CI but an ellipse six times smaller, with inclusion
386/1,000 versus 947/1,000. The prior-once product fixes common-prior reuse under
disjoint observations but does not fix overlapping likelihoods. Under software
heavy overlap, CI state MSE is 0.014655 m^2 versus latest 0.018341 and the
visible-union oracle 0.012420. This is a state-estimation result, not class-q loss.
Cumulative-information CI collapses to latest/union. With omitted shared bias,
its ellipse inclusion is 290/1,000 versus 955/1,000 for the privileged bias-aware
oracle. Input covariance misspecification remains a failure, not a CI guarantee.

These reproduce known information-reuse behavior in a static toy model. No new
fusion theory, orbital validation, class-forecast benefit or operational safety
claim follows. All oracles retain the working wide Gaussian prior and are not
claimed Bayes-optimal for the enriched mixture. All production covariances are
isotropic; the general anisotropic solver is validated only by analytic tests.
The NARROW benchmark direction remains; final novelty and scope are unresolved.

The exports retain all banks/conditions and 1,050 prespecified contrasts with
2,000 common scenario resamples per bank. Intervals are unweighted, descriptive,
marginal and not adjusted for multiplicity. Assess state error, uncertainty area
and ellipse inclusion together. Do not compare these directly to class q or Pc.

Validation: **392 passed / 1 skipped** in 59.53 seconds, exit 0. Five compact
bundles / 47 artifact files pass checksums. Original 12 raw/data-manifest,
45 historical and eight frozen files are unchanged. All milestone jobs exited;
scientific seed 20261012 remains reserved and ungenerated. A03 independent
scientific review remains open. No paid inference or external submission occurred.

**Next task:** the [sequence-family adaptation plan](docs/research/execution/sequence_adaptation_plan.md).
PyTorch is not installed (`importlib.util.find_spec('torch')` returned None), and
requirements do not list it. Verify official compatibility, record a separate
research dependency, run a small synthetic timing/masking check, and commit an
explicit budget before study fits. Include a latest-only neural arm to distinguish
capacity from history information. No sequence CLI exists yet; do not invent one.
Observable-provenance component ablations and precision planning also remain.
V02 stays unchecked; state-oracle diagnostics do not replace class-forecast
component ablations.

### Sequence preflight checkpoint - 9 October 2026

- [x] Install optional CPU dependency and verify deterministic/masked synthetic training.
- [x] Implement visible-prefix and latest-only LSTM with safe weight/preprocessor checkpoints.
- [x] Fix widths 8/16/32 crossed with 20/60 epochs before study fitting.
- [ ] Complete the 304-fit campaign and reconstruction; no study result exists at this checkpoint.

Evidence: [contract](docs/research/execution/sequence_contract.md), [settings](docs/research/execution/sequence_contract.json), [synthetic environment/timing](docs/research/execution/sequence_preflight.json). Exact next step is runner/fold-audit implementation. Scientific reservation unopened; V02 remains open.

Sequence runner added and targeted suite expanded: 15 passed in 8.65s. Tests verify whole-scenario fold separation, reconstruct inner OOF from saved fold models, refit calibration/threshold from selected OOF, and retain a deliberately injected candidate failure. Ready for the declared campaign; no study fit at this commit.

### V02 sequence-adaptation milestone - 10 October 2026

- [x] Pin compatible local CPU dependency and pass synthetic timing/masking/determinism checks.
- [x] Commit the six-candidate contract before study fitting; implement history and latest-only LSTM.
- [x] Complete 304 fits and 16 selected models on unchanged scenario subsets/folds.
- [x] Reconstruct all 285,600 candidate OOF values, train-only preprocessors, selections, calibration and thresholds.
- [x] Reconstruct 224,000 new forecasts bitwise and compare with 88 compatible saved controls.
- [x] Preserve every reuse/bias/new-information condition, paired endpoint and subset sensitivity table.
- [x] Update three reports, manuscript, verification and portable handoff.
- [ ] Complete provenance-component ablations, tuning-adequacy decision and precision planning; V02 remains open.

Evidence: [results](docs/research/results/sequence_2026-10-10/report.md),
[audit](docs/research/results/sequence_2026-10-10/audit.json),
[fixed contract](docs/research/execution/sequence_contract.md),
[verification](docs/research/execution/sequence_verification.json),
[exact commands and interpretation](docs/research/execution/v02_development.md).

In matched software new-information cases, full-reference history LSTM loss is
0.109397, latest-only LSTM 0.083539 and latest metadata 0.062295. History loses
to both latest controls in all three overlapping subsets. On software heavy
overlap it beats latest-only LSTM in all three but loses to singleton/grouping
in all three. Under shared-bias new information, its full-reference loss improves
to 0.812824 versus latest metadata 1.532965, yet it misses 160/326 positives.
Ignore-updates beats latest-only LSTM on this bias condition in all three subsets
and beats history LSTM in one. Keep these tradeoffs; no uniform neural or history
advantage has been established.

All 16 selections reach 60 epochs and eight reach maximum width. Candidate
profiles and loss traces remain available for an explicit tuning-adequacy decision.
The combined 1,456,000 prediction rows reuse the same 1,000 scenarios per evaluation
bank; the three 800-scenario training subsets overlap and are not independent
replications. Selected OOF calibration/threshold reuse is not risk certification.

The environment now contains PyTorch 2.14.1+cpu; optional installation is recorded
in requirements-sequence.txt and sequence_preflight.json. Preserve historical
requirements.txt. Model weights, prediction Parquets, source archives and local
logs remain outside Git; transfer required ignored data and processed/research/
artifacts for another machine. Safe model loading uses weights_only=True.

Implementation commits: bde47ec (preflight/contract), 88ec87d (campaign), c3c4966
(reconstruction), 44a22bd (stricter audit and next-step plan). The results/checkpoint
commit follows these. Author and committer are NitinTheGreat with the requested
email, without assistant trailers. No push or paid inference was performed.

**Next:** [observable-provenance component plan](docs/research/execution/provenance_component_plan.md).
The current grouping rule uses OD fields and time gaps, not categorical age;
separate age readout, OD readout and OD grouping interventions accordingly.
Run label-free construction checks and commit the component budget before fitting.
A03 independent review and V03 scientific freeze remain unchecked. Seed 20261012
and scientific:00000..04999 remain reserved but ungenerated. No milestone job is active.

### V02 provenance-component milestone - 10 October 2026

- [x] Commit the component contract before fitting (`31eb1f8`); implement label-free feature/lineage construction with 24 test items.
- [x] Complete 608 fits / 32 selections / 448,000 forecasts with no failed fit (`components_20261010_v1`, runner `49dcb49`).
- [x] Reconstruct all checkpoints, 571,200 candidate OOF values, selections, calibration, thresholds and forecasts (`components_summary_20261010_v1`, `6e90b79`/`ad60140`).
- [x] Export, verify, and update reports, manuscript and handoff.
- [ ] Tuning adequacy, primary contrast, precision and simulator sensitivity; V02 remains open.

Evidence: [results](docs/research/results/components_2026-10-10/report.md),
[audit](docs/research/results/components_2026-10-10/audit.json),
[contract](docs/research/execution/component_contract.md),
[verification](docs/research/execution/components_verification.json),
[commands and interpretation](docs/research/execution/v02_development.md).
Campaign 19:46-20:00 UTC (PID 28728); reconstruction 20:00-20:16 UTC (PID 24056);
both manifests are `complete` and their code hashes match the committed tree.

Commands executed from `F:\conjunction-triage` with process-local
`LOKY_MAX_CPU_COUNT`, `OMP_NUM_THREADS` and `MKL_NUM_THREADS` set to 2:

```powershell
.\.venv\Scripts\python.exe -m research.component_campaign --run-id components_20261010_v1
.\.venv\Scripts\python.exe -m research.summarize_components --source processed/research/components_20261010_v1 --run-id components_summary_20261010_v1 --export docs/research/results/components_2026-10-10
.\.venv\Scripts\python.exe -m pytest tests/test_research_components.py tests/test_research_exports.py -q --tb=short --no-showlocals -p no:cacheprovider
.\.venv\Scripts\python.exe -m research.verify_exports --root docs/research/results
```

Results, matched training, 1,000 paired scenarios per exposed bank: removing age
readout lowers software heavy-overlap and new-information loss relative to grouping
in all three overlapping subsets (ranges -0.001471 to -0.000285 and -0.001888 to
-0.000322). OD-readout removal is condition dependent: worse in software 90% overlap
and solution reissue (3/3), better in no-reuse/replay/burst/50% overlap (3/3).
Oracle lineage weighting beats singleton on software new information (3/3) but
loses to latest metadata there (0/3) and to ignore-updates on software heavy
overlap (0/3). It worsens shared-bias heavy-overlap and new-information loss
relative to singleton (0/3 each); its full-reference shared-bias/new-information
threshold misses 189/326 positives. Fourteen of 32 selections reach C=1000. These
are retuned development contrasts on exposed banks, not causal fixed-model field
effects, a deployable method or confirmation. NARROW remains the route.

Validation: full suite 434 passed / 1 skipped (78.18 s) on code identical to HEAD;
26 component/export test items passed after reconstruction. Seven bundles / 66
artifact files pass. The 12 raw, 45 historical and 8 frozen files were rechecked
against `workspace_snapshot_2026-10-09.json` after export; `requirements.txt` is
unchanged. No paid inference, external contact, push or scientific-bank access.

Session note: at the start of this session an orphaned system-Python process
(PID 836, `timeout 400 python -` reading a script from stdin; its launching shell
was already gone) was observed. Later evidence indicates it belonged to a
different project: `F:\Agentic BSN\scripts\phase6_0_baseline.py` was written two
seconds before it started, and three further system-Python processes from that
project ran under `nohup` from 03:50:55. None was started or touched by this work.
PID 836 exited by itself, and no file in this repository was written by any of
them (checked by modification time). Nothing here depends on them.

### V02 tuning-adequacy milestone - 10 October 2026

- [x] Implement a no-fit inventory/profile analysis with 8 focused tests (`research/tuning_adequacy.py`; commits `43d7de4`, `12706f3`).
- [x] Re-derive all 136 selections from 816 candidate scores; reconcile all candidates for 48 models and the selected candidate for 88 (max difference 5.6e-17); 1,128 per-fold scores.
- [x] Separate grid limits from failures; quantify boundary steps, paired/fold resolution and neural traces.
- [x] Record the dated decision: RESTRICT to the declared bounded implementations ([decision](docs/research/execution/tuning_decision.md)).
- [ ] §2 primary contrast and precision, §3 uncertainty design, §4 exposed simulator sensitivity; V02 remains open.

Evidence: [report](docs/research/results/tuning_adequacy_2026-10-10/report.md),
[decision](docs/research/execution/tuning_decision.md),
[verification](docs/research/execution/tuning_adequacy_verification.json),
[plan with ticked §1](docs/research/execution/tuning_precision_plan.md),
[commands](docs/research/execution/v02_development.md). Run
`tuning_adequacy_20261010_v2` (22:37:14-22:37:39 UTC, PID 9336, code `12706f3`)
is the evidence of record. `tuning_adequacy_20261010_v1` (code `43d7de4`) is
complete but lacked per-fold scores; it is retained locally and superseded. Its
uncommitted export copy was byte-identical to its run files and was replaced by
the v2 export at the same path before any commit.

```powershell
.\.venv\Scripts\python.exe -m research.tuning_adequacy --run-id tuning_adequacy_20261010_v2 --export docs/research/results/tuning_adequacy_2026-10-10
.\.venv\Scripts\python.exe -m research.verify_exports --root docs/research/results
.\.venv\Scripts\python.exe -m pytest -q --tb=short --no-showlocals -p no:cacheprovider
```

Findings: matched-training logistic, 7/60 at C=1000 with last-step inner-OOF gain
at most 0.000622; C=1000 beats C=100 in 1/16 component models (z at most 1.06).
No-reuse logistic, 40/60 at C=1000 (24 distinct), gains up to 0.009756. LSTM,
16/16 at 60 epochs; 20-to-60-epoch median gain 0.020 (matched) and 0.150 (no reuse,
about 180 versus 780 optimizer steps). No fit failed (max iterations 262/10,000).
Claim boundaries: matched logistic comparisons are conditional on the grid;
no-reuse within-regime differences below 0.01 nats and neural family rankings are
not interpreted. Reopen if §2 picks a contrast depending on no-reuse training or
an LSTM arm; then commit an equal-opportunity extension contract before fitting.

Validation: full suite 442 passed / 1 skipped (58.53 s) on committed code; 8
bundles / 78 artifacts pass; 12 raw, 45 historical and 8 frozen files unchanged.
No fitting, paid inference, external contact, push or scientific-bank access.

**Exact next step (§2):** fix and record one primary paired contrast among logistic
representations under matched training, with its estimand (absolute loss or
degradation relative to no reuse), condition, bank, clipping and an explicit
adverse outcome. F01's falsifiable claim concerns reuse-induced degradation of a
history model relative to latest-only prediction, so candidates include a history
representation (singleton or grouped) versus latest-metadata under heavy overlap,
with new-information and absolute-loss results kept as secondary. Then build the
planning table: per-contrast paired mean and SD are already in each bundle's
`paired_contrasts.csv` (1,000 scenarios per bank; the three overlapping subsets
are not independent replications). Miss/review discordance counts are not
exported; derive them from the source runs' `predictions.parquet` files. No
precision CLI exists yet. Scientific seed 20261012 remains ungenerated.

### V02 primary-contrast and precision milestone - 10 October 2026

- [x] Recompute 2,560 matched-training paired contrasts with case-ID hashes and review/miss discordance; reconcile 1,280 export rows (`research/precision_planning.py`, commits `00462a8`, `a98236c`; 6 tests).
- [x] Normal-approximation sizes, resampled t-interval checks and exact miss bounds; infeasible targets retained.
- [x] Record the proposed primary contrast, margin, decision rule and provisional size ([primary contrast](docs/research/execution/primary_contrast.md)).
- [ ] §3 analysis specification and §4 simulator sensitivity; V02 remains open; nothing is frozen.

Evidence: [report](docs/research/results/precision_2026-10-10/report.md), run
`precision_planning_20261010_v2` (22:57:51-22:58:15 UTC, PID 17924, code `a98236c`).
`precision_planning_20261010_v1` (code `00462a8`) is byte-identical apart from the
added case-ID columns; it is retained locally and superseded.

P1 = degradation of singleton versus latest_metadata at 90% overlap, correctly
specified noise, matched training. Development effect 0.069578-0.074915; planning
SD 0.363. Margin 0.02 nats: confirm if L > 0.02, "not material" if U < 0.02,
otherwise inconclusive. Provisional n = 5,000 (the full reservation). Recompute
before generation if §4 finds SD > 0.40 or effect < 0.035. Secondary candidates
S1-S6 cover the absolute crossover under solution reissue, grouping, oracle
weighting and an exploratory shared-bias bank. Reports 1-3 and the manuscript
will be updated at the end of §3/§4 rather than per substep; the decision files
here are current.

**Exact next step (§3):** write the analysis specification. Quantify training
versus evaluation variance: for S2/S3, between-trial SD is about three times the
n = 5,000 evaluation SE. Decide between conditional-on-one-fit inference and
independent training banks, with seeds and runtime fixed before generating them.
Fix selection/calibration/threshold roles; choose and validate the interval
method under right skew; fix the confirmatory secondary family and Holm
multiplicity; and set the failure policy.

### V02 completion milestone - 10 October 2026

- [x] Independent training-bank and configuration sensitivity under a committed contract (`sensitivity_20261010_v1`, 61 min, 2,128,000 predictions).
- [x] Interval-method validation (bootstrap-t; bank-combined coverage 0.950-0.966 in simulation).
- [x] Complete analysis specification; plan sections 1-5 ticked with evidence.
- [x] Three-phase scientific runner with sealed labels and protocol-gated reserved access (`25d4854`), tested on development seeds only.
- [ ] V03 freeze; V04 awaits user authorization.

Evidence:
- [sensitivity](docs/research/results/sensitivity_2026-10-10/report.md);
- [bank intervals](docs/research/results/bank_intervals_2026-10-10/report.md);
- [intervals](docs/research/results/intervals_2026-10-10/report.md) and [P1 n = 5,000](docs/research/results/intervals_p1_n5000_2026-10-10/report.md);
- [specification](docs/research/execution/analysis_specification.md), [freeze plan](docs/research/execution/v03_freeze_plan.md) and [verification](docs/research/execution/v02_completion_verification.json);
- commands in [V02 record](docs/research/execution/v02_development.md).

**Key results** (exposed development):
- **P1 persists:** reuse degradation is 0.051-0.074 across six independent isotropic banks and 0.044-0.079 under anisotropy and doubled noise. It is +0.020 with bias-matched training; earlier negative bias results came from training without bias.
- **Bank variance:** it is about 3.6 times the earlier overlapping-trial estimate, so V04 uses K = 10 independent banks.
- **Small or null contrasts:** S1 is near zero; S6 is small and therefore exploratory; grouping and oracle weighting give no reduction above 0.01.

**Decision for the user:** V03 can be frozen locally. Running V04 opens the reserved scientific bank permanently. Report 2 asks for a separate analysis owner to reproduce the decision rule on boundary-null cases before then. Same-assistant tests exist (`tests/test_research_track_r_analysis.py`); an independent check does not.

**Exact next step:** create `docs/research/execution/track_r_protocol.json` from the analysis specification and `tests/test_research_track_r_scientific.py::protocol()`, substituting the scientific values:
- `scitrain01`-`scitrain10` banks with seeds 20261301-20261310;
- the `scientific` evaluation bank with seed 20261012;
- 1,000 training and 5,000 evaluation scenarios;
- the six-value C grid;
- 9,999 bootstrap resamples with a fixed seed;
- the analysis contrasts;
- `code_sha256` for every research module the runner imports.

Then write the reservation manifest and `track_r_freeze.json`, containing the protocol hash, and commit them before any generation.

### V03 freeze milestone - 10 October 2026

- [x] `research/freeze_track_r.py` transcribes the [analysis specification](docs/research/execution/analysis_specification.md) into the [protocol](docs/research/execution/track_r_protocol.json). It refuses to run with uncommitted code or with any existing reserved bank.
- [x] The protocol pins code by git blob id; `load_protocol()` accepts the committed freeze.
- [ ] V04 has not been run. User authorization and an independent analysis check are pending.

Commits:
- `7e456a2`: freeze tool and blob-id pinning;
- `8903632`: protocol, reservation and freeze record.

Freeze record: no scientific outcome accessed and no reserved bank file present.
The one prior label-free contact is recorded in the reservation manifest: an
integration accuracy check under the configuration's noise covariance.

**Why V04 waits.** It permanently consumes the reserved holdout, and Report 2
asks for a separate analysis owner first. This is a user-owned decision, not a
technical blocker. Same-assistant evidence exists:
- boundary-null tests: `tests/test_research_track_r_analysis.py`;
- the label-permutation invariance test;
- bank-combined coverage of 0.950-0.966 in simulation.

**If authorized,** run V04 with the command in the checkpoint table. Then
summarize with the frozen rules, keeping null, inconclusive and adverse results.
Do not regenerate, extend or retune anything. A01 can proceed meanwhile.

### A01 milestone - 10 October 2026

- [x] Contract committed before fitting (`fa92928`).
- [x] Refit under the frozen choices: `real_retrospective_20261010_v1`.
- [x] Analysis `real_summary_20261010_v2` and post-hoc quality addendum `real_quality_20261010_v1`.
- [x] Exposed labelling throughout; nothing pooled with simulation.

Evidence: [report](docs/research/results/real_2026-10-10/report.md), [quality](docs/research/results/real_quality_2026-10-10/report.md),
and commands in [V02 record](docs/research/execution/v02_development.md).
The earlier `real_summary_20261010_v1` failed on a too-strict optimizer check and
is retained as a failed run.

Next: draft the A02 claim-evidence register for development, A01 and protocol
claims, leaving the V04 rows visibly pending. V04 still waits on the user.

