"""Tests for taxomesh.contrib.api.errors — exception-to-HTTP status mapping."""

import inspect
import logging
import subprocess
import sys

import pytest

import taxomesh.exceptions as exceptions_module
from taxomesh.contrib.api.errors import GENERIC_SERVER_ERROR_DETAIL, to_tuple
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


class TestGenericServerErrorDetail:
    """T002 — the constant clients receive for every 500 (FR-004)."""

    def test_constant_is_a_non_empty_string(self) -> None:
        """The generic detail is a usable, displayable string."""
        assert isinstance(GENERIC_SERVER_ERROR_DETAIL, str)
        assert GENERIC_SERVER_ERROR_DETAIL.strip()

    @pytest.mark.parametrize("forbidden", ["sql", "constraint", "table", "traceback", "/", "\\"])
    def test_constant_reveals_nothing_about_the_backend(self, forbidden: str) -> None:
        """The constant itself must not name storage internals or contain a path separator."""
        assert forbidden not in GENERIC_SERVER_ERROR_DETAIL.lower()


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
        """Unrecognised TaxomeshError subclass → 500 fallback, redacted (T008, FR-002).

        Before 059 this asserted body["detail"] == "unexpected" — the exception's own text
        reached the client. The 500 body is now a fixed constant.
        """
        status, body = to_tuple(TaxomeshError("unexpected"))
        assert status == 500
        assert body["detail"] == GENERIC_SERVER_ERROR_DETAIL


class TestServerErrorRedaction:
    """US1 — a failing backend does not describe itself to the caller (FR-001..FR-003)."""

    _LEAKY_MESSAGE = 'duplicate key value violates unique constraint "taxomesh_item_external_id_key"'

    def test_repository_error_body_is_the_generic_constant(self) -> None:
        """T005 — the TaxomeshRepositoryError branch returns the constant, not str(exc)."""
        status, body = to_tuple(TaxomeshRepositoryError(self._LEAKY_MESSAGE))
        assert status == 500
        assert body == {"detail": GENERIC_SERVER_ERROR_DETAIL}

    def test_repository_error_leaks_no_fragment_of_the_original_message(self) -> None:
        """T006 — proven by absence, not by equality (SC-001).

        Asserting equality with the constant would still pass if a future change appended
        detail to it. This asserts that no 8-character window of the backend message
        survives into the body.
        """
        marker = "S3CR3T-TABLE-NAME"
        message = f"{self._LEAKY_MESSAGE} [{marker}]"
        _, body = to_tuple(TaxomeshRepositoryError(message))
        detail = body["detail"]

        assert marker not in detail
        window = 8
        for start in range(len(message) - window + 1):
            fragment = message[start : start + window]
            assert fragment not in detail, f"Leaked fragment {fragment!r} from the backend message"

    @pytest.mark.parametrize(
        "error_type",
        [TaxomeshError, TaxomeshConfigError, TaxomeshRootCategoryError],
        ids=lambda c: c.__name__,
    )
    def test_fallback_branch_types_are_redacted(self, error_type: type[TaxomeshError]) -> None:
        """T007 — every type reaching the unmatched branch is redacted.

        TaxomeshConfigError and TaxomeshRootCategoryError match no branch and land on the
        fallback; a config error's message can carry the taxomesh.toml path.
        """
        status, body = to_tuple(error_type("/Users/someone/private/taxomesh.toml is malformed"))
        assert status == 500
        assert body["detail"] == GENERIC_SERVER_ERROR_DETAIL


class TestClientErrorMessagesArePreserved:
    """US2 — the redaction must be narrow (FR-006, G2).

    These fail if a future change over-redacts. 4xx messages describe the caller's own
    input and are the only reason a client can correct its request.
    """

    @pytest.mark.parametrize(
        "error_type",
        [TaxomeshDuplicateSlugError, TaxomeshExternalIdConflictError],
        ids=lambda c: c.__name__,
    )
    def test_conflict_messages_survive_verbatim(self, error_type: type[TaxomeshError]) -> None:
        """T010 — 409 bodies are byte-identical to the exception message."""
        message = "slug 'jazz' already exists"
        status, body = to_tuple(error_type(message))
        assert status == 409
        assert body["detail"] == message

    @pytest.mark.parametrize(
        "error_type",
        [
            TaxomeshNotFoundError,
            TaxomeshItemNotFoundError,
            TaxomeshCategoryNotFoundError,
            TaxomeshTagNotFoundError,
        ],
        ids=lambda c: c.__name__,
    )
    def test_not_found_messages_survive_verbatim(self, error_type: type[TaxomeshError]) -> None:
        """T011 — 404 bodies are byte-identical to the exception message."""
        message = "category 'jazz' does not exist"
        status, body = to_tuple(error_type(message))
        assert status == 404
        assert body["detail"] == message

    @pytest.mark.parametrize(
        "error_type",
        [TaxomeshValidationError, TaxomeshCyclicDependencyError, TaxomeshRelationError],
        ids=lambda c: c.__name__,
    )
    def test_validation_messages_survive_verbatim(self, error_type: type[TaxomeshError]) -> None:
        """T012 — 422 bodies are byte-identical to the exception message."""
        message = "adding 'music' under 'jazz' would create a cycle"
        status, body = to_tuple(error_type(message))
        assert status == 422
        assert body["detail"] == message


