"""Admin registration smoke tests for taxomesh Django models."""

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

from django.contrib import admin  # noqa: E402

from taxomesh.contrib.django.models import (  # noqa: E402
    CategoryModel,
    ItemModel,
    TagModel,
)

pytestmark = pytest.mark.django_db


def test_core_models_registered_in_admin() -> None:
    registered = set(admin.site._registry.keys())
    expected = {CategoryModel, ItemModel, TagModel}
    missing = expected - registered
    assert not missing, f"Models not registered in admin: {missing}"


def test_core_models_admin_plural_labels() -> None:
    assert CategoryModel._meta.verbose_name_plural == "Categories"
    assert ItemModel._meta.verbose_name_plural == "Items"
    assert TagModel._meta.verbose_name_plural == "Tags"


# ---------------------------------------------------------------------------
# T012 — TestGraphAdminView
# ---------------------------------------------------------------------------


class TestGraphAdminView:
    """Tests for the taxonomy graph admin view."""

    def test_graph_url_is_registered(self) -> None:
        """reverse('admin:taxomesh_contrib_django_graph') must not raise NoReverseMatch."""
        from django.urls import reverse  # noqa: PLC0415

        url = reverse("admin:taxomesh_contrib_django_graph")
        assert url  # Does not raise NoReverseMatch

    def test_graph_view_returns_200_for_staff_user(self, admin_client: object) -> None:
        """GET the graph URL as a staff user must return HTTP 200."""
        from django.urls import reverse  # noqa: PLC0415

        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)  # type: ignore[attr-defined]
        assert response.status_code == 200

    def test_graph_view_shows_category_name(self, admin_client: object) -> None:
        """GET the graph URL shows category names from the database."""
        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        svc.create_category(name="TestCategory")
        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)  # type: ignore[attr-defined]
        assert b"TestCategory" in response.content

    def test_graph_view_empty_state_message(self, admin_client: object) -> None:
        """GET the graph URL with no categories shows the empty-state message."""
        from django.urls import reverse  # noqa: PLC0415

        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)  # type: ignore[attr-defined]
        assert response.status_code == 200
        assert b"No categories" in response.content

    def test_graph_view_shows_error_on_db_failure(self, admin_client: object) -> None:
        """GET the graph URL with a mocked DB failure shows error in content, status 200."""
        from unittest.mock import patch  # noqa: PLC0415

        from django.urls import reverse  # noqa: PLC0415

        from taxomesh.exceptions import TaxomeshError  # noqa: PLC0415

        url = reverse("admin:taxomesh_contrib_django_graph")
        with patch(
            "taxomesh.application.service.TaxomeshService.get_graph",
            side_effect=TaxomeshError("db error"),
        ):
            response = admin_client.get(url)  # type: ignore[attr-defined]
        assert response.status_code == 200
        assert b"db error" in response.content


# ---------------------------------------------------------------------------
# T020 — Proxy model: Graph link on main admin index
# ---------------------------------------------------------------------------


class TestGraphProxyAdminIndex:
    """Tests for CategoryGraphProxy surfacing the Graph link on the main admin index."""

    def test_graph_proxy_model_appears_in_admin_app_list(self, admin_client: object) -> None:
        """GET /admin/ must contain 'Graph' — the proxy model row in the Taxomesh section."""
        from django.urls import reverse  # noqa: PLC0415

        url = reverse("admin:index")
        response = admin_client.get(url)  # type: ignore[attr-defined]
        assert response.status_code == 200
        assert b"Graph" in response.content

    def test_graph_proxy_changelist_redirects(self, admin_client: object) -> None:
        """GET /admin/taxomesh_contrib_django/categorygraphproxy/ must 302 to the graph view URL."""
        from django.urls import reverse  # noqa: PLC0415

        changelist_url = reverse("admin:taxomesh_contrib_django_categorygraphproxy_changelist")
        graph_url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(changelist_url)  # type: ignore[attr-defined]
        assert response.status_code == 302
        assert response["Location"] == graph_url
