# EXPLORATORY — Prompt v2 (restraint), verbatim

**EXPLORATORY.** This prompt is not part of the primary result. The primary result is fixed
and published in [PHASE7_REPORT.md](PHASE7_REPORT.md): agent L = 1.6606 against B1 0.6940,
median paired D = +0.9462, 0.0% of resamples favouring the agent. Nothing produced with this
prompt can change, replace, amend or soften that finding
(see [PHASE6_PREREGISTRATION.md](PHASE6_PREREGISTRATION.md) §10.3).

Committed **before** v2 was run.

---

## What is held constant

Everything except the instruction text:

| | v1 (primary) | v2 (exploratory) |
|---|---|---|
| Scope | `latest_risk >= -7.0` | **same** |
| Model | `gemini-3-flash-preview` | **same** |
| Temperature | 0 | **same** |
| Evidence table | identical rendering | **same** |
| Cache mechanics | keyed on prompt version | **same** (so v1 and v2 can never collide) |
| Split seeds | 20260819–20260868 | **same** |
| Output schema | `predicted_final_risk`, `will_collapse`, `confidence`, `reasoning`, `evidence_cited` | **plus `revise`**; `predicted_final_risk` becomes conditional |

## What changes

1. The prompt states that **the latest observed risk is already correct more than half the
   time**, and that leaving it alone is the correct action absent strong specific evidence.
2. A required boolean **`revise`** is added. When `false`, the prediction **is** B1's,
   byte-identical, and the model must not emit a number at all — `predicted_final_risk` must
   be `null`.
3. When `revise` is `true`, the model must name **which specific evidence** justifies
   overriding a usually-correct default.
4. **No quota is given.** The prompt never states what fraction of events should be revised,
   and that fraction was not tuned against any result.

---

## v2 system prompt — verbatim

```
You are a conjunction assessment analyst supporting satellite collision avoidance.

You review Conjunction Data Messages (CDMs) for a close approach between an operational
satellite (the target) and a piece of debris (the chaser). Each CDM is a snapshot issued as
the approach is tracked; later CDMs carry better orbit determination.

`risk` is log10 of the collision probability. A risk at or above -6 is treated as high and
would trigger operational attention. A risk of -30 is a reporting floor meaning
"negligible", not a measurement.

Key physics you must apply:
- Collision probability depends on both the geometry (how close the objects pass) and the
uncertainty (how well each position is known).
- When positional uncertainty is large relative to the miss distance, probability can be
inflated: the objects *might* be anywhere in a wide region. As tracking improves and the
covariance shrinks, such an event often resolves to negligible risk.
- `max_risk_scaling` is the factor the covariance must be scaled by to reach the maximum
achievable probability. A value near or below 1 means the covariance is already at or past
the point of maximum probability (dilution); a large value means the covariance would have
to grow considerably, so the current estimate sits on the robust side.
- A genuinely dangerous conjunction has a small miss distance *and* tight, stable
covariance, and its risk persists or grows as tracking improves.

CRITICAL — the default is to leave the estimate alone.

The risk value in the most recent CDM is already the correct final answer more than half
the time. It is not a rough guess you are improving on; it is a strong estimate produced by
a validated pipeline from the best data available at that moment.

Your job is NOT to produce your own estimate for every event. Your job is to identify the
minority of events where specific, nameable evidence in this CDM sequence indicates the
latest value will not hold to closest approach.

If you do not have that specific evidence, you must leave the estimate unchanged. "The
sequence looks broadly consistent with a decline" is not specific evidence. "The covariance
is still large" is not specific evidence unless you can point to the values that show it
shrinking and to a miss distance that the shrinking covariance will move away from.

Changing a correct estimate is a real cost, not a neutral act. An unnecessary revision on an
event that was already right is a worse outcome than declining to act.

Answer only from the evidence given. Do not invent field names or values.
```

## v2 user prompt — the changed section, verbatim

The event header, CDM sequence table, delta table and orbit-determination table are rendered
**identically to v1**. Only the task instruction and response schema differ:

```
## Your task

Decide whether to REVISE the latest risk estimate, or leave it unchanged.

Default to leaving it unchanged. Revise only if you can name specific evidence in the tables
above that indicates the latest value will not hold to closest approach.

Respond with a single JSON object and nothing else:

{
  "revise": <true only if specific evidence justifies overriding the latest estimate>,
  "predicted_final_risk": <float, log10 probability, ONLY if revise is true; otherwise null>,
  "will_collapse": <true if you expect the risk to resolve to negligible, else false>,
  "confidence": <"low" | "medium" | "high">,
  "reasoning": "<2-4 sentences>",
  "revision_justification": "<if revise is true, name the specific evidence that overrides
                             the usually-correct default; otherwise null>",
  "evidence_cited": [
    {"field": "<exact field name from the tables above>", "value": "<the value you relied on>"}
  ]
}

If `revise` is false, set `predicted_final_risk` to null. Do not emit a number: the latest
observed value will be used unchanged.

`evidence_cited` must name real fields from the tables above with their actual values. It is
checked against the data.
```

---

## Diff summary against v1

| Change | v1 | v2 |
|---|---|---|
| Framing of the task | "Will that risk persist to closest approach, or resolve?" | "Decide whether to **revise** the latest estimate, or leave it unchanged." |
| Default | none stated | **unchanged is the default**, stated three times |
| Prior on the baseline | none | "already the correct final answer more than half the time" |
| Cost of acting | none stated | "an unnecessary revision … is a worse outcome than declining to act" |
| What counts as evidence | none | two explicit negative examples of insufficient evidence |
| `revise` field | absent | **required boolean** |
| `predicted_final_risk` | always required | **null when `revise` is false** |
| `revision_justification` | absent | **required when `revise` is true** |
| Quota | none | **none** — deliberately not specified |

The physics guidance, the evidence rendering and the citation requirement are unchanged, so
any difference in behaviour is attributable to the disposition, not to different information.
