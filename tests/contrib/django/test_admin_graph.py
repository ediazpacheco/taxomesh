"""Tests for the Django admin taxonomy graph view (024-graph-enhancements)."""

import pathlib

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

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
    """Tests for expand/collapse toggle buttons in the admin graph view (US3)."""

    def test_non_empty_category_has_toggle_button(self, admin_client: object) -> None:
        """A category that has items must render a taxomesh-toggle button."""
        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.create_category(name="NonEmptyCat")
        item = svc.create_item(name="SomeItem")
        svc.place_item_in_category(item.item_id, cat.category_id)

        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)  # type: ignore[attr-defined]
        assert b'<button class="taxomesh-toggle"' in response.content, (
            "Expected a taxomesh-toggle button element for a category with items"
        )

    def test_empty_category_has_no_toggle_button(self, admin_client: object) -> None:
        """A category with no items and no children must NOT have a toggle button."""
        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        svc.create_category(name="EmptyCat")

        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)  # type: ignore[attr-defined]
        assert b'<button class="taxomesh-toggle"' not in response.content, (
            "Expected no taxomesh-toggle button element for an empty category"
        )

    def test_leaf_item_without_relations_has_no_toggle_button(self, admin_client: object) -> None:
        """An item without outgoing relations must NOT have a toggle button."""
        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.create_category(name="MyCat")
        item = svc.create_item(name="LeafItem")
        svc.place_item_in_category(item.item_id, cat.category_id)

        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)  # type: ignore[attr-defined]
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
    """Tests for item relations toggle in the admin graph view (US4)."""

    def _setup_taxonomy_with_relation(self) -> None:
        """Create a category with two items and an outgoing relation."""
        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.create_category(name="Music")
        item_a = svc.create_item(name="Alpha")
        item_b = svc.create_item(name="Beta")
        svc.place_item_in_category(item_a.item_id, cat.category_id)
        svc.place_item_in_category(item_b.item_id, cat.category_id)
        svc.relate_items(item_a.item_id, item_b.item_id, "covers")

    def test_relations_toggle_checkbox_removed(self, admin_client: object) -> None:
        """The global 'Show item relations' checkbox must not be present (removed in 025)."""
        from django.urls import reverse  # noqa: PLC0415

        self._setup_taxonomy_with_relation()
        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)  # type: ignore[attr-defined]
        assert b'id="taxomesh-show-relations"' not in response.content, (
            "The 'Show item relations' global checkbox must be absent (per-item toggle only)"
        )

    def test_item_relations_in_context(self, admin_client: object) -> None:
        """Relation data must appear in the children endpoint HTML fragment."""
        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.create_category(name="MusicRel")
        item_a = svc.create_item(name="Alpha")
        item_b = svc.create_item(name="Beta")
        svc.place_item_in_category(item_a.item_id, cat.category_id)
        svc.place_item_in_category(item_b.item_id, cat.category_id)
        svc.relate_items(item_a.item_id, item_b.item_id, "covers")

        url = reverse("admin:taxomesh_contrib_django_graph_children")
        response = admin_client.get(url, {"parent_uuid": str(cat.category_id), "depth": "1"})  # type: ignore[attr-defined]
        content = response.content.decode()
        assert "covers" in content, "Expected relation type 'covers' to appear in children HTML fragment"
        assert "Beta" in content, "Expected target item name 'Beta' to appear in relation row"

    def test_relation_rows_hidden_by_default(self, admin_client: object) -> None:
        """Relation rows CSS (.taxomesh-relations) must have display:none in graph.html."""
        from django.urls import reverse  # noqa: PLC0415

        self._setup_taxonomy_with_relation()
        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)  # type: ignore[attr-defined]
        # The CSS rule must be present in the page
        assert b".taxomesh-relations" in response.content

    def test_item_with_relations_has_toggle_button_when_relations_loaded(self, admin_client: object) -> None:
        """An item that has outgoing relations must render a rel-toggle button in children fragment."""
        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.create_category(name="MusicToggle")
        item_a = svc.create_item(name="AlphaToggle")
        item_b = svc.create_item(name="BetaToggle")
        svc.place_item_in_category(item_a.item_id, cat.category_id)
        svc.place_item_in_category(item_b.item_id, cat.category_id)
        svc.relate_items(item_a.item_id, item_b.item_id, "covers")

        url = reverse("admin:taxomesh_contrib_django_graph_children")
        response = admin_client.get(url, {"parent_uuid": str(cat.category_id), "depth": "1"})  # type: ignore[attr-defined]
        assert b"taxomesh-rel-toggle" in response.content, (
            "Expected a taxomesh-rel-toggle button for an item with outgoing relations in children fragment"
        )


