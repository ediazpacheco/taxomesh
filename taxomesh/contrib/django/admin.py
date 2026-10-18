"""The Django admin of taxomesh.

It has the admin of each model, with its forms, inlines and filters; the graph page and the debug
page; and the mixins for the admin of your own models.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, Final
from uuid import UUID

from django import forms
from django.apps import apps
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.exceptions import NotRegistered
from django.contrib.admin.utils import flatten_fieldsets
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.auth import get_permission_codename
from django.db import models
from django.forms import ModelChoiceField
from django.forms.renderers import BaseRenderer
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse
from django.template.loader import render_to_string
from django.template.response import TemplateResponse
from django.urls import URLPattern, path, reverse
from django.utils.html import format_html
from django.utils.safestring import SafeString

from taxomesh import TaxomeshService
from taxomesh.adapters.repositories.django_repository import DjangoRepository
from taxomesh.contrib.api.errors import GENERIC_SERVER_ERROR_DETAIL, to_tuple
from taxomesh.contrib.django.graph_sort import DEFAULT_SORT_MODE, DEFAULT_SORT_MODES, SortMode, SortModeFn
from taxomesh.contrib.django.graph_types import GraphEntry, RelationEntry
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
from taxomesh.contrib.django.widgets import JsonEditorFormField, JsonEditorWidget, TaxomeshLinkedFKWidget
from taxomesh.domain.constants import ROOT_CATEGORY_NAME
from taxomesh.domain.dag import check_no_cycle
from taxomesh.domain.models import Category, Item
from taxomesh.exceptions import (
    TaxomeshCyclicDependencyError,
    TaxomeshError,
    TaxomeshValidationError,
)

logger = logging.getLogger(__name__)

# django-stubs types the admin and form classes by their models, but Django cannot subscript
# them at run time. The type checker reads each base below with its models; the running code
# reads the bare class. A mixin's base names ``Any``, since it serves the admin of any model,
# and is ``object`` at run time, where the ``ModelAdmin`` or the inline comes after it.
if TYPE_CHECKING:
    # The type of what ModelAdmin.get_fields returns, which only django-stubs defines.
    from django.contrib.admin.options import _FieldGroups

    _ModelAdminMixinBase = admin.ModelAdmin[Any]
    _LinkInlineMixinBase = admin.TabularInline[Any, Any]
    _CategoryAdminBase = admin.ModelAdmin[CategoryModel]
    _ItemAdminBase = admin.ModelAdmin[ItemModel]
    _TagAdminBase = admin.ModelAdmin[TagModel]
    _GraphProxyAdminBase = admin.ModelAdmin[CategoryGraphProxy]
    _DebugProxyAdminBase = admin.ModelAdmin[TaxomeshDebugProxy]
    _CategoryParentLinkTabular = admin.TabularInline[CategoryParentLinkModel, CategoryModel]
    _CategoryItemLinkTabular = admin.TabularInline[ItemParentLinkModel, CategoryModel]
    _ItemParentLinkTabular = admin.TabularInline[ItemParentLinkModel, ItemModel]
    _ItemTagLinkTabular = admin.TabularInline[ItemTagLinkModel, ItemModel]
    _ItemRelationLinkTabular = admin.TabularInline[ItemRelationLinkModel, ItemModel]
    _CategoryParentLinkFormBase = forms.ModelForm[CategoryParentLinkModel]
    _CategoryFormBase = forms.ModelForm[CategoryModel]
    _ItemRelationLinkFormBase = forms.ModelForm[ItemRelationLinkModel]
    _TagFormBase = forms.ModelForm[TagModel]
else:
    _ModelAdminMixinBase = _LinkInlineMixinBase = object
    _CategoryAdminBase = _ItemAdminBase = _TagAdminBase = admin.ModelAdmin
    _GraphProxyAdminBase = _DebugProxyAdminBase = admin.ModelAdmin
    _CategoryParentLinkTabular = _CategoryItemLinkTabular = admin.TabularInline
    _ItemParentLinkTabular = _ItemTagLinkTabular = _ItemRelationLinkTabular = admin.TabularInline
    _CategoryParentLinkFormBase = _CategoryFormBase = forms.ModelForm
    _ItemRelationLinkFormBase = _TagFormBase = forms.ModelForm


TAXOMESH_LINKED_MODEL_SETTING: Final[str] = "TAXOMESH_LINKED_MODEL"
TAXOMESH_CATEGORY_LINKED_MODEL_SETTING: Final[str] = "TAXOMESH_CATEGORY_LINKED_MODEL"
GRAPH_REORDER_URL_NAME: Final[str] = "taxomesh_contrib_django_graph_reorder"
GRAPH_REPARENT_URL_NAME: Final[str] = "taxomesh_contrib_django_graph_reparent"
GRAPH_CHILDREN_URL_NAME: Final[str] = "taxomesh_contrib_django_graph_children"
GRAPH_REORDER_PATH: Final[str] = "graph/reorder/"
GRAPH_REPARENT_PATH: Final[str] = "graph/reparent/"
GRAPH_CHILDREN_PATH: Final[str] = "graph/children/"
DRAG_KIND_ITEM: Final[str] = "item"
DRAG_KIND_CATEGORY: Final[str] = "category"
# The category page's read-only flag for the top level; CategoryModelAdmin.at_top_level renders it.
TOP_LEVEL_FIELD: Final[str] = "at_top_level"
# How the graph's drag-and-drop names the top level as a parent: a category there has none.
TOP_LEVEL_PARENT: Final[str] = ""
# The read-only field of a change page that shows the ↗ link to the linked record.
_LINKED_OBJECT_FIELD: Final[str] = "linked_object_url"
# The form field that ItemCategoryAssignmentMixin adds, and the end of the name of the hidden input
# that its widget renders beside it.
_CATEGORIES_FIELD: Final[str] = "categories"
_SHOWN_SUFFIX: Final[str] = "_shown"


def _uuid_from_payload(raw: object) -> UUID:
    """Read an identifier that the graph's drag-and-drop sends as text.

    Args:
        raw: The identifier as the payload carries it.

    Returns:
        The identifier.

    Raises:
        ValueError: If it is text that is not a UUID.
        TypeError: If it is not a string.
    """
    if not isinstance(raw, str):
        raise TypeError(f"Expected a UUID as a string, not {type(raw).__name__}")
    return UUID(raw)


def _parent_from_payload(raw: object) -> UUID | None:
    """Read a parent the graph's drag-and-drop sends: the empty string is the top level.

    Args:
        raw: The parent as the payload carries it.

    Returns:
        The parent's identifier, or ``None`` for the top level.

    Raises:
        ValueError: If it is neither empty nor a UUID.
        TypeError: If it is not a string.
    """
    return None if raw == TOP_LEVEL_PARENT else _uuid_from_payload(raw)


def _graph_view_error(exc: Exception) -> JsonResponse:
    """Answer an exception of a graph view as the HTTP edge answers it.

    A library error that maps to a client error is the caller's to correct: 400, with the message of
    the error. A library error that maps to 500, and any other exception, answers 500 with one
    generic text, since their own text can name a table, a constraint or a path. The server error is
    logged.

    Args:
        exc: The exception that the view caught.

    Returns:
        The JSON answer, with the key ``error``.
    """
    if isinstance(exc, TaxomeshError):
        status, body = to_tuple(exc)  # logs a server error
        if status != HTTPStatus.INTERNAL_SERVER_ERROR:
            return JsonResponse({"error": body["detail"]}, status=HTTPStatus.BAD_REQUEST)
    else:
        logger.exception("A graph view failed")
    return JsonResponse({"error": GENERIC_SERVER_ERROR_DETAIL}, status=HTTPStatus.INTERNAL_SERVER_ERROR)


def _linked_model_label(setting_name: str) -> str | None:
    """Return the ``"app_label.ModelName"`` that a linked-model setting holds, or ``None`` when it is not set or empty.

    Args:
        setting_name: The Django setting.
    """
    label: str | None = getattr(settings, setting_name, None)
    return label or None


def _category_linked_model_setting() -> str:
    """Return the setting that names the linked model of a category.

    It is ``TAXOMESH_CATEGORY_LINKED_MODEL`` when that setting is set, and ``TAXOMESH_LINKED_MODEL``
    otherwise. The category pages, the category list and the graph read this rule.
    """
    if _linked_model_label(TAXOMESH_CATEGORY_LINKED_MODEL_SETTING):
        return TAXOMESH_CATEGORY_LINKED_MODEL_SETTING
    return TAXOMESH_LINKED_MODEL_SETTING


def _resolve_linked_url(external_id: str | None, setting_name: str = TAXOMESH_LINKED_MODEL_SETTING) -> str | None:
    """Return the admin change URL of the record that an external id names in the linked model.

    The Django setting ``setting_name`` names the linked model, as ``"app_label.ModelName"``. The
    function builds the URL of that model's admin change page with the external id as the primary
    key. It does not check that a record with that key exists. When the setting is not set, it
    returns ``None``, since the setting is optional. When the URL cannot be built, it logs a warning
    and returns ``None``.

    Args:
        external_id: The external id, used as the primary key in the linked model. An empty value
            or ``None`` returns ``None``.
        setting_name: The Django setting that names the linked model. The default is
            ``TAXOMESH_LINKED_MODEL``.

    Returns:
        The admin change URL, or ``None``.
    """
    linked_model_label = _linked_model_label(setting_name)
    if not external_id or linked_model_label is None:
        return None
    try:
        linked_model = apps.get_model(linked_model_label)
        app_label = linked_model._meta.app_label
        model_name = linked_model._meta.model_name
        return reverse(f"admin:{app_label}_{model_name}_change", args=[external_id])
    except Exception as exc:
        logger.warning("_resolve_linked_url(%r, %r) failed: %s", external_id, setting_name, exc)
        return None


def _fields_with_link(fields: _FieldGroups, setting_name: str) -> _FieldGroups:
    """Return the fields of a change page, without the ↗ link while ``setting_name`` is not set.

    A line of fields that holds the link keeps its other fields.

    Args:
        fields: The fields of the page, as ``ModelAdmin.get_fields`` returns them.
        setting_name: The setting that names the linked model of the page's rows.
    """
    if _linked_model_label(setting_name) is not None:
        return fields
    return [
        line if isinstance(line, str) else tuple(name for name in line if name != _LINKED_OBJECT_FIELD)
        for line in fields
        if line != _LINKED_OBJECT_FIELD
    ]


def _build_child_entries(  # noqa: PLR0913
    child_cats: Sequence[Category],
    items: Sequence[Item],
    depth: int,
    parent_uuid_str: str,
    cats_with_children: set[UUID],
    cats_with_items: set[UUID],
    cat_sort_map: dict[UUID, int],
    item_sort_map: dict[UUID, int],
) -> list[GraphEntry]:
    """Build the graph entries of the direct children of a category: its items, then its child categories.

    Args:
        child_cats: The rows of the child categories.
        items: The rows of the items placed in the category.
        depth: The depth on the page of every entry.
        parent_uuid_str: The identifier of the category, as text.
        cats_with_children: The identifiers of the categories that have a child category.
        cats_with_items: The identifiers of the categories that have an item.
        cat_sort_map: The ``sort_index`` of each child category under this category, by identifier.
        item_sort_map: The ``sort_index`` of each item in this category, by identifier.

    Returns:
        The entries.
    """
    entries: list[GraphEntry] = []

    for idx, item in enumerate(items):
        item_uuid_str = str(item.item_id)
        entries.append(
            GraphEntry(
                depth=depth,
                kind=DRAG_KIND_ITEM,
                name=str(item),
                uuid=item_uuid_str,
                enabled=item.enabled,
                external_id=item.external_id or "",
                linked_url=_resolve_linked_url(item.external_id or ""),
                has_descendants=False,
                depth_limited=False,
                initially_collapsed=False,
                sort_index=item_sort_map.get(item.item_id, idx),
                parent_uuid=parent_uuid_str,
            )
        )

    for idx, cat in enumerate(child_cats):
        cat_uuid_str = str(cat.category_id)
        has_descendants = cat.category_id in cats_with_children or cat.category_id in cats_with_items
        entries.append(
            GraphEntry(
                depth=depth,
                kind=DRAG_KIND_CATEGORY,
                name=str(cat),
                uuid=cat_uuid_str,
                enabled=cat.enabled,
                external_id=cat.external_id or "",
                linked_url=_resolve_linked_url(cat.external_id or "", _category_linked_model_setting()),
                has_descendants=has_descendants,
                depth_limited=False,
                initially_collapsed=True,
                sort_index=cat_sort_map.get(cat.category_id, idx),
                parent_uuid=parent_uuid_str,
            )
        )

    return entries


# ---------------------------------------------------------------------------
# Shared mixin
# ---------------------------------------------------------------------------


class TaxomeshAdminMixin:
    """A mixin that builds a new service for each write, and has the display members that the admins share.

    The display members link a row to the admin page of its linked record: the record of the linked
    model whose primary key is the row's external id. The setting of an admin names the linked
    model. It is ``TAXOMESH_LINKED_MODEL``, and for the admin of categories
    ``TAXOMESH_CATEGORY_LINKED_MODEL`` while that setting is set.
    """

    def _make_service(self) -> TaxomeshService:
        """Build a new ``TaxomeshService`` over a new ``DjangoRepository``.

        Returns:
            A new service on each call. One request can make several calls, such as ``save_model``
            and then ``save_formset``.
        """
        return TaxomeshService(repository=DjangoRepository())

    def _linked_model_setting(self) -> str:
        """Return the setting that names the model of the records that the rows of this admin link to."""
        return TAXOMESH_LINKED_MODEL_SETTING

    @admin.display(description="↗")
    # Any: Django hands a display method a row of whichever model the admin lists, a consumer's own included.
    def linked_object_url(self, obj: Any) -> str:
        """Return a ↗ link to the admin page of the linked record, when the setting of this admin is set.

        It works with any model that has an ``external_id`` attribute, such as ``CategoryModel`` and
        ``ItemModel``.

        Args:
            obj: The object that the admin shows.

        Returns:
            An HTML link with the ↗ icon, or an empty string when no URL can be built.
        """
        url = _resolve_linked_url(getattr(obj, "external_id", None) or "", self._linked_model_setting())
        if url:
            return format_html('<a href="{}" title="View in admin">&#8599;</a>', url)
        return ""

    @admin.display(description="External id", ordering="external_id")
    # Any: Django hands a display method a row of whichever model the admin lists, a consumer's own included.
    def external_id_with_link(self, obj: Any) -> str:
        """Show the external id, and after it a ↗ link to the admin page of the linked record.

        When the setting of this admin is not set, or the URL cannot be built, it shows the external
        id alone.

        Args:
            obj: The object that the admin shows.

        Returns:
            Safe HTML: the external id and a ↗ link, or the external id alone.
        """
        external_id = getattr(obj, "external_id", None) or ""
        url = _resolve_linked_url(external_id, self._linked_model_setting())
        if url and external_id:
            return format_html(
                '{} <a href="{}" title="View in admin" style="text-decoration:none">&#8599;</a>',
                external_id,
                url,
            )
        return external_id

    sort_modes: list[SortMode] = list(DEFAULT_SORT_MODES)

    def _resolve_sort_fn(self, sort_by: str) -> SortModeFn:
        """Return the function of the sort mode that ``sort_by`` names, or of the first mode.

        Args:
            sort_by: The key of the sort mode, from the query string.

        Returns:
            The function of the mode with that key, or of the first mode in ``sort_modes`` when no
            mode has the key.
        """
        for key, _label, fn in self.sort_modes:
            if key == sort_by:
                return fn
        return self.sort_modes[0][2]


# ---------------------------------------------------------------------------
# TaxomeshLinkedFKMixin
# ---------------------------------------------------------------------------


class TaxomeshLinkedFKMixin(_ModelAdminMixinBase):
    """A ``ModelAdmin`` mixin that uses ``TaxomeshLinkedFKWidget`` for each foreign key to a taxomesh model.

    Add it to the ``ModelAdmin`` of a model of your own that has foreign keys to ``ItemModel`` or
    ``CategoryModel``. Each such field then renders as a Select2 autocomplete, with a ``↗`` link to
    the taxomesh admin page of the selected object, and needs no code of its own.

    The mixin knows nothing of your app: when Django builds the form, it reads
    ``db_field.related_model`` to find the foreign keys to taxomesh models.

    Usage::

        from taxomesh.contrib.django.admin import TaxomeshLinkedFKMixin

        @admin.register(Content)
        class ContentAdmin(TaxomeshLinkedFKMixin, admin.ModelAdmin):
            fields = ["title", "type", "item", "category", "relevance"]
    """

    # Any: an override takes what django-stubs' ModelAdmin.formfield_for_foreignkey takes, which is Any.
    def formfield_for_foreignkey(
        self,
        db_field: models.ForeignKey[Any, Any],
        request: HttpRequest,
        **kwargs: Any,
    ) -> ModelChoiceField[Any] | None:
        """Use ``TaxomeshLinkedFKWidget`` for a foreign key to ``ItemModel`` or ``CategoryModel``.

        Any other foreign key gets the field that Django builds for it.

        Args:
            db_field: The foreign key of the edited model.
            request: The current HTTP request.
            **kwargs: Passed to ``super().formfield_for_foreignkey()``.

        Returns:
            The form field: with ``TaxomeshLinkedFKWidget`` for a foreign key to ``ItemModel`` or
            ``CategoryModel``, and with the default widget otherwise.
        """

        if db_field.related_model in (ItemModel, CategoryModel):
            kwargs["widget"] = TaxomeshLinkedFKWidget(
                field=db_field,
                admin_site=self.admin_site,
                using=kwargs.pop("using", None),
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# ---------------------------------------------------------------------------
# ItemCategoryAssignmentMixin helpers
# ---------------------------------------------------------------------------


# Any: obj is a row of the consumer's own model, which taxomesh does not know.
def _get_item_category_ids(obj: Any, external_id_attr: str) -> list[UUID]:
    """Return the identifiers of the categories that the item of a record is placed in.

    Args:
        obj: Your record: an object of your own model, whose ``external_id_attr`` is the external id
            of an item.
        external_id_attr: The name of the attribute of ``obj`` that holds the external id.

    Returns:
        The identifiers of the categories; empty when no item has that external id.
    """
    external_id = str(getattr(obj, external_id_attr))
    svc = TaxomeshService(repository=DjangoRepository())
    item = svc.items.get_by_external_id(external_id)
    if item is None:
        return []
    return [link.category_id for link in svc.repository.list_item_parent_links() if link.item_id == item.item_id]


class _CategoriesWidget(FilteredSelectMultiple):
    """The widget of the ``categories`` field: the admin's two-box select, and a hidden input after it.

    A browser posts nothing for a multiple select with no option selected. The posted data alone
    then does not tell an empty selection from a form that did not show the field. The hidden input
    is posted with each form that shows the field, and tells the two apart.
    """

    # Any: an override takes what django-stubs' Widget.render takes, whose attrs are dict[str, Any].
    def render(
        self,
        name: str,
        value: object,
        attrs: dict[str, Any] | None = None,
        renderer: BaseRenderer | None = None,
    ) -> SafeString:
        """Render the select, then the hidden input, named ``name`` followed by ``_shown``."""
        return format_html(
            '{}<input type="hidden" name="{}" value="1">',
            super().render(name, value, attrs, renderer),
            name + _SHOWN_SUFFIX,
        )

    def value_omitted_from_data(self, data: Mapping[str, object], files: object, name: str) -> bool:
        """Return whether the data comes from a form that did not show the field: it holds no hidden input."""
        return name + _SHOWN_SUFFIX not in data


# Any: obj is a row of the consumer's own model, and form the admin form django-stubs types as Any.
def _reconcile_categories(obj: Any, form: Any, external_id_attr: str) -> None:
    """Place the item of a record in the selected categories, and remove it from the others that the field offers.

    The service makes the changes. Nothing changes when the form has no ``categories`` field, when
    the data does not come from a form that showed the field, or when no item has the external id.
    A placement in a category that the field does not offer, such as a disabled category, stays.

    Args:
        obj: Your record, which the admin saves.
        form: The bound admin form, with ``cleaned_data``.
        external_id_attr: The name of the attribute of ``obj`` that holds the external id.
    """
    field = form.fields.get(_CATEGORIES_FIELD)
    if field is None or field.widget.value_omitted_from_data(
        form.data, form.files, form.add_prefix(_CATEGORIES_FIELD)
    ):
        return
    external_id = str(getattr(obj, external_id_attr))
    svc = TaxomeshService(repository=DjangoRepository())
    item = svc.items.get_by_external_id(external_id)
    if item is None:
        return
    all_links = svc.repository.list_item_parent_links()
    current_ids = {link.category_id for link in all_links if link.item_id == item.item_id}
    selected = {cat.category_id for cat in form.cleaned_data[_CATEGORIES_FIELD]}
    # The categories that the item is in and the field offers: only these can be deselected.
    offered_ids = set(field.queryset.filter(category_id__in=current_ids).values_list("category_id", flat=True))
    for cat_id in selected - current_ids:
        svc.items.place_in(item.item_id, cat_id)
    for cat_id in offered_ids - selected:
        svc.items.remove_from(item.item_id, cat_id)


# ---------------------------------------------------------------------------
# Shared list filters (must be defined before ItemCategoryAssignmentMixin)
# ---------------------------------------------------------------------------


class TaxomeshCategoryListFilter(admin.SimpleListFilter):
    """Filter the admin list of your model by the taxomesh category that each record's item is in."""

    title = "taxomesh category"
    parameter_name = "taxomesh_category"

    def lookups(self, request: HttpRequest, model_admin: object) -> list[tuple[str, str]]:
        """Return the taxomesh categories as the choices of the filter.

        Args:
            request: The current HTTP request.
            model_admin: The model admin.

        Returns:
            A ``(category_id, name)`` pair for each enabled category, without the implicit root.
        """
        try:
            qs = DjangoRepository().assignable_categories_qs()
            return [(str(cat.category_id), cat.name) for cat in qs]
        except Exception:
            return []

    # Any: a list filter is handed a queryset of whichever model the admin lists, as django-stubs types it.
    def queryset(self, request: HttpRequest, queryset: models.QuerySet[Any]) -> models.QuerySet[Any]:
        """Keep the records whose item is placed in the selected category.

        Args:
            request: The current HTTP request.
            queryset: The queryset to filter.

        Returns:
            The records whose item is placed in the selected category, or the queryset as it is
            when no category is selected.
        """
        value = self.value()
        if not value:
            return queryset
        try:
            cat_uuid = UUID(value)
            repo = DjangoRepository()
            svc = TaxomeshService(repository=repo)
            items = svc.items.list(category=cat_uuid, enabled=None)
            external_ids = [str(item.external_id) for item in items if item.external_id]
            return queryset.filter(pk__in=external_ids)
        except Exception:
            return queryset


