"""Tests for YAMLRepository persistence behaviour (US1 — 007-yaml-repository)."""

from pathlib import Path
from uuid import uuid4

import pytest
import yaml

from taxomesh.adapters.repositories.yaml_repository import YAMLRepository
from taxomesh.domain.models import Category, CategoryParentLink, Item, ItemParentLink, Tag
from taxomesh.exceptions import TaxomeshRepositoryError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_yaml_path(tmp_path: Path) -> Path:
    """Return a path for a YAML repo file that does not exist yet."""
    return tmp_path / "taxomesh_test.yaml"


# ---------------------------------------------------------------------------
# Init behaviour
# ---------------------------------------------------------------------------


def test_init_creates_file_when_not_exists(tmp_yaml_path: Path) -> None:
    assert not tmp_yaml_path.exists()
    YAMLRepository(tmp_yaml_path)
    assert tmp_yaml_path.exists()


def test_init_loads_existing_valid_file(tmp_yaml_path: Path) -> None:
    repo1 = YAMLRepository(tmp_yaml_path)
    cat = Category(category_id=uuid4(), name="Persisted")
    repo1.save_category(cat)

    repo2 = YAMLRepository(tmp_yaml_path)
    result = repo2.get_category(cat.category_id)
    assert result is not None
    assert result.name == "Persisted"


def test_init_raises_on_directory_path(tmp_path: Path) -> None:
    with pytest.raises(TaxomeshRepositoryError):
        YAMLRepository(tmp_path)


def test_init_raises_on_invalid_yaml(tmp_yaml_path: Path) -> None:
    tmp_yaml_path.write_text(": invalid: yaml: {{{{\n", encoding="utf-8")
    with pytest.raises(TaxomeshRepositoryError):
        YAMLRepository(tmp_yaml_path)


def test_init_empty_file_treated_as_empty_taxonomy(tmp_yaml_path: Path) -> None:
    tmp_yaml_path.write_text("", encoding="utf-8")
    repo = YAMLRepository(tmp_yaml_path)
    assert repo.list_categories() == []
    assert repo.list_items() == []
    assert repo.list_tags() == []
    assert repo.list_category_parent_links() == []
    assert repo.list_item_parent_links() == []


def test_init_missing_top_level_keys_treated_as_empty(tmp_yaml_path: Path) -> None:
    tmp_yaml_path.write_text("categories: {}\n", encoding="utf-8")
    repo = YAMLRepository(tmp_yaml_path)
    assert repo.list_items() == []
    assert repo.list_tags() == []
    assert repo.list_category_parent_links() == []
    assert repo.list_item_parent_links() == []


def test_init_creates_parent_directories(tmp_path: Path) -> None:
    nested = tmp_path / "nested" / "deep" / "taxomesh.yaml"
    assert not nested.parent.exists()
    YAMLRepository(nested)
    assert nested.exists()


# ---------------------------------------------------------------------------
# Category CRUD
# ---------------------------------------------------------------------------


def test_save_and_get_category(tmp_yaml_path: Path) -> None:
    repo = YAMLRepository(tmp_yaml_path)
    cat = Category(category_id=uuid4(), name="Animals")
    repo.save_category(cat)
    assert repo.get_category(cat.category_id) == cat


def test_list_categories(tmp_yaml_path: Path) -> None:
    repo = YAMLRepository(tmp_yaml_path)
    c1 = Category(category_id=uuid4(), name="A")
    c2 = Category(category_id=uuid4(), name="B")
    repo.save_category(c1)
    repo.save_category(c2)
    ids = {c.category_id for c in repo.list_categories()}
    assert c1.category_id in ids
    assert c2.category_id in ids


def test_delete_category_returns_true(tmp_yaml_path: Path) -> None:
    repo = YAMLRepository(tmp_yaml_path)
    cat = Category(category_id=uuid4(), name="Gone")
    repo.save_category(cat)
    assert repo.delete_category(cat.category_id) is True
    assert repo.get_category(cat.category_id) is None


def test_delete_category_missing_returns_false(tmp_yaml_path: Path) -> None:
    repo = YAMLRepository(tmp_yaml_path)
    assert repo.delete_category(uuid4()) is False


# ---------------------------------------------------------------------------
# Item CRUD
# ---------------------------------------------------------------------------


def test_save_and_get_item(tmp_yaml_path: Path) -> None:
    repo = YAMLRepository(tmp_yaml_path)
    item = Item(external_id="lion")
    repo.save_item(item)
    assert repo.get_item(item.item_id) == item


def test_list_items(tmp_yaml_path: Path) -> None:
    repo = YAMLRepository(tmp_yaml_path)
    i1 = Item(external_id="lion")
    i2 = Item(external_id="tiger")
    repo.save_item(i1)
    repo.save_item(i2)
    ids = {i.item_id for i in repo.list_items()}
    assert i1.item_id in ids
    assert i2.item_id in ids


def test_delete_item_returns_true(tmp_yaml_path: Path) -> None:
    repo = YAMLRepository(tmp_yaml_path)
    item = Item(external_id="gone")
    repo.save_item(item)
    assert repo.delete_item(item.item_id) is True
    assert repo.get_item(item.item_id) is None


