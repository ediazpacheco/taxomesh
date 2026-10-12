"""A category given as its own parent is refused in one wording, whichever way it comes in.

The service's ``add_parent`` and ``move``, both forms of the admin and the admin's graph view all
refuse it. The refusal has one text, so an operator who meets it in the admin reads what a caller of
the service reads.
"""

import json
from unittest.mock import MagicMock
from uuid import UUID

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

from django.core.exceptions import ValidationError  # noqa: E402
from django.test import Client  # noqa: E402
from django.urls import reverse  # noqa: E402

from taxomesh import TaxomeshCyclicDependencyError, TaxomeshService  # noqa: E402
from taxomesh.contrib.django.admin import CategoryChildLinkForm, CategoryParentLinkForm  # noqa: E402
from taxomesh.contrib.django.models import CategoryModel  # noqa: E402
from taxomesh.repositories import DjangoRepository  # noqa: E402

pytestmark = pytest.mark.django_db


def _expected(category_id: UUID) -> str:
    return f"Category {category_id} cannot be its own parent"


def _cleaned(form_class: type[CategoryParentLinkForm] | type[CategoryChildLinkForm], category_id: UUID) -> None:
    """Run ``clean()`` of a form that holds the category as both ends of the link."""
    form = form_class.__new__(form_class)
    cat = MagicMock(spec=CategoryModel)
    cat.category_id = category_id
    form.cleaned_data = {"category": cat, "parent_category": cat, "sort_index": 0}
    form.clean()


class TestOneWordingForACategoryAsItsOwnParent:
    def test_add_parent(self) -> None:
        service = TaxomeshService(repository=DjangoRepository())
        category = service.categories.create("Jazz")

        with pytest.raises(TaxomeshCyclicDependencyError) as raised:
            service.categories.add_parent(category, category)

        assert str(raised.value) == _expected(category.category_id)

    def test_move(self) -> None:
        service = TaxomeshService(repository=DjangoRepository())
        category = service.categories.create("Jazz")

        with pytest.raises(TaxomeshCyclicDependencyError) as raised:
            service.categories.move(category, from_parent=None, to_parent=category)

        assert str(raised.value) == _expected(category.category_id)

    @pytest.mark.parametrize("form_class", [CategoryParentLinkForm, CategoryChildLinkForm])
    def test_the_admin_forms(self, form_class: type[CategoryParentLinkForm] | type[CategoryChildLinkForm]) -> None:
        service = TaxomeshService(repository=DjangoRepository())
        category = service.categories.create("Jazz")

        with pytest.raises(ValidationError) as raised:
            _cleaned(form_class, category.category_id)

        assert raised.value.messages == [_expected(category.category_id)]

    def test_the_admin_graph_view(self, admin_client: Client) -> None:
        service = TaxomeshService(repository=DjangoRepository())
        category = service.categories.create("Jazz")
        payload = {
            "kind": "category",
            "node_uuid": str(category.category_id),
            "old_parent_uuid": "",
            "new_parent_uuid": str(category.category_id),
            "insert_before_uuid": None,
        }

        response = admin_client.post(
            reverse("admin:taxomesh_contrib_django_graph_reparent"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 400
        assert _expected(category.category_id) in json.loads(response.content)["error"]
