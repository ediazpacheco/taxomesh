# Feature Specification: API Request Omission and Explicit-Null Semantics

**Feature Branch**: `057-api-request-omission`  
**Created**: 2026-07-15  
**Status**: Draft  
**Input**: User description: "Create a new flow-forward corrective specification for the public request semantics in taxomesh.contrib.api. This specification reconciles behavior already merged into main. Treat completed feature directories as immutable historical records: do not modify specs 028-contrib-api, 041-unique-external-id, or 043-clear-external-id. Create one new numbered feature specification and link those three specs as predecessors. Cover creating items without external IDs, and preserving omitted PATCH fields, auditing the field-presence bug class across every partial-update handler."

## Context

Three predecessor specs each own one piece of external-identifier behavior, and no spec owns the seam between them.

**028-contrib-api** owns the original public schema and handler contract for `taxomesh.contrib.api`. It defined item creation with an empty-string external identifier as the "absent" marker, and defined partial updates as "apply only non-null values" — a rule that makes an explicitly supplied null indistinguishable from a field the caller never mentioned.

**041-unique-external-id** owns nullable and unique external-identifier semantics. It replaced the empty-string-as-absent convention with a true absence value at the domain level, and made non-absent external identifiers unique per entity type, with absent values exempt from that uniqueness.

**043-clear-external-id** owns service-level omitted/set/clear semantics. It established that an update caller has three distinct intents — leave unchanged, set to a value, clear to no value — and deliberately fenced the mechanism off as private: the way "not provided" is represented is an internal detail that callers must not depend on.

**This spec aligns those three contracts at the public HTTP-handler boundary.** That boundary is where the seam tore, and it tore twice in ways already merged to `main` without a governing spec:

- Item creation still carried 028's empty-string default after 041 made empty strings collide under the uniqueness constraint. Every item created without an external identifier persisted the same empty string; the second such item conflicted.
- Partial item updates forwarded the external identifier unconditionally, so a request that only changed an item's name silently **destroyed** its stored external identifier.

A third tear is still open, and this spec closes it too. When 041 introduced the external-identifier conflict error, it did not update 028's error mapping, which had been written ten days earlier with an explicit case for the slug conflict. The new error therefore fell through to the generic validation status and has been reaching callers as an unprocessable-entity response ever since — while its structural twin, the slug conflict, correctly reports a conflict. Nothing chose that difference. It is the same seam, torn the same way: 041 changed the domain and the public boundary did not follow.

### The single rule

Both defects share one root cause: **the request schemas expressed "you may omit this field" by widening the field's type to allow null.** Those are different statements. "May be absent" is a fact about the request envelope. "May be null" is a fact about the field's value domain. Conflating them makes a supplied null and an unmentioned field arrive as the same thing, and that is precisely how a rename came to erase an external identifier.

This spec asserts one rule, from which every requirement below follows:

> **An omitted field carries no instruction. A present field means "assign exactly this value", and is rejected if that value is not valid for that field.**

This rule has no special cases. It reads uniformly across every field:

| Request | Outcome | Why |
|---|---|---|
| field omitted | stored value untouched | no instruction given |
| `{"name": "x"}` | name becomes `"x"` | valid name |
| `{"name": null}` | rejected | a name has no null value |
| `{"slug": ""}` | slug cleared | empty string is a valid slug, and is how a slug is cleared |
| `{"slug": null}` | rejected | a slug has no null value |
| `{"external_id": "x"}` | external identifier becomes `"x"` | valid |
| `{"external_id": null}` | external identifier cleared | null **is** a valid external identifier |

The external identifier is not governed by a different rule. It is the only field whose value domain includes null — 041 made it so — and therefore the only field for which "assign null" is a coherent instruction. Any future nullable field obeys the same rule with no new logic; any future non-nullable field rejects null with no new logic.