# ---------------------------------------------------------------------------
# ItemCategoryAssignmentMixin
# ---------------------------------------------------------------------------


class ItemCategoryAssignmentMixin(TaxomeshAdminMixin, _ModelAdminMixinBase):
    """An admin mixin that adds a ``categories`` field, which selects many, to the admin of your model.

    Each record of your model stands for the taxomesh item whose external id is the record's
    ``taxomesh_external_id_attr``, its primary key by default. The field offers the enabled
    categories, and places that item in the selected ones.

    The page shows the field last when your admin declares no ``fields`` or ``fieldsets``, unless
    the user may only view the record. When your admin declares them, the page shows the field
    where they name ``categories``, and not at all when they do not name it. A save changes the
    placements only when its page showed the field. It removes the item only from categories that
    the field offers, so a placement in a disabled category stays.

    Usage::

        class MyModelAdmin(ItemCategoryAssignmentMixin, admin.ModelAdmin):
            taxomesh_external_id_attr = "id"   # default: "pk"
    """

    taxomesh_external_id_attr: str = "pk"
    list_filter = (TaxomeshCategoryListFilter,)

    # Any: the mixin serves the consumer's own ModelAdmin, whose model taxomesh does not know.
    def get_fields(self, request: HttpRequest, obj: Any | None = None) -> _FieldGroups:
        """Add the ``categories`` field, last, to the fields of an admin that declares no ``fields``.

        Django then lists the fields of the form that ``get_form(fields=None)`` returns, and that
        form has no ``categories`` field. A page for a user who may not change the record shows no
        form, so the method adds no field to it.

        Args:
            request: The current HTTP request.
            obj: The record that the page edits; ``None`` on the add page.

        Returns:
            The fields of the page.
        """
        fields = super().get_fields(request, obj)
        if self.fields or _CATEGORIES_FIELD in fields:
            return fields
        if obj is not None and not self.has_change_permission(request, obj):
            return fields
        return [*fields, _CATEGORIES_FIELD]

    # Any: the mixin serves the consumer's own ModelAdmin, whose model taxomesh does not know.
    def get_form(
        self, request: HttpRequest, obj: Any | None = None, change: bool = False, **kwargs: Any
    ) -> type[forms.ModelForm[Any]]:
        """Add a ``categories`` field, a ``ModelMultipleChoiceField``, to the form of a page that shows it.

        Django passes ``fields``, the fields that the page shows; without it, the method reads them
        from ``get_fieldsets()``, as Django's own method does. When they name ``categories``, the
        method declares the field on the base form class before it calls ``super().get_form()``.
        ``modelform_factory`` then finds the field in ``declared_fields``. Without that, a
        ``fieldsets`` that names the field, which the model does not have, would raise
        ``FieldError``.

        Django's ``ModelAdmin._get_form_for_get_fields`` calls ``get_form(fields=None)`` to find
        the fields of the form. ``fields=None`` names no field, so that form has no ``categories``
        field, and ``get_fields`` adds the field to the list.

        Args:
            request: The current HTTP request.
            obj: The record that the page edits; ``None`` on the add page.
            change: Whether the form edits a stored record; passed to the parent.
            **kwargs: Passed to ``super().get_form()``.

        Returns:
            The form class. When the page shows the field, it has a ``categories`` field, whose
            choices are the enabled categories, without the implicit root, from
            ``DjangoRepository.assignable_categories_qs()``.
        """
        if "fields" not in kwargs:
            kwargs["fields"] = flatten_fieldsets(self.get_fieldsets(request, obj))
        if kwargs["fields"] is None or _CATEGORIES_FIELD not in kwargs["fields"]:
            return super().get_form(request, obj, change, **kwargs)

        qs = DjangoRepository().assignable_categories_qs()
        cat_field = forms.ModelMultipleChoiceField(
            queryset=qs,
            required=False,
            widget=_CategoriesWidget(_CATEGORIES_FIELD, is_stacked=False),
            label="Categories",
        )

        # Register categories on the base form as a declared field so that
        # modelform_factory does not raise FieldError when 'categories' appears
        # in fieldsets (which become the fields= argument to modelform_factory).
        # Any: the consumer's form is a ModelForm of its own model, which taxomesh does not know.
        base_form: type[forms.ModelForm[Any]] = kwargs.pop("form", None) or self.form
        kwargs["form"] = type(base_form.__name__, (base_form,), {_CATEGORIES_FIELD: cat_field})

        form_class = super().get_form(request, obj, change, **kwargs)

        if obj is not None:
            initial_ids = _get_item_category_ids(obj, self.taxomesh_external_id_attr)
            if initial_ids:
                form_class.base_fields[_CATEGORIES_FIELD].initial = CategoryModel.objects.filter(
                    category_id__in=initial_ids
                )

        return form_class

    # Any: the mixin serves the consumer's own ModelAdmin, whose model taxomesh does not know; django-stubs
    # types the form as Any.
    def save_model(self, request: HttpRequest, obj: Any, form: Any, change: bool) -> None:
        """Save the record, then place its item in the selected categories through the service.

        ``super().save_model()`` stores the record first. When the page showed the ``categories``
        field, ``items.place_in`` then places the item in each selected category that it is not in,
        and ``items.remove_from`` removes it from each category that the field offers and that is
        not selected.

        Args:
            request: The current HTTP request.
            obj: The record that the admin saves.
            form: The bound admin form, with ``cleaned_data``.
            change: ``True`` when the page edits a stored record; ``False`` when it adds one.
        """
        super().save_model(request, obj, form, change)
        _reconcile_categories(obj, form, self.taxomesh_external_id_attr)


