"""A category is at the top level exactly when it has no other parent, on every backend.

Storage keeps the implicit root and its links, under one invariant: a category holds a link to the
root if and only if it holds no other parent link. ``add_parent`` drops the root link, and every
write that takes a category's last parent gives it back, as ``create`` makes it: ``remove_parent``,
``move`` and deleting that parent. ``None`` spells the top level in ``move`` and ``reorder``, and
``categories.roots()`` and ``graph().roots`` hold the same categories, in the same order, at every
``enabled`` setting.
"""

from collections.abc import Callable, Iterable
from unittest.mock import patch
from uuid import UUID

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import Category, CategoryParentLink
from taxomesh.exceptions import TaxomeshCyclicDependencyError, TaxomeshValidationError
from tests.service.conftest import CountedService

ENABLED_SETTINGS = (True, False, None)


def _stored_links(service: TaxomeshService) -> set[tuple[UUID, UUID, int]]:
    """Every stored parent link, as ``(category, parent, sort_index)``."""
    return {
        (lnk.category_id, lnk.parent_category_id, lnk.sort_index)
        for lnk in service.repository.list_category_parent_links()
    }


def _parents(service: TaxomeshService, category: Category) -> set[UUID]:
    """The parents one category holds a stored link to, the root included."""
    return {
        lnk.parent_category_id
        for lnk in service.repository.list_category_parent_links(category_ids=[category.category_id])
    }


def _root_link(service: TaxomeshService, category: Category) -> CategoryParentLink | None:
    """The category's stored link to the root, if it holds one."""
    links = service.repository.list_category_parent_links(category_ids=[category.category_id])
    return next((lnk for lnk in links if lnk.parent_category_id == service._root_id), None)


def _assert_invariant(service: TaxomeshService) -> None:
    """Every stored category but the root holds the root link exactly when it has no other parent."""
    root_id = service._root_id
    parents: dict[UUID, set[UUID]] = {}
    for lnk in service.repository.list_category_parent_links():
        parents.setdefault(lnk.category_id, set()).add(lnk.parent_category_id)
    for category in service.repository.list_categories(enabled=None):
        if category.category_id == root_id:
            continue
        held = parents.get(category.category_id, set())
        assert (root_id in held) == (held == {root_id}), f"{category.name} holds {held}"


def _assert_roots_agree(service: TaxomeshService) -> None:
    """``roots()`` and the graph's roots hold the same categories, in order, at each setting."""
    for enabled in ENABLED_SETTINGS:
        listed = [c.category_id for c in service.categories.roots(enabled=enabled)]
        drawn = [node.category.category_id for node in service.graph(enabled=enabled).roots]
        assert listed == drawn, f"enabled={enabled}"


def _names(rows: Iterable[Category]) -> list[str]:
    return [row.name for row in rows]


class TestAddParent:
    def test_it_drops_the_root_link(self, service: TaxomeshService) -> None:
        music = service.categories.create("Music")
        jazz = service.categories.create("Jazz")

        service.categories.add_parent(jazz.category_id, music.category_id)

        assert _parents(service, jazz) == {music.category_id}
        assert _names(service.categories.roots()) == ["Music"]
        _assert_invariant(service)

    def test_a_second_parent_gains_no_root_link(self, service: TaxomeshService) -> None:
        music = service.categories.create("Music")
        dance = service.categories.create("Dance")
        tango = service.categories.create("Tango")

        service.categories.add_parent(tango.category_id, music.category_id)
        service.categories.add_parent(tango.category_id, dance.category_id)

        assert _parents(service, tango) == {music.category_id, dance.category_id}
        _assert_invariant(service)

    def test_a_refused_add_parent_keeps_the_root_link(self, service: TaxomeshService) -> None:
        music = service.categories.create("Music")
        jazz = service.categories.create("Jazz")
        service.categories.add_parent(jazz.category_id, music.category_id)
        before = _stored_links(service)

        with pytest.raises(TaxomeshCyclicDependencyError):
            service.categories.add_parent(music.category_id, jazz.category_id)

        assert _stored_links(service) == before
        assert _root_link(service, music) is not None


