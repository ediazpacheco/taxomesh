"""The three-state ``enabled`` filter on the handler edge.

One spelling, one meaning, on every surface: ``True`` enabled only, ``False`` disabled only,
``None`` all. A two-state flag could not express the third. These tests pin all three on the
filtering handlers and the ``search`` pair.

``TestFilterSignature`` guards the *shape* rather than the behaviour, and it deliberately mirrors
``tests/service/test_enabled_defaults.py``: that file asserts the defaults on the collections and
imports only those, so nothing there reaches the periphery. The defect both guard against is a
default silently flipping, which no behavioural test catches because each one passes the filter it
cares about explicitly.
"""

import inspect
from collections.abc import Callable

import pytest
from pydantic import BaseModel

from taxomesh.application.service import TaxomeshService
from taxomesh.contrib.api import handlers
from taxomesh.contrib.api.schemas import SearchCategoriesRequest, SearchItemsRequest


def _disabled_category(service: TaxomeshService, name: str) -> None:
    """Create a category and disable it."""
    created = service.categories.create(name=name)
    service.categories.update(created.category_id, enabled=False)


def _disabled_item(service: TaxomeshService, name: str) -> None:
    """Create an item and disable it."""
    created = service.items.create(name=name)
    service.items.update(created.item_id, enabled=False)


class TestCategoriesListEnabled:
    def test_default_excludes_disabled(self, service: TaxomeshService) -> None:
        service.categories.create(name="PublicCat")
        _disabled_category(service, "PrivateCat")

        names = {c.name for c in handlers.categories_list(service)}

        assert "PublicCat" in names
        assert "PrivateCat" not in names

    def test_enabled_none_returns_all(self, service: TaxomeshService) -> None:
        service.categories.create(name="PublicCat2")
        _disabled_category(service, "PrivateCat2")

        names = {c.name for c in handlers.categories_list(service, enabled=None)}

        assert "PublicCat2" in names
        assert "PrivateCat2" in names

    def test_enabled_false_returns_disabled_only(self, service: TaxomeshService) -> None:
        """The state no spelling could reach before: disabled rows, and only those."""
        service.categories.create(name="PublicCat3")
        _disabled_category(service, "PrivateCat3")

        names = {c.name for c in handlers.categories_list(service, enabled=False)}

        assert names == {"PrivateCat3"}


class TestItemsListEnabled:
    def test_default_excludes_disabled(self, service: TaxomeshService) -> None:
        service.items.create(name="PublicItem")
        _disabled_item(service, "PrivateItem")

        names = {i.name for i in handlers.items_list(service)}

        assert "PublicItem" in names
        assert "PrivateItem" not in names

    def test_enabled_none_returns_all(self, service: TaxomeshService) -> None:
        service.items.create(name="PublicItem2")
        _disabled_item(service, "PrivateItem2")

        names = {i.name for i in handlers.items_list(service, enabled=None)}

        assert "PublicItem2" in names
        assert "PrivateItem2" in names

    def test_enabled_false_returns_disabled_only(self, service: TaxomeshService) -> None:
        service.items.create(name="PublicItem3")
        _disabled_item(service, "PrivateItem3")

        names = {i.name for i in handlers.items_list(service, enabled=False)}

        assert names == {"PrivateItem3"}


class TestGraphEnabled:
    """The graph handler takes the same filter."""

    def test_enabled_none_includes_disabled(self, service: TaxomeshService) -> None:
        service.categories.create(name="Shown")
        _disabled_category(service, "Hidden")

        names = {node.category.name for node in handlers.graph(service, enabled=None).roots}

        assert {"Shown", "Hidden"} <= names

    def test_enabled_false_keeps_a_disabled_child_off_the_top_level(self, service: TaxomeshService) -> None:
        """``enabled=False`` holds the disabled rows, and a child keeps its place under its parent.

        A link survives only when *both* endpoints do, so a disabled child of an enabled parent
        loses its edge in that snapshot. It is still not at the top level, since it has a parent:
        the snapshot holds it, and its roots are the disabled categories with no parent.
        """
        parent = service.categories.create(name="Animals")
        child = service.categories.create(name="Mammals")
        service.categories.add_parent(child.category_id, parent.category_id)
        service.categories.update(child.category_id, enabled=False)

        graph = handlers.graph(service, enabled=False)

        assert child.category_id in graph
        assert graph.roots == ()


FILTERING_HANDLERS: list[tuple[str, Callable[..., object]]] = [
    ("categories_list", handlers.categories_list),
    ("categories_roots", handlers.categories_roots),
    ("items_list", handlers.items_list),
    ("graph", handlers.graph),
]


