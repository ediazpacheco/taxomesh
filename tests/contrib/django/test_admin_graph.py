"""Tests for the Django admin taxonomy graph view."""

import pathlib
import re

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

from django.test import Client  # noqa: E402
from pytest_django.fixtures import SettingsWrapper  # noqa: E402

pytestmark = pytest.mark.django_db


def test_graph_links_have_no_underline() -> None:
    """Regression: .taxomesh-label a must have text-decoration: none in graph.html."""
    template_path = (
        pathlib.Path(__file__).parent.parent.parent.parent
        / "taxomesh"
        / "contrib"
        / "django"
        / "templates"
        / "admin"
        / "taxomesh_contrib_django"
        / "graph.html"
    )
    template_source = template_path.read_text()
    assert "text-decoration: none" in template_source, (
        "Expected '.taxomesh-label a { text-decoration: none; }' in graph.html"
    )


class TestExpandCollapse:
    """Tests for expand/collapse toggle buttons in the admin graph view."""

    def test_non_empty_category_has_toggle_button(self, admin_client: Client) -> None:
        """A category that has items must render a taxomesh-toggle button."""
        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.categories.create(name="NonEmptyCat")
        item = svc.items.create(name="SomeItem")
        svc.items.place_in(item.item_id, cat.category_id)

        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)
        assert b'<button class="taxomesh-toggle"' in response.content, (
            "Expected a taxomesh-toggle button element for a category with items"
        )

    def test_empty_category_has_no_toggle_button(self, admin_client: Client) -> None:
        """A category with no items and no children must NOT have a toggle button."""
        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        svc.categories.create(name="EmptyCat")

        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)
        assert b'<button class="taxomesh-toggle"' not in response.content, (
            "Expected no taxomesh-toggle button element for an empty category"
        )

    def test_leaf_item_without_relations_has_no_toggle_button(self, admin_client: Client) -> None:
        """An item without outgoing relations must NOT have a toggle button."""
        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.categories.create(name="MyCat")
        item = svc.items.create(name="LeafItem")
        svc.items.place_in(item.item_id, cat.category_id)

        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)
        content = response.content.decode()

        # The category itself has a toggle (it has items), but the item entry must not
        # We look for toggle buttons that appear right before item entries
        # Split by data-kind="item" and check for rel-toggle buttons only in item sections
        parts = content.split('data-kind="item"')
        for part in parts[1:]:  # skip text before first item
            item_section = part[:500]
            assert "taxomesh-rel-toggle" not in item_section, (
                "Item without relations must not have a relation toggle button"
            )


class TestRelationsToggle:
    """Tests for item relations toggle in the admin graph view."""

    def _setup_taxonomy_with_relation(self) -> None:
        """Create a category with two items and an outgoing relation."""
        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.categories.create(name="Music")
        item_a = svc.items.create(name="Alpha")
        item_b = svc.items.create(name="Beta")
        svc.items.place_in(item_a.item_id, cat.category_id)
        svc.items.place_in(item_b.item_id, cat.category_id)
        svc.items.relate(item_a.item_id, item_b.item_id, "covers")

    def test_relations_toggle_checkbox_absent(self, admin_client: Client) -> None:
        """The graph page carries no global 'Show item relations' checkbox."""
        from django.urls import reverse  # noqa: PLC0415

        self._setup_taxonomy_with_relation()
        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)
        assert b'id="taxomesh-show-relations"' not in response.content, (
            "The 'Show item relations' global checkbox must be absent (per-item toggle only)"
        )

    def test_item_relations_in_context(self, admin_client: Client) -> None:
        """Relation data must appear in the children endpoint HTML fragment."""
        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.categories.create(name="MusicRel")
        item_a = svc.items.create(name="Alpha")
        item_b = svc.items.create(name="Beta")
        svc.items.place_in(item_a.item_id, cat.category_id)
        svc.items.place_in(item_b.item_id, cat.category_id)
        svc.items.relate(item_a.item_id, item_b.item_id, "covers")

        url = reverse("admin:taxomesh_contrib_django_graph_children")
        response = admin_client.get(url, {"parent_uuid": str(cat.category_id), "depth": "1"})
        content = response.content.decode()
        assert "covers" in content, "Expected relation type 'covers' to appear in children HTML fragment"
        assert "Beta" in content, "Expected target item name 'Beta' to appear in relation row"

    def test_relation_rows_hidden_by_default(self, admin_client: Client) -> None:
        """Relation rows CSS (.taxomesh-relations) must have display:none in graph.html."""
        from django.urls import reverse  # noqa: PLC0415

        self._setup_taxonomy_with_relation()
        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)
        # The CSS rule must be present in the page
        assert b".taxomesh-relations" in response.content

    def test_item_with_relations_has_toggle_button_when_relations_loaded(self, admin_client: Client) -> None:
        """An item that has outgoing relations must render a rel-toggle button in children fragment."""
        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.categories.create(name="MusicToggle")
        item_a = svc.items.create(name="AlphaToggle")
        item_b = svc.items.create(name="BetaToggle")
        svc.items.place_in(item_a.item_id, cat.category_id)
        svc.items.place_in(item_b.item_id, cat.category_id)
        svc.items.relate(item_a.item_id, item_b.item_id, "covers")

        url = reverse("admin:taxomesh_contrib_django_graph_children")
        response = admin_client.get(url, {"parent_uuid": str(cat.category_id), "depth": "1"})
        assert b"taxomesh-rel-toggle" in response.content, (
            "Expected a taxomesh-rel-toggle button for an item with outgoing relations in children fragment"
        )


