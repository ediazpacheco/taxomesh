"""Tests that Django admin call sites use enabled=None (spec 046).

These tests verify admin views pass enabled=None when listing for display
purposes, so disabled records are visible in the admin interface.

Written before implementation (TDD-first).
"""

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

pytestmark = pytest.mark.django_db


def test_graph_view_lists_all_categories(admin_client: object) -> None:
    """graph_view should list both enabled and disabled categories."""
    from django.urls import reverse  # noqa: PLC0415

    from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415
    from taxomesh.application.service import TaxomeshService  # noqa: PLC0415

    svc = TaxomeshService(repository=DjangoRepository())
    svc.create_category(name="AdminVisible")
    cat_off = svc.create_category(name="AdminHidden")
    cat_off_obj = DjangoRepository().get_category(cat_off.category_id)
    assert cat_off_obj is not None
    cat_off_obj.enabled = False
    DjangoRepository().save_category(cat_off_obj)

    url = reverse("admin:taxomesh_contrib_django_graph")
    response = admin_client.get(url)  # type: ignore[attr-defined]
    assert response.status_code == 200
    content = response.content.decode()
    assert "AdminVisible" in content
    assert "AdminHidden" in content
