"""Integration tests for DjangoRepository using SQLite :memory: via pytest-django."""

import builtins
import importlib
import re
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

from django.db import connection  # noqa: E402

from taxomesh import TaxomeshService  # noqa: E402
from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: E402
from taxomesh.adapters.repositories.json_repository import JsonRepository  # noqa: E402
from taxomesh.contrib.django.models import ItemTagLinkModel  # noqa: E402
from taxomesh.domain.models import (  # noqa: E402
    Category,
    CategoryParentLink,
    Item,
    ItemParentLink,
    Tag,
)
from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: E402

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def make_category(**kwargs) -> Category:  # type: ignore[type-arg]
    defaults: dict = dict(category_id=uuid4(), name="Test Category", external_id="ext-1")
    defaults.update(kwargs)
    return Category(**defaults)


def make_item(**kwargs) -> Item:  # type: ignore[type-arg]
    defaults: dict = dict(item_id=uuid4(), external_id="item-ext-1")
    defaults.update(kwargs)
    return Item(**defaults)


def make_tag(**kwargs) -> Tag:  # type: ignore[type-arg]
    defaults: dict = dict(tag_id=uuid4(), name="tagname")
    defaults.update(kwargs)
    return Tag(**defaults)


def make_repo() -> DjangoRepository:
    return DjangoRepository()


# ---------------------------------------------------------------------------
# US1 — Install & Migrate
# ---------------------------------------------------------------------------


def test_migrate_creates_six_tables() -> None:
    table_names = connection.introspection.table_names()
    expected = {
        "taxomesh_category",
        "taxomesh_item",
        "taxomesh_tag",
        "taxomesh_category_parent_link",
        "taxomesh_item_parent_link",
        "taxomesh_item_tag_link",
    }
    assert expected.issubset(set(table_names)), f"Missing tables. Got: {table_names}"


def test_init_raises_repository_error_when_django_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def fake_import(name: str, *args, **kwargs):  # type: ignore[no-untyped-def]
        if name == "django" or name.startswith("django."):
            raise ImportError("mocked: django not found")
        return real_import(name, *args, **kwargs)

    # Remove cached django and taxomesh.contrib.django modules so the deferred import triggers the fake
    evict = [
        k for k in sys.modules if k == "django" or k.startswith("django.") or k.startswith("taxomesh.contrib.django")
    ]
    saved = {k: sys.modules.pop(k) for k in evict}

    import taxomesh.adapters.repositories.django_repository as dr_mod  # noqa: PLC0415

    try:
        monkeypatch.setattr(builtins, "__import__", fake_import)
        importlib.reload(dr_mod)
        with pytest.raises(TaxomeshRepositoryError, match="pip install taxomesh\\[django\\]"):
            dr_mod.DjangoRepository()
    finally:
        sys.modules.update(saved)
        monkeypatch.undo()
        importlib.reload(dr_mod)


def test_get_config_summary_format() -> None:
    repo = make_repo()
    summary = repo.get_config_summary()
    assert re.match(r"^django:\w+/\w+$", summary), f"Unexpected format: {summary!r}"
    lower = summary.lower()
    assert "password" not in lower
    assert "host" not in lower
    assert "port" not in lower


# ---------------------------------------------------------------------------
# US2 — Category CRUD
# ---------------------------------------------------------------------------


def test_save_and_get_category() -> None:
    repo = make_repo()
    cat = make_category(name="Books", description="All books", enabled=True)
    repo.save_category(cat)
    result = repo.get_category(cat.category_id)
    assert result is not None
    assert result.category_id == cat.category_id
    assert result.name == "Books"
    assert result.description == "All books"
    assert result.enabled is True


def test_get_category_missing_returns_none() -> None:
    repo = make_repo()
    assert repo.get_category(uuid4()) is None


def test_list_categories_returns_all() -> None:
    repo = make_repo()
    cat1 = make_category(name="Books")
    cat2 = make_category(name="Music")
    repo.save_category(cat1)
    repo.save_category(cat2)
    ids = {c.category_id for c in repo.list_categories()}
    assert cat1.category_id in ids
    assert cat2.category_id in ids


def test_list_categories_empty() -> None:
    repo = make_repo()
    assert repo.list_categories() == []


def test_delete_category_returns_true() -> None:
    repo = make_repo()
    cat = make_category()
    repo.save_category(cat)
    assert repo.delete_category(cat.category_id) is True
    assert repo.get_category(cat.category_id) is None


