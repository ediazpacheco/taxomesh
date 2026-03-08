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


class TestShowRelations:
    """Tests for the --show-relations flag on the graph command (T004)."""

    def _make_service_with_relation(self) -> tuple[object, object, object]:
        """Return (service, item_a, item_b) with an outgoing 'covers' relation from a to b."""
        from taxomesh.application.service import TaxomeshService  # noqa: PLC0415
        from tests.service.conftest import InMemoryRepository  # noqa: PLC0415

        repo = InMemoryRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.create_category(name="Music")
        item_a = svc.create_item(name="Alpha")
        item_b = svc.create_item(name="Beta")
        svc.place_item_in_category(item_a.item_id, cat.category_id)
        svc.place_item_in_category(item_b.item_id, cat.category_id)
        svc.relate_items(item_a.item_id, item_b.item_id, "covers")
        return svc, item_a, item_b

    def _render_graph_cmd(self, args: list[str], svc: object) -> str:
        """Invoke graph_cmd via CliRunner with the given args and a patched service."""
        from unittest.mock import MagicMock, patch  # noqa: PLC0415

        from typer.testing import CliRunner  # noqa: PLC0415

        from taxomesh.adapters.cli.main import app  # noqa: PLC0415

        runner = CliRunner()
        build_result = MagicMock()
        build_result.service = svc
        with patch("taxomesh.adapters.cli.main.build", return_value=build_result):
            result = runner.invoke(app, ["graph"] + args)
        return result.output

    def test_graph_no_show_relations_omits_relation_lines(self) -> None:
        """--no-show-relations flag must suppress relation type → target lines."""
        svc, _item_a, _item_b = self._make_service_with_relation()
        output = self._render_graph_cmd(["--no-show-relations"], svc)
        assert "covers" not in output
        assert "→" not in output

    def test_graph_show_relations_prints_relation_lines(self) -> None:
        """--show-relations flag must print [relation_type] → target_name for each relation."""
        svc, _item_a, _item_b = self._make_service_with_relation()
        output = self._render_graph_cmd(["--show-relations"], svc)
        assert "covers" in output
        assert "Beta" in output

    def test_graph_show_relations_no_op_when_no_relations(self) -> None:
        """--show-relations with no relations present must not add extra lines."""
        from taxomesh.application.service import TaxomeshService  # noqa: PLC0415
        from tests.service.conftest import InMemoryRepository  # noqa: PLC0415

        repo = InMemoryRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.create_category(name="Music")
        item = svc.create_item(name="Alpha")
        svc.place_item_in_category(item.item_id, cat.category_id)

        output_without_flag = self._render_graph_cmd([], svc)
        output_with_flag = self._render_graph_cmd(["--show-relations"], svc)
        # Both outputs should contain the item name but no relation markers
        assert "Alpha" in output_without_flag
        assert "Alpha" in output_with_flag
        assert "→" not in output_with_flag

    def test_graph_shows_relations_by_default(self) -> None:
        """With no --show-relations flag, relations are shown by default (T028)."""
        svc, _item_a, _item_b = self._make_service_with_relation()
        output = self._render_graph_cmd([], svc)
        assert "covers" in output
        assert "Beta" in output