# ---------------------------------------------------------------------------
# The forms of a link between two categories (cycle / self-reference validation via clean())
# ---------------------------------------------------------------------------


class _CategoryLinkForm(_CategoryParentLinkFormBase):
    """The form of a link between two categories: it refuses a link that makes a cycle.

    ``clean()`` refuses a category as its own parent, and a parent link that makes a cycle with the
    stored links. It runs when Django validates the form, so the page shows the error with the
    form, and nothing is stored. ``CategoryModelAdmin.save_formset`` then stores each accepted link
    through the service, which checks for a cycle again.
    """

    class Meta:
        model = CategoryParentLinkModel
        fields = "__all__"

    # Any: a form's cleaned_data, which django-stubs types as dict[str, Any].
    def clean(self) -> dict[str, Any]:
        """Refuse a category as its own parent, and a parent link that makes a cycle.

        Raises:
            forms.ValidationError: If ``category`` is ``parent_category``, or if the link would
                make a cycle in the category graph.
        """
        super().clean()
        cleaned_data = self.cleaned_data
        category = cleaned_data.get("category")
        parent_category = cleaned_data.get("parent_category")
        if category and parent_category:
            cat_id = category.category_id
            parent_id = parent_category.category_id
            names = {cat_id: category.name, parent_id: parent_category.name}
            try:
                check_no_cycle(cat_id, parent_id, DjangoRepository().list_category_parent_links(), names)
            except TaxomeshCyclicDependencyError as exc:
                raise forms.ValidationError(str(exc)) from exc
        return cleaned_data


