# Research: Safe HTTP 500 response bodies

**Feature**: 059-safe-error-bodies | **Date**: 2026-09-09

No `NEEDS CLARIFICATION` markers were carried into the plan. The items below record
decisions that had real alternatives, each verified against the current tree.

---

## 1. What actually leaks, and from where

**Finding**: `DjangoRepository` raises `TaxomeshRepositoryError(str(exc))` in 14
distinct places (`taxomesh/adapters/repositories/django_repository.py`, e.g. lines 289,
338, 395, 442, 472, 512, 543, 564, 595, 639, 677, 704). The wrapper message *is* the
backend message, verbatim. `to_tuple` then places it in `{"detail": ...}` and returns
it with status 500.

The exposure is therefore concrete, not theoretical: a Django `IntegrityError` names
the constraint and usually the table and column; an `OperationalError` may name the
database file; the JSON and YAML repositories surface the absolute path of the data
file.

**Second path, found during research**: `TaxomeshConfigError` and
`TaxomeshRootCategoryError` do not match any branch and reach the same 500 fallback
(confirmed by the existing `EXPECTED_STATUS` map in `tests/contrib/test_api_errors.py`,
lines 105–119). `TaxomeshConfigError` messages can carry the `taxomesh.toml` path. This
strengthens the decision below to redact the fallback rather than only the
`TaxomeshRepositoryError` branch.

---

## 2. Redact both 500 branches, or only the repository branch?

**Decision**: Redact both.

**Rationale**: The fallback is the branch that catches error types nobody has classified
yet, including any subclass added after this spec. Leaving it verbatim would mean a new
exception type leaks by default and only stops leaking if someone remembers to classify
it. Redacting by default inverts that: forgetting is safe. Research item 1 also shows
the fallback already carries a path-bearing error type today.

**Alternatives considered**:

- *Redact only `TaxomeshRepositoryError`.* Rejected — leaves `TaxomeshConfigError`
  leaking a filesystem path right now, and makes safety depend on future diligence.
- *Redact everything, all statuses.* Rejected — 404/409/422 messages are authored inside
  taxomesh from the caller's own input and are the only reason a client can correct its
  request. Redacting them would trade an information leak for a usability regression,
  and would break every consuming client's error display.

---

## 3. Where the detail goes instead

**Decision**: `logger = logging.getLogger(__name__)` at module level in `errors.py`,
called as `logger.error(<static message>, exc_info=exc)`.

**Rationale**: Matches the convention already used in `taxomesh/application/service.py`
(line 38: `logger = logging.getLogger(__name__)`). `__name__` resolves to
`taxomesh.contrib.api.errors`, a descendant of the `"taxomesh"` logger that
`taxomesh/__init__.py:30` already equips with a `NullHandler`, so an application that
configures nothing stays silent (SC-005) and one that configures a handler receives the
record. Passing `exc_info=exc` attaches the traceback, and because the repository
adapters raise `... from exc`, the chained cause travels with it.

**Alternatives considered**:

- *`logger.exception(...)`.* Rejected — it is defined in terms of the *currently handled*
  exception (`sys.exc_info()`), and `to_tuple` may be called outside an `except` block.
  `exc_info=exc` is explicit and correct in both cases.
- *A dedicated `"taxomesh.security"` logger.* Rejected — invents a channel the project
  does not otherwise use, and applications already filter on the `taxomesh` tree.
- *Returning the detail through a second return value or an out-parameter.* Rejected —
  FR-008 fixes the signature, and it would push the leak decision onto every consumer.

---

## 4. Log level

**Decision**: `ERROR`.

**Rationale**: A 500 is an operator-actionable failure of the service itself. The
existing `WARNING` uses in `service.py` (lines 1309, 1343) cover degraded-but-served
paths, which is a different situation. Nothing in this feature is recoverable.

---

## 5. Keep the `detail` key?

**Decision**: Keep it.

**Rationale**: Consuming applications already read `body["detail"]` for 4xx responses.
Renaming or dropping it for 500s alone would force every consumer to branch on status
before reading the body, for no security gain — the protection comes from the *value*,
not the key. Recorded in the spec's Assumptions.

---

## 6. Wording of the generic message

**Decision**: `GENERIC_SERVER_ERROR_DETAIL: Final[str] = "An internal error occurred."`

**Rationale**: States that the failure is server-side and terminal, tells the client
nothing about cause, location, or backend, and reads as a finished sentence in a UI that
displays it. Public per FR-004 (no leading underscore, unlike the module's private
`_HTTP_*` constants) so consumers and tests can import it instead of copying the literal.

**Alternatives considered**:

- *`"Internal Server Error"`.* Rejected — duplicates the HTTP reason phrase the status
  code already carries.
- *Including a correlation id.* Rejected — genuinely useful, but it requires deciding who
  generates the id and how it reaches the log record. That is a public-contract decision
  of its own; the spec lists it as out of scope.

---

## 7. Making `to_tuple` non-raising (FR-010)

**Decision**: Order the work so the mapping cannot be disturbed by logging — compute the
status, log, then return.

**Rationale**: The standard library already guarantees most of this: `logging` routes
handler failures through `handleError`, which swallows them unless
`logging.raiseExceptions` is set *and* stderr is available. A caller who has installed a
badly behaved handler is outside what this function can defend against, and wrapping the
call in a bare `except` would violate principle V's ban on swallowing exceptions. The
requirement is satisfied by not introducing any *new* raising path: the constant is a
module-level literal, and no formatting of `str(exc)` happens on the 500 path at all.

**Alternatives considered**:

- *`try/except Exception` around the log call.* Rejected — swallows failures the
  constitution says must not be swallowed, to defend against a caller-installed defect.

---

## 8. Test approach for "does not leak"

**Decision**: Plant a marker string in the exception message, then assert the marker —
and every 8-character window of the original message — is absent from the returned body
(SC-001), and present on the captured log record (SC-003).

**Rationale**: Asserting `body["detail"] == GENERIC_SERVER_ERROR_DETAIL` alone would pass
even if a future change appended detail to the constant. Testing for absence of the
input is what the requirement actually says. `caplog` covers the log side with no new
dependency.