class TestMaxDepth:
    """Tests for the --max-depth flag on the graph command (T004)."""

    def _make_deep_service(self) -> object:
        """Return a service with a 5-level taxonomy: L0 > L1 > L2 > L3 > L4, each with one item."""
        from taxomesh.application.service import TaxomeshService  # noqa: PLC0415
        from tests.service.conftest import InMemoryRepository  # noqa: PLC0415

        repo = InMemoryRepository()
        svc = TaxomeshService(repository=repo)
        l0 = svc.create_category(name="L0")
        l1 = svc.create_category(name="L1")
        l2 = svc.create_category(name="L2")
        l3 = svc.create_category(name="L3")
        l4 = svc.create_category(name="L4")
        svc.add_category_parent(l1.category_id, l0.category_id)
        svc.add_category_parent(l2.category_id, l1.category_id)
        svc.add_category_parent(l3.category_id, l2.category_id)
        svc.add_category_parent(l4.category_id, l3.category_id)
        for lvl, cat in enumerate([l0, l1, l2, l3, l4]):
            item = svc.create_item(name=f"Item{lvl}")
            svc.place_item_in_category(item.item_id, cat.category_id)
        return svc

    def _render_graph_cmd(self, args: list[str], svc: object) -> str:
        """Invoke graph_cmd via CliRunner with a patched service."""
        from unittest.mock import MagicMock, patch  # noqa: PLC0415

        from typer.testing import CliRunner  # noqa: PLC0415

        from taxomesh.adapters.cli.main import app  # noqa: PLC0415

        runner = CliRunner()
        build_result = MagicMock()
        build_result.service = svc
        with patch("taxomesh.adapters.cli.main.build", return_value=build_result):
            result = runner.invoke(app, ["graph"] + args)
        return result.output

    def test_graph_default_max_depth_hides_deep_nodes(self) -> None:
        """Default graph (max-depth=3) must omit nodes at depth > 3 (L3 items, L4 and its items)."""
        svc = self._make_deep_service()
        output = self._render_graph_cmd([], svc)
        # L3 category at depth 3 is included (depth 3 == max_depth), but its items at depth 4 are excluded
        # L4 category at depth 4 is excluded entirely
        assert "L3" in output, "L3 (depth 3) must appear in default output"
        assert "L4" not in output, "L4 (depth 4) must be hidden in default output"
        assert "Item3" not in output, "Item at depth 4 must be hidden in default output"
        assert "Item4" not in output, "Item at depth 5 must be hidden in default output"

    def test_graph_max_depth_zero_shows_all_nodes(self) -> None:
        """--max-depth 0 (unlimited) must render all nodes including the deepest."""
        svc = self._make_deep_service()
        output = self._render_graph_cmd(["--max-depth", "0"], svc)
        assert "L4" in output
        assert "Item4" in output

    def test_graph_max_depth_one_shows_only_root_categories(self) -> None:
        """--max-depth 1 shows root categories + their direct items but no child categories."""
        svc = self._make_deep_service()
        output = self._render_graph_cmd(["--max-depth", "1"], svc)
        assert "L0" in output
        assert "Item0" in output  # item inside L0 (depth 1) is shown (depth 1 == max_depth, not > it)
        assert "L1" in output  # L1 (child of L0) is at depth 1; child recurse at depth 1 (0+1=1 > 1 False)
        assert "Item1" not in output  # item inside L1 (depth 2) is hidden (1+1=2 > 1 True)
        assert "L2" not in output  # L2 (child of L1) is at depth 2; hidden (1+1=2 > 1 True)

    def test_graph_show_relations_respects_max_depth(self) -> None:
        """--show-relations with --max-depth must only show relations for items within the depth limit."""
        from taxomesh.application.service import TaxomeshService  # noqa: PLC0415
        from tests.service.conftest import InMemoryRepository  # noqa: PLC0415

        repo = InMemoryRepository()
        svc = TaxomeshService(repository=repo)
        l0 = svc.create_category(name="L0")
        l1 = svc.create_category(name="L1")
        svc.add_category_parent(l1.category_id, l0.category_id)
        shallow_item = svc.create_item(name="ShallowItem")
        deep_item = svc.create_item(name="DeepItem")
        other_item = svc.create_item(name="OtherItem")
        svc.place_item_in_category(shallow_item.item_id, l0.category_id)
        svc.place_item_in_category(deep_item.item_id, l1.category_id)
        svc.place_item_in_category(other_item.item_id, l0.category_id)
        svc.relate_items(shallow_item.item_id, other_item.item_id, "covers")
        svc.relate_items(deep_item.item_id, other_item.item_id, "linked")

        # max-depth 1: L0 visible, items at depth 1 visible; L1 (depth 1) visible but its items at depth 2 hidden
        output = self._render_graph_cmd(["--max-depth", "1", "--show-relations"], svc)
        assert "ShallowItem" in output
        # DeepItem is an item inside L1 (depth 1 category → item at depth 2), hidden
        assert "DeepItem" not in output
        # "linked" relation belongs to DeepItem which is hidden
        assert "linked" not in output
