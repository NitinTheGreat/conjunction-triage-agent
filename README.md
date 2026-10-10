# ConjunctionTriage Agent

Does an LLM reasoning agent triage satellite collision warnings better than a one-line
baseline?

**No.** On a held-out test set the agent scored **L = 1.6606** against the latest-CDM
baseline's **L = 0.6940** on the official ESA Kelvins metric — **2.4× worse**, lower being
better. In a 10,000-resample paired bootstrap it was ahead in **0.0%** of resamples.

That is the finding, and it is stated first because the rest of the repository exists to
make it trustworthy: a task defined before anything was built, an evaluation protocol
committed before it was run, published baselines reproduced to four decimal places, and a
test set scored exactly once.

---

## The result

| Arm | L | MSE_HR | F₂ |
|---|---:|---:|---:|
| **B1 — latest CDM** | **0.6940** | 0.5129 | 0.7391 |
| B5 — two-stage GBM | 0.8978 | 0.5341 | 0.5949 |
| **Agent — LLM corrector** | **1.6606** | 0.8492 | 0.5114 |
| B2b — constant −5 | 2.5041 | 0.6788 | 0.2711 |
| B3 — linear extrapolation | 4.2217 | 2.9420 | 0.6969 |
| B4 — gradient boosting | 36.8784 | 1.8197 | 0.0493 |

2,167 test events, 150 of them truly high-risk. Paired difference agent − B1: median
**+0.9462**, 95% CI [+0.5119, +1.6152].

Two published figures were reproduced independently, which is what licenses the rest of the
table: our B1 lands on the published **LRP 0.694** to four decimal places, and our constant
−5 arm lands on **CRP 2.500** to three significant figures (arXiv:2008.03069, Table 3).

Full write-up: [docs/PHASE7_REPORT.md](docs/PHASE7_REPORT.md).
Whether the loss is a prompt artefact was tested separately and **exploratorily** in
[docs/PHASE8_EXPLORATORY_REPORT.md](docs/PHASE8_EXPLORATORY_REPORT.md); it does not amend
the result above.

---

## Reproduce it

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows;  source .venv/bin/activate elsewhere
pip install -r requirements.txt

python scripts/reproduce.py
```

That one command checks the environment, checks the datasets against their checksums,
builds every derived artefact that is missing, and prints the table above.

It deliberately will not do two things. It **will not download the data** — the TraCSS
files are 620 MB and Kelvins comes from a Zenodo record requiring accepted terms, so both
are placed by hand and verified against [`dataset/MANIFEST.md`](dataset/MANIFEST.md). And it
**will not re-run the agent** unless you pass `--with-agent`, because that spends about $7
of LLM calls; without it the agent row is labelled *from an earlier run* rather than
silently presented as fresh.

```bash
python scripts/reproduce.py --check        # verify and report; build nothing
python scripts/reproduce.py --fast         # skip the 620 MB re-hash and the Pc gate
python scripts/reproduce.py --with-agent   # re-run the LLM arm too (needs a key, ~$7)
```

A pinned container is in [`Dockerfile`](Dockerfile). It carries the code and dependencies;
the datasets are mounted at run time rather than baked in. See [Docker](#docker) below for
the full container and Compose workflow.

---

## Run the system

```bash
uvicorn api.main:app                                  # API + OpenAPI docs at /docs
python -m http.server 8001 --directory frontend       # the frontend, then open :8001
python -m mcp_server.server                           # MCP server over stdio
python -m mcp_server.verify_client                    # check the MCP server end to end
```

| Endpoint | What it does |
|---|---|
| `GET /health` | which subsystems are available, and which are not |
| `POST /pc` | Alfano 2004 probability of collision from two states and covariances |
| `POST /screen` | close approaches between two TLEs inside a window |
| `GET /events` | read-only query over the TraCSS IV&V benchmark |
| `POST /triage` | the reasoning agent over Kelvins CDM series |

Every response carries a `provenance` block naming the dataset, the method, the units and
the frames, and saying what the number does not establish. No path returns a bare 500.

The frontend degrades cleanly: with no API running, the 3D geometry, distribution charts and
results table all still work from static exports, and the live panels are disabled with an
explanation rather than showing a stale number.

The MCP server exposes `fetch_conjunctions`, `compute_pc`, `get_object_metadata` and
`triage_events` to any MCP client — see [`mcp_server/README.md`](mcp_server/README.md) for
the Claude Desktop and Claude Code configuration.

---

## Docker

```bash
docker build -t conjunction-triage .   # the backend image (default target, unchanged by Compose below)
docker run --rm conjunction-triage     # the offline 286-test suite — no data, no network, no credential
```

The full stack — the API, the live frontend, and the frozen viz snapshot — comes up together
with Compose:

```bash
cp .env.example .env          # fill in a credential only if you want /triage to work
docker compose up --build
```

| Service | Port | What it serves |
|---|---|---|
| `api` | `8000` | the FastAPI app (`api.main:app`); `/docs` for the interactive schema |
| `frontend` | `8001` | the live dashboard, nginx |
| `viz` | `8002` | the frozen Phase 3 snapshot, nginx |

```bash
docker compose run --rm api python -m pytest -q            # the offline suite, in-container
docker compose run --rm api python scripts/reproduce.py    # needs dataset/ mounted
docker compose down                                          # stop everything
docker compose down -v                                       # also wipe the processed/cache volumes
```

The dataset is never baked into the image: `api`'s Compose mount is `./dataset:/app/dataset:ro`,
the same pattern the plain `docker run -v` commands above use. `frontend/lib/` and `viz/lib/`
vendor a byte-identical copy of three.js; the Dockerfile builds it once into a shared stage so
neither the `frontend` nor the `viz` image pays for it twice. The `app` stage runs as a non-root
user.

The MCP server isn't a Compose service — it speaks stdio, not a port — so run it directly as the
`command` an MCP client launches, in place of the `.venv` path in
[`mcp_server/README.md`](mcp_server/README.md):

```bash
docker run -i --rm --env-file .env \
  -v "$PWD/dataset:/app/dataset:ro" -v conjunction-triage-agent_processed:/app/processed \
  conjunction-triage python -m mcp_server.server