class CategoryParentLinkForm(_CategoryLinkForm):
    """The form of a parent link on the category page: it refuses a link that makes a cycle.

    ``CategoryParentLinkInline`` uses it. Its ``parent_category`` field is the parent, and
    ``category`` is the category of the page.
    """


class CategoryChildLinkForm(_CategoryLinkForm):
    """The form of a child link on the category page: it refuses a link that makes a cycle.

    ``CategoryChildLinkInline`` uses it. Its ``category`` field is the child, and
    ``parent_category`` is the category of the page.
    """


# ---------------------------------------------------------------------------
# The base of the link inlines
# ---------------------------------------------------------------------------


class _LinkInlineMixin(_LinkInlineMixinBase):
    """An inline of links that reads the two ends of each link with the link, in one query.

    The label of each row names both ends, so without this, each row would read them on its own.
    """

    # Any: the mixin serves the inline of each link model, with the model of its page.
    def get_queryset(self, request: HttpRequest) -> models.QuerySet[Any]:
        """Return the links, each with the rows of its two ends.

        Args:
            request: The current HTTP request.
        """
        return super().get_queryset(request).select_related()


# ---------------------------------------------------------------------------
# CategoryParentLink Inline
# ---------------------------------------------------------------------------


class CategoryParentLinkInline(_LinkInlineMixin, _CategoryParentLinkTabular):
    """The inline of the parent links of a category, on the category page."""

    model = CategoryParentLinkModel
    form = CategoryParentLinkForm
    extra = 0
    fk_name = "category"
    verbose_name = "Parent category"
    verbose_name_plural = "Parent categories"
    autocomplete_fields = ["parent_category"]

    def get_queryset(self, request: HttpRequest) -> models.QuerySet[CategoryParentLinkModel]:
        """Leave out the link to the implicit root, which this inline's parent select cannot show.

        ``formfield_for_foreignkey`` removes the implicit root from the parent choices. If the link
        to it were listed, its line would render a select with no option: the browser would send
        no parent for that line, and each save of the page would fail on a missing required field.
        The link stays stored, and only its line is not listed. The page shows it as the read-only
        top-level flag, and the service adds or removes it as the other parents change.

        Args:
            request: The current HTTP request.

        Returns:
            The category's parent links, without the one to the implicit root.
        """
        return super().get_queryset(request).exclude(parent_category__name=ROOT_CATEGORY_NAME)

    # Any: an override takes what django-stubs' ModelAdmin.formfield_for_foreignkey takes, which is Any.
    def formfield_for_foreignkey(
        self,
        db_field: models.ForeignKey[Any, Any],
        request: HttpRequest,
        **kwargs: Any,
    ) -> ModelChoiceField[Any] | None:
        """Leave the implicit root out of the choices of ``parent_category``.

        Args:
            db_field: The ForeignKey field descriptor.
            request: The current HTTP request.
            **kwargs: Passed through to super().
        """
        if db_field.name == "parent_category":
            kwargs["queryset"] = CategoryModel.objects.exclude(name=ROOT_CATEGORY_NAME)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# ---------------------------------------------------------------------------
# CategoryChildLink Inline
# ---------------------------------------------------------------------------


class CategoryChildLinkInline(_LinkInlineMixin, _CategoryParentLinkTabular):
    """The inline of the child categories of a category: the links whose parent is the category of the page."""

    model = CategoryParentLinkModel
    form = CategoryChildLinkForm
    fk_name = "parent_category"
    extra = 0
    verbose_name = "Child category"
    verbose_name_plural = "Child categories"
    autocomplete_fields = ["category"]

    # Any: an override takes what django-stubs' ModelAdmin.formfield_for_foreignkey takes, which is Any.
    def formfield_for_foreignkey(
        self,
        db_field: models.ForeignKey[Any, Any],
        request: HttpRequest,
        **kwargs: Any,
    ) -> ModelChoiceField[Any] | None:
        """Leave the implicit root out of the choices of ``category``, the child.

        Args:
            db_field: The ForeignKey field descriptor.
            request: The current HTTP request.
            **kwargs: Passed through to super().
        """
        if db_field.name == "category":
            kwargs["queryset"] = CategoryModel.objects.exclude(name=ROOT_CATEGORY_NAME)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# ---------------------------------------------------------------------------
# Item inlines
# ---------------------------------------------------------------------------


class ItemParentLinkInline(_LinkInlineMixin, _ItemParentLinkTabular):
    """The inline of the placements of an item, on the item page."""

    model = ItemParentLinkModel
    verbose_name = "Category"
    verbose_name_plural = "Categories"
    extra = 0
    autocomplete_fields = ["category"]


class ItemTagLinkInline(_LinkInlineMixin, _ItemTagLinkTabular):
    """The inline of the tag links of an item, on the item page."""

    model = ItemTagLinkModel
    extra = 0
    verbose_name = "Tag"
    verbose_name_plural = "Tags"
    autocomplete_fields = ["tag"]


class CategoryItemLinkInline(_LinkInlineMixin, _CategoryItemLinkTabular):
    """The inline of the placements in a category, on the category page.

    It lists the items placed in the category, and an admin can place an item there or remove one
    on the category page.
    """

    model = ItemParentLinkModel
    fk_name = "category"
    extra = 0
    verbose_name = "Item"
    verbose_name_plural = "Items"
    autocomplete_fields = ["item"]


# ---------------------------------------------------------------------------
# Shared filters
# ---------------------------------------------------------------------------


class HasSlugFilter(admin.SimpleListFilter):
    """Filter the list by whether the slug is empty: 'Has slug' or 'No slug'."""

    title = "has slug"
    parameter_name = "has_slug"

    def lookups(self, request: HttpRequest, model_admin: object) -> list[tuple[str, str]]:
        """Return the filter options."""
        return [("yes", "Has slug"), ("no", "No slug")]

    # Any: a list filter is handed a queryset of whichever model the admin lists, as django-stubs types it.
    def queryset(self, request: HttpRequest, queryset: models.QuerySet[Any]) -> models.QuerySet[Any]:
        """Apply the filter to the queryset."""
        if self.value() == "yes":
            return queryset.exclude(slug="")
        if self.value() == "no":
            return queryset.filter(slug="")
        return queryset


