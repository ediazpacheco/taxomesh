"""Tests for CLI graph output rendering."""

import sys
from collections.abc import Sequence
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from click.testing import Result
from rich.console import Console
from rich.tree import Tree
from typer.testing import CliRunner

from taxomesh.adapters.cli.main import CYCLE_MARK, MAX_DEPTH_UNLIMITED, _draw_graph, app
from taxomesh.application.service import TaxomeshService
from taxomesh.domain.graph import CategoryNode, TaxomeshGraph
from taxomesh.domain.models import Category, CategoryParentLink, Item
from tests.service.conftest import CountingRepository, InMemoryRepository


def _render_tree(category_node: CategoryNode) -> str:
    """Render a CategoryNode to a plain-text string via Rich."""
    tree = Tree("Taxonomy")
    _draw_graph(tree, [category_node])
    console = Console(force_terminal=True, no_color=True, width=200)
    with console.capture() as capture:
        console.print(tree)
    return capture.get()


def _make_category(
    *,
    enabled: bool = True,
    external_id: str | None = None,
    slug: str = "",
) -> Category:
    """Create a Category with minimal required fields."""
    return Category(category_id=uuid4(), name="TestCat", enabled=enabled, external_id=external_id, slug=slug)


def _make_item(
    *, enabled: bool = True, external_id: str | None = "item-1", slug: str = "", name: str = "TestItem"
) -> Item:
    """Create an Item with minimal required fields."""
    return Item(name=name, external_id=external_id, enabled=enabled, slug=slug)


def _single_node(category: Category, items: Sequence[Item] = ()) -> CategoryNode:
    """Return the node of a one-category graph — the smallest thing the renderer is given.

    A node is a view over a graph's flat storage, so it is not built on its own; the renderer
    only ever receives one that came from a graph. These tests render a single category, which
    is the one-category graph built here.
    """
    graph = TaxomeshGraph(
        categories={category.category_id: category},
        children={},
        parents={},
        items={category.category_id: list(items)},
        roots=[category.category_id],
    )
    return graph[category.category_id]


class TestItemEnabledIcon:
    def test_enabled_item_shows_check_icon(self) -> None:
        node = _single_node(_make_category(), [_make_item(enabled=True)])
        output = _render_tree(node)
        assert "✓" in output
        assert "enabled=True" not in output

    def test_disabled_item_shows_cross_icon(self) -> None:
        node = _single_node(_make_category(), [_make_item(enabled=False)])
        output = _render_tree(node)
        assert "✗" in output
        assert "enabled=False" not in output


class TestCategoryEnabledIcon:
    def test_enabled_category_shows_check_icon(self) -> None:
        node = _single_node(_make_category(enabled=True))
        output = _render_tree(node)
        assert "✓" in output

    def test_disabled_category_shows_cross_icon(self) -> None:
        node = _single_node(_make_category(enabled=False))
        output = _render_tree(node)
        assert "✗" in output


class TestCategoryExternalId:
    def test_category_external_id_shown_in_graph(self) -> None:
        # Category.__str__ includes external_id when not None
        node = _single_node(_make_category(external_id="genre-rock"))
        output = _render_tree(node)
        assert "genre-rock" in output

    def test_category_with_none_external_id_omits_it(self) -> None:
        node = _single_node(_make_category(external_id=None))
        output = _render_tree(node)
        lines = output.strip().split("\n")
        cat_line = lines[1]  # first child line under "Taxonomy"
        assert "genre-rock" not in cat_line


class TestSlugRendering:
    def test_category_with_slug_renders_slug_and_uuid(self) -> None:
        cat = _make_category(slug="my-cat")
        node = _single_node(cat)
        output = _render_tree(node)
        assert "my-cat" in output
        assert str(cat.category_id) in output

    def test_category_without_slug_renders_uuid_only(self) -> None:
        cat = _make_category(slug="")
        node = _single_node(cat)
        output = _render_tree(node)
        assert str(cat.category_id) in output
        # No slug segment present when slug is empty
        assert "s:" not in output

    def test_item_with_slug_renders_slug_and_uuid(self) -> None:
        item = _make_item(slug="my-item")
        node = _single_node(_make_category(), [item])
        output = _render_tree(node)
        assert "my-item" in output
        assert str(item.item_id) in output

    def test_item_without_slug_renders_uuid_only(self) -> None:
        item = _make_item(slug="")
        node = _single_node(_make_category(), [item])
        output = _render_tree(node)
        assert str(item.item_id) in output


