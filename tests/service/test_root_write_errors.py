"""Root-addressed writes answer not-found.

Handing the implicit root's identifier to ``delete``, ``update``, ``add_parent``, ``move`` or
``remove_parent`` raises ``TaxomeshCategoryNotFoundError``, exactly as any identifier the container
does not hold. This is the write-side half of the rule ``test_root_invisible.py`` pins on the read
side: an object invisible to every read cannot coherently produce a special error on write. A
``remove_parent`` validating its subject with a bare repository read would let the root pass, and
the call would be a silent no-op, since the root never has a parent.

``TaxomeshRootCategoryError`` is the reserved-name guard on creation and on renaming, a guard
about the *name* rather than about the root's visibility, and it stays exported. It reads the name
the built row holds, so a value the model decodes to the reserved name is refused as well.

The root is a stored row, so a write that did not refuse it would not fall through to a
not-found: ``delete`` would find the row and delete it, and ``add_parent`` would link the root
under a category. Each refusal is therefore asserted
together with the state it protects, because the assertion that the call raises does not by itself
distinguish a guard from its absence.
"""

from typing import Any

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.constants import ROOT_CATEGORY_NAME
from taxomesh.exceptions import TaxomeshCategoryNotFoundError, TaxomeshRootCategoryError


# Any: bytes are passed where the annotation asks for text, as an untyped caller can.
def untyped(value: object) -> Any:
    """Return ``value`` typed as anything, so a call can pass what its annotation refuses."""
    return value


def _assert_a_later_service_keeps_the_root(service: TaxomeshService, top_level: str) -> None:
    """A service built later over the store finds the same root, and the top level beneath it."""
    later = TaxomeshService(repository=service.repository)
    assert later._root_id == service._root_id
    assert [category.name for category in later.categories.roots()] == [top_level]


class TestRootAddressedWritesAnswerNotFound:
    """``delete``, ``update``, ``add_parent``, ``move`` and ``remove_parent`` all answer not-found."""

    def test_delete_answers_not_found(self, service: TaxomeshService) -> None:
        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.categories.delete(service._root_id)

    def test_update_answers_not_found(self, service: TaxomeshService) -> None:
        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.categories.update(service._root_id, name="x")

    def test_add_parent_answers_not_found(self, service: TaxomeshService) -> None:
        cat = service.categories.create(name="SomeCat")

        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.categories.add_parent(service._root_id, cat.category_id)

    def test_move_answers_not_found(self, service: TaxomeshService) -> None:
        """``move`` validates its subject through subscript.

        Pinned here because nothing else pins it, and because it is what makes the write side
        uniform: every member taking the root as the row being changed says not-found.
        """
        alpha = service.categories.create(name="Alpha")
        beta = service.categories.create(name="Beta")

        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.categories.move(service._root_id, from_parent=alpha.category_id, to_parent=beta.category_id)

    def test_remove_parent_answers_not_found(self, service: TaxomeshService) -> None:
        """The inverse of ``add_parent`` refuses the root as its subject too.

        Asserted by the raise alone: unlike the three refusals below, this one protects no stored
        state, since the root has no parent link to remove.
        """
        cat = service.categories.create(name="SomeCat")

        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.categories.remove_parent(service._root_id, cat.category_id)


class TestTheRefusalProtectsTheStoredRow:
    """A guard that merely disappeared would let the write SUCCEED — the root is a real row."""

    def test_a_refused_delete_leaves_the_row_in_storage(self, service: TaxomeshService) -> None:
        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.categories.delete(service._root_id)

        root = service.repository.find_category(service._root_id)
        assert root is not None
        assert root.name == ROOT_CATEGORY_NAME

    def test_a_refused_update_leaves_the_row_unchanged(self, service: TaxomeshService) -> None:
        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.categories.update(service._root_id, name="renamed")

        root = service.repository.find_category(service._root_id)
        assert root is not None
        assert root.name == ROOT_CATEGORY_NAME

    def test_a_refused_add_parent_creates_no_link(self, service: TaxomeshService) -> None:
        cat = service.categories.create(name="Alpha")

        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.categories.add_parent(service._root_id, cat.category_id)

        links = service.repository.list_category_parent_links()
        assert [lnk for lnk in links if lnk.category_id == service._root_id] == []


class TestTheRootErrorSurvives:
    """Removes three raisers of ``TaxomeshRootCategoryError`` and keeps the fourth."""

    def test_creating_a_category_with_the_reserved_name_still_raises_it(self, service: TaxomeshService) -> None:
        """The guard that keeps the exception live: it is about the name, not about the root.

        Also asserted by ``test_service_categories.py::test_create_category_reserved_name_raises``,
        which is unchanged. Repeated here deliberately — this file is where the exception's
        remaining reach is described, and the survival is only meaningful beside the removals.
        """
        with pytest.raises(TaxomeshRootCategoryError):
            service.categories.create(name=ROOT_CATEGORY_NAME)

    def test_renaming_a_category_to_the_reserved_name_raises_it(self, service: TaxomeshService) -> None:
        """The same guard covers a rename, and the refused rename leaves the row as it was.

        A category renamed ``__root__`` would show as such in every unfiltered listing, and a
        service built later over the same file could adopt it as the root, since the service
        finds its root by that name: the category would vanish and the real root become a
        visible row.
        """
        category = service.categories.create(name="Renamable")

        with pytest.raises(TaxomeshRootCategoryError):
            service.categories.update(category.category_id, name=ROOT_CATEGORY_NAME)

        assert service.categories[category.category_id].name == "Renamable"


class TestTheDecodedNameIsChecked:
    """The model reads ``b"__root__"`` as the reserved name, so the guard reads the name it built."""

    def test_creating_with_the_reserved_name_as_bytes_raises_it(self, service: TaxomeshService) -> None:
        service.categories.create(name="Tango")
        before = list(service.repository.list_categories(enabled=None))

        with pytest.raises(TaxomeshRootCategoryError):
            service.categories.create(untyped(ROOT_CATEGORY_NAME.encode()))

        assert list(service.repository.list_categories(enabled=None)) == before
        _assert_a_later_service_keeps_the_root(service, "Tango")

    def test_renaming_to_the_reserved_name_as_bytes_raises_it(self, service: TaxomeshService) -> None:
        category = service.categories.create(name="Renamable")

        with pytest.raises(TaxomeshRootCategoryError):
            service.categories.update(category, name=untyped(ROOT_CATEGORY_NAME.encode()))

        assert service.repository.find_category(category.category_id) == category
        _assert_a_later_service_keeps_the_root(service, "Renamable")
