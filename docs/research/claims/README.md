# Claim-evidence register (A02)

`claim_evidence.csv` maps each quantitative statement intended for the paper to
the committed evidence that regenerates it. V04 rows (`V01`-`V10`) were added after the frozen run; no row is pending.

| Column | Meaning |
|---|---|
| `evidence_type` | `exposed development simulation`, `exposed retrospective real data`, `protocol`, `frozen scientific simulation` (V04) or `pending scientific evaluation`. Types are never pooled. |
| `source`, `selector`, `column`, `statistic` | Repository-relative CSV, pandas query, column and `value`/`min`/`max`/`mean`/`count` that recompute the claim |
| `expected`, `tolerance` | Stated value and allowed difference |
| `uncertainty`, `limitations` | What the number does and does not support |
| `status` | `regenerated` (checked against the bundle), `documented` (cited file must exist) or `pending` (no value allowed) |

The register includes null and adverse findings: D05-D09, D11, D15, R04, R06, V06 and V07.
Verify it with:

```powershell
.\.venv\Scripts\python.exe -m research.claim_register
```

The verifier checks bundle content only. It does not judge whether a sentence
overstates its evidence; A03 review covers that.