class TestLinkedModel:
    """Tests for admin icon-links to configured Django model."""

    def _setup_category_with_item(self, external_id: str | None = None) -> None:
        """Create a category with one item, optionally with an external_id."""
        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.categories.create(name="TestCat")
        item = svc.items.create(name="TestItem", external_id=external_id or "")
        svc.items.place_in(item.item_id, cat.category_id)

    def test_icon_link_appears_when_model_configured_and_external_id_set(
        self, admin_client: Client, settings: SettingsWrapper
    ) -> None:
        """When TAXOMESH_LINKED_MODEL is set and item.external_id matches a pk, ↗ appears in children fragment."""
        from django.contrib.auth.models import User  # noqa: PLC0415
        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        # Create a Django User whose pk will be used as external_id
        user = User.objects.create_user(username="linked-user", password="x")
        self._setup_category_with_item(external_id=str(user.pk))

        settings.TAXOMESH_LINKED_MODEL = "auth.User"

        # Items are loaded lazily via the children endpoint, not the initial graph page
        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cats = svc.categories.roots()
        assert cats, "Expected at least one top-level category"
        cat = cats[0]

        url = reverse("admin:taxomesh_contrib_django_graph_children")
        response = admin_client.get(url, {"parent_uuid": str(cat.category_id), "depth": "1"})
        assert "&#8599;" in response.content.decode(), (
            "Expected ↗ icon-link (&#8599;) for item with matching external_id in children fragment"
        )

    def test_no_icon_when_external_id_absent(self, admin_client: Client, settings: SettingsWrapper) -> None:
        """No ↗ icon when the item has no external_id."""
        from django.urls import reverse  # noqa: PLC0415

        self._setup_category_with_item(external_id="")
        settings.TAXOMESH_LINKED_MODEL = "auth.User"

        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)
        assert "&#8599;" not in response.content.decode(), "Expected no ↗ icon when item has no external_id"

    def test_no_icon_when_setting_absent(self, admin_client: Client) -> None:
        """No ↗ icon when TAXOMESH_LINKED_MODEL is not configured."""
        from django.contrib.auth.models import User  # noqa: PLC0415
        from django.urls import reverse  # noqa: PLC0415

        user = User.objects.create_user(username="unlinked-user", password="x")
        self._setup_category_with_item(external_id=str(user.pk))

        # Do NOT set TAXOMESH_LINKED_MODEL in settings

        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)
        assert "&#8599;" not in response.content.decode(), (
            "Expected no ↗ icon when TAXOMESH_LINKED_MODEL setting is absent"
        )

    def test_no_icon_when_instance_not_found(self, admin_client: Client, settings: SettingsWrapper) -> None:
        """No ↗ icon when setting is valid but no instance with the given pk exists."""
        from django.urls import reverse  # noqa: PLC0415

        # Use a pk that doesn't exist
        self._setup_category_with_item(external_id="999999")
        settings.TAXOMESH_LINKED_MODEL = "auth.User"

        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)
        assert "&#8599;" not in response.content.decode(), (
            "Expected no ↗ icon when linked model instance does not exist"
        )