class TestRemoveParent:
    def test_the_last_parent_gives_the_root_link_back_as_create_makes_it(self, service: TaxomeshService) -> None:
        music = service.categories.create("Music")
        jazz = service.categories.create("Jazz")
        service.categories.add_parent(jazz.category_id, music.category_id, sort_index=4)

        service.categories.remove_parent(jazz.category_id, music.category_id)

        link = _root_link(service, jazz)
        assert link is not None
        assert link.sort_index == 0
        assert _parents(service, jazz) == {service._root_id}
        assert set(_names(service.categories.roots())) == {"Music", "Jazz"}
        _assert_invariant(service)

    def test_a_parent_that_is_not_the_last_gives_nothing_back(self, service: TaxomeshService) -> None:
        music = service.categories.create("Music")
        dance = service.categories.create("Dance")
        tango = service.categories.create("Tango")
        service.categories.add_parent(tango.category_id, music.category_id)
        service.categories.add_parent(tango.category_id, dance.category_id)

        service.categories.remove_parent(tango.category_id, music.category_id)

        assert _parents(service, tango) == {dance.category_id}
        _assert_invariant(service)

    def test_an_absent_link_changes_nothing(self, service: TaxomeshService) -> None:
        music = service.categories.create("Music")
        jazz = service.categories.create("Jazz")
        before = _stored_links(service)

        service.categories.remove_parent(jazz.category_id, music.category_id)

        assert _stored_links(service) == before


class TestDelete:
    def test_deleting_the_only_parent_gives_each_child_the_root_link(self, service: TaxomeshService) -> None:
        music = service.categories.create("Music")
        jazz = service.categories.create("Jazz")
        blues = service.categories.create("Blues")
        service.categories.add_parent(jazz.category_id, music.category_id)
        service.categories.add_parent(blues.category_id, music.category_id)

        service.categories.delete(music.category_id)

        for child in (jazz, blues):
            link = _root_link(service, child)
            assert link is not None
            assert link.sort_index == 0
        assert set(_names(service.categories.roots())) == {"Jazz", "Blues"}
        _assert_invariant(service)

    def test_a_child_that_keeps_another_parent_gains_nothing(self, service: TaxomeshService) -> None:
        music = service.categories.create("Music")
        dance = service.categories.create("Dance")
        tango = service.categories.create("Tango")
        service.categories.add_parent(tango.category_id, music.category_id)
        service.categories.add_parent(tango.category_id, dance.category_id)

        service.categories.delete(music.category_id)

        assert _parents(service, tango) == {dance.category_id}
        _assert_invariant(service)

    def test_a_grandchild_keeps_its_parent(self, service: TaxomeshService) -> None:
        top = service.categories.create("Top")
        middle = service.categories.create("Middle")
        bottom = service.categories.create("Bottom")
        service.categories.add_parent(middle.category_id, top.category_id)
        service.categories.add_parent(bottom.category_id, middle.category_id)

        service.categories.delete(top.category_id)

        assert _parents(service, middle) == {service._root_id}
        assert _parents(service, bottom) == {middle.category_id}
        _assert_invariant(service)

    def test_deleting_a_middle_category_gives_its_child_the_root_link(self, service: TaxomeshService) -> None:
        top = service.categories.create("Top")
        middle = service.categories.create("Middle")
        bottom = service.categories.create("Bottom")
        service.categories.add_parent(middle.category_id, top.category_id)
        service.categories.add_parent(bottom.category_id, middle.category_id)

        service.categories.delete(middle.category_id)

        assert _parents(service, bottom) == {service._root_id}
        assert _names(service.categories.list(parent=top.category_id)) == []
        _assert_invariant(service)


