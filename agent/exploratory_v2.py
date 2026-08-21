"""EXPLORATORY — prompt v2 (restraint). Not part of the primary result.

The primary result is fixed and published in ``docs/PHASE7_REPORT.md``: agent L = 1.6606
against B1 0.6940, median paired D = +0.9462, 0.0% of resamples favouring the agent.
Nothing in this module can change, replace, amend or soften that finding
(``docs/PHASE6_PREREGISTRATION.md`` §10.3).

**This is a separate module rather than an edit to** :mod:`agent.triage_agent` **for two
reasons.** First, ``agent/triage_agent.py`` is recorded in
``docs/PHASE7_FROZEN_MANIFEST.md`` by blob hash and ``verify_phase7.py`` check 1 fails if it
changes — the primary result must stay provable. Second, v1 and v2 must be runnable
side by side to compare them.

What v2 tests: whether the Phase 6/7 loss is an artefact of prompt design. v1 revised 99.7%
of the events it saw despite being described as a corrector. v2 makes *unchanged* the
default and requires a named justification for any revision. The prompt is recorded verbatim
in ``docs/EXPLORATORY_PROMPT_V2.md``, committed before this ran.

Everything except the instruction is identical to v1: scope, model, temperature, evidence
rendering, citation requirement, cache mechanics.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional, TypedDict

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from agent.llm import LLMClient, LLMError, LLMResponse
from agent.triage_agent import (
    RISK_FLOOR,
    SCOPE_THRESHOLD,
    SEQUENCE_COLUMNS,
    _delta_table,
    _format_number,
    _od_table,
    build_evidence_table,
    in_scope,
)

__all__ = [
    "PROMPT_VERSION_V2",
    "SYSTEM_PROMPT_V2",
    "USER_PROMPT_V2",
    "AgentVerdictV2",
    "TriageAgentV2",
    "parse_verdict_v2",
]

#: Distinct from v1's "v1", so cache keys can never collide between the two prompts.
PROMPT_VERSION_V2 = "v2"

SYSTEM_PROMPT_V2 = """\
You are a conjunction assessment analyst supporting satellite collision avoidance.

You review Conjunction Data Messages (CDMs) for a close approach between an operational \
satellite (the target) and a piece of debris (the chaser). Each CDM is a snapshot issued \
as the approach is tracked; later CDMs carry better orbit determination.

`risk` is log10 of the collision probability. A risk at or above -6 is treated as high and \
would trigger operational attention. A risk of -30 is a reporting floor meaning \
"negligible", not a measurement.

Key physics you must apply:
- Collision probability depends on both the geometry (how close the objects pass) and the \
uncertainty (how well each position is known).
- When positional uncertainty is large relative to the miss distance, probability can be \
inflated: the objects *might* be anywhere in a wide region. As tracking improves and the \
covariance shrinks, such an event often resolves to negligible risk.
- `max_risk_scaling` is the factor the covariance must be scaled by to reach the maximum \
achievable probability. A value near or below 1 means the covariance is already at or past \
the point of maximum probability (dilution); a large value means the covariance would have \
to grow considerably, so the current estimate sits on the robust side.
- A genuinely dangerous conjunction has a small miss distance *and* tight, stable \
covariance, and its risk persists or grows as tracking improves.

CRITICAL - the default is to leave the estimate alone.

The risk value in the most recent CDM is already the correct final answer more than half \
the time. It is not a rough guess you are improving on; it is a strong estimate produced by \
a validated pipeline from the best data available at that moment.

Your job is NOT to produce your own estimate for every event. Your job is to identify the \
minority of events where specific, nameable evidence in this CDM sequence indicates the \
latest value will not hold to closest approach.

If you do not have that specific evidence, you must leave the estimate unchanged. "The \
sequence looks broadly consistent with a decline" is not specific evidence. "The covariance \
is still large" is not specific evidence unless you can point to the values that show it \
shrinking and to a miss distance that the shrinking covariance will move away from.

