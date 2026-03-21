"""Admin registration smoke tests for taxomesh Django models."""

from unittest.mock import MagicMock

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

from django.contrib import admin  # noqa: E402

from taxomesh.contrib.django.models import (  # noqa: E402
    CategoryModel,
    ItemModel,
    ItemParentLinkModel,
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


def test_category_model_str_shows_name_and_uuid() -> None:
    """CategoryModel.__str__ without slug returns '📂 Name (id: <category_id>)'."""
    cat = CategoryModel(name="Electronics")
    assert str(cat) == f"📂 Electronics (id: {cat.category_id})"


def test_category_model_str_with_slug_shows_name_slug_and_uuid() -> None:
    """CategoryModel.__str__ with slug returns '📂 Name (s: <slug> - id: <category_id>)'."""
    cat = CategoryModel(name="Electronics", slug="electronics")
    assert str(cat) == f"📂 Electronics (s: electronics - id: {cat.category_id})"


def test_item_model_str_shows_icon_name_and_uuid() -> None:
    """ItemModel.__str__ without slug returns '🏷️ Name (id: <item_id>)'."""
    item = ItemModel(name="My Item", external_id="some-ext")
    s = str(item)
    assert s.startswith("🏷️")
    assert "My Item" in s
    assert str(item.item_id) in s


def test_item_model_str_with_slug_shows_icon_name_slug_and_uuid() -> None:
    """ItemModel.__str__ with slug returns '🏷️ Name (s: <slug> - id: <item_id>)'."""
    item = ItemModel(name="My Track", external_id="track-1", slug="my-track")
    s = str(item)
    assert s.startswith("🏷️")
    assert "My Track" in s
    assert "s: my-track" in s
    assert str(item.item_id) in s


@pytest.mark.django_db
def test_item_parent_link_model_str_shows_item_and_category() -> None:
    """ItemParentLinkModel.__str__ delegates to Item.__str__ and appends category name."""
    cat = CategoryModel.objects.create(name="Music")
    item = ItemModel.objects.create(name="track-1", external_id="track-1")
    link = ItemParentLinkModel.objects.create(item=item, category=cat)
    s = str(link)
    assert str(item.item_id) in s
    assert "track-1" in s
    assert "Music" in s


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
            "taxomesh.adapters.repositories.django_repository.DjangoRepository.list_category_parent_links",
            side_effect=TaxomeshError("db error"),
        ):
            response = admin_client.get(url)  # type: ignore[attr-defined]
        assert response.status_code == 200
        assert b"db error" in response.content

    def test_graph_view_renders_anchor_links(self, admin_client: object) -> None:
        """Each entry label in the graph view must be wrapped in an <a> tag (SC-002)."""
        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.create_category(name="LinkTestCat")
        item = svc.create_item(name="LinkTestItem")
        svc.place_item_in_category(item.item_id, cat.category_id)
        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)  # type: ignore[attr-defined]
        assert b"<a href=" in response.content


class TestFlattenGraph:
    """Unit tests for the _build_child_entries helper (replaces _flatten_graph)."""

    def test_entry_schema_has_no_legacy_keys(self) -> None:
        """_build_child_entries entries must not contain slug or indent_em keys.

        Note: external_id is now an intentional GraphEntry field (024-graph-enhancements).
        """
        from uuid import uuid4  # noqa: PLC0415

        from taxomesh.contrib.django.admin import _build_child_entries  # noqa: PLC0415
        from taxomesh.domain.models import Category, Item  # noqa: PLC0415

        parent_uuid = uuid4()
        cat = Category(name="TestCat", slug="test-cat", external_id="ext-1")
        item = Item(name="TestItem", slug="test-item", external_id="EXT-1")
        entries, _ = _build_child_entries(
            child_cats=[cat],
            items=[item],
            depth=1,
            parent_uuid_str=str(parent_uuid),
            cats_with_children=set(),
            cats_with_items=set(),
            cat_sort_map={},
            item_sort_map={},
        )
        forbidden_keys = {"slug", "indent_em"}
        for entry in entries:
            assert not forbidden_keys & entry.keys(), f"Unexpected keys in entry: {entry.keys()}"

    def test_entry_name_equals_str_of_domain_object(self) -> None:
        """_build_child_entries entry 'name' must equal str(category) or str(item)."""
        from uuid import uuid4  # noqa: PLC0415

        from taxomesh.contrib.django.admin import _build_child_entries  # noqa: PLC0415
        from taxomesh.domain.models import Category, Item  # noqa: PLC0415

        parent_uuid = uuid4()
        cat = Category(name="Rock", slug="rock", external_id="genre-rock")
        item = Item(name="Song", external_id="EXT-2")
        entries, _ = _build_child_entries(
            child_cats=[cat],
            items=[item],
            depth=1,
            parent_uuid_str=str(parent_uuid),
            cats_with_children=set(),
            cats_with_items=set(),
            cat_sort_map={},
            item_sort_map={},
        )
        cat_entry = next(e for e in entries if e["kind"] == "category")
        item_entry = next(e for e in entries if e["kind"] == "item")
        assert cat_entry["name"] == str(cat)
        assert item_entry["name"] == str(item)


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