class TestDepthAndRelations:
    """Tests for admin graph depth limit and relations-always-collapsed."""

    def _setup_deep_taxonomy(self) -> None:
        """Create a 5-level taxonomy: L0 > L1 > L2 > L3 > L4, each category with one item."""
        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        l0 = svc.categories.create(name="L0admin")
        l1 = svc.categories.create(name="L1admin")
        l2 = svc.categories.create(name="L2admin")
        l3 = svc.categories.create(name="L3admin")
        l4 = svc.categories.create(name="L4admin")
        svc.categories.add_parent(l1.category_id, l0.category_id)
        svc.categories.add_parent(l2.category_id, l1.category_id)
        svc.categories.add_parent(l3.category_id, l2.category_id)
        svc.categories.add_parent(l4.category_id, l3.category_id)
        for lvl, cat in enumerate([l0, l1, l2, l3, l4]):
            item = svc.items.create(name=f"AdminItem{lvl}")
            svc.items.place_in(item.item_id, cat.category_id)

    def _setup_taxonomy_with_relation(self) -> None:
        """Create a category with two items and an outgoing relation."""
        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.categories.create(name="RelCat")
        item_a = svc.items.create(name="RelAlpha")
        item_b = svc.items.create(name="RelBeta")
        svc.items.place_in(item_a.item_id, cat.category_id)
        svc.items.place_in(item_b.item_id, cat.category_id)
        svc.items.relate(item_a.item_id, item_b.item_id, "related_to")

    def test_admin_graph_omits_nodes_beyond_default_depth(self, admin_client: Client) -> None:
        """Initial graph view shows only top-level categories; subcategories load lazily."""
        from django.urls import reverse  # noqa: PLC0415

        self._setup_deep_taxonomy()
        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)
        content = response.content.decode()
        # L0admin is the top-level category and must appear in the initial page
        assert "L0admin" in content, "L0admin (top-level) must appear in the initial graph page"
        # L1admin is a subcategory and must NOT appear in the initial page (lazy-loaded)
        assert "L1admin" not in content, "L1admin (subcategory) must not appear in initial page — lazy-loaded"
        # data-depth-limited concept is removed; no such attribute
        assert 'data-depth-limited="1"' not in content, "data-depth-limited attribute must be absent (concept removed)"

    def test_admin_graph_no_relations_toggle_checkbox(self, admin_client: Client) -> None:
        """The 'Show item relations' checkbox must not be present in admin graph HTML."""
        from django.urls import reverse  # noqa: PLC0415

        self._setup_taxonomy_with_relation()
        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)
        assert b'id="taxomesh-show-relations"' not in response.content, (
            "The 'Show item relations' checkbox must be removed from admin graph"
        )

    def test_admin_graph_item_with_relations_has_toggle_button(self, admin_client: Client) -> None:
        """Items with outgoing relations must render a rel-toggle button in the children fragment."""
        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.categories.create(name="RelCat2")
        item_a = svc.items.create(name="RelAlpha2")
        item_b = svc.items.create(name="RelBeta2")
        svc.items.place_in(item_a.item_id, cat.category_id)
        svc.items.place_in(item_b.item_id, cat.category_id)
        svc.items.relate(item_a.item_id, item_b.item_id, "related_to")

        url = reverse("admin:taxomesh_contrib_django_graph_children")
        response = admin_client.get(url, {"parent_uuid": str(cat.category_id), "depth": "1"})
        assert b"taxomesh-rel-toggle" in response.content, "Items with relations must have a rel-toggle button"

    def test_admin_graph_relation_rows_hidden_by_default(self, admin_client: Client) -> None:
        """Relation rows CSS (.taxomesh-relations) must have display:none in graph.html style block."""
        from django.urls import reverse  # noqa: PLC0415

        self._setup_taxonomy_with_relation()
        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)
        content = response.content.decode()
        # The CSS rule must be present in the page
        assert ".taxomesh-relations {" in content or ".taxomesh-relations{" in content
        assert "taxomesh-relations-visible" not in content, (
            "The .taxomesh-relations-visible CSS class and JS must be removed"
        )

    def test_admin_graph_depth_limited_category_shows_clickable_expand_button(self, admin_client: Client) -> None:
        """A top-level category with subcategories must show a [+] toggle button in the initial graph page."""
        from django.urls import reverse  # noqa: PLC0415

        self._setup_deep_taxonomy()
        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)
        content = response.content.decode()
        # L0admin is at the top level and has descendants (L1admin), so it must show a toggle button
        assert "L0admin" in content, "L0admin must be present in the initial graph"
        assert "taxomesh-depth-limited" not in content, (
            "taxomesh-depth-limited class must be absent — depth limiting concept removed"
        )
        assert 'class="taxomesh-toggle"' in content, "L0admin (which has children) must show a toggle [+] button"


class TestLinkedObjectColumn:
    """Tests for linked_object_url column in Item/Category list and detail."""

    def _setup_item_with_external_id(self, external_id: str) -> None:
        """Create an item with the given external_id in a category."""
        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.categories.create(name="IconCat")
        item = svc.items.create(name="IconItem", external_id=external_id)
        svc.items.place_in(item.item_id, cat.category_id)

    def _setup_category_with_external_id(self, external_id: str) -> None:
        """Create a category with the given external_id (set via ORM after service create)."""
        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415
        from taxomesh.contrib.django.models import CategoryModel  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.categories.create(name="IconLinkCat")
        CategoryModel.objects.filter(category_id=cat.category_id).update(external_id=external_id)

    def test_item_list_shows_linked_url_column_when_model_configured(
        self, admin_client: Client, settings: SettingsWrapper
    ) -> None:
        """Item changelist must show a ↗ icon link for items with external_id when TAXOMESH_LINKED_MODEL is set."""
        from django.contrib.auth.models import User  # noqa: PLC0415
        from django.urls import reverse  # noqa: PLC0415

        user = User.objects.create_user(username="icon-user", password="x")
        self._setup_item_with_external_id(str(user.pk))
        settings.TAXOMESH_LINKED_MODEL = "auth.User"

        url = reverse("admin:taxomesh_contrib_django_itemmodel_changelist")
        response = admin_client.get(url)
        assert "&#8599;" in response.content.decode(), (
            "Expected ↗ (&#8599;) icon-link in Item changelist when TAXOMESH_LINKED_MODEL configured"
        )

    def test_item_list_no_icon_when_external_id_absent(self, admin_client: Client, settings: SettingsWrapper) -> None:
        """No ↗ icon in Item changelist for items without external_id."""
        from django.urls import reverse  # noqa: PLC0415

        self._setup_item_with_external_id("")
        settings.TAXOMESH_LINKED_MODEL = "auth.User"

        url = reverse("admin:taxomesh_contrib_django_itemmodel_changelist")
        response = admin_client.get(url)
        assert "&#8599;" not in response.content.decode(), (
            "Expected no ↗ icon in Item changelist for items without external_id"
        )

    def test_category_list_shows_linked_url_column(self, admin_client: Client, settings: SettingsWrapper) -> None:
        """Category changelist must show a ↗ icon link for categories with external_id."""
        from django.contrib.auth.models import User  # noqa: PLC0415
        from django.urls import reverse  # noqa: PLC0415

        user = User.objects.create_user(username="cat-icon-user", password="x")
        self._setup_category_with_external_id(str(user.pk))
        settings.TAXOMESH_LINKED_MODEL = "auth.User"

        url = reverse("admin:taxomesh_contrib_django_categorymodel_changelist")
        response = admin_client.get(url)
        assert "&#8599;" in response.content.decode(), (
            "Expected ↗ (&#8599;) icon-link in Category changelist when TAXOMESH_LINKED_MODEL configured"
        )

    def test_item_detail_shows_linked_url_field(self, admin_client: Client, settings: SettingsWrapper) -> None:
        """Item change form must show ↗ link in readonly fields when external_id matches linked model."""
        from django.contrib.auth.models import User  # noqa: PLC0415
        from django.urls import reverse  # noqa: PLC0415

        user = User.objects.create_user(username="detail-icon-user", password="x")
        self._setup_item_with_external_id(str(user.pk))
        settings.TAXOMESH_LINKED_MODEL = "auth.User"

        # Get the item's UUID
        from taxomesh.contrib.django.models import ItemModel  # noqa: PLC0415

        item_obj = ItemModel.objects.get(external_id=str(user.pk))

        url = reverse("admin:taxomesh_contrib_django_itemmodel_change", args=[item_obj.item_id])
        response = admin_client.get(url)
        assert "&#8599;" in response.content.decode(), "Expected ↗ icon-link in Item change form readonly fields"


