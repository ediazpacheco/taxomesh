"""Django admin registrations for taxomesh ORM models."""

from typing import Any, Final, TypedDict
from uuid import UUID

from django import forms
from django.contrib import admin
from django.http import HttpRequest, HttpResponse
from django.urls import path
from django.utils.html import format_html

from taxomesh import TaxomeshService
from taxomesh.adapters.repositories.django_repository import DjangoRepository
from taxomesh.contrib.django.models import (
    CategoryGraphProxy,
    CategoryModel,
    CategoryParentLinkModel,
    ItemModel,
    ItemParentLinkModel,
    ItemRelationLinkModel,
    ItemTagLinkModel,
    TagModel,
    TaxomeshDebugProxy,
)
from taxomesh.domain.constants import ROOT_CATEGORY_NAME
from taxomesh.domain.dag import check_no_cycle
from taxomesh.domain.graph import CategoryNode, TaxomeshGraph
from taxomesh.exceptions import TaxomeshCyclicDependencyError, TaxomeshError, TaxomeshValidationError


class GraphEntry(TypedDict):
    """A single flattened entry for template rendering."""

    depth: int
    kind: str
    name: str
    uuid: str
    enabled: bool
    external_id: str
    linked_url: str | None
    has_descendants: bool
    depth_limited: bool
    initially_collapsed: bool


class RelationEntry(TypedDict):
    """A single outgoing item relation for template rendering."""

    relation_type: str
    target_name: str
    target_uuid: str


TAXOMESH_LINKED_MODEL_SETTING: Final[str] = "TAXOMESH_LINKED_MODEL"
TAXOMESH_CATEGORY_LINKED_MODEL_SETTING: Final[str] = "TAXOMESH_CATEGORY_LINKED_MODEL"
ADMIN_GRAPH_DEFAULT_MAX_DEPTH: Final[int] = 3


def _resolve_linked_url(external_id: str, setting_name: str = TAXOMESH_LINKED_MODEL_SETTING) -> str | None:
    """Resolve a Django admin change URL for a configured linked model instance.

    Reads the given Django settings key, looks up the instance by external_id as its
    primary key, and returns the admin change URL if found.

    Args:
        external_id: The external_id string to use as the linked model PK.
        setting_name: The Django settings key that holds the ``"app_label.ModelName"``
            string. Defaults to ``TAXOMESH_LINKED_MODEL`` (item-linked model).

    Returns:
        The admin change URL string, or None if not resolved.
    """
    if not external_id:
        return None
    try:
        from django.apps import apps as django_apps  # noqa: PLC0415
        from django.conf import settings as django_settings  # noqa: PLC0415
        from django.urls import reverse as dj_reverse  # noqa: PLC0415

        linked_model_label = getattr(django_settings, setting_name, None)
        if not linked_model_label:
            return None
        linked_model = django_apps.get_model(linked_model_label)
        app_label = linked_model._meta.app_label
        model_name = linked_model._meta.model_name
        if not linked_model.objects.filter(pk=external_id).exists():
            return None
        return dj_reverse(f"admin:{app_label}_{model_name}_change", args=[external_id])
    except Exception:
        return None


def _flatten_graph(graph: TaxomeshGraph, max_depth: int = ADMIN_GRAPH_DEFAULT_MAX_DEPTH) -> list[GraphEntry]:
    """Flatten a TaxomeshGraph into a depth-annotated list for template rendering.

    Args:
        graph: The taxonomy graph to flatten.
        max_depth: Maximum category depth to include (0 = unlimited). Items are included
            only when their parent category depth + 1 <= max_depth.
    """
    entries: list[GraphEntry] = []
    depth_limited = max_depth != 0

    def _visit(node: CategoryNode, depth: int) -> None:
        cat = node.category
        is_depth_limited = depth_limited and depth > max_depth
        children_depth_limited = depth_limited and depth + 1 > max_depth
        has_real_children = bool(node.items or node.children)
        initially_collapsed = children_depth_limited and has_real_children
        entries.append(
            GraphEntry(
                depth=depth,
                kind="category",
                name=str(cat),
                uuid=str(cat.category_id),
                enabled=cat.enabled,
                external_id=cat.external_id or "",
                linked_url=None,
                has_descendants=has_real_children,
                depth_limited=is_depth_limited,
                initially_collapsed=initially_collapsed,
            )
        )
        for item in node.items:
            entries.append(
                GraphEntry(
                    depth=depth + 1,
                    kind="item",
                    name=str(item),
                    uuid=str(item.item_id),
                    enabled=item.enabled,
                    external_id=item.external_id or "",
                    linked_url=None,
                    has_descendants=False,
                    depth_limited=children_depth_limited,
                    initially_collapsed=False,
                )
            )
        for child in node.children:
            _visit(child, depth + 1)

    for root in graph.roots:
        _visit(root, 0)
    return entries


