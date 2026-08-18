"""Configuration and credential access for the ConjunctionTriage Agent.

Importing this module never fails and never requires credentials, so the whole project
stays importable (and testable) on a machine with no ``.env`` at all. Credentials are
resolved **lazily**: a component that needs one calls the corresponding accessor, and
that accessor raises :class:`MissingCredentialError` if the value is absent or is still
an unedited placeholder.

Secret values are never logged, printed, or included in exception messages or reprs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Optional

from dotenv import load_dotenv

__all__ = [
    "ConfigError",
    "MissingCredentialError",
    "Settings",
    "settings",
    "REPO_ROOT",
]

#: Repository root, derived from this file's location (``core/config.py`` -> parent^2).
REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent

#: Substrings that mark a value as an unedited template rather than a real credential.
#: ``.env`` ships with ``your_..._here`` placeholders, which must never be treated as
#: usable credentials -- doing so would surface as a confusing 401 much later.
_PLACEHOLDER_MARKERS: Final[tuple[str, ...]] = (
    "your_",
    "_here",
    "changeme",
    "change_me",
    "placeholder",
    "replace_me",
    "xxxxx",
    "todo",
    "<",
    ">",
)


class ConfigError(RuntimeError):
    """Base class for configuration problems."""


class MissingCredentialError(ConfigError):
    """A required credential is absent, empty, or still an unedited placeholder.

    The offending variable is named; its value is never included.
    """

    def __init__(self, variable: str, reason: str) -> None:
        self.variable = variable
        self.reason = reason
        super().__init__(
            f"{variable} is {reason}. Set it in {REPO_ROOT / '.env'} "
            f"(see .env.example). Value not shown."
        )


def _is_placeholder(value: str) -> bool:
    """Whether ``value`` looks like an unedited template entry."""
    lowered = value.strip().lower()
    return any(marker in lowered for marker in _PLACEHOLDER_MARKERS)


@dataclass(frozen=True)
class Settings:
    """Typed access to project paths and credentials.

    Paths are always available. Credentials raise on access when unusable -- see
    :meth:`require`.
    """

    repo_root: Path = REPO_ROOT

    # -- derived paths -----------------------------------------------------------------

    @property
    def DATASET_DIR(self) -> Path:
        """Read-only benchmark data. **Never** written to by any phase."""
        return self.repo_root / "dataset"

    @property
    def PROCESSED_DIR(self) -> Path:
        """Derived artefacts (normalised records, metrics tables)."""
        return self.repo_root / "processed"

    @property
    def CACHE_DIR(self) -> Path:
        """Cached responses from live sources."""
        return self.repo_root / "cache"

    @property
    def FIXTURES_DIR(self) -> Path:
        """Small committed samples the offline test suite runs against."""
        return self.repo_root / "tests" / "fixtures"

    def ensure_dirs(self) -> None:
        """Create the writable derived directories. Never touches :attr:`DATASET_DIR`."""
        for path in (self.PROCESSED_DIR, self.CACHE_DIR):
            path.mkdir(parents=True, exist_ok=True)

    # -- credentials -------------------------------------------------------------------

    def get(self, variable: str) -> Optional[str]:
        """Return a raw environment value, or ``None`` if unset/empty/placeholder.

        Non-raising counterpart to :meth:`require`, for callers that want to branch on
        availability rather than fail. Never logs the value.
        """
        value = os.environ.get(variable)
        if value is None:
            return None
        value = value.strip()
        if not value or _is_placeholder(value):
            return None
        return value

    def require(self, variable: str) -> str:
        """Return a credential or raise :class:`MissingCredentialError`.

        Fails loud: an unset variable and an unedited placeholder are both errors, never
        silently substituted with a default.
        """
        raw = os.environ.get(variable)
        if raw is None:
            raise MissingCredentialError(variable, "not set")
        stripped = raw.strip()
        if not stripped:
            raise MissingCredentialError(variable, "set but empty")
        if _is_placeholder(stripped):
            raise MissingCredentialError(
                variable, "still an unedited placeholder from .env.example"
            )
        return stripped

    def is_available(self, variable: str) -> bool:
        """Whether :meth:`require` would succeed for ``variable``."""
        return self.get(variable) is not None

    @property
    def ANTHROPIC_API_KEY(self) -> str:
        """Anthropic API key. Raises if unusable. Needed from Phase 7 (agent) onward."""
        return self.require("ANTHROPIC_API_KEY")

    @property
    def SPACETRACK_EMAIL(self) -> str:
        """Space-Track account email. Raises if unusable."""
        return self.require("SPACETRACK_EMAIL")

    @property
    def SPACETRACK_PASSWORD(self) -> str:
        """Space-Track account password. Raises if unusable."""
        return self.require("SPACETRACK_PASSWORD")

    def __repr__(self) -> str:
        """Report credential *availability* only -- never a value."""
        status = {
            name: ("set" if self.is_available(name) else "missing-or-placeholder")
            for name in (
                "ANTHROPIC_API_KEY",
                "SPACETRACK_EMAIL",
                "SPACETRACK_PASSWORD",
            )
        }
        return f"Settings(repo_root={self.repo_root!s}, credentials={status})"


# Populate os.environ from .env at import. `override=False` so a real environment
# variable always beats the file, which matters in CI. This reads configuration only --
# no credential is validated here, so import stays safe without a .env.
load_dotenv(REPO_ROOT / ".env", override=False)

#: Shared instance. Import this rather than constructing your own.
settings: Final[Settings] = Settings()