# ---------------------------------------------------------------------------
# Root category hidden from list view and dropdowns
# ---------------------------------------------------------------------------


class TestRootCategoryHidden:
    """Root category must not appear in CategoryModelAdmin list view or FK dropdowns."""

    def test_get_queryset_excludes_root(self) -> None:
        """CategoryModelAdmin.get_queryset() must not return the root category."""
        from django.contrib.admin.sites import AdminSite  # noqa: PLC0415
        from django.http import HttpRequest  # noqa: PLC0415

        from taxomesh.contrib.django.admin import CategoryModelAdmin  # noqa: PLC0415
        from taxomesh.contrib.django.models import CategoryModel  # noqa: PLC0415
        from taxomesh.domain.constants import ROOT_CATEGORY_NAME  # noqa: PLC0415

        CategoryModel.objects.create(name=ROOT_CATEGORY_NAME)
        CategoryModel.objects.create(name="Electronics")

        site = AdminSite()
        admin_obj = CategoryModelAdmin(CategoryModel, site)
        request = MagicMock(spec=HttpRequest)
        qs = admin_obj.get_queryset(request)

        names = list(qs.values_list("name", flat=True))
        assert ROOT_CATEGORY_NAME not in names
        assert "Electronics" in names

    def test_parent_category_dropdown_excludes_root(self) -> None:
        """CategoryParentLinkInline FK dropdown for parent_category must exclude root."""
        from django.contrib.admin.sites import AdminSite  # noqa: PLC0415
        from django.http import HttpRequest  # noqa: PLC0415

        from taxomesh.contrib.django.admin import CategoryParentLinkInline  # noqa: PLC0415
        from taxomesh.contrib.django.models import CategoryModel, CategoryParentLinkModel  # noqa: PLC0415
        from taxomesh.domain.constants import ROOT_CATEGORY_NAME  # noqa: PLC0415

        CategoryModel.objects.create(name=ROOT_CATEGORY_NAME)
        CategoryModel.objects.create(name="Electronics")

        site = AdminSite()
        inline = CategoryParentLinkInline(CategoryModel, site)
        request = MagicMock(spec=HttpRequest)

        db_field = CategoryParentLinkModel._meta.get_field("parent_category")
        form_field = inline.formfield_for_foreignkey(db_field, request)  # type: ignore[arg-type]

        names = list(form_field.queryset.values_list("name", flat=True))  # type: ignore[union-attr]
        assert ROOT_CATEGORY_NAME not in names
        assert "Electronics" in names


# ---------------------------------------------------------------------------
# Slug field visibility and filter
# ---------------------------------------------------------------------------