class TestMove:
    def test_from_the_top_level_to_a_parent(self, service: TaxomeshService) -> None:
        music = service.categories.create("Music")
        jazz = service.categories.create("Jazz")

        service.categories.move(jazz.category_id, from_parent=None, to_parent=music.category_id)

        assert _parents(service, jazz) == {music.category_id}
        assert _names(service.categories.roots()) == ["Music"]
        _assert_invariant(service)

    def test_off_the_top_level_deletes_the_root_link_once(self, service: TaxomeshService) -> None:
        """Leaving the top level and joining a parent both name the root link, which goes once."""
        music = service.categories.create("Music")
        jazz = service.categories.create("Jazz")
        repository = service.repository

        with patch.object(
            repository, "delete_category_parent_link", wraps=repository.delete_category_parent_link
        ) as deletes:
            service.categories.move(jazz, from_parent=None, to_parent=music)

        assert deletes.call_count == 1
        assert _parents(service, jazz) == {music.category_id}
        _assert_invariant(service)

    def test_from_the_last_parent_to_the_top_level(self, service: TaxomeshService) -> None:
        music = service.categories.create("Music")
        jazz = service.categories.create("Jazz")
        service.categories.add_parent(jazz.category_id, music.category_id)

        service.categories.move(jazz.category_id, from_parent=music.category_id, to_parent=None)

        assert _parents(service, jazz) == {service._root_id}
        assert _names(service.categories.roots()) == ["Music", "Jazz"]
        _assert_invariant(service)

    def test_from_a_parent_to_another(self, service: TaxomeshService) -> None:
        music = service.categories.create("Music")
        dance = service.categories.create("Dance")
        tango = service.categories.create("Tango")
        service.categories.add_parent(tango.category_id, music.category_id)

        service.categories.move(tango.category_id, from_parent=music.category_id, to_parent=dance.category_id)

        assert _parents(service, tango) == {dance.category_id}
        _assert_invariant(service)

    def test_to_the_top_level_with_another_parent_left_raises_and_changes_nothing(
        self, service: TaxomeshService
    ) -> None:
        music = service.categories.create("Music")
        dance = service.categories.create("Dance")
        tango = service.categories.create("Tango")
        service.categories.add_parent(tango.category_id, music.category_id)
        service.categories.add_parent(tango.category_id, dance.category_id)
        before = _stored_links(service)

        with pytest.raises(TaxomeshValidationError):
            service.categories.move(tango.category_id, from_parent=music.category_id, to_parent=None)

        assert _stored_links(service) == before

    def test_within_the_top_level_with_a_parent_held_raises_and_changes_nothing(
        self, service: TaxomeshService
    ) -> None:
        """Taking a category off the top level it is not at removes nothing, so its parent remains."""
        music = service.categories.create("Music")
        jazz = service.categories.create("Jazz")
        service.categories.add_parent(jazz.category_id, music.category_id)
        before = _stored_links(service)

        with pytest.raises(TaxomeshValidationError):
            service.categories.move(jazz.category_id, from_parent=None, to_parent=None)

        assert _stored_links(service) == before

    def test_within_the_top_level_repositions(self, service: TaxomeshService) -> None:
        alpha = service.categories.create("Alpha")
        beta = service.categories.create("Beta")
        gamma = service.categories.create("Gamma")
        service.categories.reorder(None, [alpha.category_id, beta.category_id, gamma.category_id])

        service.categories.move(gamma.category_id, from_parent=None, to_parent=None, before=alpha.category_id)

        assert _names(service.categories.roots()) == ["Gamma", "Alpha", "Beta"]
        _assert_invariant(service)
        _assert_roots_agree(service)

    def test_from_a_parent_the_category_is_not_under_takes_it_off_the_top_level(
        self, service: TaxomeshService
    ) -> None:
        """Removing the absent link is a no-op, and the new parent is still a parent."""
        music = service.categories.create("Music")
        dance = service.categories.create("Dance")
        jazz = service.categories.create("Jazz")

        service.categories.move(jazz.category_id, from_parent=dance.category_id, to_parent=music.category_id)

        assert _parents(service, jazz) == {music.category_id}
        _assert_invariant(service)

    @pytest.mark.parametrize("source", ["top_level", "parent"])
    def test_a_move_refused_as_a_cycle_changes_nothing(self, service: TaxomeshService, source: str) -> None:
        """Checked before the first write, so no backend is left without the link being moved."""
        top = service.categories.create("Top")
        middle = service.categories.create("Middle")
        bottom = service.categories.create("Bottom")
        service.categories.add_parent(middle.category_id, top.category_id)
        service.categories.add_parent(bottom.category_id, middle.category_id)
        before = _stored_links(service)

        with pytest.raises(TaxomeshCyclicDependencyError):
            if source == "top_level":
                service.categories.move(top.category_id, from_parent=None, to_parent=bottom.category_id)
            else:
                service.categories.move(middle.category_id, from_parent=top.category_id, to_parent=bottom.category_id)

        assert _stored_links(service) == before


class TestReorder:
    def test_none_orders_the_top_level(self, service: TaxomeshService) -> None:
        alpha = service.categories.create("Alpha")
        beta = service.categories.create("Beta")
        gamma = service.categories.create("Gamma")

        service.categories.reorder(None, [gamma.category_id, alpha.category_id, beta.category_id])

        assert _names(service.categories.roots()) == ["Gamma", "Alpha", "Beta"]
        _assert_roots_agree(service)

    def test_none_refuses_a_category_off_the_top_level(self, service: TaxomeshService) -> None:
        music = service.categories.create("Music")
        jazz = service.categories.create("Jazz")
        service.categories.add_parent(jazz.category_id, music.category_id)

        with pytest.raises(TaxomeshValidationError):
            service.categories.reorder(None, [jazz.category_id, music.category_id])


