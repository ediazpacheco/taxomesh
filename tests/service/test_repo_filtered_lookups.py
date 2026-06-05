"""Repository contract tests for 054: get_items_by_ids + list_item_parent_links filters."""

from pathlib import Path
from uuid import UUID

import pytest

from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.adapters.repositories.yaml_repository import YAMLRepository
from taxomesh.domain.models import Category, Item, ItemParentLink
from taxomesh.ports.repository import TaxomeshRepositoryBase
from tests.service.conftest import InMemoryRepository


@pytest.fixture(
    params=["in_memory", "json", "yaml", "django"],
    ids=["in_memory", "json", "yaml", "django"],
)
def repo(request: pytest.FixtureRequest, tmp_path: Path) -> TaxomeshRepositoryBase:
    """Return a fresh raw repository for each backend (no service wrapper).

    Mirrors the backend matrix of the parametrized ``service`` fixture so the
    port contract is verified identically across all four implementations.
    """
    if request.param == "in_memory":
        return InMemoryRepository()
    if request.param == "json":
        return JsonRepository(tmp_path / "test.json")
    if request.param == "yaml":
        return YAMLRepository(tmp_path / "test.yaml")
    # django
    pytest.importorskip("django", reason="django not installed")
    request.getfixturevalue("db")
    from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

    return DjangoRepository()


def _uuid(n: int) -> UUID:
    """Deterministic UUID whose string form sorts in numeric order of n."""
    return UUID(int=n)


def _make_item(n: int, *, enabled: bool = True) -> Item:
    return Item(item_id=_uuid(n), name=f"item-{n:03d}", slug=f"item-{n:03d}", enabled=enabled)


def _make_category(n: int) -> Category:
    return Category(category_id=_uuid(n), name=f"cat-{n:03d}", slug=f"cat-{n:03d}")


# ---------------------------------------------------------------------------
# get_items_by_ids — basic contract
# ---------------------------------------------------------------------------


def test_get_items_by_ids_returns_found_subset(repo: TaxomeshRepositoryBase) -> None:
    items = [_make_item(n) for n in (1, 2, 3)]
    for item in items:
        repo.save_item(item)
    result = repo.get_items_by_ids([_uuid(1), _uuid(3)])
    assert set(result.keys()) == {_uuid(1), _uuid(3)}
    assert result[_uuid(1)].name == "item-001"
    assert result[_uuid(3)].name == "item-003"


def test_get_items_by_ids_missing_ids_silently_absent(repo: TaxomeshRepositoryBase) -> None:
    repo.save_item(_make_item(1))
    result = repo.get_items_by_ids([_uuid(1), _uuid(99)])
    assert set(result.keys()) == {_uuid(1)}


def test_get_items_by_ids_all_missing_returns_empty(repo: TaxomeshRepositoryBase) -> None:
    result = repo.get_items_by_ids([_uuid(98), _uuid(99)])
    assert result == {}


def test_get_items_by_ids_empty_input_returns_empty(repo: TaxomeshRepositoryBase) -> None:
    repo.save_item(_make_item(1))
    assert repo.get_items_by_ids([]) == {}


def test_get_items_by_ids_values_match_get_item(repo: TaxomeshRepositoryBase) -> None:
    repo.save_item(_make_item(7))
    result = repo.get_items_by_ids([_uuid(7)])
    assert result[_uuid(7)] == repo.get_item(_uuid(7))


def test_get_items_by_ids_values_are_item_instances(repo: TaxomeshRepositoryBase) -> None:
    repo.save_item(_make_item(7))
    result = repo.get_items_by_ids([_uuid(7)])
    assert isinstance(result[_uuid(7)], Item)


# ---------------------------------------------------------------------------
# get_items_by_ids — enabled tri-state
# ---------------------------------------------------------------------------


def test_get_items_by_ids_enabled_true(repo: TaxomeshRepositoryBase) -> None:
    repo.save_item(_make_item(1, enabled=True))
    repo.save_item(_make_item(2, enabled=False))
    result = repo.get_items_by_ids([_uuid(1), _uuid(2)], enabled=True)
    assert set(result.keys()) == {_uuid(1)}


def test_get_items_by_ids_enabled_false(repo: TaxomeshRepositoryBase) -> None:
    repo.save_item(_make_item(1, enabled=True))
    repo.save_item(_make_item(2, enabled=False))
    result = repo.get_items_by_ids([_uuid(1), _uuid(2)], enabled=False)
    assert set(result.keys()) == {_uuid(2)}


def test_get_items_by_ids_enabled_none_returns_all(repo: TaxomeshRepositoryBase) -> None:
    repo.save_item(_make_item(1, enabled=True))
    repo.save_item(_make_item(2, enabled=False))
    result = repo.get_items_by_ids([_uuid(1), _uuid(2)], enabled=None)
    assert set(result.keys()) == {_uuid(1), _uuid(2)}