class TestShowRelations:
    """Tests for the --show-relations flag on the graph command."""

    def _make_service_with_relation(self) -> tuple[object, object, object]:
        """Return (service, item_a, item_b) with an outgoing 'covers' relation from a to b."""
        from taxomesh.application.service import TaxomeshService  # noqa: PLC0415
        from tests.service.conftest import InMemoryRepository  # noqa: PLC0415

        repo = InMemoryRepository()
        svc = TaxomeshService(repository=repo)
        cat = svc.categories.create(name="Music")
        item_a = svc.items.create(name="Alpha")
        item_b = svc.items.create(name="Beta")
        svc.items.place_in(item_a.item_id, cat.category_id)
        svc.items.place_in(item_b.item_id, cat.category_id)
        svc.items.relate(item_a.item_id, item_b.item_id, "covers")
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
        cat = svc.categories.create(name="Music")
        item = svc.items.create(name="Alpha")
        svc.items.place_in(item.item_id, cat.category_id)

        output_without_flag = self._render_graph_cmd([], svc)
        output_with_flag = self._render_graph_cmd(["--show-relations"], svc)
        # Both outputs should contain the item name but no relation markers
        assert "Alpha" in output_without_flag
        assert "Alpha" in output_with_flag
        assert "→" not in output_with_flag

    def test_graph_shows_relations_by_default(self) -> None:
        """With no --show-relations flag, relations are shown by default."""
        svc, _item_a, _item_b = self._make_service_with_relation()
        output = self._render_graph_cmd([], svc)
        assert "covers" in output
        assert "Beta" in output


class TestMaxDepth:
    """Tests for the --max-depth flag on the graph command."""

    def _make_deep_service(self) -> object:
        """Return a service with a 5-level taxonomy: L0 > L1 > L2 > L3 > L4, each with one item."""
        from taxomesh.application.service import TaxomeshService  # noqa: PLC0415
        from tests.service.conftest import InMemoryRepository  # noqa: PLC0415

        repo = InMemoryRepository()
        svc = TaxomeshService(repository=repo)
        l0 = svc.categories.create(name="L0")
        l1 = svc.categories.create(name="L1")
        l2 = svc.categories.create(name="L2")
        l3 = svc.categories.create(name="L3")
        l4 = svc.categories.create(name="L4")
        svc.categories.add_parent(l1.category_id, l0.category_id)
        svc.categories.add_parent(l2.category_id, l1.category_id)
        svc.categories.add_parent(l3.category_id, l2.category_id)
        svc.categories.add_parent(l4.category_id, l3.category_id)
        for lvl, cat in enumerate([l0, l1, l2, l3, l4]):
            item = svc.items.create(name=f"Item{lvl}")
            svc.items.place_in(item.item_id, cat.category_id)
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
        """--max-depth 1 shows top-level categories + their direct items but no child categories."""
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
        l0 = svc.categories.create(name="L0")
        l1 = svc.categories.create(name="L1")
        svc.categories.add_parent(l1.category_id, l0.category_id)
        shallow_item = svc.items.create(name="ShallowItem")
        deep_item = svc.items.create(name="DeepItem")
        other_item = svc.items.create(name="OtherItem")
        svc.items.place_in(shallow_item.item_id, l0.category_id)
        svc.items.place_in(deep_item.item_id, l1.category_id)
        svc.items.place_in(other_item.item_id, l0.category_id)
        svc.items.relate(shallow_item.item_id, other_item.item_id, "covers")
        svc.items.relate(deep_item.item_id, other_item.item_id, "linked")

        # max-depth 1: L0 visible, items at depth 1 visible; L1 (depth 1) visible but its items at depth 2 hidden
        output = self._render_graph_cmd(["--max-depth", "1", "--show-relations"], svc)
        assert "ShallowItem" in output
        # DeepItem is an item inside L1 (depth 1 category → item at depth 2), hidden
        assert "DeepItem" not in output
        # "linked" relation belongs to DeepItem which is hidden
        assert "linked" not in output


def _graph_output(svc: TaxomeshService, args: list[str]) -> tuple[int, str]:
    """Run ``taxomesh graph`` over the given service and return its exit code and output."""
    build_result = MagicMock()
    build_result.service = svc
    with patch("taxomesh.adapters.cli.main.build", return_value=build_result):
        result = CliRunner().invoke(app, ["graph", *args])
    assert not isinstance(result.exception, RecursionError), "the drawing recursed without bound"
    return result.exit_code, result.output


def _service_with_a_stored_cycle() -> TaxomeshService:
    """R at the top level, A under R, B under A, and A under B: a cycle only a direct port write stores."""
    repo = InMemoryRepository()
    svc = TaxomeshService(repository=repo)
    r = svc.categories.create(name="R")
    a = svc.categories.create(name="A")
    b = svc.categories.create(name="B")
    svc.categories.add_parent(a, r)
    svc.categories.add_parent(b, a)
    repo.save_category_parent_link(
        CategoryParentLink(category_id=a.category_id, parent_category_id=b.category_id, sort_index=0)
    )
    svc._cache.clear()
    return svc