class TestSlugAdminConfig:
    """Verify slug is exposed in admin fields, search_fields, and list_filter."""

    def test_category_admin_fields_includes_slug(self) -> None:
        from django.contrib.admin.sites import AdminSite  # noqa: PLC0415

        from taxomesh.contrib.django.admin import CategoryModelAdmin  # noqa: PLC0415

        admin_obj = CategoryModelAdmin(CategoryModel, AdminSite())
        assert "slug" in admin_obj.fields

    def test_category_admin_search_fields_includes_slug(self) -> None:
        from django.contrib.admin.sites import AdminSite  # noqa: PLC0415

        from taxomesh.contrib.django.admin import CategoryModelAdmin  # noqa: PLC0415

        admin_obj = CategoryModelAdmin(CategoryModel, AdminSite())
        assert "slug" in admin_obj.search_fields

    def test_category_admin_list_filter_includes_has_slug_filter(self) -> None:
        from django.contrib.admin.sites import AdminSite  # noqa: PLC0415

        from taxomesh.contrib.django.admin import CategoryModelAdmin, HasSlugFilter  # noqa: PLC0415

        admin_obj = CategoryModelAdmin(CategoryModel, AdminSite())
        assert HasSlugFilter in admin_obj.list_filter

    def test_item_admin_fields_includes_slug(self) -> None:
        from django.contrib.admin.sites import AdminSite  # noqa: PLC0415

        from taxomesh.contrib.django.admin import ItemModelAdmin  # noqa: PLC0415

        admin_obj = ItemModelAdmin(ItemModel, AdminSite())
        assert "slug" in admin_obj.fields

    def test_item_admin_search_fields_includes_slug(self) -> None:
        from django.contrib.admin.sites import AdminSite  # noqa: PLC0415

        from taxomesh.contrib.django.admin import ItemModelAdmin  # noqa: PLC0415

        admin_obj = ItemModelAdmin(ItemModel, AdminSite())
        assert "slug" in admin_obj.search_fields

    def test_item_admin_list_filter_includes_has_slug_filter(self) -> None:
        from django.contrib.admin.sites import AdminSite  # noqa: PLC0415

        from taxomesh.contrib.django.admin import HasSlugFilter, ItemModelAdmin  # noqa: PLC0415

        admin_obj = ItemModelAdmin(ItemModel, AdminSite())
        assert HasSlugFilter in admin_obj.list_filter

    @pytest.mark.django_db
    def test_has_slug_filter_yes_returns_only_slugged(self) -> None:
        from unittest.mock import MagicMock  # noqa: PLC0415

        from django.http import HttpRequest, QueryDict  # noqa: PLC0415

        from taxomesh.contrib.django.admin import HasSlugFilter  # noqa: PLC0415

        CategoryModel.objects.create(name="With Slug", slug="w")
        CategoryModel.objects.create(name="No Slug", slug="")

        f = HasSlugFilter(MagicMock(spec=HttpRequest), QueryDict("has_slug=yes").copy(), CategoryModel, None)
        qs = f.queryset(MagicMock(spec=HttpRequest), CategoryModel.objects.all())
        names = list(qs.values_list("name", flat=True))  # type: ignore[union-attr]
        assert "With Slug" in names
        assert "No Slug" not in names

    @pytest.mark.django_db
    def test_has_slug_filter_no_returns_only_unslugged(self) -> None:
        from unittest.mock import MagicMock  # noqa: PLC0415

        from django.http import HttpRequest, QueryDict  # noqa: PLC0415

        from taxomesh.contrib.django.admin import HasSlugFilter  # noqa: PLC0415

        CategoryModel.objects.create(name="With Slug", slug="w")
        CategoryModel.objects.create(name="No Slug", slug="")

        f = HasSlugFilter(MagicMock(spec=HttpRequest), QueryDict("has_slug=no").copy(), CategoryModel, None)
        qs = f.queryset(MagicMock(spec=HttpRequest), CategoryModel.objects.all())
        names = list(qs.values_list("name", flat=True))  # type: ignore[union-attr]
        assert "No Slug" in names
        assert "With Slug" not in names


# ---------------------------------------------------------------------------
# Metadata field visibility and save routing — Category
# ---------------------------------------------------------------------------