The rule governs every public request, for creation and partial update alike. The creation requests **already satisfy it** — they express omissibility with real default values rather than by widening a field's type, so they reject a null name or a null slug today and accept a null external identifier. That is not a coincidence; it is the same rule, and it is why creation needs no correction beyond the empty-string default that 041 invalidated. The partial-update requests are where omissibility was expressed by widening the type instead, and they are where both defects appeared. The creation surface is the existence proof that the rule is natural to satisfy.

### Scope honesty

Both defects are fixed in `main` (commits `e93ef5d` and `e049b68`). Neither fix had a spec, which is a debt against the constitution's spec-first principle, and this spec repays it. But this is **not purely a retrospective record**: the audit that produced it surfaced live gaps requiring new behavior. User Story 1 is merged and covered. User Story 2 is merged but unproven on three of four storage backends. User Stories 3 and 4 are not implemented at all. The plan and tasks for this feature must preserve that distinction rather than presenting the whole feature as either purely retrospective or purely greenfield.

## Clarifications

### Session 2026-07-15

- Q: FR-002 requires an invalid value to be rejected rather than discarded — but where does taxomesh's guarantee end, given that `to_tuple` accepts only a taxomesh error and the handlers receive an already-constructed request? → A: Schema-level only. taxomesh guarantees that constructing a request with an invalid value raises a validation error; mapping that to an HTTP response belongs to the consuming framework. The error-mapping primitive and the exception hierarchy are unchanged.
- Q: Does the single rule govern every request type, or only partial updates? → A: Every request type. The creation requests already satisfy it, so no production change is needed there; they gain regression coverage so the conformance cannot silently lapse.

### Session 2026-07-16

- Q: An external-identifier uniqueness conflict surfaces with the generic validation status, while the structurally identical slug uniqueness conflict surfaces with the conflict status. Should this spec align them? → A: Yes. Both are uniqueness conflicts and MUST surface identically, with the conflict status. The divergence is an artifact of the conflict error being introduced after the error-mapping primitive was written — the same 041-versus-028 seam this spec exists to close — not a deliberate distinction.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Create items without an external identifier (Priority: P1)

An application creates items that have no counterpart in any external system. It omits the external identifier entirely. Absence must be recorded as genuine absence, and any number of such items must coexist.

**Why this priority**: Creating an item without an external identifier is the most common creation path for consumers that do not integrate an external system. Under the uniqueness constraint, getting absence wrong corrupts data on the second create — a total failure of the primary path.

**Independent Test**: Create two items through the public create handler supplying only a name, on each supported storage backend. Both succeed, both report an absent external identifier, and both are independently retrievable.

**Acceptance Scenarios**:

1. **Given** a create request that omits the external identifier, **When** the item is created, **Then** the stored external identifier is the absence value and never an empty string.
2. **Given** two create requests that both omit the external identifier, **When** both are created, **Then** both succeed, receive distinct library-assigned identifiers, and neither triggers an external-identifier conflict.
3. **Given** the in-memory, JSON, YAML, and Django-backed storage backends, **When** scenarios 1 and 2 run against each, **Then** the observable outcome is identical on every backend.
4. **Given** a create request that supplies an external identifier string, **When** the item is created, **Then** that string is stored unchanged.

---

### User Story 2 - Omitted fields in a partial update are preserved (Priority: P1)

An application sends a partial update changing one field. Every field it did not mention must survive untouched. In particular, renaming an item must not disturb its external identifier.

**Why this priority**: The failure mode is silent, irreversible data loss on the most ordinary update a consumer can make. It is fixed in `main`, but the fix is currently verified against one storage backend only — and the specific path it exercises (clearing an external identifier) is the same path whose uniqueness constraint caused the Story 1 defect on the Django backend. The fix is therefore unproven exactly where it is most likely to differ.

**Independent Test**: Create an item with an external identifier, send a partial update that mentions only the name, and confirm the external identifier survives — on each supported storage backend.

**Acceptance Scenarios**:

