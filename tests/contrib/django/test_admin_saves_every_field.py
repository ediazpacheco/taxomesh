"""The Django admin saves every field its forms show.

Each admin page saves the row it edits through the service rather than ``obj.save()``, so a field
the service call does not pass would be dropped without a word: the form shows the edit, the page
reports success, and the stored row does not take it. The fields at risk are an item's external id,
a category's and an item's enabled state (on create, which the service's ``create`` does not take,
and on change), and a tag's metadata on create and on change. The pages at risk are a category's
change page at the top level, which must save as the browser renders it and still offer a way off
the top level, and a tag's, which must save a tag holding no metadata and an emptied metadata box.

A save is judged by the **stored** row, not by the service call: the routing tests beside this file
already pin which member is called, and a call that omits a keyword passes them. A refusal is judged
by what the form or the page reports.
"""

import re
from html.parser import HTMLParser
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

from django.contrib import admin, messages  # noqa: E402
from django.contrib.admin.models import LogEntry  # noqa: E402
from django.http import HttpRequest  # noqa: E402
from django.test import Client, RequestFactory  # noqa: E402
from django.urls import reverse  # noqa: E402

from taxomesh import TaxomeshService  # noqa: E402
from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: E402
from taxomesh.contrib.django.admin import CategoryModelAdmin, ItemModelAdmin, TagModelAdmin  # noqa: E402
from taxomesh.contrib.django.models import CategoryModel, CategoryParentLinkModel, ItemModel, TagModel  # noqa: E402
from taxomesh.domain.constants import ROOT_CATEGORY_NAME  # noqa: E402

pytestmark = pytest.mark.django_db

CATEGORY_ADD_URL_NAME = "admin:taxomesh_contrib_django_categorymodel_add"
CATEGORY_CHANGE_URL_NAME = "admin:taxomesh_contrib_django_categorymodel_change"
TAG_ADD_URL_NAME = "admin:taxomesh_contrib_django_tagmodel_add"
TAG_CHANGE_URL_NAME = "admin:taxomesh_contrib_django_tagmodel_change"
TOP_LEVEL_BOX = "at_top_level"  # the read-only flag; a box of that name is ignored


def _request() -> HttpRequest:
    """A bare POST; no save below reaches ``message_user`` unless the test replaces it."""
    return RequestFactory().post("/")


def _category_form_data(name: str) -> dict[str, str]:
    """The category form's own fields, as the add page posts them with every box left as it opens."""
    return {
        "name": name,
        "slug": "",
        "description": "",
        "enabled": "on",
        "external_id": "",
        "metadata": "{}",
    }


def _category_change_url(category_id: UUID) -> str:
    """The change page of one category."""
    return reverse(CATEGORY_CHANGE_URL_NAME, args=[category_id])


def _parent_names(category_id: UUID) -> set[str]:
    """The names of the parents a category's stored links point at, the implicit root's included."""
    links = CategoryParentLinkModel.objects.filter(category_id=category_id)
    return set(links.values_list("parent_category__name", flat=True))


def _with_empty_inlines(client: Client, url: str, data: dict[str, str]) -> dict[str, str]:
    """Add an empty management form for each inline the page at ``url`` renders.

    The add view validates every inline formset it shows, and a formset posted without its
    management form is rejected before the page's own form is looked at. Reading the prefixes off
    the page keeps this in step with whichever inlines the admin declares.
    """
    page = client.get(url).content.decode()
    posted = dict(data)
    for prefix in sorted(set(re.findall(r'name="([\w-]+)-TOTAL_FORMS"', page))):
        posted[f"{prefix}-TOTAL_FORMS"] = "0"
        posted[f"{prefix}-INITIAL_FORMS"] = "0"
    return posted


