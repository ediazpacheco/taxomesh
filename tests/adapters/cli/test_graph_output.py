"""Tests for CLI graph output rendering."""

from uuid import uuid4

from rich.console import Console
from rich.tree import Tree

from taxomesh.adapters.cli.main import _add_graph_node
from taxomesh.domain.graph import CategoryNode
from taxomesh.domain.models import Category, Item


def _render_tree(category_node: CategoryNode) -> str:
    """Render a CategoryNode to a plain-text string via Rich."""
    tree = Tree("Taxonomy")
    _add_graph_node(tree, category_node)
    console = Console(force_terminal=True, no_color=True, width=200)
    with console.capture() as capture:
        console.print(tree)
    return capture.get()


def _make_category(
    *,
    enabled: bool = True,
    external_id: str = "",
    slug: str = "",
) -> Category:
    """Create a Category with minimal required fields."""
    return Category(category_id=uuid4(), name="TestCat", enabled=enabled, external_id=external_id, slug=slug)


def _make_item(*, enabled: bool = True, external_id: str = "item-1", slug: str = "", name: str = "TestItem") -> Item:
    """Create an Item with minimal required fields."""
    return Item(name=name, external_id=external_id, enabled=enabled, slug=slug)


class TestItemEnabledIcon:
    def test_enabled_item_shows_check_icon(self) -> None:
        node = CategoryNode(category=_make_category(), items=[_make_item(enabled=True)], children=[])
        output = _render_tree(node)
        assert "✓" in output
        assert "enabled=True" not in output

    def test_disabled_item_shows_cross_icon(self) -> None:
        node = CategoryNode(category=_make_category(), items=[_make_item(enabled=False)], children=[])
        output = _render_tree(node)
        assert "✗" in output
        assert "enabled=False" not in output


class TestCategoryEnabledIcon:
    def test_enabled_category_shows_check_icon(self) -> None:
        node = CategoryNode(category=_make_category(enabled=True), items=[], children=[])
        output = _render_tree(node)
        assert "✓" in output

    def test_disabled_category_shows_cross_icon(self) -> None:
        node = CategoryNode(category=_make_category(enabled=False), items=[], children=[])
        output = _render_tree(node)
        assert "✗" in output


class TestCategoryExternalId:
    def test_category_external_id_shown_in_graph(self) -> None:
        # Category.__str__ includes external_id when non-empty
        node = CategoryNode(
            category=_make_category(external_id="genre-rock"),
            items=[],
            children=[],
        )
        output = _render_tree(node)
        assert "genre-rock" in output

    def test_category_with_empty_external_id_omits_it(self) -> None:
        node = CategoryNode(
            category=_make_category(external_id=""),
            items=[],
            children=[],
        )
        output = _render_tree(node)
        lines = output.strip().split("\n")
        cat_line = lines[1]  # first child line under "Taxonomy"
        assert "genre-rock" not in cat_line


class TestSlugRendering:
    def test_category_with_slug_renders_slug_and_uuid(self) -> None:
        cat = _make_category(slug="my-cat")
        node = CategoryNode(category=cat, items=[], children=[])
        output = _render_tree(node)
        assert "my-cat" in output
        assert str(cat.category_id) in output

    def test_category_without_slug_renders_uuid_only(self) -> None:
        cat = _make_category(slug="")
        node = CategoryNode(category=cat, items=[], children=[])
        output = _render_tree(node)
        assert str(cat.category_id) in output
        # No slug segment present when slug is empty
        assert "s:" not in output

    def test_item_with_slug_renders_slug_and_uuid(self) -> None:
        item = _make_item(slug="my-item")
        node = CategoryNode(category=_make_category(), items=[item], children=[])
        output = _render_tree(node)
        assert "my-item" in output
        assert str(item.item_id) in output

    def test_item_without_slug_renders_uuid_only(self) -> None:
        item = _make_item(slug="")
        node = CategoryNode(category=_make_category(), items=[item], children=[])
        output = _render_tree(node)
        assert str(item.item_id) in output