Changing a correct estimate is a real cost, not a neutral act. An unnecessary revision on \
an event that was already right is a worse outcome than declining to act.

Answer only from the evidence given. Do not invent field names or values."""

USER_PROMPT_V2 = """\
This conjunction currently shows elevated risk two or more days before closest approach.

Only the CDMs issued at least 2 days before closest approach are available to you. The \
final risk being predicted is the value in the last CDM before closest approach, which you \
cannot see.

## Event {series_id}

Object type (chaser): {object_type}
Target span: {target_span} m   Chaser span: {chaser_span} m
Space weather at the latest CDM: F10 = {f10}, AP = {ap}

## CDM sequence (earliest first, {n_cdms} messages spanning {span_days} days)

{sequence_table}

## Change across the sequence (first -> latest)

{delta_table}

## Orbit determination quality at the latest CDM

{od_table}

## Your task

Decide whether to REVISE the latest risk estimate, or leave it unchanged.

Default to leaving it unchanged. Revise only if you can name specific evidence in the \
tables above that indicates the latest value will not hold to closest approach.

Respond with a single JSON object and nothing else:

{{
  "revise": <true only if specific evidence justifies overriding the latest estimate>,
  "predicted_final_risk": <float, log10 probability, ONLY if revise is true; otherwise null>,
  "will_collapse": <true if you expect the risk to resolve to negligible, else false>,
  "confidence": <"low" | "medium" | "high">,
  "reasoning": "<2-4 sentences>",
  "revision_justification": "<if revise is true, name the specific evidence that overrides \
the usually-correct default; otherwise null>",
  "evidence_cited": [
    {{"field": "<exact field name from the tables above>", "value": "<the value you relied on>"}}
  ]
}}

If `revise` is false, set `predicted_final_risk` to null. Do not emit a number: the latest \
observed value will be used unchanged.

