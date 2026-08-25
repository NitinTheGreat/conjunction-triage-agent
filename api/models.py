"""Request and response schemas for the API.

Validation is deliberately strict. Every physical quantity carries its unit in the field
description so the generated OpenAPI page is self-documenting, and every input that could
be silently misinterpreted -- above all the covariance frame -- is required rather than
defaulted.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

Vector3 = Annotated[list[float], Field(min_length=3, max_length=3)]


class ObjectState(BaseModel):
    """One object's state and position covariance at TCA."""

    position_km: Vector3 = Field(
        ..., description="Position in km, J2000/ECI, as [x, y, z]."
    )
    velocity_kms: Vector3 = Field(
        ..., description="Velocity in km/s, J2000/ECI, as [vx, vy, vz]."
    )
    covariance: list[list[float]] = Field(
        ...,
        description=(
            "3x3 position covariance in km^2. Its frame is declared by the request's "
            "`covariance_frame` field, not inferred."
        ),
    )
    hard_body_radius_m: float = Field(
        ..., gt=0, le=1000,
        description="Hard-body radius in metres. The combined radius is the sum of both.",
    )
    catalog_id: Optional[str] = Field(
        None, description="Optional catalogue identifier, echoed back unchanged."
    )

    @field_validator("covariance")
    @classmethod
    def _shape_and_symmetry(cls, value: list[list[float]]) -> list[list[float]]:
        if len(value) != 3 or any(len(row) != 3 for row in value):
            raise ValueError("covariance must be 3x3")
        for i in range(3):
            for j in range(i + 1, 3):
                a, b = value[i][j], value[j][i]
                scale = max(abs(a), abs(b), 1e-30)
                if abs(a - b) / scale > 1e-6:
                    raise ValueError(
                        f"covariance is not symmetric at ({i},{j}): {a} vs {b}"
                    )
        return value


class PcRequest(BaseModel):
    """Probability of collision between two objects at TCA."""

    object1: ObjectState
    object2: ObjectState
    covariance_frame: Literal["uvw", "eci"] = Field(
        ...,
        description=(
            "Frame of BOTH covariances. `uvw` means each is in its own object's local "
            "radial/in-track/cross-track frame, which is how TraCSS publishes them; `eci` "
            "means both are already inertial. Required with no default: getting it wrong "
            "changes the answer by orders of magnitude without any error."
        ),
    )

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "object1": {
                    "position_km": [7000.0, 0.0, 0.0],
                    "velocity_kms": [0.0, 7.5, 0.0],
                    "covariance": [[0.01, 0, 0], [0, 4.0, 0], [0, 0, 0.02]],
                    "hard_body_radius_m": 5.0,
                },
                "object2": {
                    "position_km": [7000.0, 0.0, 0.4],
                    "velocity_kms": [0.0, 0.0, 7.5],
                    "covariance": [[0.02, 0, 0], [0, 9.0, 0], [0, 0, 0.03]],
                    "hard_body_radius_m": 3.0,
                },
                "covariance_frame": "uvw",
            }]
        }
    }


class ConditioningBlock(BaseModel):
    """Whether a covariance had to be repaired before it could be used."""

    was_conditioned: bool
    had_negative_eigenvalue: bool
    condition_number: float
    smallest_original_eigenvalue: float
    method: str


class PcResponse(BaseModel):
    pc: float = Field(..., description="Probability of collision in [0, 1].")
    log10_pc: Optional[float] = Field(
        None, description="log10(pc), or null when pc is exactly zero."
    )
    miss_distance_km: float
    relative_speed_kms: float
    combined_hard_body_radius_m: float
    mahalanobis_distance_2d: float = Field(
        ..., description="In the encounter plane -- the space the Alfano integral works in."
    )
    mahalanobis_distance_3d: float = Field(
        ..., description="Full 3D. This is the quantity TraCSS publishes as `mdistance`."
    )
    projected_covariance_km2: list[list[float]]
    conditioning_2d: ConditioningBlock
    conditioning_3d: ConditioningBlock
    provenance: dict[str, Any]


class TwoLineElement(BaseModel):
    line1: str = Field(..., min_length=60, max_length=80)
    line2: str = Field(..., min_length=60, max_length=80)
    name: Optional[str] = None


