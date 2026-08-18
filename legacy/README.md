# legacy/

Frozen copies of pre-Phase-1 code, preserved so nothing is lost. **Not imported by the
project.** Reference only.

| File | Origin |
|---|---|
| `data_init_at_19d6662.py` | Verbatim `data/__init__.py` at commit `19d6662`. Deleted in the working tree before Phase 1; recovered with `git show`. Defines the old CelesTrak/SOCRATES-shaped `ConjunctionEvent` and `fetch_conjunctions()`. |
| `celestrak_worktree.py` | Verbatim working-tree `data/celestrak.py` as of the Phase 1 audit. Defines `SatelliteTLE` and `fetch_tle_for_object()`. |

The old `ConjunctionEvent` here is **deliberately not restored**. The benchmark data
defines the schema: the TraCSS IVV files carry state vectors and 3x3 covariances that the
CelesTrak shape has no field for, and those are the inputs collision-probability
computation needs. See `docs/PHASE1_REPORT.md`.
