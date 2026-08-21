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

## Deviation 2 — none recorded

Any further deviation discovered during the run is appended below with its reason, before
the affected result is interpreted.
