# Claim-evidence register (A02 draft)

`claim_evidence.csv` maps each quantitative statement intended for the paper to
the committed evidence that regenerates it. This is a draft: A02 also needs V04,
whose rows are marked `pending`.

| Column | Meaning |
|---|---|
| `evidence_type` | `exposed development simulation`, `exposed retrospective real data`, `protocol` or `pending scientific evaluation`. Types are never pooled. |
| `source`, `selector`, `column`, `statistic` | Repository-relative CSV, pandas query, column and `value`/`min`/`max`/`mean`/`count` that recompute the claim |
| `expected`, `tolerance` | Stated value and allowed difference |
| `uncertainty`, `limitations` | What the number does and does not support |
| `status` | `regenerated` (checked against the bundle), `documented` (cited file must exist) or `pending` (no value allowed) |

The register includes null and adverse findings: D05-D09, D11, D15, R04 and R06.
Verify it with:

```powershell
.\.venv\Scripts\python.exe -m research.claim_register
```

The verifier checks bundle content only. It does not judge whether a sentence
overstates its evidence; A03 review covers that.
