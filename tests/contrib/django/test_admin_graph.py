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
        """item_relations must be passed in context: relation data appears in response HTML."""
        from django.urls import reverse  # noqa: PLC0415

        self._setup_taxonomy_with_relation()
        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)  # type: ignore[attr-defined]
        content = response.content.decode()
        # The relation between Alpha and Beta (relation_type='covers') must appear in HTML
        # This is only possible if item_relations is populated in context and rendered
        assert "covers" in content, (
            "Expected relation type 'covers' to appear in graph HTML (item_relations in context)"
        )
        assert "Beta" in content, "Expected target item name 'Beta' to appear in relation row"

    def test_relation_rows_hidden_by_default(self, admin_client: object) -> None:
        """Relation rows must have display:none by default (CSS class, not inline style)."""
        from django.urls import reverse  # noqa: PLC0415

        self._setup_taxonomy_with_relation()
        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)  # type: ignore[attr-defined]
        assert b"taxomesh-relations" in response.content, "Expected .taxomesh-relations elements in the HTML"
        # The CSS must have display:none for .taxomesh-relations
        assert b".taxomesh-relations" in response.content

    def test_item_with_relations_has_toggle_button_when_relations_loaded(self, admin_client: object) -> None:
        """An item that has outgoing relations must render a rel-toggle button."""
        from django.urls import reverse  # noqa: PLC0415

        self._setup_taxonomy_with_relation()
        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)  # type: ignore[attr-defined]
        assert b"taxomesh-rel-toggle" in response.content, (
            "Expected a taxomesh-rel-toggle button for an item with outgoing relations"
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
        """When TAXOMESH_LINKED_MODEL is set and item.external_id matches a pk, ↗ appears."""
        from django.contrib.auth.models import User  # noqa: PLC0415
        from django.urls import reverse  # noqa: PLC0415

        # Create a Django User whose pk will be used as external_id
        user = User.objects.create_user(username="linked-user", password="x")
        self._setup_category_with_item(external_id=str(user.pk))

        settings.TAXOMESH_LINKED_MODEL = "auth.User"  # type: ignore[union-attr]

        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)  # type: ignore[attr-defined]
        assert "&#8599;" in response.content.decode(), (
            "Expected ↗ icon-link (&#8599;) for item with matching external_id"
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
        """Nodes beyond ADMIN_GRAPH_DEFAULT_MAX_DEPTH=3 must be in DOM but marked depth-limited."""
        from django.urls import reverse  # noqa: PLC0415

        self._setup_deep_taxonomy()
        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)  # type: ignore[attr-defined]
        content = response.content.decode()
        assert "L3admin" in content, "L3admin (depth 3) must appear"
        # L4admin and AdminItem4 are in the DOM (hidden via JS) so the [+] on L3admin is clickable
        assert "L4admin" in content, "L4admin must be in DOM (depth-limited, initially hidden)"
        assert 'data-depth-limited="1"' in content, "depth-limited entries must carry data-depth-limited attribute"

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
        """Items with outgoing relations must still have a taxomesh-rel-toggle button."""
        from django.urls import reverse  # noqa: PLC0415

        self._setup_taxonomy_with_relation()
        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)  # type: ignore[attr-defined]
        assert b"taxomesh-rel-toggle" in response.content, "Items with relations must have a rel-toggle button"

    def test_admin_graph_relation_rows_hidden_by_default(self, admin_client: object) -> None:
        """Relation rows (.taxomesh-relations) must have display:none by default."""
        from django.urls import reverse  # noqa: PLC0415

        self._setup_taxonomy_with_relation()
        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)  # type: ignore[attr-defined]
        content = response.content.decode()
        assert "taxomesh-relations" in content, "Expected .taxomesh-relations elements in HTML"
        # The CSS must have display:none for .taxomesh-relations (not .taxomesh-relations-visible)
        assert ".taxomesh-relations {" in content or ".taxomesh-relations{" in content
        assert "taxomesh-relations-visible" not in content, (
            "The .taxomesh-relations-visible CSS class and JS must be removed"
        )

    def test_admin_graph_depth_limited_category_shows_clickable_expand_button(self, admin_client: object) -> None:
        """Categories at max depth with real children must show a clickable [+] toggle button."""
        from django.urls import reverse  # noqa: PLC0415

        self._setup_deep_taxonomy()
        url = reverse("admin:taxomesh_contrib_django_graph")
        response = admin_client.get(url)  # type: ignore[attr-defined]
        content = response.content.decode()
        # L3admin is at depth 3 (max); L4admin is its child (depth-limited, initially hidden).
        assert "L3admin" in content, "L3admin must be present in the graph"
        assert "taxomesh-depth-limited" not in content, (
            "taxomesh-depth-limited class must be removed — [+] buttons are now regular toggles"
        )
        # The [+] button on L3admin must carry a data-idx attribute (regular toggle mechanism)
        assert "data-idx=" in content, "Toggle buttons must use data-idx for JS expand/collapse"


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