class TestCategoryMetadataAdminConfig:
    """Verify metadata is exposed in admin fields and routed through save_model."""

    def test_category_admin_fields_includes_metadata(self) -> None:
        from django.contrib.admin.sites import AdminSite  # noqa: PLC0415

        from taxomesh.contrib.django.admin import CategoryModelAdmin  # noqa: PLC0415

        admin_obj = CategoryModelAdmin(CategoryModel, AdminSite())
        assert "metadata" in admin_obj.fields

    def test_category_admin_save_model_passes_metadata_on_update(self) -> None:
        from unittest.mock import patch  # noqa: PLC0415

        from django.contrib.admin.sites import AdminSite  # noqa: PLC0415
        from django.http import HttpRequest  # noqa: PLC0415

        from taxomesh.contrib.django.admin import CategoryModelAdmin  # noqa: PLC0415

        site = AdminSite()
        admin_obj = CategoryModelAdmin(CategoryModel, site)
        request = MagicMock(spec=HttpRequest)

        mock_obj = MagicMock(spec=CategoryModel)
        mock_obj.category_id = __import__("uuid").uuid4()
        mock_obj.name = "Updated"
        mock_obj.description = "desc"
        mock_obj.slug = ""
        mock_obj.metadata = {"x": 1}

        with patch("taxomesh.contrib.django.admin.TaxomeshService") as MockSvc:
            mock_svc = MagicMock()
            MockSvc.return_value = mock_svc
            admin_obj.save_model(request, mock_obj, MagicMock(), True)
            call_kwargs = mock_svc.update_category.call_args.kwargs
            assert call_kwargs.get("metadata") == {"x": 1}

    def test_category_admin_save_model_passes_metadata_on_create(self) -> None:
        from unittest.mock import patch  # noqa: PLC0415

        from django.contrib.admin.sites import AdminSite  # noqa: PLC0415
        from django.http import HttpRequest  # noqa: PLC0415

        from taxomesh.contrib.django.admin import CategoryModelAdmin  # noqa: PLC0415

        site = AdminSite()
        admin_obj = CategoryModelAdmin(CategoryModel, site)
        request = MagicMock(spec=HttpRequest)

        mock_obj = MagicMock(spec=CategoryModel)
        mock_obj.name = "New"
        mock_obj.description = ""
        mock_obj.slug = ""
        mock_obj.metadata = {"new": True}
        mock_obj._state = MagicMock()

        with patch("taxomesh.contrib.django.admin.TaxomeshService") as MockSvc:
            mock_svc = MagicMock()
            MockSvc.return_value = mock_svc
            mock_svc.create_category.return_value = MagicMock(category_id=__import__("uuid").uuid4())
            admin_obj.save_model(request, mock_obj, MagicMock(), False)
            call_kwargs = mock_svc.create_category.call_args.kwargs
            assert call_kwargs.get("metadata") == {"new": True}


# ---------------------------------------------------------------------------
# Metadata field visibility and save routing — Item
# ---------------------------------------------------------------------------


class TestItemMetadataAdminConfig:
    """Verify metadata is exposed in admin fields and routed through save_model."""

    def test_item_admin_fields_includes_metadata(self) -> None:
        from django.contrib.admin.sites import AdminSite  # noqa: PLC0415

        from taxomesh.contrib.django.admin import ItemModelAdmin  # noqa: PLC0415

        admin_obj = ItemModelAdmin(ItemModel, AdminSite())
        assert "metadata" in admin_obj.fields

    def test_item_admin_save_model_passes_metadata_on_update(self) -> None:
        from unittest.mock import patch  # noqa: PLC0415

        from django.contrib.admin.sites import AdminSite  # noqa: PLC0415
        from django.http import HttpRequest  # noqa: PLC0415

        from taxomesh.contrib.django.admin import ItemModelAdmin  # noqa: PLC0415

        site = AdminSite()
        admin_obj = ItemModelAdmin(ItemModel, site)
        request = MagicMock(spec=HttpRequest)

        mock_obj = MagicMock(spec=ItemModel)
        mock_obj.item_id = __import__("uuid").uuid4()
        mock_obj.name = "Updated Item"
        mock_obj.external_id = "ext-1"
        mock_obj.enabled = True
        mock_obj.slug = ""
        mock_obj.metadata = {"x": 1}

        with patch("taxomesh.contrib.django.admin.TaxomeshService") as MockSvc:
            mock_svc = MagicMock()
            MockSvc.return_value = mock_svc
            admin_obj.save_model(request, mock_obj, MagicMock(), True)
            call_kwargs = mock_svc.update_item.call_args.kwargs
            assert call_kwargs.get("metadata") == {"x": 1}

    def test_item_admin_save_model_passes_metadata_on_create(self) -> None:
        from unittest.mock import patch  # noqa: PLC0415

        from django.contrib.admin.sites import AdminSite  # noqa: PLC0415
        from django.http import HttpRequest  # noqa: PLC0415

        from taxomesh.contrib.django.admin import ItemModelAdmin  # noqa: PLC0415

        site = AdminSite()
        admin_obj = ItemModelAdmin(ItemModel, site)
        request = MagicMock(spec=HttpRequest)

        mock_obj = MagicMock(spec=ItemModel)
        mock_obj.name = "New Item"
        mock_obj.external_id = "ext-new"
        mock_obj.slug = ""
        mock_obj.metadata = {"new": True}
        mock_obj._state = MagicMock()

        with patch("taxomesh.contrib.django.admin.TaxomeshService") as MockSvc:
            mock_svc = MagicMock()
            MockSvc.return_value = mock_svc
            mock_svc.create_item.return_value = MagicMock(item_id=__import__("uuid").uuid4())
            admin_obj.save_model(request, mock_obj, MagicMock(), False)
            call_kwargs = mock_svc.create_item.call_args.kwargs
            assert call_kwargs.get("metadata") == {"new": True}