class TestRootsAgree:
    def test_a_category_whose_parents_are_all_filtered_out_is_not_a_root(self, service: TaxomeshService) -> None:
        """It holds no root link, so neither side lists it; the snapshot still holds it."""
        music = service.categories.create("Music")
        jazz = service.categories.create("Jazz")
        service.categories.add_parent(jazz.category_id, music.category_id)
        service.categories.update(music.category_id, enabled=False)

        graph = service.graph()

        assert jazz.category_id in graph
        assert jazz.category_id in {node.category.category_id for node in graph.walk()}
        assert jazz.category_id not in {node.category.category_id for node in graph.roots}
        assert jazz.category_id not in {c.category_id for c in service.categories.roots()}
        _assert_roots_agree(service)

    def test_a_scripted_sequence_keeps_the_invariant_at_every_step(self, service: TaxomeshService) -> None:
        """Every write of the five, refused ones included, with disabled rows among the categories."""
        cats = {name: service.categories.create(name).category_id for name in "ABCDEF"}
        categories = service.categories

        def refused(error: type[Exception], call: Callable[[], object]) -> Callable[[], object]:
            def step() -> None:
                with pytest.raises(error):
                    call()

            return step

        steps: list[Callable[[], object]] = [
            lambda: categories.add_parent(cats["B"], cats["A"]),
            lambda: categories.add_parent(cats["C"], cats["B"]),
            lambda: categories.add_parent(cats["D"], cats["A"]),
            lambda: categories.add_parent(cats["D"], cats["C"]),
            lambda: categories.update(cats["E"], enabled=False),
            lambda: categories.move(cats["E"], from_parent=None, to_parent=cats["A"]),
            refused(
                TaxomeshCyclicDependencyError,
                lambda: categories.move(cats["A"], from_parent=None, to_parent=cats["C"]),
            ),
            refused(
                TaxomeshValidationError,
                lambda: categories.move(cats["D"], from_parent=cats["A"], to_parent=None),
            ),
            lambda: categories.remove_parent(cats["D"], cats["A"]),
            lambda: categories.move(cats["D"], from_parent=cats["C"], to_parent=None),
            lambda: categories.update(cats["C"], enabled=False),
            lambda: categories.add_parent(cats["F"], cats["C"]),
            lambda: categories.remove_parent(cats["C"], cats["B"]),
            lambda: categories.delete(cats["A"]),
            lambda: categories.add_parent(cats["B"], cats["D"]),
            lambda: categories.delete(cats["D"]),
            lambda: categories.move(cats["F"], from_parent=cats["C"], to_parent=cats["B"]),
            lambda: categories.move(cats["B"], from_parent=None, to_parent=None),
            lambda: categories.reorder(None, [cats["E"], cats["C"], cats["B"]]),
            lambda: categories.remove_parent(cats["F"], cats["B"]),
            lambda: categories.delete(cats["C"]),
        ]

        for number, step in enumerate(steps, start=1):
            step()
            try:
                _assert_invariant(service)
                _assert_roots_agree(service)
            except AssertionError as exc:
                raise AssertionError(f"after step {number}: {exc}") from exc

        assert set(_names(service.categories.roots(enabled=None))) == {"E", "B", "F"}


class TestAddedReads:
    """What the invariant costs: one read on ``remove_parent``, one or two on ``delete``, none on ``move``."""

    def test_removing_the_last_parent_reads_the_remaining_links_once(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        music = svc.categories.create("Music")
        jazz = svc.categories.create("Jazz")
        svc.categories.add_parent(jazz.category_id, music.category_id)
        counting_service.cold()

        svc.categories.remove_parent(jazz.category_id, music.category_id)

        assert counting_service.reads.count_of("list_category_parent_links") == 1
        assert counting_service.reads.total == 3

    def test_removing_an_absent_link_reads_no_links(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        music = svc.categories.create("Music")
        jazz = svc.categories.create("Jazz")
        counting_service.cold()

        svc.categories.remove_parent(jazz.category_id, music.category_id)

        assert counting_service.reads.count_of("list_category_parent_links") == 0
        assert counting_service.reads.total == 2

    def test_deleting_a_category_with_no_children_reads_its_children_once(
        self, counting_service: CountedService
    ) -> None:
        svc = counting_service.service
        music = svc.categories.create("Music")
        counting_service.cold()

        svc.categories.delete(music.category_id)

        assert counting_service.reads.total == 1

    def test_deleting_a_category_with_children_reads_their_links_once_more(
        self, counting_service: CountedService
    ) -> None:
        svc = counting_service.service
        music = svc.categories.create("Music")
        for name in ("Jazz", "Blues", "Tango"):
            child = svc.categories.create(name)
            svc.categories.add_parent(child.category_id, music.category_id)
        counting_service.cold()

        svc.categories.delete(music.category_id)

        assert counting_service.reads.total == 2

    def test_a_move_reads_its_rows_and_the_links_once(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        music = svc.categories.create("Music")
        dance = svc.categories.create("Dance")
        tango = svc.categories.create("Tango")
        svc.categories.add_parent(tango.category_id, music.category_id)
        counting_service.cold()

        svc.categories.move(tango.category_id, from_parent=music.category_id, to_parent=dance.category_id)

        assert counting_service.reads.count_of("list_category_parent_links") == 1
        assert counting_service.reads.total == 4