class TestFilterSignature:
    """On the handler edge: a filtering member defaults to enabled-only, by keyword."""

    @pytest.mark.parametrize(("label", "handler"), FILTERING_HANDLERS, ids=[label for label, _ in FILTERING_HANDLERS])
    def test_filter_is_keyword_only_and_defaults_to_enabled(self, label: str, handler: Callable[..., object]) -> None:
        parameter = inspect.signature(handler).parameters.get("enabled")

        assert parameter is not None, f"handlers.{label} must accept an enabled filter"
        assert parameter.default is True, f"handlers.{label} must default to enabled=True, not {parameter.default!r}"
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY, f"handlers.{label} must take enabled as keyword-only"


SEARCH_SCHEMAS: list[tuple[str, type[BaseModel]]] = [
    ("SearchItemsRequest", SearchItemsRequest),
    ("SearchCategoriesRequest", SearchCategoriesRequest),
]


class TestSearchFilterField:
    """On the two search schemas, where the filter is a field rather than a parameter.

    ``TestFilterSignature`` above cannot reach these: the search handlers take a request object,
    so ``enabled`` lives on the schema and no signature carries it. The defect guarded against is
    the same one — a default silently flipping, which every behavioural test misses because each
    passes the filter it cares about explicitly.
    """

    @pytest.mark.parametrize(("label", "schema"), SEARCH_SCHEMAS, ids=[label for label, _ in SEARCH_SCHEMAS])
    def test_enabled_is_three_state_and_defaults_to_enabled(self, label: str, schema: type[BaseModel]) -> None:
        field = schema.model_fields["enabled"]

        assert field.annotation == bool | None, f"{label}.enabled must be bool | None, not {field.annotation}"
        assert field.default is True, f"{label}.enabled must default to True, not {field.default!r}"


class TestItemsSearchEnabledParam:
    def test_search_items_request_uses_enabled_field(self) -> None:
        req = SearchItemsRequest(query="test", enabled=False)
        assert req.enabled is False

    def test_items_search_handler_passes_enabled_param(self, service: TaxomeshService) -> None:
        service.items.create(name="VisibleWidget")
        _disabled_item(service, "HiddenWidget")

        params = SearchItemsRequest(query="Widget", enabled=True)
        names = {i.name for i in handlers.items_search(service, params=params)}

        assert "VisibleWidget" in names
        assert "HiddenWidget" not in names

    def test_enabled_none_returns_both_states(self, service: TaxomeshService) -> None:
        """The state the HTTP edge could not express: both ranked together, not an error."""
        service.items.create(name="VisibleWidget")
        _disabled_item(service, "HiddenWidget")

        params = SearchItemsRequest(query="Widget", enabled=None)
        names = {i.name for i in handlers.items_search(service, params=params)}

        assert {"VisibleWidget", "HiddenWidget"} <= names

    def test_enabled_false_returns_disabled_only(self, service: TaxomeshService) -> None:
        """``False`` means disabled only — search had no HTTP-edge test for this at all."""
        service.items.create(name="VisibleWidget")
        _disabled_item(service, "HiddenWidget")

        params = SearchItemsRequest(query="Widget", enabled=False)
        names = {i.name for i in handlers.items_search(service, params=params)}

        assert names == {"HiddenWidget"}


class TestCategoriesSearchEnabledParam:
    def test_search_categories_request_uses_enabled_field(self) -> None:
        req = SearchCategoriesRequest(query="test", enabled=True)
        assert req.enabled is True

    def test_categories_search_handler_passes_enabled_param(self, service: TaxomeshService) -> None:
        service.categories.create(name="VisibleSection")
        _disabled_category(service, "HiddenSection")

        params = SearchCategoriesRequest(query="Section", enabled=True)
        names = {c.name for c in handlers.categories_search(service, params=params)}

        assert "VisibleSection" in names
        assert "HiddenSection" not in names

    def test_enabled_none_returns_both_states(self, service: TaxomeshService) -> None:
        """The state the HTTP edge could not express: both ranked together, not an error."""
        service.categories.create(name="VisibleSection")
        _disabled_category(service, "HiddenSection")

        params = SearchCategoriesRequest(query="Section", enabled=None)
        names = {c.name for c in handlers.categories_search(service, params=params)}

        assert {"VisibleSection", "HiddenSection"} <= names

    def test_enabled_false_returns_disabled_only(self, service: TaxomeshService) -> None:
        """``False`` means disabled only — search had no HTTP-edge test for this at all."""
        service.categories.create(name="VisibleSection")
        _disabled_category(service, "HiddenSection")

        params = SearchCategoriesRequest(query="Section", enabled=False)
        names = {c.name for c in handlers.categories_search(service, params=params)}

        assert names == {"HiddenSection"}
