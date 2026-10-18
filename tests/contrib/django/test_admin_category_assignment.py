"""The ``categories`` field of ``ItemCategoryAssignmentMixin``, on the admin page of a site's own model.

The pages are driven through Django's test client, with the URLs of ``_consumer_admin``: a group
stands for a record of the site, and its primary key is the external id of an item. The item is
placed in an enabled category and in a disabled one. The field offers the enabled categories only.

A save is judged by the stored placements, read from the ORM.
"""

from dataclasses import dataclass
from html.parser import HTMLParser
from uuid import UUID

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

from django.contrib.auth.models import Group, Permission, User  # noqa: E402
from django.test import Client  # noqa: E402
from django.urls import reverse  # noqa: E402

from taxomesh import TaxomeshService  # noqa: E402
from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: E402
from taxomesh.contrib.django.models import ItemParentLinkModel  # noqa: E402

pytestmark = [pytest.mark.django_db, pytest.mark.urls("tests.contrib.django._consumer_admin")]

CATEGORIES_FIELD = "categories"


@dataclass(frozen=True)
class _Record:
    """A group, the item that stands for it, and the categories of the tests."""

    group: Group
    item_id: UUID
    news: UUID  # enabled; the item is placed in it
    archive: UUID  # disabled; the item is placed in it
    sport: UUID  # enabled; the item is not placed in it


@pytest.fixture
def record() -> _Record:
    svc = TaxomeshService(DjangoRepository(), cache_ttl=0)
    group = Group.objects.create(name="Article")
    item = svc.items.create("Article", external_id=group.pk)
    news = svc.categories.create("News")
    archive = svc.categories.create("Archive")
    sport = svc.categories.create("Sport")
    svc.items.place_in(item, news)
    svc.items.place_in(item, archive)
    svc.categories.update(archive, enabled=False)
    return _Record(group, item.item_id, news.category_id, archive.category_id, sport.category_id)


def _placements(record: _Record) -> set[str]:
    """The names of the categories that the stored placements of the record's item name."""
    links = ItemParentLinkModel.objects.filter(item_id=record.item_id)
    return set(links.values_list("category__name", flat=True))


def _change_url(record: _Record, site: str = "admin") -> str:
    return reverse(f"{site}:auth_group_change", args=[record.group.pk])


class _PostedByThePage(HTMLParser):
    """What a browser posts for the text and hidden inputs and the multiple selects of a page, read as it renders.

    Such an input sends its value. A multiple select sends each selected option, and nothing when no
    option is selected.
    """

    def __init__(self) -> None:
        super().__init__()
        self.data: dict[str, list[str]] = {}
        self._select: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        name = attributes.get("name")
        if tag == "input" and attributes.get("type") in ("text", "hidden") and name:
            self.data.setdefault(name, []).append(attributes.get("value") or "")
        elif tag == "select" and "multiple" in attributes and name:
            self._select = name
            self.data.setdefault(name, [])
        elif tag == "option" and self._select is not None and "selected" in attributes:
            self.data[self._select].append(attributes.get("value") or "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "select":
            self._select = None


def _as_the_page_posts(client: Client, url: str, **fields: str | list[str]) -> dict[str, str | list[str]]:
    """The data a browser posts for the page at ``url``: what the page renders, then ``fields``."""
    parser = _PostedByThePage()
    parser.feed(client.get(url).content.decode())
    posted: dict[str, str | list[str]] = dict(parser.data)
    posted.update(fields)
    return posted


class TestTheFieldIsOnThePage:
    """The admin of the mixin's docstring, which declares no ``fields``, shows the field."""

    def test_the_change_page_shows_it(self, admin_client: Client, record: _Record) -> None:
        page = admin_client.get(_change_url(record)).content.decode()

        assert f'name="{CATEGORIES_FIELD}"' in page

    def test_the_add_page_shows_it(self, admin_client: Client) -> None:
        page = admin_client.get(reverse("admin:auth_group_add")).content.decode()

        assert f'name="{CATEGORIES_FIELD}"' in page

    def test_it_selects_the_placements_it_offers(self, admin_client: Client, record: _Record) -> None:
        posted = _as_the_page_posts(admin_client, _change_url(record))

        assert posted[CATEGORIES_FIELD] == [str(record.news)]

    def test_a_page_that_only_shows_the_record_leaves_it_out(self, record: _Record) -> None:
        viewer = User.objects.create_user("viewer", password="x", is_staff=True)
        viewer.user_permissions.set(Permission.objects.filter(codename="view_group"))
        client = Client()
        client.force_login(viewer)

        response = client.get(_change_url(record))

        assert response.status_code == 200
        assert "Categories" not in response.content.decode()


class TestASaveChangesThePlacementsTheFieldOffers:
    """A save changes placements only when the page shows the field, and only in the categories it offers."""

    def test_a_save_of_the_page_as_it_renders_keeps_every_placement(
        self, admin_client: Client, record: _Record
    ) -> None:
        url = _change_url(record)

        response = admin_client.post(url, _as_the_page_posts(admin_client, url, name="Article edited"))

        assert response.status_code == 302
        assert _placements(record) == {"News", "Archive"}

    def test_a_save_that_posts_no_field_keeps_every_placement(self, admin_client: Client, record: _Record) -> None:
        response = admin_client.post(_change_url(record), {"name": "Article edited"})

        assert response.status_code == 302
        assert _placements(record) == {"News", "Archive"}

    def test_a_save_places_the_item_in_a_selected_category_and_removes_it_from_another(
        self, admin_client: Client, record: _Record
    ) -> None:
        url = _change_url(record)
        posted = _as_the_page_posts(admin_client, url, categories=[str(record.sport)])

        response = admin_client.post(url, posted)

        assert response.status_code == 302
        assert _placements(record) == {"Sport", "Archive"}

    def test_a_save_with_no_category_selected_keeps_the_one_the_field_does_not_offer(
        self, admin_client: Client, record: _Record
    ) -> None:
        url = _change_url(record)
        posted = _as_the_page_posts(admin_client, url, categories=[])

        response = admin_client.post(url, posted)

        assert response.status_code == 302
        assert _placements(record) == {"Archive"}

    def test_an_admin_whose_fields_leave_it_out_changes_no_placement(
        self, admin_client: Client, record: _Record
    ) -> None:
        url = _change_url(record, site="fields_admin")
        page = admin_client.get(url)
        assert f'name="{CATEGORIES_FIELD}"' not in page.content.decode()
        assert CATEGORIES_FIELD not in page.context["adminform"].form.fields
        posted = _as_the_page_posts(admin_client, url, name="Article edited", categories=[str(record.sport)])

        response = admin_client.post(url, posted)

        assert response.status_code == 302
        assert _placements(record) == {"News", "Archive"}
