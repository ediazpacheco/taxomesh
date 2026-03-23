"""Tests for _resolve_linked_url() WARNING log behaviour in taxomesh Django admin."""

import logging

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

ADMIN_LOGGER = "taxomesh.contrib.django.admin"


def test_missing_setting_key_emits_warning(caplog: pytest.LogCaptureFixture) -> None:
    """Missing Django settings key emits a WARNING containing the setting name."""
    from taxomesh.contrib.django.admin import _resolve_linked_url  # noqa: PLC0415

    with caplog.at_level(logging.WARNING, logger=ADMIN_LOGGER):
        result = _resolve_linked_url("ext-123", "TAXOMESH_NONEXISTENT_SETTING_XYZ")

    assert result is None
    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warning_records) == 1
    msg = warning_records[0].getMessage()
    assert "TAXOMESH_NONEXISTENT_SETTING_XYZ" in msg


def test_url_resolution_failure_emits_warning(caplog: pytest.LogCaptureFixture) -> None:
    """URL resolution failure emits a WARNING containing external_id, setting name and exception."""
    from django.conf import settings as django_settings  # noqa: PLC0415

    from taxomesh.contrib.django.admin import _resolve_linked_url  # noqa: PLC0415

    setting_name = "TAXOMESH_LINKED_MODEL"
    # Point to a non-existent model label so get_model() raises LookupError
    django_settings.TAXOMESH_LINKED_MODEL = "nonexistent_app.NonexistentModel"
    try:
        with caplog.at_level(logging.WARNING, logger=ADMIN_LOGGER):
            result = _resolve_linked_url("ext-456", setting_name)
    finally:
        del django_settings.TAXOMESH_LINKED_MODEL

    assert result is None
    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warning_records) == 1
    msg = warning_records[0].getMessage()
    assert "ext-456" in msg
    assert setting_name in msg


def test_successful_resolution_no_warning(caplog: pytest.LogCaptureFixture) -> None:
    """No WARNING emitted when external_id is None (early return before any setting lookup)."""
    from taxomesh.contrib.django.admin import _resolve_linked_url  # noqa: PLC0415

    with caplog.at_level(logging.WARNING, logger=ADMIN_LOGGER):
        result = _resolve_linked_url(None, "TAXOMESH_LINKED_MODEL")

    assert result is None
    assert not any(r.levelno == logging.WARNING for r in caplog.records)