# ---------------------------------------------------------------------------
# Shared mixin
# ---------------------------------------------------------------------------


class TaxomeshAdminMixin:
    """Mixin that provides a per-request TaxomeshService factory and shared display helpers."""

    def _make_service(self) -> TaxomeshService:
        """Instantiate a TaxomeshService backed by DjangoRepository.

        Returns:
            A fresh TaxomeshService instance per request.
        """
        return TaxomeshService(repository=DjangoRepository())

    def linked_object_url(self, obj: Any) -> str:
        """Return a ↗ icon-link to the linked admin model if TAXOMESH_LINKED_MODEL is configured.

        Works with any model that has an ``external_id`` attribute (CategoryModel, ItemModel).

        Args:
            obj: The model instance being rendered.

        Returns:
            An HTML anchor string with the ↗ icon, or an empty string if not resolved.
        """
        url = _resolve_linked_url(getattr(obj, "external_id", None) or "")
        if url:
            return format_html('<a href="{}" title="View in admin">&#8599;</a>', url)
        return ""

    linked_object_url.short_description = "↗"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# ItemCategoryAssignmentMixin helpers
# ---------------------------------------------------------------------------


def _get_item_category_ids(obj: Any, external_id_attr: str) -> list[UUID]:
    """Return current category UUIDs assigned to the taxomesh item for obj.

    Args:
        obj: The Django model instance whose PK maps to a taxomesh Item external_id.
        external_id_attr: Name of the attribute on obj that holds the external_id value.

    Returns:
        List of category UUIDs currently assigned to the item; empty if item not found.
    """
    external_id = str(getattr(obj, external_id_attr))
    svc = TaxomeshService(repository=DjangoRepository())
    items = svc.get_items_by_external_id(external_id)
    if not items:
        return []
    item_id = items[0].item_id
    return [link.category_id for link in svc.repository.list_item_parent_links() if link.item_id == item_id]


def _reconcile_categories(obj: Any, form: Any, external_id_attr: str) -> None:
    """Diff selected vs. current categories and apply place/remove via service.

    Args:
        obj: The Django model instance being saved.
        form: The bound admin form (must have ``cleaned_data``).
        external_id_attr: Name of the attribute on obj that holds the external_id value.
    """
    if "categories" not in form.cleaned_data:
        return
    external_id = str(getattr(obj, external_id_attr))
    svc = TaxomeshService(repository=DjangoRepository())
    items = svc.get_items_by_external_id(external_id)
    if not items:
        return
    item_id = items[0].item_id
    current_ids = {link.category_id for link in svc.repository.list_item_parent_links() if link.item_id == item_id}
    selected = {cat.category_id for cat in form.cleaned_data["categories"]}
    for cat_id in selected - current_ids:
        svc.place_item_in_category(item_id, cat_id)
    for cat_id in current_ids - selected:
        svc.remove_item_from_category(item_id, cat_id)


# ---------------------------------------------------------------------------
# Shared list filters (must be defined before ItemCategoryAssignmentMixin)
# ---------------------------------------------------------------------------


class TaxomeshCategoryListFilter(admin.SimpleListFilter):
    """Filter an external model admin list by assigned taxomesh category."""

    title = "taxomesh category"
    parameter_name = "taxomesh_category"

    def lookups(self, request: HttpRequest, model_admin: Any) -> list[tuple[str, str]]:
        """Return available taxomesh categories as filter choices.

        Args:
            request: The current HTTP request.
            model_admin: The model admin instance.

        Returns:
            List of (category_id, name) pairs for all assignable categories.
        """
        try:
            qs = DjangoRepository().assignable_categories_qs()
            return [(str(cat.category_id), cat.name) for cat in qs]
        except Exception:
            return []

    def queryset(self, request: HttpRequest, queryset: Any) -> Any:
        """Filter the queryset to items assigned to the selected taxomesh category.

        Args:
            request: The current HTTP request.
            queryset: The queryset to filter.

        Returns:
            Filtered queryset containing only objects linked to the selected category.
        """
        value = self.value()
        if not value:
            return queryset
        try:
            cat_uuid = UUID(value)
            repo = DjangoRepository()
            svc = TaxomeshService(repository=repo)
            items = svc.list_items(category_id=cat_uuid)
            external_ids = [str(item.external_id) for item in items if item.external_id]
            return queryset.filter(pk__in=external_ids)
        except Exception:
            return queryset


# ---------------------------------------------------------------------------
# ItemCategoryAssignmentMixin
# ---------------------------------------------------------------------------


