"""A row a caller holds never changes, and no two calls share a result, on all four backends.

``update`` returns a new row and storage replaces the one it had, so every row read before the
update, whether by subscript, from a listing or through a graph, keeps the values it was read
with. A repository's ``save_category`` and ``save_item`` never change the row they are given:
they return the row as stored, whose ``version`` storage assigns, one higher than the row an
update replaces. An update refused by any check stores nothing, so no later read returns what
it refused. A member returning a mapping returns a new ``dict`` on every call, so changing one
changes no later result, whether that result comes from the cache or not.
"""

import json
import re
from collections.abc import Callable
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import yaml

from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.adapters.repositories.yaml_repository import YamlRepository
from taxomesh.application.service import TaxomeshService
from taxomesh.domain.constants import MAX_EXTERNAL_ID_STR_LENGTH, MAX_ITEM_NAME_LENGTH
from taxomesh.domain.models import Category, Item
from taxomesh.exceptions import TaxomeshExternalIdConflictError, TaxomeshValidationError
from tests.service.conftest import DJANGO_PARAM


class TestASave:
    """``save_category`` and ``save_item`` leave their argument alone and return the stored row."""

    def test_saving_a_category_leaves_its_argument_and_returns_the_stored_row(self, service: TaxomeshService) -> None:
        row = Category(category_id=uuid4(), name="Tango")
        inserted = service.repository.save_category(row)
        replaced = service.repository.save_category(row)
        assert row.version == 0
        assert (inserted.category_id, inserted.version) == (row.category_id, 0)
        assert (replaced.name, replaced.version) == ("Tango", 1)
        stored = service.repository.find_category(row.category_id)
        assert stored is not None
        assert stored.version == 1

    def test_saving_an_item_leaves_its_argument_and_returns_the_stored_row(self, service: TaxomeshService) -> None:
        row = Item(item_id=uuid4(), name="Percanta")
        inserted = service.repository.save_item(row)
        replaced = service.repository.save_item(row)
        assert row.version == 0
        assert (inserted.item_id, inserted.version) == (row.item_id, 0)
        assert (replaced.name, replaced.version) == ("Percanta", 1)
        stored = service.repository.find_item(row.item_id)
        assert stored is not None
        assert stored.version == 1

    def test_each_update_stores_one_version_higher(self, service: TaxomeshService) -> None:
        """Saving the same unchanged row three times over the insert stores version 3."""
        row = Category(category_id=uuid4(), name="Tango")
        for _ in range(4):
            last = service.repository.save_category(row)
        assert last.version == 3
        assert row.version == 0


class TestAnUpdate:
    """``update`` returns a new row, one version higher, and every row held before is unchanged."""

    def test_a_category_update_returns_a_new_row_and_leaves_the_held_ones(self, service: TaxomeshService) -> None:
        created = service.categories.create("Tango")
        by_key = service.categories[created.category_id]
        (listed,) = service.categories.list()
        updated = service.categories.update(created.category_id, name="Milonga", metadata={"k": 1})
        assert updated is not by_key
        assert (updated.name, updated.metadata, updated.version) == ("Milonga", {"k": 1}, 1)
        for held in (created, by_key, listed):
            assert (held.name, held.metadata, held.version) == ("Tango", {}, 0)
        assert service.categories[created.category_id].version == 1

    def test_an_item_update_returns_a_new_row_and_leaves_the_held_ones(self, service: TaxomeshService) -> None:
        created = service.items.create("Percanta")
        by_key = service.items[created.item_id]
        (listed,) = service.items.list()
        updated = service.items.update(created.item_id, name="Mina", enabled=False)
        assert updated is not by_key
        assert (updated.name, updated.enabled, updated.version) == ("Mina", False, 1)
        for held in (created, by_key, listed):
            assert (held.name, held.enabled, held.version) == ("Percanta", True, 0)
        assert service.items[created.item_id].version == 1

    def test_a_tag_update_returns_a_new_row_and_leaves_the_held_ones(self, service: TaxomeshService) -> None:
        created = service.tags.create("lunfardo")
        by_key = service.tags[created.tag_id]
        updated = service.tags.update(created.tag_id, name="slang")
        assert updated is not by_key
        assert updated.name == "slang"
        assert (created.name, by_key.name) == ("lunfardo", "lunfardo")

    def test_successive_updates_count_up_from_the_stored_version(self, service: TaxomeshService) -> None:
        created = service.items.create("Percanta")
        first = service.items.update(created.item_id, name="Mina")
        second = service.items.update(created.item_id, name="Paica")
        assert (created.version, first.version, second.version) == (0, 1, 2)