class TestVersionWidget:
    """Tests for the taxomesh version widget in the admin app_index."""

    def test_app_index_shows_taxomesh_version(self, admin_client: Client) -> None:
        """The app_index page must show the installed taxomesh version."""
        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import __version__  # noqa: PLC0415

        url = reverse("admin:app_list", kwargs={"app_label": "taxomesh_contrib_django"})
        response = admin_client.get(url)
        content = response.content.decode()
        assert f"taxomesh {__version__}" in content, (
            f"Expected 'taxomesh {__version__}' (the installed version) in app_index HTML"
        )
        assert "View the taxonomy as a tree" in content

    def test_app_index_shows_backend_info(self, admin_client: Client) -> None:
        """The app_index page must show backend/config info."""
        from django.urls import reverse  # noqa: PLC0415

        url = reverse("admin:app_list", kwargs={"app_label": "taxomesh_contrib_django"})
        response = admin_client.get(url)
        content = response.content.decode()
        # Either a path to taxomesh.toml or the default Django ORM backend string
        assert "Django ORM backend" in content or "taxomesh.toml" in content, (
            "Expected backend info ('Django ORM backend' or taxomesh.toml path) in app_index HTML"
        )


class TestItemRelationLinkNotRegistered:
    """Tests that ItemRelationLinkModel is NOT registered in the Django admin."""

    def test_item_relation_link_not_in_admin_registry(self) -> None:
        """ItemRelationLinkModel is not in admin.site._registry."""
        from django.contrib import admin  # noqa: PLC0415

        from taxomesh.contrib.django.models import ItemRelationLinkModel  # noqa: PLC0415

        assert ItemRelationLinkModel not in admin.site._registry, (
            "ItemRelationLinkModelAdmin must be removed from admin registry"
        )


class TestReorderView:
    """Tests for the graph reorder endpoint POST graph/reorder/ (drag-and-drop ordering)."""

    def test_reorder_items_returns_200(self, admin_client: Client) -> None:
        """Valid POST with kind=item, existing parent_uuid, and ordered_uuids returns 200 {ok: true}."""
        import json  # noqa: PLC0415

        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.categories.create(name="Cat")
        item_a = svc.items.create(name="A")
        item_b = svc.items.create(name="B")
        item_c = svc.items.create(name="C")
        svc.items.place_in(item_a.item_id, cat.category_id, sort_index=0)
        svc.items.place_in(item_b.item_id, cat.category_id, sort_index=1)
        svc.items.place_in(item_c.item_id, cat.category_id, sort_index=2)

        url = reverse("admin:taxomesh_contrib_django_graph_reorder")
        payload = {
            "kind": "item",
            "parent_uuid": str(cat.category_id),
            "ordered_uuids": [str(item_c.item_id), str(item_a.item_id), str(item_b.item_id)],
        }
        response = admin_client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data == {"ok": True}

    def test_reorder_missing_kind_returns_400(self, admin_client: Client) -> None:
        """POST without 'kind' field returns 400 with an error key."""
        import json  # noqa: PLC0415

        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.categories.create(name="CatMissingKind")
        item_a = svc.items.create(name="MKA")
        svc.items.place_in(item_a.item_id, cat.category_id, sort_index=0)

        url = reverse("admin:taxomesh_contrib_django_graph_reorder")
        payload = {
            "parent_uuid": str(cat.category_id),
            "ordered_uuids": [str(item_a.item_id)],
        }
        response = admin_client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data

    def test_reorder_missing_parent_uuid_returns_400(self, admin_client: Client) -> None:
        """POST without 'parent_uuid' field returns 400 with an error key."""
        import json  # noqa: PLC0415

        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        item_a = svc.items.create(name="MPA")

        url = reverse("admin:taxomesh_contrib_django_graph_reorder")
        payload = {
            "kind": "item",
            "ordered_uuids": [str(item_a.item_id)],
        }
        response = admin_client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data

    def test_reorder_unknown_parent_uuid_returns_400(self, admin_client: Client) -> None:
        """POST with a well-formed but non-existent parent_uuid returns 400."""
        import json  # noqa: PLC0415
        import uuid  # noqa: PLC0415

        from django.urls import reverse  # noqa: PLC0415

        url = reverse("admin:taxomesh_contrib_django_graph_reorder")
        payload = {
            "kind": "item",
            "parent_uuid": str(uuid.uuid4()),
            "ordered_uuids": [str(uuid.uuid4())],
        }
        response = admin_client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_reorder_get_returns_405(self, admin_client: Client) -> None:
        """GET to the reorder endpoint returns 405 Method Not Allowed."""
        from django.urls import reverse  # noqa: PLC0415

        url = reverse("admin:taxomesh_contrib_django_graph_reorder")
        response = admin_client.get(url)
        assert response.status_code == 405