class _SubmittedForm(HTMLParser):
    """What a browser submits for an admin page's own form, read off the page as it renders.

    An input sends its value, and a checkbox only when checked. A select sends its selected option,
    else its first, and nothing at all when it renders no option. A textarea sends its text. The
    rows an inline keeps as a template (``__prefix__``) and the CSRF token are left out.
    """

    def __init__(self) -> None:
        super().__init__()
        self.data: dict[str, str] = {}
        self._in_form = False
        self._select: str | None = None
        self._textarea: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "form":
            self._in_form = (attributes.get("id") or "").endswith("_form")
            return
        if not self._in_form:
            return
        if tag == "option" and self._select is not None:
            if "selected" in attributes or self._select not in self.data:
                self.data[self._select] = attributes.get("value") or ""
            return
        name = attributes.get("name")
        if name is None or "__prefix__" in name or name == "csrfmiddlewaretoken":
            return
        if tag == "input":
            kind = attributes.get("type") or "text"
            if kind in ("checkbox", "radio"):
                if "checked" in attributes:
                    self.data[name] = attributes.get("value") or "on"
            elif kind not in ("submit", "button", "reset", "image", "file"):
                self.data[name] = attributes.get("value") or ""
        elif tag == "select":
            self._select = name
        elif tag == "textarea":
            self._textarea = name
            self.data[name] = ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "form":
            self._in_form = False
        elif tag == "select":
            self._select = None
        elif tag == "textarea" and self._textarea is not None:
            # HTML drops the one newline that may follow the opening tag.
            text = self.data[self._textarea]
            self.data[self._textarea] = text.removeprefix("\n")
            self._textarea = None

    def handle_data(self, data: str) -> None:
        if self._textarea is not None:
            self.data[self._textarea] += data


def _as_rendered(client: Client, url: str) -> dict[str, str]:
    """The data a browser posts when the page at ``url`` is saved without an edit."""
    form = _SubmittedForm()
    form.feed(client.get(url).content.decode())
    return form.data


def _service() -> TaxomeshService:
    """A service over the admin's own storage, to build rows as the library builds them."""
    return TaxomeshService(repository=DjangoRepository())


class TestAnEditReachesStorage:
    """A changed field is stored, for each of the three fields a save could drop."""

    def test_an_items_external_id(self) -> None:
        item_admin = ItemModelAdmin(ItemModel, admin.site)
        obj = ItemModel(name="Kind of Blue", external_id="old", slug="", metadata={})
        item_admin.save_model(_request(), obj, MagicMock(), False)

        row = ItemModel.objects.get(pk=obj.item_id)
        row.external_id = "new"
        item_admin.save_model(_request(), row, MagicMock(), True)

        assert ItemModel.objects.get(pk=obj.item_id).external_id == "new"

    def test_a_categorys_enabled_state(self) -> None:
        category_admin = CategoryModelAdmin(CategoryModel, admin.site)
        obj = CategoryModel(name="Jazz", description="", slug="", metadata={}, external_id=None)
        category_admin.save_model(_request(), obj, MagicMock(), False)

        row = CategoryModel.objects.get(pk=obj.category_id)
        row.enabled = False
        category_admin.save_model(_request(), row, MagicMock(), True)

        assert CategoryModel.objects.get(pk=obj.category_id).enabled is False

    def test_a_tags_metadata_on_create(self) -> None:
        """Stored, and under the identifier the service assigned, which ``obj`` now carries."""
        tag_admin = TagModelAdmin(TagModel, admin.site)
        obj = TagModel(tag_id=uuid4(), name="classic", metadata={"k": "v"})
        tag_admin.save_model(_request(), obj, MagicMock(), False)

        assert TagModel.objects.get(pk=obj.tag_id).metadata == {"k": "v"}

    def test_a_tags_metadata_on_change(self) -> None:
        """Seeded through the ORM so this test depends on the change path alone."""
        tag_admin = TagModelAdmin(TagModel, admin.site)
        row = TagModel.objects.create(tag_id=uuid4(), name="classic", metadata={})

        row.metadata = {"x": 1}
        tag_admin.save_model(_request(), row, MagicMock(), True)

        assert TagModel.objects.get(pk=row.tag_id).metadata == {"x": 1}


