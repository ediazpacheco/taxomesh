"""Tests for taxomesh.contrib.api.serializers — graph_to_dict."""

import json

import taxomesh.contrib.api as contrib_api
from taxomesh.application.service import TaxomeshService
from taxomesh.contrib.api.serializers import graph_to_dict


class TestSerializersReExport:
    """serializers is accessible via taxomesh.contrib.api."""

    def test_serializers_importable_from_contrib_api(self) -> None:
        """from taxomesh.contrib.api import serializers succeeds."""
        from taxomesh.contrib.api import serializers  # noqa: PLC0415

        assert callable(serializers.graph_to_dict)

    def test_serializers_in_all(self) -> None:
        """'serializers' appears in taxomesh.contrib.api.__all__."""
        assert "serializers" in contrib_api.__all__


class TestGraphToDictEmptyGraph:
    """graph_to_dict on an empty graph."""

    def test_returns_empty_roots(self, service: TaxomeshService) -> None:
        """Empty graph produces {"roots": []}."""
        graph = service.get_graph()
        result = graph_to_dict(graph)
        assert result == {"roots": []}


class TestGraphToDictSingleRoot:
    """Single root node with no items or children."""

    def test_node_shape(self, service: TaxomeshService) -> None:
        """A root node has exactly category, items, and children keys."""
        service.create_category(name="Music")
        graph = service.get_graph()
        result = graph_to_dict(graph)
        assert len(result["roots"]) == 1
        node = result["roots"][0]
        assert set(node.keys()) == {"category", "items", "children"}
        assert node["items"] == []
        assert node["children"] == []

    def test_category_matches_model_dump(self, service: TaxomeshService) -> None:
        """category dict equals category.model_dump(mode='json')."""
        cat = service.create_category(name="Books")
        graph = service.get_graph()
        result = graph_to_dict(graph)
        assert result["roots"][0]["category"] == cat.model_dump(mode="json")


class TestGraphToDictRootWithItems:
    """Root node that has items but no children."""

    def test_items_match_model_dump(self, service: TaxomeshService) -> None:
        """items list contains dicts equal to item.model_dump()."""
        cat = service.create_category(name="Jazz")
        item = service.create_item(name="Kind of Blue")
        service.place_item_in_category(item.item_id, cat.category_id)
        graph = service.get_graph()
        result = graph_to_dict(graph)
        node = result["roots"][0]
        assert len(node["items"]) == 1
        assert node["items"][0] == item.model_dump(mode="json")
        assert node["children"] == []


class TestGraphToDictRootWithChildren:
    """Root node that has children but no items."""

    def test_children_list_has_node_shape(self, service: TaxomeshService) -> None:
        """children list contains correctly shaped node dicts."""
        parent = service.create_category(name="Fiction")
        child = service.create_category(name="Fantasy")
        service.add_category_parent(child.category_id, parent.category_id)
        graph = service.get_graph()
        result = graph_to_dict(graph)
        root_node = result["roots"][0]
        assert root_node["items"] == []
        assert len(root_node["children"]) == 1
        child_node = root_node["children"][0]
        assert set(child_node.keys()) == {"category", "items", "children"}
        assert child_node["category"] == child.model_dump(mode="json")
        assert child_node["children"] == []


class TestGraphToDictMultiLevel:
    """Multi-level nesting: root → child → grandchild."""

    def test_three_levels_preserved(self, service: TaxomeshService) -> None:
        """Nesting is preserved recursively at three levels."""
        root_cat = service.create_category(name="Root")
        child_cat = service.create_category(name="Child")
        grand_cat = service.create_category(name="Grandchild")
        service.add_category_parent(child_cat.category_id, root_cat.category_id)
        service.add_category_parent(grand_cat.category_id, child_cat.category_id)
        graph = service.get_graph()
        result = graph_to_dict(graph)
        root_node = result["roots"][0]
        assert len(root_node["children"]) == 1
        child_node = root_node["children"][0]
        assert child_node["category"] == child_cat.model_dump(mode="json")
        assert len(child_node["children"]) == 1
        grand_node = child_node["children"][0]
        assert grand_node["category"] == grand_cat.model_dump(mode="json")
        assert grand_node["children"] == []


class TestGraphToDictMultipleRoots:
    """Multiple top-level root categories."""

    def test_all_roots_present(self, service: TaxomeshService) -> None:
        """All root-level categories appear in roots list."""
        service.create_category(name="Alpha")
        service.create_category(name="Beta")
        service.create_category(name="Gamma")
        graph = service.get_graph()
        result = graph_to_dict(graph)
        assert len(result["roots"]) == 3
        names = {node["category"]["name"] for node in result["roots"]}
        assert names == {"Alpha", "Beta", "Gamma"}


class TestGraphToDictItemsAndChildren:
    """Node with both items and children simultaneously."""

    def test_items_and_children_both_present(self, service: TaxomeshService) -> None:
        """A node with both items and children serializes both correctly."""
        parent = service.create_category(name="Science")
        child = service.create_category(name="Physics")
        service.add_category_parent(child.category_id, parent.category_id)
        item = service.create_item(name="Principia")
        service.place_item_in_category(item.item_id, parent.category_id)
        graph = service.get_graph()
        result = graph_to_dict(graph)
        root_node = result["roots"][0]
        assert len(root_node["items"]) == 1
        assert root_node["items"][0] == item.model_dump(mode="json")
        assert len(root_node["children"]) == 1
        assert root_node["children"][0]["category"] == child.model_dump(mode="json")


class TestGraphToDictJsonSerializable:
    """Output is JSON-serializable for any valid graph."""

    def test_empty_graph_json_safe(self, service: TaxomeshService) -> None:
        """Empty graph output passes json.dumps without raising TypeError."""
        result = graph_to_dict(service.get_graph())
        json.dumps(result)  # must not raise

    def test_populated_graph_json_safe(self, service: TaxomeshService) -> None:
        """Populated graph with categories, items, and children passes json.dumps."""
        cat = service.create_category(name="History")
        child = service.create_category(name="Ancient")
        service.add_category_parent(child.category_id, cat.category_id)
        item = service.create_item(name="Sapiens")
        service.place_item_in_category(item.item_id, cat.category_id)
        result = graph_to_dict(service.get_graph())
        json.dumps(result)  # must not raise
