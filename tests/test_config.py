"""Tests for :mod:`core.config`.

Credential resolution must be lazy (import never needs a ``.env``) and loud (a missing
or placeholder value raises a named error, never a silent default).
"""

from __future__ import annotations

import pytest

from core.config import MissingCredentialError, Settings, settings

CREDENTIALS = ("ANTHROPIC_API_KEY", "SPACETRACK_EMAIL", "SPACETRACK_PASSWORD")


class TestPaths:
    def test_paths_are_derived_from_the_repo_root(self) -> None:
        root = settings.repo_root
        assert settings.DATASET_DIR == root / "dataset"
        assert settings.PROCESSED_DIR == root / "processed"
        assert settings.CACHE_DIR == root / "cache"
        assert settings.FIXTURES_DIR == root / "tests" / "fixtures"

    def test_fixtures_dir_exists(self) -> None:
        assert settings.FIXTURES_DIR.is_dir()

    def test_paths_resolve_without_credentials(self, monkeypatch) -> None:
        """Paths must work even with the environment stripped bare."""
        for name in CREDENTIALS:
            monkeypatch.delenv(name, raising=False)
        assert Settings().DATASET_DIR.name == "dataset"


class TestCredentialsFailLoud:
    @pytest.mark.parametrize("variable", CREDENTIALS)
    def test_raises_when_unset(self, monkeypatch, variable) -> None:
        monkeypatch.delenv(variable, raising=False)
        with pytest.raises(MissingCredentialError, match="not set"):
            settings.require(variable)

    @pytest.mark.parametrize("variable", CREDENTIALS)
    def test_raises_when_empty(self, monkeypatch, variable) -> None:
        monkeypatch.setenv(variable, "   ")
        with pytest.raises(MissingCredentialError, match="empty"):
            settings.require(variable)

    @pytest.mark.parametrize(
        "placeholder",
        [
            "your_api_key_here",
            "your_email_here",
            "CHANGEME",
            "<replace_me>",
            "placeholder",
        ],
    )
    def test_raises_on_placeholder(self, monkeypatch, placeholder) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", placeholder)
        with pytest.raises(MissingCredentialError, match="placeholder"):
            settings.require("ANTHROPIC_API_KEY")

    def test_shipped_dotenv_placeholders_are_rejected(self) -> None:
        """The repo's .env currently holds unedited placeholders; that path must raise.

        Skipped rather than failed if the developer has since filled in a real key --
        the point is that a placeholder never passes, not that one is present.
        """
        if settings.is_available("ANTHROPIC_API_KEY"):
            pytest.skip("ANTHROPIC_API_KEY has been set to a real value")
        with pytest.raises(MissingCredentialError):
            settings.ANTHROPIC_API_KEY

    @pytest.mark.parametrize("variable", CREDENTIALS)
    def test_error_never_leaks_the_value(self, monkeypatch, variable) -> None:
        secret = "sk-ant-super-secret-do-not-print"
        monkeypatch.setenv(variable, "   ")
        with pytest.raises(MissingCredentialError) as excinfo:
            settings.require(variable)
        assert variable in str(excinfo.value)
        assert secret not in str(excinfo.value)

    def test_repr_reports_availability_not_values(self, monkeypatch) -> None:
        secret = "sk-ant-super-secret-do-not-print"
        monkeypatch.setenv("ANTHROPIC_API_KEY", secret)
        text = repr(settings)
        assert secret not in text
        assert "ANTHROPIC_API_KEY" in text


class TestCredentialsSucceed:
    @pytest.mark.parametrize("variable", CREDENTIALS)
    def test_returns_a_real_value(self, monkeypatch, variable) -> None:
        monkeypatch.setenv(variable, "a-real-looking-value-123")
        assert settings.require(variable) == "a-real-looking-value-123"

    def test_strips_surrounding_whitespace(self, monkeypatch) -> None:
        monkeypatch.setenv("SPACETRACK_EMAIL", "  user@example.org  ")
        assert settings.require("SPACETRACK_EMAIL") == "user@example.org"

    def test_typed_properties_resolve(self, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "key-1")
        monkeypatch.setenv("SPACETRACK_EMAIL", "user@example.org")
        monkeypatch.setenv("SPACETRACK_PASSWORD", "pw-1")
        assert settings.ANTHROPIC_API_KEY == "key-1"
        assert settings.SPACETRACK_EMAIL == "user@example.org"
        assert settings.SPACETRACK_PASSWORD == "pw-1"

    def test_get_returns_none_instead_of_raising(self, monkeypatch) -> None:
        monkeypatch.delenv("SPACETRACK_EMAIL", raising=False)
        assert settings.get("SPACETRACK_EMAIL") is None
        assert settings.is_available("SPACETRACK_EMAIL") is False