class ItemCategoryAssignmentMixin(TaxomeshAdminMixin):
    """Admin mixin that adds a 'categories' multi-select field to any ModelAdmin
    whose model PK maps to a taxomesh Item external_id.

    Usage::

        class MyModelAdmin(ItemCategoryAssignmentMixin, admin.ModelAdmin):
            taxomesh_external_id_attr = "id"   # default: "pk"
    """

    taxomesh_external_id_attr: str = "pk"
    list_filter: tuple[Any, ...] = (TaxomeshCategoryListFilter,)

    def get_form(self, request: HttpRequest, obj: Any = None, **kwargs: Any) -> Any:
        """Inject a 'categories' ModelMultipleChoiceField into the admin form.

        Django's ``ModelAdmin._get_form_for_get_fields`` calls ``get_form(fields=None)``
        recursively to discover available fields. The ``fields=None`` sentinel signals
        this discovery path; injection is skipped then to avoid polluting the field
        list with a non-model field.

        For all other call paths (add/change views), the ``categories`` field is
        registered on the base form class as a declared field before passing it to
        ``super().get_form()``. This lets ``modelform_factory`` see it in
        ``declared_fields``, preventing the ``FieldError`` that would occur when the
        field name appears in ``fieldsets`` but not on the model.

        Args:
            request: The current HTTP request.
            obj: The model instance being edited; ``None`` for the add view.
            **kwargs: Passed through to ``super().get_form()``.

        Returns:
            A form class with an additional ``categories`` field populated from
            the enabled, non-root categories in ``DjangoRepository``.
        """
        # fields=None is the _get_form_for_get_fields sentinel — skip injection.
        if "fields" in kwargs and kwargs.get("fields") is None:
            return super().get_form(request, obj, **kwargs)  # type: ignore[misc]

        from django import forms as dj_forms  # noqa: PLC0415
        from django.contrib.admin.widgets import FilteredSelectMultiple  # noqa: PLC0415

        qs = DjangoRepository().assignable_categories_qs()
        cat_field = dj_forms.ModelMultipleChoiceField(
            queryset=qs,
            required=False,
            widget=FilteredSelectMultiple("categories", is_stacked=False),
            label="Categories",
        )

        # Register categories on the base form as a declared field so that
        # modelform_factory does not raise FieldError when 'categories' appears
        # in fieldsets (which become the fields= argument to modelform_factory).
        base_form: Any = kwargs.pop("form", None) or self.form
        kwargs["form"] = type(base_form.__name__, (base_form,), {"categories": cat_field})

        form_class = super().get_form(request, obj, **kwargs)  # type: ignore[misc]

        if obj is not None:
            initial_ids = _get_item_category_ids(obj, self.taxomesh_external_id_attr)
            if initial_ids:
                form_class.base_fields["categories"].initial = CategoryModel.objects.filter(  # type: ignore[index]
                    category_id__in=initial_ids
                )

        return form_class

    def save_model(self, request: HttpRequest, obj: Any, form: Any, change: bool) -> None:
        """Save the model and reconcile category assignments via the service layer.

        Calls ``super().save_model()`` first (which persists the model instance),
        then diffs the selected categories against the current assignments and
        applies ``place_item_in_category`` / ``remove_item_from_category`` as needed.

        Args:
            request: The current HTTP request.
            obj: The model instance being saved.
            form: The bound admin form with ``cleaned_data``.
            change: ``True`` if updating an existing record; ``False`` if creating.
        """
        super().save_model(request, obj, form, change)  # type: ignore[misc]
        _reconcile_categories(obj, form, self.taxomesh_external_id_attr)


# ---------------------------------------------------------------------------
# CategoryParentLink Form (cycle / self-reference validation via clean())
# ---------------------------------------------------------------------------


class CategoryParentLinkForm(forms.ModelForm):  # type: ignore[type-arg]
    """ModelForm for CategoryParentLinkModel that enforces DAG integrity in clean().

    Django's inline formset save flow calls ``form.instance.save()`` directly,
    bypassing ``InlineModelAdmin.save_model()``.  This form's ``clean()`` is the
    only hook that runs before the ORM write, so all cycle and self-reference
    checks live here.
    """

    class Meta:
        model = CategoryParentLinkModel
        fields = "__all__"

    def clean(self) -> dict[str, Any]:
        """Validate that the proposed parent link does not create a cycle or self-reference.

        Raises:
            forms.ValidationError: If category == parent_category (self-reference), or
                if the link would introduce a cycle in the category DAG.
        """
        cleaned_data: dict[str, Any] = super().clean()
        category = cleaned_data.get("category")
        parent_category = cleaned_data.get("parent_category")
        if category and parent_category:
            cat_id = category.category_id
            parent_id = parent_category.category_id
            if cat_id == parent_id:
                raise forms.ValidationError("A category cannot be its own parent.")
            try:
                check_no_cycle(cat_id, parent_id, DjangoRepository().list_category_parent_links())
            except TaxomeshCyclicDependencyError as exc:
                raise forms.ValidationError(str(exc)) from exc
        return cleaned_data


