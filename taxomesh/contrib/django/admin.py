"""Django admin registrations for taxomesh ORM models."""

from django.contrib import admin
from django.http import HttpRequest, HttpResponse
from django.urls import path

from taxomesh import TaxomeshService
from taxomesh.adapters.repositories.django_repository import DjangoRepository
from taxomesh.contrib.django.models import (
    CategoryGraphProxy,
    CategoryModel,
    ItemModel,
    TagModel,
)
from taxomesh.domain.graph import CategoryNode, TaxomeshGraph
from taxomesh.exceptions import TaxomeshError


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
                    "enabled": item.enabled,
                    "external_id": None,
                }
            )
        for child in node.children:
            _visit(child, depth + 1)

    for root in graph.roots:
        _visit(root, 0)
    return entries


@admin.register(CategoryModel)
class CategoryModelAdmin(admin.ModelAdmin):
    """Admin view for Category records."""

    list_display = ("category_id", "name", "enabled", "external_id")
    search_fields = ("name",)
    list_filter = ("enabled",)

    def get_urls(self) -> list:
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


@admin.register(ItemModel)
class ItemModelAdmin(admin.ModelAdmin):
    """Admin view for Item records."""

    list_display = ("item_id", "external_id", "enabled")
    search_fields = ()
    list_filter = ("enabled",)


@admin.register(TagModel)
class TagModelAdmin(admin.ModelAdmin):
    """Admin view for Tag records."""

    list_display = ("tag_id", "name")
    search_fields = ("name",)


@admin.register(CategoryGraphProxy)
class CategoryGraphProxyAdmin(admin.ModelAdmin):
    """Proxy admin that surfaces the Graph link on the main admin index."""

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: object = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: object = None) -> bool:
        return False

    def has_view_permission(self, request: HttpRequest, obj: object = None) -> bool:
        return request.user.is_staff

    def changelist_view(self, request: HttpRequest, extra_context: object = None) -> HttpResponse:
        from django.http import HttpResponseRedirect  # noqa: PLC0415
        from django.urls import reverse  # noqa: PLC0415

        return HttpResponseRedirect(reverse("admin:taxomesh_contrib_django_graph"))
