# Phase 9 — The working system

Physics validated against the answer key, served over an API, exposed as an MCP server,
with a frontend demonstrating the whole pipeline.

This phase is **engineering, not research**. It makes no new claim about whether an agent
triages conjunctions well. The Phase 7 result stands unchanged and unamended: the agent
scored L = 1.6606 against the latest-CDM baseline's L = 0.6940, and nothing built here
moves that number.

---

## 1. The headline — reproducing the TraCSS `prob` column

**An independent implementation of Alfano (2004) reproduces the published `prob` column to
a median ratio of 0.9999945 — 5.5 parts per million — with 100% of events agreeing to
within 0.1%.**

`scripts/validate_pc.py` recomputed Pc for 10,000 randomly sampled events from each answer
key and compared against the published value.

| | SFSH | Spherical |
|---|---:|---:|
| Sampled | 10,000 | 10,000 |
| Failed to compute | 0 | 0 |
| Censored, excluded from the ratios | 1,457 | 7,484 |
| **Comparable** | **8,543** | **2,516** |
| Median log₁₀(ours/theirs) | **−2.384 × 10⁻⁶** | **−2.400 × 10⁻⁶** |
| Quartiles | [−2.464, −2.304] × 10⁻⁶ | [−2.595, −2.142] × 10⁻⁶ |
| Full range | [−5.29, +5.92] × 10⁻⁶ | [−7.72, +2.53] × 10⁻⁶ |
| Within 0.1% | **100.00%** | **100.00%** |
| Within a factor of 2 | 100.00% | 100.00% |
| Within an order of magnitude | 100.00% | 100.00% |
| Disagreeing by more than 2 orders | **0** | **0** |

The phase asked for every disagreement beyond two orders of magnitude to be investigated.
There are none. The largest disagreement anywhere in 11,059 comparable events is
7.7 × 10⁻⁶ in log₁₀ — a ratio of 1.0000178.

### Breakdowns

The residual is flat across every cut the phase asked for, which is itself the finding: a
disagreement concentrated in diluted covariances or ill-conditioned matrices would point at
a real modelling difference, and there is no such concentration.

| Cut | n (SFSH) | Median log₁₀ ratio |
|---|---:|---:|
| Robust (dilution = 0) | 2,747 | −2.389 × 10⁻⁶ |
| Diluted (dilution = 1) | 5,796 | −2.383 × 10⁻⁶ |
| Condition number < 10³ | 3,545 | −2.388 × 10⁻⁶ |
| Condition number 10³–10⁶ | 4,993 | −2.383 × 10⁻⁶ |
| Condition number 10⁶–10⁹ | 5 | −2.190 × 10⁻⁶ |
| Miss < 1 km | 261 | −2.383 × 10⁻⁶ |
| Miss 1–5 km | 1,009 | −2.389 × 10⁻⁶ |
| Miss 5–10 km | 1,292 | −2.384 × 10⁻⁶ |
| Miss ≥ 10 km | 5,981 | −2.384 × 10⁻⁶ |

### Where the remaining 5.5 ppm comes from

It is systematic, not scatter: the interquartile range is 1.6 × 10⁻⁷ wide around a median
of −2.4 × 10⁻⁶. TraCSS publishes `prob` to eight significant figures, so the file resolves
differences down to about 10⁻⁸ relative — the residual is roughly 500× larger than the
file's own precision and therefore real, not rounding. The most likely cause is a small
difference in quadrature resolution. It was not chased further: at 5.5 ppm it cannot affect
any decision this system supports.

An earlier version of this measurement reported −6.6 × 10⁻⁵, and **the bias was ours**.
Integrating the disc directly in *x*, Simpson's rule meets the square-root singularity of
the chord half-width at the rim of the disc, where it converges at only O(h^1.5); at 200
intervals it under-read the disc area by 1.46 × 10⁻⁴ relative, and that landed straight on
Pc. Substituting *x = R sin t* makes the integrand smooth and restores O(h⁴). The bug was
visible only because the reproduction was measured in parts per million rather than
declared successful at "within a factor of two". `tests/test_orbital.py` holds it against a
closed form.

### Two independent checks that cannot be circular

Neither quantity is used anywhere in computing our Pc, so agreement on them is evidence
about the inputs rather than about the method.

| Quantity | SFSH | Spherical |
|---|---:|---:|
| Miss distance, max absolute error | 8.08 × 10⁻⁶ km | 6.02 × 10⁻⁶ km |
| `mdistance` (3D), median relative error | **1.25 × 10⁻⁷** | **2.60 × 10⁻⁷** |
| `mdistance` (2D encounter plane), median relative error | 3.30 × 10⁻³ | 1.94 × 10⁻³ |