# ---------------------------------------------------------------------------
# CategoryParentLink Inline
# ---------------------------------------------------------------------------


class CategoryParentLinkInline(TaxomeshAdminMixin, admin.TabularInline):
    """Inline for managing CategoryParentLink records on the Category admin page."""

    model = CategoryParentLinkModel
    form = CategoryParentLinkForm
    extra = 0
    fk_name = "category"

    def save_model(
        self,
        request: HttpRequest,
        obj: CategoryParentLinkModel,
        form: forms.BaseModelForm,
        change: bool,
    ) -> None:
        """Persist the parent link via the service layer.

        Args:
            request: The current HTTP request.
            obj: The CategoryParentLinkModel instance being saved.
            form: The bound ModelForm.
            change: True if updating an existing record; False if creating.
        """
        svc = self._make_service()
        try:
            svc.add_category_parent(
                category_id=obj.category_id,
                parent_id=obj.parent_category_id,
                sort_index=obj.sort_index,
            )
        except TaxomeshCyclicDependencyError as exc:
            from django.contrib import messages  # noqa: PLC0415

            self.message_user(request, str(exc), level=messages.ERROR)

    def delete_model(self, request: HttpRequest, obj: CategoryParentLinkModel) -> None:
        """Remove the parent link via the service layer.

        Args:
            request: The current HTTP request.
            obj: The CategoryParentLinkModel instance being deleted.
        """
        svc = self._make_service()
        svc.remove_category_parent(
            category_id=obj.category_id,
            parent_id=obj.parent_category_id,
        )

    def formfield_for_foreignkey(  # type: ignore[override]
        self,
        db_field: object,
        request: HttpRequest,
        **kwargs: object,
    ) -> object:
        """Exclude the root category from the parent_category FK dropdown.

        Args:
            db_field: The ForeignKey field descriptor.
            request: The current HTTP request.
            **kwargs: Passed through to super().
        """
        if getattr(db_field, "name", None) == "parent_category":
            kwargs["queryset"] = CategoryModel.objects.exclude(name=ROOT_CATEGORY_NAME)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Item inlines
# ---------------------------------------------------------------------------


class ItemParentLinkInline(TaxomeshAdminMixin, admin.TabularInline):
    """Inline for managing ItemParentLink records on the Item admin page."""

    model = ItemParentLinkModel
    extra = 0

    def save_model(
        self,
        request: HttpRequest,
        obj: ItemParentLinkModel,
        form: forms.BaseModelForm,
        change: bool,
    ) -> None:
        """Persist the item-category placement via the service layer.

        Args:
            request: The current HTTP request.
            obj: The ItemParentLinkModel instance being saved.
            form: The bound ModelForm.
            change: True if updating an existing record; False if creating.
        """
        svc = self._make_service()
        try:
            svc.place_item_in_category(obj.item_id, obj.category_id, obj.sort_index)
        except TaxomeshError as exc:
            from django.contrib import messages  # noqa: PLC0415

            self.message_user(request, str(exc), level=messages.ERROR)

    def delete_model(self, request: HttpRequest, obj: ItemParentLinkModel) -> None:
        """Remove the item-category placement via the service layer.

        Args:
            request: The current HTTP request.
            obj: The ItemParentLinkModel instance being deleted.
        """
        svc = self._make_service()
        svc.remove_item_from_category(obj.item_id, obj.category_id)


class ItemTagLinkInline(TaxomeshAdminMixin, admin.TabularInline):
    """Inline for managing ItemTagLink records on the Item admin page."""

    model = ItemTagLinkModel
    extra = 0

    def save_model(
        self,
        request: HttpRequest,
        obj: ItemTagLinkModel,
        form: forms.BaseModelForm,
        change: bool,
    ) -> None:
        """Persist the tag assignment via the service layer.

        Args:
            request: The current HTTP request.
            obj: The ItemTagLinkModel instance being saved.
            form: The bound ModelForm.
            change: True if updating an existing record; False if creating.
        """
        svc = self._make_service()
        try:
            svc.assign_tag(obj.tag_id, obj.item_id)
        except TaxomeshError as exc:
            from django.contrib import messages  # noqa: PLC0415

            self.message_user(request, str(exc), level=messages.ERROR)

    def delete_model(self, request: HttpRequest, obj: ItemTagLinkModel) -> None:
        """Remove the tag assignment via the service layer.

        Args:
            request: The current HTTP request.
            obj: The ItemTagLinkModel instance being deleted.
        """
        svc = self._make_service()
        svc.remove_tag(obj.tag_id, obj.item_id)


# ---------------------------------------------------------------------------
# Shared filters
# ---------------------------------------------------------------------------