class TestLinkedModel:
    """Tests for admin icon-links to configured Django model (US5)."""

    def _setup_category_with_item(self, external_id: str | None = None) -> None:
        """Create a category with one item, optionally with an external_id."""
        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.create_category(name="TestCat")
        item = svc.create_item(name="TestItem", external_id=external_id or "")
        svc.place_item_in_category(item.item_id, cat.category_id)

    def test_icon_link_appears_when_model_configured_and_external_id_set(
        self, admin_client: object, settings: object
    ) -> None:
        """When TAXOMESH_LINKED_MODEL is set and item.external_id matches a pk, ↗ appears in children fragment."""
        from django.contrib.auth.models import User  # noqa: PLC0415
        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        # Create a Django User whose pk will be used as external_id
        user = User.objects.create_user(username="linked-user", password="x")
        self._setup_category_with_item(external_id=str(user.pk))

        settings.TAXOMESH_LINKED_MODEL = "auth.User"  # type: ignore[union-attr]

        # Items are loaded lazily via the children endpoint, not the initial graph page
        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cats = svc.list_categories()
        assert cats, "Expected at least one root category"
        cat = cats[0]

        url = reverse("admin:taxomesh_contrib_django_graph_children")
        response = admin_client.get(url, {"parent_uuid": str(cat.category_id), "depth": "1"})  # type: ignore[attr-defined]
        assert "&#8599;" in response.content.decode(), (
            "Expected ↗ icon-link (&#8599;) for item with matching external_id in children fragment"
        )

    def test_no_icon_when_external_id_absent(self, admin_client: object, settings: object) -> None:
        """No ↗ icon when the item has no external_id."""
        from django.urls import reverse  # noqa: PLC0415

        self._setup_category_with_item(external_id="")
        settings.TAXOMESH_LINKED_MODEL = "auth.User"  # type: ignore[union-attr]

        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)  # type: ignore[attr-defined]
        assert "&#8599;" not in response.content.decode(), "Expected no ↗ icon when item has no external_id"

    def test_no_icon_when_setting_absent(self, admin_client: object) -> None:
        """No ↗ icon when TAXOMESH_LINKED_MODEL is not configured."""
        from django.contrib.auth.models import User  # noqa: PLC0415
        from django.urls import reverse  # noqa: PLC0415

        user = User.objects.create_user(username="unlinked-user", password="x")
        self._setup_category_with_item(external_id=str(user.pk))

        # Do NOT set TAXOMESH_LINKED_MODEL in settings

        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)  # type: ignore[attr-defined]
        assert "&#8599;" not in response.content.decode(), (
            "Expected no ↗ icon when TAXOMESH_LINKED_MODEL setting is absent"
        )

    def test_no_icon_when_instance_not_found(self, admin_client: object, settings: object) -> None:
        """No ↗ icon when setting is valid but no instance with the given pk exists."""
        from django.urls import reverse  # noqa: PLC0415

        # Use a pk that doesn't exist
        self._setup_category_with_item(external_id="999999")
        settings.TAXOMESH_LINKED_MODEL = "auth.User"  # type: ignore[union-attr]

        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)  # type: ignore[attr-defined]
        assert "&#8599;" not in response.content.decode(), (
            "Expected no ↗ icon when linked model instance does not exist"
        )