The Users Guide does not say whether its `mdistance` is two- or three-dimensional. Computing
both settles it: it is the 3D distance. That agreement, to eight significant figures, is
what independently pins down the covariance units (km²) and the UVW→ECI rotation.

### Framing

**This reproduces TraCSS's published method. It does not validate Pc against reality.**

No collision occurs anywhere in this dataset, and `prob` is itself a computed quantity, not
an observation. The Users Guide states directly that "direct comparison of Pc values
requires the same method of Pc computation and is therefore not a key metric of this
dataset" — which is precisely why this compares like with like and is called a
reproduction throughout. What it establishes is that an independent implementation of the
same published method, given the same inputs, lands on the same number. Nothing more.

---

## 2. Covariance conditioning — the decision, and the counts

**The choice: eigenvalue flooring, reported per call, never silent.** Any eigenvalue below
10⁻¹² of the largest is raised to that floor. A matrix whose *negative* eigenvalue exceeds
10⁻⁶ of the largest is not a rounding artefact, is not a covariance, and raises instead of
being repaired.

Rejection was the alternative and was rejected: dropping non-PSD covariances would silently
remove exactly the diluted, badly-determined events that matter most operationally.
Flooring keeps them and makes the repair visible in a `ConditioningReport` attached to every
result, so a caller can see whether a given Pc rested on a repaired matrix.

### Counts in the 20,000 sampled events

| | SFSH | Spherical |
|---|---:|---:|
| Non-PSD combined 3×3 input | 0 | 0 |
| Repaired 3×3 covariance | 0 | 0 |
| Repaired 2×2 projection | 0 | 0 |

Zero, in both. Non-PSD covariances exist in the benchmark but are rare — 33 events in
1.2 million — so a random 20,000 contains none. That is why the gate also runs all of them.

### The 33 events TraCSS itself could not compute

The Users Guide says a NULL `prob` means their own computation failed, most likely on a
non-positive-definite covariance. There are 13 such rows in SFSH and 20 in Spherical. The
gate runs every one.

| | SFSH | Spherical |
|---|---:|---:|
| Rows | 13 | 20 |
| At least one non-PSD **per-object** covariance | **13 (all)** | **20 (all)** |
| Non-PSD **combined** covariance | 5 | 10 |
| We refused | 0 | 0 |
| We computed a value | 13 | 20 |
| … on a repaired 3×3 | 5 | 11 |
| Range of the values we produced | 2.0 × 10⁻³⁴ – 1.6 × 10⁻¹⁵ | 4.7 × 10⁻³⁰ – 3.4 × 10⁻¹⁴ |

Two things follow, and both are worth stating plainly.

First, **the Users Guide's explanation checks out**: every one of the 33 has at least one
non-PSD object covariance. Nothing else needs to be invoked.

Second, **we compute where they declined**, and that is not obviously the better behaviour.
The sum of a bad covariance and a good one can be positive-definite, which is why only 5 of
13 combined matrices are non-PSD. Where the combined matrix is PSD the computation is
well-posed; where it is not, the flooring repairs it and the report says so. Every value we
produce for these rows is below 3.4 × 10⁻¹⁴, far under the 1e-10 reporting floor, so
nothing operationally meaningful rides on the difference. They are excluded from every
agreement statistic above, because there is nothing to agree with.

### A defect this uncovered

The PSD check originally ran only on the projected 2×2 matrix. **A non-PSD 3×3 can project
to a perfectly healthy-looking 2×2** when the bad direction falls outside the encounter
plane — so on the 13 SFSH rows, where the input was bad in all 13, the after-the-fact check
flagged 1. `pc_from_states` now conditions the combined 3×3 *before* projecting and reports
that separately. Healthy rows are unaffected: the Spherical median ratio is unchanged at
−2.400 × 10⁻⁶ either way.

---

## 3. Frame transforms

`orbital/frames.py`. The conventions are written down because frame confusion produces a
plausible number rather than an error.

### UVW, defined per object

| Axis | Name | Definition |
|---|---|---|
| U | radial | `r / |r|` |
| V | in-track | `W × U` |
| W | cross-track | `(r × v) / |r × v|` |

V is **not** `v / |v|`. For an eccentric orbit the velocity is not perpendicular to the
radius, so the in-track axis is built from the cross-product to keep the triad orthonormal;
for a circular orbit the two coincide. `tests/test_orbital.py` holds the distinction with an
explicitly eccentric state.