class HasLinkedObjectListFilter(admin.SimpleListFilter):
    """Filter the categories by whether they have an external id.

    The service stores no external id as ``NULL``, and a row that another writer made can hold ``""``.
    Both mean "No linked object".
    """

    title = "linked object"
    parameter_name = "has_linked_object"

    def lookups(self, request: HttpRequest, model_admin: object) -> list[tuple[str, str]]:
        """Return the filter choices.

        Args:
            request: The current HTTP request.
            model_admin: The model admin instance.

        Returns:
            The ``(value, label)`` pairs.
        """
        return [("yes", "Has linked object"), ("no", "No linked object")]

    # Any: a list filter is handed a queryset of whichever model the admin lists, as django-stubs types it.
    def queryset(self, request: HttpRequest, queryset: models.QuerySet[Any]) -> models.QuerySet[Any]:
        """Apply the filter to the queryset.

        Args:
            request: The current HTTP request.
            queryset: The queryset to filter.

        Returns:
            The filtered queryset, or the queryset as it is when no value is selected.
        """
        has_none = models.Q(external_id__isnull=True) | models.Q(external_id="")
        if self.value() == "yes":
            return queryset.exclude(has_none)
        if self.value() == "no":
            return queryset.filter(has_none)
        return queryset


# ---------------------------------------------------------------------------
# CategoryModel Form (reserved-name validation via clean_name())
# ---------------------------------------------------------------------------


class CategoryModelForm(_CategoryFormBase):
    """The form of a category: it refuses the reserved name of the implicit root.

    The service refuses the name too, on create and on rename. But ``save_model`` runs only after
    Django accepts the form, so a refusal there would show on the page beside Django's own "was
    added successfully", and Django would log an addition of a row that is not stored. Refused here,
    the page shows the form again with the error under the field, as it does for an external id that
    another category has.
    """

    class Meta:
        model = CategoryModel
        fields = "__all__"

    def clean_name(self) -> str:
        """Refuse the name the implicit root is stored under.

        Returns:
            The name, unchanged.

        Raises:
            forms.ValidationError: If the name is the reserved name of the implicit root.
        """
        name: str = self.cleaned_data["name"]
        if name == ROOT_CATEGORY_NAME:
            raise forms.ValidationError(f"Category name '{ROOT_CATEGORY_NAME}' is reserved for the implicit root.")
        return name


# ---------------------------------------------------------------------------
# CategoryModelAdmin
# ---------------------------------------------------------------------------


