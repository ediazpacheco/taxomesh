"""Tests for taxomesh.contrib.api.errors — exception-to-HTTP status mapping."""

from taxomesh.contrib.api.errors import to_tuple
from taxomesh.exceptions import (
    TaxomeshCategoryNotFoundError,
    TaxomeshCyclicDependencyError,
    TaxomeshDuplicateSlugError,
    TaxomeshError,
    TaxomeshItemNotFoundError,
    TaxomeshNotFoundError,
    TaxomeshRepositoryError,
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
