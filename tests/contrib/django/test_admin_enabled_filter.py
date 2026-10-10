"""Tests that Django admin call sites use enabled=None.

These tests verify admin views pass enabled=None when listing for display
purposes, so disabled rows are visible in the admin interface.
"""

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

from django.test import Client  # noqa: E402

pytestmark = pytest.mark.django_db


def test_graph_view_lists_all_categories(admin_client: Client) -> None:
    """graph_view should list both enabled and disabled categories."""
    from django.urls import reverse  # noqa: PLC0415

    from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415
    from taxomesh.application.service import TaxomeshService  # noqa: PLC0415

    svc = TaxomeshService(repository=DjangoRepository())
    svc.categories.create(name="AdminVisible")
    cat_off = svc.categories.create(name="AdminHidden")
    cat_off_obj = DjangoRepository().find_category(cat_off.category_id)
    assert cat_off_obj is not None
    DjangoRepository().save_category(cat_off_obj.model_copy(update={"enabled": False}))

    url = reverse("admin:taxomesh_contrib_django_graph")
    response = admin_client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "AdminVisible" in content
    assert "AdminHidden" in content