class TestReorderViewCategory:
    """Tests for the graph reorder endpoint with kind="category" (drag-and-drop category ordering)."""

    def test_reorder_categories_returns_200(self, admin_client: Client) -> None:
        """Valid POST with kind=category, existing parent_uuid, and ordered_uuids returns 200 {ok: true}."""
        import json  # noqa: PLC0415

        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        parent = svc.categories.create(name="Parent")
        child_a = svc.categories.create(name="ChildA")
        child_b = svc.categories.create(name="ChildB")
        child_c = svc.categories.create(name="ChildC")
        svc.categories.add_parent(child_a.category_id, parent.category_id, sort_index=0)
        svc.categories.add_parent(child_b.category_id, parent.category_id, sort_index=1)
        svc.categories.add_parent(child_c.category_id, parent.category_id, sort_index=2)

        url = reverse("admin:taxomesh_contrib_django_graph_reorder")
        payload = {
            "kind": "category",
            "parent_uuid": str(parent.category_id),
            "ordered_uuids": [
                str(child_c.category_id),
                str(child_a.category_id),
                str(child_b.category_id),
            ],
        }
        response = admin_client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data == {"ok": True}

    def test_reorder_categories_unknown_parent_returns_400(self, admin_client: Client) -> None:
        """POST with kind=category and a well-formed but non-existent parent_uuid returns 400."""
        import json  # noqa: PLC0415
        import uuid  # noqa: PLC0415

        from django.urls import reverse  # noqa: PLC0415

        url = reverse("admin:taxomesh_contrib_django_graph_reorder")
        payload = {
            "kind": "category",
            "parent_uuid": str(uuid.uuid4()),
            "ordered_uuids": [str(uuid.uuid4()), str(uuid.uuid4())],
        }
        response = admin_client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_reorder_invalid_kind_returns_400(self, admin_client: Client) -> None:
        """POST with an unrecognised kind value returns 400 with an error key."""
        import json  # noqa: PLC0415
        import uuid  # noqa: PLC0415

        from django.urls import reverse  # noqa: PLC0415

        url = reverse("admin:taxomesh_contrib_django_graph_reorder")
        payload = {
            "kind": "widget",
            "parent_uuid": str(uuid.uuid4()),
            "ordered_uuids": [],
        }
        response = admin_client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data


class TestReparentView:
    """Tests for the graph reparent endpoint POST graph/reparent/ (drag-and-drop reparenting)."""

    def test_reparent_item_returns_200(self, admin_client: Client) -> None:
        """Valid POST with kind=item, existing node/parent UUIDs returns 200 {ok: true}."""
        import json  # noqa: PLC0415

        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat_a = svc.categories.create(name="A")
        cat_b = svc.categories.create(name="B")
        item_x = svc.items.create(name="X")
        svc.items.place_in(item_x.item_id, cat_a.category_id)

        url = reverse("admin:taxomesh_contrib_django_graph_reparent")
        payload = {
            "kind": "item",
            "node_uuid": str(item_x.item_id),
            "old_parent_uuid": str(cat_a.category_id),
            "new_parent_uuid": str(cat_b.category_id),
            "insert_before_uuid": None,
        }
        response = admin_client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data == {"ok": True}

    def test_reparent_missing_field_returns_400(self, admin_client: Client) -> None:
        """POST missing the node_uuid field returns 400 with an error key."""
        import json  # noqa: PLC0415

        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat_a = svc.categories.create(name="MissingFieldA")
        cat_b = svc.categories.create(name="MissingFieldB")

        url = reverse("admin:taxomesh_contrib_django_graph_reparent")
        # Deliberately omit node_uuid
        payload = {
            "kind": "item",
            "old_parent_uuid": str(cat_a.category_id),
            "new_parent_uuid": str(cat_b.category_id),
            "insert_before_uuid": None,
        }
        response = admin_client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data

    def test_reparent_invalid_kind_returns_400(self, admin_client: Client) -> None:
        """POST with an unrecognised kind value returns 400."""
        import json  # noqa: PLC0415
        import uuid  # noqa: PLC0415

        from django.urls import reverse  # noqa: PLC0415

        url = reverse("admin:taxomesh_contrib_django_graph_reparent")
        payload = {
            "kind": "unknown",
            "node_uuid": str(uuid.uuid4()),
            "old_parent_uuid": str(uuid.uuid4()),
            "new_parent_uuid": str(uuid.uuid4()),
            "insert_before_uuid": None,
        }
        response = admin_client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data

    def test_reparent_get_returns_405(self, admin_client: Client) -> None:
        """GET to the reparent endpoint returns 405 Method Not Allowed."""
        from django.urls import reverse  # noqa: PLC0415

        url = reverse("admin:taxomesh_contrib_django_graph_reparent")
        response = admin_client.get(url)
        assert response.status_code == 405

    def test_reparent_same_parent_is_idempotent_or_allowed(self, admin_client: Client) -> None:
        """POST with old_parent_uuid == new_parent_uuid returns 200 (backend allows same-parent reparent)."""
        import json  # noqa: PLC0415

        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat_a = svc.categories.create(name="SameParentA")
        item_x = svc.items.create(name="SameParentX")
        svc.items.place_in(item_x.item_id, cat_a.category_id)

        url = reverse("admin:taxomesh_contrib_django_graph_reparent")
        payload = {
            "kind": "item",
            "node_uuid": str(item_x.item_id),
            "old_parent_uuid": str(cat_a.category_id),
            "new_parent_uuid": str(cat_a.category_id),
            "insert_before_uuid": None,
        }
        response = admin_client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data == {"ok": True}