1. **Given** an item with a stored external identifier, **When** a partial update mentions only the name, **Then** the name changes and the external identifier is unchanged.
2. **Given** an item with a stored external identifier, **When** a partial update supplies a different external identifier string, **Then** the stored external identifier is replaced by that string.
3. **Given** an item with a stored external identifier, **When** a partial update supplies an explicit null external identifier, **Then** the stored external identifier is cleared.
4. **Given** the in-memory, JSON, YAML, and Django-backed storage backends, **When** scenarios 1 through 3 run against each, **Then** the observable outcome is identical on every backend.
5. **Given** a partial update that mentions no fields at all, **When** it is applied, **Then** it succeeds and no stored field value changes.
6. **Given** the partial-update handlers for categories, items, and tags, **When** each receives a request mentioning a strict subset of its fields, **Then** none of the unmentioned fields change — the same presence rule holds for all three handlers, with no exceptions.

---

### User Story 3 - A present field is assigned or rejected, never silently discarded (Priority: P2)

An application sends a partial update naming a field explicitly. The system either assigns the supplied value or tells the caller the value was invalid. It never reports success for an instruction it discarded.

**Why this priority**: Today every field except the external identifier accepts an explicit null, returns success, and changes nothing. The caller is told their update succeeded when it was thrown away. This violates the constitution's prohibition on silent failures, and it is the same conflation of "absent" with "null" that caused Stories 1 and 2 — the last place it still survives. It destroys no data and no known consumer depends on the path, so it ranks below the two data-integrity stories.

**Independent Test**: Send a partial update setting a non-nullable field to null and confirm a validation error is raised rather than a success response.

**Acceptance Scenarios**:

1. **Given** a partial item update that explicitly sets the name to null, **When** it is validated, **Then** it is rejected with a validation error and no stored value changes.
2. **Given** a partial item update that explicitly sets the external identifier to null, **When** it is applied, **Then** the external identifier is cleared and the request succeeds — because null is a valid external identifier.
3. **Given** a partial item update that explicitly sets the slug to null, **When** it is validated, **Then** it is rejected with a validation error; supplying an empty string instead clears the slug.
4. **Given** a partial update that omits a non-nullable field entirely, **When** it is applied, **Then** it succeeds and that field is unchanged — omission remains always legal.
5. **Given** the partial-update handlers for categories, items, and tags, **When** each receives an explicit null on a non-nullable field, **Then** all three reject it consistently.

---

### User Story 4 - Category external identifier and enabled state are reachable (Priority: P2)

An application manages categories through the public API and needs to set, change, or clear a category's external identifier, and to enable or disable a category.

**Why this priority**: The service layer already supports both operations with full omitted/set/clear semantics, but the public request schema exposes neither, so consumers cannot reach them at all. This is a completeness gap in the public surface rather than a defect — nothing is broken, something is merely unreachable. It is included here because the external-identifier semantics it needs are exactly the ones this spec defines, and specifying them twice would invite the two surfaces to drift apart again.

**Independent Test**: Through the public partial-update handler for categories, set a category's external identifier, then clear it, then confirm an unrelated update leaves it intact.

**Acceptance Scenarios**:

1. **Given** a category with no external identifier, **When** a partial update supplies an external identifier string, **Then** it is stored.
2. **Given** a category with a stored external identifier, **When** a partial update mentions only the name, **Then** the external identifier is unchanged.
3. **Given** a category with a stored external identifier, **When** a partial update supplies an explicit null external identifier, **Then** it is cleared.
4. **Given** a category, **When** a partial update supplies an enabled state, **Then** that state is stored.
5. **Given** two categories, **When** a partial update would give one an external identifier already held by the other, **Then** the request is rejected with an external-identifier conflict, surfaced with the same status as a slug conflict.

### Edge Cases