class HasSlugFilter(admin.SimpleListFilter):
    """Filter by slug presence: 'Has slug' / 'No slug'."""

    title = "has slug"
    parameter_name = "has_slug"

    def lookups(self, request: HttpRequest, model_admin: object) -> list[tuple[str, str]]:
        """Return the filter options."""
        return [("yes", "Has slug"), ("no", "No slug")]

    def queryset(self, request: HttpRequest, queryset: object) -> object:
        """Apply the filter to the queryset."""
        if self.value() == "yes":
            return queryset.exclude(slug="")  # type: ignore[union-attr]
        if self.value() == "no":
            return queryset.filter(slug="")  # type: ignore[union-attr]
        return queryset


class HasLinkedObjectListFilter(admin.SimpleListFilter):
    """Filter categories by whether their external_id field is non-empty."""

    title = "linked object"
    parameter_name = "has_linked_object"

    def lookups(self, request: HttpRequest, model_admin: Any) -> list[tuple[str, str]]:
        """Return the filter choices.

        Args:
            request: The current HTTP request.
            model_admin: The model admin instance.

        Returns:
            List of (value, display_label) pairs.
        """
        return [("yes", "Has linked object"), ("no", "No linked object")]

    def queryset(self, request: HttpRequest, queryset: Any) -> Any:
        """Apply the filter to the queryset.

        Args:
            request: The current HTTP request.
            queryset: The queryset to filter.

        Returns:
            Filtered queryset, or the original queryset if no value is selected.
        """
        if self.value() == "yes":
            return queryset.exclude(external_id="")
        if self.value() == "no":
            return queryset.filter(external_id="")
        return queryset


# ---------------------------------------------------------------------------
# CategoryModelAdmin
# ---------------------------------------------------------------------------


@admin.register(CategoryModel)
class CategoryModelAdmin(TaxomeshAdminMixin, admin.ModelAdmin):  # type: ignore[type-arg]
    """Admin view for Category records."""

    list_display = ("category_id", "name", "slug", "enabled", "external_id", "linked_object_url")
    search_fields = ("name", "slug", "category_id")
    list_filter = ("enabled", HasSlugFilter, HasLinkedObjectListFilter)
    fields = ("name", "slug", "description", "enabled", "external_id", "metadata")
    readonly_fields = ("linked_object_url",)
    inlines = [CategoryParentLinkInline]

    def linked_object_url(self, obj: Any) -> str:
        """Return a link to a linked admin model for this category.

        Checks TAXOMESH_CATEGORY_LINKED_MODEL first; falls back to TAXOMESH_LINKED_MODEL.

        Args:
            obj: The CategoryModel instance being rendered.

        Returns:
            An HTML anchor string with the arrow icon, or an empty string if not resolved.
        """
        external_id = getattr(obj, "external_id", None) or ""
        url = _resolve_linked_url(external_id, TAXOMESH_CATEGORY_LINKED_MODEL_SETTING) or _resolve_linked_url(
            external_id
        )
        if url:
            return format_html('<a href="{}" title="View in admin">&#8599;</a>', url)
        return ""

    linked_object_url.short_description = "↗"  # type: ignore[attr-defined]

    def get_queryset(self, request: HttpRequest) -> object:  # type: ignore[override]
        """Return the base queryset with the internal root category excluded.

        Args:
            request: The current HTTP request.
        """
        return super().get_queryset(request).exclude(name=ROOT_CATEGORY_NAME)  # type: ignore[union-attr]

    def get_urls(self) -> list:  # type: ignore[type-arg]
        """Add the taxonomy graph view URL to the admin URL patterns."""
        urls = super().get_urls()
        custom = [
            path(
                "graph/",
                self.admin_site.admin_view(self.graph_view),
                name="taxomesh_contrib_django_graph",
            )
        ]
        return custom + urls

    def graph_view(self, request: HttpRequest) -> HttpResponse:
        """Render the taxonomy graph as a styled HTML tree."""
        from django.template.response import TemplateResponse  # noqa: PLC0415

        error: str | None = None
        entries: list[GraphEntry] = []
        has_entries = False
        item_relations: dict[str, list[RelationEntry]] = {}
        try:
            repo = DjangoRepository()
            svc = TaxomeshService(repository=repo)
            graph = svc.get_graph()
            entries = _flatten_graph(graph)
            has_entries = bool(graph.roots)
            for entry in entries:
                if entry["kind"] != "item":
                    continue
                item_uuid_str = entry["uuid"]
                try:
                    links = svc.list_item_relations(UUID(item_uuid_str))
                    if links:
                        rels: list[RelationEntry] = []
                        for link in links:
                            try:
                                target = svc.get_item(link.target_item_id)
                                target_name = target.name if target is not None else str(link.target_item_id)
                            except Exception:
                                target_name = str(link.target_item_id)
                            rels.append(
                                RelationEntry(
                                    relation_type=link.relation_type,
                                    target_name=target_name,
                                    target_uuid=str(link.target_item_id),
                                )
                            )
                        item_relations[item_uuid_str] = rels
                except Exception:
                    pass
        except TaxomeshError as exc:
            error = str(exc)

        # Resolve linked_url for each entry with a non-empty external_id
        for entry in entries:
            entry["linked_url"] = _resolve_linked_url(entry.get("external_id", "") or "")

        context = {
            **self.admin_site.each_context(request),
            "title": "Taxonomy Graph",
            "entries": entries,
            "has_entries": has_entries,
            "error": error,
            "item_relations": item_relations,
            "opts": self.model._meta,
        }
        return TemplateResponse(request, "admin/taxomesh_contrib_django/graph.html", context)

    def save_model(
        self,
        request: HttpRequest,
        obj: CategoryModel,
        form: object,
        change: bool,
    ) -> None:
        """Route category create/update through the service layer.

        Args:
            request: The current HTTP request.
            obj: The CategoryModel instance being saved.
            form: The bound ModelForm (unused; required by Django's interface).
            change: True if updating an existing record; False if creating.
        """
        from django.contrib import messages  # noqa: PLC0415

        svc = self._make_service()
        try:
            if not change:
                domain_cat = svc.create_category(
                    name=obj.name,
                    description=obj.description,
                    slug=obj.slug,
                    metadata=obj.metadata,
                    external_id=obj.external_id,
                )
                # Sync obj so Django can use it as a FK target for inline saves.
                # Without this, Django 4.0+ raises ValueError ("unsaved related object")
                # because obj was never passed through obj.save().
                obj.category_id = domain_cat.category_id
                obj._state.adding = False  # type: ignore[union-attr]
            else:
                svc.update_category(
                    category_id=obj.category_id,
                    name=obj.name,
                    description=obj.description,
                    slug=obj.slug,
                    metadata=obj.metadata,
                    external_id=obj.external_id,
                )
        except TaxomeshValidationError as exc:
            self.message_user(request, str(exc), level=messages.ERROR)

    def delete_model(self, request: HttpRequest, obj: CategoryModel) -> None:
        """Route category deletion through the service layer.

        Args:
            request: The current HTTP request.
            obj: The CategoryModel instance being deleted.
        """
        from django.contrib import messages  # noqa: PLC0415

        svc = self._make_service()
        try:
            svc.delete_category(obj.category_id)
        except TaxomeshError as exc:
            self.message_user(request, str(exc), level=messages.ERROR)

    def delete_queryset(self, request: HttpRequest, queryset: object) -> None:
        """Route bulk category deletion through the service layer.

        Args:
            request: The current HTTP request.
            queryset: An iterable of CategoryModel instances to delete.
        """
        from django.contrib import messages  # noqa: PLC0415

        svc = self._make_service()
        for obj in queryset:  # type: ignore[union-attr]
            try:
                svc.delete_category(obj.category_id)
            except TaxomeshError as exc:
                self.message_user(request, str(exc), level=messages.ERROR)


