"""A file store is brought to the top-level invariant as it loads, and written that way on the next save.

The invariant: a category holds a link to the implicit root exactly when it holds no other parent
link, and no item is placed in the root. A store written without it loads with it:

- a category holding the root link beside another parent loses the root link;
- a category holding no parent link gains the root link, as ``create`` makes it;
- an item placed in the root loses that placement.

Loading never writes: the file changes with the next save, and a store that already holds the
invariant is not rewritten at all.
"""

import json
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
import yaml

from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.adapters.repositories.yaml_repository import YamlRepository
from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import CategoryParentLink, ItemParentLink

BACKENDS = ("json", "yaml")


def _open(backend: str, path: Path) -> JsonRepository | YamlRepository:
    return JsonRepository(path) if backend == "json" else YamlRepository(path)


def _parents(service: TaxomeshService, category_id: UUID) -> dict[UUID, int]:
    """The parents a category holds a stored link to, with each link's sort index."""
    return {
        lnk.parent_category_id: lnk.sort_index
        for lnk in service.repository.list_category_parent_links(category_ids=[category_id])
    }


def _placements(service: TaxomeshService, item_id: UUID) -> set[UUID]:
    return {lnk.category_id for lnk in service.repository.list_item_parent_links(item_ids=[item_id])}


def _on_disk(backend: str, path: Path) -> tuple[set[tuple[str, str, int]], set[tuple[str, str]]]:
    """The parent links and placements the file holds, read without an adapter, which would fix them."""
    text = path.read_text(encoding="utf-8")
    # Any: the parsed file, indexed by the keys a store writes.
    data: dict[str, Any] = json.loads(text) if backend == "json" else yaml.safe_load(text)
    return (
        {(lnk["category_id"], lnk["parent_category_id"], lnk["sort_index"]) for lnk in data["category_parent_links"]},
        {(lnk["item_id"], lnk["category_id"]) for lnk in data["item_parent_links"]},
    )


class _Store:
    """A store holding every shape the invariant forbids, planted through the repository port."""

    def __init__(self, backend: str, path: Path) -> None:
        service = TaxomeshService(repository=_open(backend, path))
        repository = service.repository
        root_id = service._root_id
        music = service.categories.create("Music")
        jazz = service.categories.create("Jazz")
        service.categories.add_parent(jazz.category_id, music.category_id)
        stray = service.categories.create("Stray")
        lost = service.categories.create("Lost")
        song = service.items.create("Song")
        service.items.place_in(song.item_id, music.category_id)

        # A root link beside another parent.
        repository.save_category_parent_link(
            CategoryParentLink(category_id=jazz.category_id, parent_category_id=root_id, sort_index=3)
        )
        # A category with no link at all.
        repository.delete_category_parent_link(stray.category_id, root_id)
        # A category whose only link names a parent the store does not hold.
        repository.delete_category_parent_link(lost.category_id, root_id)
        repository.save_category_parent_link(
            CategoryParentLink(category_id=lost.category_id, parent_category_id=uuid4())
        )
        # An item placed in the root.
        repository.save_item_parent_link(ItemParentLink(item_id=song.item_id, category_id=root_id))

        self.root_id = root_id
        self.music = music.category_id
        self.jazz = jazz.category_id
        self.stray = stray.category_id
        self.lost = lost.category_id
        self.song = song.item_id


@pytest.mark.parametrize("backend", BACKENDS)
def test_a_store_without_the_invariant_loads_with_it(backend: str, tmp_path: Path) -> None:
    path = tmp_path / f"store.{backend}"
    store = _Store(backend, path)

    service = TaxomeshService(repository=_open(backend, path))

    assert _parents(service, store.jazz) == {store.music: 0}
    assert _parents(service, store.stray) == {store.root_id: 0}
    assert _parents(service, store.lost) == {store.root_id: 0}
    assert _placements(service, store.song) == {store.music}
    assert {c.name for c in service.categories.roots(enabled=None)} == {"Music", "Stray", "Lost"}


@pytest.mark.parametrize("backend", BACKENDS)
def test_loading_writes_nothing_and_the_next_save_writes_the_fix(backend: str, tmp_path: Path) -> None:
    path = tmp_path / f"store.{backend}"
    store = _Store(backend, path)
    written = path.read_bytes()

    service = TaxomeshService(repository=_open(backend, path))
    service.categories.roots(enabled=None)
    service.graph(enabled=None)

    assert path.read_bytes() == written

    service.tags.create("the next save")

    links, placements = _on_disk(backend, path)
    root = str(store.root_id)
    assert {(child, parent) for child, parent, _ in links if child == str(store.jazz)} == {
        (str(store.jazz), str(store.music))
    }
    assert (str(store.stray), root, 0) in links
    assert {(child, parent, index) for child, parent, index in links if child == str(store.lost)} == {
        (str(store.lost), root, 0)
    }
    assert placements == {(str(store.song), str(store.music))}


@pytest.mark.parametrize("backend", BACKENDS)
def test_a_store_that_holds_the_invariant_is_not_rewritten(backend: str, tmp_path: Path) -> None:
    path = tmp_path / f"store.{backend}"
    service = TaxomeshService(repository=_open(backend, path))
    music = service.categories.create("Music")
    for name in ("Jazz", "Tango"):
        child = service.categories.create(name)
        service.categories.add_parent(child.category_id, music.category_id)
    song = service.items.create("Song")
    service.items.place_in(song.item_id, music.category_id)
    service.categories.create("Poetry")
    written = path.read_bytes()

    reopened = TaxomeshService(repository=_open(backend, path))
    reopened.categories.roots(enabled=None)
    reopened.graph(enabled=None)
    reopened.items.list(category=music.category_id)

    assert path.read_bytes() == written