_ERRORS_LOGGER = "taxomesh.contrib.api.errors"


class TestServerErrorLogging:
    """US3 — the detail is relocated to the logger, not destroyed (FR-005, FR-007)."""

    def test_server_error_emits_exactly_one_error_record_with_exc_info(self, caplog: pytest.LogCaptureFixture) -> None:
        """T014 — one ERROR record on the module logger, carrying the exception (G4, SC-003)."""
        exc = TaxomeshRepositoryError("constraint taxomesh_item_external_id_key on taxomesh_item")
        with caplog.at_level(logging.ERROR, logger=_ERRORS_LOGGER):
            to_tuple(exc)

        records = [r for r in caplog.records if r.name == _ERRORS_LOGGER]
        assert len(records) == 1
        record = records[0]
        assert record.levelno == logging.ERROR
        assert record.exc_info is not None
        assert record.exc_info[1] is exc

    def test_log_message_itself_carries_no_backend_text(self, caplog: pytest.LogCaptureFixture) -> None:
        """T015 — the detail lives in exc_info, not in the formatted message.

        A handler configured to log only record.getMessage() must not leak either.
        """
        marker = "S3CR3T-TABLE-NAME"
        with caplog.at_level(logging.ERROR, logger=_ERRORS_LOGGER):
            to_tuple(TaxomeshRepositoryError(f"failure near {marker}"))

        record = next(r for r in caplog.records if r.name == _ERRORS_LOGGER)
        assert marker not in record.getMessage()

    @pytest.mark.parametrize(
        "error_type",
        [
            TaxomeshNotFoundError,
            TaxomeshDuplicateSlugError,
            TaxomeshExternalIdConflictError,
            TaxomeshValidationError,
            TaxomeshCyclicDependencyError,
        ],
        ids=lambda c: c.__name__,
    )
    def test_client_errors_emit_no_records(
        self, error_type: type[TaxomeshError], caplog: pytest.LogCaptureFixture
    ) -> None:
        """T016 — 4xx mappings log nothing; they are client mistakes, not operator events (G5)."""
        with caplog.at_level(logging.DEBUG, logger=_ERRORS_LOGGER):
            to_tuple(error_type("client mistake"))

        assert [r for r in caplog.records if r.name == _ERRORS_LOGGER] == []

    def test_unconfigured_application_sees_nothing_on_stderr(self) -> None:
        """T017 — silence by default (G6, SC-005).

        Run in a clean interpreter: pytest installs its own logging handlers, which would
        mask whether taxomesh is silent on its own. The NullHandler registered in
        taxomesh/__init__.py is what stops logging.lastResort from writing to stderr.
        """
        script = (
            "from taxomesh.contrib.api.errors import to_tuple\n"
            "from taxomesh.exceptions import TaxomeshRepositoryError\n"
            "status, body = to_tuple(TaxomeshRepositoryError('secret backend detail'))\n"
            "assert status == 500, status\n"
            "print(body['detail'])\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=True,
        )
        assert result.stderr == ""
        assert "secret backend detail" not in result.stdout


class TestToTupleIsTotal:
    """FR-010 — to_tuple must not raise, whatever it is handed."""

    def test_exception_with_a_raising_str_still_maps(self) -> None:
        """A 500 body never touches str(exc), so a broken __str__ cannot break the mapping.

        Closes analyze finding C1: FR-010 was argued in research §7 but never asserted.
        """

        class HostileError(TaxomeshError):
            def __str__(self) -> str:
                raise RuntimeError("__str__ is broken")

        status, body = to_tuple(HostileError())
        assert status == 500
        assert body == {"detail": GENERIC_SERVER_ERROR_DETAIL}


class TestToTupleBodyShape:
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
