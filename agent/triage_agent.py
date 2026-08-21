"""The conjunction triage agent.

**Design principle (fixed in the pre-registration): the agent is a corrector on an alert
queue, not a replacement predictor.** B1 — predict the latest visible risk — is already
*exactly* right on 55.6% of events. The agent is invoked only on events whose latest
visible risk is at or above ``SCOPE_THRESHOLD`` (−7.0: the −6 decision threshold plus a
1-dex margin band to catch escalations). Everywhere else the prediction *is* B1's,
unchanged and uninvoked.

That scope is both the operationally realistic design — an analyst reviews an alert queue,
not the whole catalogue — and the only place Phase 5 found any headroom.

The question the agent answers is the Phase 5 error mode stated directly: of the events B1
flags, more than half see their risk collapse to the floor as orbit determination resolves.
So the agent is asked whether elevated risk will **persist** or **resolve**, and is required
to ground that judgement in whether the uncertainty is still shrinking.

The agent is never shown B1's answer. It receives the evidence and is asked for a
judgement; anchoring it on the baseline would make any agreement uninterpretable.

Graph
-----
``prepare_evidence -> reason -> validate`` — a small LangGraph, linear by design. A
malformed model response raises at ``validate``; nothing is defaulted.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional, TypedDict

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, ValidationError, field_validator

from agent.llm import LLMClient, LLMError, LLMResponse

__all__ = [
    "PROMPT_VERSION",
    "SCOPE_THRESHOLD",
    "AgentVerdict",
    "TriageAgent",
    "in_scope",
    "build_evidence_table",
]

#: Bump when the prompt changes. Part of every cache key, so a prompt change never
#: silently reuses responses generated under the old wording.
PROMPT_VERSION = "v1"

#: The agent examines events whose latest visible risk is at or above this value.
#: Fixed in docs/PHASE6_PREREGISTRATION.md §7 before any output was seen.
SCOPE_THRESHOLD = -7.0

#: Kelvins censoring floor.
RISK_FLOOR = -30.0

#: Columns the evidence table shows, in the order they appear.
SEQUENCE_COLUMNS = (
    "time_to_tca_days", "risk_log10", "miss_distance_km", "mahalanobis_distance",
    "max_risk_scaling", "target_sigma_max_km", "chaser_sigma_max_km",
    "relative_speed_kms",
)

OD_COLUMNS = (
    "target_obs_used", "chaser_obs_used",
    "target_residuals_accepted", "chaser_residuals_accepted",
    "target_weighted_rms", "chaser_weighted_rms",
    "target_actual_od_span", "chaser_actual_od_span",
    "target_recommended_od_span", "chaser_recommended_od_span",
)

SYSTEM_PROMPT = """\
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

Answer only from the evidence given. Do not invent field names or values."""

USER_PROMPT = """\
This conjunction currently shows elevated risk two or more days before closest approach.
Will that risk persist to closest approach, or resolve as orbit determination improves?

Only the CDMs issued at least 2 days before closest approach are available to you. The \
final risk you are predicting is the value in the last CDM before closest approach, which \
you cannot see.

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

Decide whether the elevated risk will persist to closest approach or resolve.

Respond with a single JSON object and nothing else:

{{
  "predicted_final_risk": <float, log10 probability; use -30.0 for negligible>,
  "will_collapse": <true if you expect the risk to resolve to negligible, else false>,
  "confidence": <"low" | "medium" | "high">,
  "reasoning": "<2-4 sentences explaining your judgement>",
  "evidence_cited": [
    {{"field": "<exact field name from the tables above>", "value": "<the value you relied on>"}}
  ]
}}

