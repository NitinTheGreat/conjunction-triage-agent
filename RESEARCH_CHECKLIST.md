# Research execution checklist and assistant handoff

**Project:** ConjunctionTriage  
**Created:** 6 October 2026; **last checkpoint:** 9 October 2026
**Purpose:** carry the project from the research reports to a defensible paper, with work resumable by Codex, Claude Code, or another coding assistant using this file and the repository.

This is the live execution record. Update it as work happens. Checked preparation tasks describe work already evidenced in the repository; unchecked implementation and experiment tasks remain to be done. A completed task can produce a negative or inconclusive finding. A checkbox does not mean that the proposed method succeeded or that a paper is accepted.

## 1. Resume here

| Field | Current checkpoint — replace after each work session |
|---|---|
| NOW | First research cycle complete: P01-P04, D01-D04, B01-B04, M01-M02, S01-S03, F01-F02; W01 manuscript skeleton exists. **Decision: NARROW**, not method superiority. |
| NEXT | **V01 - closest-work compatibility review**, then V02: distinct simulation controls, latest-metadata comparator, matched new-information training, ablations and precision planning. |
| Active task / owner | V01 in progress: primary-source methods/code retrieval and comparator compatibility review. |
| Selected direction | **Track R, narrowed:** controlled robustness/measurement benchmark. Grouping remains a candidate and may be discarded if simpler controls explain results. |
| Conditional extension | **Track E:** independent real-data efficacy, only after access and statistical requirements pass. |
| Research blockers | None preventing V01/V02 preparation. Full methods for some close papers and independent operational data remain unavailable; no novelty or real efficacy claim is established. |
| Current machine | Windows, PowerShell; repository at `F:\conjunction-triage`; Python environment at `.venv\Scripts\python.exe`. Paths elsewhere in this file are relative to the repository root. |
| HEAD when this checklist was created | `89d7f2efb8bf135e02fa51760e0ed3bb33a105c9`; working tree contains pre-existing modifications and untracked files. |
| Latest validation | **349 passed, 1 skipped** in 47.40s on 9 October; five input runs passed checksum/metric/fold audits, all eight frozen files and 57 raw/historical files unchanged. See execution verification and synthesis audit. |
| New scientific runs | Completed **development** runs: data v2, CV v2 (11 arms x 5 folds), two-stage v1, simulation v1, mechanism v1, synthesis v1 and two-stage reconstruction v1. No frozen confirmatory evaluation yet. |
| Scientific holdout status | Seed 20261012 / scientific:00000..04999 reserved **but not generated**. Candidate anisotropic configuration and sample size still need V03 freeze. Kelvins and all pilot banks are exposed. |
| Running jobs / processes | None from this session. Failed data v1 and CV v1 are retained with explicit failure reasons; all later named runs complete. |
| Next executable command | `Get-Content -Encoding UTF8 docs/research/execution/feasibility_decision.md`, then inspect the dated primary-source ledger for V01. No V02 successor runner exists yet; implement and test it before launching. |

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

- [ ] **V01 — resolve the closest-work comparison.** Depends on: F02; literature acquisition may start earlier. **Do:** inspect enough accessible full methods/code for the relevant Sánchez weighting/classification approach, a strong sequence/ensemble family, and applicable fusion alternatives. Track TimeQuery, Ouari, the TCN–Transformer, and AMOS fusion work without mixing their targets. **Expected:** compatibility table with dataset, label, horizon, split, inputs, calibration, metric, and reproduced/adapted/approximate/discussion-only status. **Done when:** the selected comparison is justified and remaining inaccessible details explicitly limit claims. Do not stall all local work while waiting for a paper.

- [ ] **V02 — complete strong comparators, ablations, and precision planning.** Depends on: F02, B04, V01. **Do:** implement feasible close comparators; remove grouping/age/OD components separately; compare oracle versus observed provenance only where lineage is known. Use development results for sample-size and runtime planning. **Expected:** development comparison package, tuning budgets, simulator sensitivity plan, and precision/power report. **Done when:** the study size and primary comparator are justified, all arms share an honest evaluation, and ineffective complexity is not retained solely for a headline.

- [ ] **V03 — freeze the scientific Track R protocol.** Depends on: V02, S02. **Do:** fix one primary method, comparator, overlap/noise condition, sample size, scenario partition, clipped log-loss rule, paired contrast, uncertainty procedure, secondary analyses, failure policy, and all software/configuration hashes. **Expected:** immutable `protocol.json`, reservation/access manifest, and freeze record. **Done when:** the freeze precedes scientific outcome access and every item in Report 2's freeze checklist is addressed. A draft document or timestamp alone does not satisfy this task.

- [ ] **V04 — run the held-out scientific simulation evaluation.** Depends on: V03. **Do:** execute the frozen run; retain all scenarios, failures, and planned secondary conditions. Compare the overlap-induced change in loss for method versus comparator, with absolute loss and new-information controls. **Expected:** complete run manifest, predictions, scenario-level paired analysis, intervals, and deviation log. **Done when:** all planned outputs are traceable and the conclusion follows the frozen rule. Do not tune on these outcomes and keep calling them untouched.

- [ ] **A01 — finalize retrospective real-CDM analysis.** Depends on: V03, B04. **Do:** generate the selected real-data comparisons, calibration, workload/miss frontiers, censoring diagnostics, and mission/quality sensitivity under the frozen analysis choices. **Expected:** separate retrospective tables and failure analysis. **Done when:** exposed-data results are labeled as such and are not pooled with simulation or new-real-cohort confirmation into an ambiguous test score.

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