def test_delete_category_missing_returns_false() -> None:
    repo = make_repo()
    assert repo.delete_category(uuid4()) is False


def test_save_category_upserts_on_repeat_call() -> None:
    repo = make_repo()
    cat = make_category(name="Original")
    repo.save_category(cat)
    updated = Category(**{**cat.model_dump(), "name": "Updated"})
    repo.save_category(updated)
    categories = repo.list_categories()
    assert len(categories) == 1
    assert categories[0].name == "Updated"


def test_external_id_uuid_round_trip() -> None:
    repo = make_repo()
    eid = uuid4()
    cat = make_category(external_id=eid)
    repo.save_category(cat)
    result = repo.get_category(cat.category_id)
    assert result is not None
    assert isinstance(result.external_id, str)
    assert result.external_id == str(eid)


def test_external_id_int_round_trip() -> None:
    repo = make_repo()
    cat = make_category(external_id=42)
    repo.save_category(cat)
    result = repo.get_category(cat.category_id)
    assert result is not None
    assert isinstance(result.external_id, str)
    assert result.external_id == "42"


def test_external_id_str_round_trip() -> None:
    repo = make_repo()
    cat = make_category(external_id="my-slug")
    repo.save_category(cat)
    result = repo.get_category(cat.category_id)
    assert result is not None
    assert isinstance(result.external_id, str)
    assert result.external_id == "my-slug"


# ---------------------------------------------------------------------------
# US3 — Item & Tag CRUD
# ---------------------------------------------------------------------------


def test_save_and_get_item() -> None:
    repo = make_repo()
    item = make_item(external_id="my-item")
    repo.save_item(item)
    result = repo.get_item(item.item_id)
    assert result is not None
    assert result.item_id == item.item_id
    assert result.external_id == "my-item"


def test_get_item_missing_returns_none() -> None:
    repo = make_repo()
    assert repo.get_item(uuid4()) is None


def test_list_items_returns_all() -> None:
    repo = make_repo()
    i1 = make_item(external_id="a")
    i2 = make_item(external_id="b")
    repo.save_item(i1)
    repo.save_item(i2)
    ids = {i.item_id for i in repo.list_items()}
    assert i1.item_id in ids
    assert i2.item_id in ids


def test_delete_item_returns_true() -> None:
    repo = make_repo()
    item = make_item()
    repo.save_item(item)
    assert repo.delete_item(item.item_id) is True
    assert repo.get_item(item.item_id) is None


def test_delete_item_missing_returns_false() -> None:
    repo = make_repo()
    assert repo.delete_item(uuid4()) is False


def test_item_external_id_uuid_round_trip() -> None:
    repo = make_repo()
    eid = uuid4()
    item = make_item(external_id=eid)
    repo.save_item(item)
    result = repo.get_item(item.item_id)
    assert result is not None
    assert isinstance(result.external_id, str)
    assert result.external_id == str(eid)


def test_item_external_id_int_round_trip() -> None:
    repo = make_repo()
    item = make_item(external_id=99)
    repo.save_item(item)
    result = repo.get_item(item.item_id)
    assert result is not None
    assert isinstance(result.external_id, str)
    assert result.external_id == "99"


def test_save_and_get_tag() -> None:
    repo = make_repo()
    tag = make_tag(name="fiction")
    repo.save_tag(tag)
    result = repo.get_tag(tag.tag_id)
    assert result is not None
    assert result.tag_id == tag.tag_id
    assert result.name == "fiction"


def test_get_tag_missing_returns_none() -> None:
    repo = make_repo()
    assert repo.get_tag(uuid4()) is None


def test_list_tags_returns_all() -> None:
    repo = make_repo()
    t1 = make_tag(name="scifi")
    t2 = make_tag(name="history")
    repo.save_tag(t1)
    repo.save_tag(t2)
    ids = {t.tag_id for t in repo.list_tags()}
    assert t1.tag_id in ids
    assert t2.tag_id in ids


def test_delete_tag_returns_true() -> None:
    repo = make_repo()
    tag = make_tag()
    repo.save_tag(tag)
    assert repo.delete_tag(tag.tag_id) is True
    assert repo.get_tag(tag.tag_id) is None


def test_delete_tag_missing_returns_false() -> None:
    repo = make_repo()
    assert repo.delete_tag(uuid4()) is False


