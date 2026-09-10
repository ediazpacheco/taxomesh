# Feature Specification: Safe HTTP 500 response bodies

**Feature Branch**: `059-safe-error-bodies`
**Created**: 2026-09-09
**Status**: Draft
**Input**: User description: "Stop leaking backend internals in HTTP 500 responses from taxomesh.contrib.api. The two 500 branches of to_tuple must return a generic non-revealing body; the real detail goes to the taxomesh logger at error level. 404/409/422 keep returning str(exc)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A failing backend does not describe itself to the caller (Priority: P1)

An application exposes the taxonomy over HTTP using `taxomesh.contrib.api`. Its
storage backend fails mid-request — a database constraint fires, a connection drops,
or the YAML file cannot be written. The application maps the exception with
`errors.to_tuple` and returns the result.

Today the client receives the backend's own words: the constraint name, the table and
column involved, or the absolute path of a file on the server's disk. The operator
never sees it, because nothing is logged.

After this change the client receives a fixed, generic message that says a server
error occurred and nothing more, while the operator gets the full exception — message
and traceback — on the `taxomesh` logger.

**Why this priority**: This is the whole feature. Every other story is a guard around
it.

**Independent Test**: Raise a `TaxomeshRepositoryError` carrying a recognisable secret
string, map it with `to_tuple`, and assert the string appears nowhere in the returned
body while appearing in the captured log record.

**Acceptance Scenarios**:

1. **Given** a `TaxomeshRepositoryError` whose message contains backend detail,
   **When** it is mapped with `to_tuple`, **Then** the status is 500 and the body
   contains a fixed generic message that does not include any part of the original
   message.
2. **Given** the same error, **When** it is mapped, **Then** a record is emitted on
   the `taxomesh` logger at error level carrying the original exception and its
   traceback.
3. **Given** a `TaxomeshError` subclass that matches none of the mapped branches,
   **When** it is mapped, **Then** it behaves exactly as scenario 1 — generic body,
   logged detail.

---

### User Story 2 - Actionable client errors keep their message (Priority: P1)

A client sends a request that is wrong in a way it can fix: a slug already taken, an
external identifier already bound, a category that does not exist, a field that fails
validation. Those messages are written by taxomesh itself, describe the caller's own
input, and are the reason the caller can correct the request.

They must keep flowing through unchanged. A fix that redacted them would trade one
defect for a worse one.

**Why this priority**: Equal to Story 1. The change is only correct if it is narrow;
over-redaction would break every consuming client's error display.

**Independent Test**: Map one exception per non-500 branch and assert each body still
contains `str(exc)` verbatim.

**Acceptance Scenarios**:

1. **Given** a duplicate-slug or external-id conflict error, **When** it is mapped,
   **Then** the status is 409 and the body still contains the exception's own message.
2. **Given** a not-found error, **When** it is mapped, **Then** the status is 404 and
   the body still contains the exception's own message.
3. **Given** a validation error, **When** it is mapped, **Then** the status is 422 and
   the body still contains the exception's own message.
4. **Given** any non-500 mapping, **When** it is mapped, **Then** no log record is
   emitted — these are client errors, not operator events.

---

### User Story 3 - An operator can diagnose what the client was not told (Priority: P2)

Because the client no longer receives the detail, the operator must be able to get it.
An application that configures a handler on the `taxomesh` logger sees the full
exception; one that configures nothing sees nothing, and no warning is printed about
missing handlers.

**Why this priority**: Story 1 is not safely shippable without it — redacting without
logging would destroy information rather than relocate it — but it is a consequence of
Story 1 rather than a separate behavior.

**Independent Test**: Attach a capturing handler to the `taxomesh` logger, map a
repository error, and assert the record carries the original exception. Repeat with no
handler configured and assert nothing is emitted to stderr.

**Acceptance Scenarios**:

1. **Given** an application that has attached a handler to the `taxomesh` logger,
   **When** a 500-mapped error is produced, **Then** the record reaches that handler
   with exception information attached.
2. **Given** an application that has configured no logging at all, **When** a
   500-mapped error is produced, **Then** nothing is written to stderr and no
   "no handlers could be found" warning appears.

---

### Edge Cases

- **An exception with an empty message.** The generic body is a fixed string and does
  not vary with the input, so an empty message produces the same body as any other.