class TestDepthAndRelations:
    """Tests for admin graph depth limit and relations-always-collapsed (T007)."""

    def _setup_deep_taxonomy(self) -> None:
        """Create a 5-level taxonomy: L0 > L1 > L2 > L3 > L4, each category with one item."""
        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        l0 = svc.create_category(name="L0admin")
        l1 = svc.create_category(name="L1admin")
        l2 = svc.create_category(name="L2admin")
        l3 = svc.create_category(name="L3admin")
        l4 = svc.create_category(name="L4admin")
        svc.add_category_parent(l1.category_id, l0.category_id)
        svc.add_category_parent(l2.category_id, l1.category_id)
        svc.add_category_parent(l3.category_id, l2.category_id)
        svc.add_category_parent(l4.category_id, l3.category_id)
        for lvl, cat in enumerate([l0, l1, l2, l3, l4]):
            item = svc.create_item(name=f"AdminItem{lvl}")
            svc.place_item_in_category(item.item_id, cat.category_id)

    def _setup_taxonomy_with_relation(self) -> None:
        """Create a category with two items and an outgoing relation."""
        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.create_category(name="RelCat")
        item_a = svc.create_item(name="RelAlpha")
        item_b = svc.create_item(name="RelBeta")
        svc.place_item_in_category(item_a.item_id, cat.category_id)
        svc.place_item_in_category(item_b.item_id, cat.category_id)
        svc.relate_items(item_a.item_id, item_b.item_id, "related_to")

    def test_admin_graph_omits_nodes_beyond_default_depth(self, admin_client: object) -> None:
        """Initial graph view shows only root-level categories; subcategories load lazily."""
        from django.urls import reverse  # noqa: PLC0415

        self._setup_deep_taxonomy()
        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)  # type: ignore[attr-defined]
        content = response.content.decode()
        # L0admin is the root-level category and must appear in the initial page
        assert "L0admin" in content, "L0admin (root) must appear in the initial graph page"
        # L1admin is a subcategory and must NOT appear in the initial page (lazy-loaded)
        assert "L1admin" not in content, "L1admin (subcategory) must not appear in initial page — lazy-loaded"
        # data-depth-limited concept is removed; no such attribute
        assert 'data-depth-limited="1"' not in content, "data-depth-limited attribute must be absent (concept removed)"

    def test_admin_graph_no_relations_toggle_checkbox(self, admin_client: object) -> None:
        """The 'Show item relations' checkbox must not be present in admin graph HTML."""
        from django.urls import reverse  # noqa: PLC0415

        self._setup_taxonomy_with_relation()
        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)  # type: ignore[attr-defined]
        assert b'id="taxomesh-show-relations"' not in response.content, (
            "The 'Show item relations' checkbox must be removed from admin graph"
        )

    def test_admin_graph_item_with_relations_has_toggle_button(self, admin_client: object) -> None:
        """Items with outgoing relations must render a rel-toggle button in the children fragment."""
        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.create_category(name="RelCat2")
        item_a = svc.create_item(name="RelAlpha2")
        item_b = svc.create_item(name="RelBeta2")
        svc.place_item_in_category(item_a.item_id, cat.category_id)
        svc.place_item_in_category(item_b.item_id, cat.category_id)
        svc.relate_items(item_a.item_id, item_b.item_id, "related_to")

        url = reverse("admin:taxomesh_contrib_django_graph_children")
        response = admin_client.get(url, {"parent_uuid": str(cat.category_id), "depth": "1"})  # type: ignore[attr-defined]
        assert b"taxomesh-rel-toggle" in response.content, "Items with relations must have a rel-toggle button"

    def test_admin_graph_relation_rows_hidden_by_default(self, admin_client: object) -> None:
        """Relation rows CSS (.taxomesh-relations) must have display:none in graph.html style block."""
        from django.urls import reverse  # noqa: PLC0415

        self._setup_taxonomy_with_relation()
        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)  # type: ignore[attr-defined]
        content = response.content.decode()
        # The CSS rule must be present in the page
        assert ".taxomesh-relations {" in content or ".taxomesh-relations{" in content
        assert "taxomesh-relations-visible" not in content, (
            "The .taxomesh-relations-visible CSS class and JS must be removed"
        )

    def test_admin_graph_depth_limited_category_shows_clickable_expand_button(self, admin_client: object) -> None:
        """A root category with subcategories must show a [+] toggle button in the initial graph page."""
        from django.urls import reverse  # noqa: PLC0415

        self._setup_deep_taxonomy()
        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)  # type: ignore[attr-defined]
        content = response.content.decode()
        # L0admin is root-level and has descendants (L1admin), so it must show a toggle button
        assert "L0admin" in content, "L0admin must be present in the initial graph"
        assert "taxomesh-depth-limited" not in content, (
            "taxomesh-depth-limited class must be absent — depth limiting concept removed"
        )
        assert 'class="taxomesh-toggle"' in content, "L0admin (which has children) must show a toggle [+] button"


