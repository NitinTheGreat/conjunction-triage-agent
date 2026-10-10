# W03 claim audit: weak claims supported or softened before drafting

**Date:** 10 October 2026. **Scope:** every statement in the previous draft
(`paper/manuscript.md`, commit `78760c0`) that was not tied to a regenerating
claim-register row, plus claims whose wording went beyond their evidence.

The user's request referred to a "weak evidence" list in a skeleton. No such list,
and no `.tex` skeleton, exists in this repository. This audit is its equivalent for
this paper. Each item below was resolved **before** the corresponding LaTeX section
was written. Register rows are in
[`claim_evidence.csv`](../claims/claim_evidence.csv) (67 rows after this audit:
54 regenerate from bundles, 13 cite a committed file).

## Supported (evidence added or located)

| # | Draft claim | Evidence now |
|---|---|---|
| 1 | Static 2D encounter-plane simulator; 80 observations with identities; first 60 visible; Gaussian posterior per window; risk = disk probability; label from all 80 | `research/simulation.py`; register X03; tested in `tests/test_research_web_findings.py` |
| 2 | Two independent quadratures verify the probability integration | X06 (worst relative difference 1.75e-7 on the scientific covariance) |
| 3 | Matched mixture: one objective unit per scenario, whole-scenario folds | X13 (`simulation_regimes.training_rows` asserts weight 1 per scenario; `scenario_folds`) |
| 4 | Between-bank SD of P1 about 3.6 times the overlapping-subset estimate | D10 (0.0080) and X07 (0.0022, analysis specification) |
| 5 | 18 of 40 scientific selections at the C edge; last-step gains at most 0.0011 | V15 and X05 (V04 record) |
| 6 | Predictions sealed before labels; analysis reconstructs exactly | X04 (`audit.json`: 1,400,000 rows, phase-2 hash verified, exact reconstruction) |
| 7 | Development summaries (covariance weighting, state fusion, LSTM, components) | X08-X11 (one report each); shortened to one sentence each in the paper |
| 8 | Pooled reuse misses 599 new / 33 recovered / 7,700 positive pairs | V16-V18 |
| 9 | Latest-message comparator miss rate 4.7% in every reuse condition | V19 |
| 10 | Post-hoc OD-quality strata | X12, labelled post hoc and exploratory |

## Corrected

| # | Draft wording | Problem | Paper wording |
|---|---|---|---|
| 11 | Grouping "takes the maximum calibrated score" | Order was wrong | The largest partition score is taken first and then calibrated (`models.py`, `MonotonePlatt`) |
| 12 | "The bootstrap-t corrects the right-skew asymmetry of the t interval" | Overstated; no numbers | In development simulation at n = 5,000 and skewness 4.5 (D22), the Student t interval's one-sided errors were 0.021 and 0.034 (D20, D19); the studentized bootstrap's were 0.026 and 0.029 (D21, D13), nominal 0.025 |
| 13 | "A label-permutation test confirms that predictions are label-independent" | The test runs on development data, not on the scientific run | A pipeline test shows on development data that permuting labels leaves predictions unchanged; in the scientific run, predictions were sealed before labels were read (X04) |

## Softened

| # | Draft wording | Problem | Paper wording |
|---|---|---|---|
| 14 | Reuse "removes the value of a history summary" through double counting | Conflates two mechanisms. With the latest message fixed, 90% overlap also leaves less *new* information in the history: 15 distinct observations against 60 without reuse (X03) | P1 measures the combined effect of a less informative history and a forecaster that cannot tell. Solution reissue, where the history adds nothing beyond the latest message, isolates the misreading of repeated messages; that contrast (S6) is exploratory |
| 15 | Lineage weighting fails because "timing, count and summary-shape features still respond to reuse" | Untested mechanism | Interpretation only: no reweighting can restore observations that the messages never used (15 of 60); presented as a likely reason, not a finding |
| 16 | Real-data agreement "is what one would expect if real CDM sequences carry substantial reuse" | Ignores a simpler explanation: later messages are closer in time to the final recorded risk, so a latest-message advantage is expected without any reuse | Consistent with reuse in direction, but not evidence for it |
| 17 | Statements about other papers' splits, horizons and calibration (Ouari, Zerrouki) | Based on publisher previews | Cited only for what their abstracts state |

## Removed from the paper

- Process details of earlier reviews (which pages of which source were inspected).
- Development results that rank neural and logistic families (D15 shows the LSTM epoch budget binds).

## Kept, with the evidence already in the register

Primary and secondary results (V01-V15), development persistence (D01-D07),
coverage (D11, D12), tuning (D14, D17, D18), real-data results (R01-R12).
