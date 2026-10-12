"""Tests for the taxomesh exception hierarchy.

Verifies that every exception class is correctly placed in the hierarchy,
catchable at the right granularity, and importable from the public surface.
TaxomeshCyclicDependencyError is a stub for future DAG cycle-detection logic;
its hierarchy placement is validated here even though no service method raises
it yet.
"""

import pickle

import pytest

from taxomesh import (
    TaxomeshCategoryNotFoundError,
    TaxomeshConfigError,
    TaxomeshCyclicDependencyError,
    TaxomeshDuplicateSlugError,
    TaxomeshError,
    TaxomeshExternalIdConflictError,
    TaxomeshItemNotFoundError,
    TaxomeshNotFoundError,
    TaxomeshRelationError,
    TaxomeshRepositoryError,
    TaxomeshRootCategoryError,
    TaxomeshTagNotFoundError,
    TaxomeshValidationError,
)

# ------------------------------------------------------------------
# TaxomeshCyclicDependencyError — primary focus
# ------------------------------------------------------------------


def test_cyclic_dependency_error_is_subclass_of_validation_error() -> None:
    assert issubclass(TaxomeshCyclicDependencyError, TaxomeshValidationError)


def test_cyclic_dependency_error_is_subclass_of_taxomesh_error() -> None:
    assert issubclass(TaxomeshCyclicDependencyError, TaxomeshError)


def test_cyclic_dependency_error_is_not_a_not_found_error() -> None:
    assert not issubclass(TaxomeshCyclicDependencyError, TaxomeshNotFoundError)


def test_cyclic_dependency_error_catchable_as_validation_error() -> None:
    with pytest.raises(TaxomeshValidationError):
        raise TaxomeshCyclicDependencyError("cycle: A → B → A")


def test_cyclic_dependency_error_catchable_as_taxomesh_error() -> None:
    with pytest.raises(TaxomeshError):
        raise TaxomeshCyclicDependencyError("cycle: A → B → A")


def test_cyclic_dependency_error_message_preserved() -> None:
    exc = TaxomeshCyclicDependencyError("cycle: A → B → A")
    assert "cycle: A → B → A" in str(exc)


# ------------------------------------------------------------------
# Full hierarchy structure
# ------------------------------------------------------------------


def test_not_found_error_hierarchy() -> None:
    assert issubclass(TaxomeshNotFoundError, TaxomeshError)
    assert issubclass(TaxomeshCategoryNotFoundError, TaxomeshNotFoundError)
    assert issubclass(TaxomeshItemNotFoundError, TaxomeshNotFoundError)
    assert issubclass(TaxomeshTagNotFoundError, TaxomeshNotFoundError)


def test_validation_error_hierarchy() -> None:
    assert issubclass(TaxomeshValidationError, TaxomeshError)
    assert issubclass(TaxomeshCyclicDependencyError, TaxomeshValidationError)
    assert issubclass(TaxomeshDuplicateSlugError, TaxomeshValidationError)


def test_repository_error_hierarchy() -> None:
    assert issubclass(TaxomeshRepositoryError, TaxomeshError)
    assert not issubclass(TaxomeshRepositoryError, TaxomeshNotFoundError)
    assert not issubclass(TaxomeshRepositoryError, TaxomeshValidationError)


def test_not_found_subclasses_are_mutually_exclusive() -> None:
    assert not issubclass(TaxomeshCategoryNotFoundError, TaxomeshItemNotFoundError)
    assert not issubclass(TaxomeshItemNotFoundError, TaxomeshTagNotFoundError)
    assert not issubclass(TaxomeshTagNotFoundError, TaxomeshCategoryNotFoundError)


# ------------------------------------------------------------------
# TaxomeshDuplicateSlugError
# ------------------------------------------------------------------


def test_duplicate_slug_error_is_subclass_of_validation_error() -> None:
    assert issubclass(TaxomeshDuplicateSlugError, TaxomeshValidationError)


def test_duplicate_slug_error_is_subclass_of_taxomesh_error() -> None:
    assert issubclass(TaxomeshDuplicateSlugError, TaxomeshError)


def test_duplicate_slug_error_is_not_a_not_found_error() -> None:
    assert not issubclass(TaxomeshDuplicateSlugError, TaxomeshNotFoundError)


def test_duplicate_slug_error_catchable_as_validation_error() -> None:
    with pytest.raises(TaxomeshValidationError):
        raise TaxomeshDuplicateSlugError("Slug 'books' is already in use")


def test_duplicate_slug_error_catchable_as_taxomesh_error() -> None:
    with pytest.raises(TaxomeshError):
        raise TaxomeshDuplicateSlugError("Slug 'books' is already in use")


def test_duplicate_slug_error_message_preserved() -> None:
    exc = TaxomeshDuplicateSlugError("Slug 'electronics' is already in use")
    assert "electronics" in str(exc)


def test_duplicate_slug_error_exported_from_package() -> None:
    """TaxomeshDuplicateSlugError must be importable from the top-level taxomesh package."""
    from taxomesh import TaxomeshDuplicateSlugError as _TaxomeshDuplicateSlugError  # noqa: PLC0415

    assert _TaxomeshDuplicateSlugError is TaxomeshDuplicateSlugError