class ScreenRequest(BaseModel):
    """Screen two objects for close approaches inside a time window."""

    object1: TwoLineElement
    object2: TwoLineElement
    start_utc: datetime = Field(..., description="Window start, timezone-aware UTC.")
    stop_utc: datetime = Field(..., description="Window end, timezone-aware UTC.")
    threshold_km: float = Field(
        10.0, gt=0, le=1000, description="Report approaches closer than this, in km."
    )
    coarse_step_seconds: float = Field(60.0, gt=0, le=3600)
    refine_step_seconds: float = Field(0.5, gt=0, le=60)

    @model_validator(mode="after")
    def _window_is_sane(self) -> "ScreenRequest":
        if self.start_utc.tzinfo is None or self.stop_utc.tzinfo is None:
            raise ValueError("start_utc and stop_utc must be timezone-aware")
        if self.stop_utc <= self.start_utc:
            raise ValueError("stop_utc must be after start_utc")
        span_days = (self.stop_utc - self.start_utc).total_seconds() / 86400
        if span_days > 30:
            raise ValueError(
                f"window is {span_days:.1f} days; TLE accuracy degrades badly beyond a "
                "few days, so windows longer than 30 are refused rather than served"
            )
        if self.refine_step_seconds > self.coarse_step_seconds:
            raise ValueError("refine_step_seconds must not exceed coarse_step_seconds")
        return self


class CloseApproachOut(BaseModel):
    tca_utc: str
    miss_distance_km: float
    relative_speed_kms: float
    object1: dict[str, Any]
    object2: dict[str, Any]
    frame: str


class ScreenResponse(BaseModel):
    approaches: list[CloseApproachOut]
    count: int
    window: dict[str, str]
    provenance: dict[str, Any]


class EventOut(BaseModel):
    event_id: str
    source: str
    tca: Optional[str]
    miss_distance_km: float
    relative_speed_kms: float
    pc: Optional[float]
    pc_is_floored: bool
    mahalanobis_distance: Optional[float]
    dilution: Optional[int]
    object1_catalog_id: str
    object2_catalog_id: str
    object1_hbr_m: Optional[float]
    object2_hbr_m: Optional[float]


class EventsResponse(BaseModel):
    events: list[EventOut]
    returned: int
    total_matching: int
    limit: int
    offset: int
    filters: dict[str, Any]
    provenance: dict[str, Any]


class TriageRequest(BaseModel):
    """Run the reasoning agent over Kelvins CDM series."""

    series_ids: list[str] = Field(
        ..., min_length=1, max_length=25,
        description=(
            "Kelvins series identifiers from the test split. Capped at 25 per request: "
            "each one is a billed LLM call."
        ),
    )
    split: Literal["test", "train"] = Field(
        "test", description="Which ingested Kelvins split to read the CDMs from."
    )


class TriageVerdict(BaseModel):
    series_id: str
    in_scope: bool = Field(
        ...,
        description=(
            "The agent is a corrector on an alert queue: it is invoked only when the "
            "latest visible risk is at or above -7.0. Out-of-scope events fall through "
            "to the baseline, which is what the Phase 6/7 protocol evaluated."
        ),
    )
    baseline_risk: float = Field(..., description="B1: the latest visible CDM's risk.")
    predicted_final_risk: Optional[float] = None
    effective_prediction: float = Field(
        ...,
        description="What the arm actually predicts: the agent's value in scope, B1 out.",
    )
    will_collapse: Optional[bool] = None
    confidence: Optional[str] = None
    reasoning: Optional[str] = None
    evidence_cited: list[dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None


class TriageResponse(BaseModel):
    verdicts: list[TriageVerdict]
    requested: int
    answered: int
    failed: int
    provenance: dict[str, Any]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    checks: dict[str, Any]
    provenance: dict[str, Any]


class ErrorBody(BaseModel):
    """Every error the API returns, including unhandled ones."""

    error: str = Field(..., description="Stable machine-readable code.")
    detail: str = Field(..., description="What went wrong, in a sentence.")
    hint: Optional[str] = Field(None, description="What the caller can do about it.")
    request_id: Optional[str] = None