class TestLinkedObjectColumn:
    """Tests for linked_object_url column in Item/Category list and detail (T010)."""

    def _setup_item_with_external_id(self, external_id: str) -> None:
        """Create an item with the given external_id in a category."""
        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.create_category(name="IconCat")
        item = svc.create_item(name="IconItem", external_id=external_id)
        svc.place_item_in_category(item.item_id, cat.category_id)

    def _setup_category_with_external_id(self, external_id: str) -> None:
        """Create a category with the given external_id (set via ORM after service create)."""
        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415
        from taxomesh.contrib.django.models import CategoryModel  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.create_category(name="IconLinkCat")
        CategoryModel.objects.filter(category_id=cat.category_id).update(external_id=external_id)

    def test_item_list_shows_linked_url_column_when_model_configured(
        self, admin_client: object, settings: object
    ) -> None:
        """Item changelist must show a ↗ icon link for items with external_id when TAXOMESH_LINKED_MODEL is set."""
        from django.contrib.auth.models import User  # noqa: PLC0415
        from django.urls import reverse  # noqa: PLC0415

        user = User.objects.create_user(username="icon-user", password="x")
        self._setup_item_with_external_id(str(user.pk))
        settings.TAXOMESH_LINKED_MODEL = "auth.User"  # type: ignore[union-attr]

        url = reverse("admin:taxomesh_contrib_django_itemmodel_changelist")
        response = admin_client.get(url)  # type: ignore[attr-defined]
        assert "&#8599;" in response.content.decode(), (
            "Expected ↗ (&#8599;) icon-link in Item changelist when TAXOMESH_LINKED_MODEL configured"
        )

    def test_item_list_no_icon_when_external_id_absent(self, admin_client: object, settings: object) -> None:
        """No ↗ icon in Item changelist for items without external_id."""
        from django.urls import reverse  # noqa: PLC0415

        self._setup_item_with_external_id("")
        settings.TAXOMESH_LINKED_MODEL = "auth.User"  # type: ignore[union-attr]

        url = reverse("admin:taxomesh_contrib_django_itemmodel_changelist")
        response = admin_client.get(url)  # type: ignore[attr-defined]
        assert "&#8599;" not in response.content.decode(), (
            "Expected no ↗ icon in Item changelist for items without external_id"
        )

    def test_category_list_shows_linked_url_column(self, admin_client: object, settings: object) -> None:
        """Category changelist must show a ↗ icon link for categories with external_id."""
        from django.contrib.auth.models import User  # noqa: PLC0415
        from django.urls import reverse  # noqa: PLC0415

        user = User.objects.create_user(username="cat-icon-user", password="x")
        self._setup_category_with_external_id(str(user.pk))
        settings.TAXOMESH_LINKED_MODEL = "auth.User"  # type: ignore[union-attr]

        url = reverse("admin:taxomesh_contrib_django_categorymodel_changelist")
        response = admin_client.get(url)  # type: ignore[attr-defined]
        assert "&#8599;" in response.content.decode(), (
            "Expected ↗ (&#8599;) icon-link in Category changelist when TAXOMESH_LINKED_MODEL configured"
        )

    def test_item_detail_shows_linked_url_field(self, admin_client: object, settings: object) -> None:
        """Item change form must show ↗ link in readonly fields when external_id matches linked model."""
        from django.contrib.auth.models import User  # noqa: PLC0415
        from django.urls import reverse  # noqa: PLC0415

        user = User.objects.create_user(username="detail-icon-user", password="x")
        self._setup_item_with_external_id(str(user.pk))
        settings.TAXOMESH_LINKED_MODEL = "auth.User"  # type: ignore[union-attr]

        # Get the item's UUID
        from taxomesh.contrib.django.models import ItemModel  # noqa: PLC0415

        item_obj = ItemModel.objects.get(external_id=str(user.pk))

        url = reverse("admin:taxomesh_contrib_django_itemmodel_change", args=[item_obj.item_id])
        response = admin_client.get(url)  # type: ignore[attr-defined]
        assert "&#8599;" in response.content.decode(), "Expected ↗ icon-link in Item change form readonly fields"


class TestVersionWidget:
    """Tests for the taxomesh version widget in the admin app_index (T013)."""

    def test_app_index_shows_taxomesh_version(self, admin_client: object) -> None:
        """The app_index page must show a taxomesh version string."""
        from django.urls import reverse  # noqa: PLC0415

        url = reverse("admin:app_list", kwargs={"app_label": "taxomesh_contrib_django"})
        response = admin_client.get(url)  # type: ignore[attr-defined]
        content = response.content.decode()
        # The version string must be non-empty and present in the page
        assert "0.1.0" in content or "unknown" in content, (
            "Expected taxomesh version (e.g. '0.1.0a12') or 'unknown' in app_index HTML"
        )

    def test_app_index_shows_backend_info(self, admin_client: object) -> None:
        """The app_index page must show backend/config info."""
        from django.urls import reverse  # noqa: PLC0415

        url = reverse("admin:app_list", kwargs={"app_label": "taxomesh_contrib_django"})
        response = admin_client.get(url)  # type: ignore[attr-defined]
        content = response.content.decode()
        # Either a path to taxomesh.toml or the default Django ORM backend string
        assert "Django ORM backend" in content or "taxomesh.toml" in content, (
            "Expected backend info ('Django ORM backend' or taxomesh.toml path) in app_index HTML"
        )


class TestItemRelationLinkNotRegistered:
    """Tests that ItemRelationLinkModel is NOT registered in the Django admin (T016)."""

    def test_item_relation_link_not_in_admin_registry(self) -> None:
        """ItemRelationLinkModel must not be in admin.site._registry after T017."""
        from django.contrib import admin  # noqa: PLC0415

        from taxomesh.contrib.django.models import ItemRelationLinkModel  # noqa: PLC0415

        assert ItemRelationLinkModel not in admin.site._registry, (
            "ItemRelationLinkModelAdmin must be removed from admin registry"
        )


