"""Canonical record type for the ConjunctionTriage Agent.

The benchmark data defines the schema. Every source -- the TraCSS IV&V benchmark files,
CelesTrak, Space-Track -- normalises into :class:`ConjunctionEvent`. Live sources adapt
to this shape, never the reverse: the IV&V files carry state vectors and 3x3 covariances
that are precisely the inputs a collision-probability computation needs, and a
CelesTrak-shaped record has nowhere to put them.

Fields a live source cannot supply are ``Optional``, so a CelesTrak-derived record with
no state vector is still a valid :class:`ConjunctionEvent`.

Units
-----
Positions km, velocities km/s, position covariance km^2, hard-body radius metres,
times timezone-aware UTC.

Design rules enforced here
--------------------------
* **Fail loud.** A missing or unparseable field raises; nothing is silently defaulted.
* **``pc`` is censored.** The benchmark reports a floor of 1e-10 rather than a
  measurement. :attr:`ConjunctionEvent.pc_is_floored` records this per record so that
  downstream log-transforms, ROC curves and distribution statistics can handle it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Optional, Sequence

import numpy as np

__all__ = [
    "PC_FLOOR",
    "KELVINS_PC_FLOOR",
    "SOURCE_PC_FLOOR",
    "EventSource",
    "SchemaValidationError",
    "ObjectState",
    "ConjunctionEvent",
    "ConjunctionEventSeries",
]

#: Reporting floor of the ``prob`` column in the TraCSS IV&V benchmark. Values at this
#: value are censored -- the true probability is somewhere at or below it, unknown.
PC_FLOOR = 1e-10

#: Reporting floor of the ESA Kelvins ``risk`` column, which is log10(Pc) and is clamped
#: at exactly -30.0. Like the TraCSS floor this is a bound, not a measurement -- but it is
#: a *different* bound, so the two datasets' censored populations are not comparable.
KELVINS_PC_FLOOR = 1e-30

#: Timestamp layouts accepted for the IV&V ``epoch`` column, most specific first.
_EPOCH_FORMATS = ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S")


class EventSource(str, Enum):
    """Where a record originated. Inherits ``str`` so it serialises transparently."""

    TRACSS_SPHERICAL = "TRACSS_SPHERICAL"
    TRACSS_SFSH = "TRACSS_SFSH"
    KELVINS = "KELVINS"
    CELESTRAK = "CELESTRAK"
    SPACETRACK = "SPACETRACK"


#: Canonical benchmark filename backing each TraCSS source, used as default provenance.
SOURCE_FILENAMES: dict[EventSource, str] = {
    EventSource.TRACSS_SPHERICAL: "IVV_Releasable_Dataset_Spherical_DefaultHBR.csv",
    EventSource.TRACSS_SFSH: "IVV_Releasable_Dataset_SFSH_DiscreteHBR.csv",
}


#: Reporting floor per source. ``None`` means the source publishes no floor, so no value
#: can be treated as censored. Sources differ: TraCSS clamps Pc at 1e-10, Kelvins clamps
#: log10(Pc) at -30. Using one floor for both would mislabel 41% of Kelvins CDMs.
SOURCE_PC_FLOOR: dict[EventSource, Optional[float]] = {
    EventSource.TRACSS_SPHERICAL: PC_FLOOR,
    EventSource.TRACSS_SFSH: PC_FLOOR,
    EventSource.KELVINS: KELVINS_PC_FLOOR,
    EventSource.CELESTRAK: None,
    EventSource.SPACETRACK: None,
}


class SchemaValidationError(ValueError):
    """Raised when a record is structurally or physically invalid.

    Always raised rather than repaired: a silent substitution makes a broken run look
    like a working one.
    """


# --------------------------------------------------------------------------------------
# helpers -- every one of these raises rather than substituting a default
# --------------------------------------------------------------------------------------

def _require(row: Mapping[str, Any], column: str) -> Any:
    """Fetch ``column`` from ``row`` or raise. Missing data is never defaulted."""
    try:
        value = row[column]
    except (KeyError, IndexError) as exc:
        raise SchemaValidationError(f"missing required column {column!r}") from exc
    if value is None:
        raise SchemaValidationError(f"column {column!r} is null")
    return value


def _as_float(value: Any, column: str) -> float:
    """Coerce to a finite float or raise, naming the offending column."""
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise SchemaValidationError(
            f"column {column!r} is not numeric: {value!r}"
        ) from exc
    if not math.isfinite(out):
        raise SchemaValidationError(f"column {column!r} is not finite: {out!r}")
    return out


def _as_optional_float(value: Any, column: str) -> Optional[float]:
    """Like :func:`_as_float`, but maps a genuinely absent value to ``None``."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, str) and value.strip() in {"", "NaN", "nan", "N/A", "NA"}:
        return None
    return _as_float(value, column)