class TestReparentViewCategory:
    """Tests for reparent_view POST graph/reparent/ with kind="category"."""

    def test_reparent_category_returns_200(self, admin_client: Client) -> None:
        """Valid POST with kind=category, existing UUIDs returns 200 {ok: true}."""
        import json  # noqa: PLC0415

        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        old_parent = svc.categories.create(name="RVCOldParent")
        new_parent = svc.categories.create(name="RVCNewParent")
        child = svc.categories.create(name="RVCChild")
        svc.categories.add_parent(child.category_id, old_parent.category_id, sort_index=0)

        url = reverse("admin:taxomesh_contrib_django_graph_reparent")
        payload = {
            "kind": "category",
            "node_uuid": str(child.category_id),
            "old_parent_uuid": str(old_parent.category_id),
            "new_parent_uuid": str(new_parent.category_id),
            "insert_before_uuid": None,
        }
        response = admin_client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data == {"ok": True}

    def test_reparent_root_category_returns_400(self, admin_client: Client) -> None:
        """POST with the implicit root's identifier as node_uuid returns 400: the implicit root cannot be moved."""
        import json  # noqa: PLC0415

        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        root_uuid = TaxomeshService(repository=DjangoRepository())._root_id

        url = reverse("admin:taxomesh_contrib_django_graph_reparent")
        payload = {
            "kind": "category",
            "node_uuid": str(root_uuid),
            "old_parent_uuid": str(root_uuid),
            "new_parent_uuid": str(root_uuid),
            "insert_before_uuid": None,
        }
        response = admin_client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 400
        data = json.loads(response.content)
        assert data["error"] == "The implicit root cannot be moved"

    def test_reparent_category_cycle_returns_400(self, admin_client: Client) -> None:
        """POST that would create a DAG cycle returns 400 with a cycle error message."""
        import json  # noqa: PLC0415

        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        ancestor_parent = svc.categories.create(name="RVCCycleAncestorParent")
        ancestor = svc.categories.create(name="RVCCycleAncestor")
        descendant = svc.categories.create(name="RVCCycleDescendant")
        svc.categories.add_parent(ancestor.category_id, ancestor_parent.category_id, sort_index=0)
        svc.categories.add_parent(descendant.category_id, ancestor.category_id, sort_index=0)

        url = reverse("admin:taxomesh_contrib_django_graph_reparent")
        payload = {
            "kind": "category",
            "node_uuid": str(ancestor.category_id),
            "old_parent_uuid": str(ancestor_parent.category_id),
            "new_parent_uuid": str(descendant.category_id),
            "insert_before_uuid": None,
        }
        response = admin_client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data
        assert "ycle" in data["error"]  # "Cycle detected: ..." or similar
        # The page puts its own prefix before an error that names a cycle: the two together name it once.
        templates = pathlib.Path(__file__).parents[3] / "taxomesh" / "contrib" / "django" / "templates"
        page = (templates / "admin" / "taxomesh_contrib_django" / "graph.html").read_text(encoding="utf-8")
        prefix = re.search(r'msg\.indexOf\("ycle"\) !== -1 \? "([^"]*)"', page)
        assert prefix is not None
        assert (prefix.group(1) + data["error"]).count("Cycle detected") == 1

    def test_reparent_category_not_found_returns_400(self, admin_client: Client) -> None:
        """POST with a non-existent category UUID returns 400."""
        import json  # noqa: PLC0415
        import uuid  # noqa: PLC0415

        from django.urls import reverse  # noqa: PLC0415

        url = reverse("admin:taxomesh_contrib_django_graph_reparent")
        payload = {
            "kind": "category",
            "node_uuid": str(uuid.uuid4()),
            "old_parent_uuid": str(uuid.uuid4()),
            "new_parent_uuid": str(uuid.uuid4()),
            "insert_before_uuid": None,
        }
        response = admin_client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data