- **An exception whose message is already generic.** Still redacted. The rule is
  structural — decided by which branch matched, never by inspecting the message text.
- **A new `TaxomeshError` subclass added later.** It falls to the unmatched branch and
  is therefore redacted by default. Safe-by-default is the intended direction: a new
  error type cannot leak by being forgotten.
- **The same error mapped more than once.** `to_tuple` stays free of side effects other
  than logging; mapping twice logs twice and returns equal bodies both times.
- **A caller that inspects the 500 body to branch on it.** The body is now constant, so
  such a caller cannot branch. This is intended; the status code is the contract.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `to_tuple` MUST return a body containing a fixed, non-revealing message
  for the `TaxomeshRepositoryError` branch.
- **FR-002**: `to_tuple` MUST return the same fixed, non-revealing message for the
  unmatched-exception fallback branch.
- **FR-003**: The generic message MUST NOT contain any substring derived from the
  mapped exception, its arguments, its cause, or its traceback.
- **FR-004**: The generic message MUST be defined once as a named constant, per
  constitution principle X, and be importable so consuming applications and tests can
  reference it rather than duplicating the literal.
- **FR-005**: Every branch mapping to 500 MUST emit exactly one record on the
  `taxomesh` logger at error level, carrying the original exception with traceback.
- **FR-006**: Branches mapping to 404, 409, and 422 MUST continue to return
  `str(exc)` in the body, unchanged and byte-for-byte.
- **FR-007**: Branches mapping to 404, 409, and 422 MUST NOT emit any log record.
- **FR-008**: `to_tuple` MUST keep its signature
  `(exc: TaxomeshError) -> tuple[int, dict[str, Any]]` and its body key `detail`.
- **FR-009**: The status codes returned for every existing branch MUST be unchanged.
- **FR-010**: `to_tuple` MUST NOT raise. A failure while logging MUST NOT prevent the
  status and body from being returned.
- **FR-011**: The public documentation of the error mapping
  (`docs/http-api-integration.md`) MUST state that 500 bodies are generic and that the
  detail is available on the `taxomesh` logger.

### Key Entities

- **Error body**: The `dict[str, Any]` returned alongside a status code. Carries a
  single `detail` key. For client errors it holds the exception's own message; for
  server errors it holds the fixed generic message.
- **Generic server-error message**: A single named constant, the only text a client
  ever receives for a 500.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every exception type that maps to 500, the returned body shares no
  substring of length 8 or greater with the original exception message — verified by a
  test that plants a recognisable marker in the message.
- **SC-002**: 100% of `TaxomeshError` subclasses defined in the package are covered by
  the mapping test suite, and every one of them either returns its own message with a
  4xx status or returns the generic message with a 500 status. No third outcome exists.
- **SC-003**: For every 500 mapping, exactly one error-level record is captured on the
  `taxomesh` logger, and that record carries exception information.
- **SC-004**: All four existing quality gates continue to pass unchanged: `ruff check`,
  `ruff format --check`, `mypy --strict`, and the full suite at or above 80% coverage.
- **SC-005**: An application that configures no logging produces no output on stderr
  when a 500 is mapped.

## Assumptions

- The `detail` key is retained rather than renamed. Consuming applications already read
  it for 4xx responses, and renaming it would break them for no security benefit.
- Client errors (404/409/422) are safe to expose. Their messages are authored inside
  taxomesh from domain concepts — names, slugs, identifiers the caller itself supplied —
  and never wrap a backend exception. `TaxomeshRepositoryError` is the only branch that
  carries backend text.
- Error level is the right severity for a 500. These are operator-actionable events, not
  warnings.
- The existing `NullHandler` registered on the `taxomesh` logger at import is sufficient
  to keep unconfigured applications silent; no additional handler management is needed.

## Out of Scope

- Changing which status code any exception maps to. Spec 057 settled that; this feature
  changes only what accompanies the 500s.
- Adding an error code, correlation identifier, or machine-readable error taxonomy to
  the body. Worth considering, but a separate decision about the public contract.
- Redacting or restructuring the messages of the domain exceptions themselves.
- The `taxomesh.contrib.django` admin, the CLI, and any other surface that renders
  errors. This feature is scoped to `taxomesh.contrib.api`.