def _as_triple(
    values: Sequence[Any], columns: Sequence[str]
) -> tuple[float, float, float]:
    """Build a fixed 3-tuple of finite floats from three named columns."""
    if len(values) != 3:
        raise SchemaValidationError(f"expected 3 values for {tuple(columns)}")
    a, b, c = (_as_float(v, col) for v, col in zip(values, columns))
    return (a, b, c)


def _parse_epoch_utc(value: Any, column: str = "epoch") -> datetime:
    """Parse an IV&V epoch string into a timezone-aware UTC datetime.

    The benchmark supplies naive timestamps with no offset. They are documented as UTC,
    so UTC is attached explicitly here -- the schema never carries a naive datetime.
    """
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        raise SchemaValidationError(f"column {column!r} is empty")
    for fmt in _EPOCH_FORMATS:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:  # ISO-8601, possibly already carrying an offset
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise SchemaValidationError(
            f"column {column!r} is not a recognised timestamp: {text!r}"
        ) from exc
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _covariance_from_triangular(
    c11: float, c12: float, c13: float, c22: float, c23: float, c33: float
) -> np.ndarray:
    """Reconstruct a full symmetric 3x3 covariance from six upper-triangular elements.

    The benchmark stores only the upper triangle. Mirroring it across the diagonal gives
    the full matrix, which is symmetric by construction::

        [[c11, c12, c13],
         [c12, c22, c23],
         [c13, c23, c33]]
    """
    return np.array(
        [[c11, c12, c13], [c12, c22, c23], [c13, c23, c33]],
        dtype=np.float64,
    )


def _is_positive_semidefinite(matrix: np.ndarray, tol: float = 1e-10) -> bool:
    """True when the smallest eigenvalue is non-negative within ``tol``.

    ``eigvalsh`` is used because the matrix is symmetric by construction; a small
    negative tolerance absorbs floating-point noise in near-singular covariances.
    """
    eigenvalues = np.linalg.eigvalsh(matrix)
    scale = max(1.0, float(np.max(np.abs(eigenvalues))))
    return bool(np.min(eigenvalues) >= -tol * scale)


# --------------------------------------------------------------------------------------
# per-object state
# --------------------------------------------------------------------------------------

