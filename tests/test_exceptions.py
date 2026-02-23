"""Tests for the taxomesh exception hierarchy.

Verifies that every exception class is correctly placed in the hierarchy,
catchable at the right granularity, and importable from the public surface.
TaxomeshCyclicDependencyError is a stub for future DAG cycle-detection logic;
its hierarchy placement is validated here even though no service method raises
it yet.
"""

import pytest

from taxomesh import (
    TaxomeshCategoryNotFoundError,
    TaxomeshCyclicDependencyError,
    TaxomeshError,
    TaxomeshItemNotFoundError,
    TaxomeshNotFoundError,
    TaxomeshRepositoryError,
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


def test_repository_error_hierarchy() -> None:
    assert issubclass(TaxomeshRepositoryError, TaxomeshError)
    assert not issubclass(TaxomeshRepositoryError, TaxomeshNotFoundError)
    assert not issubclass(TaxomeshRepositoryError, TaxomeshValidationError)


def test_not_found_subclasses_are_mutually_exclusive() -> None:
    assert not issubclass(TaxomeshCategoryNotFoundError, TaxomeshItemNotFoundError)
    assert not issubclass(TaxomeshItemNotFoundError, TaxomeshTagNotFoundError)
    assert not issubclass(TaxomeshTagNotFoundError, TaxomeshCategoryNotFoundError)