class TestReorderView:
    """Tests for the graph reorder endpoint POST graph/reorder/ (drag-and-drop ordering)."""

    def test_reorder_items_returns_200(self, admin_client: object) -> None:
        """Valid POST with kind=item, existing parent_uuid, and ordered_uuids returns 200 {ok: true}."""
        import json  # noqa: PLC0415

        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.create_category(name="Cat")
        item_a = svc.create_item(name="A")
        item_b = svc.create_item(name="B")
        item_c = svc.create_item(name="C")
        svc.place_item_in_category(item_a.item_id, cat.category_id, sort_index=0)
        svc.place_item_in_category(item_b.item_id, cat.category_id, sort_index=1)
        svc.place_item_in_category(item_c.item_id, cat.category_id, sort_index=2)

        url = reverse("admin:taxomesh_contrib_django_graph_reorder")
        payload = {
            "kind": "item",
            "parent_uuid": str(cat.category_id),
            "ordered_uuids": [str(item_c.item_id), str(item_a.item_id), str(item_b.item_id)],
        }
        response = admin_client.post(  # type: ignore[attr-defined]
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data == {"ok": True}

    def test_reorder_missing_kind_returns_400(self, admin_client: object) -> None:
        """POST without 'kind' field returns 400 with an error key."""
        import json  # noqa: PLC0415

        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.create_category(name="CatMissingKind")
        item_a = svc.create_item(name="MKA")
        svc.place_item_in_category(item_a.item_id, cat.category_id, sort_index=0)

        url = reverse("admin:taxomesh_contrib_django_graph_reorder")
        payload = {
            "parent_uuid": str(cat.category_id),
            "ordered_uuids": [str(item_a.item_id)],
        }
        response = admin_client.post(  # type: ignore[attr-defined]
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data

    def test_reorder_missing_parent_uuid_returns_400(self, admin_client: object) -> None:
        """POST without 'parent_uuid' field returns 400 with an error key."""
        import json  # noqa: PLC0415

        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        item_a = svc.create_item(name="MPA")

        url = reverse("admin:taxomesh_contrib_django_graph_reorder")
        payload = {
            "kind": "item",
            "ordered_uuids": [str(item_a.item_id)],
        }
        response = admin_client.post(  # type: ignore[attr-defined]
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data

    def test_reorder_unknown_parent_uuid_returns_400(self, admin_client: object) -> None:
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
        response = admin_client.post(  # type: ignore[attr-defined]
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_reorder_get_returns_405(self, admin_client: object) -> None:
        """GET to the reorder endpoint returns 405 Method Not Allowed."""
        from django.urls import reverse  # noqa: PLC0415

        url = reverse("admin:taxomesh_contrib_django_graph_reorder")
        response = admin_client.get(url)  # type: ignore[attr-defined]
        assert response.status_code == 405


class TestReorderViewCategory:
    """Tests for the graph reorder endpoint with kind="category" (drag-and-drop category ordering)."""

    def test_reorder_categories_returns_200(self, admin_client: object) -> None:
        """Valid POST with kind=category, existing parent_uuid, and ordered_uuids returns 200 {ok: true}."""
        import json  # noqa: PLC0415

        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        parent = svc.create_category(name="Parent")
        child_a = svc.create_category(name="ChildA")
        child_b = svc.create_category(name="ChildB")
        child_c = svc.create_category(name="ChildC")
        svc.add_category_parent(child_a.category_id, parent.category_id, sort_index=0)
        svc.add_category_parent(child_b.category_id, parent.category_id, sort_index=1)
        svc.add_category_parent(child_c.category_id, parent.category_id, sort_index=2)

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
        response = admin_client.post(  # type: ignore[attr-defined]
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data == {"ok": True}

    def test_reorder_categories_unknown_parent_returns_400(self, admin_client: object) -> None:
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
        response = admin_client.post(  # type: ignore[attr-defined]
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_reorder_invalid_kind_returns_400(self, admin_client: object) -> None:
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
        response = admin_client.post(  # type: ignore[attr-defined]
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data


class TestReparentView:
    """Tests for the graph reparent endpoint POST graph/reparent/ (drag-and-drop reparenting)."""

    def test_reparent_item_returns_200(self, admin_client: object) -> None:
        """Valid POST with kind=item, existing node/parent UUIDs returns 200 {ok: true}."""
        import json  # noqa: PLC0415

        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat_a = svc.create_category(name="A")
        cat_b = svc.create_category(name="B")
        item_x = svc.create_item(name="X")
        svc.place_item_in_category(item_x.item_id, cat_a.category_id)

        url = reverse("admin:taxomesh_contrib_django_graph_reparent")
        payload = {
            "kind": "item",
            "node_uuid": str(item_x.item_id),
            "old_parent_uuid": str(cat_a.category_id),
            "new_parent_uuid": str(cat_b.category_id),
            "insert_before_uuid": None,
        }
        response = admin_client.post(  # type: ignore[attr-defined]
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data == {"ok": True}

    def test_reparent_missing_field_returns_400(self, admin_client: object) -> None:
        """POST missing the node_uuid field returns 400 with an error key."""
        import json  # noqa: PLC0415

        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat_a = svc.create_category(name="MissingFieldA")
        cat_b = svc.create_category(name="MissingFieldB")

        url = reverse("admin:taxomesh_contrib_django_graph_reparent")
        # Deliberately omit node_uuid
        payload = {
            "kind": "item",
            "old_parent_uuid": str(cat_a.category_id),
            "new_parent_uuid": str(cat_b.category_id),
            "insert_before_uuid": None,
        }
        response = admin_client.post(  # type: ignore[attr-defined]
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data

    def test_reparent_invalid_kind_returns_400(self, admin_client: object) -> None:
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
        response = admin_client.post(  # type: ignore[attr-defined]
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data

    def test_reparent_get_returns_405(self, admin_client: object) -> None:
        """GET to the reparent endpoint returns 405 Method Not Allowed."""
        from django.urls import reverse  # noqa: PLC0415

        url = reverse("admin:taxomesh_contrib_django_graph_reparent")
        response = admin_client.get(url)  # type: ignore[attr-defined]
        assert response.status_code == 405

    def test_reparent_same_parent_is_idempotent_or_allowed(self, admin_client: object) -> None:
        """POST with old_parent_uuid == new_parent_uuid returns 200 (backend allows same-parent reparent)."""
        import json  # noqa: PLC0415

        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat_a = svc.create_category(name="SameParentA")
        item_x = svc.create_item(name="SameParentX")
        svc.place_item_in_category(item_x.item_id, cat_a.category_id)

        url = reverse("admin:taxomesh_contrib_django_graph_reparent")
        payload = {
            "kind": "item",
            "node_uuid": str(item_x.item_id),
            "old_parent_uuid": str(cat_a.category_id),
            "new_parent_uuid": str(cat_a.category_id),
            "insert_before_uuid": None,
        }
        response = admin_client.post(  # type: ignore[attr-defined]
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data == {"ok": True}


class TestReparentViewCategory:
    """Tests for reparent_view POST graph/reparent/ with kind="category" (US4)."""

    def test_reparent_category_returns_200(self, admin_client: object) -> None:
        """Valid POST with kind=category, existing UUIDs returns 200 {ok: true}."""
        import json  # noqa: PLC0415

        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        old_parent = svc.create_category(name="RVCOldParent")
        new_parent = svc.create_category(name="RVCNewParent")
        child = svc.create_category(name="RVCChild")
        svc.add_category_parent(child.category_id, old_parent.category_id, sort_index=0)

        url = reverse("admin:taxomesh_contrib_django_graph_reparent")
        payload = {
            "kind": "category",
            "node_uuid": str(child.category_id),
            "old_parent_uuid": str(old_parent.category_id),
            "new_parent_uuid": str(new_parent.category_id),
            "insert_before_uuid": None,
        }
        response = admin_client.post(  # type: ignore[attr-defined]
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data == {"ok": True}

    def test_reparent_root_category_returns_400(self, admin_client: object) -> None:
        """POST with node_uuid == ROOT category UUID returns 400 with cycle/root error."""
        import json  # noqa: PLC0415

        from django.urls import reverse  # noqa: PLC0415

        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415
        from taxomesh.domain.constants import ROOT_CATEGORY_NAME  # noqa: PLC0415

        repo = DjangoRepository()
        root_cats = [c for c in repo.list_categories() if c.name == ROOT_CATEGORY_NAME]
        if not root_cats:
            pytest.skip("No ROOT category present in test DB")
        root_uuid = root_cats[0].category_id

        url = reverse("admin:taxomesh_contrib_django_graph_reparent")
        payload = {
            "kind": "category",
            "node_uuid": str(root_uuid),
            "old_parent_uuid": str(root_uuid),
            "new_parent_uuid": str(root_uuid),
            "insert_before_uuid": None,
        }
        response = admin_client.post(  # type: ignore[attr-defined]
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data

    def test_reparent_category_cycle_returns_400(self, admin_client: object) -> None:
        """POST that would create a DAG cycle returns 400 with a cycle error message."""
        import json  # noqa: PLC0415

        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        ancestor_parent = svc.create_category(name="RVCCycleAncestorParent")
        ancestor = svc.create_category(name="RVCCycleAncestor")
        descendant = svc.create_category(name="RVCCycleDescendant")
        svc.add_category_parent(ancestor.category_id, ancestor_parent.category_id, sort_index=0)
        svc.add_category_parent(descendant.category_id, ancestor.category_id, sort_index=0)

        url = reverse("admin:taxomesh_contrib_django_graph_reparent")
        payload = {
            "kind": "category",
            "node_uuid": str(ancestor.category_id),
            "old_parent_uuid": str(ancestor_parent.category_id),
            "new_parent_uuid": str(descendant.category_id),
            "insert_before_uuid": None,
        }
        response = admin_client.post(  # type: ignore[attr-defined]
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data
        assert "ycle" in data["error"]  # "Cycle detected: ..." or similar

    def test_reparent_category_not_found_returns_400(self, admin_client: object) -> None:
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
        response = admin_client.post(  # type: ignore[attr-defined]
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 400
        data = json.loads(response.content)
        assert "error" in data


class TestExpandCollapseAfterDnd:
    """Regression: expand/collapse toggles remain functional after reorder and reparent (T031)."""

    def test_toggle_buttons_present_after_item_reorder(self, admin_client: object) -> None:
        """After reordering items in a category, the graph view still renders toggle buttons."""
        import json  # noqa: PLC0415

        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.create_category(name="ECRCat")
        item_a = svc.create_item(name="ECRA")
        item_b = svc.create_item(name="ECRB")
        svc.place_item_in_category(item_a.item_id, cat.category_id, sort_index=0)
        svc.place_item_in_category(item_b.item_id, cat.category_id, sort_index=1)

        reorder_url = reverse("admin:taxomesh_contrib_django_graph_reorder")
        admin_client.post(  # type: ignore[attr-defined]
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
        response = admin_client.get(graph_url)  # type: ignore[attr-defined]
        assert response.status_code == 200
        assert b'class="taxomesh-toggle"' in response.content, (
            "Toggle buttons must still be present after item reorder"
        )

    def test_toggle_buttons_present_after_item_reparent(self, admin_client: object) -> None:
        """After reparenting an item, graph view still renders toggle buttons for non-empty categories."""
        import json  # noqa: PLC0415

        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat_a = svc.create_category(name="ECRCatA")
        cat_b = svc.create_category(name="ECRCatB")
        item_x = svc.create_item(name="ECRX")
        item_y = svc.create_item(name="ECRY")
        svc.place_item_in_category(item_x.item_id, cat_a.category_id, sort_index=0)
        svc.place_item_in_category(item_y.item_id, cat_b.category_id, sort_index=0)

        reparent_url = reverse("admin:taxomesh_contrib_django_graph_reparent")
        admin_client.post(  # type: ignore[attr-defined]
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
        response = admin_client.get(graph_url)  # type: ignore[attr-defined]
        assert response.status_code == 200
        # cat_b now has 2 items → must show a toggle button in initial graph page
        assert b'class="taxomesh-toggle"' in response.content, (
            "Toggle buttons must still be present after item reparent (cat_b now has items)"
        )
        # Items themselves are lazy-loaded; verify via children endpoint
        children_url = reverse("admin:taxomesh_contrib_django_graph_children")
        children_resp = admin_client.get(  # type: ignore[attr-defined]
            children_url, {"parent_uuid": str(cat_b.category_id), "depth": "1"}
        )
        content = children_resp.content.decode()
        assert "ECRX" in content
        assert "ECRY" in content


class TestDragHandleRendering:
    """Tests for drag handle HTML presence (US1 AC3 — singleton handle hidden by JS)."""

    def test_drag_handle_rendered_for_single_item_category(self, admin_client: object) -> None:
        """Graph HTML must contain .taxomesh-drag-handle even when a category has only one item.

        The JS initHandles() hides it at runtime; this test verifies the element is present
        in the server-rendered HTML so the JS has something to act on.
        """
        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.create_category(name="SingleItemCat")
        item = svc.create_item(name="OnlyItem")
        svc.place_item_in_category(item.item_id, cat.category_id)

        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)  # type: ignore[attr-defined]
        assert response.status_code == 200
        assert b"taxomesh-drag-handle" in response.content


class TestGraphChildrenView:
    """Tests for the lazy-load children endpoint GET graph/children/ (030-graph-drag-drop)."""

    def test_returns_items_for_category(self, admin_client: object) -> None:
        """GET graph/children/?parent_uuid=<uuid>&depth=1 returns items placed in that category."""
        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.create_category(name="ChildCat")
        item_a = svc.create_item(name="ChildItemA")
        item_b = svc.create_item(name="ChildItemB")
        svc.place_item_in_category(item_a.item_id, cat.category_id)
        svc.place_item_in_category(item_b.item_id, cat.category_id)

        url = reverse("admin:taxomesh_contrib_django_graph_children")
        response = admin_client.get(url, {"parent_uuid": str(cat.category_id), "depth": "1"})  # type: ignore[attr-defined]
        assert response.status_code == 200
        content = response.content.decode()
        assert "ChildItemA" in content
        assert "ChildItemB" in content

    def test_returns_subcategories_for_category(self, admin_client: object) -> None:
        """GET graph/children/ returns subcategories of the given parent."""
        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        parent = svc.create_category(name="ParentChildCat")
        child = svc.create_category(name="SubChildCat")
        svc.add_category_parent(child.category_id, parent.category_id)

        url = reverse("admin:taxomesh_contrib_django_graph_children")
        response = admin_client.get(url, {"parent_uuid": str(parent.category_id), "depth": "1"})  # type: ignore[attr-defined]
        assert response.status_code == 200
        assert b"SubChildCat" in response.content

    def test_entries_carry_correct_depth_attribute(self, admin_client: object) -> None:
        """Returned entries must carry data-depth matching the requested depth parameter."""
        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.create_category(name="DepthCat")
        item = svc.create_item(name="DepthItem")
        svc.place_item_in_category(item.item_id, cat.category_id)

        url = reverse("admin:taxomesh_contrib_django_graph_children")
        response = admin_client.get(url, {"parent_uuid": str(cat.category_id), "depth": "2"})  # type: ignore[attr-defined]
        assert response.status_code == 200
        assert b'data-depth="2"' in response.content, "Returned entries must carry data-depth=2"

    def test_subcategory_with_children_has_toggle_button(self, admin_client: object) -> None:
        """A subcategory that itself has children must have a toggle button in the fragment."""
        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        root = svc.create_category(name="ToggleRoot")
        child = svc.create_category(name="ToggleChild")
        grandchild = svc.create_category(name="ToggleGrandchild")
        svc.add_category_parent(child.category_id, root.category_id)
        svc.add_category_parent(grandchild.category_id, child.category_id)

        url = reverse("admin:taxomesh_contrib_django_graph_children")
        response = admin_client.get(url, {"parent_uuid": str(root.category_id), "depth": "1"})  # type: ignore[attr-defined]
        assert response.status_code == 200
        assert b'class="taxomesh-toggle"' in response.content, (
            "Subcategory with grandchildren must have a toggle button"
        )

    def test_missing_parent_uuid_returns_400(self, admin_client: object) -> None:
        """GET without parent_uuid returns 400."""
        from django.urls import reverse  # noqa: PLC0415

        url = reverse("admin:taxomesh_contrib_django_graph_children")
        response = admin_client.get(url)  # type: ignore[attr-defined]
        assert response.status_code == 400

    def test_invalid_parent_uuid_returns_400(self, admin_client: object) -> None:
        """GET with a malformed parent_uuid returns 400."""
        from django.urls import reverse  # noqa: PLC0415

        url = reverse("admin:taxomesh_contrib_django_graph_children")
        response = admin_client.get(url, {"parent_uuid": "not-a-uuid"})  # type: ignore[attr-defined]
        assert response.status_code == 400

    def test_item_relations_appear_in_fragment(self, admin_client: object) -> None:
        """Items with outgoing relations render relation data and rel-toggle in the fragment."""
        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.create_category(name="RelFragCat")
        src = svc.create_item(name="RelSrc")
        tgt = svc.create_item(name="RelTgt")
        svc.place_item_in_category(src.item_id, cat.category_id)
        svc.place_item_in_category(tgt.item_id, cat.category_id)
        svc.relate_items(src.item_id, tgt.item_id, "uses")

        url = reverse("admin:taxomesh_contrib_django_graph_children")
        response = admin_client.get(url, {"parent_uuid": str(cat.category_id), "depth": "1"})  # type: ignore[attr-defined]
        content = response.content.decode()
        assert response.status_code == 200
        assert "uses" in content, "Relation type must appear in fragment"
        assert "RelTgt" in content, "Target item name must appear in fragment"
        assert "taxomesh-rel-toggle" in content, "Rel-toggle button must appear for item with relations"

    def test_linked_url_appears_in_fragment(self, admin_client: object, settings: object) -> None:
        """Items with a matching external_id get a ↗ icon in the children fragment."""
        from django.contrib.auth.models import User  # noqa: PLC0415
        from django.urls import reverse  # noqa: PLC0415

        from taxomesh import TaxomeshService  # noqa: PLC0415
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        user = User.objects.create_user(username="frag-linked-user", password="x")
        repo = DjangoRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.create_category(name="LinkedFragCat")
        item = svc.create_item(name="LinkedFragItem", external_id=str(user.pk))
        svc.place_item_in_category(item.item_id, cat.category_id)

        settings.TAXOMESH_LINKED_MODEL = "auth.User"  # type: ignore[union-attr]

        url = reverse("admin:taxomesh_contrib_django_graph_children")
        response = admin_client.get(url, {"parent_uuid": str(cat.category_id), "depth": "1"})  # type: ignore[attr-defined]
        assert "&#8599;" in response.content.decode(), (
            "Expected ↗ icon-link in children fragment for item with matching external_id"
        )
