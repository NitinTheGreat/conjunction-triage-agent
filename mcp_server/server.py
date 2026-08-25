"""MCP server exposing the conjunction pipeline to an LLM client.

Four tools: :func:`fetch_conjunctions`, :func:`compute_pc`, :func:`get_object_metadata`,
:func:`triage_events`.

Why the descriptions are so explicit
------------------------------------
A tool description is the only thing the calling model sees before it decides what to pass.
Every quantity here has a unit and most have a frame, and the frame in particular is the
one mistake that produces a plausible wrong answer rather than an error: two covariances
published in their own objects' UVW frames cannot be summed until each is rotated to ECI.
So every parameter states its unit and frame in the description, and ``compute_pc`` refuses
to guess ``covariance_frame``.

The same applies to the results. ``fetch_conjunctions`` returns a ``pc_is_floored`` flag on
every event and says in its description that a floored value is an upper bound rather than
a measurement, because a model that averages censored values will produce a confident
number that means nothing. ``triage_events`` states in its own description that the agent
it calls **lost** to a one-line baseline, so a model choosing between them has that in
front of it rather than buried in a report.

Transport is stdio, which is what Claude Desktop and Claude Code speak. See the README in
this directory for the client configuration.

    python -m mcp_server.server
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, Any, Literal, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from mcp.server.mcpserver import MCPServer  # noqa: E402
from pydantic import Field  # noqa: E402

from api.provenance import provenance  # noqa: E402
from core.config import MissingCredentialError, settings  # noqa: E402
from core.store import SOURCES, StoreError, store  # noqa: E402
from orbital.frames import FrameError  # noqa: E402
from orbital.pc import PcError, pc_from_states  # noqa: E402

INSTRUCTIONS = """
Conjunction assessment over the TraCSS IV&V benchmark and the ESA Kelvins challenge.

Three things to carry into any use of these tools:

1. `pc` is censored at 1e-10. A value on that floor is an upper bound, not a measurement.
   Every event carries `pc_is_floored`; never average, rank or reason across floored and
   unfloored values as if they were the same kind of number.
2. Covariance frames are not interchangeable. TraCSS publishes each object's covariance in
   that object's own UVW frame. `compute_pc` requires you to declare the frame and will
   not guess.
3. `triage_events` runs an LLM agent that was measured against a one-line baseline and
   LOST, by 2.4x. Prefer the baseline risk it returns alongside the agent's answer.