def test_assign_tag_links_tag_to_item() -> None:
    repo = make_repo()
    tag = make_tag()
    item = make_item()
    repo.save_tag(tag)
    repo.save_item(item)
    repo.assign_tag(tag.tag_id, item.item_id)
    count = ItemTagLinkModel.objects.filter(tag_id=tag.tag_id, item_id=item.item_id).count()
    assert count == 1


def test_assign_tag_is_idempotent() -> None:
    repo = make_repo()
    tag = make_tag()
    item = make_item()
    repo.save_tag(tag)
    repo.save_item(item)
    repo.assign_tag(tag.tag_id, item.item_id)
    repo.assign_tag(tag.tag_id, item.item_id)  # second call — must not create duplicate
    count = ItemTagLinkModel.objects.filter(tag_id=tag.tag_id, item_id=item.item_id).count()
    assert count == 1


def test_remove_tag_returns_true() -> None:
    repo = make_repo()
    tag = make_tag()
    item = make_item()
    repo.save_tag(tag)
    repo.save_item(item)
    repo.assign_tag(tag.tag_id, item.item_id)
    assert repo.remove_tag(tag.tag_id, item.item_id) is True


def test_remove_tag_missing_returns_false() -> None:
    repo = make_repo()
    assert repo.remove_tag(uuid4(), uuid4()) is False


# ---------------------------------------------------------------------------
# US4 — Parent Links
# ---------------------------------------------------------------------------


def test_save_category_parent_link_and_list() -> None:
    repo = make_repo()
    parent = make_category(name="Parent")
    child = make_category(name="Child")
    repo.save_category(parent)
    repo.save_category(child)
    link = CategoryParentLink(category_id=child.category_id, parent_category_id=parent.category_id, sort_index=1)
    repo.save_category_parent_link(link)
    links = repo.list_category_parent_links()
    assert any(lnk.category_id == child.category_id and lnk.parent_category_id == parent.category_id for lnk in links)


def test_save_category_parent_link_upserts_sort_index() -> None:
    repo = make_repo()
    parent = make_category(name="Parent")
    child = make_category(name="Child")
    repo.save_category(parent)
    repo.save_category(child)
    link1 = CategoryParentLink(category_id=child.category_id, parent_category_id=parent.category_id, sort_index=0)
    link2 = CategoryParentLink(category_id=child.category_id, parent_category_id=parent.category_id, sort_index=5)
    repo.save_category_parent_link(link1)
    repo.save_category_parent_link(link2)
    links = repo.list_category_parent_links()
    matching = [
        lnk for lnk in links if lnk.category_id == child.category_id and lnk.parent_category_id == parent.category_id
    ]
    assert len(matching) == 1
    assert matching[0].sort_index == 5


def test_list_category_parent_links_empty() -> None:
    repo = make_repo()
    assert repo.list_category_parent_links() == []


def test_delete_category_cascades_parent_link() -> None:
    repo = make_repo()
    parent = make_category(name="Parent")
    child = make_category(name="Child")
    repo.save_category(parent)
    repo.save_category(child)
    link = CategoryParentLink(category_id=child.category_id, parent_category_id=parent.category_id)
    repo.save_category_parent_link(link)
    repo.delete_category(child.category_id)
    assert repo.list_category_parent_links() == []


def test_save_item_parent_link_and_list() -> None:
    repo = make_repo()
    cat = make_category(name="Sci-Fi")
    item = make_item(external_id="book-1")
    repo.save_category(cat)
    repo.save_item(item)
    link = ItemParentLink(item_id=item.item_id, category_id=cat.category_id, sort_index=0)
    repo.save_item_parent_link(link)
    links = repo.list_item_parent_links()
    assert any(lnk.item_id == item.item_id and lnk.category_id == cat.category_id for lnk in links)


def test_save_item_parent_link_upserts_sort_index() -> None:
    repo = make_repo()
    cat = make_category()
    item = make_item()
    repo.save_category(cat)
    repo.save_item(item)
    repo.save_item_parent_link(ItemParentLink(item_id=item.item_id, category_id=cat.category_id, sort_index=0))
    repo.save_item_parent_link(ItemParentLink(item_id=item.item_id, category_id=cat.category_id, sort_index=7))
    links = [lnk for lnk in repo.list_item_parent_links() if lnk.item_id == item.item_id]
    assert len(links) == 1
    assert links[0].sort_index == 7


def test_list_item_parent_links_empty() -> None:
    repo = make_repo()
    assert repo.list_item_parent_links() == []