class TestExpandCollapseAfterDnd:
    """Regression: expand/collapse toggles remain functional after reorder and reparent."""

    def test_toggle_buttons_present_after_item_reorder(self, admin_client: Client) -> None:
        """After reordering items in a category, the graph view still renders toggle buttons."""
        import json  # noqa: PLC0415

        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.categories.create(name="ECRCat")
        item_a = svc.items.create(name="ECRA")
        item_b = svc.items.create(name="ECRB")
        svc.items.place_in(item_a.item_id, cat.category_id, sort_index=0)
        svc.items.place_in(item_b.item_id, cat.category_id, sort_index=1)

        reorder_url = reverse("admin:taxomesh_contrib_django_graph_reorder")
        admin_client.post(
            reorder_url,
            data=json.dumps(
                {
                    "kind": "item",
                    "parent_uuid": str(cat.category_id),
                    "ordered_uuids": [str(item_b.item_id), str(item_a.item_id)],
                }
            ),
            content_type="application/json",
        )

        graph_url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(graph_url)
        assert response.status_code == 200
        assert b'class="taxomesh-toggle"' in response.content, (
            "Toggle buttons must still be present after item reorder"
        )

    def test_toggle_buttons_present_after_item_reparent(self, admin_client: Client) -> None:
        """After reparenting an item, graph view still renders toggle buttons for non-empty categories."""
        import json  # noqa: PLC0415

        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat_a = svc.categories.create(name="ECRCatA")
        cat_b = svc.categories.create(name="ECRCatB")
        item_x = svc.items.create(name="ECRX")
        item_y = svc.items.create(name="ECRY")
        svc.items.place_in(item_x.item_id, cat_a.category_id, sort_index=0)
        svc.items.place_in(item_y.item_id, cat_b.category_id, sort_index=0)

        reparent_url = reverse("admin:taxomesh_contrib_django_graph_reparent")
        admin_client.post(
            reparent_url,
            data=json.dumps(
                {
                    "kind": "item",
                    "node_uuid": str(item_x.item_id),
                    "old_parent_uuid": str(cat_a.category_id),
                    "new_parent_uuid": str(cat_b.category_id),
                    "insert_before_uuid": None,
                }
            ),
            content_type="application/json",
        )

        graph_url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(graph_url)
        assert response.status_code == 200
        # cat_b now has 2 items → must show a toggle button in initial graph page
        assert b'class="taxomesh-toggle"' in response.content, (
            "Toggle buttons must still be present after item reparent (cat_b now has items)"
        )
        # Items themselves are lazy-loaded; verify via children endpoint
        children_url = reverse("admin:taxomesh_contrib_django_graph_children")
        children_resp = admin_client.get(children_url, {"parent_uuid": str(cat_b.category_id), "depth": "1"})
        content = children_resp.content.decode()
        assert "ECRX" in content
        assert "ECRY" in content


class TestDragHandleRendering:
    """Tests for drag handle HTML presence (a single item's handle is hidden by JS)."""

    def test_drag_handle_rendered_for_single_item_category(self, admin_client: Client) -> None:
        """Graph HTML must contain .taxomesh-drag-handle even when a category has only one item.

        The JS initHandles() hides it at runtime; this test verifies the element is present
        in the server-rendered HTML so the JS has something to act on.
        """
        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.categories.create(name="SingleItemCat")
        item = svc.items.create(name="OnlyItem")
        svc.items.place_in(item.item_id, cat.category_id)

        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)
        assert response.status_code == 200
        assert b"taxomesh-drag-handle" in response.content
        assert b'title="Drag to reorder or move"' in response.content
        # A failed drag names one of the page's two operations, a move or a reorder.
        assert set(re.findall(r'"(\w+) failed: "', response.content.decode())) == {"Move", "Reorder"}


