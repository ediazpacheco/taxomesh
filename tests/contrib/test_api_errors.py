"""Tests for taxomesh.contrib.api.errors — exception-to-HTTP status mapping."""

import inspect

import pytest

import taxomesh.exceptions as exceptions_module
from taxomesh.contrib.api.errors import to_tuple
from taxomesh.exceptions import (
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


class TestToTuple:
    """Tests for to_tuple() — maps TaxomeshError subclasses to (status, body) pairs."""

    def test_not_found_error_is_404(self) -> None:
        """TaxomeshNotFoundError → 404."""
        status, body = to_tuple(TaxomeshNotFoundError("not found"))
        assert status == 404
        assert "detail" in body

    def test_category_not_found_is_404(self) -> None:
        """TaxomeshCategoryNotFoundError (subclass of NotFound) → 404."""
        status, body = to_tuple(TaxomeshCategoryNotFoundError("cat missing"))
        assert status == 404
        assert body["detail"] == "cat missing"

    def test_item_not_found_is_404(self) -> None:
        """TaxomeshItemNotFoundError → 404."""
        status, _ = to_tuple(TaxomeshItemNotFoundError("item missing"))
        assert status == 404

    def test_tag_not_found_is_404(self) -> None:
        """TaxomeshTagNotFoundError → 404."""
        status, _ = to_tuple(TaxomeshTagNotFoundError("tag missing"))
        assert status == 404

    def test_duplicate_slug_is_409(self) -> None:
        """TaxomeshDuplicateSlugError → 409 (conflict), not 422."""
        status, body = to_tuple(TaxomeshDuplicateSlugError("slug taken"))
        assert status == 409
        assert body["detail"] == "slug taken"

    def test_external_id_conflict_is_409(self) -> None:
        """TaxomeshExternalIdConflictError → 409 (conflict), not 422 — identical to the slug conflict (FR-006)."""
        status, body = to_tuple(TaxomeshExternalIdConflictError("external_id taken"))
        assert status == 409
        assert body["detail"] == "external_id taken"

    def test_validation_error_is_422(self) -> None:
        """TaxomeshValidationError → 422."""
        status, body = to_tuple(TaxomeshValidationError("invalid"))
        assert status == 422
        assert "detail" in body

    def test_cyclic_dependency_is_422(self) -> None:
        """TaxomeshCyclicDependencyError (subclass of Validation) → 422."""
        status, _ = to_tuple(TaxomeshCyclicDependencyError("cycle"))
        assert status == 422

    def test_repository_error_is_500(self) -> None:
        """TaxomeshRepositoryError → 500."""
        status, body = to_tuple(TaxomeshRepositoryError("io error"))
        assert status == 500
        assert "detail" in body

    def test_base_error_fallback_is_500(self) -> None:
        """Unrecognised TaxomeshError subclass → 500 fallback."""
        status, body = to_tuple(TaxomeshError("unexpected"))
        assert status == 500
        assert body["detail"] == "unexpected"

    def test_body_always_has_detail_key(self) -> None:
        """Every mapped exception produces a body with a 'detail' key."""
        exceptions = [
            TaxomeshNotFoundError("a"),
            TaxomeshDuplicateSlugError("b"),
            TaxomeshValidationError("c"),
            TaxomeshCyclicDependencyError("d"),
            TaxomeshRepositoryError("e"),
            TaxomeshError("f"),
        ]
        for exc in exceptions:
            _, body = to_tuple(exc)
            assert "detail" in body, f"Missing 'detail' for {type(exc).__name__}"


# The intended HTTP status for every TaxomeshError type the mapping can receive. Semantically
# equivalent errors MUST assert identical statuses: both uniqueness conflicts (slug, external_id)
# map to 409. Errors that never reach a public handler (config/root-category) map to the 500
# fallback and are listed explicitly so the guard below can prove the mapping is exhaustive.
EXPECTED_STATUS: dict[type[TaxomeshError], int] = {
    TaxomeshError: 500,
    TaxomeshNotFoundError: 404,
    TaxomeshItemNotFoundError: 404,
    TaxomeshCategoryNotFoundError: 404,
    TaxomeshTagNotFoundError: 404,
    TaxomeshValidationError: 422,
    TaxomeshCyclicDependencyError: 422,
    TaxomeshRelationError: 422,
    TaxomeshDuplicateSlugError: 409,
    TaxomeshExternalIdConflictError: 409,
    TaxomeshRepositoryError: 500,
    TaxomeshConfigError: 500,
    TaxomeshRootCategoryError: 500,
}


def _all_taxomesh_error_types() -> set[type[TaxomeshError]]:
    """Discover every TaxomeshError subclass defined in taxomesh.exceptions."""
    return {obj for _, obj in inspect.getmembers(exceptions_module, inspect.isclass) if issubclass(obj, TaxomeshError)}


class TestMappingCompleteness:
    """FR-018 / SC-006 — guard against a new error type silently inheriting a generic status."""

    def test_every_error_type_is_listed(self) -> None:
        """Every TaxomeshError subclass must have an intended status recorded.

        This is the guard the divergence FR-006 corrects would have caught: when 041 added
        TaxomeshExternalIdConflictError, nothing forced contrib.api to assign it a status, so it
        silently inherited 422. A newly added error type now fails this test until it is mapped.
        """
        unlisted = _all_taxomesh_error_types() - set(EXPECTED_STATUS)
        assert not unlisted, (
            f"Unlisted TaxomeshError types: {sorted(c.__name__ for c in unlisted)}. "
            "Assign each an intended status in errors.to_tuple and EXPECTED_STATUS."
        )

    @pytest.mark.parametrize("error_type", list(EXPECTED_STATUS), ids=lambda c: c.__name__)
    def test_error_type_maps_to_expected_status(self, error_type: type[TaxomeshError]) -> None:
        """Each error type maps to its intended status, so equivalent errors stay identical."""
        status, _ = to_tuple(error_type("boom"))
        assert status == EXPECTED_STATUS[error_type]