@admin.register(CategoryModel)
class CategoryModelAdmin(TaxomeshAdminMixin, _CategoryAdminBase):
    """The admin of ``CategoryModel``: the category pages, and the graph page with its views."""

    form = CategoryModelForm

    list_display = (
        "category_id",
        "external_id_with_link",
        "name",
        "slug",
        "enabled",
        "version",
        "created_at",
        "updated_at",
    )
    search_fields = ("name", "slug", "category_id")
    list_filter = ("enabled", HasSlugFilter, HasLinkedObjectListFilter)
    fields = (
        "name",
        "slug",
        "description",
        "enabled",
        TOP_LEVEL_FIELD,
        ("external_id", _LINKED_OBJECT_FIELD),
        "metadata",
        ("created_at", "updated_at", "version"),
    )
    readonly_fields = (TOP_LEVEL_FIELD, _LINKED_OBJECT_FIELD, "created_at", "updated_at", "version")
    inlines = [CategoryParentLinkInline, CategoryChildLinkInline, CategoryItemLinkInline]
    formfield_overrides = {models.JSONField: {"widget": JsonEditorWidget, "form_class": JsonEditorFormField}}

    def _linked_model_setting(self) -> str:
        """Return the setting that names the linked model of a category: see ``_category_linked_model_setting``."""
        return _category_linked_model_setting()

    def get_fields(self, request: HttpRequest, obj: CategoryModel | None = None) -> _FieldGroups:
        """Return the fields of the page, without the ↗ link while no setting names the linked model.

        Args:
            request: The current HTTP request.
            obj: The category that the page edits; ``None`` on the add page.
        """
        return _fields_with_link(super().get_fields(request, obj), self._linked_model_setting())

    def get_queryset(self, request: HttpRequest) -> models.QuerySet[CategoryModel]:
        """Return the queryset of the categories, without the implicit root.

        Args:
            request: The current HTTP request.
        """
        return super().get_queryset(request).exclude(name=ROOT_CATEGORY_NAME)

    def get_urls(self) -> list[URLPattern]:
        """Add the URLs of the graph page and its views to the URLs of the admin."""
        urls = super().get_urls()
        custom = [
            path(
                "graph/",
                self.admin_site.admin_view(self.graph_view),
                name="taxomesh_contrib_django_graph",
            ),
            path(
                GRAPH_REORDER_PATH,
                self.admin_site.admin_view(self.reorder_view),
                name=GRAPH_REORDER_URL_NAME,
            ),
            path(
                GRAPH_REPARENT_PATH,
                self.admin_site.admin_view(self.reparent_view),
                name=GRAPH_REPARENT_URL_NAME,
            ),
            path(
                GRAPH_CHILDREN_PATH,
                self.admin_site.admin_view(self.graph_children_view),
                name=GRAPH_CHILDREN_URL_NAME,
            ),
        ]
        return custom + urls

    def _may_move(self, request: HttpRequest, kind: str) -> bool:
        """Return whether the user may move a node of this kind: the change permission of its admin.

        A category asks this admin, and an item the admin that the same site registers for items, so
        an override of ``has_change_permission`` is obeyed. With no admin for items on the site,
        Django's own rule answers: the user's ``change`` permission on the item model.
        """
        if kind == DRAG_KIND_CATEGORY:
            return self.has_change_permission(request)
        try:
            return self.admin_site.get_model_admin(ItemModel).has_change_permission(request)
        except NotRegistered:
            opts = ItemModel._meta
            return request.user.has_perm(f"{opts.app_label}.{get_permission_codename('change', opts)}")

    def _move_refused(self, kind: str) -> JsonResponse:
        """Answer a move that the user may not make: 403, in the shape the graph page shows."""
        plural = "categories" if kind == DRAG_KIND_CATEGORY else "items"
        return JsonResponse(
            {"error": f"Moving {plural} needs the permission to change {plural}"}, status=HTTPStatus.FORBIDDEN
        )

    # Any: the JSON body of the request, whose values the view checks one by one.
    def _read_move(self, request: HttpRequest, fields: tuple[str, ...]) -> dict[str, Any] | JsonResponse:
        """Read the body of a move that the graph page sends, or return the answer that refuses it.

        A move is a POST whose JSON object holds ``kind``, a kind the graph knows, and ``fields``,
        from a user who may move that kind. A refusal answers 405, 400 or 403.

        Args:
            request: The current HTTP request.
            fields: The fields the move needs besides ``kind``.

        Returns:
            The body, or the JSON answer that refuses the request.
        """
        if request.method != "POST":
            return JsonResponse({"error": "Method not allowed"}, status=HTTPStatus.METHOD_NOT_ALLOWED)
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            body = None
        if not isinstance(body, dict):
            return JsonResponse({"error": "Invalid JSON"}, status=HTTPStatus.BAD_REQUEST)
        for field in ("kind", *fields):
            if field not in body:
                return JsonResponse({"error": f"Missing field: {field}"}, status=HTTPStatus.BAD_REQUEST)
        kind = body["kind"]
        if kind not in (DRAG_KIND_ITEM, DRAG_KIND_CATEGORY):
            return JsonResponse({"error": f"Invalid kind: {kind}"}, status=HTTPStatus.BAD_REQUEST)
        if not self._may_move(request, kind):
            return self._move_refused(kind)
        return body

    def reorder_view(self, request: HttpRequest) -> HttpResponse:
        """Reorder the items or the child categories of one parent, as the graph page's drag-and-drop sends them.

        An empty ``parent_uuid`` names the top level, which only categories have. The user needs the
        permission to change the kind that the request reorders.
        """
        body = self._read_move(request, ("parent_uuid", "ordered_uuids"))
        if isinstance(body, JsonResponse):
            return body
        kind = body["kind"]

        try:
            parent_uuid = _parent_from_payload(body["parent_uuid"])
            ordered_uuids = [_uuid_from_payload(u) for u in body["ordered_uuids"]]
        except (ValueError, TypeError):
            return JsonResponse({"error": "Invalid UUID format"}, status=400)

        try:
            svc = TaxomeshService(repository=DjangoRepository())
            if kind == DRAG_KIND_ITEM:
                if parent_uuid is None:
                    return JsonResponse({"error": "Items have no top level"}, status=400)
                svc.items.reorder(parent_uuid, ordered_uuids)
            else:
                svc.categories.reorder(parent_uuid, ordered_uuids)
        except Exception as exc:
            return _graph_view_error(exc)

        return JsonResponse({"ok": True})

    def reparent_view(self, request: HttpRequest) -> HttpResponse:  # noqa: PLR0911
        """Move an item or a category from one parent to another, as the graph page's drag-and-drop sends it.

        An empty ``old_parent_uuid`` or ``new_parent_uuid`` names the top level, which only
        categories have. The user needs the permission to change the kind that the request moves.
        """
        body = self._read_move(request, ("node_uuid", "old_parent_uuid", "new_parent_uuid", "insert_before_uuid"))
        if isinstance(body, JsonResponse):
            return body
        kind = body["kind"]

        try:
            node_uuid = _uuid_from_payload(body["node_uuid"])
            old_parent_uuid = _parent_from_payload(body["old_parent_uuid"])
            new_parent_uuid = _parent_from_payload(body["new_parent_uuid"])
            raw_insert = body["insert_before_uuid"]
            insert_before_uuid = _uuid_from_payload(raw_insert) if raw_insert is not None else None
        except (ValueError, TypeError):
            return JsonResponse({"error": "Invalid UUID format"}, status=400)

        try:
            repo = DjangoRepository()
            svc = TaxomeshService(repository=repo)
            root_cats = [c for c in repo.list_categories(enabled=None) if c.name == ROOT_CATEGORY_NAME]
            root_uuid = root_cats[0].category_id if root_cats else None
            if root_uuid is not None and node_uuid == root_uuid:
                return JsonResponse({"error": "The implicit root cannot be moved"}, status=400)
            if kind == DRAG_KIND_ITEM:
                if old_parent_uuid is None or new_parent_uuid is None:
                    return JsonResponse({"error": "Items have no top level"}, status=400)
                svc.items.move(
                    node_uuid,
                    from_category=old_parent_uuid,
                    to_category=new_parent_uuid,
                    before=insert_before_uuid,
                )
            else:
                svc.categories.move(
                    node_uuid,
                    from_parent=old_parent_uuid,
                    to_parent=new_parent_uuid,
                    before=insert_before_uuid,
                )
        except TaxomeshCyclicDependencyError as exc:
            return JsonResponse({"error": f"Cycle detected: {exc}"}, status=400)
        except Exception as exc:
            return _graph_view_error(exc)

        return JsonResponse({"ok": True})

    def graph_view(self, request: HttpRequest) -> HttpResponse:
        """Render the graph page: the top-level categories, whose children the page loads when it opens each one.

        The page reads the graph with ``enabled=None``, so the filter leaves out no category. It
        starts at ``graph.roots``, so it does not draw the categories of a stored cycle that no
        top-level category reaches, or a category that only those reach; ``graph.walk()`` yields
        them all. When the graph holds only such categories, the page says "No categories found."

        Args:
            request: The current HTTP request.

        Returns:
            The rendered graph page.
        """

        error: str | None = None
        entries: list[GraphEntry] = []
        has_entries = False
        sort_by = request.GET.get("sort_by", DEFAULT_SORT_MODE)

        try:
            repo = DjangoRepository()
            svc = TaxomeshService(repository=repo)

            # One snapshot answers both of the page's questions: which categories are at the top
            # level, and whether each has anything under it.
            graph = svc.graph(enabled=None)
            root_nodes = graph.roots
            has_entries = bool(root_nodes)

            # A top-level category has one link, its link to the implicit root, so this read of
            # those links gives the STORED sort_index values that these entries render. The
            # drag-and-drop payload names their parent as the top level, never by the identifier
            # of the implicit root.
            root_ids = [node.category.category_id for node in root_nodes]
            root_links = repo.list_category_parent_links(category_ids=root_ids) if root_ids else []
            root_sort_map: dict[UUID, int] = {lnk.category_id: lnk.sort_index for lnk in root_links}

            for idx, node in enumerate(root_nodes):
                cat = node.category
                entries.append(
                    GraphEntry(
                        depth=0,
                        kind=DRAG_KIND_CATEGORY,
                        name=str(cat),
                        uuid=str(cat.category_id),
                        enabled=cat.enabled,
                        external_id=cat.external_id or "",
                        linked_url=_resolve_linked_url(cat.external_id or "", self._linked_model_setting()),
                        has_descendants=bool(node.children or node.items),
                        depth_limited=False,
                        initially_collapsed=True,
                        sort_index=root_sort_map.get(cat.category_id, idx),
                        parent_uuid=TOP_LEVEL_PARENT,
                    )
                )
        except TaxomeshError as exc:
            error = str(exc)

        entries = self._resolve_sort_fn(sort_by)(entries)

        children_url = reverse(f"admin:{GRAPH_CHILDREN_URL_NAME}")
        context = {
            **self.admin_site.each_context(request),
            "title": "Taxonomy Graph",
            "entries": entries,
            "has_entries": has_entries,
            "error": error,
            "item_relations": {},
            "children_url": children_url,
            "sort_by": sort_by,
            "sort_mode_options": [{"key": k, "label": lbl} for k, lbl, _ in self.sort_modes],
            "opts": self.model._meta,
        }
        return TemplateResponse(request, "admin/taxomesh_contrib_django/graph.html", context)

    def graph_children_view(self, request: HttpRequest) -> HttpResponse:
        """Return an HTML fragment with the direct children of one category: its items and its child categories.

        A refusal or a failure answers as the graph's other views do: JSON with the key ``error``.
        """

        sort_by = request.GET.get("sort_by", DEFAULT_SORT_MODE)
        try:
            parent_uuid = UUID(request.GET["parent_uuid"])
            depth = int(request.GET.get("depth", 1))
        except (KeyError, ValueError):
            return JsonResponse({"error": "Missing or invalid parent_uuid or depth"}, status=HTTPStatus.BAD_REQUEST)

        try:
            repo = DjangoRepository()
            svc = TaxomeshService(repository=repo)

            child_cats = svc.categories.list(parent=parent_uuid, enabled=None)
            items = svc.items.list(category=parent_uuid, enabled=None)

            # Only the links of this category and its children, which is all that these entries
            # need: the STORED sort_index values that they render, and whether each child has
            # anything under it. Reading both link tables whole, each time the page opens a
            # category, would cost more.
            scope_ids = [parent_uuid, *(cat.category_id for cat in child_cats)]
            cat_links = repo.list_category_parent_links(parent_category_ids=scope_ids)
            item_links = repo.list_item_parent_links(category_ids=scope_ids)
            cats_with_children = {lnk.parent_category_id for lnk in cat_links}
            cats_with_items = {lnk.category_id for lnk in item_links}

            cat_sort_map = {
                lnk.category_id: lnk.sort_index for lnk in cat_links if lnk.parent_category_id == parent_uuid
            }
            item_sort_map = {lnk.item_id: lnk.sort_index for lnk in item_links if lnk.category_id == parent_uuid}

            parent_uuid_str = str(parent_uuid)
            entries = _build_child_entries(
                child_cats=child_cats,
                items=items,
                depth=depth,
                parent_uuid_str=parent_uuid_str,
                cats_with_children=cats_with_children,
                cats_with_items=cats_with_items,
                cat_sort_map=cat_sort_map,
                item_sort_map=item_sort_map,
            )

            # The relations of every rendered item in one batch read, one query for the links and
            # one for the items, and not a query for each item and a subscript for each relation.
            # The read itself logs and skips a relation whose other end is not stored, so this
            # view hides no failure.
            related = svc.items.get_many_related([item.item_id for item in items])
            item_relations: dict[str, list[RelationEntry]] = {}
            for item in items:
                found = related.get(item.item_id)
                if found is None:
                    continue
                item_relations[str(item.item_id)] = [
                    RelationEntry(
                        relation_type=relation_type,
                        target_name=target.name,
                        target_uuid=str(target.item_id),
                    )
                    for relation_type in found.relation_types
                    for target in found.of_type(relation_type)
                ]

        except Exception as exc:
            return _graph_view_error(exc)

        entries = self._resolve_sort_fn(sort_by)(entries)

        children_url = reverse(f"admin:{GRAPH_CHILDREN_URL_NAME}")
        html = render_to_string(
            "admin/taxomesh_contrib_django/_graph_entry_list.html",
            {"entries": entries, "item_relations": item_relations, "children_url": children_url},
            request=request,
        )
        return HttpResponse(html, content_type="text/html")

    def save_model(
        self,
        request: HttpRequest,
        obj: CategoryModel,
        form: object,
        change: bool,
    ) -> None:
        """Create or update the category through the service.

        Args:
            request: The current HTTP request.
            obj: The category that the page saves.
            form: The bound form, which this method does not use; Django's interface passes it.
            change: ``True`` when the page edits a stored row; ``False`` when it adds one.
        """

        svc = self._make_service()
        try:
            if not change:
                domain_cat = svc.categories.create(
                    name=obj.name,
                    description=obj.description,
                    slug=obj.slug,
                    metadata=obj.metadata,
                    external_id=obj.external_id,
                )
                # ``create`` takes no enabled state, and each new category is enabled, so the next
                # update applies a box left unchecked on the add form.
                if not obj.enabled:
                    svc.categories.update(category=domain_cat.category_id, enabled=False)
                # Give obj the stored identifier, so that the inlines can save foreign keys to it.
                # Without this, Django raises ValueError ("unsaved related object"), because
                # obj.save() never ran.
                obj.category_id = domain_cat.category_id
                obj._state.adding = False
            else:
                svc.categories.update(
                    category=obj.category_id,
                    name=obj.name,
                    description=obj.description,
                    slug=obj.slug,
                    metadata=obj.metadata,
                    external_id=obj.external_id,
                    enabled=obj.enabled,
                )
        except TaxomeshValidationError as exc:
            # CategoryModelForm refuses the reserved name of the implicit root before this runs;
            # this branch reports a save that does not go through that form.
            self.message_user(request, str(exc), level=messages.ERROR)

    # Any: an override takes what django-stubs' ModelAdmin.save_formset takes, which is Any.
    def save_formset(
        self,
        request: HttpRequest,
        form: CategoryModelForm,
        formset: Any,
        change: bool,
    ) -> None:
        """Save the parent-link and child-link inlines through the service.

        Django's default ``save_formset`` writes the links through the ORM, which keeps whatever
        link to the implicit root the category has. ``add_parent`` and ``remove_parent`` keep the
        top level instead: a category that gets a parent leaves it, and one that loses its last
        parent returns to it. For a line whose pair changed, the new parent is added, then the old
        one removed. The other inlines use Django's default save, through the ORM.

        Each line is saved on its own, the deleted lines first. A line that the service refuses is
        reported and changes nothing, so an edited line keeps its old link, and the lines after it
        are saved. Each form checks its own line against the stored links, so two lines can still
        make a cycle together; the service then refuses the second.

        Args:
            request: The current HTTP request.
            form: The category form.
            formset: The inline formset that the page saves.
            change: ``True`` when the page edits a stored category; ``False`` when it adds one.
        """

        if formset.model is not CategoryParentLinkModel:
            super().save_formset(request, form, formset, change)
            return
        svc = self._make_service()
        links = formset.save(commit=False)
        for link in formset.deleted_objects:
            try:
                svc.categories.remove_parent(link.category_id, link.parent_category_id)
            except TaxomeshError as exc:
                self.message_user(request, str(exc), level=messages.ERROR)
        for link in links:
            try:
                svc.categories.add_parent(link.category_id, link.parent_category_id, sort_index=link.sort_index)
                if link.pk is not None:
                    stored = CategoryParentLinkModel.objects.get(pk=link.pk)
                    if (stored.category_id, stored.parent_category_id) != (link.category_id, link.parent_category_id):
                        svc.categories.remove_parent(stored.category_id, stored.parent_category_id)
            except TaxomeshError as exc:
                self.message_user(request, str(exc), level=messages.ERROR)

    @admin.display(boolean=True, description="At the top level")
    def at_top_level(self, obj: CategoryModel | None) -> bool | None:
        """Whether the category is at the top level: it has no parent.

        Read-only, since the parents decide it. Adding a parent takes a category off the top level,
        and removing its last one puts it back. Unknown on the add page, before any parent is saved.

        Args:
            obj: The category being shown.

        Returns:
            ``True`` or ``False``, or ``None`` for a category not stored yet.
        """
        if obj is None or obj._state.adding:
            return None
        return CategoryParentLinkModel.objects.filter(
            category_id=obj.category_id, parent_category__name=ROOT_CATEGORY_NAME
        ).exists()

    def delete_model(self, request: HttpRequest, obj: CategoryModel) -> None:
        """Delete the category through the service.

        Args:
            request: The current HTTP request.
            obj: The category to delete.
        """

        svc = self._make_service()
        try:
            svc.categories.delete(obj.category_id)
        except TaxomeshError as exc:
            self.message_user(request, str(exc), level=messages.ERROR)

    def delete_queryset(self, request: HttpRequest, queryset: models.QuerySet[CategoryModel]) -> None:
        """Delete each selected category through the service.

        Args:
            request: The current HTTP request.
            queryset: The categories to delete.
        """

        svc = self._make_service()
        for obj in queryset:
            try:
                svc.categories.delete(obj.category_id)
            except TaxomeshError as exc:
                self.message_user(request, str(exc), level=messages.ERROR)


