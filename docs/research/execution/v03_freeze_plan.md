# V03 freeze plan: Report 2 checklist mapped to artifacts

Prepared 10 October 2026, during V02. **This is a plan, not the freeze.** V03
requires V02 acceptance first. The freeze is an immutable `protocol.json`, a
reservation/access manifest and a freeze record, all committed before any
scientific scenario exists.

| Report 2 freeze item | Planned source | Status |
|---|---|---|
| Selected claim track | Track R, narrowed benchmark ([F02](feasibility_decision.md), [roadmap](../2026-10-06/03_RESEARCH_DIRECTION_AND_PAPER_ROADMAP.md)) | Decided |
| Event population and estimand | [Analysis specification](analysis_specification.md) §1; unweighted enriched latent scenarios | Drafted |
| One primary method and comparator | P1, singleton versus latest_metadata ([primary contrast](primary_contrast.md)) | Proposed |
| Partition construction and field semantics | `research/history.py` and `research/components.py`, frozen by hash | Code exists |
| Model/calibration training membership | Scientific training banks under a new reservation; inner folds by fixed seed | Waits on §3 bank design |
| Optional risk-calibration membership | None; no risk certificate is claimed | Decided |
| Prediction horizon | Latest message at the 2-day cutoff; matched latest window | Fixed by generator |
| Action/failure policy | Nominal 95% training-recall threshold (descriptive); stop on any failure | Drafted |
| Primary contrast and direction | Degradation at overlap_90; positive means history degrades more | Proposed |
| Margins and justification | 0.02 nats for P1; delta_m for S2/S3 | P1 proposed; delta_m pending |
| Inference implementation and tolerances | t versus bootstrap-t; resample count and seed | Waits on interval validation |
| Multiplicity families | P1 alone; Holm over S1, S5, S6, S2, S3 | Drafted |
| Simulation distribution, seeds, configurations, lineage oracle | Candidate configuration (ratio 4, 30 degrees) unless §4 changes it; evaluation seed 20261012; new training-bank seeds | Waits on §4 |
| Sample-size/power assumptions | Provisional 5,000 evaluation scenarios ([precision report](../results/precision_2026-10-10/report.md)) | Waits on §3/§4 |
| Software/data hashes | `protocol.json` lists code SHA-256 values, contract hashes, environment and requirements | At freeze |
| No outcome-derived grouping, features or thresholds | Two-phase evaluation and label-insensitivity tests | To implement in the V04 runner |
| Separate analysis owner checks | Boundary-null and zero-discordance simulations; second reviewer | To arrange (A03-type) |
| Amendment policy | Analysis specification §7 | Drafted |

## Software that must exist before the freeze

The frozen hashes must cover the code that will run, so these come first.

1. **V04 runner:**
   - generates the reserved evaluation bank and the new training banks from the
     frozen protocol;
   - fits the four arms with the frozen grid and rules;
   - writes predictions and model hashes before reading evaluation labels;
   - computes P1 and the secondaries with the frozen interval method and rules.
2. **Tests:** run the runner end to end on **development** seeds and identifiers
   only, plus label-insensitivity, boundary-null and failure-path checks. The
   reserved seed and `scientific:` identifiers stay refused everywhere except
   the frozen V04 entry point.
3. **Reservation manifest:** add the new training-bank seeds before any
   generation.

Generating the scientific bank is the user's decision to authorize after V03 is
reviewed. Record that authorization in the checklist when it is given.