class TestACreateKeepsItsEnabledState:
    """A box left unchecked on an add form is stored unchecked.

    ``categories.create`` and ``items.create`` take no enabled state — every new row starts
    enabled — so the save has to apply the form's value itself. It did not, and the row was stored
    enabled under a page that reported success.
    """

    @pytest.mark.parametrize("enabled", [True, False])
    def test_a_category(self, enabled: bool) -> None:
        category_admin = CategoryModelAdmin(CategoryModel, admin.site)
        obj = CategoryModel(name="Jazz", description="", slug="", metadata={}, external_id=None, enabled=enabled)
        category_admin.save_model(_request(), obj, MagicMock(), False)

        assert CategoryModel.objects.get(pk=obj.category_id).enabled is enabled

    @pytest.mark.parametrize("enabled", [True, False])
    def test_an_item(self, enabled: bool) -> None:
        item_admin = ItemModelAdmin(ItemModel, admin.site)
        obj = ItemModel(name="Kind of Blue", external_id=None, slug="", metadata={}, enabled=enabled)
        item_admin.save_model(_request(), obj, MagicMock(), False)

        assert ItemModel.objects.get(pk=obj.item_id).enabled is enabled


class TestTheFormRefusesTheReservedName:
    """The category form refuses the root's reserved name, so the page never reports a save.

    Refused only by the service, the name reached the page twice: the refusal as a message, and
    beside it Django's own "was added successfully", with an addition logged for a row that was
    never stored. Refused by the form, the page is shown again with the error under the field, as
    it is for an external id already taken.
    """

    def test_on_the_add_form(self) -> None:
        form_class = CategoryModelAdmin(CategoryModel, admin.site).get_form(_request())
        form = form_class(data=_category_form_data(ROOT_CATEGORY_NAME))

        assert not form.is_valid()
        assert form.errors["name"] == [f"Category name '{ROOT_CATEGORY_NAME}' is reserved for the implicit root."]

    def test_on_the_change_form(self) -> None:
        row = CategoryModel.objects.create(name="Renamable", description="", slug="", metadata={})
        form_class = CategoryModelAdmin(CategoryModel, admin.site).get_form(_request(), row)
        form = form_class(data=_category_form_data(ROOT_CATEGORY_NAME), instance=row)

        assert not form.is_valid()
        assert "name" in form.errors

    def test_an_ordinary_name_is_accepted(self) -> None:
        form_class = CategoryModelAdmin(CategoryModel, admin.site).get_form(_request())

        assert form_class(data=_category_form_data("Jazz")).is_valid()

    def test_the_add_view_reports_no_save(self, admin_client: Client) -> None:
        """Through the real add view: nothing stored, nothing logged, no success reported."""
        url = reverse(CATEGORY_ADD_URL_NAME)
        stored_before = CategoryModel.objects.count()
        posted = _with_empty_inlines(admin_client, url, _category_form_data(ROOT_CATEGORY_NAME))

        response = admin_client.post(url, posted)

        assert response.status_code == 200  # the form, shown again
        assert "was added successfully" not in response.content.decode()
        assert CategoryModel.objects.count() == stored_before
        assert not LogEntry.objects.exists()


class TestTheReservedNameIsReported:
    """A save that bypasses the form still reports the reserved name as a message, not a 500.

    The form refuses the name first (``TestTheFormRefusesTheReservedName``); this is the backstop
    behind it. ``TaxomeshRootCategoryError`` is a validation error, and the category save reports
    validation errors to the user, on create and on rename alike.
    """

    def test_on_create(self) -> None:
        category_admin = CategoryModelAdmin(CategoryModel, admin.site)
        obj = CategoryModel(name=ROOT_CATEGORY_NAME, description="", slug="", metadata={}, external_id=None)

        with patch.object(category_admin, "message_user") as message_user:
            category_admin.save_model(_request(), obj, MagicMock(), False)

        message_user.assert_called_once()
        assert message_user.call_args.kwargs["level"] == messages.ERROR

    def test_on_rename(self) -> None:
        category_admin = CategoryModelAdmin(CategoryModel, admin.site)
        obj = CategoryModel(name="Renamable", description="", slug="", metadata={}, external_id=None)
        category_admin.save_model(_request(), obj, MagicMock(), False)

        row = CategoryModel.objects.get(pk=obj.category_id)
        row.name = ROOT_CATEGORY_NAME
        with patch.object(category_admin, "message_user") as message_user:
            category_admin.save_model(_request(), row, MagicMock(), True)

        message_user.assert_called_once()
        assert message_user.call_args.kwargs["level"] == messages.ERROR
        assert CategoryModel.objects.get(pk=obj.category_id).name == "Renamable"