def _item_fields(service: TaxomeshService, item_id: UUID) -> tuple[str, str | None, str, bool]:
    item = service.items[item_id]
    return item.name, item.external_id, item.slug, item.enabled


def _category_fields(service: TaxomeshService, category_id: UUID) -> tuple[str, str | None, str, bool]:
    category = service.categories[category_id]
    return category.name, category.external_id, category.slug, category.enabled


def _open(kind: str, path: Path) -> TaxomeshService:
    return TaxomeshService(repository=JsonRepository(path) if kind == "json" else YamlRepository(path))


def _hold_twice(kind: str, path: Path, section: str, row_id: UUID, external_id: str) -> None:
    """Give a stored row an external id another row already holds, by writing the file directly."""
    text = path.read_text(encoding="utf-8")
    data = json.loads(text) if kind == "json" else yaml.safe_load(text)
    data[section][str(row_id)]["external_id"] = external_id
    path.write_text(json.dumps(data) if kind == "json" else yaml.safe_dump(data), encoding="utf-8")


class TestARefusedUpdate:
    """An update refused by any check changes nothing stored and nothing a later read returns.

    Each test reads the row twice: straight after the refusal, and after an unrelated create,
    which clears the service's cache and, on the file backends, writes the stored rows out.
    """

    def test_a_taken_item_external_id_changes_nothing(self, service: TaxomeshService) -> None:
        """The name passed beside a taken external id is not kept, and the id stays held once."""
        service.items.create("A", external_id="taken")
        b = service.items.create("B")
        message = "External id 'taken' is already used by another item"
        with pytest.raises(TaxomeshExternalIdConflictError, match=re.escape(message)):
            service.items.update(b.item_id, name="B2", external_id="taken")
        assert _item_fields(service, b.item_id) == ("B", None, "", True)
        service.items.create("C")
        assert _item_fields(service, b.item_id) == ("B", None, "", True)
        assert [i.external_id for i in service.items.list(enabled=None)].count("taken") == 1

    def test_an_item_value_the_model_refuses_changes_nothing(self, service: TaxomeshService) -> None:
        """The values passed beside a name past its limit are not kept."""
        b = service.items.create("B")
        with pytest.raises(TaxomeshValidationError):
            service.items.update(b.item_id, enabled=False, slug="new-slug", name="x" * (MAX_ITEM_NAME_LENGTH + 1))
        assert _item_fields(service, b.item_id) == ("B", None, "", True)
        service.items.create("C")
        assert _item_fields(service, b.item_id) == ("B", None, "", True)

    def test_a_taken_category_external_id_changes_nothing(self, service: TaxomeshService) -> None:
        """The name passed beside a taken external id is not kept, and the id stays held once."""
        service.categories.create("X", external_id="taken")
        y = service.categories.create("Y")
        message = "External id 'taken' is already used by another category"
        with pytest.raises(TaxomeshExternalIdConflictError, match=re.escape(message)):
            service.categories.update(y.category_id, name="Y2", external_id="taken")
        assert _category_fields(service, y.category_id) == ("Y", None, "", True)
        service.categories.create("Z")
        assert _category_fields(service, y.category_id) == ("Y", None, "", True)
        assert [c.external_id for c in service.categories.list(enabled=None)].count("taken") == 1

    def test_a_category_value_the_model_refuses_changes_nothing(self, service: TaxomeshService) -> None:
        """The values passed beside an external id past its limit are not kept."""
        y = service.categories.create("Y")
        with pytest.raises(TaxomeshValidationError):
            service.categories.update(
                y.category_id, name="Y2", slug="new-slug", external_id="e" * (MAX_EXTERNAL_ID_STR_LENGTH + 1)
            )
        assert _category_fields(service, y.category_id) == ("Y", None, "", True)
        service.categories.create("Z")
        assert _category_fields(service, y.category_id) == ("Y", None, "", True)

    @pytest.mark.parametrize("kind", ["json", "yaml"])
    def test_a_stored_duplicate_refuses_an_item_rename_that_changes_nothing(self, kind: str, tmp_path: Path) -> None:
        """A file holding one external id on two items refuses renaming either, and keeps the name."""
        path = tmp_path / f"store.{kind}"
        service = _open(kind, path)
        a = service.items.create("A", external_id="42")
        b = service.items.create("B", external_id="43")
        _hold_twice(kind, path, "items", b.item_id, "42")
        service = _open(kind, path)
        with pytest.raises(TaxomeshExternalIdConflictError):
            service.items.update(a.item_id, name="A2")
        assert _item_fields(service, a.item_id) == ("A", "42", "", True)
        service.items.create("C")
        assert _item_fields(_open(kind, path), a.item_id) == ("A", "42", "", True)

    @pytest.mark.parametrize("kind", ["json", "yaml"])
    def test_a_stored_duplicate_refuses_a_category_rename_that_changes_nothing(
        self, kind: str, tmp_path: Path
    ) -> None:
        """A file holding one external id on two categories refuses renaming either, and keeps the name."""
        path = tmp_path / f"store.{kind}"
        service = _open(kind, path)
        x = service.categories.create("X", external_id="42")
        y = service.categories.create("Y", external_id="43")
        _hold_twice(kind, path, "categories", y.category_id, "42")
        service = _open(kind, path)
        with pytest.raises(TaxomeshExternalIdConflictError):
            service.categories.update(x.category_id, name="X2")
        assert _category_fields(service, x.category_id) == ("X", "42", "", True)
        service.categories.create("Z")
        assert _category_fields(_open(kind, path), x.category_id) == ("X", "42", "", True)

    @pytest.mark.parametrize("service", ["json", "yaml", DJANGO_PARAM], indirect=True)
    def test_an_item_id_taken_past_the_check_changes_nothing(
        self, service: TaxomeshService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An external id the check misses, as a write landing in between would, is refused by the save."""
        service.items.create("A", external_id="taken")
        b = service.items.create("B")
        monkeypatch.setattr(service.repository, "find_item_by_external_id", lambda _external_id: None)
        message = "External id 'taken' is already used by another item"
        with pytest.raises(TaxomeshExternalIdConflictError, match=re.escape(message)):
            service.items.update(b.item_id, name="B2", external_id="taken")
        assert _item_fields(service, b.item_id) == ("B", None, "", True)
        service.items.create("C")
        assert _item_fields(service, b.item_id) == ("B", None, "", True)

    @pytest.mark.parametrize("service", ["json", "yaml", DJANGO_PARAM], indirect=True)
    def test_a_category_id_taken_past_the_check_changes_nothing(
        self, service: TaxomeshService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An external id the check misses, as a write landing in between would, is refused by the save."""
        service.categories.create("X", external_id="taken")
        y = service.categories.create("Y")
        monkeypatch.setattr(service.repository, "find_category_by_external_id", lambda _external_id: None)
        message = "External id 'taken' is already used by another category"
        with pytest.raises(TaxomeshExternalIdConflictError, match=re.escape(message)):
            service.categories.update(y.category_id, name="Y2", external_id="taken")
        assert _category_fields(service, y.category_id) == ("Y", None, "", True)
        service.categories.create("Z")
        assert _category_fields(service, y.category_id) == ("Y", None, "", True)


class TestAHeldLink:
    """Reordering and moving save new links, and a link returned earlier keeps its sort index."""

    def test_reorder_leaves_a_held_category_link(self, service: TaxomeshService) -> None:
        parent = service.categories.create("Parent")
        a = service.categories.create("A")
        b = service.categories.create("B")
        link_a = service.categories.add_parent(a.category_id, parent.category_id, sort_index=0)
        link_b = service.categories.add_parent(b.category_id, parent.category_id, sort_index=1)
        service.categories.reorder(parent.category_id, [b.category_id, a.category_id])
        assert (link_a.sort_index, link_b.sort_index) == (0, 1)
        assert [c.name for c in service.categories.list(parent=parent.category_id)] == ["B", "A"]

    def test_reorder_leaves_a_held_placement(self, service: TaxomeshService) -> None:
        category = service.categories.create("C")
        x = service.items.create("X")
        y = service.items.create("Y")
        link_x = service.items.place_in(x.item_id, category.category_id, sort_index=0)
        link_y = service.items.place_in(y.item_id, category.category_id, sort_index=1)
        service.items.reorder(category.category_id, [y.item_id, x.item_id])
        assert (link_x.sort_index, link_y.sort_index) == (0, 1)
        assert [i.name for i in service.items.list(category=category.category_id)] == ["Y", "X"]

    def test_move_leaves_a_held_placement_of_a_sibling(self, service: TaxomeshService) -> None:
        source = service.categories.create("Source")
        target = service.categories.create("Target")
        x = service.items.create("X")
        y = service.items.create("Y")
        service.items.place_in(x.item_id, source.category_id)
        link_y = service.items.place_in(y.item_id, target.category_id, sort_index=5)
        service.items.move(
            x.item_id, from_category=source.category_id, to_category=target.category_id, before=y.item_id
        )
        assert link_y.sort_index == 5
        assert [i.name for i in service.items.list(category=target.category_id)] == ["X", "Y"]


class TestAGraph:
    """A graph is a snapshot: a later update does not show through its nodes."""

    def test_a_graph_built_before_an_update_is_unchanged_after_it(self, service: TaxomeshService) -> None:
        category = service.categories.create("Tango")
        item = service.items.create("Percanta")
        service.items.place_in(item.item_id, category.category_id)
        graph = service.graph()
        node = graph[category.category_id]
        service.categories.update(category.category_id, name="Milonga")
        service.items.update(item.item_id, name="Mina")
        assert node.category.name == "Tango"
        assert [i.name for i in node.items] == ["Percanta"]
        assert service.graph()[category.category_id].category.name == "Milonga"


MAPPING_MEMBERS = [
    "categories.get_many",
    "categories.get_many_by_external_id",
    "items.get_many",
    "items.get_many_by_external_id",
    "items.get_many_related",
    "tags.get_many",
]


def _mapping_calls(service: TaxomeshService) -> dict[str, Callable[[], object]]:
    """Store one row for each mapping member to find, and return a call to each member."""
    category = service.categories.create("Tango", external_id="c-1")
    item = service.items.create("Percanta", external_id="i-1")
    other = service.items.create("Mina")
    service.items.relate(item.item_id, other.item_id, "covers")
    tag = service.tags.create("lunfardo")
    return {
        "categories.get_many": lambda: service.categories.get_many([category.category_id]),
        "categories.get_many_by_external_id": lambda: service.categories.get_many_by_external_id(["c-1"]),
        "items.get_many": lambda: service.items.get_many([item.item_id]),
        "items.get_many_by_external_id": lambda: service.items.get_many_by_external_id(["i-1"]),
        "items.get_many_related": lambda: service.items.get_many_related([item.item_id]),
        "tags.get_many": lambda: service.tags.get_many([tag.tag_id]),
    }


class TestAReturnedMapping:
    """Each mapping member returns a new dict, so a caller may change what it was given."""

    @pytest.mark.parametrize("member", MAPPING_MEMBERS)
    def test_changing_a_returned_mapping_changes_no_later_result(self, service: TaxomeshService, member: str) -> None:
        call = _mapping_calls(service)[member]
        for _ in range(2):
            found = call()
            assert isinstance(found, dict)
            assert len(found) == 1
            found.clear()

    def test_changing_the_groups_of_related_items_changes_no_later_result(self, service: TaxomeshService) -> None:
        item = service.items.create("Percanta")
        other = service.items.create("Mina")
        service.items.relate(item.item_id, other.item_id, "covers")
        for _ in range(2):
            by_type = service.items.get_many_related([item.item_id])[item.item_id].by_type
            assert isinstance(by_type, dict)
            assert [[related.item_id for related in group] for group in by_type.values()] == [[other.item_id]]
            by_type.clear()