### The transform that matters

TraCSS publishes each object's covariance in **that object's own** UVW frame. Two objects in
different orbits therefore have covariances in two different rotated frames, and **they
cannot be summed until each is rotated to ECI**:

```
C_eci = R C_uvw Rᵀ,   R = [U | V | W] expressed in ECI
```

`pc_from_states` takes `covariance_frame` as a required argument with no default, and so do
`POST /pc` and the MCP `compute_pc` tool. This is not defensive API design for its own sake.
On one test geometry — two objects in genuinely different orbital planes, with in-track
dominated covariances — the two readings of the identical input differ by **3.35 × 10⁷×**.
Nothing raises. A default would be a correctness bug wearing the costume of a convenience.

Check 3 of `verify_phase9.py` re-derives that factor and then asserts the field is required
in both schemas, in that order: if the frames agreed, requiring the argument would be
pedantry rather than correctness.

### Encounter plane

Perpendicular to the relative velocity. Under the short-encounter approximation the objects
pass fast enough that motion along the relative velocity contributes nothing to the
collision integral, so the 3D problem collapses to a 2D one in this plane. The first basis
axis is taken along the projected relative position; the in-plane rotation does not affect
the probability — the integration region is a circle — but fixing it makes intermediate
values reproducible.

### SGP4 and TEME

`orbital/propagate.py` produces **TEME**, not J2000 — that is what SGP4 natively yields.
The difference is a small rotation common to both objects, and Pc depends only on their
*relative* geometry, so it cancels. It would not cancel if an SGP4 state were mixed with a
state in another frame, which this project never does. Verified against the Vallado
satellite 88888 case at 360 minutes past epoch: **position residual 5 micrometres**,
velocity residual 0.0003 mm/s.

A first attempt at those reference constants was transcribed from memory, used values
belonging to a different satellite, and reported a 15,746 km residual against a propagation
that was in fact exactly correct. They are now read from the `sgp4` package's own
`tcppver.out`, the official Vallado verification output.

---

## 4. What is served

### HTTP API — `api/main.py`

| Endpoint | Purpose | Needs |
|---|---|---|
| `GET /health` | per-subsystem availability | nothing |
| `POST /pc` | Alfano 2004 Pc from two states and covariances | nothing |
| `POST /screen` | close approaches between two TLEs in a window | nothing |
| `GET /events` | read-only query over the TraCSS benchmark | ingested benchmark |
| `POST /triage` | the reasoning agent over Kelvins CDM series | Kelvins + an LLM key |

OpenAPI at `/docs`. Two invariants hold across all of it.

**Every response carries provenance** — the dataset, the method, the units, the frames, and
what the number does not establish. For `/triage` the provenance leads with the fact that
the agent lost, because serving its predictions without that would be presenting a worse
estimator as a product.

**No path returns a bare 500.** Validation failures, undefined-Pc refusals, propagation
failures, a missing dataset and a missing credential each map to a structured `ErrorBody`
with a stable code; a catch-all logs the traceback server-side and returns a request id.

CORS is restricted to an explicit localhost origin list rather than `*`. This server reads a
local dataset and can spend money on LLM calls; a page on any origin being able to drive it
is not a trade worth making.

Verified against a live `uvicorn` server, not only the test client. `/triage` reproduced
`test:100` and `test:1001` exactly as recorded in the Phase 7 predictions.

### MCP server — `mcp_server/`

| Tool | Purpose |
|---|---|
| `fetch_conjunctions` | query the benchmark |
| `compute_pc` | Alfano 2004 Pc |
| `get_object_metadata` | hard-body radius and conjunction history for one object |
| `triage_events` | run the agent over Kelvins series |

The descriptions are as much the deliverable as the code. A tool description is the entire
briefing the calling model gets before it chooses arguments, so every quantity states its
unit, every vector its frame, and three things are repeated because getting them wrong is
silent rather than loud: `pc` is censored at 1e-10 and a floored value is a bound;
`covariance_frame` is required; and `triage_events` says outright that the agent lost and
returns `baseline_risk` beside `agent_risk`. `verify_phase9.py` check 5 asserts those
statements are present, as functional requirements rather than prose.

Tools return `{ok: false, error, hint}` rather than raising — a raise reaches the model as a
transport failure carrying no explanation.

`mcp_server/verify_client.py` is a real client, not a double: it spawns the server as a
subprocess, completes the handshake, lists the tools, checks every description, and calls
three of them including a deliberately non-positive-definite covariance. Verified against
mcp 2.1.0.