# ---------------------------------------------------------------------------
# ItemRelationLink Form (self-relation validation)
# ---------------------------------------------------------------------------


class ItemRelationLinkForm(_ItemRelationLinkFormBase):
    """The form of a relation: it refuses a relation of an item to itself, and an empty relation type."""

    class Meta:
        model = ItemRelationLinkModel
        fields = "__all__"

    # Any: a form's cleaned_data, which django-stubs types as dict[str, Any].
    def clean(self) -> dict[str, Any]:
        """Refuse a relation of an item to itself, and a relation type that is empty or only spaces.

        Raises:
            forms.ValidationError: If ``source_item`` is ``target_item``, or if the relation type is
                empty once stripped.
        """
        super().clean()
        cleaned_data = self.cleaned_data
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


class _ItemRelationInlineBase(_LinkInlineMixin, _ItemRelationLinkTabular):
    """The base of the two relation inlines; a subclass sets ``fk_name``, its names and ``autocomplete_fields``."""

    model = ItemRelationLinkModel
    form = ItemRelationLinkForm
    extra = 0


def _page_object_id(request: HttpRequest) -> UUID | None:
    """Return the identifier of the item a change page shows, from its resolved URL.

    Args:
        request: The current HTTP request.

    Returns:
        The ``object_id`` the admin URL captured, or ``None`` on the add page, whose URL captures
        none.
    """
    match = request.resolver_match
    object_id = None if match is None else match.kwargs.get("object_id")
    return None if object_id is None else UUID(object_id)


class OutgoingRelationInline(_ItemRelationInlineBase):
    """The inline of the relations from the item of the page: those whose ``source_item`` is that item."""

    verbose_name = "Relation from this item"
    verbose_name_plural = "Relations from this item"
    fk_name = "source_item"
    autocomplete_fields = ["target_item"]

    def get_queryset(self, request: HttpRequest) -> models.QuerySet[ItemRelationLinkModel]:
        return super().get_queryset(request).filter(source_item_id=_page_object_id(request))


class IncomingRelationInline(_ItemRelationInlineBase):
    """The inline of the relations to the item of the page: those whose ``target_item`` is that item."""

    verbose_name = "Relation to this item"
    verbose_name_plural = "Relations to this item"
    fk_name = "target_item"
    autocomplete_fields = ["source_item"]

    def get_queryset(self, request: HttpRequest) -> models.QuerySet[ItemRelationLinkModel]:
        return super().get_queryset(request).filter(target_item_id=_page_object_id(request))


# ---------------------------------------------------------------------------
# ItemModelAdmin
# ---------------------------------------------------------------------------


@admin.register(ItemModel)
class ItemModelAdmin(TaxomeshAdminMixin, _ItemAdminBase):
    """The admin of ``ItemModel``: the item pages."""

    list_display = ("name", "external_id_with_link", "slug", "enabled", "version", "created_at", "updated_at")
    search_fields = ("name", "external_id", "slug", "item_id")
    list_filter = ("enabled", HasSlugFilter)
    fields = (
        "name",
        ("external_id", _LINKED_OBJECT_FIELD),
        "slug",
        "enabled",
        "metadata",
        ("created_at", "updated_at", "version"),
    )
    readonly_fields = (_LINKED_OBJECT_FIELD, "created_at", "updated_at", "version")
    inlines = [ItemParentLinkInline, OutgoingRelationInline, IncomingRelationInline, ItemTagLinkInline]
    formfield_overrides = {models.JSONField: {"widget": JsonEditorWidget, "form_class": JsonEditorFormField}}

    def get_fields(self, request: HttpRequest, obj: ItemModel | None = None) -> _FieldGroups:
        """Return the fields of the page, without the ↗ link while ``TAXOMESH_LINKED_MODEL`` is not set.

        Args:
            request: The current HTTP request.
            obj: The item that the page edits; ``None`` on the add page.
        """
        return _fields_with_link(super().get_fields(request, obj), self._linked_model_setting())

    def save_model(
        self,
        request: HttpRequest,
        obj: ItemModel,
        form: object,
        change: bool,
    ) -> None:
        """Create or update the item through the service.

        Args:
            request: The current HTTP request.
            obj: The item that the page saves.
            form: The bound form, which this method does not use; Django's interface passes it.
            change: ``True`` when the page edits a stored row; ``False`` when it adds one.
        """

        svc = self._make_service()
        try:
            if not change:
                domain_item = svc.items.create(
                    name=obj.name,
                    external_id=obj.external_id,
                    slug=obj.slug,
                    metadata=obj.metadata,
                )
                # ``create`` takes no enabled state, and each new item is enabled, so the next
                # update applies a box left unchecked on the add form.
                if not obj.enabled:
                    svc.items.update(item=domain_item.item_id, enabled=False)
                # Give obj the stored identifier, so that the inlines can save foreign keys to it.
                obj.item_id = domain_item.item_id
                obj._state.adding = False
            else:
                svc.items.update(
                    item=obj.item_id,
                    enabled=obj.enabled,
                    slug=obj.slug,
                    name=obj.name,
                    metadata=obj.metadata,
                    external_id=obj.external_id,
                )
        except TaxomeshValidationError as exc:
            self.message_user(request, str(exc), level=messages.ERROR)

    def delete_model(self, request: HttpRequest, obj: ItemModel) -> None:
        """Delete the item through the service.

        Args:
            request: The current HTTP request.
            obj: The item to delete.
        """

        svc = self._make_service()
        try:
            svc.items.delete(obj.item_id)
        except TaxomeshError as exc:
            self.message_user(request, str(exc), level=messages.ERROR)

    def delete_queryset(self, request: HttpRequest, queryset: models.QuerySet[ItemModel]) -> None:
        """Delete each selected item through the service.

        Args:
            request: The current HTTP request.
            queryset: The items to delete.
        """

        svc = self._make_service()
        for obj in queryset:
            try:
                svc.items.delete(obj.item_id)
            except TaxomeshError as exc:
                self.message_user(request, str(exc), level=messages.ERROR)

    # Any: an override takes what django-stubs' ModelAdmin.save_formset takes, which is Any.
    def save_formset(self, request: HttpRequest, form: Any, formset: Any, change: bool) -> None:
        """Save the two relation inlines through the service.

        Django's default ``save_formset`` calls ``formset.save()``, which writes through the ORM and
        not through the service. For the outgoing and the incoming relation inlines, this method
        calls ``items.relate`` and ``items.unrelate`` instead.

        Each line is saved on its own, the deleted lines first. For a line whose stored key changed,
        the new relation is stored, then the old one removed, so a refused line keeps the relation
        that it had. The key compared is the one that ``relate`` stores, so a relation type that
        changes only in case or in the spaces around it is the same relation.

        The other inlines use Django's default save, through the ORM.

        Args:
            request: The current HTTP request.
            form: The form of the item.
            formset: The inline formset that the page saves.
            change: ``True`` when the page edits a stored item; ``False`` when it adds one.
        """

        fk_name = getattr(getattr(formset, "fk", None), "name", None)
        if formset.model is ItemRelationLinkModel and fk_name in ("source_item", "target_item"):
            svc = self._make_service()
            instances = formset.save(commit=False)
            for obj in formset.deleted_objects:
                try:
                    svc.items.unrelate(obj.source_item_id, obj.target_item_id, obj.relation_type)
                except TaxomeshError as exc:
                    self.message_user(request, str(exc), level=messages.ERROR)
            for obj in instances:
                original = None if obj.pk is None else ItemRelationLinkModel.objects.filter(pk=obj.pk).first()
                try:
                    link = svc.items.relate(
                        obj.source_item_id,
                        obj.target_item_id,
                        obj.relation_type,
                        sort_index=obj.sort_index,
                        metadata=obj.metadata or {},
                    )
                    if original is not None and (
                        original.source_item_id,
                        original.target_item_id,
                        original.relation_type,
                    ) != (link.source_item_id, link.target_item_id, link.relation_type):
                        svc.items.unrelate(original.source_item_id, original.target_item_id, original.relation_type)
                except TaxomeshError as exc:
                    self.message_user(request, str(exc), level=messages.ERROR)
        else:
            super().save_formset(request, form, formset, change)