`evidence_cited` must name real fields from the tables above with their actual values. \
It is checked against the data."""


# --------------------------------------------------------------------------------------
# the validated output schema
# --------------------------------------------------------------------------------------

class AgentVerdict(BaseModel):
    """Structured agent output. A malformed response raises; nothing is defaulted."""

    predicted_final_risk: float
    will_collapse: bool
    confidence: str
    reasoning: str
    evidence_cited: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("predicted_final_risk")
    @classmethod
    def _risk_in_range(cls, value: float) -> float:
        if not np.isfinite(value):
            raise ValueError(f"predicted_final_risk is not finite: {value!r}")
        if not (RISK_FLOOR <= value <= 0.0):
            raise ValueError(
                f"predicted_final_risk {value} is outside [{RISK_FLOOR}, 0]"
            )
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


# --------------------------------------------------------------------------------------
# scope and evidence
# --------------------------------------------------------------------------------------

def in_scope(latest_risk: float, threshold: float = SCOPE_THRESHOLD) -> bool:
    """Whether the agent is invoked for an event with this latest visible risk."""
    return bool(np.isfinite(latest_risk) and latest_risk >= threshold)


def _format_number(value: Any, digits: int = 4) -> str:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return "n/a"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number != 0 and (abs(number) < 1e-3 or abs(number) >= 1e6):
        return f"{number:.{digits}e}"
    return f"{number:.{digits}g}"


def build_evidence_table(cdms: pd.DataFrame) -> str:
    """Render the visible CDM sequence as a fixed-width table, earliest first."""
    if cdms.empty:
        raise ValueError("no CDMs to render")

    ordered = cdms.sort_values("time_to_tca_days", ascending=False)
    headers = ["t-2d+", "risk", "miss_km", "mahal", "scaling", "sig_tgt_km",
               "sig_chs_km", "vrel_kms"]
    widths = [8, 8, 10, 9, 11, 11, 11, 9]

    lines = ["  ".join(h.ljust(w) for h, w in zip(headers, widths))]
    lines.append("  ".join("-" * w for w in widths))
    for _, row in ordered.iterrows():
        cells = [
            _format_number(row["time_to_tca_days"], 4),
            _format_number(row["risk_log10"], 5),
            _format_number(row["miss_distance_km"], 4),
            _format_number(row["mahalanobis_distance"], 4),
            _format_number(row["max_risk_scaling"], 4),
            _format_number(row["target_sigma_max_km"], 4),
            _format_number(row["chaser_sigma_max_km"], 4),
            _format_number(row["relative_speed_kms"], 4),
        ]
        lines.append("  ".join(c.ljust(w) for c, w in zip(cells, widths)))
    return "\n".join(lines)


def _delta_table(cdms: pd.DataFrame) -> str:
    ordered = cdms.sort_values("time_to_tca_days", ascending=False)
    if len(ordered) < 2:
        return (
            "Only one CDM is available, so no trend can be computed. "
            "Judge from the single snapshot."
        )
    first, last = ordered.iloc[0], ordered.iloc[-1]
    rows = []
    for label, column in (
        ("risk", "risk_log10"),
        ("miss_distance_km", "miss_distance_km"),
        ("mahalanobis_distance", "mahalanobis_distance"),
        ("max_risk_scaling", "max_risk_scaling"),
        ("target_sigma_max_km", "target_sigma_max_km"),
        ("chaser_sigma_max_km", "chaser_sigma_max_km"),
    ):
        start, end = first[column], last[column]
        if start is None or end is None or not np.isfinite(start) or not np.isfinite(end):
            rows.append(f"{label:24s} n/a")
            continue
        change = end - start
        direction = "increasing" if change > 0 else ("decreasing" if change < 0 else "flat")
        rows.append(
            f"{label:24s} {_format_number(start)} -> {_format_number(end)}  "
            f"({direction}, delta {_format_number(change)})"
        )
    return "\n".join(rows)


def _od_table(latest: pd.Series) -> str:
    rows = []
    for column in OD_COLUMNS:
        if column not in latest.index:
            continue
        rows.append(f"{column:30s} {_format_number(latest[column])}")
    return "\n".join(rows) if rows else "no orbit-determination columns available"


# --------------------------------------------------------------------------------------
# the agent
# --------------------------------------------------------------------------------------

class AgentState(TypedDict, total=False):
    """LangGraph state passed between nodes."""

    series_id: str
    cdms: Any
    features: Any
    prompt: str
    raw_response: str
    response_meta: Any
    verdict: Any
    error: Optional[str]


@dataclass
class TriageAgent:
    """Corrector agent over an alert queue.

    ``client`` is injected so tests can supply an offline, cache-only client.
    """

    client: LLMClient
    scope_threshold: float = SCOPE_THRESHOLD
    #: Generous enough to cover internal reasoning plus the JSON answer. Gemini 3 shares
    #: this budget between thinking and output: 900 left only 32 tokens for the answer,
    #: and 4000 still truncated events that spent 3,840 tokens thinking.
    max_tokens: int = 8000
    _graph: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self._graph = self._build_graph()

    # -- graph ---------------------------------------------------------------------------

    def _build_graph(self) -> Any:
        from langgraph.graph import END, StateGraph

        graph = StateGraph(AgentState)
        graph.add_node("prepare_evidence", self._node_prepare)
        graph.add_node("reason", self._node_reason)
        graph.add_node("validate", self._node_validate)
        graph.set_entry_point("prepare_evidence")
        graph.add_edge("prepare_evidence", "reason")
        graph.add_edge("reason", "validate")
        graph.add_edge("validate", END)
        return graph.compile()

    def _node_prepare(self, state: AgentState) -> AgentState:
        """Render the evidence. Raises if a required column is absent — see phase5.9."""
        cdms: pd.DataFrame = state["cdms"]
        features: pd.Series = state["features"]

        missing = [c for c in SEQUENCE_COLUMNS if c not in cdms.columns]
        if missing:
            raise KeyError(
                f"{state['series_id']}: CDM frame is missing {missing}; refusing to "
                "render a partial evidence table"
            )

        ordered = cdms.sort_values("time_to_tca_days", ascending=False)
        latest = ordered.iloc[-1]
        span = float(ordered["time_to_tca_days"].max() - ordered["time_to_tca_days"].min())

        state["prompt"] = USER_PROMPT.format(
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

    def _node_reason(self, state: AgentState) -> AgentState:
        response = self.client.complete(
            state["prompt"],
            system=SYSTEM_PROMPT,
            max_tokens=self.max_tokens,
            salt=state.get("salt", ""),
        )
        state["raw_response"] = response.text
        state["response_meta"] = response
        return state

    def _node_validate(self, state: AgentState) -> AgentState:
        state["verdict"] = parse_verdict(state["raw_response"], state["series_id"])
        return state

    # -- public ---------------------------------------------------------------------------

    def analyse(
        self,
        series_id: str,
        cdms: pd.DataFrame,
        features: pd.Series,
        salt: str = "",
    ) -> tuple[AgentVerdict, LLMResponse]:
        """Run the graph for one event. Raises on any malformed output."""
        state: AgentState = {
            "series_id": series_id,
            "cdms": cdms,
            "features": features,
            "salt": salt,
        }
        result = self._graph.invoke(state)
        return result["verdict"], result["response_meta"]


def parse_verdict(text: str, series_id: str = "") -> AgentVerdict:
    """Parse and validate a model response. Raises rather than defaulting.

    Tolerates a fenced code block or surrounding prose, because those are formatting
    noise rather than a different answer — but a response with no parseable JSON object,
    or one that fails schema validation, is an error.
    """
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
        return AgentVerdict.model_validate(payload)
    except ValidationError as exc:
        raise LLMError(f"{series_id}: response failed schema validation: {exc}") from exc
