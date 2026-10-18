"""Which model the link to a site's record opens on each admin page, and when a page shows the ↗ row.

``TAXOMESH_LINKED_MODEL`` names the model of the records that items stand for.
``TAXOMESH_CATEGORY_LINKED_MODEL`` names the model for categories; while it is not set, categories
use ``TAXOMESH_LINKED_MODEL``. The test settings set neither, and each test sets the ones it needs.
"""

import re
from dataclasses import dataclass
from uuid import UUID

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

from django.test import Client  # noqa: E402
from django.urls import reverse  # noqa: E402
from pytest_django.fixtures import SettingsWrapper  # noqa: E402

from taxomesh import TaxomeshService  # noqa: E402
from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: E402

pytestmark = pytest.mark.django_db

USER_MODEL = "auth.User"
GROUP_MODEL = "auth.Group"
LINK_ROW = "field-linked_object_url"  # the class of the ↗ row on a change page


@dataclass(frozen=True)
class _Rows:
    """A category with the external id 1, its child with 2, and an item in the category with 1."""

    category_id: UUID
    child_id: UUID
    item_id: UUID


@pytest.fixture
def rows() -> _Rows:
    svc = TaxomeshService(DjangoRepository(), cache_ttl=0)
    category = svc.categories.create("Linked", external_id=1)
    child = svc.categories.create("Child", external_id=2)
    svc.categories.add_parent(child, category)
    item = svc.items.create("Linked item", external_id=1)
    svc.items.place_in(item, category)
    return _Rows(category.category_id, child.category_id, item.item_id)


def _record_links(client: Client, url: str) -> list[str]:
    """The links of a page to the change page of a record of the ``auth`` app."""
    page = client.get(url).content.decode()
    return sorted(set(re.findall(r'href="(/admin/auth/[a-z]+/\d+/change/)"', page)))


def _category_page(rows: _Rows) -> str:
    return reverse("admin:taxomesh_contrib_django_categorymodel_change", args=[rows.category_id])


def _item_page(rows: _Rows) -> str:
    return reverse("admin:taxomesh_contrib_django_itemmodel_change", args=[rows.item_id])


def _graph_branch(rows: _Rows) -> str:
    return f"{reverse('admin:taxomesh_contrib_django_graph_children')}?parent_uuid={rows.category_id}&depth=1"


class TestACategoryLinksToTheModelOfItsSetting:
    """Every page that links a category opens a record of the model that the category setting names."""

    @pytest.fixture(autouse=True)
    def _both_settings(self, settings: SettingsWrapper) -> None:
        settings.TAXOMESH_CATEGORY_LINKED_MODEL = USER_MODEL
        settings.TAXOMESH_LINKED_MODEL = GROUP_MODEL

    def test_the_category_page(self, admin_client: Client, rows: _Rows) -> None:
        assert _record_links(admin_client, _category_page(rows)) == ["/admin/auth/user/1/change/"]

    def test_the_category_list(self, admin_client: Client, rows: _Rows) -> None:
        url = reverse("admin:taxomesh_contrib_django_categorymodel_changelist")

        assert _record_links(admin_client, url) == ["/admin/auth/user/1/change/", "/admin/auth/user/2/change/"]

    def test_the_graph_page(self, admin_client: Client, rows: _Rows) -> None:
        url = reverse("admin:taxomesh_contrib_django_graph")

        assert _record_links(admin_client, url) == ["/admin/auth/user/1/change/"]

    def test_a_graph_branch_links_its_category_to_a_user_and_its_item_to_a_group(
        self, admin_client: Client, rows: _Rows
    ) -> None:
        links = _record_links(admin_client, _graph_branch(rows))

        assert links == ["/admin/auth/group/1/change/", "/admin/auth/user/2/change/"]

    def test_the_item_page_links_to_the_model_of_the_item_setting(self, admin_client: Client, rows: _Rows) -> None:
        assert _record_links(admin_client, _item_page(rows)) == ["/admin/auth/group/1/change/"]


class TestACategoryLinksWithTheCategorySettingAlone:
    """With the category setting alone, every page links a category, and no page links an item."""

    @pytest.fixture(autouse=True)
    def _category_setting(self, settings: SettingsWrapper) -> None:
        settings.TAXOMESH_CATEGORY_LINKED_MODEL = USER_MODEL

    def test_the_category_list(self, admin_client: Client, rows: _Rows) -> None:
        url = reverse("admin:taxomesh_contrib_django_categorymodel_changelist")

        assert _record_links(admin_client, url) == ["/admin/auth/user/1/change/", "/admin/auth/user/2/change/"]

    def test_the_graph_page(self, admin_client: Client, rows: _Rows) -> None:
        url = reverse("admin:taxomesh_contrib_django_graph")

        assert _record_links(admin_client, url) == ["/admin/auth/user/1/change/"]

    def test_a_graph_branch(self, admin_client: Client, rows: _Rows) -> None:
        assert _record_links(admin_client, _graph_branch(rows)) == ["/admin/auth/user/2/change/"]


class TestAChangePageShowsTheLinkRowWhileASettingApplies:
    """The ↗ row of a change page shows only while a setting names the model of its records."""

    def test_with_neither_setting_no_page_shows_it(self, admin_client: Client, rows: _Rows) -> None:
        for url in (
            _category_page(rows),
            _item_page(rows),
            reverse("admin:taxomesh_contrib_django_categorymodel_add"),
            reverse("admin:taxomesh_contrib_django_itemmodel_add"),
        ):
            assert LINK_ROW not in admin_client.get(url).content.decode(), url

    def test_with_the_item_setting_both_pages_show_it(
        self, admin_client: Client, rows: _Rows, settings: SettingsWrapper
    ) -> None:
        settings.TAXOMESH_LINKED_MODEL = GROUP_MODEL

        assert LINK_ROW in admin_client.get(_category_page(rows)).content.decode()
        assert LINK_ROW in admin_client.get(_item_page(rows)).content.decode()

    def test_with_the_category_setting_alone_only_the_category_page_shows_it(
        self, admin_client: Client, rows: _Rows, settings: SettingsWrapper
    ) -> None:
        settings.TAXOMESH_CATEGORY_LINKED_MODEL = USER_MODEL

        assert LINK_ROW in admin_client.get(_category_page(rows)).content.decode()
        assert LINK_ROW not in admin_client.get(_item_page(rows)).content.decode()