class TestItemExternalIdOptional:
    """Tests that external_id is not required when creating an Item via the admin form."""

    def test_admin_create_item_blank_external_id(self) -> None:
        """ItemModel form must accept a blank external_id (the reported bug)."""
        from django.forms import ModelForm  # noqa: PLC0415

        from taxomesh.contrib.django.models import ItemModel  # noqa: PLC0415

        class _ItemForm(ModelForm):  # type: ignore[type-arg]
            class Meta:
                model = ItemModel
                fields = ["name", "external_id", "slug", "enabled", "metadata"]

        form = _ItemForm(
            data={"name": "Item Without External ID", "external_id": "", "slug": "", "enabled": True, "metadata": "{}"}
        )
        assert form.is_valid(), f"Form should be valid with blank external_id but got errors: {form.errors}"


# ---------------------------------------------------------------------------
# T007-T008 — Category linked_object_url using TAXOMESH_CATEGORY_LINKED_MODEL
# ---------------------------------------------------------------------------


class TestCategoryLinkedObjectUrl:
    """Tests for CategoryModelAdmin.linked_object_url using the category-specific setting."""

    def test_category_linked_object_url_empty_external_id(self) -> None:
        """With empty external_id, linked_object_url returns empty string regardless of settings."""
        from django.contrib import admin as dj_admin  # noqa: PLC0415

        from taxomesh.contrib.django.admin import CategoryModelAdmin  # noqa: PLC0415

        cat_admin = CategoryModelAdmin(CategoryModel, dj_admin.site)
        mock_obj = MagicMock()
        mock_obj.external_id = ""
        result = cat_admin.linked_object_url(mock_obj)
        assert result == ""

    def test_category_linked_object_url_no_setting(self, settings: object) -> None:
        """Without TAXOMESH_CATEGORY_LINKED_MODEL, linked_object_url returns empty string."""
        import django.conf  # noqa: PLC0415

        if hasattr(django.conf.settings, "TAXOMESH_CATEGORY_LINKED_MODEL"):
            delattr(django.conf.settings, "TAXOMESH_CATEGORY_LINKED_MODEL")
        from django.contrib import admin as dj_admin  # noqa: PLC0415

        from taxomesh.contrib.django.admin import CategoryModelAdmin  # noqa: PLC0415

        cat_admin = CategoryModelAdmin(CategoryModel, dj_admin.site)
        mock_obj = MagicMock()
        mock_obj.external_id = "some-ext-id"
        result = cat_admin.linked_object_url(mock_obj)
        assert result == ""


# ---------------------------------------------------------------------------
# T018-T019 — UUID search fields
# ---------------------------------------------------------------------------


class TestUUIDSearchFields:
    """Tests for UUID-based search in Category and Item admin."""

    def test_category_search_by_uuid_substring(self, admin_client: object) -> None:
        """Category admin list search by partial UUID returns matching category."""
        from django.urls import reverse  # noqa: PLC0415

        cat = CategoryModel.objects.create(name="SearchCat")
        uuid_str = str(cat.category_id)
        partial = uuid_str[:8]
        url = reverse("admin:taxomesh_contrib_django_categorymodel_changelist") + f"?q={partial}"
        response = admin_client.get(url)  # type: ignore[attr-defined]
        assert response.status_code == 200
        assert "SearchCat" in response.content.decode()

    def test_item_search_by_uuid_substring(self, admin_client: object) -> None:
        """Item admin list search by partial UUID returns matching item."""
        from django.urls import reverse  # noqa: PLC0415

        item = ItemModel.objects.create(name="SearchItem")
        uuid_str = str(item.item_id)
        partial = uuid_str[:8]
        url = reverse("admin:taxomesh_contrib_django_itemmodel_changelist") + f"?q={partial}"
        response = admin_client.get(url)  # type: ignore[attr-defined]
        assert response.status_code == 200
        assert "SearchItem" in response.content.decode()


# ---------------------------------------------------------------------------
# T022-T023 — Admin filters
# ---------------------------------------------------------------------------