# ---------------------------------------------------------------------------
# ItemRelationLink Form (self-relation validation)
# ---------------------------------------------------------------------------


class ItemRelationLinkForm(forms.ModelForm):  # type: ignore[type-arg]
    """ModelForm for ItemRelationLinkModel that rejects self-relations in clean()."""

    class Meta:
        model = ItemRelationLinkModel
        fields = "__all__"

    def clean(self) -> dict[str, Any]:
        """Reject self-relations (source == target).

        Raises:
            forms.ValidationError: If source_item == target_item.
        """
        cleaned_data: dict[str, Any] = super().clean()
        source = cleaned_data.get("source_item")
        target = cleaned_data.get("target_item")
        if source and target and source.item_id == target.item_id:
            raise forms.ValidationError("An item cannot be related to itself.")
        relation_type = cleaned_data.get("relation_type", "")
        if not str(relation_type).strip():
            raise forms.ValidationError("Relation type must not be empty.")
        return cleaned_data


# ---------------------------------------------------------------------------
# Outgoing / Incoming relation inlines
# ---------------------------------------------------------------------------


class OutgoingRelationInline(TaxomeshAdminMixin, admin.TabularInline):
    """Editable inline for outgoing item relations (source_item == current item)."""

    model = ItemRelationLinkModel
    form = ItemRelationLinkForm
    fk_name = "source_item"
    extra = 0

    def save_model(
        self,
        request: HttpRequest,
        obj: ItemRelationLinkModel,
        form: forms.BaseModelForm,
        change: bool,
    ) -> None:
        """Route relation create/update through the service layer."""
        svc = self._make_service()
        try:
            svc.relate_items(
                obj.source_item_id,
                obj.target_item_id,
                obj.relation_type,
                sort_index=obj.sort_index,
                metadata=obj.metadata,
            )
        except TaxomeshError as exc:
            from django.contrib import messages  # noqa: PLC0415

            self.message_user(request, str(exc), level=messages.ERROR)

    def delete_model(self, request: HttpRequest, obj: ItemRelationLinkModel) -> None:
        """Remove the relation via the service layer."""
        svc = self._make_service()
        try:
            svc.remove_item_relation(obj.source_item_id, obj.target_item_id, obj.relation_type)
        except TaxomeshError as exc:
            from django.contrib import messages  # noqa: PLC0415

            self.message_user(request, str(exc), level=messages.ERROR)


