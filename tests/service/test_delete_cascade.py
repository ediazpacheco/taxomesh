"""A delete takes every link that names the deleted row with it, on every backend.

After a category, an item or a tag is deleted, no stored link names it and no read meets a link
to a row that is gone. The file backends also drop, as they load a store, any link naming a row the
store does not hold, and write the store without it on the next save.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.adapters.repositories.yaml_repository import YamlRepository
from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import (
    Category,
    CategoryParentLink,
    Item,
    ItemParentLink,
    ItemRelationLink,
    ItemTagLink,
    Tag,
)
from taxomesh.ports.repository import TaxomeshRepositoryBase

type Link = CategoryParentLink | ItemParentLink | ItemTagLink | ItemRelationLink


@dataclass(frozen=True)
class Scene:
    """Every kind of link, around rows that each sit at both ends of something.

    ``middle`` is a child of ``top`` and the parent of ``bottom``, and holds ``placed``.
    ``placed`` carries both tags, relates to ``other`` and is related from ``third``.
    """

    top: Category
    middle: Category
    bottom: Category
    placed: Item
    other: Item
    third: Item
    tango: Tag
    lunfardo: Tag

    @property
    def categories(self) -> tuple[Category, ...]:
        return (self.top, self.middle, self.bottom)

    @property
    def items(self) -> tuple[Item, ...]:
        return (self.placed, self.other, self.third)

    @property
    def tags(self) -> tuple[Tag, ...]:
        return (self.tango, self.lunfardo)


def _scene(service: TaxomeshService) -> Scene:
    top = service.categories.create("Top")
    middle = service.categories.create("Middle")
    bottom = service.categories.create("Bottom")
    service.categories.add_parent(middle.category_id, top.category_id)
    service.categories.add_parent(bottom.category_id, middle.category_id)
    placed = service.items.create("Placed")
    other = service.items.create("Other")
    third = service.items.create("Third")
    service.items.place_in(placed.item_id, middle.category_id)
    service.items.place_in(other.item_id, bottom.category_id)
    tango = service.tags.create("tango")
    lunfardo = service.tags.create("lunfardo")
    service.items.tag(placed.item_id, tango.tag_id)
    service.items.tag(placed.item_id, lunfardo.tag_id)
    service.items.tag(other.item_id, tango.tag_id)
    service.items.relate(placed.item_id, other.item_id, "covers")
    service.items.relate(third.item_id, placed.item_id, "samples")
    service.items.relate(third.item_id, other.item_id, "covers")
    return Scene(top, middle, bottom, placed, other, third, tango, lunfardo)


def _links_naming(repository: TaxomeshRepositoryBase, row_id: UUID) -> list[Link]:
    """Return every stored link with this identifier at either end."""
    return [
        *(
            lnk
            for lnk in repository.list_category_parent_links()
            if row_id in (lnk.category_id, lnk.parent_category_id)
        ),
        *(lnk for lnk in repository.list_item_parent_links() if row_id in (lnk.item_id, lnk.category_id)),
        *(lnk for lnk in repository.list_item_tag_links() if row_id in (lnk.item_id, lnk.tag_id)),
        *repository.list_item_relation_links(row_id, direction="both"),
    ]


def _read_everything(service: TaxomeshService, scene: Scene, *, deleted: UUID | None = None) -> None:
    """Run every read that could meet a link to a row that is gone, addressing only stored rows."""
    service.categories.roots(enabled=None)
    service.graph(enabled=None)
    for category in scene.categories:
        if category.category_id == deleted:
            continue
        service.categories.list(parent=category.category_id, enabled=None)
        service.categories.search("o", parent=category.category_id, enabled=None)
        for recursive in (False, True):
            service.items.list(category=category.category_id, recursive=recursive, enabled=None)
            service.items.search("e", category=category.category_id, recursive=recursive, enabled=None)
    survivors = [item.item_id for item in scene.items if item.item_id != deleted]
    for item_id in survivors:
        service.categories.list(item=item_id, enabled=None)
        service.tags.list(item=item_id)
        service.items.list_relations(item_id, direction="both")
        service.items.list_related(item_id, direction="both", enabled=None)
    service.items.get_many_related(survivors, direction="both", enabled=None)
    for tag in scene.tags:
        if tag.tag_id != deleted:
            service.items.list(tag=tag.tag_id, enabled=None)


def _names(rows: Sequence[Category] | Sequence[Item] | Sequence[Tag]) -> list[str]:
    return [row.name for row in rows]


class TestDeletingACategory:
    def test_no_link_names_it_and_no_read_raises(
        self, service: TaxomeshService, caplog: pytest.LogCaptureFixture
    ) -> None:
        scene = _scene(service)

        service.categories.delete(scene.middle.category_id)

        assert _links_naming(service.repository, scene.middle.category_id) == []
        with caplog.at_level(logging.WARNING):
            _read_everything(service, scene, deleted=scene.middle.category_id)
        assert [record.getMessage() for record in caplog.records if record.levelno >= logging.WARNING] == []

    def test_the_links_of_other_rows_stay(self, service: TaxomeshService) -> None:
        scene = _scene(service)

        service.categories.delete(scene.middle.category_id)

        assert service.categories.list(parent=scene.top.category_id) == ()
        assert service.categories.list(item=scene.placed.item_id) == ()
        assert _names(service.items.list(category=scene.bottom.category_id)) == ["Other"]
        assert _names(service.tags.list(item=scene.placed.item_id)) == ["lunfardo", "tango"]


class TestDeletingAnItem:
    def test_no_link_names_it_and_no_read_raises(
        self, service: TaxomeshService, caplog: pytest.LogCaptureFixture
    ) -> None:
        scene = _scene(service)

        service.items.delete(scene.placed.item_id)

        assert _links_naming(service.repository, scene.placed.item_id) == []
        with caplog.at_level(logging.WARNING):
            _read_everything(service, scene, deleted=scene.placed.item_id)
        assert [record.getMessage() for record in caplog.records if record.levelno >= logging.WARNING] == []

    def test_the_links_of_other_rows_stay(self, service: TaxomeshService) -> None:
        scene = _scene(service)

        service.items.delete(scene.placed.item_id)

        assert service.items.list(category=scene.middle.category_id) == ()
        assert _names(service.items.list(tag=scene.tango.tag_id)) == ["Other"]
        assert service.items.list(tag=scene.lunfardo.tag_id) == ()
        assert _names(service.items.list_related(scene.third.item_id)) == ["Other"]
        assert _names(service.items.list(category=scene.bottom.category_id)) == ["Other"]


class TestDeletingATag:
    def test_no_link_names_it_and_no_read_raises(
        self, service: TaxomeshService, caplog: pytest.LogCaptureFixture
    ) -> None:
        scene = _scene(service)

        service.tags.delete(scene.tango.tag_id)

        assert _links_naming(service.repository, scene.tango.tag_id) == []
        with caplog.at_level(logging.WARNING):
            _read_everything(service, scene, deleted=scene.tango.tag_id)
        assert [record.getMessage() for record in caplog.records if record.levelno >= logging.WARNING] == []

    def test_the_links_of_other_rows_stay(self, service: TaxomeshService) -> None:
        scene = _scene(service)

        service.tags.delete(scene.tango.tag_id)

        assert _names(service.tags.list(item=scene.placed.item_id)) == ["lunfardo"]
        assert service.tags.list(item=scene.other.item_id) == ()
        assert _names(service.items.list(tag=scene.lunfardo.tag_id)) == ["Placed"]


def _open(backend: str, path: Path) -> JsonRepository | YamlRepository:
    return JsonRepository(path) if backend == "json" else YamlRepository(path)


@pytest.mark.parametrize("backend", ["json", "yaml"])
def test_links_naming_a_row_not_stored_are_dropped_on_load_and_on_the_next_save(backend: str, tmp_path: Path) -> None:
    """A store holding links to rows it does not hold loads without them, and loses them on disk too."""
    path = tmp_path / f"store.{backend}"
    service = TaxomeshService(repository=_open(backend, path))
    scene = _scene(service)
    gone = [uuid4() for _ in range(8)]
    repository = service.repository
    repository.save_category_parent_link(
        CategoryParentLink(category_id=gone[0], parent_category_id=scene.top.category_id)
    )
    repository.save_category_parent_link(
        CategoryParentLink(category_id=scene.bottom.category_id, parent_category_id=gone[1])
    )
    repository.save_item_parent_link(ItemParentLink(item_id=gone[2], category_id=scene.middle.category_id))
    repository.save_item_parent_link(ItemParentLink(item_id=scene.other.item_id, category_id=gone[3]))
    repository.add_item_tag_link(gone[4], scene.tango.tag_id)
    repository.add_item_tag_link(scene.other.item_id, gone[5])
    repository.save_item_relation_link(
        ItemRelationLink(source_item_id=gone[6], target_item_id=scene.other.item_id, relation_type="covers")
    )
    repository.save_item_relation_link(
        ItemRelationLink(source_item_id=scene.third.item_id, target_item_id=gone[7], relation_type="covers")
    )
    assert all(str(row_id) in path.read_text(encoding="utf-8") for row_id in gone)

    reopened = TaxomeshService(repository=_open(backend, path))

    assert [lnk for row_id in gone for lnk in _links_naming(reopened.repository, row_id)] == []
    _read_everything(reopened, scene)
    assert all(str(row_id) in path.read_text(encoding="utf-8") for row_id in gone)

    reopened.tags.create("the next save")

    assert not any(str(row_id) in path.read_text(encoding="utf-8") for row_id in gone)