`evidence_cited` must name real fields from the tables above with their actual values. \
It is checked against the data."""


class AgentVerdictV2(BaseModel):
    """v2 output. ``predicted_final_risk`` is conditional on ``revise``.

    The conditionality is enforced, not merely documented: a response claiming not to
    revise while still emitting a number is contradictory and is rejected, because
    accepting it would let the model revise by the back door.
    """

    revise: bool
    predicted_final_risk: Optional[float] = None
    will_collapse: bool
    confidence: str
    reasoning: str
    revision_justification: Optional[str] = None
    evidence_cited: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("predicted_final_risk")
    @classmethod
    def _risk_in_range(cls, value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        if not np.isfinite(value):
            raise ValueError(f"predicted_final_risk is not finite: {value!r}")
        if not (RISK_FLOOR <= value <= 0.0):
            raise ValueError(f"predicted_final_risk {value} is outside [{RISK_FLOOR}, 0]")
        return float(value)

    @field_validator("confidence")
    @classmethod
    def _known_confidence(cls, value: str) -> str:
        lowered = value.strip().lower()
        if lowered not in {"low", "medium", "high"}:
            raise ValueError(f"confidence {value!r} is not low/medium/high")
        return lowered

    @field_validator("reasoning")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reasoning is empty")
        return value.strip()

    @field_validator("evidence_cited")
    @classmethod
    def _citations_well_formed(cls, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cleaned = []
        for item in value:
            if not isinstance(item, dict) or "field" not in item:
                raise ValueError(f"malformed citation {item!r}; expected a 'field' key")
            cleaned.append({"field": str(item["field"]), "value": item.get("value")})
        return cleaned

    @model_validator(mode="after")
    def _revise_and_value_agree(self) -> "AgentVerdictV2":
        if self.revise and self.predicted_final_risk is None:
            raise ValueError("revise is true but no predicted_final_risk was given")
        if not self.revise and self.predicted_final_risk is not None:
            raise ValueError(
                f"revise is false but a value {self.predicted_final_risk} was emitted; "
                "the prompt requires null so the baseline is used unchanged"
            )
        if self.revise and not (self.revision_justification or "").strip():
            raise ValueError("revise is true but no revision_justification was given")
        return self


class AgentStateV2(TypedDict, total=False):
    """LangGraph state. Every key is declared: LangGraph drops undeclared keys, which is
    how the Phase 6 self-consistency salt was silently lost."""

    series_id: str
    cdms: Any
    features: Any
    salt: str
    prompt: str
    raw_response: str
    response_meta: Any
    verdict: Any


@dataclass
class TriageAgentV2:
    """v2 agent. Same graph shape as v1; only the prompt and schema differ."""

    client: LLMClient
    scope_threshold: float = SCOPE_THRESHOLD
    max_tokens: int = 8000
    _graph: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self._graph = self._build_graph()

    def _build_graph(self) -> Any:
        from langgraph.graph import END, StateGraph

        graph = StateGraph(AgentStateV2)
        graph.add_node("prepare_evidence", self._node_prepare)
        graph.add_node("reason", self._node_reason)
        graph.add_node("validate", self._node_validate)
        graph.set_entry_point("prepare_evidence")
        graph.add_edge("prepare_evidence", "reason")
        graph.add_edge("reason", "validate")
        graph.add_edge("validate", END)
        return graph.compile()

    def _node_prepare(self, state: AgentStateV2) -> AgentStateV2:
        cdms: pd.DataFrame = state["cdms"]
        missing = [c for c in SEQUENCE_COLUMNS if c not in cdms.columns]
        if missing:
            raise KeyError(
                f"{state['series_id']}: CDM frame is missing {missing}; refusing to "
                "render a partial evidence table"
            )

        ordered = cdms.sort_values("time_to_tca_days", ascending=False)
        latest = ordered.iloc[-1]
        span = float(ordered["time_to_tca_days"].max() - ordered["time_to_tca_days"].min())

        state["prompt"] = USER_PROMPT_V2.format(
            series_id=state["series_id"],
            object_type=latest.get("c_object_type", "UNKNOWN"),
            target_span=_format_number(latest.get("target_span_m")),
            chaser_span=_format_number(latest.get("chaser_span_m")),
            f10=_format_number(latest.get("F10")),
            ap=_format_number(latest.get("AP")),
            n_cdms=len(ordered),
            span_days=_format_number(span, 3),
            sequence_table=build_evidence_table(ordered),
            delta_table=_delta_table(ordered),
            od_table=_od_table(latest),
        )
        return state

    def _node_reason(self, state: AgentStateV2) -> AgentStateV2:
        response = self.client.complete(
            state["prompt"],
            system=SYSTEM_PROMPT_V2,
            max_tokens=self.max_tokens,
            salt=state.get("salt", ""),
        )
        state["raw_response"] = response.text
        state["response_meta"] = response
        return state

    def _node_validate(self, state: AgentStateV2) -> AgentStateV2:
        state["verdict"] = parse_verdict_v2(state["raw_response"], state["series_id"])
        return state

    def analyse(
        self, series_id: str, cdms: pd.DataFrame, features: pd.Series, salt: str = ""
    ) -> tuple[AgentVerdictV2, LLMResponse]:
        result = self._graph.invoke({
            "series_id": series_id, "cdms": cdms, "features": features, "salt": salt,
        })
        return result["verdict"], result["response_meta"]


def parse_verdict_v2(text: str, series_id: str = "") -> AgentVerdictV2:
    """Parse and validate a v2 response. Raises rather than defaulting."""
    candidate = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.+?)\s*```", candidate, re.S)
    if fenced:
        candidate = fenced.group(1).strip()
    else:
        start, end = candidate.find("{"), candidate.rfind("}")
        if start != -1 and end > start:
            candidate = candidate[start : end + 1]

    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise LLMError(
            f"{series_id}: response is not valid JSON ({exc}); first 200 chars: "
            f"{text[:200]!r}"
        ) from exc

    try:
        return AgentVerdictV2.model_validate(payload)
    except ValidationError as exc:
        raise LLMError(f"{series_id}: response failed schema validation: {exc}") from exc