class TestTheDrawingTerminates:
    """``taxomesh graph`` ends on any stored shape, at every ``--max-depth``, ``0`` included."""

    @pytest.mark.parametrize("args", [[], ["--max-depth", "3"], ["--max-depth", "0"]], ids=["default", "3", "0"])
    def test_a_stored_cycle_is_drawn_once_and_marked(self, args: list[str]) -> None:
        """A category already on the path is shown, marked, and not descended into."""
        code, output = _graph_output(_service_with_a_stored_cycle(), args)

        assert code == 0
        assert output.count(CYCLE_MARK) == 1
        cycle_line = next(line for line in output.splitlines() if CYCLE_MARK in line)
        assert "A (id:" in cycle_line
        assert output.count("A (id:") == 2

    def test_a_chain_deeper_than_the_recursion_limit_is_drawn(self) -> None:
        """Without a depth limit, a chain longer than the interpreter's recursion limit is drawn whole.

        The chain is drawn onto a tree rather than printed: printing it is Rich's work, and Rich
        prints a tree without recursing.
        """
        repo = InMemoryRepository()
        svc = TaxomeshService(repository=repo)
        top = svc.categories.create(name="C0")
        length = sys.getrecursionlimit() + 500
        previous = top
        for index in range(1, length + 1):
            current = repo.save_category(Category(name=f"C{index}"))
            repo.save_category_parent_link(
                CategoryParentLink(
                    category_id=current.category_id, parent_category_id=previous.category_id, sort_index=0
                )
            )
            previous = current

        tree = Tree("Taxonomy")
        _draw_graph(tree, svc.graph().roots, max_depth=MAX_DEPTH_UNLIMITED)

        depth, branch = 0, tree
        while branch.children:
            (branch,) = branch.children
            depth += 1
        assert depth == length + 1
        assert CYCLE_MARK not in str(branch.label)


class TestRelationsAreReadInOneBatch:
    """The items' relations are read once for every item drawn, not once per item."""

    def test_one_batch_read_for_every_drawn_item(self) -> None:
        reads = CountingRepository(InMemoryRepository())
        svc = TaxomeshService(repository=reads)
        music = svc.categories.create(name="Music")
        jazz = svc.categories.create(name="Jazz")
        svc.categories.add_parent(jazz, music)
        items = [svc.items.create(name=f"Item{index}") for index in range(5)]
        for item in items[:3]:
            svc.items.place_in(item, music)
        for item in items[3:]:
            svc.items.place_in(item, jazz)
        for source, target in zip(items, items[1:], strict=False):
            svc.items.relate(source, target, "next")
        reads.reset()

        code, output = _graph_output(svc, [])

        assert code == 0
        assert output.count("[next] →") == 4
        assert reads.count_of("list_item_relation_links_batch") == 1
        assert reads.count_of("list_item_relation_links") == 0

    def test_no_relation_read_without_relations_shown(self) -> None:
        reads = CountingRepository(InMemoryRepository())
        svc = TaxomeshService(repository=reads)
        music = svc.categories.create(name="Music")
        item = svc.items.create(name="Alpha")
        svc.items.place_in(item, music)
        reads.reset()

        code, _ = _graph_output(svc, ["--no-show-relations"])

        assert code == 0
        assert reads.count_of("list_item_relation_links_batch") == 0
        assert reads.count_of("list_item_relation_links") == 0


def _stacked_diamonds(levels: int) -> TaxomeshService:
    """A top category, then ``levels`` diamonds stacked below it, each closed by one category.

    Each diamond's two sides share the category below them, so drawing every path doubles the
    rows at each level: the store holds ``3 * levels + 1`` categories, and the tree
    ``2 ** (levels + 2) - 3`` branches.
    """
    svc = TaxomeshService(repository=InMemoryRepository())
    bottom = svc.categories.create(name="T0")
    for level in range(1, levels + 1):
        left = svc.categories.create(name=f"A{level}")
        right = svc.categories.create(name=f"B{level}")
        joined = svc.categories.create(name=f"T{level}")
        for side in (left, right):
            svc.categories.add_parent(side, bottom)
            svc.categories.add_parent(joined, side)
        bottom = joined
    return svc


class TestTheDrawingHasANodeBudget:
    """``taxomesh graph`` stops past the serializer's node budget and names ``--max-depth``.

    Four stacked diamonds draw 61 branches at ``--max-depth 0``; the budget is lowered to 20 so the
    store stays small.
    """

    @staticmethod
    def _draw(args: list[str]) -> Result:
        build_result = MagicMock()
        build_result.service = _stacked_diamonds(4)
        with (
            patch("taxomesh.adapters.cli.main.build", return_value=build_result),
            patch("taxomesh.adapters.cli.main.MAX_EMITTED_NODES", 20),
        ):
            return CliRunner().invoke(app, ["graph", *args])

    def test_past_the_budget_the_drawing_stops(self) -> None:
        result = self._draw(["--max-depth", "0"])

        assert result.exit_code == 1
        assert "Taxonomy" not in result.stdout
        assert "--max-depth" in result.stderr

    def test_within_the_budget_the_same_store_is_drawn(self) -> None:
        """The default depth draws nine branches of the same store."""
        result = self._draw([])

        assert result.exit_code == 0
        assert result.stdout.count("(id:") == 9