# ---------------------------------------------------------------------------
# TagModel Form (a tag without metadata)
# ---------------------------------------------------------------------------


class TagModelForm(_TagFormBase):
    """The form of a tag: it accepts a tag without metadata.

    ``TagModel.metadata`` is declared without ``blank=True``, so the form that Django builds from it
    would require the field and refuse ``{}``, the metadata of every tag created without any: the
    admin could then neither add nor save such a tag. The field is optional here, because a change
    to the model would need a migration.

    It is the JSON field of the category and item forms, which reads an empty box as ``{}``. A
    plain optional field would read it as ``None``, which ``tags.update`` refuses. The add page
    opens the box with ``{}``, and a change page with the stored metadata.
    """

    metadata = JsonEditorFormField(required=False, initial=dict)

    class Meta:
        model = TagModel
        fields = "__all__"


# ---------------------------------------------------------------------------
# TagModelAdmin
# ---------------------------------------------------------------------------


@admin.register(TagModel)
class TagModelAdmin(TaxomeshAdminMixin, _TagAdminBase):
    """The admin of ``TagModel``: the tag pages.

    The pages take no identifier, as the category and item pages take none: the service assigns it
    when it creates the tag. The change page shows it in its heading.
    """

    form = TagModelForm
    list_display = ("tag_id", "name")
    search_fields = ("name",)
    fields = ("name", "metadata")

    def save_model(
        self,
        request: HttpRequest,
        obj: TagModel,
        form: object,
        change: bool,
    ) -> None:
        """Create or update the tag through the service.

        Args:
            request: The current HTTP request.
            obj: The tag that the page saves.
            form: The bound form, which this method does not use; Django's interface passes it.
            change: ``True`` when the page edits a stored row; ``False`` when it adds one.
        """

        svc = self._make_service()
        try:
            if not change:
                domain_tag = svc.tags.create(name=obj.name, metadata=obj.metadata)
                # The service assigns the identifier. Give it to obj, so that the confirmation after
                # the save and the log entry name the stored tag.
                obj.tag_id = domain_tag.tag_id
            else:
                svc.tags.update(tag=obj.tag_id, name=obj.name, metadata=obj.metadata)
        except TaxomeshValidationError as exc:
            self.message_user(request, str(exc), level=messages.ERROR)

    def delete_model(self, request: HttpRequest, obj: TagModel) -> None:
        """Delete the tag through the service.

        Args:
            request: The current HTTP request.
            obj: The tag to delete.
        """

        svc = self._make_service()
        try:
            svc.tags.delete(obj.tag_id)
        except TaxomeshError as exc:
            self.message_user(request, str(exc), level=messages.ERROR)

    def delete_queryset(self, request: HttpRequest, queryset: models.QuerySet[TagModel]) -> None:
        """Delete each selected tag through the service.

        Args:
            request: The current HTTP request.
            queryset: The tags to delete.
        """

        svc = self._make_service()
        for obj in queryset:
            try:
                svc.tags.delete(obj.tag_id)
            except TaxomeshError as exc:
                self.message_user(request, str(exc), level=messages.ERROR)


# ---------------------------------------------------------------------------
# CategoryGraphProxyAdmin
# ---------------------------------------------------------------------------


@admin.register(CategoryGraphProxy)
class CategoryGraphProxyAdmin(_GraphProxyAdminBase):
    """The admin of the graph proxy: it shows the Graph entry on the admin index, which opens the graph page."""

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Refuse adding: this proxy is read-only."""
        return False

    def has_change_permission(self, request: HttpRequest, obj: object = None) -> bool:
        """Refuse changing: this proxy is read-only."""
        return False

    def has_delete_permission(self, request: HttpRequest, obj: object = None) -> bool:
        """Refuse deleting: this proxy is read-only."""
        return False

    def has_view_permission(self, request: HttpRequest, obj: object = None) -> bool:
        """Allow viewing for staff users."""
        return request.user.is_staff

    def changelist_view(self, request: HttpRequest, extra_context: object = None) -> HttpResponse:
        """Redirect the change list to the graph page."""

        return HttpResponseRedirect(reverse("admin:taxomesh_contrib_django_graph"))


# ---------------------------------------------------------------------------
# TaxomeshDebugProxyAdmin
# ---------------------------------------------------------------------------


@admin.register(TaxomeshDebugProxy)
class TaxomeshDebugProxyAdmin(_DebugProxyAdminBase):
    """The admin of the debug proxy: a page that shows what the service reports about itself."""

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Refuse adding: the debug page is read-only."""
        return False

    def has_change_permission(self, request: HttpRequest, obj: TaxomeshDebugProxy | None = None) -> bool:
        """Refuse changing: the debug page is read-only."""
        return False

    def has_delete_permission(self, request: HttpRequest, obj: TaxomeshDebugProxy | None = None) -> bool:
        """Refuse deleting: the debug page is read-only."""
        return False

    def has_view_permission(self, request: HttpRequest, obj: TaxomeshDebugProxy | None = None) -> bool:
        """Allow staff users to view the debug page."""
        return request.user.is_staff

    # Any: an override takes what django-stubs' ModelAdmin.changelist_view takes, a context of any values.
    def changelist_view(self, request: HttpRequest, extra_context: dict[str, Any] | None = None) -> HttpResponse:
        """Render the debug page.

        Args:
            request: The current HTTP request.
            extra_context: Extra template context, which this page does not use.

        Returns:
            The page, which shows ``TaxomeshService.info``, or the text of the error when the
            service cannot be built or read.
        """

        # Any: template context, one row per key; its values are TaxomeshInfo's, of several types.
        debug_info: dict[str, Any] = {}
        try:
            svc = TaxomeshService(repository=DjangoRepository())
            info = svc.info
            # Flattened into the rows debug.html walks, one key per row, each named as the info
            # names it.
            debug_info = {
                "version": info.version,
                "config_name": info.config_name,
                "item_corpus_size": info.item_corpus_size,
                "category_corpus_size": info.category_corpus_size,
                "repository.backend": info.repository.backend,
                "repository.path": info.repository.path,
                "repository.diagnostics": info.repository.diagnostics,
            }
        except Exception as exc:
            debug_info = {"error": str(exc)}

        context = {
            **self.admin_site.each_context(request),
            "title": "Taxomesh Debug",
            "debug_info": debug_info,
            "opts": self.model._meta,
        }
        return TemplateResponse(request, "admin/taxomesh_contrib_django/debug.html", context)