class TestAChangePageSavesAsRendered:
    """A category's change page saves when it is posted as the browser renders it.

    For a category at the top level — where ``create`` puts every category — the parent-link inline
    listed its link to the implicit root, and that row's parent select, whose choices leave the root
    out, rendered no option at all. The browser sent no parent for the row, so every save failed
    with "This field is required." and no edit on the page could be stored; deleting the row, the
    only way through, took the category off the top level.
    """

    def test_an_edit_is_stored(self, admin_client: Client) -> None:
        jazz = _service().categories.create("Jazz")
        url = _category_change_url(jazz.category_id)
        posted = _as_rendered(admin_client, url)
        posted["description"] = "Improvised."
        del posted["enabled"]  # the box, unchecked

        response = admin_client.post(url, posted)

        assert response.status_code == 302
        stored = CategoryModel.objects.get(pk=jazz.category_id)
        assert (stored.description, stored.enabled) == ("Improvised.", False)

    def test_the_link_to_the_top_level_is_kept(self, admin_client: Client) -> None:
        jazz = _service().categories.create("Jazz")
        url = _category_change_url(jazz.category_id)

        response = admin_client.post(url, _as_rendered(admin_client, url))

        assert response.status_code == 302
        assert _parent_names(jazz.category_id) == {ROOT_CATEGORY_NAME}

    def test_an_explicit_parent_is_listed_and_kept(self, admin_client: Client) -> None:
        svc = _service()
        music = svc.categories.create("Music")
        jazz = svc.categories.create("Jazz")
        svc.categories.add_parent(jazz.category_id, music.category_id)
        url = _category_change_url(jazz.category_id)
        posted = _as_rendered(admin_client, url)

        assert str(music.category_id) in posted.values()  # the row names its parent
        response = admin_client.post(url, posted)

        assert response.status_code == 302
        assert _parent_names(jazz.category_id) == {"Music"}


