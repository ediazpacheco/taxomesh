"""What the two file stores share: the file itself.

``JsonRepository`` and ``YamlRepository`` hold the whole store in one file, written again in full on
every write through a temporary file and ``os.replace``. They are one store with two formats: a
private base holds the whole port, and each adapter says only how its text becomes data and back.
These tests cover that file: creating it, refusing one that cannot be read, loading a document with
sections missing, and reading back after a reopen what each write stored. The port's own behaviour
is asserted for every implementation in ``test_repository_contract.py``.
"""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final, Literal
from uuid import UUID

import pytest
import yaml

from taxomesh.adapters.repositories._file import FileRepositoryBase
from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.adapters.repositories.yaml_repository import YamlRepository
from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import (
    Category,
    CategoryParentLink,
    Item,
    ItemParentLink,
    ItemRelationLink,
    Tag,
)
from taxomesh.exceptions import TaxomeshCyclicDependencyError, TaxomeshRepositoryError
from taxomesh.ports.repository import TaxomeshRepositoryBase
from tests.surface._surface import public_names

type FileKind = Literal["json", "yaml"]
type FileRepository = JsonRepository | YamlRepository

# Text each format fails to parse.
_UNPARSEABLE: Final[dict[FileKind, str]] = {
    "json": "this is not valid json!!!",
    "yaml": ": invalid: yaml: {{{{\n",
}


def _uuid(n: int) -> UUID:
    return UUID(int=n)


def _open(kind: FileKind, path: Path) -> FileRepository:
    """Open the store at ``path``, as a process does when it starts."""
    return JsonRepository(path) if kind == "json" else YamlRepository(path)


def _dump(kind: FileKind, document: Mapping[str, object]) -> str:
    return json.dumps(document) if kind == "json" else yaml.safe_dump(document)


# Any: the parser answers whatever the text holds.
def _read(kind: FileKind, path: Path) -> Any:
    """The document the file holds, as parsed text."""
    text = path.read_text(encoding="utf-8")
    return json.loads(text) if kind == "json" else yaml.safe_load(text)


@pytest.fixture(params=["json", "yaml"])
def kind(request: pytest.FixtureRequest) -> FileKind:
    """Each file format."""
    file_kind: FileKind = request.param
    return file_kind


@pytest.fixture
def path(kind: FileKind, tmp_path: Path) -> Path:
    """A store's path, with no file there yet."""
    return tmp_path / f"store.{kind}"


class TestOneBase:
    """Each port member is written once, on the base; an adapter adds only its format."""

    def test_the_base_holds_every_port_member(self) -> None:
        missing = [name for name in public_names(TaxomeshRepositoryBase) if name not in vars(FileRepositoryBase)]
        assert missing == []

    @pytest.mark.parametrize("adapter", [JsonRepository, YamlRepository])
    def test_an_adapter_defines_only_its_constructor_and_its_format(self, adapter: type[FileRepositoryBase]) -> None:
        own = {name for name, value in vars(adapter).items() if callable(value) or isinstance(value, property)}
        assert issubclass(adapter, FileRepositoryBase)
        assert own == {"__init__", "_parse", "_render"}


class TestTheFile:
    """Opening a store creates its file, and a file that cannot be a store is refused."""

    def test_opening_creates_the_file_and_its_directories(self, kind: FileKind, tmp_path: Path) -> None:
        path = tmp_path / "nested" / "deep" / f"store.{kind}"
        _open(kind, path)
        assert path.is_file()

    def test_a_directory_is_refused(self, kind: FileKind, tmp_path: Path) -> None:
        with pytest.raises(TaxomeshRepositoryError):
            _open(kind, tmp_path)

    def test_text_the_format_cannot_parse_is_refused(self, kind: FileKind, path: Path) -> None:
        path.write_text(_UNPARSEABLE[kind], encoding="utf-8")
        with pytest.raises(TaxomeshRepositoryError):
            _open(kind, path)

    def test_a_document_other_than_a_mapping_is_refused(self, kind: FileKind, path: Path) -> None:
        path.write_text("[1, 2, 3]", encoding="utf-8")
        with pytest.raises(TaxomeshRepositoryError):
            _open(kind, path)

    def test_a_missing_section_loads_empty(self, kind: FileKind, path: Path) -> None:
        path.write_text(_dump(kind, {"categories": {}}), encoding="utf-8")
        repo = _open(kind, path)
        assert repo.list_items() == []
        assert repo.list_tags() == []
        assert repo.list_item_tag_links() == []
        assert repo.list_category_parent_links() == []
        assert repo.list_item_parent_links() == []
        assert repo.list_item_relation_links(_uuid(1)) == []

    def test_a_null_description_loads_as_empty(self, kind: FileKind, path: Path) -> None:
        category_id = str(_uuid(1))
        document = {"categories": {category_id: {"category_id": category_id, "name": "X", "description": None}}}
        path.write_text(_dump(kind, document), encoding="utf-8")
        stored = _open(kind, path).find_category(_uuid(1))
        assert stored is not None
        assert stored.description == ""

    def test_the_summary_names_the_file(self, kind: FileKind, path: Path) -> None:
        assert str(path) in _open(kind, path).config_summary

    def test_no_temporary_file_is_left(self, kind: FileKind, path: Path) -> None:
        svc = TaxomeshService(repository=_open(kind, path))
        svc.categories.create(name="Clean")
        svc.items.create(name="x", external_id="x")
        assert [p.name for p in path.parent.iterdir()] == [path.name]