# ---------------------------------------------------------------------------
# US5 — Full Graph
# ---------------------------------------------------------------------------


def test_get_graph_empty_repository() -> None:
    repo = make_repo()
    svc = TaxomeshService(repository=repo)
    graph = svc.get_graph()
    # Only the internal root category exists — no user-created categories, so roots is empty
    assert len(graph.roots) == 0


def test_get_graph_returns_correct_structure() -> None:
    repo = make_repo()
    svc = TaxomeshService(repository=repo)

    parent = svc.create_category("ParentCat")
    child = svc.create_category("ChildCat")
    svc.add_category_parent(child.category_id, parent.category_id)
    item = svc.create_item("test-item", "test-item")
    svc.place_item_in_category(item.item_id, parent.category_id)
    tag = svc.create_tag("fiction")
    svc.assign_tag(tag.tag_id, item.item_id)

    graph = svc.get_graph()

    def _collect_names(nodes: list) -> set:  # type: ignore[type-arg]
        names: set[str] = set()
        for node in nodes:
            names.add(node.category.name)
            names |= _collect_names(node.children)
        return names

    all_names = _collect_names(graph.roots)
    assert "ParentCat" in all_names
    assert "ChildCat" in all_names


def test_get_graph_structure_matches_json_repository() -> None:
    """US5-AC2: DjangoRepository and JsonRepository produce identical graph category sets."""

    def _collect_names(nodes: list) -> set:  # type: ignore[type-arg]
        names: set[str] = set()
        for node in nodes:
            names.add(node.category.name)
            names |= _collect_names(node.children)
        return names

    def _build_taxonomy(svc: TaxomeshService) -> set[str]:
        parent = svc.create_category("Alpha")
        child = svc.create_category("Beta")
        svc.add_category_parent(child.category_id, parent.category_id)
        item = svc.create_item("item-x", "item-x")
        svc.place_item_in_category(item.item_id, parent.category_id)
        tag = svc.create_tag("t1")
        svc.assign_tag(tag.tag_id, item.item_id)
        return _collect_names(svc.get_graph().roots)

    # DjangoRepository backend
    django_names = _build_taxonomy(TaxomeshService(repository=make_repo()))

    # JsonRepository backend (temp file, discarded after test)
    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = Path(tmpdir) / "taxomesh.json"
        json_names = _build_taxonomy(TaxomeshService(repository=JsonRepository(json_path)))

    assert django_names == json_names


# ---------------------------------------------------------------------------
# Slug save/retrieve and lookup tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_save_and_retrieve_item_with_slug() -> None:
    from taxomesh.domain.models import Item  # noqa: PLC0415

    repo = make_repo()
    item = Item(external_id="ext-slug", slug="my-item-slug")
    repo.save_item(item)
    loaded = repo.get_item(item.item_id)
    assert loaded is not None
    assert loaded.slug == "my-item-slug"


@pytest.mark.django_db
def test_save_and_retrieve_category_with_slug() -> None:
    from taxomesh.domain.models import Category  # noqa: PLC0415

    repo = make_repo()
    cat = Category(name="Slugged", slug="slugged-cat")
    repo.save_category(cat)
    loaded = repo.get_category(cat.category_id)
    assert loaded is not None
    assert loaded.slug == "slugged-cat"


@pytest.mark.django_db
def test_get_item_by_slug_found() -> None:
    from taxomesh.domain.models import Item  # noqa: PLC0415

    repo = make_repo()
    item = Item(external_id="ext-1", slug="find-me")
    repo.save_item(item)
    found = repo.get_item_by_slug("find-me")
    assert found is not None
    assert found.item_id == item.item_id


@pytest.mark.django_db
def test_get_item_by_slug_not_found() -> None:
    repo = make_repo()
    assert repo.get_item_by_slug("no-such-slug") is None


@pytest.mark.django_db
def test_get_category_by_slug_found() -> None:
    from taxomesh.domain.models import Category  # noqa: PLC0415

    repo = make_repo()
    cat = Category(name="FindMe", slug="find-cat")
    repo.save_category(cat)
    found = repo.get_category_by_slug("find-cat")
    assert found is not None
    assert found.category_id == cat.category_id


@pytest.mark.django_db
def test_get_category_by_slug_not_found() -> None:
    repo = make_repo()
    assert repo.get_category_by_slug("no-such-slug") is None