class IncomingRelationInline(admin.TabularInline):
    """Read-only inline for incoming item relations (target_item == current item)."""

    model = ItemRelationLinkModel
    fk_name = "target_item"
    extra = 0

    def has_add_permission(self, request: HttpRequest, obj: object = None) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: object = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: object = None) -> bool:
        return False


# ---------------------------------------------------------------------------
# ItemModelAdmin
# ---------------------------------------------------------------------------


@admin.register(ItemModel)
class ItemModelAdmin(TaxomeshAdminMixin, admin.ModelAdmin):  # type: ignore[type-arg]
    """Admin view for Item records."""

    list_display = ("name", "external_id", "slug", "enabled", "linked_object_url")
    search_fields = ("name", "external_id", "slug", "item_id")
    list_filter = ("enabled", HasSlugFilter)
    fields = ("name", "external_id", "slug", "enabled", "metadata", "linked_object_url")
    readonly_fields = ("linked_object_url",)
    inlines = [ItemParentLinkInline, ItemTagLinkInline, OutgoingRelationInline, IncomingRelationInline]

    def save_model(
        self,
        request: HttpRequest,
        obj: ItemModel,
        form: object,
        change: bool,
    ) -> None:
        """Route item create/update through the service layer.

        Args:
            request: The current HTTP request.
            obj: The ItemModel instance being saved.
            form: The bound ModelForm (unused; required by Django's interface).
            change: True if updating an existing record; False if creating.
        """
        from django.contrib import messages  # noqa: PLC0415

        svc = self._make_service()
        try:
            if not change:
                domain_item = svc.create_item(
                    name=obj.name,
                    external_id=obj.external_id,
                    slug=obj.slug,
                    metadata=obj.metadata,
                )
                # Sync obj so Django can use it as a FK target for inline saves.
                obj.item_id = domain_item.item_id
                obj._state.adding = False  # type: ignore[union-attr]
            else:
                svc.update_item(
                    item_id=obj.item_id,
                    enabled=obj.enabled,
                    slug=obj.slug,
                    name=obj.name,
                    metadata=obj.metadata,
                )
        except TaxomeshValidationError as exc:
            self.message_user(request, str(exc), level=messages.ERROR)

    def delete_model(self, request: HttpRequest, obj: ItemModel) -> None:
        """Route item deletion through the service layer.

        Args:
            request: The current HTTP request.
            obj: The ItemModel instance being deleted.
        """
        from django.contrib import messages  # noqa: PLC0415

        svc = self._make_service()
        try:
            svc.delete_item(obj.item_id)
        except TaxomeshError as exc:
            self.message_user(request, str(exc), level=messages.ERROR)

    def delete_queryset(self, request: HttpRequest, queryset: object) -> None:
        """Route bulk item deletion through the service layer.

        Args:
            request: The current HTTP request.
            queryset: An iterable of ItemModel instances to delete.
        """
        from django.contrib import messages  # noqa: PLC0415

        svc = self._make_service()
        for obj in queryset:  # type: ignore[union-attr]
            try:
                svc.delete_item(obj.item_id)
            except TaxomeshError as exc:
                self.message_user(request, str(exc), level=messages.ERROR)

    def save_formset(self, request: HttpRequest, form: Any, formset: Any, change: bool) -> None:
        """Route OutgoingRelationInline saves through the service layer.

        Django's default save_formset calls formset.save() directly, bypassing the
        service layer. This override intercepts the outgoing relation inline so that
        relate_items / remove_item_relation are called instead.

        All other inline formsets fall through to the default ORM path.

        Args:
            request: The current HTTP request.
            form: The parent ItemModel form.
            formset: The inline formset being saved.
            change: True if the parent object is being updated; False if created.
        """
        from django.contrib import messages  # noqa: PLC0415

        fk_name = getattr(getattr(formset, "fk", None), "name", None)
        if formset.model is ItemRelationLinkModel and fk_name == "source_item":
            svc = self._make_service()
            instances = formset.save(commit=False)
            for obj in instances:
                try:
                    svc.relate_items(
                        obj.source_item_id,
                        obj.target_item_id,
                        obj.relation_type,
                        sort_index=obj.sort_index,
                        metadata=obj.metadata or {},
                    )
                except TaxomeshError as exc:
                    self.message_user(request, str(exc), level=messages.ERROR)
            for obj in formset.deleted_objects:
                try:
                    svc.remove_item_relation(obj.source_item_id, obj.target_item_id, obj.relation_type)
                except TaxomeshError as exc:
                    self.message_user(request, str(exc), level=messages.ERROR)
        else:
            super().save_formset(request, form, formset, change)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TagModelAdmin