def test_get_items_by_ids_enabled_default_is_none(repo: TaxomeshRepositoryBase) -> None:
    repo.save_item(_make_item(1, enabled=True))
    repo.save_item(_make_item(2, enabled=False))
    result = repo.get_items_by_ids([_uuid(1), _uuid(2)])
    assert set(result.keys()) == {_uuid(1), _uuid(2)}


# ---------------------------------------------------------------------------
# list_item_parent_links — filters
# ---------------------------------------------------------------------------


def _seed_links(repo: TaxomeshRepositoryBase) -> None:
    """Two categories, four items, five links — including a sort_index tie.

    Expected unfiltered order (category_id ASC, sort_index ASC, item_id ASC):
        (item 11, cat 1, idx 0)   <- tie on (cat 1, idx 0), item 11 < 12
        (item 12, cat 1, idx 0)
        (item 13, cat 1, idx 1)
        (item 11, cat 2, idx 0)
        (item 14, cat 2, idx 5)
    """
    for n in (1, 2):
        repo.save_category(_make_category(n))
    for n in (11, 12, 13, 14):
        repo.save_item(_make_item(n))
    # Saved deliberately out of expected order to exercise the ordering contract.
    repo.save_item_parent_link(ItemParentLink(item_id=_uuid(14), category_id=_uuid(2), sort_index=5))
    repo.save_item_parent_link(ItemParentLink(item_id=_uuid(12), category_id=_uuid(1), sort_index=0))
    repo.save_item_parent_link(ItemParentLink(item_id=_uuid(13), category_id=_uuid(1), sort_index=1))
    repo.save_item_parent_link(ItemParentLink(item_id=_uuid(11), category_id=_uuid(2), sort_index=0))
    repo.save_item_parent_link(ItemParentLink(item_id=_uuid(11), category_id=_uuid(1), sort_index=0))


def _as_tuples(links: list[ItemParentLink]) -> list[tuple[UUID, UUID, int]]:
    return [(lnk.item_id, lnk.category_id, lnk.sort_index) for lnk in links]


_EXPECTED_ALL = [
    (_uuid(11), _uuid(1), 0),
    (_uuid(12), _uuid(1), 0),
    (_uuid(13), _uuid(1), 1),
    (_uuid(11), _uuid(2), 0),
    (_uuid(14), _uuid(2), 5),
]


def test_links_no_args_returns_all_in_contract_order(repo: TaxomeshRepositoryBase) -> None:
    _seed_links(repo)
    assert _as_tuples(repo.list_item_parent_links()) == _EXPECTED_ALL


def test_links_item_id_filter(repo: TaxomeshRepositoryBase) -> None:
    _seed_links(repo)
    result = repo.list_item_parent_links(item_id=_uuid(11))
    assert _as_tuples(result) == [(_uuid(11), _uuid(1), 0), (_uuid(11), _uuid(2), 0)]


def test_links_item_id_filter_no_matches(repo: TaxomeshRepositoryBase) -> None:
    _seed_links(repo)
    assert repo.list_item_parent_links(item_id=_uuid(99)) == []


def test_links_category_ids_filter_single(repo: TaxomeshRepositoryBase) -> None:
    _seed_links(repo)
    result = repo.list_item_parent_links(category_ids=[_uuid(2)])
    assert _as_tuples(result) == [(_uuid(11), _uuid(2), 0), (_uuid(14), _uuid(2), 5)]


def test_links_category_ids_filter_multiple_preserves_order(repo: TaxomeshRepositoryBase) -> None:
    _seed_links(repo)
    result = repo.list_item_parent_links(category_ids={_uuid(1), _uuid(2)})
    assert _as_tuples(result) == _EXPECTED_ALL


def test_links_category_ids_empty_collection_returns_empty(repo: TaxomeshRepositoryBase) -> None:
    _seed_links(repo)
    assert repo.list_item_parent_links(category_ids=[]) == []
    assert repo.list_item_parent_links(category_ids=set()) == []


def test_links_both_filters_and_semantics(repo: TaxomeshRepositoryBase) -> None:
    _seed_links(repo)
    result = repo.list_item_parent_links(item_id=_uuid(11), category_ids=[_uuid(2)])
    assert _as_tuples(result) == [(_uuid(11), _uuid(2), 0)]


def test_links_both_filters_disjoint_returns_empty(repo: TaxomeshRepositoryBase) -> None:
    _seed_links(repo)
    assert repo.list_item_parent_links(item_id=_uuid(14), category_ids=[_uuid(1)]) == []


def test_links_filtered_ordering_with_ties(repo: TaxomeshRepositoryBase) -> None:
    _seed_links(repo)
    result = repo.list_item_parent_links(category_ids=[_uuid(1)])
    # Tie on (cat 1, sort_index 0) must order by item_id ASC: 11 before 12.
    assert _as_tuples(result) == [
        (_uuid(11), _uuid(1), 0),
        (_uuid(12), _uuid(1), 0),
        (_uuid(13), _uuid(1), 1),
    ]
