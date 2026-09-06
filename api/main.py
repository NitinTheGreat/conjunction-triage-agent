"""The ConjunctionTriage HTTP API.

Five endpoints over the physics layer, the ingested benchmark, and the agent:

===============  =========================================================================
``GET  /health``  what is available and what is not
``POST /pc``      probability of collision from two states and covariances
``POST /screen``  close approaches between two TLEs inside a window
``GET  /events``  read-only query over the TraCSS IV&V benchmark
``POST /triage``  the reasoning agent over Kelvins CDM series
===============  =========================================================================

Two rules run through all of it.

**Every response carries provenance.** A bare number is not interpretable: it does not say
which dataset it came from, which method produced it, or how well that method was checked.
See :mod:`api.provenance`. For ``/triage`` the provenance says outright that the agent lost
to a one-line baseline, because serving its predictions without that would be presenting a
worse estimator as a product.

**No bare 500s.** Every failure path -- validation, physics, missing data, missing
credentials, and anything unforeseen -- returns a structured :class:`api.models.ErrorBody`
with a stable code. The catch-all handler logs the traceback server-side and returns the
request id, never the traceback.

Run it with::

    uvicorn api.main:app --reload
"""

from __future__ import annotations

import logging
import sys
import uuid
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from fastapi import FastAPI, Query, Request, status  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

from api.models import (  # noqa: E402
    ErrorBody,
    EventOut,
    EventsResponse,
    HealthResponse,
    PcRequest,
    PcResponse,
    ScreenRequest,
    ScreenResponse,
    TriageRequest,
    TriageResponse,
    TriageVerdict,
)
from api.provenance import code_version, provenance  # noqa: E402
from core.config import MissingCredentialError, settings  # noqa: E402
from core.kelvins_store import KelvinsStoreError  # noqa: E402
from core.store import SOURCES, StoreError, store  # noqa: E402
from orbital.frames import FrameError  # noqa: E402
from orbital.pc import PcError, pc_from_states  # noqa: E402
from orbital.propagate import PropagationError, screen_pair, verify_reference_case  # noqa: E402

logger = logging.getLogger("conjunction_triage.api")

DESCRIPTION = """
Conjunction triage over the TraCSS IV&V benchmark and the ESA Kelvins challenge.

Every response carries a `provenance` block naming the dataset, the method, the units and
the frames, and stating what the number does **not** establish. Read it.

**On `/triage`:** the reasoning agent it serves scored **L = 1.6606** on the held-out test
set against the latest-CDM baseline's **L = 0.6940** — 2.4x worse, with the agent ahead in
0.0% of 10,000 bootstrap resamples. It is exposed because the pipeline is the deliverable.
For an actual estimate, take the most recent CDM's risk.
"""

app = FastAPI(
    title="ConjunctionTriage API",
    description=DESCRIPTION,
    version=code_version(),
    contact={"name": "ConjunctionTriage Agent"},
    license_info={"name": "See repository"},
)