### Frontend — `frontend/`

A copy of the frozen Phase 3 `viz/` with three tabs added: a live Pc calculator, a triage
panel, and the Phase 7 results table. `viz/` itself is untouched.

Graceful degradation is the design. The page probes `/health` once; with no API, the live
controls are disabled with an explanation of what to start, and the 3D geometry,
distribution charts and results table all keep working from static exports. Nothing ever
falls back to a stale or fabricated value — if the server cannot answer, the panel says so.

The Pc panel loads a real SFSH event's covariance magnitudes, where in-track uncertainty
dominates by three orders of magnitude. Switching `covariance_frame` and recomputing moves
the answer from 3.087 × 10⁻⁷ to 1.973 × 10⁻⁶. The page makes the claim and the reader can
check it in two clicks.

Verified in headless Chromium against a live server and again with it stopped. That caught a
bug nothing else would have: the hard-body-radius inputs carried `step="0.1" min="0.001"`,
so their own default values were a step mismatch, the form never validated, and the submit
event never fired. The button looked live and did nothing. Node syntax checks, HTML
structure checks and DOM id resolution all passed while it was broken.

### Reproducibility

`python scripts/reproduce.py` goes from a clean clone to the Phase 7 headline table. It
refuses two conveniences deliberately: it will not download the data, and it will not re-run
the agent without `--with-agent`. Every row of the printed table says whether *this*
invocation produced it or whether it came from an earlier run — a table that cannot tell a
fresh number from an inherited one is not a reproduction.

---

## 5. What this phase does not establish

**It does not establish that Pc is correct.** It establishes that two implementations of
Alfano 2004 agree to 5.5 ppm. Whether Alfano 2004 is the right model for a given encounter
is a separate question this project has not touched, and no collision outcome exists
anywhere in the data to settle it.

**It does not establish that the screening is right.** `POST /screen` propagates TLEs, whose
accuracy is typically kilometres and is not modelled here. A close approach found that way
is a candidate for assessment, not an assessment.

**It does not change the Phase 7 result.** The agent still lost by 2.4×. Building an API
around a worse estimator does not improve it, which is why every surface that serves the
agent also serves the baseline and says which one won.

**It does not make anything here operational.** Public orbital data must never be used for
operational collision avoidance. The benchmark is a screening validation dataset, the
Kelvins events are anonymised and time-shifted with no TCA and no catalogue identity, and
nothing in this system is a live feed.

**The Dockerfile is not build-verified.** The Docker daemon is not running on this host, and
starting it plus pulling a gigabyte of wheels was not something to do uninvited. Every
`COPY` source was checked to exist and the instruction set is valid, but the image has not
been built. It is the one deliverable in this phase that was written rather than executed.

---

## 6. On novelty

**A comparable open pipeline already exists.** Gazagnaire published one in April 2026 — an
OCaml implementation with a browser globe, covering the same ground from TLE ingestion
through conjunction screening to a rendered visualisation.

So this phase is engineering completeness, not a novelty claim. What it contributes is not a
new capability but a measured one: the Pc implementation here is checked against a published
answer key at parts-per-million resolution and reports its own conditioning decisions, and
the agent it serves is one whose performance was measured against baselines and found
wanting. The value of the system is that the numbers it produces come with their provenance
and their limits attached, not that it produces numbers nobody could produce before.

---

## 7. Verification

`python scripts/verify_phase9.py` — **8/8 pass**.

| # | Check | Result |
|---|---|---|
| 1 | SGP4 reproduces the published reference state | 5 μm position residual |
| 2 | Pc reproduces the TraCSS column on ≥ 10,000 events | 100% within 0.1%, both keys |
| 3 | The covariance frame is required, and matters | 3.35 × 10⁷× apart; required in both schemas |
| 4 | Every endpoint exists and no path returns a bare 500 | 5 endpoints, 4 failure paths structured |
| 5 | MCP descriptions state their units and caveats | 4 tools, all complete |
| 6 | Censored values are never served unmarked | across MCP, API and the gate |
| 7 | The Phase 7 frozen manifest is untouched | 8 blob hashes match; `viz/` untouched |
| 8 | `reproduce.py --check` and the offline suite pass | 286 tests |

Every check is written so a vacuous pass fails: an empty tool list, a zero-row comparison, a
manifest with no artefacts and an empty commit window all raise rather than passing quietly.

All eight earlier phase suites remain green: phase1 7/7, phase2 9/9, phase3 9/9, phase4 9/9,
phase5 9/9, phase6 10/10, phase7 7/7.