class TestGraphChildrenView:
    """Tests for the lazy-load children endpoint GET graph/children/."""

    def test_returns_items_for_category(self, admin_client: Client) -> None:
        """GET graph/children/?parent_uuid=<uuid>&depth=1 returns items placed in that category."""
        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.categories.create(name="ChildCat")
        item_a = svc.items.create(name="ChildItemA")
        item_b = svc.items.create(name="ChildItemB")
        svc.items.place_in(item_a.item_id, cat.category_id)
        svc.items.place_in(item_b.item_id, cat.category_id)

        url = reverse("admin:taxomesh_contrib_django_graph_children")
        response = admin_client.get(url, {"parent_uuid": str(cat.category_id), "depth": "1"})
        assert response.status_code == 200
        content = response.content.decode()
        assert "ChildItemA" in content
        assert "ChildItemB" in content

    def test_returns_subcategories_for_category(self, admin_client: Client) -> None:
        """GET graph/children/ returns subcategories of the given parent."""
        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        parent = svc.categories.create(name="ParentChildCat")
        child = svc.categories.create(name="SubChildCat")
        svc.categories.add_parent(child.category_id, parent.category_id)

        url = reverse("admin:taxomesh_contrib_django_graph_children")
        response = admin_client.get(url, {"parent_uuid": str(parent.category_id), "depth": "1"})
        assert response.status_code == 200
        assert b"SubChildCat" in response.content

    def test_entries_carry_correct_depth_attribute(self, admin_client: Client) -> None:
        """Returned entries must carry data-depth matching the requested depth parameter."""
        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.categories.create(name="DepthCat")
        item = svc.items.create(name="DepthItem")
        svc.items.place_in(item.item_id, cat.category_id)

        url = reverse("admin:taxomesh_contrib_django_graph_children")
        response = admin_client.get(url, {"parent_uuid": str(cat.category_id), "depth": "2"})
        assert response.status_code == 200
        assert b'data-depth="2"' in response.content, "Returned entries must carry data-depth=2"

    def test_subcategory_with_children_has_toggle_button(self, admin_client: Client) -> None:
        """A subcategory that itself has children must have a toggle button in the fragment."""
        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        root = svc.categories.create(name="ToggleRoot")
        child = svc.categories.create(name="ToggleChild")
        grandchild = svc.categories.create(name="ToggleGrandchild")
        svc.categories.add_parent(child.category_id, root.category_id)
        svc.categories.add_parent(grandchild.category_id, child.category_id)

        url = reverse("admin:taxomesh_contrib_django_graph_children")
        response = admin_client.get(url, {"parent_uuid": str(root.category_id), "depth": "1"})
        assert response.status_code == 200
        assert b'class="taxomesh-toggle"' in response.content, (
            "Subcategory with grandchildren must have a toggle button"
        )

    def test_missing_parent_uuid_returns_400(self, admin_client: Client) -> None:
        """GET without parent_uuid returns 400."""
        from django.urls import reverse  # noqa: PLC0415

        url = reverse("admin:taxomesh_contrib_django_graph_children")
        response = admin_client.get(url)
        assert response.status_code == 400

    def test_invalid_parent_uuid_returns_400(self, admin_client: Client) -> None:
        """GET with a malformed parent_uuid returns 400."""
        from django.urls import reverse  # noqa: PLC0415

        url = reverse("admin:taxomesh_contrib_django_graph_children")
        response = admin_client.get(url, {"parent_uuid": "not-a-uuid"})
        assert response.status_code == 400

    def test_item_relations_appear_in_fragment(self, admin_client: Client) -> None:
        """Items with outgoing relations render relation data and rel-toggle in the fragment."""
        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.categories.create(name="RelFragCat")
        src = svc.items.create(name="RelSrc")
        tgt = svc.items.create(name="RelTgt")
        svc.items.place_in(src.item_id, cat.category_id)
        svc.items.place_in(tgt.item_id, cat.category_id)
        svc.items.relate(src.item_id, tgt.item_id, "uses")

        url = reverse("admin:taxomesh_contrib_django_graph_children")
        response = admin_client.get(url, {"parent_uuid": str(cat.category_id), "depth": "1"})
        content = response.content.decode()
        assert response.status_code == 200
        assert "uses" in content, "Relation type must appear in fragment"
        assert "RelTgt" in content, "Target item name must appear in fragment"
        assert "taxomesh-rel-toggle" in content, "Rel-toggle button must appear for item with relations"

    def test_linked_url_appears_in_fragment(self, admin_client: Client, settings: SettingsWrapper) -> None:
        """Items with a matching external_id get a ↗ icon in the children fragment."""
        from django.contrib.auth.models import User  # noqa: PLC0415
        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        user = User.objects.create_user(username="frag-linked-user", password="x")
        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.categories.create(name="LinkedFragCat")
        item = svc.items.create(name="LinkedFragItem", external_id=str(user.pk))
        svc.items.place_in(item.item_id, cat.category_id)

        settings.TAXOMESH_LINKED_MODEL = "auth.User"

        url = reverse("admin:taxomesh_contrib_django_graph_children")
        response = admin_client.get(url, {"parent_uuid": str(cat.category_id), "depth": "1"})
        assert "&#8599;" in response.content.decode(), (
            "Expected ↗ icon-link in children fragment for item with matching external_id"
        )

    def test_relation_to_disabled_item_is_not_rendered(self, admin_client: Client) -> None:
        """A relation whose target is disabled does not appear in the fragment.

        The graph renders a disabled *row* in its own right, marked with a ✗, but a relation
        is resolved through the batch read, which materialises enabled items only.
        """
        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.categories.create(name="DisabledRelCat")
        src = svc.items.create(name="RelSourceVisible")
        live = svc.items.create(name="RelTargetLive")
        gone = svc.items.create(name="RelTargetDisabled")
        svc.items.place_in(src.item_id, cat.category_id)
        svc.items.relate(src.item_id, live.item_id, "covers")
        svc.items.relate(src.item_id, gone.item_id, "covers")
        svc.items.update(gone.item_id, enabled=False)

        url = reverse("admin:taxomesh_contrib_django_graph_children")
        response = admin_client.get(url, {"parent_uuid": str(cat.category_id), "depth": "1"})
        content = response.content.decode()
        assert "RelTargetLive" in content, "a relation to an enabled item must still render"
        assert "RelTargetDisabled" not in content, (
            "a relation whose target is disabled must not render: the batch read resolves enabled items only"
        )