#: Origins the browser frontend is served from. Deliberately an explicit localhost list
#: rather than "*": this server reads a local dataset and can spend money on LLM calls, so a
#: page on any origin being able to drive it is not a trade worth making for convenience.
LOCAL_ORIGINS = [
    f"http://{host}:{port}"
    for host in ("localhost", "127.0.0.1")
    for port in (8001, 8080, 5173, 3000)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=LOCAL_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


# ------------------------------------------------------------------------------------
# errors: every path returns a structured body
# ------------------------------------------------------------------------------------

def _error(
    code: str, detail: str, http_status: int,
    hint: Optional[str] = None, request_id: Optional[str] = None,
) -> JSONResponse:
    body = ErrorBody(error=code, detail=detail, hint=hint, request_id=request_id)
    return JSONResponse(status_code=http_status, content=body.model_dump())


@app.exception_handler(RequestValidationError)
async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    problems = "; ".join(
        f"{'.'.join(str(p) for p in err['loc'][1:])}: {err['msg']}"
        for err in exc.errors()[:6]
    )
    return _error(
        "invalid_request", problems or "request body failed validation",
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        hint="See /docs for the schema; units and frames are in the field descriptions.",
    )


@app.exception_handler(PcError)
@app.exception_handler(FrameError)
async def _physics_error(request: Request, exc: Exception) -> JSONResponse:
    # A refusal, not a crash: the inputs describe a geometry or a covariance for which Pc
    # is undefined. Returning a number anyway is the failure mode this guards against.
    return _error(
        "pc_undefined", str(exc), status.HTTP_422_UNPROCESSABLE_CONTENT,
        hint="Check that the covariance is a covariance and the states are distinct.",
    )


@app.exception_handler(PropagationError)
async def _propagation_error(request: Request, exc: PropagationError) -> JSONResponse:
    return _error(
        "propagation_failed", str(exc), status.HTTP_422_UNPROCESSABLE_CONTENT,
        hint="Check the TLE lines and that the window is near the element set epoch.",
    )


@app.exception_handler(StoreError)
async def _store_error(request: Request, exc: StoreError) -> JSONResponse:
    return _error(
        "dataset_unavailable", str(exc), status.HTTP_503_SERVICE_UNAVAILABLE,
        hint="Run scripts/ingest.py to build the ingested store.",
    )


@app.exception_handler(KelvinsStoreError)
async def _kelvins_store_error(request: Request, exc: KelvinsStoreError) -> JSONResponse:
    return _error(
        "dataset_unavailable", str(exc), status.HTTP_503_SERVICE_UNAVAILABLE,
        hint="Run scripts/ingest_kelvins.py to build the ingested Kelvins store.",
    )


@app.exception_handler(MissingCredentialError)
async def _credential_error(request: Request, exc: MissingCredentialError) -> JSONResponse:
    # The message from core.config names the variable but never its value.
    return _error(
        "llm_unavailable", str(exc), status.HTTP_503_SERVICE_UNAVAILABLE,
        hint=(
            "Set the provider's API key in .env. Only /triage needs it; /pc, /screen and "
            "/events work without any credential."
        ),
    )


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
    request_id = uuid.uuid4().hex[:12]
    logger.exception("unhandled error on %s [%s]", request.url.path, request_id)
    return _error(
        "internal_error",
        "The server hit an unexpected condition. The traceback is in the server log.",
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        hint="Quote the request_id when reporting this.",
        request_id=request_id,
    )


# ------------------------------------------------------------------------------------
# health
# ------------------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["meta"])
def health() -> HealthResponse:
    """What this server can actually do right now.

    Reports each subsystem separately rather than a single boolean, because the useful
    answer is usually partial: the physics endpoints work with no dataset and no
    credential, so a missing LLM key degrades ``/triage`` alone.
    """
    checks: dict[str, Any] = {}

    try:
        available = store.available()
        checks["tracss_store"] = {
            "ok": True,
            "sources": {name: store.count(name) for name in available},
        }
    except StoreError as exc:
        checks["tracss_store"] = {"ok": False, "detail": str(exc)}

    kelvins = settings.PROCESSED_DIR / "kelvins"
    kelvins_files = sorted(p.name for p in kelvins.glob("*.parquet")) if kelvins.is_dir() else []
    checks["kelvins_store"] = {"ok": bool(kelvins_files), "files": kelvins_files}

    try:
        reference = verify_reference_case()
        checks["sgp4"] = {
            "ok": bool(reference["within_tolerance"]),
            "reference_case": reference["case"],
            "position_residual_m": round(reference["position_residual_m"], 6),
        }
    except Exception as exc:  # noqa: BLE001 - health must never itself fail
        checks["sgp4"] = {"ok": False, "detail": str(exc)}

    try:
        settings.llm_api_key()
        checks["llm"] = {
            "ok": True,
            "provider": settings.LLM_PROVIDER,
            "model": settings.LLM_MODEL,
        }
    except Exception as exc:  # noqa: BLE001
        # Never echo the value, only the fact that it is unusable.
        checks["llm"] = {"ok": False, "detail": str(exc), "affects": ["/triage"]}

    degraded = [name for name, result in checks.items() if not result.get("ok")]
    return HealthResponse(
        status="ok" if not degraded else "degraded",
        checks=checks,
        provenance={"code_version": code_version(), "degraded": degraded},
    )


# ------------------------------------------------------------------------------------
# physics
# ------------------------------------------------------------------------------------

def _conditioning_block(report: Any) -> dict[str, Any]:
    data = report.as_dict()
    return {
        "was_conditioned": data["was_conditioned"],
        "had_negative_eigenvalue": data["had_negative_eigenvalue"],
        "condition_number": data["condition_number"],
        "smallest_original_eigenvalue": data["smallest_original_eigenvalue"],
        "method": data["method"],
    }


@app.post("/pc", response_model=PcResponse, tags=["physics"])
def compute_pc(request: PcRequest) -> PcResponse:
    """Probability of collision between two objects at TCA, by Alfano (2004).

    ``covariance_frame`` is required and has no default. Two covariances published in
    their own objects' UVW frames cannot be summed until each is rotated to ECI, and doing
    it wrong changes the answer by orders of magnitude with no error anywhere.
    """
    result = pc_from_states(
        position1_km=request.object1.position_km,
        velocity1_kms=request.object1.velocity_kms,
        covariance1=np.array(request.object1.covariance, dtype=float),
        position2_km=request.object2.position_km,
        velocity2_kms=request.object2.velocity_kms,
        covariance2=np.array(request.object2.covariance, dtype=float),
        hbr1_m=request.object1.hard_body_radius_m,
        hbr2_m=request.object2.hard_body_radius_m,
        covariance_frame=request.covariance_frame,
    )
    return PcResponse(
        pc=result.pc,
        log10_pc=float(np.log10(result.pc)) if result.pc > 0 else None,
        miss_distance_km=result.miss_distance_km,
        relative_speed_kms=result.relative_speed_kms,
        combined_hard_body_radius_m=result.combined_hbr_m,
        mahalanobis_distance_2d=result.mahalanobis_distance,
        mahalanobis_distance_3d=result.mahalanobis_distance_3d,
        projected_covariance_km2=result.projected_covariance.tolist(),
        conditioning_2d=_conditioning_block(result.conditioning),
        conditioning_3d=_conditioning_block(result.conditioning_3d),
        provenance=provenance("pc", covariance_frame=request.covariance_frame),
    )


@app.post("/screen", response_model=ScreenResponse, tags=["physics"])
def screen(request: ScreenRequest) -> ScreenResponse:
    """Close approaches between two objects, from their TLEs, inside a window.

    Two-pass: a coarse sweep finds local minima of the range, then each candidate is
    re-propagated finely. A single coarse pass would misplace TCA by up to half a step,
    which at 14 km/s is kilometres of error in the miss distance.
    """
    approaches = screen_pair(
        (request.object1.line1, request.object1.line2),
        (request.object2.line1, request.object2.line2),
        request.start_utc,
        request.stop_utc,
        threshold_km=request.threshold_km,
        coarse_step_seconds=request.coarse_step_seconds,
        refine_step_seconds=request.refine_step_seconds,
    )
    return ScreenResponse(
        approaches=[a.as_dict() for a in approaches],
        count=len(approaches),
        window={
            "start_utc": request.start_utc.isoformat(),
            "stop_utc": request.stop_utc.isoformat(),
            "threshold_km": str(request.threshold_km),
        },
        provenance=provenance(
            "screen",
            object1=request.object1.name,
            object2=request.object2.name,
        ),
    )


# ------------------------------------------------------------------------------------
# benchmark events
# ------------------------------------------------------------------------------------

EVENT_COLUMNS = (
    "event_id, source, tca, miss_distance_km, relative_speed_kms, pc, pc_is_floored, "
    "mahalanobis_distance, dilution, obj1_catalog_id, obj2_catalog_id, "
    "obj1_hbr_m, obj2_hbr_m"
)


def _optional(value: Any) -> Any:
    """None for anything pandas considers missing, so JSON never carries a NaN."""
    if value is None:
        return None
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return None if pd.isna(value) else value


@app.get("/events", response_model=EventsResponse, tags=["benchmark"])
def events(
    source: str = Query("sfsh", description=f"One of {list(SOURCES)}."),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    min_pc: Optional[float] = Query(None, description="Lower bound on published pc."),
    max_pc: Optional[float] = Query(None, description="Upper bound on published pc."),
    exclude_floored: bool = Query(
        False,
        description=(
            "Drop events whose pc sits on the 1e-10 reporting floor. Those are upper "
            "bounds rather than measurements, so include them only knowingly."
        ),
    ),
    max_miss_km: Optional[float] = Query(None, gt=0),
    catalog_id: Optional[str] = Query(
        None, description="Return only events involving this catalogue object."
    ),
    order_by: str = Query("pc_desc", pattern="^(pc_desc|pc_asc|miss_asc|tca_asc)$"),
) -> EventsResponse:
    """Query the ingested TraCSS IV&V benchmark. Read-only.

    A filtered slice is not the population: statistics computed from a result here
    describe the query, not the benchmark. `pc_is_floored` marks censored values and is
    always returned.
    """
    if source not in SOURCES:
        raise StoreError(f"unknown source {source!r}; expected one of {list(SOURCES)}")

    # Parameterised throughout -- nothing from the query string is interpolated into SQL.
    clauses: list[str] = []
    parameters: list[Any] = []
    if min_pc is not None:
        clauses.append("pc >= ?")
        parameters.append(min_pc)
    if max_pc is not None:
        clauses.append("pc <= ?")
        parameters.append(max_pc)
    if exclude_floored:
        clauses.append("not pc_is_floored")
    if max_miss_km is not None:
        clauses.append("miss_distance_km <= ?")
        parameters.append(max_miss_km)
    if catalog_id is not None:
        clauses.append("(obj1_catalog_id = ? or obj2_catalog_id = ?)")
        parameters.extend([catalog_id, catalog_id])

    where = f" where {' and '.join(clauses)}" if clauses else ""
    ordering = {
        "pc_desc": "pc desc nulls last",
        "pc_asc": "pc asc nulls last",
        "miss_asc": "miss_distance_km asc",
        "tca_asc": "tca asc",
    }[order_by]

    total = int(
        store.query(f"select count(*) as n from {source}{where}", parameters or None)
        ["n"].iloc[0]
    )
    frame = store.query(
        f"select {EVENT_COLUMNS} from {source}{where} "
        f"order by {ordering} limit ? offset ?",
        [*parameters, limit, offset],
    )

    rows = [
        EventOut(
            event_id=str(row["event_id"]),
            source=str(row["source"]),
            tca=None if pd.isna(row["tca"]) else row["tca"].isoformat(),
            miss_distance_km=float(row["miss_distance_km"]),
            relative_speed_kms=float(row["relative_speed_kms"]),
            pc=_optional(row["pc"]),
            pc_is_floored=bool(row["pc_is_floored"]),
            mahalanobis_distance=_optional(row["mahalanobis_distance"]),
            dilution=(
                None if pd.isna(row["dilution"]) else int(row["dilution"])
            ),
            object1_catalog_id=str(row["obj1_catalog_id"]),
            object2_catalog_id=str(row["obj2_catalog_id"]),
            object1_hbr_m=_optional(row["obj1_hbr_m"]),
            object2_hbr_m=_optional(row["obj2_hbr_m"]),
        )
        for _, row in frame.iterrows()
    ]

    return EventsResponse(
        events=rows,
        returned=len(rows),
        total_matching=total,
        limit=limit,
        offset=offset,
        filters={
            "source": source, "min_pc": min_pc, "max_pc": max_pc,
            "exclude_floored": exclude_floored, "max_miss_km": max_miss_km,
            "catalog_id": catalog_id, "order_by": order_by,
        },
        provenance=provenance("events", source=source),
    )


# ------------------------------------------------------------------------------------
# triage
# ------------------------------------------------------------------------------------

@app.post("/triage", response_model=TriageResponse, tags=["agent"])
def triage(request: TriageRequest) -> TriageResponse:
    """Run the reasoning agent over Kelvins CDM series.

    **The agent lost.** On the held-out test set it scored L = 1.6606 against the
    latest-CDM baseline's L = 0.6940. The provenance block repeats this and it is not
    decoration: anything consuming these predictions should prefer the baseline.

    Each series costs one LLM call, so the batch is capped at 25. Out-of-scope events (a
    latest visible risk below -7.0) are returned without a call, with the baseline as the
    effective prediction — the same protocol Phase 6 pre-registered and Phase 7 scored.
    """
    from agent.llm import LLMClient, LLMError
    from agent.triage_agent import PROMPT_VERSION, TriageAgent, in_scope
    from core.features import build_dataset
    from core.kelvins_store import load_visible_cdms

    settings.llm_api_key()  # raises MissingCredentialError -> structured 503

    events_frame = build_dataset(request.split)
    events_frame = events_frame.set_index("series_id", drop=False)
    known = [sid for sid in request.series_ids if sid in events_frame.index]
    unknown = [sid for sid in request.series_ids if sid not in events_frame.index]

    cdms_by_series = load_visible_cdms(known, request.split) if known else {}
    client = LLMClient(prompt_version=PROMPT_VERSION)
    agent = TriageAgent(client=client)

    verdicts: list[TriageVerdict] = []
    answered = failed = 0

    for series_id in unknown:
        failed += 1
        verdicts.append(TriageVerdict(
            series_id=series_id, in_scope=False, baseline_risk=float("nan"),
            effective_prediction=float("nan"),
            error=f"{series_id} is not an eligible event in the {request.split} split",
        ))

    for series_id in known:
        row = events_frame.loc[series_id]
        baseline = float(row["latest_risk"])
        scoped = in_scope(baseline)
        if not scoped:
            answered += 1
            verdicts.append(TriageVerdict(
                series_id=series_id, in_scope=False, baseline_risk=baseline,
                effective_prediction=baseline,
            ))
            continue

        cdms = cdms_by_series.get(series_id)
        if cdms is None or cdms.empty:
            failed += 1
            verdicts.append(TriageVerdict(
                series_id=series_id, in_scope=True, baseline_risk=baseline,
                effective_prediction=baseline,
                error="no visible CDMs at or beyond 2 days to TCA",
            ))
            continue

        try:
            verdict, _ = agent.analyse(series_id, cdms, row)
        except (LLMError, ValueError, KeyError) as exc:
            failed += 1
            verdicts.append(TriageVerdict(
                series_id=series_id, in_scope=True, baseline_risk=baseline,
                effective_prediction=baseline, error=str(exc)[:300],
            ))
            continue

        answered += 1
        verdicts.append(TriageVerdict(
            series_id=series_id,
            in_scope=True,
            baseline_risk=baseline,
            predicted_final_risk=verdict.predicted_final_risk,
            effective_prediction=verdict.predicted_final_risk,
            will_collapse=verdict.will_collapse,
            confidence=verdict.confidence,
            reasoning=verdict.reasoning,
            evidence_cited=verdict.evidence_cited,
        ))

    return TriageResponse(
        verdicts=verdicts,
        requested=len(request.series_ids),
        answered=answered,
        failed=failed,
        provenance=provenance(
            "triage",
            split=request.split,
            prompt_version=PROMPT_VERSION,
            provider=settings.LLM_PROVIDER,
            model=settings.LLM_MODEL,
            scope_threshold=-7.0,
        ),
    )
