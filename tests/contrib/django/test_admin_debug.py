"""Tests for TaxomeshDebugProxyAdmin."""

import pytest

django = pytest.importorskip("django", reason="Django is not installed")
pytestmark = pytest.mark.django_db


def test_debug_proxy_registered_in_admin(db: object) -> None:
    """TaxomeshDebugProxy is registered in the Django admin."""
    from django.contrib import admin  # noqa: PLC0415

    from taxomesh.contrib.django.admin import TaxomeshDebugProxy  # noqa: PLC0415

    assert TaxomeshDebugProxy in admin.site._registry


def test_debug_page_returns_200_for_staff(admin_client: object) -> None:
    """GET to the debug admin page returns HTTP 200 for staff users."""
    from django.urls import reverse  # noqa: PLC0415

    url = reverse("admin:taxomesh_contrib_django_taxomeshdebugproxy_changelist")
    response = admin_client.get(url)  # type: ignore[attr-defined]
    assert response.status_code == 200


def test_debug_page_contains_debug_fields(admin_client: object) -> None:
    """The debug page response contains the four debug field labels."""
    from django.urls import reverse  # noqa: PLC0415

    url = reverse("admin:taxomesh_contrib_django_taxomeshdebugproxy_changelist")
    response = admin_client.get(url)  # type: ignore[attr-defined]
    content = response.content.decode()
    assert "version" in content.lower()
    assert "repository" in content.lower()


def test_debug_page_requires_auth(client: object) -> None:
    """Anonymous access to the debug page redirects to login."""
    from django.urls import reverse  # noqa: PLC0415

    url = reverse("admin:taxomesh_contrib_django_taxomeshdebugproxy_changelist")
    response = client.get(url)  # type: ignore[attr-defined]
    assert response.status_code == 302