def test_delete_item_missing_returns_false(tmp_yaml_path: Path) -> None:
    repo = YAMLRepository(tmp_yaml_path)
    assert repo.delete_item(uuid4()) is False


# ---------------------------------------------------------------------------
# Tag CRUD
# ---------------------------------------------------------------------------


def test_save_and_get_tag(tmp_yaml_path: Path) -> None:
    repo = YAMLRepository(tmp_yaml_path)
    tag = Tag(tag_id=uuid4(), name="wild")
    repo.save_tag(tag)
    assert repo.get_tag(tag.tag_id) == tag


def test_list_tags(tmp_yaml_path: Path) -> None:
    repo = YAMLRepository(tmp_yaml_path)
    t1 = Tag(tag_id=uuid4(), name="a")
    t2 = Tag(tag_id=uuid4(), name="b")
    repo.save_tag(t1)
    repo.save_tag(t2)
    ids = {t.tag_id for t in repo.list_tags()}
    assert t1.tag_id in ids
    assert t2.tag_id in ids


def test_delete_tag_returns_true(tmp_yaml_path: Path) -> None:
    repo = YAMLRepository(tmp_yaml_path)
    tag = Tag(tag_id=uuid4(), name="bye")
    repo.save_tag(tag)
    assert repo.delete_tag(tag.tag_id) is True
    assert repo.get_tag(tag.tag_id) is None


def test_delete_tag_missing_returns_false(tmp_yaml_path: Path) -> None:
    repo = YAMLRepository(tmp_yaml_path)
    assert repo.delete_tag(uuid4()) is False


# ---------------------------------------------------------------------------
# Tag ↔ Item associations
# ---------------------------------------------------------------------------


def test_assign_tag_links_tag_to_item(tmp_yaml_path: Path) -> None:
    repo = YAMLRepository(tmp_yaml_path)
    tag_id = uuid4()
    item_id = uuid4()
    repo.assign_tag(tag_id, item_id)
    raw = yaml.safe_load(tmp_yaml_path.read_text(encoding="utf-8"))
    assert len(raw["item_tag_links"]) == 1


def test_assign_tag_is_idempotent(tmp_yaml_path: Path) -> None:
    repo = YAMLRepository(tmp_yaml_path)
    tag_id = uuid4()
    item_id = uuid4()
    repo.assign_tag(tag_id, item_id)
    repo.assign_tag(tag_id, item_id)
    raw = yaml.safe_load(tmp_yaml_path.read_text(encoding="utf-8"))
    assert len(raw["item_tag_links"]) == 1


def test_remove_tag_returns_true(tmp_yaml_path: Path) -> None:
    repo = YAMLRepository(tmp_yaml_path)
    tag_id = uuid4()
    item_id = uuid4()
    repo.assign_tag(tag_id, item_id)
    assert repo.remove_tag(tag_id, item_id) is True
    raw = yaml.safe_load(tmp_yaml_path.read_text(encoding="utf-8"))
    assert len(raw["item_tag_links"]) == 0


def test_remove_tag_missing_returns_false(tmp_yaml_path: Path) -> None:
    repo = YAMLRepository(tmp_yaml_path)
    assert repo.remove_tag(uuid4(), uuid4()) is False


# ---------------------------------------------------------------------------
# Category parent links
# ---------------------------------------------------------------------------


def test_save_category_parent_link_and_list(tmp_yaml_path: Path) -> None:
    repo = YAMLRepository(tmp_yaml_path)
    link = CategoryParentLink(category_id=uuid4(), parent_category_id=uuid4(), sort_index=1)
    repo.save_category_parent_link(link)
    links = repo.list_category_parent_links()
    assert len(links) == 1
    assert links[0].category_id == link.category_id
    assert links[0].sort_index == 1


# ---------------------------------------------------------------------------
# Item parent links
# ---------------------------------------------------------------------------


def test_save_item_parent_link_upserts_sort_index(tmp_yaml_path: Path) -> None:
    repo = YAMLRepository(tmp_yaml_path)
    item_id = uuid4()
    cat_id = uuid4()
    repo.save_item_parent_link(ItemParentLink(item_id=item_id, category_id=cat_id, sort_index=1))
    repo.save_item_parent_link(ItemParentLink(item_id=item_id, category_id=cat_id, sort_index=99))
    links = repo.list_item_parent_links()
    assert len(links) == 1
    assert links[0].sort_index == 99


def test_list_item_parent_links(tmp_yaml_path: Path) -> None:
    repo = YAMLRepository(tmp_yaml_path)
    assert repo.list_item_parent_links() == []
    link = ItemParentLink(item_id=uuid4(), category_id=uuid4(), sort_index=0)
    repo.save_item_parent_link(link)
    assert len(repo.list_item_parent_links()) == 1


# ---------------------------------------------------------------------------
# Config summary
# ---------------------------------------------------------------------------


def test_get_config_summary_returns_path_string(tmp_yaml_path: Path) -> None:
    repo = YAMLRepository(tmp_yaml_path)
    summary = repo.get_config_summary()
    assert summary != ""
    assert str(tmp_yaml_path) in summary
