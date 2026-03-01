"""Tests for CLI Django error handling (T004)."""

from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from taxomesh.adapters.cli.main import app
from taxomesh.exceptions import TaxomeshRepositoryError

runner = CliRunner()


class TestDjangoRepoWrapsImproperlyConfigured:
    def test_django_repo_wraps_improperly_configured(self) -> None:
        """DjangoRepository() raises TaxomeshRepositoryError with 'DJANGO_SETTINGS_MODULE'
        in the message when ImproperlyConfigured is raised during model import."""
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        # Save original module if present
        original = sys.modules.get("taxomesh.contrib.django.models")

        # Create a fake module whose attribute access raises ImproperlyConfigured
        class _FakeModule(types.ModuleType):
            def __getattr__(self, name: str) -> object:
                from django.core.exceptions import (  # type: ignore[import-untyped]  # noqa: PLC0415
                    ImproperlyConfigured,
                )

                raise ImproperlyConfigured("Django settings are not configured")

        fake_module = _FakeModule("taxomesh.contrib.django.models")
        sys.modules["taxomesh.contrib.django.models"] = fake_module

        try:
            with pytest.raises(TaxomeshRepositoryError) as exc_info:
                DjangoRepository()
            assert "DJANGO_SETTINGS_MODULE" in str(exc_info.value)
        finally:
            if original is None:
                sys.modules.pop("taxomesh.contrib.django.models", None)
            else:
                sys.modules["taxomesh.contrib.django.models"] = original


class TestCliExitsWithFriendlyMessageWhenDjangoNotConfigured:
    def test_cli_exits_with_friendly_message_when_django_not_configured(self, tmp_path: Path) -> None:
        """CLI exits with code 1 and 'DJANGO_SETTINGS_MODULE' in output when DjangoRepository
        raises TaxomeshRepositoryError due to missing Django settings."""
        toml_file = tmp_path / "taxomesh.toml"
        toml_file.write_text('[repository]\ntype = "django"\n', encoding="utf-8")

        with patch(
            "taxomesh.adapters.repositories.django_repository.DjangoRepository.__init__",
            side_effect=TaxomeshRepositoryError(
                "Django settings are not configured. "
                "Set the DJANGO_SETTINGS_MODULE environment variable before running "
                "taxomesh with type = 'django'."
            ),
        ):
            result = runner.invoke(app, ["--config", str(toml_file), "category", "list"])

        assert result.exit_code == 1
        output = (result.stdout or "") + (result.stderr if result.stderr else "")
        assert "DJANGO_SETTINGS_MODULE" in output
