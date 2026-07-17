"""Atomicity behavior tests for the five multi-write ``TaxomeshService`` operations.

These tests exercise the ``with self._repo.atomic():`` boundary added to
``create_category``, ``reorder_subcategories``, ``reorder_items_in_category``,
``reparent_category``, and ``reparent_item``:

- **User Story 1 (Django, transactional)**: a mid-operation write failure rolls
  the whole operation back to its pre-operation state, and a raw backend error
  surfaces as ``TaxomeshRepositoryError`` (chained) — never as a raw type. A
  mid-write ``TaxomeshError`` propagates unchanged *and* still rolls back
  (savepoint nesting). Pre-write ``ValueError`` / ``pydantic.ValidationError``
  stay outside the boundary and propagate unwrapped.
- **User Story 2 (all backends)**: the success path is byte-for-byte unchanged.
- **User Story 3 (file/in-memory)**: the boundary is a best-effort no-op —
  partial state MAY remain after a mid-operation failure, exactly as documented.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.application.service import TaxomeshService
from taxomesh.exceptions import (
    TaxomeshError,
    TaxomeshExternalIdConflictError,
    TaxomeshRepositoryError,
)
from tests.service.conftest import InMemoryRepository

# ---------------------------------------------------------------------------
# T010 — failure-injection repository double
# ---------------------------------------------------------------------------


class FailingRepository:
    """Wrap a real backend and raise on the Nth call to a targeted write method.

    Delegates every attribute — including ``atomic()`` — to the wrapped
    repository, so it behaves identically to the real backend until *armed*.
    Once :meth:`arm` is called, the ``call``-th invocation of ``method`` raises
    the supplied exception **instance** (a raw ``RuntimeError`` *or* a
    ``TaxomeshError`` subclass), allowing a failure to occur *after* an earlier
    write has already been performed — exercising Django savepoint nesting.
    """

    def __init__(self, wrapped: Any) -> None:
        self._wrapped = wrapped
        self._fail_on_method: str | None = None
        self._fail_on_call = 0
        self._exception: BaseException | None = None
        self._counts: dict[str, int] = {}

    @property
    def wrapped(self) -> Any:
        """Return the underlying real repository (unarmed, for snapshots)."""
        return self._wrapped

    def arm(self, method: str, call: int, exception: BaseException) -> None:
        """Arm the double to raise ``exception`` on the ``call``-th ``method`` call."""
        self._fail_on_method = method
        self._fail_on_call = call
        self._exception = exception
        self._counts = {}

    def atomic(self) -> AbstractContextManager[None]:
        """Delegate the atomicity boundary to the wrapped backend."""
        result: AbstractContextManager[None] = self._wrapped.atomic()
        return result

    def __getattr__(self, name: str) -> Any:
        # Only reached for names not found as real attributes on the instance;
        # `_wrapped`, `_fail_on_method`, etc. are set in __init__ so no recursion.
        attr = getattr(self._wrapped, name)
        if name != self._fail_on_method or not callable(attr):
            return attr

        def proxy(*args: Any, **kwargs: Any) -> Any:
            self._counts[name] = self._counts.get(name, 0) + 1
            if self._counts[name] == self._fail_on_call:
                assert self._exception is not None
                raise self._exception
            return attr(*args, **kwargs)

        return proxy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

Snapshot = tuple[list[Any], list[Any], list[Any], list[Any]]


def _snapshot(repo: Any) -> Snapshot:
    """Read the full datastore into a deterministically-ordered snapshot."""
    cats = sorted(repo.list_categories(enabled=None), key=lambda c: str(c.category_id))
    items = sorted(repo.list_items(enabled=None), key=lambda i: str(i.item_id))
    cpl = sorted(
        repo.list_category_parent_links(),
        key=lambda link: (str(link.category_id), str(link.parent_category_id)),
    )
    ipl = sorted(
        repo.list_item_parent_links(),
        key=lambda link: (str(link.item_id), str(link.category_id)),
    )
    return cats, items, cpl, ipl


@pytest.fixture
def django_factory(request: pytest.FixtureRequest) -> Callable[[], tuple[TaxomeshService, FailingRepository]]:
    """Return a factory building a Django-backed service wrapped in a FailingRepository.

    Skips when Django is unavailable; provisions the test database via the
    pytest-django ``db`` fixture.
    """
    pytest.importorskip("django", reason="django not installed")
    request.getfixturevalue("db")
    from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

    def _make() -> tuple[TaxomeshService, FailingRepository]:
        failing = FailingRepository(DjangoRepository())
        service = TaxomeshService(repository=failing)
        return service, failing

    return _make


# ---------------------------------------------------------------------------
# T011–T015 — Django rollback for each of the five operations (raw-error path)
# ---------------------------------------------------------------------------


def test_create_category_rolls_back_on_write_failure(
    django_factory: Callable[[], tuple[TaxomeshService, FailingRepository]],
) -> None:
    """T011: failure on save_category_parent_link → no category, no link, wrapped error."""
    service, failing = django_factory()
    before = _snapshot(failing.wrapped)

    boom = RuntimeError("parent link write exploded")
    failing.arm("save_category_parent_link", 1, boom)

    with pytest.raises(TaxomeshRepositoryError) as exc_info:
        service.create_category(name="Orphan")

    assert exc_info.value.__cause__ is boom
    assert not isinstance(exc_info.value.__cause__, TaxomeshError)
    after = _snapshot(failing.wrapped)
    assert after == before
    assert all(c.name != "Orphan" for c in failing.wrapped.list_categories(enabled=None))


def test_reparent_category_rolls_back_on_write_failure(
    django_factory: Callable[[], tuple[TaxomeshService, FailingRepository]],
) -> None:
    """T012: mid-loop failure after the delete → original parent link + ordering restored."""
    service, failing = django_factory()
    parent_a = service.create_category(name="Parent A")
    parent_b = service.create_category(name="Parent B")
    moving = service.create_category(name="Moving")
    service.add_category_parent(moving.category_id, parent_a.category_id, sort_index=0)
    # Siblings already in B so the re-index loop runs more than once.
    sib_1 = service.create_category(name="Sibling 1")
    sib_2 = service.create_category(name="Sibling 2")
    service.add_category_parent(sib_1.category_id, parent_b.category_id, sort_index=0)
    service.add_category_parent(sib_2.category_id, parent_b.category_id, sort_index=1)

    before = _snapshot(failing.wrapped)
    # Call 1 = add_category_parent's save; call 2 = first re-index loop save.
    failing.arm("save_category_parent_link", 2, RuntimeError("mid-loop boom"))

    with pytest.raises(TaxomeshError):
        service.reparent_category(
            moving.category_id,
            old_parent_id=parent_a.category_id,
            new_parent_id=parent_b.category_id,
            insert_before_uuid=None,
        )

    after = _snapshot(failing.wrapped)
    assert after == before


def test_reparent_item_rolls_back_on_write_failure(
    django_factory: Callable[[], tuple[TaxomeshService, FailingRepository]],
) -> None:
    """T013: mid-loop failure after the delete → original placement + ordering restored."""
    service, failing = django_factory()
    cat_a = service.create_category(name="Cat A")
    cat_b = service.create_category(name="Cat B")
    moving = service.create_item(name="Moving item")
    service.place_item_in_category(moving.item_id, cat_a.category_id, sort_index=0)
    sib_1 = service.create_item(name="Sib item 1")
    sib_2 = service.create_item(name="Sib item 2")
    service.place_item_in_category(sib_1.item_id, cat_b.category_id, sort_index=0)
    service.place_item_in_category(sib_2.item_id, cat_b.category_id, sort_index=1)

    before = _snapshot(failing.wrapped)
    # Fail on the 2nd save_item_parent_link (after the delete + first re-index save).
    failing.arm("save_item_parent_link", 2, RuntimeError("mid-loop boom"))

    with pytest.raises(TaxomeshError):
        service.reparent_item(
            moving.item_id,
            old_category_id=cat_a.category_id,
            new_category_id=cat_b.category_id,
            insert_before_uuid=None,
        )

    after = _snapshot(failing.wrapped)
    assert after == before


def test_reorder_subcategories_rolls_back_on_write_failure(
    django_factory: Callable[[], tuple[TaxomeshService, FailingRepository]],
) -> None:
    """T014: mid-loop failure → none of the sort_index changes survive."""
    service, failing = django_factory()
    parent = service.create_category(name="Parent")
    child_1 = service.create_category(name="Child 1")
    child_2 = service.create_category(name="Child 2")
    child_3 = service.create_category(name="Child 3")
    service.add_category_parent(child_1.category_id, parent.category_id, sort_index=0)
    service.add_category_parent(child_2.category_id, parent.category_id, sort_index=1)
    service.add_category_parent(child_3.category_id, parent.category_id, sort_index=2)

    before = _snapshot(failing.wrapped)
    failing.arm("save_category_parent_link", 2, RuntimeError("reorder boom"))

    with pytest.raises(TaxomeshRepositoryError):
        service.reorder_subcategories(
            parent.category_id,
            [child_3.category_id, child_2.category_id, child_1.category_id],
        )

    after = _snapshot(failing.wrapped)
    assert after == before


def test_reorder_items_in_category_rolls_back_on_write_failure(
    django_factory: Callable[[], tuple[TaxomeshService, FailingRepository]],
) -> None:
    """T015: mid-loop failure → none of the sort_index changes survive."""
    service, failing = django_factory()
    category = service.create_category(name="Bucket")
    item_1 = service.create_item(name="Item 1")
    item_2 = service.create_item(name="Item 2")
    item_3 = service.create_item(name="Item 3")
    service.place_item_in_category(item_1.item_id, category.category_id, sort_index=0)
    service.place_item_in_category(item_2.item_id, category.category_id, sort_index=1)
    service.place_item_in_category(item_3.item_id, category.category_id, sort_index=2)

    before = _snapshot(failing.wrapped)
    failing.arm("save_item_parent_link", 2, RuntimeError("reorder boom"))

    with pytest.raises(TaxomeshRepositoryError):
        service.reorder_items_in_category(
            category.category_id,
            [item_3.item_id, item_2.item_id, item_1.item_id],
        )

    after = _snapshot(failing.wrapped)
    assert after == before


# ---------------------------------------------------------------------------
# T016 — the "must NOT be wrapped" contract (three exception classes)
# ---------------------------------------------------------------------------


def test_midwrite_taxomesh_error_propagates_unchanged_and_rolls_back(
    django_factory: Callable[[], tuple[TaxomeshService, FailingRepository]],
) -> None:
    """T016(a): mid-write TaxomeshError → exact type propagates AND earlier write rolls back."""
    service, failing = django_factory()
    before = _snapshot(failing.wrapped)

    # create_category writes save_category (earlier) then save_category_parent_link
    # (later). Raise a TaxomeshError on the later write: the earlier save_category
    # has already committed to a savepoint and must be rolled back.
    conflict = TaxomeshExternalIdConflictError("simulated conflict")
    failing.arm("save_category_parent_link", 1, conflict)

    with pytest.raises(TaxomeshExternalIdConflictError) as exc_info:
        service.create_category(name="Should Vanish")

    assert exc_info.value is conflict  # not re-wrapped
    after = _snapshot(failing.wrapped)
    assert after == before  # earlier save_category rolled back
    assert all(c.name != "Should Vanish" for c in failing.wrapped.list_categories(enabled=None))


def test_prewrite_value_error_propagates_unwrapped() -> None:
    """T016(b): pre-write builtin ValueError is NOT converted to TaxomeshRepositoryError."""
    service = TaxomeshService(repository=InMemoryRepository())
    parent = service.create_category(name="Parent")

    with pytest.raises(ValueError) as exc_info:
        service.reorder_subcategories(parent.category_id, [uuid4()])  # not a child

    assert not isinstance(exc_info.value, TaxomeshError)


def test_prewrite_validation_error_propagates_unwrapped() -> None:
    """T016(c): pre-write pydantic.ValidationError propagates, unwrapped, no partial write."""
    repo = InMemoryRepository()
    service = TaxomeshService(repository=repo)
    before = _snapshot(repo)

    with pytest.raises(ValidationError):
        service.create_category(name="x" * 300)  # exceeds the 256-char limit

    assert _snapshot(repo) == before  # no category or link written


# ---------------------------------------------------------------------------
# T024 — success-path parity across every backend (US2)
# ---------------------------------------------------------------------------


def test_create_category_success_unchanged(service: TaxomeshService) -> None:
    """Wrapping create_category leaves the success path unchanged on every backend."""
    category = service.create_category(name="Alpha")
    assert service.get_category(category.category_id).name == "Alpha"
    assert category.category_id in {c.category_id for c in service.list_categories()}


def test_reorder_subcategories_success_unchanged(service: TaxomeshService) -> None:
    """reorder_subcategories persists the requested order on every backend."""
    parent = service.create_category(name="Parent")
    child_1 = service.create_category(name="Child 1")
    child_2 = service.create_category(name="Child 2")
    child_3 = service.create_category(name="Child 3")
    for idx, child in enumerate((child_1, child_2, child_3)):
        service.add_category_parent(child.category_id, parent.category_id, sort_index=idx)

    service.reorder_subcategories(
        parent.category_id,
        [child_3.category_id, child_2.category_id, child_1.category_id],
    )

    ordered = [c.category_id for c in service.list_categories(parent_id=parent.category_id)]
    assert ordered == [child_3.category_id, child_2.category_id, child_1.category_id]


def test_reorder_items_in_category_success_unchanged(service: TaxomeshService) -> None:
    """reorder_items_in_category persists the requested order on every backend."""
    category = service.create_category(name="Bucket")
    item_1 = service.create_item(name="Item 1")
    item_2 = service.create_item(name="Item 2")
    item_3 = service.create_item(name="Item 3")
    for idx, item in enumerate((item_1, item_2, item_3)):
        service.place_item_in_category(item.item_id, category.category_id, sort_index=idx)

    service.reorder_items_in_category(
        category.category_id,
        [item_3.item_id, item_2.item_id, item_1.item_id],
    )

    ordered = [i.item_id for i in service.list_items(category_id=category.category_id)]
    assert ordered == [item_3.item_id, item_2.item_id, item_1.item_id]


def test_reparent_category_success_unchanged(service: TaxomeshService) -> None:
    """reparent_category moves the category and returns the new link on every backend."""
    parent_a = service.create_category(name="Parent A")
    parent_b = service.create_category(name="Parent B")
    moving = service.create_category(name="Moving")
    service.add_category_parent(moving.category_id, parent_a.category_id, sort_index=0)

    new_link = service.reparent_category(
        moving.category_id,
        old_parent_id=parent_a.category_id,
        new_parent_id=parent_b.category_id,
        insert_before_uuid=None,
    )

    assert new_link.parent_category_id == parent_b.category_id
    assert moving.category_id in {c.category_id for c in service.list_categories(parent_id=parent_b.category_id)}
    assert moving.category_id not in {c.category_id for c in service.list_categories(parent_id=parent_a.category_id)}


def test_reparent_item_success_unchanged(service: TaxomeshService) -> None:
    """reparent_item moves the item and returns the new link on every backend."""
    cat_a = service.create_category(name="Cat A")
    cat_b = service.create_category(name="Cat B")
    moving = service.create_item(name="Moving item")
    service.place_item_in_category(moving.item_id, cat_a.category_id, sort_index=0)

    new_link = service.reparent_item(
        moving.item_id,
        old_category_id=cat_a.category_id,
        new_category_id=cat_b.category_id,
        insert_before_uuid=None,
    )

    assert new_link.category_id == cat_b.category_id
    assert moving.item_id in {i.item_id for i in service.list_items(category_id=cat_b.category_id)}
    assert moving.item_id not in {i.item_id for i in service.list_items(category_id=cat_a.category_id)}


# ---------------------------------------------------------------------------
# T026 — best-effort no-op semantics on file/in-memory backends (US3)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("backend", ["in_memory", "json"])
def test_best_effort_backend_may_leave_partial_state(backend: str, tmp_path: Path) -> None:
    """A mid-operation failure on a best-effort backend MAY leave partial state.

    JSON/in-memory backends implement ``atomic()`` as a documented no-op: there
    is NO rollback. When ``create_category`` fails on the second write, the first
    write (``save_category``) is NOT undone — the category persists without its
    parent link. This asserts the exact limitation the docstrings state.
    """
    real: Any = InMemoryRepository() if backend == "in_memory" else JsonRepository(tmp_path / "t.json")
    failing = FailingRepository(real)
    service = TaxomeshService(repository=failing)

    failing.arm("save_category_parent_link", 1, RuntimeError("no-op backend cannot roll back"))
    with pytest.raises(TaxomeshRepositoryError):
        service.create_category(name="Partial")

    # Partial state remains: the category was persisted (no rollback) ...
    persisted = [c for c in real.list_categories(enabled=None) if c.name == "Partial"]
    assert len(persisted) == 1
    # ... but its parent link never got written.
    partial_id = persisted[0].category_id
    assert all(link.category_id != partial_id for link in real.list_category_parent_links())


@pytest.mark.parametrize("backend", ["in_memory", "json"])
def test_best_effort_backend_success_path_unaffected(backend: str, tmp_path: Path) -> None:
    """On the success path, the no-op boundary behaves exactly as before."""
    real: Any = InMemoryRepository() if backend == "in_memory" else JsonRepository(tmp_path / "ok.json")
    service = TaxomeshService(repository=real)

    category = service.create_category(name="Whole")
    assert service.get_category(category.category_id).name == "Whole"
    links = [link for link in real.list_category_parent_links() if link.category_id == category.category_id]
    assert len(links) == 1  # category + its parent link both persisted
