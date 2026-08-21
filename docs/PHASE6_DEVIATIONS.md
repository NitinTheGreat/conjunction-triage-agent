# Phase 6 — Protocol Deviations

`docs/PHASE6_PREREGISTRATION.md` is immutable. Every departure from it is recorded here
instead, **before** the result it affects is observed. This file was committed before the
first API call of the primary run.

---

## Deviation 1 — provider and model

**Pre-registered (§7):**

> **Model.** A single Anthropic model, **temperature 0**, one prompt version.

**Actually run:**

| | |
|---|---|
| Provider | **gemini** |
| Model | **`gemini-3-flash-preview`** |
| Temperature | **0** (as pre-registered) |
| Prompt version | **`v1`** (as pre-registered, unchanged) |
| Scope threshold | **−7.0** (as pre-registered, unchanged) |

**Reason.** Provider flexibility was requested and the provider was fixed **before any
agent output existed** — no prompt, no verdict, no score had been observed at the moment
the choice was made. The pre-registration's purpose is to prevent an analysis choice being
made *after* seeing results; that protection is intact. Everything the pre-registration
exists to protect — the endpoint, the 50 splits and their seeds, the test, alpha, the
0.138 minimum important difference, and the five-outcome decision rule — is unchanged.

**Note on the model identifier.** The instruction that requested this deviation named
`gemini-2.5-flash` in one sentence and `gemini-3-flash-preview` in another. The value
actually configured in `.env`, and therefore actually used, is **`gemini-3-flash-preview`**;
that is what is recorded here and in every cache entry. The discrepancy is noted rather
than silently resolved.

**Commitment.** **No second provider will be run and reported as the primary result.** Any
later run under a different provider or model is **EXPLORATORY**, is reported separately
and after the primary result, and cannot replace the headline. The primary result is
whatever this single frozen configuration produces.

---

## Implementation notes — not protocol deviations

These changed **how** the run executes, not **what** it produces. The pre-registration
fixes the endpoint, splits, test, alpha, effect size, decision rule, scope and prompt;
none of those is touched. Recorded here for transparency.

### N1 — `max_tokens` raised 900 → 4000 → 8000

`gemini-3-flash-preview` reasons internally before answering, and those thinking tokens
are drawn from the same `max_output_tokens` budget as the answer. At 900 the model spent
the entire budget thinking and returned 32 tokens of truncated JSON — every response
failed to parse. At 4000, two events in ten still truncated after 3,840 thinking tokens.
8000 completes them.

Two defects in our own client were fixed alongside, both of which would have corrupted the
results silently:

* **Thinking tokens were not counted.** Only `candidates_token_count` was recorded, so
  roughly 80% of billable output was invisible and the cost figure would have been a large
  under-report.
* **Truncated responses were cached.** The client returned whatever text arrived without
  checking `finish_reason`, so a truncated answer was written to cache and replayed even
  after the budget was raised. `finish_reason == MAX_TOKENS` now raises, and `max_tokens`
  is part of the cache key so a budget change cannot replay an answer produced under a
  different one.

### N2 — requests issued concurrently (12 in flight)

Wall time only. Every call is independent, temperature is 0, cache keys do not depend on
ordering, and results are sorted by `series_id` before writing, so the output is identical
to a serial run. Serially the run would have taken about 16 hours.

### N3 — cost is higher than projected

Projected $1.09 for 1,215 calls; measured $0.0095 per call, so approximately **$11.60**.
The gap is thinking tokens, which the projection did not anticipate. **Token counts are
exact; the dollar figure is not** — public pricing for `gemini-3-flash-preview` was not
available, so it is priced at the `gemini-2.5-flash` rate and every reported cost should be
read as an estimate of that form.

---

## Further deviations — none recorded

Any deviation discovered during the remainder of the run is appended below with its reason,
before the affected result is interpreted.