- **Absence versus empty string on create**: an omitted external identifier must never be normalized into an empty string at any layer. Empty string and absence are different values, and only absence is exempt from uniqueness.
- **Explicitly supplied absence on create**: a create request that explicitly supplies a null external identifier must behave identically to one that omits it, because null is a valid external identifier and is also the default.
- **Empty partial update**: a request body mentioning no fields is valid and must be a no-op on stored values.
- **Unmentioned versus null**: these are distinct for every field, not only the external identifier. Story 2 governs the first, Story 3 the second.
- **Slug clearing**: the slug is cleared by an empty string because an empty string is a valid slug and null is not. This follows from the single rule rather than contradicting it, and is not changed here.
- **Uniqueness on update**: setting an external identifier already held by a different record of the same type must be rejected, on every backend, whether reached through the item or the category handler, and must surface as a conflict rather than as a generic validation failure.
- **A new error type added elsewhere**: an error type introduced outside the public API layer must not reach a caller with a generic status merely because nobody updated the error mapping. This is how the external-identifier conflict came to differ from its slug counterpart.
- **Unknown fields in a request body**: unchanged from 028 — extra fields are ignored, not rejected.
- **Schema and service parameter drift**: because partial-update handlers forward only the fields a caller mentioned, a request schema field with no corresponding service parameter cannot be detected by static type checking and would surface as an unhandled runtime failure. This class of drift must be caught by the test suite instead.
- **Repeated clears**: clearing an already-absent external identifier is a no-op and must not raise a conflict, since absence is exempt from uniqueness.

## Requirements *(mandatory)*

### Functional Requirements

**The single rule**

- **FR-001**: A field omitted from a request MUST carry no instruction, and MUST leave the corresponding stored value untouched.
- **FR-002**: A field present in a request MUST mean "assign this value", and the supplied value MUST either be assigned or rejected by request validation. It MUST NOT be accepted and discarded.
- **FR-003**: A request schema MUST NOT express omissibility by widening a field's value domain. The set of values a request field accepts MUST match the set of values the corresponding stored field can hold; whether the field may be absent MUST be expressed independently of that set.
- **FR-004**: A request schema default value MUST NOT be interpretable as an intent to update.

**Error surfacing**

- **FR-005**: The rejection required by FR-002 MUST occur at request validation. Constructing a request that carries an invalid value for a field MUST raise a validation error, and this is the full extent of taxomesh's guarantee: translating that error into an HTTP response is the consuming framework's responsibility, consistent with 028's framework-agnostic boundary. Accordingly, the error-mapping primitive MUST NOT be widened to accept request-validation errors, and the taxomesh exception hierarchy MUST NOT gain a member representing them.
- **FR-006**: An external-identifier uniqueness conflict MUST surface to the caller with the conflict status (409), identically to the structurally equivalent slug uniqueness conflict, rather than with the generic validation status (422). This MUST hold wherever the conflict arises — through the item handler or the category handler. This requirement adds a case to the existing error-mapping primitive; it does not widen that primitive's accepted input and therefore does not conflict with FR-005.

**Consequences for the external identifier**

- **FR-007**: The external identifier's value domain includes null. Accordingly, for item and category partial updates: omission MUST preserve the stored value; an explicit string MUST replace it; an explicit null MUST clear it.
- **FR-008**: The external identifier MUST be the only field for which an explicit null is accepted, for as long as it remains the only field whose stored value domain includes null. This MUST hold as a consequence of FR-002 and FR-003, not as a field-specific exception.
- **FR-009**: The item creation request MUST treat the external identifier as optional, and MUST represent an omitted external identifier as the absence value — never as an empty string.
- **FR-010**: Any number of items created without an external identifier MUST coexist without triggering an external-identifier conflict.

**Uniform application**

- **FR-011**: Every public request schema MUST obey FR-001 through FR-004 identically, for creation and for partial update alike. No request schema may be exempt. The creation requests already conform; that conformance MUST be locked in by tests so it cannot lapse, in particular so that a creation field cannot later be made to accept null merely to express that it may be omitted.
- **FR-012**: The mechanism representing "not provided" at the service layer MUST remain private. The public request schemas and handlers MUST NOT require callers to import, name, or construct it.

