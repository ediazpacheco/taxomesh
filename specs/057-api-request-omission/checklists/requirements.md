# Specification Quality Checklist: API Request Omission and Explicit-Null Semantics

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-07-15
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- **Partially retrospective.** User Story 1 and the code path behind User Story 2 are
  already implemented and merged to `main` (commits `e93ef5d`, `e049b68`); the spec
  describes them in the normal normative voice, with the existing test suite as
  compensating evidence — the same convention used by `022-unified-str-admin-links`.
  User Stories 3 and 4 are new work. The Context section's "Scope honesty" subsection
  and the first Assumptions bullet carry this disclosure, and the spec requires the
  plan and tasks to preserve the distinction rather than presenting the feature as
  uniformly retrospective or uniformly greenfield.

- **Commit SHAs appear in the spec.** Normally an implementation detail, they are
  retained deliberately: a corrective spec's central claim is *which* behavior is
  already merged, and that claim is unverifiable without them. They are cited as
  historical record, never as a prescription.

- **Storage backends are named in SC-001, SC-002 and FR-014.** These are the four
  backends the public contract must behave identically across, and enumerating them
  was an explicit requirement of the feature request. They describe the parity
  obligation's scope, not an implementation choice — the same convention as
  `056` SC-004 ("across all repository backends covered by the existing parametrized
  suite") and `046`'s dependency on `036-service-repo-parity`.

- **No mechanism is prescribed.** The spec deliberately states *what* must be
  distinguished (a field's presence from its value) and never *how*. The choice of
  representation for "omitted" in the request schemas, and the means of rejecting an
  invalid value, are left entirely to `/speckit.plan`.

- **`/speckit.clarify` session 2026-07-15 asked two questions, both resolved** and
  integrated (see the spec's Clarifications section):
  1. *Validation boundary* — taxomesh's FR-002 guarantee ends at request-model
     construction; the consuming framework maps the failure to HTTP. This closed a
     real tension: `to_tuple` is typed to accept only a `TaxomeshError`, Pydantic's
     `ValidationError` is not one, and Principle IX freezes `to_tuple` as the sole
     error-mapping primitive. The chosen answer resolves it by scoping the guarantee
     to what taxomesh can actually enforce, leaving both the primitive and the
     exception hierarchy untouched. Recorded as FR-005, which also explicitly
     forecloses the two rejected alternatives.
  2. *Rule scope* — the single rule governs every request schema, creation included.
     The creation requests were verified to already conform, so this adds regression
     coverage and no production work; recorded in FR-010 and in Assumptions, which
     instructs the plan not to budget effort for it.

- **`/speckit.clarify` session 2026-07-16 asked one question, resolved** and integrated:
  3. *Conflict status* — an external-identifier uniqueness conflict must surface with
     the conflict status (409), identically to the structurally equivalent slug
     conflict, rather than with the generic validation status (422). The divergence was
     verified live and is an artifact of ordering: 028 wrote the error mapping with an
     explicit slug-conflict case; 041 added the conflict error ten days later and never
     updated `contrib.api`, so the new error fell through to the generic branch. This is
     a third instance of the same 041-versus-028 seam the spec exists to close, and it
     is now named as such in Context. Recorded as FR-006, with FR-018 adding a guard so
     a future error type cannot silently inherit a generic status the same way.
     Verified that no existing test asserts a status for this error, so the change
     rewrites no test — recorded in SC-007 as a claim the plan must confirm rather than
     assume. The supersession scope of 028 widened from two points to three as a result,
     and the third falls inside 028's stability guarantee (which covers the error-mapping
     statuses); FR-019 and the Dependencies entry record that explicitly rather than
     leaving the guarantee quietly broken.

- **Three design decisions were resolved with the user before writing**, so no
  [NEEDS CLARIFICATION] markers were needed:
  1. An explicit null on a non-nullable field is **rejected with a validation error**,
     not silently ignored (User Story 3) — chosen over documenting the existing
     silent-discard behavior as intended.
  2. The spec **reconciles the merged fixes and closes the surrounding gaps**
     (missing cross-backend parity, the drift blind spot, the superseded 028 contract
     statement) rather than recording the merged behavior alone.
  3. The category partial-update surface **gains the external identifier and enabled
     state** (User Story 4) rather than deferring them to a later spec.

- **The `external_id` asymmetry was challenged during authoring and the framing
  changed as a result.** An earlier draft presented "null clears `external_id`, null is
  rejected everywhere else" as a field-specific exception, which is a design smell.
  It is not one: `external_id` is simply the only field whose stored value domain
  includes null (established by `041`), so it is the only field for which "assign null"
  is a coherent instruction. The spec now leads with the single rule this follows from
  (Context → "The single rule") and derives every requirement from it. FR-006 is
  explicitly scoped to the *property* of being nullable rather than to the field's
  name, so a future nullable field needs no new specification.
