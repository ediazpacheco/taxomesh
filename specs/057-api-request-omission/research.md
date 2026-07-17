# Phase 0 Research: API Request Omission and Explicit-Null Semantics

**Feature**: `057-api-request-omission` | **Date**: 2026-07-16

The spec deliberately left one question open: *how* a request schema should express "this
field may be absent" without also saying "this field may be null". Everything else follows
from that choice. Each decision below was verified against the running code rather than
reasoned about abstractly; the probes are reproducible from `quickstart.md`.

---

## Decision 1 — Express omissibility with an inert default, not a widened type

**Decision**: Each partial-update field is declared with its true value domain and given a
default whose only job is to make the field optional. The default is never forwarded,
because handlers already filter to the fields the caller actually set. Fields whose stored
value domain genuinely includes null keep `| None`; fields whose domain does not, lose it.

```python
name: Annotated[str, Field(max_length=MAX_ITEM_NAME_LENGTH)] = ""   # inert default
external_id: Annotated[str | None, Field(max_length=...)] = None    # genuinely nullable
enabled: bool = False                                               # inert default
```

**Rationale**:

1. **It makes the published contract truthful.** This is the decisive argument. Under the
   current typing, a consumer's generated OpenAPI advertises `name` as
   `{"anyOf": [{"type": "string"}, {"type": "null"}]}` — it tells callers null is
   acceptable. Under the decision it advertises `{"type": "string"}`. Verified directly
   from `model_json_schema()`. FR-003 outlaws a schema that lies about its value domain;
   an alternative that merely relocates the lie from the code to the published contract
   does not satisfy it.
2. **It requires no validation code.** Pydantic rejects null natively once the type no
   longer admits it. Nothing to write, nothing to keep in sync, nothing to forget on a
   newly added field.
3. **The creation schemas already do this**, which is why they never had the bug. The
   decision does not invent a pattern; it propagates the one that already works. This is
   the "existence proof" the spec's Context relies on.
4. **The default's value is irrelevant by construction**, since presence-filtering drops
   unset fields before delegation. Principle X's carve-out for self-evident literals
   (`""`, `0`, `1`, `True`/`False`) covers them exactly.

**Alternatives considered**:

- **Keep `X | None` and add a validator that rejects an explicit null.** Rejected. It was
  the intuitive choice and it survives longest, so it is worth recording *why* it loses.
  Behaviorally it is indistinguishable — both prototypes were run against every case in the
  spec and produced identical results. It loses on three counts. It publishes an OpenAPI
  contract that advertises null and then refuses it at runtime, which is FR-003's exact
  prohibition wearing a different hat. It requires a custom validator on every non-nullable
  field of every partial-update schema, i.e. new code whose omission on a future field is
  silent. And its apparent safety advantage is **illusory**: the argument for it is that its
  `None` defaults degrade harmlessly if presence-filtering is ever dropped, but this was
  tested and is false — it degrades to `external_id=None`, which the service reads as
  *clear*, destroying the stored external identifier. That is `e049b68` reproduced exactly,
  on the one field whose loss caused the original incident. It protects `name` and
  `enabled` while leaving the field that actually matters exposed.
- **A schema-level sentinel (`name: str | UnsetType = UNSET`).** Rejected. It leaks a
  taxomesh-internal marker into the public schema and into every consumer's generated
  documentation, and it cannot be represented in JSON Schema. FR-012 keeps the service's
  private "not provided" marker out of the public surface; introducing a second, public
  marker to solve a problem Pydantic already solves is strictly worse.
- **Leave the schemas alone and validate in the handlers.** Rejected. Handlers receive an
  already-constructed request (Clarification 1), so by then a null has already been accepted
  as valid. Validation must live where construction happens.

**Residual risk, accepted**: presence-filtering becomes load-bearing. If it were ever
dropped, the inert defaults would be forwarded and would overwrite stored values. This risk
is **not introduced by the decision** — it is inherent to presence-based partial updates and
present in the rejected alternative too, where it is worse because it is silent on the
highest-value field. It is bounded by two required tests: the empty-body no-op (US2 scenario
5) fails loudly if filtering is dropped, and the FR-017 drift guard covers the adjacent
failure mode. No further mitigation is warranted.

---

## Decision 2 — Add a branch to the error mapping; do not widen it

**Decision**: `errors.to_tuple` gains a case mapping the external-identifier conflict to
409, placed with the other specific-before-parent cases. Its signature is untouched.

**Rationale**: The divergence is an accident of ordering, verified: `to_tuple` was written
by 028 with an explicit 409 case for the slug conflict; 041 introduced the external-ID
conflict error ten days later and never updated `contrib.api`, so it fell through to the
generic `TaxomeshValidationError → 422` branch. Both errors are direct subclasses of
`TaxomeshValidationError` and both are uniqueness conflicts; nothing chose to treat them
differently. The mapping function already documents that "the mapping order matters:
more-specific subclasses are checked before their parents", and already carries the
precedent — `TaxomeshDuplicateSlugError` "is a validation subclass but maps to 409
(Conflict) rather than 422". The fix is to apply the existing rule to the case it was never
applied to. `_HTTP_409` already exists as a `Final[int]`.

**Alternatives considered**:

- **Leave it at 422.** Rejected by clarification. It would mean knowingly shipping a third
  instance of the seam the feature exists to close.
- **Reparent the exception under a new conflict base class.** Rejected. It would change the
  domain exception hierarchy — which 041 owns and this spec's Assumptions place off-limits —
  to solve a presentation problem local to the API layer. It would also silently alter what
  `except TaxomeshValidationError` catches for existing consumers.

---

## Decision 3 — Guard the class of bug, not just the instance

**Decision**: Two tests are treated as first-class deliverables rather than incidental
coverage: FR-018 asserts a status for every error type the mapping can receive and fails
when one is unlisted; FR-017 asserts every partial-update schema field is accepted by its
service operation.

**Rationale**: Both guard failures that are provably invisible to the existing gates.

For FR-017 this was demonstrated, not assumed: a partial-update schema carrying a field the
service cannot accept passes `mypy --strict` cleanly and fails only at runtime, as a
`TypeError` surfacing to the caller as a 500. The cause is that presence-filtering produces
`dict[str, Any]`, and unpacking it erases the keyword names the type checker would need. The
current design is correct, but the property holding it together is untyped — so it must be
tested.

For FR-018 the evidence is the bug itself. `tests/contrib/test_api_errors.py` already
enumerates error types and asserts their statuses, including "DuplicateSlugError → 409, not
422". It was simply never updated when 041 added a type. A test that enumerates the mapping's
inputs and fails on an unlisted one converts that silent omission into a failing build.

**Alternative considered**: rely on review to catch a new error type. Rejected — that is the
control that already failed once, and this feature exists partly because of it.

---

## Resolved unknowns

No `NEEDS CLARIFICATION` markers remain in Technical Context. The three questions raised
during `/speckit.clarify` (validation boundary, rule scope, conflict status) are recorded in
the spec's Clarifications section. The one question the spec deferred here (Decision 1) is
resolved above.