class TestEveryWriteReachesTheFile:
    """Each write is in the file when it returns, with no save step."""

    def test_rows(self, kind: FileKind, path: Path) -> None:
        repo = _open(kind, path)
        repo.save_category(Category(category_id=_uuid(1), name="C"))
        repo.save_tag(Tag(tag_id=_uuid(2), name="t"))
        document = _read(kind, path)
        assert str(_uuid(1)) in document["categories"]
        assert str(_uuid(2)) in document["tags"]

        repo.delete_category(_uuid(1))
        repo.delete_tag(_uuid(2))
        document = _read(kind, path)
        assert str(_uuid(1)) not in document["categories"]
        assert str(_uuid(2)) not in document["tags"]

    def test_links(self, kind: FileKind, path: Path) -> None:
        repo = _open(kind, path)
        repo.save_category(Category(category_id=_uuid(1), name="C"))
        repo.save_item(Item(item_id=_uuid(2), name="A"))
        repo.save_item(Item(item_id=_uuid(3), name="B"))
        repo.save_tag(Tag(tag_id=_uuid(4), name="t"))
        repo.save_item_parent_link(ItemParentLink(item_id=_uuid(2), category_id=_uuid(1)))
        repo.add_item_tag_link(_uuid(2), _uuid(4))
        repo.save_item_relation_link(
            ItemRelationLink(source_item_id=_uuid(2), target_item_id=_uuid(3), relation_type="covers")
        )
        document = _read(kind, path)
        assert len(document["item_parent_links"]) == 1
        assert len(document["item_tag_links"]) == 1
        assert [link["relation_type"] for link in document["item_relation_links"]] == ["covers"]

        repo.delete_item_tag_link(_uuid(2), _uuid(4))
        assert _read(kind, path)["item_tag_links"] == []


class TestAReopenedStore:
    """What a store held when its process ended is what the next process reads."""

    def test_rows_come_back_equal(self, kind: FileKind, path: Path) -> None:
        repo = _open(kind, path)
        category = repo.save_category(
            Category(category_id=_uuid(1), name="Books", slug="books", external_id="b", metadata={"k": [1, 2]})
        )
        item = repo.save_item(Item(item_id=_uuid(2), name="Item", slug="my-item", external_id="ext-1"))
        tag = Tag(tag_id=_uuid(3), name="fiction")
        repo.save_tag(tag)

        reopened = _open(kind, path)
        assert reopened.find_category(_uuid(1)) == category
        assert reopened.find_item(_uuid(2)) == item
        assert reopened.find_tag(_uuid(3)) == tag

    def test_links_come_back_with_their_last_sort_index(self, kind: FileKind, path: Path) -> None:
        repo = _open(kind, path)
        for n in (1, 2):
            repo.save_category(Category(category_id=_uuid(n), name=f"C{n}"))
        repo.save_item(Item(item_id=_uuid(3), name="I"))
        repo.save_tag(Tag(tag_id=_uuid(4), name="t"))
        for sort_index in (0, 10):
            repo.save_category_parent_link(
                CategoryParentLink(category_id=_uuid(1), parent_category_id=_uuid(2), sort_index=sort_index)
            )
        repo.save_item_parent_link(ItemParentLink(item_id=_uuid(3), category_id=_uuid(2), sort_index=3))
        repo.add_item_tag_link(_uuid(3), _uuid(4))

        reopened = _open(kind, path)
        parent_links = reopened.list_category_parent_links(category_ids=[_uuid(1)])
        assert [(lnk.parent_category_id, lnk.sort_index) for lnk in parent_links] == [(_uuid(2), 10)]
        assert [(lnk.category_id, lnk.sort_index) for lnk in reopened.list_item_parent_links()] == [(_uuid(2), 3)]
        assert [(lnk.item_id, lnk.tag_id) for lnk in reopened.list_item_tag_links()] == [(_uuid(3), _uuid(4))]

    def test_relations_come_back_with_every_field(self, kind: FileKind, path: Path) -> None:
        svc = TaxomeshService(repository=_open(kind, path))
        author = svc.items.create(name="Author")
        peer = svc.items.create(name="Peer")
        work = svc.items.create(name="Work")
        svc.items.relate(author.item_id, peer.item_id, "worked_with", sort_index=1)
        svc.items.relate(author.item_id, peer.item_id, "worked_with", sort_index=7, metadata={"k": "v"})
        svc.items.relate(work.item_id, author.item_id, "lyrics_by")

        reopened = TaxomeshService(repository=_open(kind, path))
        both = reopened.items.list_relations(author.item_id, direction="both")
        assert {(lnk.source_item_id, lnk.target_item_id, lnk.relation_type) for lnk in both} == {
            (author.item_id, peer.item_id, "worked_with"),
            (work.item_id, author.item_id, "lyrics_by"),
        }
        (outgoing,) = reopened.items.list_relations(author.item_id)
        assert (outgoing.sort_index, outgoing.metadata) == (7, {"k": "v"})

    def test_a_delete_stays_done_with_the_links_it_took(self, kind: FileKind, path: Path) -> None:
        svc = TaxomeshService(repository=_open(kind, path))
        source = svc.items.create(name="A")
        target = svc.items.create(name="B")
        svc.items.relate(source.item_id, target.item_id, "covers")
        svc.items.delete(source.item_id)

        reopened = TaxomeshService(repository=_open(kind, path))
        assert reopened.items.list_relations(target.item_id, direction="incoming") == ()

    def test_the_parent_links_still_refuse_a_cycle(self, kind: FileKind, path: Path) -> None:
        svc = TaxomeshService(repository=_open(kind, path))
        child = svc.categories.create(name="A")
        parent = svc.categories.create(name="B")
        svc.categories.add_parent(child.category_id, parent.category_id)

        reopened = TaxomeshService(repository=_open(kind, path))
        with pytest.raises(TaxomeshCyclicDependencyError):
            reopened.categories.add_parent(parent.category_id, child.category_id)