# ---------------------------------------------------------------------------


@admin.register(TagModel)
class TagModelAdmin(TaxomeshAdminMixin, admin.ModelAdmin):  # type: ignore[type-arg]
    """Admin view for Tag records."""

    list_display = ("tag_id", "name")
    search_fields = ("name",)

    def save_model(
        self,
        request: HttpRequest,
        obj: TagModel,
        form: object,
        change: bool,
    ) -> None:
        """Route tag create/update through the service layer.

        Args:
            request: The current HTTP request.
            obj: The TagModel instance being saved.
            form: The bound ModelForm (unused; required by Django's interface).
            change: True if updating an existing record; False if creating.
        """
        from django.contrib import messages  # noqa: PLC0415

        svc = self._make_service()
        try:
            if not change:
                svc.create_tag(name=obj.name)
            else:
                svc.update_tag(tag_id=obj.tag_id, name=obj.name)
        except TaxomeshValidationError as exc:
            self.message_user(request, str(exc), level=messages.ERROR)

    def delete_model(self, request: HttpRequest, obj: TagModel) -> None:
        """Route tag deletion through the service layer.

        Args:
            request: The current HTTP request.
            obj: The TagModel instance being deleted.
        """
        from django.contrib import messages  # noqa: PLC0415

        svc = self._make_service()
        try:
            svc.delete_tag(obj.tag_id)
        except TaxomeshError as exc:
            self.message_user(request, str(exc), level=messages.ERROR)

    def delete_queryset(self, request: HttpRequest, queryset: object) -> None:
        """Route bulk tag deletion through the service layer.

        Args:
            request: The current HTTP request.
            queryset: An iterable of TagModel instances to delete.
        """
        from django.contrib import messages  # noqa: PLC0415

        svc = self._make_service()
        for obj in queryset:  # type: ignore[union-attr]
            try:
                svc.delete_tag(obj.tag_id)
            except TaxomeshError as exc:
                self.message_user(request, str(exc), level=messages.ERROR)


# ---------------------------------------------------------------------------
# CategoryGraphProxyAdmin
# ---------------------------------------------------------------------------


@admin.register(CategoryGraphProxy)
class CategoryGraphProxyAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Proxy admin that surfaces the Graph link on the main admin index."""

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Deny add permission — this is a read-only proxy."""
        return False

    def has_change_permission(self, request: HttpRequest, obj: object = None) -> bool:
        """Deny change permission — this is a read-only proxy."""
        return False

    def has_delete_permission(self, request: HttpRequest, obj: object = None) -> bool:
        """Deny delete permission — this is a read-only proxy."""
        return False

    def has_view_permission(self, request: HttpRequest, obj: object = None) -> bool:
        """Allow view permission for staff users."""
        return request.user.is_staff

    def changelist_view(self, request: HttpRequest, extra_context: object = None) -> HttpResponse:
        """Redirect changelist to the graph view."""
        from django.http import HttpResponseRedirect  # noqa: PLC0415
        from django.urls import reverse  # noqa: PLC0415

        return HttpResponseRedirect(reverse("admin:taxomesh_contrib_django_graph"))


# ---------------------------------------------------------------------------
# TaxomeshDebugProxyAdmin
# ---------------------------------------------------------------------------


@admin.register(TaxomeshDebugProxy)
class TaxomeshDebugProxyAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Admin page that renders taxomesh diagnostic information."""

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Deny add permission — debug page is read-only."""
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        """Deny change permission — debug page is read-only."""
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        """Deny delete permission — debug page is read-only."""
        return False

    def has_view_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        """Allow staff users to view the debug page."""
        return request.user.is_staff

    def changelist_view(self, request: HttpRequest, extra_context: dict[str, Any] | None = None) -> HttpResponse:
        """Render the taxomesh diagnostic page.

        Args:
            request: The current HTTP request.
            extra_context: Optional extra template context.

        Returns:
            TemplateResponse rendering debug info from TaxomeshService.get_debug().
        """
        from django.template.response import TemplateResponse  # noqa: PLC0415

        debug_info: dict[str, Any] = {}
        try:
            svc = TaxomeshService(repository=DjangoRepository())
            debug_info = svc.get_debug()
        except Exception as exc:
            debug_info = {"error": str(exc)}

        context = {
            **self.admin_site.each_context(request),
            "title": "Taxomesh Debug",
            "debug_info": debug_info,
            "opts": self.model._meta,
        }
        return TemplateResponse(request, "admin/taxomesh_contrib_django/debug.html", context)