**Category surface**

- **FR-013**: The category partial-update request MUST expose the external identifier with the semantics required by FR-007.
- **FR-014**: The category partial-update request MUST expose the enabled state.
- **FR-015**: External-identifier uniqueness MUST be enforced for updates reached through the category handler exactly as for the item handler, and MUST surface with the status required by FR-006.

**Verification**

- **FR-016**: The behavior required by User Stories 1 and 2 MUST be verified through the public handlers against the in-memory, JSON, YAML, and Django-backed storage backends, and MUST be identical on all four.
- **FR-017**: The test suite MUST guard against a partial-update request schema declaring a field that the corresponding service operation cannot accept, since static type checking cannot detect this.
- **FR-018**: The error-mapping primitive MUST have a test asserting the status of every taxomesh error type it can receive, so that a future error type added outside `contrib.api` cannot silently inherit a generic status — the omission that produced the divergence FR-006 corrects.

**Lineage and release**

- **FR-019**: This spec supersedes 028's public contract in three scoped respects: item-creation external-identifier defaulting, partial-update null handling, and the error-mapping status for external-identifier conflicts. The supersession MUST be recorded in this feature's own artifacts — its Dependencies section and its contract document — and MUST NOT be recorded by editing 028's. The historical spec directories for 028, 041, and 043 MUST NOT be altered in any way. This follows the precedent set by 041, which recorded its supersession of 013, 021, and 032 in its own Dependencies section rather than by amending theirs, and it is why a reader of 028 alone will still see the superseded contract: the spec directories are an append-only historical record, and 057 is the current word on these three points.
- **FR-020**: The public documentation for the affected request schemas and handlers MUST state the single rule and its consequences in the existing house style, so that a caller can predict the outcome of omitting, setting, or nulling any field.
- **FR-021**: The CHANGELOG MUST record these changes, including both behavioral breaks — the rejection required by FR-002 and the status change required by FR-006 — and the package version MUST be bumped following the established convention.

### Key Entities

- **Create request**: a caller's statement of the field values a new record should have. Every unmentioned optional field means "use the default".
- **Partial-update request**: a caller's statement of intent about a subset of a record's fields. Its meaning is defined by two independent facts per field — whether the field is present, and what value it carries — never by the value alone.
- **External identifier**: an optional caller-supplied reference linking a record to an entity in an external system. Its value domain includes null. Unique across records of the same type when non-null; unconstrained when null.
- **Absence value**: the single canonical representation of "this record has no external identifier". Distinct from the empty string, and the only value exempt from uniqueness.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Creating any number of items with no external identifier succeeds on 100% of the four supported storage backends, with zero external-identifier conflicts — verified by a backend-parametrized test exercising the public create handler.
- **SC-002**: A partial update mentioning a single field leaves 100% of unmentioned fields unchanged, on 100% of the four supported storage backends — verified by a backend-parametrized test exercising the public partial-update handlers.
- **SC-003**: The number of request fields that can accept a value and silently discard it is zero, across every partial-update handler — verified by a test per handler per non-nullable field.
- **SC-004**: For every field of every public request schema — creation and partial update alike — the outcome of omitting it, setting it, and nulling it is predictable from the single rule alone, with zero field-specific exceptions — verified by a table-driven test enumerating all three cases per field.
- **SC-005**: All three of the external identifier's update intents — preserve, replace, clear — are reachable through the public item handler and the public category handler, and each is covered by at least one test.
- **SC-006**: Every taxomesh error type that can reach a caller through the public handlers has an asserted status, and semantically equivalent errors assert identical statuses — zero divergences — verified by a test that enumerates the error types the mapping accepts and fails if one is unlisted.
- **SC-007**: 100% of the tests that existed before this feature pass unchanged, except for tests in exactly two classes, whose members must be enumerated in the plan rather than estimated: (a) tests asserting that an explicit null is silently ignored, which encode the defect FR-002 removes; and (b) tests asserting the default value of an omitted partial-update field, which encode the type-widening FR-003 removes and must be rewritten to assert presence rather than default value. No test outside these two classes may change.
- **SC-008**: All quality gates pass: lint, format, strict type checking, and the full test suite at no less than 80% coverage.