class TestAdminFilters:
    """Tests for HasLinkedObjectListFilter and TaxomeshCategoryListFilter."""

    def test_has_linked_object_filter_yes(self, admin_client: object) -> None:
        """Filter 'yes' returns only categories with non-empty external_id."""
        from django.urls import reverse  # noqa: PLC0415

        CategoryModel.objects.create(name="WithExt", external_id="ext-123")
        CategoryModel.objects.create(name="WithoutExt", external_id="")
        url = reverse("admin:taxomesh_contrib_django_categorymodel_changelist") + "?has_linked_object=yes"
        response = admin_client.get(url)  # type: ignore[attr-defined]
        content = response.content.decode()
        assert response.status_code == 200
        assert "WithExt" in content
        assert "WithoutExt" not in content

    def test_has_linked_object_filter_no(self, admin_client: object) -> None:
        """Filter 'no' returns only categories with empty external_id."""
        from django.urls import reverse  # noqa: PLC0415

        CategoryModel.objects.create(name="WithExt2", external_id="ext-456")
        CategoryModel.objects.create(name="WithoutExt2", external_id="")
        url = reverse("admin:taxomesh_contrib_django_categorymodel_changelist") + "?has_linked_object=no"
        response = admin_client.get(url)  # type: ignore[attr-defined]
        content = response.content.decode()
        assert response.status_code == 200
        assert "WithoutExt2" in content
        assert "WithExt2" not in content

    def test_taxomesh_category_list_filter_in_mixin(self) -> None:
        """ItemCategoryAssignmentMixin includes TaxomeshCategoryListFilter in list_filter."""
        from taxomesh.contrib.django.admin import (  # noqa: PLC0415
            ItemCategoryAssignmentMixin,
            TaxomeshCategoryListFilter,
        )

        assert TaxomeshCategoryListFilter in ItemCategoryAssignmentMixin.list_filter


# ---------------------------------------------------------------------------
# TestAutocompleteInlines — FK inlines use autocomplete_fields
# ---------------------------------------------------------------------------


class TestAutocompleteInlines:
    """Inline FK fields must use autocomplete_fields for scalability."""

    def test_category_parent_link_inline_uses_autocomplete(self) -> None:
        from taxomesh.contrib.django.admin import CategoryParentLinkInline  # noqa: PLC0415

        assert CategoryParentLinkInline.autocomplete_fields == ["parent_category"]

    def test_item_parent_link_inline_uses_autocomplete(self) -> None:
        from taxomesh.contrib.django.admin import ItemParentLinkInline  # noqa: PLC0415

        assert ItemParentLinkInline.autocomplete_fields == ["category"]

    def test_item_tag_link_inline_uses_autocomplete(self) -> None:
        from taxomesh.contrib.django.admin import ItemTagLinkInline  # noqa: PLC0415

        assert ItemTagLinkInline.autocomplete_fields == ["tag"]

    def test_outgoing_relation_inline_uses_autocomplete(self) -> None:
        from taxomesh.contrib.django.admin import OutgoingRelationInline  # noqa: PLC0415

        assert OutgoingRelationInline.autocomplete_fields == ["target_item"]

    @pytest.mark.django_db
    def test_root_exclusion_still_applied(self) -> None:
        """formfield_for_foreignkey on CategoryParentLinkInline still excludes ROOT after autocomplete."""
        from django.contrib.admin.sites import AdminSite  # noqa: PLC0415
        from django.http import HttpRequest  # noqa: PLC0415

        from taxomesh.contrib.django.admin import CategoryParentLinkInline  # noqa: PLC0415
        from taxomesh.contrib.django.models import CategoryModel, CategoryParentLinkModel  # noqa: PLC0415
        from taxomesh.domain.constants import ROOT_CATEGORY_NAME  # noqa: PLC0415

        CategoryModel.objects.create(name=ROOT_CATEGORY_NAME)
        CategoryModel.objects.create(name="Visible")

        site = AdminSite()
        inline = CategoryParentLinkInline(CategoryModel, site)
        request = MagicMock(spec=HttpRequest)
        db_field = CategoryParentLinkModel._meta.get_field("parent_category")
        form_field = inline.formfield_for_foreignkey(db_field, request)  # type: ignore[arg-type]

        names = list(form_field.queryset.values_list("name", flat=True))  # type: ignore[union-attr]
        assert ROOT_CATEGORY_NAME not in names
        assert "Visible" in names

    def test_incoming_relation_inline_unchanged(self) -> None:
        from taxomesh.contrib.django.admin import IncomingRelationInline  # noqa: PLC0415

        assert not getattr(IncomingRelationInline, "autocomplete_fields", [])


# ---------------------------------------------------------------------------
# TestJsonEditorWidget — unit tests for the JsonEditorWidget class (T001)
# ---------------------------------------------------------------------------


