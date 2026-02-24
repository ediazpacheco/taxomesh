"""Tests for the bundled example YAML data file (US3 — 007-yaml-repository)."""

from pathlib import Path

from taxomesh.adapters.repositories.yaml_repository import YAMLRepository
from taxomesh.application.service import TaxomeshService
from taxomesh.domain.graph import CategoryNode

EXAMPLE = Path(__file__).parent.parent / "examples" / "taxomesh_example.yaml"


def _max_depth(node: CategoryNode) -> int:
    """Return the maximum depth of the subtree rooted at node (node itself = depth 1)."""
    if not node.children:
        return 1
    return 1 + max(_max_depth(child) for child in node.children)


def test_example_file_exists() -> None:
    assert EXAMPLE.exists(), f"Example file not found: {EXAMPLE}"


def test_example_file_loads_without_error() -> None:
    YAMLRepository(EXAMPLE)


def test_example_file_has_at_least_six_categories() -> None:
    repo = YAMLRepository(EXAMPLE)
    # root + ≥5 top-level = ≥6 total category records
    cats = repo.list_categories()
    assert len(cats) >= 6, f"Expected ≥6 categories, got {len(cats)}"


def test_example_file_graph_has_at_least_five_roots() -> None:
    repo = YAMLRepository(EXAMPLE)
    svc = TaxomeshService(repository=repo)
    graph = svc.get_graph()
    assert len(graph.roots) >= 5, f"Expected ≥5 root nodes, got {len(graph.roots)}"


def test_example_file_graph_has_four_level_deep_chain() -> None:
    repo = YAMLRepository(EXAMPLE)
    svc = TaxomeshService(repository=repo)
    graph = svc.get_graph()
    max_chain = max((_max_depth(node) for node in graph.roots), default=0)
    assert max_chain >= 4, f"Expected at least one chain of depth ≥4, got max depth {max_chain}"