@dataclass(eq=False)
class ObjectState:
    """State of one of the two objects in a conjunction.

    ``eq=False`` because the dataclass-generated ``__eq__`` would compare the covariance
    with ``==``, which yields an array and raises on truth-testing. :meth:`__eq__` below
    compares it elementwise instead.
    """

    catalog_id: str
    #: ECI position, km. ``None`` for sources that do not publish state vectors.
    position_km: Optional[tuple[float, float, float]] = None
    #: ECI velocity, km/s.
    velocity_kms: Optional[tuple[float, float, float]] = None
    #: Position in the local UVW (radial / in-track / cross-track) frame, km.
    local_position_km: Optional[tuple[float, float, float]] = None
    #: Full symmetric 3x3 position covariance in the UVW frame, km^2.
    covariance: Optional[np.ndarray] = None
    #: Hard-body radius, metres. Populated in Phase 2 from the ScreeningVolumes file.
    hbr_m: Optional[float] = None
    #: Whether this object met the screening criteria for the event.
    met_criteria: Optional[bool] = None
    #: Originating per-object file (e.g. ``59208.ocm``), if the source names one.
    source_filename: Optional[str] = None

    # -- construction ------------------------------------------------------------------

    @classmethod
    def from_ivv_row(cls, row: Mapping[str, Any], index: int) -> "ObjectState":
        """Build the state of object ``index`` (1 or 2) from one IV&V CSV row."""
        if index not in (1, 2):
            raise SchemaValidationError(f"object index must be 1 or 2, got {index!r}")
        i = index

        pos_cols = (f"x{i}", f"y{i}", f"z{i}")
        vel_cols = (f"vx{i}", f"vy{i}", f"vz{i}")
        loc_cols = (f"local_x{i}", f"local_y{i}", f"local_z{i}")
        cov_cols = (
            f"c{i}_11",
            f"c{i}_12",
            f"c{i}_13",
            f"c{i}_22",
            f"c{i}_23",
            f"c{i}_33",
        )

        covariance = _covariance_from_triangular(
            *(_as_float(_require(row, c), c) for c in cov_cols)
        )

        criteria_raw = _require(row, f"met_criteria{i}")
        filename = row.get(f"obj{i}_filename")

        return cls(
            catalog_id=str(_require(row, f"obj{i}")).strip(),
            position_km=_as_triple([_require(row, c) for c in pos_cols], pos_cols),
            velocity_kms=_as_triple([_require(row, c) for c in vel_cols], vel_cols),
            local_position_km=_as_triple([_require(row, c) for c in loc_cols], loc_cols),
            covariance=covariance,
            hbr_m=None,  # Phase 2, from AerospaceIVVDataset_..._ScreeningVolumes.csv
            met_criteria=bool(int(_as_float(criteria_raw, f"met_criteria{i}"))),
            source_filename=None if filename is None else str(filename).strip(),
        )

    # -- serialisation -----------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Plain-Python representation. Round-trips exactly through :meth:`from_dict`."""
        return {
            "catalog_id": self.catalog_id,
            "position_km": (
                None if self.position_km is None else list(self.position_km)
            ),
            "velocity_kms": (
                None if self.velocity_kms is None else list(self.velocity_kms)
            ),
            "local_position_km": (
                None if self.local_position_km is None else list(self.local_position_km)
            ),
            "covariance": None if self.covariance is None else self.covariance.tolist(),
            "hbr_m": self.hbr_m,
            "met_criteria": self.met_criteria,
            "source_filename": self.source_filename,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ObjectState":
        """Inverse of :meth:`to_dict`."""

        def triple(key: str) -> Optional[tuple[float, float, float]]:
            value = payload.get(key)
            if value is None:
                return None
            return _as_triple(list(value), (key, key, key))

        covariance = payload.get("covariance")
        return cls(
            catalog_id=str(_require(payload, "catalog_id")),
            position_km=triple("position_km"),
            velocity_kms=triple("velocity_kms"),
            local_position_km=triple("local_position_km"),
            covariance=(
                None if covariance is None else np.asarray(covariance, dtype=np.float64)
            ),
            hbr_m=payload.get("hbr_m"),
            met_criteria=payload.get("met_criteria"),
            source_filename=payload.get("source_filename"),
        )

    # -- validation --------------------------------------------------------------------

    def validate(self, label: str = "object") -> None:
        """Raise :class:`SchemaValidationError` if this state is not physically sane."""
        if not self.catalog_id:
            raise SchemaValidationError(f"{label}: catalog_id is empty")

        for name, vector in (
            ("position_km", self.position_km),
            ("velocity_kms", self.velocity_kms),
            ("local_position_km", self.local_position_km),
        ):
            if vector is None:
                continue
            if len(vector) != 3:
                raise SchemaValidationError(
                    f"{label}: {name} must have 3 components, got {len(vector)}"
                )
            if not all(math.isfinite(float(v)) for v in vector):
                raise SchemaValidationError(f"{label}: {name} is not finite: {vector!r}")

        if self.hbr_m is not None and (not math.isfinite(self.hbr_m) or self.hbr_m < 0):
            raise SchemaValidationError(f"{label}: hbr_m must be finite and >= 0")

        if self.covariance is None:
            return

        cov = self.covariance
        if cov.shape != (3, 3):
            raise SchemaValidationError(
                f"{label}: covariance must be 3x3, got {cov.shape}"
            )
        if not np.isfinite(cov).all():
            raise SchemaValidationError(f"{label}: covariance is not finite")
        if not np.allclose(cov, cov.T, rtol=1e-12, atol=1e-12):
            raise SchemaValidationError(f"{label}: covariance is not symmetric")
        if not _is_positive_semidefinite(cov):
            raise SchemaValidationError(
                f"{label}: covariance is not positive-semidefinite "
                f"(min eigenvalue {float(np.min(np.linalg.eigvalsh(cov))):.6g})"
            )

    # -- equality ----------------------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ObjectState):
            return NotImplemented
        if (self.covariance is None) != (other.covariance is None):
            return False
        if self.covariance is not None and not np.array_equal(
            self.covariance, other.covariance
        ):
            return False
        return (
            self.catalog_id == other.catalog_id
            and self.position_km == other.position_km
            and self.velocity_kms == other.velocity_kms
            and self.local_position_km == other.local_position_km
            and self.hbr_m == other.hbr_m
            and self.met_criteria == other.met_criteria
            and self.source_filename == other.source_filename
        )


# --------------------------------------------------------------------------------------
# the canonical event
# --------------------------------------------------------------------------------------

@dataclass(eq=False)
class ConjunctionEvent:
    """A single close approach between two catalogued objects.

    The one record type every data source normalises into. See module docstring.
    """

    # -- identity ----------------------------------------------------------------------
    event_id: str
    run_id: int
    conj_id: str
    source: EventSource
    #: Exactly which file or endpoint this record came from. Free text, always populated.
    provenance: str

    # -- encounter geometry ------------------------------------------------------------
    #: Time of closest approach, timezone-aware UTC. ``None`` for anonymised sources that
    #: publish no absolute epoch (ESA Kelvins), in which case
    #: :attr:`time_to_tca_days` carries the only temporal information available.
    tca: Optional[datetime]
    #: Julian date of TCA as published by the source (days).
    jdate: Optional[float]
    #: Miss distance at TCA, km.
    miss_distance_km: float
    #: Relative speed at TCA, km/s.
    relative_speed_kms: Optional[float]
    #: Mahalanobis distance between the objects, dimensionless (sigma).
    mahalanobis_distance: Optional[float]
    #: Dilution indicator as published. Observed values in the benchmark are 0 and 1;
    #: exact semantics are unconfirmed pending the Users Guide, so it is carried through
    #: verbatim rather than reinterpreted.
    dilution: Optional[float]

    # -- risk --------------------------------------------------------------------------
    #: Collision probability, dimensionless in [0, 1]. ``None`` when unpublished.
    pc: Optional[float]
    #: True when ``pc`` sits at the reporting floor (:data:`PC_FLOOR`) and is therefore
    #: censored -- a bound, not a measurement.
    pc_is_floored: bool

    #: Interval from record creation to TCA, days. The only temporal information an
    #: anonymised source provides; decreases toward 0 as a conjunction is refined.
    #: Declared here rather than beside ``tca`` because it carries a default and a
    #: dataclass cannot place a defaulted field before undefaulted ones.
    time_to_tca_days: Optional[float] = None

    # -- the two objects ---------------------------------------------------------------
    object1: ObjectState = field(default_factory=lambda: ObjectState(catalog_id=""))
    object2: ObjectState = field(default_factory=lambda: ObjectState(catalog_id=""))

    # -- construction ------------------------------------------------------------------

    @classmethod
    def from_ivv_row(
        cls,
        row: Mapping[str, Any],
        source: EventSource,
        provenance: Optional[str] = None,
    ) -> "ConjunctionEvent":
        """Build an event from one row of a TraCSS IV&V CSV.

        ``row`` may be a dict or a pandas ``Series``. ``provenance`` defaults to the
        canonical benchmark filename for ``source``.
        """
        source = EventSource(source)
        if provenance is None:
            provenance = SOURCE_FILENAMES.get(source, source.value)

        run_id = int(_as_float(_require(row, "run_id"), "run_id"))
        conj_id = str(_require(row, "conj_id")).strip()
        pc = _as_optional_float(row.get("prob"), "prob")

        return cls(
            event_id=f"{source.value}:{run_id}:{conj_id}",
            run_id=run_id,
            conj_id=conj_id,
            source=source,
            provenance=provenance,
            tca=_parse_epoch_utc(_require(row, "epoch")),
            jdate=_as_optional_float(row.get("jdate"), "jdate"),
            miss_distance_km=_as_float(_require(row, "min_range"), "min_range"),
            relative_speed_kms=_as_optional_float(row.get("Vrel"), "Vrel"),
            mahalanobis_distance=_as_optional_float(row.get("mdistance"), "mdistance"),
            dilution=_as_optional_float(row.get("dilution"), "dilution"),
            pc=pc,
            pc_is_floored=cls.compute_pc_is_floored(pc, SOURCE_PC_FLOOR[source]),
            object1=ObjectState.from_ivv_row(row, 1),
            object2=ObjectState.from_ivv_row(row, 2),
        )

    @property
    def pc_floor(self) -> Optional[float]:
        """The reporting floor for this record's source, or ``None`` if it has none.

        Sources clamp at different values -- TraCSS at Pc 1e-10, Kelvins at log10(Pc)
        = -30 -- so the floor must be resolved per source, never assumed.
        """
        return SOURCE_PC_FLOOR.get(self.source)

    @staticmethod
    def compute_pc_is_floored(
        pc: Optional[float], floor: Optional[float] = PC_FLOOR
    ) -> bool:
        """Whether ``pc`` is censored at ``floor``.

        Uses ``<=`` rather than ``==`` so that any value at or below the floor is
        treated as censored; nothing below it can be a real measurement. ``floor`` of
        ``None`` means the source publishes no floor, so nothing is censored.
        """
        if pc is None or floor is None:
            return False
        return pc <= floor

    # -- serialisation -----------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Plain-Python representation. Round-trips exactly through :meth:`from_dict`.

        ``tca`` is emitted as an ISO-8601 string *with* its UTC offset, so the
        timezone survives the round trip.
        """
        return {
            "event_id": self.event_id,
            "run_id": self.run_id,
            "conj_id": self.conj_id,
            "source": self.source.value,
            "provenance": self.provenance,
            "tca": None if self.tca is None else self.tca.isoformat(),
            "jdate": self.jdate,
            "miss_distance_km": self.miss_distance_km,
            "relative_speed_kms": self.relative_speed_kms,
            "mahalanobis_distance": self.mahalanobis_distance,
            "dilution": self.dilution,
            "pc": self.pc,
            "pc_is_floored": self.pc_is_floored,
            "time_to_tca_days": self.time_to_tca_days,
            "object1": self.object1.to_dict(),
            "object2": self.object2.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ConjunctionEvent":
        """Inverse of :meth:`to_dict`."""
        raw_tca = payload.get("tca")
        tca = None if raw_tca is None else _parse_epoch_utc(raw_tca, "tca")
        return cls(
            event_id=str(_require(payload, "event_id")),
            run_id=int(_require(payload, "run_id")),
            conj_id=str(_require(payload, "conj_id")),
            source=EventSource(_require(payload, "source")),
            provenance=str(_require(payload, "provenance")),
            tca=tca,
            jdate=payload.get("jdate"),
            miss_distance_km=_as_float(
                _require(payload, "miss_distance_km"), "miss_distance_km"
            ),
            relative_speed_kms=payload.get("relative_speed_kms"),
            mahalanobis_distance=payload.get("mahalanobis_distance"),
            dilution=payload.get("dilution"),
            pc=payload.get("pc"),
            pc_is_floored=bool(_require(payload, "pc_is_floored")),
            time_to_tca_days=payload.get("time_to_tca_days"),
            object1=ObjectState.from_dict(_require(payload, "object1")),
            object2=ObjectState.from_dict(_require(payload, "object2")),
        )

    # -- validation --------------------------------------------------------------------

    def validate(self) -> None:
        """Raise :class:`SchemaValidationError` if this record is invalid.

        Checks, in order: timezone-aware ``tca``; non-negative finite miss distance;
        ``pc`` within [0, 1]; the ``pc_is_floored`` flag agreeing with ``pc``; and for
        each object, finite state vectors and a symmetric positive-semidefinite
        covariance.
        """
        if not self.event_id:
            raise SchemaValidationError("event_id is empty")

        if self.tca is None:
            # An anonymised source has no absolute epoch, but a record with neither an
            # absolute nor a relative time has no temporal anchor at all and is useless.
            if self.time_to_tca_days is None:
                raise SchemaValidationError(
                    "a record must carry either tca or time_to_tca_days; both are absent"
                )
        elif self.tca.tzinfo is None or self.tca.utcoffset() is None:
            raise SchemaValidationError(
                "tca must be timezone-aware; got a naive datetime"
            )

        if self.time_to_tca_days is not None and not math.isfinite(self.time_to_tca_days):
            raise SchemaValidationError("time_to_tca_days is not finite")

        if not math.isfinite(self.miss_distance_km):
            raise SchemaValidationError("miss_distance_km is not finite")
        if self.miss_distance_km < 0:
            raise SchemaValidationError(
                f"miss_distance_km must be >= 0, got {self.miss_distance_km!r}"
            )

        if self.pc is not None:
            if not math.isfinite(self.pc):
                raise SchemaValidationError("pc is not finite")
            if not 0.0 <= self.pc <= 1.0:
                raise SchemaValidationError(f"pc must lie in [0, 1], got {self.pc!r}")

        expected_floor = self.pc_floor
        if self.pc_is_floored != self.compute_pc_is_floored(self.pc, expected_floor):
            raise SchemaValidationError(
                f"pc_is_floored={self.pc_is_floored} contradicts pc={self.pc!r} "
                f"(floor for {self.source.value}: "
                f"{'none' if expected_floor is None else format(expected_floor, 'g')})"
            )

        if self.relative_speed_kms is not None and not math.isfinite(
            self.relative_speed_kms
        ):
            raise SchemaValidationError("relative_speed_kms is not finite")

        self.object1.validate("object1")
        self.object2.validate("object2")

    # -- equality ----------------------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ConjunctionEvent):
            return NotImplemented
        return self.to_dict() == other.to_dict() and (
            self.object1 == other.object1 and self.object2 == other.object2
        )

    def __repr__(self) -> str:  # keep covariance arrays out of the representation
        return (
            f"ConjunctionEvent(event_id={self.event_id!r}, "
            f"tca={'none' if self.tca is None else self.tca.isoformat()}, "
            f"miss_distance_km={self.miss_distance_km:.6g}, pc={self.pc!r}, "
            f"pc_is_floored={self.pc_is_floored}, "
            f"objects=({self.object1.catalog_id}, {self.object2.catalog_id}))"
        )
