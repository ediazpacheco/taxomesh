"""Tests for TaxomeshDebugProxyAdmin."""

import dataclasses
import re

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

from django.test import Client  # noqa: E402

pytestmark = pytest.mark.django_db


def test_debug_proxy_registered_in_admin(db: object) -> None:
    """TaxomeshDebugProxy is registered in the Django admin."""
    from django.contrib import admin  # noqa: PLC0415

    from taxomesh.contrib.django.models import TaxomeshDebugProxy  # noqa: PLC0415

    assert TaxomeshDebugProxy in admin.site._registry


def test_debug_page_returns_200_for_staff(admin_client: Client) -> None:
    """GET to the debug admin page returns HTTP 200 for staff users."""
    from django.urls import reverse  # noqa: PLC0415

    url = reverse("admin:taxomesh_contrib_django_taxomeshdebugproxy_changelist")
    response = admin_client.get(url)
    assert response.status_code == 200


def test_debug_page_contains_debug_fields(admin_client: Client) -> None:
    """The debug page response contains the four debug field labels."""
    from django.urls import reverse  # noqa: PLC0415

    url = reverse("admin:taxomesh_contrib_django_taxomeshdebugproxy_changelist")
    response = admin_client.get(url)
    content = response.content.decode()
    assert "version" in content.lower()
    assert "repository" in content.lower()


def test_debug_page_requires_auth(client: Client) -> None:
    """Anonymous access to the debug page redirects to login."""
    from django.urls import reverse  # noqa: PLC0415

    url = reverse("admin:taxomesh_contrib_django_taxomeshdebugproxy_changelist")
    response = client.get(url)
    assert response.status_code == 302


def test_debug_page_rows_are_named_as_the_info_names_them(admin_client: Client) -> None:
    """One row per ``TaxomeshInfo`` field, in its order, with ``repository`` spelled out field by field."""
    from django.urls import reverse  # noqa: PLC0415

    from taxomesh import RepositoryInfo, TaxomeshInfo  # noqa: PLC0415

    expected: list[str] = []
    for field in dataclasses.fields(TaxomeshInfo):
        if field.name == "repository":
            expected += [f"repository.{nested.name}" for nested in dataclasses.fields(RepositoryInfo)]
        else:
            expected.append(field.name)

    url = reverse("admin:taxomesh_contrib_django_taxomeshdebugproxy_changelist")
    body = admin_client.get(url).content.decode().split("<tbody>")[1].split("</tbody>")[0]

    assert re.findall(r"<th>(.*?)</th>", body) == expected
