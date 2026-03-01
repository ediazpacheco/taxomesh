"""Django admin registrations for taxomesh ORM models."""

from typing import Any
from uuid import UUID

from django import forms
from django.contrib import admin
from django.http import HttpRequest, HttpResponse
from django.urls import path

from taxomesh import TaxomeshService
from taxomesh.adapters.repositories.django_repository import DjangoRepository
from taxomesh.contrib.django.models import (
    CategoryGraphProxy,
    CategoryModel,
    CategoryParentLinkModel,
    ItemModel,
    ItemParentLinkModel,
    ItemTagLinkModel,
    TagModel,
)
from taxomesh.domain.constants import ROOT_CATEGORY_NAME
from taxomesh.domain.dag import check_no_cycle
from taxomesh.domain.graph import CategoryNode, TaxomeshGraph
from taxomesh.exceptions import TaxomeshCyclicDependencyError, TaxomeshError, TaxomeshValidationError


def _flatten_graph(graph: TaxomeshGraph) -> list[dict[str, object]]:
    """Flatten a TaxomeshGraph into a depth-annotated list for template rendering."""
    entries: list[dict[str, object]] = []

    def _visit(node: CategoryNode, depth: int) -> None:
        cat = node.category
        entries.append(
            {
                "depth": depth,
                "indent_em": depth * 1.5,
                "kind": "category",
                "name": cat.name,
                "uuid": str(cat.category_id),
                "slug": cat.slug or None,
                "enabled": cat.enabled,
                "external_id": cat.external_id if cat.external_id else None,
            }
        )
        for item in node.items:
            item_depth = depth + 1
            entries.append(
                {
                    "depth": item_depth,
                    "indent_em": item_depth * 1.5,
                    "kind": "item",
                    "name": str(item.external_id),
                    "uuid": str(item.item_id),
                    "slug": item.slug or None,
                    "enabled": item.enabled,
                    "external_id": None,
                }
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
    """Mixin that provides a per-request TaxomeshService factory for admin classes."""

    def _make_service(self) -> TaxomeshService:
        """Instantiate a TaxomeshService backed by DjangoRepository.

        Returns:
            A fresh TaxomeshService instance per request.
        """
        return TaxomeshService(repository=DjangoRepository())


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


# ---------------------------------------------------------------------------
# CategoryModelAdmin
# ---------------------------------------------------------------------------


@admin.register(CategoryModel)
class CategoryModelAdmin(TaxomeshAdminMixin, admin.ModelAdmin):  # type: ignore[type-arg]
    """Admin view for Category records."""

    list_display = ("category_id", "name", "slug", "enabled", "external_id")
    search_fields = ("name", "slug")
    list_filter = ("enabled", HasSlugFilter)
    fields = ("name", "slug", "description", "enabled", "external_id")
    inlines = [CategoryParentLinkInline]

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
        entries: list[dict[str, object]] = []
        has_entries = False
        try:
            repo = DjangoRepository()
            svc = TaxomeshService(repository=repo)
            graph = svc.get_graph()
            entries = _flatten_graph(graph)
            has_entries = bool(graph.roots)
        except TaxomeshError as exc:
            error = str(exc)

        context = {
            **self.admin_site.each_context(request),
            "title": "Taxonomy Graph",
            "entries": entries,
            "has_entries": has_entries,
            "error": error,
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
# ItemModelAdmin
# ---------------------------------------------------------------------------


@admin.register(ItemModel)
class ItemModelAdmin(TaxomeshAdminMixin, admin.ModelAdmin):  # type: ignore[type-arg]
    """Admin view for Item records."""

    list_display = ("name", "external_id", "slug", "enabled")
    search_fields = ("name", "external_id", "slug")
    list_filter = ("enabled", HasSlugFilter)
    fields = ("name", "external_id", "slug", "enabled")
    inlines = [ItemParentLinkInline, ItemTagLinkInline]

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
                domain_item = svc.create_item(name=obj.name, external_id=obj.external_id, slug=obj.slug)
                # Sync obj so Django can use it as a FK target for inline saves.
                obj.item_id = domain_item.item_id
                obj._state.adding = False  # type: ignore[union-attr]
            else:
                svc.update_item(item_id=obj.item_id, enabled=obj.enabled, slug=obj.slug, name=obj.name)
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