```

One caveat: `api/provenance.py` reports the running git commit, but `.git/` is deliberately
excluded from the build context (see `.dockerignore`), so `code_version` in `/health` and every
response's `provenance` block reads `"unknown"` inside any container. That is expected, not a bug.

---

## Standing constraints

These hold everywhere in the repository, not only where they were introduced.

| # | Constraint |
|---|---|
| 1 | **Never load a full dataset into memory.** 913k × 45 columns is multiple GB. Use chunked reads or push the work into DuckDB. |
| 2 | **Floors are not measurements.** TraCSS censors `pc` at `1e-10`; Kelvins clips risk at `−30.0`. `pc_is_floored` marks them. Any log transform, average, ROC curve or ratio must handle the censoring or exclude it. |
| 3 | **No test may depend on a network call.** The suite runs offline against `tests/fixtures/`. `celestrak.org` is unreachable from the development machine. |
| 4 | **numpy 2.4, pandas 3.0, astropy 8.0** are major versions with breaking changes relative to most documentation. Verify APIs against what is installed. |
| 5 | **Fail loud.** Nothing silently substitutes a default. A missing or invalid value raises. |
| 6 | **`dataset/` is read-only.** `dataset/MANIFEST.md` is the only provenance record. |
| 7 | **A sample is not the population.** The visualisation sample over-represents rare high-probability events on purpose; never read a dataset proportion off it. |
| 8 | **The Phase 7 frozen manifest is immutable.** The published result must stay reproducible byte-for-byte. New work goes in new modules. |

---

## What the physics layer establishes

`orbital/` implements Alfano (2004) collision probability and SGP4 propagation, and both
are checked against something external rather than against themselves.

**Pc.** `scripts/validate_pc.py` recomputes Pc for 10,000 random events per answer key and
compares against the published `prob` column: median log₁₀ ratio **−2.4 × 10⁻⁶**, with
**100%** agreeing to within 0.1%. Two quantities that are never used in computing our Pc
agree independently — miss distance to 8 × 10⁻⁶ km, and the published `mdistance` to a
median relative error of 1.3 × 10⁻⁷ once it is identified as the 3D distance rather than
the encounter-plane one.

That is a reproduction of TraCSS's published method, **not** a validation of Pc against
reality. No collision occurs in this dataset, and the Users Guide says directly that
comparing Pc across different methods is not meaningful.

**SGP4.** Verified against the Vallado satellite 88888 case at 360 minutes: position
residual **5 micrometres**.

---

## Layout

```
core/          schema, config, metric, evaluation, features, DuckDB stores
orbital/       frames, Alfano Pc, SGP4 propagation and close-approach screening
agent/         the LangGraph triage agent and the provider-agnostic LLM client
api/           FastAPI application, request/response models, provenance
mcp_server/    MCP server over stdio, plus a live verification client
frontend/      the full interface: Phase 3 views plus live API panels
viz/           the frozen Phase 3 visualisation, unchanged
scripts/       ingestion, baselines, evaluation, reproduce.py, verify_phase*.py
tests/         offline suite (286 tests) and committed fixtures
docs/          per-phase reports, the pre-registration, the frozen manifest
dataset/       benchmark data (gitignored, read-only) + MANIFEST.md
```

---

## Tests

```bash
python -m pytest                    # 286 tests, offline, a few seconds
python scripts/verify_phase9.py     # the Phase 9 end-to-end checks
```

Every `verify_phase<N>.py` from 1 to 9 runs the checks for that phase. Tests read only from
`tests/fixtures/` — the first 50 rows of each file, committed — so they pass on any machine
with no network, no dataset and no credential.

---

## Credentials

Only `/triage` and the agent scripts need one.

```
LLM_PROVIDER=gemini          # or anthropic, or openai
LLM_MODEL=gemini-3-flash-preview
GEMINI_API_KEY=...
```

`.env` is gitignored; `.env.example` holds placeholders. Credentials are resolved lazily, so
everything imports and every test passes without them; a component that needs one raises
`MissingCredentialError` naming the variable. No secret value is ever logged, printed,
returned in a response, or written to a cache file.

---

## Not for operational use

Public orbital data must never be used for operational collision avoidance. The benchmark
is a screening validation dataset, the Kelvins events are anonymised and time-shifted, and
nothing here is a live feed.
