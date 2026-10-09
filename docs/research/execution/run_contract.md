# Research run contract — 9 October 2026

`research.artifacts.Run` creates `processed/research/<run_id>/` exclusively. A reused ID is an error. New work never overwrites the historical corrected pilot or Phase 7 artifacts. A manifest transitions from planned to running, then complete or failed. An interrupted process can leave a running manifest: check its PID/log and mark the interrupted run explicitly before retrying with a new ID. File presence alone is not completion.

Each manifest records exact interpreter/arguments, working directory, code hashes, HEAD and dirty paths, declared input hashes, config, PID, timestamps, exposure records, and output hashes. Only explicit compute environment variables are saved; credentials are excluded. JSON rejects NaN/Infinity. Undefined or infinite metrics use null plus an explicit status. Parquet is written with DuckDB to avoid the host's PyArrow DLL restriction.

The development specification is `research/configs/development.json`. It is an exploratory design, not scientific preregistration. Split identities must be saved before fitting. No event/scenario variants cross folds. New simulation outcomes are protected only after an explicit reservation/access manifest; none is silently protected by a random seed.

## Required validation

Tests must reject run-directory reuse/path traversal, preserve failed status on exceptions, and reject non-finite JSON before replacing output. Model evaluation must retain failures and record the number of positives. A terminal complete manifest describes execution, not scientific superiority.

## Initial claim inventory

| Claim | Status | Evidence/action |
|---|---|---|
| Stored v1 LLM loses to B1 on the original metric | Historical reconstruction | Dated Report 1 and saved predictions; rescore anchors before comparing. |
| Historical B4/B5 or hybrid conclusions remain valid | Superseded | Phase 11 erratum; implement corrected comparisons. |
| Proposed grouping improves information-reuse robustness | Untested | Development controls and lineage simulation, then frozen scientific evaluation if justified. |
| Public OD metadata identifies reused observations | Unsupported | Proxy-only fields; quantify ambiguity and preserve unknown state. |
| Old raw archive supplies an independent cohort | Contradicted by overlap audit | Complete the full-column crosswalk. |
| Method reduces real operational workload safely | Not established | Track E requires new suitable data and adequate precision; current label is final reported risk. |

The current shell command and output path for every run belong in the execution log/checklist. Do not transfer secrets or assume Git includes `processed/`, `dataset/`, or `cache/`.