""".strip()

server = MCPServer(
    name="conjunction-triage",
    title="ConjunctionTriage",
    instructions=INSTRUCTIONS,
    version="0.9.0",
)


def _fail(message: str, **extra: Any) -> dict[str, Any]:
    """A structured failure. Tools return this rather than raising into the transport."""
    return {"ok": False, "error": message, **extra}


def _clean(value: Any) -> Any:
    """None for anything not JSON-representable, so no NaN reaches the client."""
    if value is None:
        return None
    if isinstance(value, (np.floating, float)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    return None if pd.isna(value) else value


# ------------------------------------------------------------------------------------


@server.tool(
    name="fetch_conjunctions",
    description=(
        "Query the TraCSS IV&V conjunction benchmark: 1.2 million screened close "
        "approaches with states, covariances and a published probability of collision at "
        "TCA.\n\n"
        "RETURNS one record per event with: miss_distance_km (km), relative_speed_kms "
        "(km/s), pc (dimensionless probability), pc_is_floored (bool), "
        "mahalanobis_distance (dimensionless, 3D), dilution (1 = the covariance is on the "
        "diluted side of the Pc-versus-scale-factor curve, where a LARGER covariance "
        "gives a SMALLER Pc), tca (UTC), and both objects' catalogue ids and hard-body "
        "radii in metres.\n\n"
        "CENSORING: pc is reported down to 1e-10 and no further. 74.7% of the spherical "
        "file and 14.7% of the SFSH file sit exactly on that floor. Those values are "
        "upper bounds, not measurements. Use exclude_floored=true before computing any "
        "statistic over pc.\n\n"
        "A filtered result describes the filter, not the benchmark."
    ),
)
def fetch_conjunctions(
    source: Annotated[
        Literal["sfsh", "spherical"],
        Field(description=(
            "Which answer key. 'sfsh' uses per-object hard-body radii (283,568 events); "
            "'spherical' uses a constant 0.5 m radius (913,292 events)."
        )),
    ] = "sfsh",
    limit: Annotated[int, Field(ge=1, le=200, description="Rows to return, 1-200.")] = 25,
    min_pc: Annotated[
        Optional[float], Field(description="Lower bound on published pc, dimensionless.")
    ] = None,
    max_miss_km: Annotated[
        Optional[float], Field(gt=0, description="Upper bound on miss distance, in km.")
    ] = None,
    exclude_floored: Annotated[
        bool, Field(description="Drop events whose pc is on the 1e-10 censoring floor.")
    ] = True,
    catalog_id: Annotated[
        Optional[str], Field(description="Only events involving this catalogue object.")
    ] = None,
) -> dict[str, Any]:
    if source not in SOURCES:
        return _fail(f"unknown source {source!r}; expected one of {list(SOURCES)}")

    clauses: list[str] = []
    parameters: list[Any] = []
    if min_pc is not None:
        clauses.append("pc >= ?")
        parameters.append(min_pc)
    if max_miss_km is not None:
        clauses.append("miss_distance_km <= ?")
        parameters.append(max_miss_km)
    if exclude_floored:
        clauses.append("not pc_is_floored")
    if catalog_id is not None:
        clauses.append("(obj1_catalog_id = ? or obj2_catalog_id = ?)")
        parameters.extend([catalog_id, catalog_id])
    where = f" where {' and '.join(clauses)}" if clauses else ""

    try:
        total = int(
            store.query(f"select count(*) as n from {source}{where}", parameters or None)
            ["n"].iloc[0]
        )
        frame = store.query(
            f"select event_id, tca, miss_distance_km, relative_speed_kms, pc, "
            f"pc_is_floored, mahalanobis_distance, dilution, obj1_catalog_id, "
            f"obj2_catalog_id, obj1_hbr_m, obj2_hbr_m from {source}{where} "
            f"order by pc desc nulls last limit ?",
            [*parameters, limit],
        )
    except StoreError as exc:
        return _fail(str(exc), hint="Run scripts/ingest.py to build the ingested store.")

    events = [
        {
            "event_id": str(row["event_id"]),
            "tca_utc": None if pd.isna(row["tca"]) else row["tca"].isoformat(),
            "miss_distance_km": _clean(row["miss_distance_km"]),
            "relative_speed_kms": _clean(row["relative_speed_kms"]),
            "pc": _clean(row["pc"]),
            "pc_is_floored": bool(row["pc_is_floored"]),
            "mahalanobis_distance": _clean(row["mahalanobis_distance"]),
            "dilution": _clean(row["dilution"]),
            "object1": {
                "catalog_id": str(row["obj1_catalog_id"]),
                "hard_body_radius_m": _clean(row["obj1_hbr_m"]),
            },
            "object2": {
                "catalog_id": str(row["obj2_catalog_id"]),
                "hard_body_radius_m": _clean(row["obj2_hbr_m"]),
            },
        }
        for _, row in frame.iterrows()
    ]
    return {
        "ok": True,
        "events": events,
        "returned": len(events),
        "total_matching": total,
        "provenance": provenance("events", source=source),
    }


@server.tool(
    name="compute_pc",
    description=(
        "Compute the probability of collision between two objects at TCA using the "
        "Alfano (2004) two-dimensional short-encounter method.\n\n"
        "UNITS AND FRAMES, all required:\n"
        "  position_km    - [x, y, z] in kilometres, J2000/ECI\n"
        "  velocity_kms   - [vx, vy, vz] in kilometres per second, J2000/ECI\n"
        "  covariance     - 3x3 position covariance in km^2\n"
        "  hbr_m          - hard-body radius in METRES (the combined radius is the sum)\n"
        "  covariance_frame - 'uvw' or 'eci', REQUIRED, no default\n\n"
        "covariance_frame is the parameter to get right. 'uvw' means each covariance is "
        "in its OWN object's local radial/in-track/cross-track frame, which is how TraCSS "
        "publishes them; they must be rotated to ECI before they can be summed. 'eci' "
        "means both are already inertial. Passing the wrong one changes the answer by "
        "orders of magnitude and raises no error.\n\n"
        "RETURNS pc, the miss distance, both Mahalanobis distances (2D in the encounter "
        "plane and 3D), and a conditioning report saying whether either covariance had to "
        "be repaired to be invertible. Check the conditioning before quoting the pc.\n\n"
        "This reproduces the TraCSS pc column to a median ratio of 0.999994 over 20,000 "
        "events. That is a reproduction of their published method, NOT evidence that pc "
        "is correct about the world: no collision outcome exists in this dataset."
    ),
)
def compute_pc(
    position1_km: Annotated[list[float], Field(description="Object 1 position, km, ECI.")],
    velocity1_kms: Annotated[list[float], Field(description="Object 1 velocity, km/s, ECI.")],
    covariance1: Annotated[
        list[list[float]], Field(description="Object 1's 3x3 position covariance, km^2.")
    ],
    hbr1_m: Annotated[float, Field(gt=0, description="Object 1 hard-body radius, metres.")],
    position2_km: Annotated[list[float], Field(description="Object 2 position, km, ECI.")],
    velocity2_kms: Annotated[list[float], Field(description="Object 2 velocity, km/s, ECI.")],
    covariance2: Annotated[
        list[list[float]], Field(description="Object 2's 3x3 position covariance, km^2.")
    ],
    hbr2_m: Annotated[float, Field(gt=0, description="Object 2 hard-body radius, metres.")],
    covariance_frame: Annotated[
        Literal["uvw", "eci"],
        Field(description=(
            "Frame of BOTH covariances. 'uvw' = each in its own object's local frame "
            "(how TraCSS publishes them); 'eci' = both already inertial. No default."
        )),
    ],
) -> dict[str, Any]:
    try:
        result = pc_from_states(
            position1_km=position1_km,
            velocity1_kms=velocity1_kms,
            covariance1=np.array(covariance1, dtype=float),
            position2_km=position2_km,
            velocity2_kms=velocity2_kms,
            covariance2=np.array(covariance2, dtype=float),
            hbr1_m=hbr1_m,
            hbr2_m=hbr2_m,
            covariance_frame=covariance_frame,
        )
    except (PcError, FrameError, ValueError) as exc:
        return _fail(
            str(exc),
            hint=(
                "Pc is undefined for these inputs. Check that each covariance is 3x3, "
                "symmetric and a genuine covariance, and that the two states differ."
            ),
        )

    return {
        "ok": True,
        "pc": result.pc,
        "log10_pc": float(np.log10(result.pc)) if result.pc > 0 else None,
        "miss_distance_km": result.miss_distance_km,
        "relative_speed_kms": result.relative_speed_kms,
        "combined_hard_body_radius_m": result.combined_hbr_m,
        "mahalanobis_distance_2d": result.mahalanobis_distance,
        "mahalanobis_distance_3d": result.mahalanobis_distance_3d,
        "conditioning": {
            "combined_3d": result.conditioning_3d.as_dict(),
            "encounter_plane_2d": result.conditioning.as_dict(),
        },
        "provenance": provenance("pc", covariance_frame=covariance_frame),
    }


@server.tool(
    name="get_object_metadata",
    description=(
        "Look up one catalogue object in the benchmark: its hard-body radius in metres "
        "and how it appears across screened conjunctions.\n\n"
        "RETURNS the hard-body radius (metres, from the Aerospace screening-volumes "
        "table), the number of events the object appears in, and the distribution of the "
        "miss distances and probabilities across those events -- with censored values "
        "counted separately, because a pc on the 1e-10 floor is a bound and averaging it "
        "in would understate every summary.\n\n"
        "This is benchmark metadata only. It carries no launch date, no operator and no "
        "orbit class; the dataset does not contain them."
    ),
)
def get_object_metadata(
    catalog_id: Annotated[str, Field(description="NORAD-style catalogue number, as a string.")],
    source: Annotated[
        Literal["sfsh", "spherical"], Field(description="Which answer key to summarise.")
    ] = "sfsh",
) -> dict[str, Any]:
    if source not in SOURCES:
        return _fail(f"unknown source {source!r}; expected one of {list(SOURCES)}")
    try:
        summary = store.query(
            f"""
            select
                count(*)                                              as events,
                sum(case when pc_is_floored then 1 else 0 end)         as censored_events,
                min(miss_distance_km)                                  as min_miss_km,
                median(miss_distance_km)                               as median_miss_km,
                max(case when not pc_is_floored then pc end)           as max_uncensored_pc,
                median(case when not pc_is_floored then pc end)        as median_uncensored_pc,
                max(case when obj1_catalog_id = ? then obj1_hbr_m
                         else obj2_hbr_m end)                          as hard_body_radius_m
            from {source}
            where obj1_catalog_id = ? or obj2_catalog_id = ?
            """,
            [catalog_id, catalog_id, catalog_id],
        )
    except StoreError as exc:
        return _fail(str(exc), hint="Run scripts/ingest.py to build the ingested store.")

    row = summary.iloc[0]
    events = int(row["events"])
    if events == 0:
        return _fail(
            f"catalogue object {catalog_id!r} does not appear in the {source} file",
            hint="Catalogue ids are strings of digits, e.g. '53022'.",
        )

    censored = int(row["censored_events"])
    return {
        "ok": True,
        "catalog_id": catalog_id,
        "source": source,
        "hard_body_radius_m": _clean(row["hard_body_radius_m"]),
        "events": events,
        "censored_events": censored,
        "uncensored_events": events - censored,
        "min_miss_distance_km": _clean(row["min_miss_km"]),
        "median_miss_distance_km": _clean(row["median_miss_km"]),
        "max_uncensored_pc": _clean(row["max_uncensored_pc"]),
        "median_uncensored_pc": _clean(row["median_uncensored_pc"]),
        "censoring_note": (
            f"{censored} of {events} events have pc on the 1e-10 floor and are excluded "
            "from the pc statistics above. They are upper bounds, not measurements."
        ),
        "provenance": provenance("events", source=source),
    }


@server.tool(
    name="triage_events",
    description=(
        "Run the LLM reasoning agent over ESA Kelvins CDM series and return, for each, "
        "the agent's predicted final risk and the latest-CDM baseline's.\n\n"
        "READ THIS BEFORE USING THE RESULT. The agent LOST. On the held-out test set it "
        "scored L = 1.6606 on the official Kelvins metric against the latest-CDM "
        "baseline's L = 0.6940 -- 2.4x worse, lower being better. In a 10,000-resample "
        "paired bootstrap the agent was ahead in 0.0% of resamples. The baseline it lost "
        "to is one line: predict the most recent CDM's risk. For an actual estimate, use "
        "baseline_risk. The agent's prediction is returned so the two can be compared, "
        "not because it is the better number.\n\n"
        "RETURNS per series: baseline_risk (log10 collision risk from the latest visible "
        "CDM), agent_risk (the agent's prediction, or null when out of scope), "
        "effective_prediction (what the arm actually predicts), will_collapse, "
        "confidence, and the agent's reasoning with the evidence it cited.\n\n"
        "SCOPE: the agent is a corrector on an alert queue. It is invoked only when the "
        "latest visible risk is at or above -7.0; below that the event falls through to "
        "the baseline with no LLM call.\n\n"
        "COST: one LLM call per in-scope series, capped at 10 per invocation. Requires an "
        "API key; without one this returns an error rather than a fabricated verdict."
    ),
)
def triage_events(
    series_ids: Annotated[
        list[str],
        Field(min_length=1, max_length=10, description=(
            "Kelvins series ids, e.g. ['test:100']. At most 10: each is a billed call."
        )),
    ],
    split: Annotated[
        Literal["test", "train"], Field(description="Which ingested Kelvins split.")
    ] = "test",
) -> dict[str, Any]:
    from agent.llm import LLMClient, LLMError
    from agent.triage_agent import PROMPT_VERSION, TriageAgent, in_scope
    from core.features import build_dataset
    from core.kelvins_store import KelvinsStoreError, load_visible_cdms

    try:
        settings.llm_api_key()
    except MissingCredentialError as exc:
        return _fail(str(exc), hint="Set the provider's API key in .env.")

    try:
        events = build_dataset(split).set_index("series_id", drop=False)
        known = [sid for sid in series_ids if sid in events.index]
        cdms = load_visible_cdms(known, split) if known else {}
    except (KelvinsStoreError, FileNotFoundError) as exc:
        return _fail(str(exc), hint="Run scripts/ingest_kelvins.py first.")

    agent = TriageAgent(client=LLMClient(prompt_version=PROMPT_VERSION))
    verdicts: list[dict[str, Any]] = []

    for series_id in series_ids:
        if series_id not in events.index:
            verdicts.append({
                "series_id": series_id,
                "error": f"not an eligible event in the {split} split",
            })
            continue

        row = events.loc[series_id]
        baseline = float(row["latest_risk"])
        if not in_scope(baseline):
            verdicts.append({
                "series_id": series_id, "in_scope": False,
                "baseline_risk": baseline, "agent_risk": None,
                "effective_prediction": baseline,
                "note": "below the -7.0 alert threshold; no LLM call made",
            })
            continue

        frame = cdms.get(series_id)
        if frame is None or frame.empty:
            verdicts.append({
                "series_id": series_id, "in_scope": True,
                "baseline_risk": baseline, "agent_risk": None,
                "effective_prediction": baseline,
                "error": "no visible CDMs at or beyond 2 days to TCA",
            })
            continue

        try:
            verdict, _ = agent.analyse(series_id, frame, row)
        except (LLMError, ValueError, KeyError) as exc:
            verdicts.append({
                "series_id": series_id, "in_scope": True,
                "baseline_risk": baseline, "agent_risk": None,
                "effective_prediction": baseline, "error": str(exc)[:300],
            })
            continue

        verdicts.append({
            "series_id": series_id,
            "in_scope": True,
            "baseline_risk": baseline,
            "agent_risk": verdict.predicted_final_risk,
            "effective_prediction": verdict.predicted_final_risk,
            "will_collapse": verdict.will_collapse,
            "confidence": verdict.confidence,
            "reasoning": verdict.reasoning,
            "evidence_cited": verdict.evidence_cited,
        })

    return {
        "ok": True,
        "verdicts": verdicts,
        "requested": len(series_ids),
        "provenance": provenance(
            "triage", split=split, prompt_version=PROMPT_VERSION,
            provider=settings.LLM_PROVIDER, model=settings.LLM_MODEL,
        ),
    }


def main() -> None:
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
