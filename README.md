# ConjunctionTriage Agent

An agentic AI system that triages satellite collision warnings (conjunctions) and decides
which ones a spacecraft operator should actually act on. Every recommendation is measured
against labelled ground truth — the US Office of Space Commerce TraCSS IV&V conjunction
screening dataset — rather than judged by eye. The research question is whether an agent
that reasons over orbital physics, space weather and object metadata ranks collision risk
better than a fixed-threshold baseline.

## Governing principle

**The benchmark data defines the schema.** Live sources (CelesTrak, Space-Track) normalise
into [`ConjunctionEvent`](core/schema.py); never the reverse. The IV&V files carry state
vectors and 3×3 covariances that are exactly the inputs collision-probability computation
needs, so the schema is built around them and fields a live source cannot supply are
`Optional`.

## Standing constraints

These hold for every phase, not just the one that introduced them.

| # | Constraint |
|---|---|
| 1 | **Never load a full IV&V CSV into memory.** 913k × 45 columns will consume multiple GB. Use chunked or column-subset reads. |
| 2 | **`prob` is censored at `1e-10`.** It is a reporting floor, not a measurement. `ConjunctionEvent.pc_is_floored` flags it; any log-transform, ROC curve or distribution statistic must handle the censoring. |
| 3 | **No phase may hard-depend on a live network call to run its tests.** `celestrak.org` is unreachable from the development machine. The suite runs offline against `tests/fixtures/`. |
| 4 | **numpy 2.4, pandas 3.0, astropy 8.0** are major versions with breaking changes relative to most documentation. Verify APIs against the installed version. |
| 5 | **Fail loud.** No fallback silently substitutes a default. A missing or invalid value raises. |
| 6 | **`dataset/` is read-only.** Never modify, move or delete anything in it. `dataset/MANIFEST.md` is the only provenance record. |

## Phase roadmap

| Phase | Scope | Status |
|---|---|---|
| **1** | **Foundation** — reproducible repo, canonical `ConjunctionEvent` schema, config, offline test harness | **complete** |
| 2 | Data layer — chunked IV&V ingestion, HBR lookup from ScreeningVolumes, response cache | planned |
| 3 | Visualisation and exploratory analysis | planned |
| 4 | Physics — orbit propagation, Alfano collision probability, object metadata | planned |
| 5 | Space weather — NOAA SWPC, NASA DONKI, drag-risk signal | planned |
| 6 | Baseline — threshold ranker and metrics | planned |
| 7 | Agent — LangGraph graph, tool nodes, `rank_risk` reasoning node | planned |
| 8 | Evaluation — benchmark harness and ablations | planned |
| 9 | API and MCP server | planned |
| 10 | Frontend and paper packaging | planned |

## Setup

Requires Python 3.11 (developed on 3.11.9).

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows
# source .venv/bin/activate   # macOS / Linux
pip install -r requirements.txt

cp .env.example .env          # then fill in real values
```

`.env` ships with `your_..._here` placeholders. The project imports fine without
credentials — they are resolved lazily, and a component that needs one raises
`MissingCredentialError` naming the variable. Secret values are never logged or printed.

The 620 MB `dataset/` directory is gitignored and is **not** obtained by cloning. The test
suite does not need it; only Phase 2 onward does. See [`dataset/MANIFEST.md`](dataset/MANIFEST.md)
for provenance and checksums.

## Running tests

```bash
python -m pytest                        # 65 tests, offline, < 1s
python scripts/verify_phase1.py         # 7 end-to-end Phase 1 checks
python scripts/verify_phase1.py --skip-checksums   # skip the 620 MB rehash
```

Tests read only from `tests/fixtures/` (the first 50 rows of each IV&V file, committed),
so they pass on any machine with no network and no dataset. Regenerate the fixtures with
`python scripts/build_fixtures.py` if the dataset is present.

## Layout

```
core/          canonical schema (schema.py) and configuration (config.py)
data/          data-source clients
scripts/       build_fixtures.py, verify_phase1.py
tests/         offline suite + committed fixtures
dataset/       benchmark data (gitignored, read-only) + MANIFEST.md
docs/          per-phase reports
legacy/        frozen pre-Phase-1 code, reference only, not imported
```
