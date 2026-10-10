# A03 independent reproduction guide

For a reviewer who did not run the original work. Same-assistant reruns do not
count as independent review: record who ran each step and what was checked. The
guide is ordered from cheapest (no data needed) to most expensive (full
refits).

## 0. Setup

- Check out the repository at the commit named in the claim register.
- Read `RESEARCH_CHECKLIST.md`: "Resume here", then the V02-V04 and A01 entries.
- For steps 2 onward, obtain the ignored `processed/research/` run directories and
  `dataset/` files listed in each run manifest. A clone alone is not enough.
- Python 3.11 with `requirements.txt` (plus `requirements-sequence.txt` for neural
  runs). Set `LOKY_MAX_CPU_COUNT`, `OMP_NUM_THREADS` and `MKL_NUM_THREADS` to 2.

## 1. Without data: committed bundles and claims

```powershell
.\.venv\Scripts\python.exe -m research.verify_exports --root docs/research/results
.\.venv\Scripts\python.exe -m research.claim_register
```

Expected:
- `verify_exports`: every bundle passes;
- `claim_register`: all non-pending claims regenerate.

This checks that the stated numbers match the committed tables, not that the
tables are right.

## 2. Frozen protocol and authorization

- Check that `docs/research/execution/track_r_protocol.json` was committed
  (`8903632`) before any `scientific` or `scitrain` file existed. Compare commit
  times with the V04 run manifest's `started_utc`.
- Run `python -c "from research.track_r_scientific import load_protocol; load_protocol()"`
  at the freeze commit. It must accept the protocol, which pins 45 files by git
  blob id.
- Read `track_r_authorization.json`. The pre-run independent check was waived;
  steps 3 and 4 below supply the post-hoc version.

## 3. Decision rule on boundary cases (Report 2 freeze item)

Independently implement, or at least inspect,
`research/track_r_analysis.bank_combined_interval` and
`combined_one_sided_p`. Then:

1. Simulate scenario x bank matrices whose mean is exactly 0.02, with right-skewed
   scenario effects (for example exponential), K = 10 and n = 5,000. Confirm that
   "material degradation confirmed" occurs in at most about 2.5% of replicates.
2. Repeat with mean exactly -0.01 for the S2/S3 nulls and -0.02 for S1.
3. Zero-discordance misses: `reuse_miss_summary(0, 0, n)` must give an upper
   bound of 1 - 0.025^(1/n) and a McNemar p of 1.

Compare against `bank_interval_validation_20261010_v1` (coverage 0.950-0.966)
and `tests/test_research_track_r_analysis.py`.

## 4. V04 recomputation from saved predictions

With `processed/research/track_r_scientific_20261010_v1`:

- Recompute the SHA-256 of `predictions_unlabeled.parquet` and compare it with
  `phase2_commit.json`.
- Join `sealed_labels.parquet` yourself (y = final_risk >= -6). Recompute
  clipped log loss (1e-6) and the P1 per-scenario matrix: singleton minus
  latest_metadata, overlap_90 minus no_reuse, one column per training bank.
- Recompute the estimate, the bank-combined interval (B = 9,999, seed 20261391)
  and the decision. Compare them with `analysis.json` and the V04 bundle report.
  Independent code may differ in the last digits of bootstrap bounds; any
  decision difference is a discrepancy.

## 5. Optional full rerun

`python -m research.track_r_scientific --run-id <new id>` reproduces V04 only
from the unchanged frozen protocol, and generation is deterministic from the
reserved seeds. The scientific outcomes are already exposed, so a rerun checks
computation, not confirmation. The development campaigns (`sensitivity_*`,
`components_*`, `sequence_*`) can be rerun from their committed contracts under
new run IDs.

## Discrepancy log

Record every difference in `docs/research/execution/a03_discrepancies.md` with
the step, the observed and expected values, the tolerance and the resolution.
Unresolved differences go into the manuscript's limitations.