class TestJsonEditorWidget:
    """Unit tests for JsonEditorWidget in taxomesh/contrib/django/widgets.py."""

    def test_render_contains_hidden_textarea(self) -> None:
        from taxomesh.contrib.django.widgets import JsonEditorWidget  # noqa: PLC0415

        widget = JsonEditorWidget()
        output = widget.render("metadata", {"key": "val"}, {"id": "id_metadata"})
        assert 'name="metadata"' in output
        assert "display:none" in output or "display: none" in output

    def test_render_contains_ace_div(self) -> None:
        from taxomesh.contrib.django.widgets import JsonEditorWidget  # noqa: PLC0415

        widget = JsonEditorWidget()
        output = widget.render("metadata", {}, {"id": "id_metadata"})
        assert 'id="ace__id_metadata"' in output

    def test_render_contains_init_script(self) -> None:
        from taxomesh.contrib.django.widgets import JsonEditorWidget  # noqa: PLC0415

        widget = JsonEditorWidget()
        output = widget.render("metadata", {}, {"id": "id_metadata"})
        assert "ace.edit(" in output
        assert "ace.config.set" in output

    def test_render_none_value_defaults_to_empty_object(self) -> None:
        from taxomesh.contrib.django.widgets import JsonEditorWidget  # noqa: PLC0415

        widget = JsonEditorWidget()
        output = widget.render("metadata", None, {"id": "id_metadata"})
        assert "{}" in output

    def test_render_dict_value_is_json_serialised(self) -> None:
        import html  # noqa: PLC0415

        from taxomesh.contrib.django.widgets import JsonEditorWidget  # noqa: PLC0415

        widget = JsonEditorWidget()
        output = widget.render("metadata", {"a": 1}, {"id": "id_metadata"})
        # format_html HTML-escapes quotes; unescape to verify JSON serialisation
        assert '"a"' in html.unescape(output)

    def test_render_unique_ids_for_different_attrs(self) -> None:
        from taxomesh.contrib.django.widgets import JsonEditorWidget  # noqa: PLC0415

        widget = JsonEditorWidget()
        out1 = widget.render("metadata", {}, {"id": "id_metadata"})
        out2 = widget.render("metadata", {}, {"id": "id_metadata2"})
        assert "ace__id_metadata2" in out2
        assert "ace__id_metadata2" not in out1

    def test_media_declares_ace_cdn_url(self) -> None:
        from taxomesh.contrib.django.widgets import ACE_EDITOR_CDN_URL, JsonEditorWidget  # noqa: PLC0415

        widget = JsonEditorWidget()
        assert ACE_EDITOR_CDN_URL in widget.media._js  # type: ignore[attr-defined]

    def test_value_from_datadict_reads_textarea_name(self) -> None:
        from taxomesh.contrib.django.widgets import JsonEditorWidget  # noqa: PLC0415

        widget = JsonEditorWidget()
        result = widget.value_from_datadict({"metadata": '{"x":1}'}, {}, "metadata")
        assert result == '{"x":1}'


# ---------------------------------------------------------------------------
# TestJsonEditorAdminIntegration — admin change pages render Ace editor (T004)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestJsonEditorAdminIntegration:
    """Integration tests: Category and Item change pages must render the Ace editor."""

    def test_category_change_page_renders_ace_editor(self, admin_client: object) -> None:
        from django.urls import reverse  # noqa: PLC0415

        from taxomesh.contrib.django.models import CategoryModel  # noqa: PLC0415

        category = CategoryModel.objects.create(name="Test Category", metadata={"k": "v"})
        url = reverse("admin:taxomesh_contrib_django_categorymodel_change", args=[category.pk])
        response = admin_client.get(url)  # type: ignore[attr-defined]
        assert response.status_code == 200
        assert b"ace.edit(" in response.content
        assert b"ace/mode/json" in response.content

    def test_item_change_page_renders_ace_editor(self, admin_client: object) -> None:
        from django.urls import reverse  # noqa: PLC0415

        from taxomesh.contrib.django.models import ItemModel  # noqa: PLC0415

        item = ItemModel.objects.create(name="Test Item", metadata={"genre": "rock"})
        url = reverse("admin:taxomesh_contrib_django_itemmodel_change", args=[item.pk])
        response = admin_client.get(url)  # type: ignore[attr-defined]
        assert response.status_code == 200
        assert b"ace.edit(" in response.content
        assert b"ace/mode/json" in response.content

    def test_category_metadata_textarea_is_hidden(self, admin_client: object) -> None:
        from django.urls import reverse  # noqa: PLC0415

        from taxomesh.contrib.django.models import CategoryModel  # noqa: PLC0415

        category = CategoryModel.objects.create(name="Another Category")
        url = reverse("admin:taxomesh_contrib_django_categorymodel_change", args=[category.pk])
        response = admin_client.get(url)  # type: ignore[attr-defined]
        assert response.status_code == 200
        assert b"display:none" in response.content