class TestTheTopLevel:
    """The category page shows whether a category is at the top level, and its parents decide it.

    A category is at the top level exactly when it has no parent, so the page offers no control of
    its own for it: the flag is read-only, and adding or removing a parent through either inline
    goes through the service, which moves the category off the top level or back onto it.
    """

    @staticmethod
    def _top_level_flag(page: str) -> str:
        """The part of the page that renders the read-only flag."""
        start = page.index("field-at_top_level")
        return page[start : page.index("field-", start + len("field-at_top_level"))]

    def test_the_flag_is_shown_read_only(self, admin_client: Client) -> None:
        svc = _service()
        music = svc.categories.create("Music")
        jazz = svc.categories.create("Jazz")
        svc.categories.add_parent(jazz.category_id, music.category_id)

        at_top = admin_client.get(_category_change_url(music.category_id)).content.decode()
        below = admin_client.get(_category_change_url(jazz.category_id)).content.decode()

        assert "At the top level" in at_top
        assert "icon-yes" in self._top_level_flag(at_top)
        assert "icon-no" in self._top_level_flag(below)
        assert f'name="{TOP_LEVEL_BOX}"' not in at_top
        assert TOP_LEVEL_BOX not in _as_rendered(admin_client, _category_change_url(music.category_id))

    def test_a_posted_flag_changes_nothing(self, admin_client: Client) -> None:
        svc = _service()
        music = svc.categories.create("Music")
        jazz = svc.categories.create("Jazz")
        svc.categories.add_parent(jazz.category_id, music.category_id)
        url = _category_change_url(jazz.category_id)
        posted = _as_rendered(admin_client, url)
        posted[TOP_LEVEL_BOX] = "on"

        response = admin_client.post(url, posted)

        assert response.status_code == 302
        assert _parent_names(jazz.category_id) == {"Music"}

    def test_a_parent_added_in_the_inline_takes_it_off_the_top_level(self, admin_client: Client) -> None:
        svc = _service()
        music = svc.categories.create("Music")
        jazz = svc.categories.create("Jazz")
        url = _category_change_url(jazz.category_id)
        posted = _as_rendered(admin_client, url)
        posted.update(
            {
                "parent_links-TOTAL_FORMS": "1",
                "parent_links-0-category": str(jazz.category_id),
                "parent_links-0-parent_category": str(music.category_id),
                "parent_links-0-sort_index": "2",
            }
        )

        response = admin_client.post(url, posted)

        assert response.status_code == 302
        assert _parent_names(jazz.category_id) == {"Music"}

    def test_its_last_parent_deleted_in_the_inline_puts_it_back(self, admin_client: Client) -> None:
        svc = _service()
        music = svc.categories.create("Music")
        jazz = svc.categories.create("Jazz")
        svc.categories.add_parent(jazz.category_id, music.category_id)
        url = _category_change_url(jazz.category_id)
        posted = _as_rendered(admin_client, url)
        posted["parent_links-0-DELETE"] = "on"

        response = admin_client.post(url, posted)

        assert response.status_code == 302
        assert _parent_names(jazz.category_id) == {ROOT_CATEGORY_NAME}

    def test_a_parent_changed_in_the_inline_replaces_the_old_one(self, admin_client: Client) -> None:
        svc = _service()
        music = svc.categories.create("Music")
        dance = svc.categories.create("Dance")
        jazz = svc.categories.create("Jazz")
        svc.categories.add_parent(jazz.category_id, music.category_id)
        url = _category_change_url(jazz.category_id)
        posted = _as_rendered(admin_client, url)
        posted["parent_links-0-parent_category"] = str(dance.category_id)

        response = admin_client.post(url, posted)

        assert response.status_code == 302
        assert _parent_names(jazz.category_id) == {"Dance"}

    def test_a_child_added_in_the_inline_leaves_the_top_level(self, admin_client: Client) -> None:
        svc = _service()
        music = svc.categories.create("Music")
        jazz = svc.categories.create("Jazz")
        url = _category_change_url(music.category_id)
        posted = _as_rendered(admin_client, url)
        posted.update(
            {
                "child_links-TOTAL_FORMS": "1",
                "child_links-0-parent_category": str(music.category_id),
                "child_links-0-category": str(jazz.category_id),
                "child_links-0-sort_index": "0",
            }
        )

        response = admin_client.post(url, posted)

        assert response.status_code == 302
        assert _parent_names(jazz.category_id) == {"Music"}

    def test_a_child_deleted_in_the_inline_returns_to_the_top_level(self, admin_client: Client) -> None:
        svc = _service()
        music = svc.categories.create("Music")
        jazz = svc.categories.create("Jazz")
        svc.categories.add_parent(jazz.category_id, music.category_id)
        url = _category_change_url(music.category_id)
        posted = _as_rendered(admin_client, url)
        posted["child_links-0-DELETE"] = "on"

        response = admin_client.post(url, posted)

        assert response.status_code == 302
        assert _parent_names(jazz.category_id) == {ROOT_CATEGORY_NAME}

    def test_an_add_with_no_parent_is_at_the_top_level(self, admin_client: Client) -> None:
        url = reverse(CATEGORY_ADD_URL_NAME)

        response = admin_client.post(url, _with_empty_inlines(admin_client, url, _category_form_data("Jazz")))

        assert response.status_code == 302
        assert _parent_names(CategoryModel.objects.get(name="Jazz").category_id) == {ROOT_CATEGORY_NAME}

    def test_an_add_with_a_parent_is_not_at_the_top_level(self, admin_client: Client) -> None:
        music = _service().categories.create("Music")
        url = reverse(CATEGORY_ADD_URL_NAME)
        posted = _with_empty_inlines(admin_client, url, _category_form_data("Jazz"))
        posted.update(
            {
                "parent_links-TOTAL_FORMS": "1",
                "parent_links-0-parent_category": str(music.category_id),
                "parent_links-0-sort_index": "0",
            }
        )

        response = admin_client.post(url, posted)

        assert response.status_code == 302
        assert _parent_names(CategoryModel.objects.get(name="Jazz").category_id) == {"Music"}