# ------------------------------------------------------------------
# TaxomeshExternalIdConflictError
# ------------------------------------------------------------------


def test_external_id_conflict_error_is_subclass_of_validation_error() -> None:
    from taxomesh import TaxomeshExternalIdConflictError  # noqa: PLC0415

    assert issubclass(TaxomeshExternalIdConflictError, TaxomeshValidationError)


def test_external_id_conflict_error_is_subclass_of_taxomesh_error() -> None:
    from taxomesh import TaxomeshExternalIdConflictError  # noqa: PLC0415

    assert issubclass(TaxomeshExternalIdConflictError, TaxomeshError)


def test_external_id_conflict_error_is_not_a_not_found_error() -> None:
    from taxomesh import TaxomeshExternalIdConflictError  # noqa: PLC0415

    assert not issubclass(TaxomeshExternalIdConflictError, TaxomeshNotFoundError)


def test_external_id_conflict_error_catchable_as_validation_error() -> None:
    from taxomesh import TaxomeshExternalIdConflictError  # noqa: PLC0415

    with pytest.raises(TaxomeshValidationError):
        raise TaxomeshExternalIdConflictError("external_id 'abc-123' is already assigned to another item")


def test_external_id_conflict_error_catchable_as_taxomesh_error() -> None:
    from taxomesh import TaxomeshExternalIdConflictError  # noqa: PLC0415

    with pytest.raises(TaxomeshError):
        raise TaxomeshExternalIdConflictError("external_id 'abc-123' is already assigned to another item")


def test_external_id_conflict_error_message_contains_conflicting_value() -> None:
    from taxomesh import TaxomeshExternalIdConflictError  # noqa: PLC0415

    exc = TaxomeshExternalIdConflictError("external_id 'dup-key-42' is already assigned to another item")
    assert "dup-key-42" in str(exc)


def test_external_id_conflict_error_exported_from_package() -> None:
    from taxomesh import TaxomeshExternalIdConflictError as _err  # noqa: PLC0415
    from taxomesh.exceptions import TaxomeshExternalIdConflictError as _err2  # noqa: PLC0415

    assert _err is _err2


# ------------------------------------------------------------------
# The stdlib bases
# ------------------------------------------------------------------

NOT_FOUND_ERRORS: list[type[TaxomeshNotFoundError]] = [
    TaxomeshNotFoundError,
    TaxomeshCategoryNotFoundError,
    TaxomeshItemNotFoundError,
    TaxomeshTagNotFoundError,
]

VALIDATION_ERRORS: list[type[TaxomeshValidationError]] = [
    TaxomeshValidationError,
    TaxomeshCyclicDependencyError,
    TaxomeshRelationError,
    TaxomeshDuplicateSlugError,
    TaxomeshExternalIdConflictError,
    TaxomeshRootCategoryError,
]


@pytest.mark.parametrize("error", NOT_FOUND_ERRORS, ids=lambda c: c.__name__)
def test_every_not_found_error_is_a_key_error(error: type[TaxomeshNotFoundError]) -> None:
    """A caller who knows only the stdlib catches a miss as it would from a ``dict``."""
    with pytest.raises(KeyError):
        raise error("Category not found: 42")


@pytest.mark.parametrize("error", NOT_FOUND_ERRORS, ids=lambda c: c.__name__)
def test_a_not_found_error_reads_as_its_message(error: type[TaxomeshNotFoundError]) -> None:
    """``KeyError`` quotes its argument when printed; a not-found error prints its message as written."""
    exc = error("Category not found: 42")
    assert str(exc) == "Category not found: 42"
    assert repr(exc) == f"{error.__name__}('Category not found: 42')"


def test_a_not_found_error_with_no_message_reads_as_empty() -> None:
    assert str(TaxomeshItemNotFoundError()) == ""


def test_a_not_found_error_survives_pickling() -> None:
    """The error crosses a process boundary, as a worker pool's result does, with its type and message."""
    restored = pickle.loads(pickle.dumps(TaxomeshItemNotFoundError("Item not found: 7")))
    assert type(restored) is TaxomeshItemNotFoundError
    assert str(restored) == "Item not found: 7"


@pytest.mark.parametrize("error", VALIDATION_ERRORS, ids=lambda c: c.__name__)
def test_every_validation_error_is_a_value_error(error: type[TaxomeshValidationError]) -> None:
    """A caller who knows only the stdlib catches a refused value as it would from ``int("x")``."""
    with pytest.raises(ValueError):
        raise error("refused")


def test_the_reserved_name_error_is_a_validation_error() -> None:
    """A category given the implicit root's name is refused input, as a duplicate slug is."""
    assert issubclass(TaxomeshRootCategoryError, TaxomeshValidationError)


@pytest.mark.parametrize("error", [TaxomeshRepositoryError, TaxomeshConfigError], ids=lambda c: c.__name__)
def test_the_operator_errors_are_neither(error: type[TaxomeshError]) -> None:
    """A storage or configuration failure is not the caller's miss and not the caller's bad input."""
    assert not issubclass(error, KeyError)
    assert not issubclass(error, ValueError)