# ---------------------------------------------------------------------------
# TestJsonEditorWidgetUS2 — failing tests for US2 validation guard (T005)
# ---------------------------------------------------------------------------


class TestJsonEditorWidgetUS2:
    """Tests for US2: real-time validation worker + submit guard + blank guard."""

    def test_render_uses_worker(self) -> None:
        from taxomesh.contrib.django.widgets import JsonEditorWidget  # noqa: PLC0415

        widget = JsonEditorWidget()
        output = widget.render("metadata", {}, {"id": "id_metadata"})
        assert "useWorker" in output

    def test_render_contains_submit_guard(self) -> None:
        from taxomesh.contrib.django.widgets import JsonEditorWidget  # noqa: PLC0415

        widget = JsonEditorWidget()
        output = widget.render("metadata", {}, {"id": "id_metadata"})
        assert "getAnnotations" in output
        assert "preventDefault" in output

    def test_render_blank_guard_client_side(self) -> None:
        from taxomesh.contrib.django.widgets import JsonEditorWidget  # noqa: PLC0415

        widget = JsonEditorWidget()
        output = widget.render("metadata", {}, {"id": "id_metadata"})
        # The change listener must normalise a blank value to "{}" client-side
        assert 'textarea.value="{}"' in output or "textarea.value='{}'" in output

    def test_clean_empty_string_returns_empty_dict(self) -> None:
        from taxomesh.contrib.django.widgets import JsonEditorFormField  # noqa: PLC0415

        # metadata is blank=True in the model, so required=False in the form
        field = JsonEditorFormField(required=False)
        result = field.clean("")
        assert result == {}


class TestCategoryChildLinkInline:
    def test_category_child_link_inline_registered_on_category_admin(self) -> None:
        from django.contrib.admin.sites import AdminSite  # noqa: PLC0415

        from taxomesh.contrib.django.admin import CategoryChildLinkInline, CategoryModelAdmin  # noqa: PLC0415

        site = AdminSite()
        admin_obj = CategoryModelAdmin(CategoryModel, site)
        inline_classes = [type(inline) for inline in admin_obj.get_inline_instances(MagicMock())]
        assert CategoryChildLinkInline in inline_classes

    def test_category_child_link_inline_is_read_only(self) -> None:
        from django.contrib.admin.sites import AdminSite  # noqa: PLC0415
        from django.http import HttpRequest  # noqa: PLC0415

        from taxomesh.contrib.django.admin import CategoryChildLinkInline  # noqa: PLC0415

        site = AdminSite()
        inline = CategoryChildLinkInline(CategoryModel, site)
        request = MagicMock(spec=HttpRequest)
        assert not inline.has_add_permission(request)
        assert not inline.has_change_permission(request)
        assert not inline.has_delete_permission(request)

    def test_category_child_link_inline_shows_category_field(self) -> None:
        from django.contrib.admin.sites import AdminSite  # noqa: PLC0415

        from taxomesh.contrib.django.admin import CategoryChildLinkInline  # noqa: PLC0415

        site = AdminSite()
        inline = CategoryChildLinkInline(CategoryModel, site)
        # No custom fields override — Django renders all fields including the
        # 'category' FK, which displays CategoryModel.__str__ (the child's name).
        assert not hasattr(inline, "fields") or inline.fields is None

    def test_category_child_link_inline_queryset_reflects_parent_links(self) -> None:
        from django.contrib.admin.sites import AdminSite  # noqa: PLC0415

        from taxomesh.contrib.django.admin import CategoryChildLinkInline  # noqa: PLC0415
        from taxomesh.contrib.django.models import CategoryParentLinkModel  # noqa: PLC0415

        parent = CategoryModel.objects.create(name="Parent")
        child = CategoryModel.objects.create(name="Child")
        CategoryParentLinkModel.objects.create(category=child, parent_category=parent, sort_index=0)

        site = AdminSite()
        inline = CategoryChildLinkInline(CategoryModel, site)
        request = MagicMock()
        qs = inline.get_queryset(request).filter(parent_category=parent)

        assert qs.count() == 1
        assert qs.first().category == child