class TestEachInlineRowIsSavedOnItsOwn:
    """A row the service refuses leaves the submission's other rows saved, and its own old link.

    Each row's form checks for a cycle against the stored links only, so two rows can pass their
    forms and still make a cycle together. Here Jazz gains Music as a parent, and an edited child row
    puts Music under Jazz: the service refuses that row, reports it, and leaves Bop, whose link the
    row held, under Jazz; the row after it, Swing under Jazz, is still saved.
    """

    def test_a_refused_row_leaves_the_others_and_its_old_link(self, admin_client: Client) -> None:
        svc = _service()
        music = svc.categories.create("Music")
        jazz = svc.categories.create("Jazz")
        bop = svc.categories.create("Bop")
        swing = svc.categories.create("Swing")
        svc.categories.add_parent(bop, jazz)
        url = _category_change_url(jazz.category_id)
        posted = _as_rendered(admin_client, url)
        posted.update(
            {
                "parent_links-TOTAL_FORMS": "1",
                "parent_links-0-category": str(jazz.category_id),
                "parent_links-0-parent_category": str(music.category_id),
                "parent_links-0-sort_index": "0",
                "child_links-TOTAL_FORMS": "2",
                "child_links-0-category": str(music.category_id),
                "child_links-1-parent_category": str(jazz.category_id),
                "child_links-1-category": str(swing.category_id),
                "child_links-1-sort_index": "0",
            }
        )

        response = admin_client.post(url, posted)

        assert response.status_code == 302
        assert _parent_names(jazz.category_id) == {"Music"}
        assert _parent_names(music.category_id) == {ROOT_CATEGORY_NAME}
        assert _parent_names(bop.category_id) == {"Jazz"}
        assert _parent_names(swing.category_id) == {"Jazz"}
        reported = [
            message for message in messages.get_messages(response.wsgi_request) if message.level == messages.ERROR
        ]
        assert len(reported) == 1


class TestATagWithoutMetadataIsSaved:
    """A tag holding no metadata saves in the admin.

    ``TagModel.metadata`` is declared without ``blank=True``, so the form Django builds from it
    would require the field and refuse ``{}``, the metadata of every tag created without any: such
    a tag could be neither added nor saved there, whatever else the page changed.

    A plain optional field would read an emptied box as ``None``, which ``tags.update`` takes as
    "leave it", so the page would report the edit saved while the stored metadata stayed. The form
    reads it as ``{}``, as the category and item forms do, and the add page opens with ``{}``
    rather than ``null``.
    """

    def test_a_rename_is_stored(self, admin_client: Client) -> None:
        mood = _service().tags.create("Mood")
        url = reverse(TAG_CHANGE_URL_NAME, args=[mood.tag_id])
        posted = _as_rendered(admin_client, url)
        posted["name"] = "Moods"

        response = admin_client.post(url, posted)

        assert response.status_code == 302
        stored = TagModel.objects.get(pk=mood.tag_id)
        assert (stored.name, stored.metadata) == ("Moods", {})

    def test_an_add_is_stored(self, admin_client: Client) -> None:
        url = reverse(TAG_ADD_URL_NAME)
        posted = _as_rendered(admin_client, url)
        posted["name"] = "Mood"
        # The form asks for an identifier, and the save stores the one the service assigns.
        posted["tag_id"] = str(uuid4())

        response = admin_client.post(url, posted)

        assert response.status_code == 302
        assert TagModel.objects.get(name="Mood").metadata == {}

    def test_an_emptied_box_stores_no_metadata(self, admin_client: Client) -> None:
        mood = _service().tags.create("Mood", metadata={"source": "import"})
        url = reverse(TAG_CHANGE_URL_NAME, args=[mood.tag_id])
        posted = _as_rendered(admin_client, url)
        posted["metadata"] = ""

        response = admin_client.post(url, posted)

        assert response.status_code == 302
        assert TagModel.objects.get(pk=mood.tag_id).metadata == {}

    def test_the_add_page_opens_the_box_empty(self, admin_client: Client) -> None:
        assert _as_rendered(admin_client, reverse(TAG_ADD_URL_NAME))["metadata"] == "{}"