## Assumptions

- Two of the behaviors specified here are already implemented and merged to `main` (commits `e93ef5d` and `e049b68`; neither bumped the version or the CHANGELOG, so neither has shipped in a release). This spec is written after the fact for those behaviors and describes them as requirements in the normal normative voice; the compensating evidence is the existing test suite, which this spec extends rather than replaces. The behaviors in User Stories 3 and 4 are **not** implemented and are new work. The plan and tasks MUST preserve this distinction.
- The domain-level type and uniqueness semantics of the external identifier are settled by 041 and are not reopened here. In particular, this spec takes as given that the external identifier's value domain includes null and that no other public request field's does — FR-008 is scoped to that fact rather than to the field's name. FR-006 changes only how 041's conflict error is surfaced to an HTTP caller, not when it is raised.
- Request validation is the consuming framework's step: taxomesh's handlers receive an already-constructed request, so taxomesh is not in the code path that turns a request body into a validation failure. FR-005 therefore scopes the guarantee to what taxomesh can actually enforce — the request schema's own rejection of an invalid value — and leaves the HTTP status to the framework. Under a framework that validates request models automatically, no consumer code is needed to obtain the correct status.
- The service-layer omitted/set/clear contract is settled by 043 and is not reopened here. This spec constrains only how the public HTTP boundary expresses those intents.
- This feature carries two breaking changes, both acceptable because the project is in a pre-1.0 alpha series where such breaks do not require a major version bump, and neither has a known dependent: FR-002 breaks any consumer sending explicit nulls and relying on them being ignored; FR-006 breaks any consumer branching on the generic validation status for an external-identifier conflict. Both are corrections of behavior that was never deliberate — 028's stability guarantee covers the error-mapping statuses, and FR-019 records the supersession rather than leaving the guarantee silently violated.
- The creation requests already satisfy the single rule, verified against the current schemas: every non-nullable field rejects a null, and the external identifier accepts one. FR-011's extension of the rule to creation therefore adds regression coverage rather than production work, and the plan MUST NOT budget implementation effort for it.
- The category creation request has no external identifier field, and adding one is out of scope; this spec extends only the category *partial-update* request per FR-013 and FR-014.
- Backend parity coverage depends on the parametrized fixture infrastructure established by 036-service-repo-parity; tests requiring it must be positioned to inherit it.

## Dependencies

- **028-contrib-api**: Owns the original public schema and handler contract for `taxomesh.contrib.api`, including the framework-agnostic handler shape and the sole error-mapping primitive. This spec supersedes it **for** three scoped points only — the item-creation external-identifier default; the treatment of an explicitly supplied null in partial updates (028's rule that handlers apply only non-null values); and the mapped status for an external-identifier conflict. The third point falls inside 028's stability guarantee, which covers the error-mapping statuses; FR-019 records that supersession explicitly rather than leaving the guarantee quietly broken. Every other part of the 028 contract stands, including the handler signatures, the response body shape, and the guarantee itself as applied to everything not listed here.
- **041-unique-external-id**: Introduced the nullable external identifier on the domain models and the uniqueness constraint that exempts absent values (released in 0.1.0a30), along with the conflict error raised when uniqueness is violated. This spec depends on those semantics and propagates them to the public boundary, which 041 did not cover — neither the request schemas nor the error mapping, which is why the conflict error has been reaching callers with a generic status since 041 shipped.
- **043-clear-external-id**: Introduced the three-state omitted/set/clear contract at the service layer, and declared its representation mechanism private to the service. This spec depends on that contract and defines how the public HTTP boundary expresses the same three intents without exposing the private mechanism.
- **036-service-repo-parity**: Parity test infrastructure for cross-backend validation. FR-016 depends on it.
