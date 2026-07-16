---
description: "Task list for 057-api-request-omission implementation"
---

# Tasks: API Request Omission and Explicit-Null Semantics

**Input**: Design documents from `/specs/057-api-request-omission/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/api-request-contract.md ✅

**Tests**: TDD is mandatory per CLAUDE.md and the project constitution. Every implementation
task is preceded by its failing test task. No implementation task exists without one.

**Organization**: Grouped by user story. The plan's **Work Classification** is load-bearing and
is honored here — US1 is validation-only, US2 is tests-only, US3/US4/FR-006 are new production
code. Nothing is treated as greenfield that is already merged to `main`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1–US4; cross-cutting requirement tasks (FR-006/017/018) carry no story label
- File paths are exact and relative to the repository root

## Baseline facts (verified against the current tree, do not re-derive)

- Current version: `pyproject.toml` → `0.1.0a46`. FR-021 bump target: `0.1.0a47`.
- `errors.to_tuple` already defines `_HTTP_409: Final[int]` and already maps
  `TaxomeshDuplicateSlugError → 409`. FR-006 reuses `_HTTP_409`; the branch pattern already
  exists to copy.
- `TaxomeshExternalIdConflictError` is a subclass of `TaxomeshValidationError`
  (`taxomesh/exceptions.py:63`) — which is exactly why it currently falls through to the
  422 branch. Its 409 branch must be placed **before** the `TaxomeshValidationError` check.
- The backend-parametrized `service` fixture lives at `tests/service/conftest.py`
  (`params=["in_memory", "json", "yaml", "django"]`). Tests requiring four-backend parity
  MUST live under `tests/service/` to inherit it; `tests/contrib/` overrides it with an
  in-memory-only fixture (this override is how US2's original coverage gap arose).
- Django-parametrized service tests require `tests/service/test_parity_fixture.py` to run
  first (recorded environment quirk) — run the whole `tests/service/` directory, not the new
  file alone.

---

## Phase 1: Setup (Baseline)

**Purpose**: Establish the pre-feature green baseline so SC-007's "tests that existed before
this feature pass unchanged" is measurable, and so failing TDD tests are unambiguously new.

- [X] T001 Run the full suite on the current tree and record the result as the SC-007 baseline:
  `pytest --cov=taxomesh --cov-fail-under=80`. Confirm green before writing any new test. Note
  the four SC-007 class-(b) tests slated for rewrite (T014, T019) currently pass as-is.

---

## Phase 2: Foundational (Shared Invariant)

**Purpose**: Lock in the single rule on the creation surface (FR-011). This is
**regression coverage only** — the creation schemas already conform (data-model.md verified it),
and the spec's Assumptions forbid budgeting production effort here. It is placed first because
it is the invariant every story depends on and it touches no production code, so it cannot
break anything downstream.

**⚠️ No blocking production prerequisites exist.** Changes are isolated to `taxomesh/contrib/api/`
and each story is independently testable. This phase adds tests only.

- [X] T002 [P] FR-011 / SC-004 regression tests locking creation conformance in
  `tests/contrib/test_api_schemas.py`: assert `CreateItemRequest`, `CreateCategoryRequest`,
  and `CreateTagRequest` reject an explicit `null` on every non-nullable field
  (`name`, `slug`, `description`, `metadata`) with a `ValidationError`, and that
  `CreateItemRequest` accepts `external_id=None`. These pass today — they exist so a creation
  field can never later be widened to `X | None` merely to express omissibility.

**Checkpoint**: The single rule is pinned on the creation surface; partial-update work can proceed.

---

## Phase 3: User Story 1 - Create items without an external identifier (Priority: P1) 🎯 MVP

**Goal**: An omitted external identifier is stored as genuine absence (`None`), never `""`, and
any number of such items coexist under the uniqueness constraint.

**Independent Test**: Create two items supplying only a name, on each backend; both succeed,
both report `external_id is None`, both are independently retrievable.

**Work Classification**: **Implemented** (`e93ef5d`). Parity coverage already exists at
`tests/service/test_api_create_item_parity.py` across all four backends. **Validation only —
no new code, no new test.**

- [X] T003 [US1] Validate US1: run `pytest tests/service/test_api_create_item_parity.py` (via the
  full `tests/service/` directory for the Django quirk) and confirm it passes on all four
  backends. If it passes, US1 is done; if it fails, stop and report — do not modify production
  code without escalating, since US1 is supposed to be merged and green.

**Checkpoint**: US1 confirmed green on four backends (SC-001).

---

## Phase 4: User Story 2 - Omitted fields in a partial update are preserved (Priority: P1)

**Goal**: A partial update changing one field leaves every unmentioned field untouched — in
particular, renaming an item must not disturb its stored external identifier — on all four
backends.

**Independent Test**: Create an item with an external identifier, PATCH only the name, confirm
the external identifier survives — on each backend.

**Work Classification**: **Implemented** (`e049b68`), but proven on `InMemoryRepository` only.
**Tests only — add the missing four-backend parity coverage (FR-016).** This is the same clear
path whose uniqueness constraint caused the US1 defect, so it is exactly where behavior is most
likely to differ across backends.

- [X] T004 [US2] Create the four-backend PATCH-parity test `tests/service/test_api_patch_parity.py`
  (located under `tests/service/` to inherit the parametrized `service` fixture — NOT under
  `tests/contrib/`). Exercise the public handlers (`handlers.update_item`, `handlers.update_category`,
  `handlers.update_tag`) and cover, per SC-002 / FR-016 / US2 scenarios 1–6:
    - PATCH mentioning only `name` leaves a stored `external_id` unchanged (scenario 1).
    - PATCH supplying a different `external_id` string replaces it (scenario 2).
    - PATCH supplying `external_id=None` clears it (scenario 3).
    - An empty request body (`UpdateItemRequest()`) is a no-op on every stored field (scenario 5) —
      this test is the loud tripwire if presence-filtering is ever dropped (research.md residual risk).
    - The subset-preservation rule holds identically for the category, item, and tag handlers (scenario 6).
  This is verification of already-merged behavior; it is expected to **pass** on all four backends.
  If any backend fails, that is a real US2 gap — report it.

**Checkpoint**: US1 + US2 confirmed identical on all four backends (SC-001, SC-002, SC-005 clear/replace/preserve).

---

## Phase 5: Error surfacing — FR-006 conflict status + FR-018 completeness guard

**Purpose**: Close the third, still-open tear: `TaxomeshExternalIdConflictError` currently
falls through to 422 while its structural twin `TaxomeshDuplicateSlugError` returns 409. This is
new production code (one branch) plus two tests. It precedes US4 because US4 scenario 5 asserts
the category external-ID conflict surfaces with this status. No story label — this is a
cross-cutting error-mapping requirement.

- [X] T005 [P] TDD (FR-006): in `tests/contrib/test_api_errors.py`, add a test asserting
  `to_tuple(TaxomeshExternalIdConflictError(...))` returns status `409` (mirroring the existing
  `TaxomeshDuplicateSlugError → 409` assertion). This test **must fail** against the current
  `errors.py` (it returns 422).
- [X] T006 [P] TDD (FR-018): in `tests/contrib/test_api_errors.py`, add a mapping-completeness
  test that enumerates every `TaxomeshError` subclass reachable through the public handlers and
  asserts each has an explicitly asserted, non-500-fallthrough status — failing if a type is
  unlisted. This encodes SC-006 and **must fail** now because `TaxomeshExternalIdConflictError`
  is unlisted (the precise omission that produced the divergence).
- [X] T007 Implement FR-006 in `taxomesh/contrib/api/errors.py`: import
  `TaxomeshExternalIdConflictError` and add `if isinstance(exc, TaxomeshExternalIdConflictError):
  return _HTTP_409, body` **before** the `TaxomeshValidationError` branch (specific-before-parent,
  as the module docstring already prescribes). Reuse the existing `_HTTP_409`; do not add a
  constant. Do NOT widen `to_tuple`'s signature (FR-005). Confirm T005 and T006 now pass.

**Checkpoint**: External-ID conflict surfaces as 409 through both handlers (SC-006); a future
error type added outside `contrib.api` can no longer inherit a generic status silently.

---

## Phase 6: User Story 3 - A present field is assigned or rejected, never silently discarded (Priority: P2)

**Goal**: A partial update naming a non-nullable field with `null` is rejected at request
validation, not accepted and discarded. `external_id` remains the sole field accepting `null`
(as "clear"), because it is the only field whose stored domain includes null.

**Independent Test**: Send a PATCH setting a non-nullable field to `null`; confirm a
`ValidationError` is raised rather than a success response.

**Work Classification**: **New production code.** Retype the three partial-update schemas per
data-model.md — express omissibility with an inert default, NOT by widening the type
(research.md Decision 1). No custom validators.

### Tests for User Story 3 (write first; must FAIL before T017) ⚠️

- [X] T008 [P] [US3] TDD (SC-003, US3 scenarios 1,3,5) — item null-rejection in
  `tests/contrib/test_api_handlers.py` (or `test_api_schemas.py`): assert `UpdateItemRequest(name=None)`,
  `UpdateItemRequest(slug=None)`, `UpdateItemRequest(enabled=None)`, and `UpdateItemRequest(metadata=None)`
  each raise `ValidationError`, while `UpdateItemRequest(external_id=None)` remains valid and clears
  (scenario 2). Must fail today (these currently succeed and return `None`).
- [X] T009 [P] [US3] TDD (SC-003, US3 scenario 5) — tag null-rejection in
  `tests/contrib/test_api_handlers.py`/`test_api_schemas.py`: assert `UpdateTagRequest(name=None)`
  raises `ValidationError`. Must fail today.
- [X] T010 [P] [US3] TDD (US3 scenario 4 / FR-001) — omission-remains-legal: assert
  `UpdateItemRequest()` and `UpdateTagRequest()` construct successfully and that
  `model_dump(exclude_unset=True)` is empty. (Complements the four-backend no-op in T004.)
- [X] T011 [P] [US3] TDD (SC-004) — item presence/value table-driven test in
  `tests/contrib/test_api_schemas.py`: enumerate omitted / valid-value / `null` for every
  `UpdateItemRequest` field, asserting untouched (absent from `model_fields_set`) / assigned /
  rejected-or-cleared per the data-model.md matrix. Must fail today for the non-nullable fields.
- [X] T012 [US3] SC-007 class (b) rewrite — `tests/contrib/test_api_schemas.py::TestUpdateItemRequest::test_all_none_is_valid`:
  rewrite to construct with fields **omitted** and assert **presence** via `model_fields_set`
  (not default values), and rename accordingly (e.g. `test_all_fields_omittable`). Retain the
  `external_id is None`-when-set assertion. This is one of the four enumerated SC-007 tests.
- [X] T013 [US3] SC-007 class (b) rewrite — `tests/contrib/test_api_schemas.py::TestUpdateTagRequest::test_all_none_is_valid`:
  rewrite to assert presence via `model_fields_set` and rename. Second of the four enumerated tests.

### Implementation for User Story 3

- [X] T014 [US3] Retype `UpdateItemRequest` in `taxomesh/contrib/api/schemas.py` per data-model.md:
  `name: Annotated[str, Field(max_length=MAX_ITEM_NAME_LENGTH)] = ""`;
  `external_id: Annotated[str | None, Field(max_length=MAX_EXTERNAL_ID_STR_LENGTH)] = None`
  (move `| None` **inside** `Annotated` — stays nullable AND length-bounded);
  `enabled: bool = True`; `slug: Annotated[str, Field(max_length=MAX_SLUG_LENGTH)] = ""`;
  `metadata: dict[str, Any] = Field(default_factory=dict)`. Drop `| None` from every
  non-nullable field. No custom validators.
- [X] T015 [US3] Retype `UpdateTagRequest` in `taxomesh/contrib/api/schemas.py`:
  `name: Annotated[str, Field(max_length=MAX_TAG_NAME_LENGTH)] = ""`.
- [X] T016 [US3] FR-020 docstrings — update the `UpdateItemRequest` and `UpdateTagRequest` class
  docstrings in `schemas.py`, and the `handlers.update_item` / `handlers.update_tag` docstrings in
  `taxomesh/contrib/api/handlers.py`, to state the single rule (omitted = no instruction; present
  = assign-or-reject; only `external_id` accepts `null`, as clear), in the existing house style.
- [X] T017 [US3] Run T008–T013 and confirm all pass; run the item/tag partial-update tests green.

**Checkpoint**: No `UpdateItemRequest`/`UpdateTagRequest` field can accept a value and silently
discard it (SC-003); the published JSON schema no longer advertises `null` on non-nullable fields.

---

## Phase 7: User Story 4 - Category external identifier and enabled state are reachable (Priority: P2)

**Goal**: `UpdateCategoryRequest` exposes `external_id` (with the omitted/set/clear semantics of
FR-007) and `enabled`, so consumers can reach service operations that already exist. Uniqueness
conflicts through the category handler surface as 409 (relies on FR-006 / Phase 5).

**Independent Test**: Through `handlers.update_category`, set a category's external identifier,
clear it, and confirm an unrelated update leaves it intact.

**Work Classification**: **New production code.** Extend `UpdateCategoryRequest` (FR-013, FR-014)
and retype its existing fields per data-model.md. Depends on Phase 5 for scenario 5.

### Tests for User Story 4 (write first; must FAIL before T022) ⚠️

- [X] T018 [P] [US4] TDD (US4 scenarios 1–4, FR-013/FR-014) — category external_id/enabled in
  `tests/contrib/test_api_handlers.py`: assert `handlers.update_category` can set an `external_id`
  string, clear it with `external_id=None`, leave it untouched when only `name` is sent, and set
  `enabled`. Must fail today — `UpdateCategoryRequest` has neither field.
- [X] T019 [P] [US4] TDD (SC-003/SC-004) — category null-rejection + presence/value table in
  `tests/contrib/test_api_schemas.py`: assert `UpdateCategoryRequest(name=None)`,
  `(description=None)`, `(slug=None)`, `(metadata=None)` raise `ValidationError`;
  `(external_id=None)` is valid; and enumerate the omitted/valid/null matrix per field. Must fail today.
- [X] T020 [P] [US4] TDD (US4 scenario 5, FR-015) — category external-ID conflict surfaces as 409:
  in `tests/contrib/test_api_handlers.py`, give two categories external IDs, PATCH one to collide,
  and assert the raised `TaxomeshExternalIdConflictError` maps (via `errors.to_tuple`) to 409.
  Depends on Phase 5 (T007).
- [X] T021 [US4] SC-007 class (b) rewrite — the two remaining enumerated tests in
  `tests/contrib/test_api_schemas.py`: `TestUpdateCategoryRequest::test_all_none_is_valid` and
  `TestUpdateCategoryRequest::test_partial_update`. Rewrite to assert **presence** via
  `model_fields_set` (not default values) and rename. These are the 3rd and 4th of the four
  enumerated SC-007 tests; `test_partial_update`'s `description is None` assertion (1) and
  `test_all_none_is_valid`'s four assertions (4) are the ones affected.

### Implementation for User Story 4

- [X] T022 [US4] Extend and retype `UpdateCategoryRequest` in `taxomesh/contrib/api/schemas.py`
  per data-model.md: retype `name`/`description`/`slug` to their true `str` type with `""` default,
  `metadata` to `dict[str, Any] = Field(default_factory=dict)`; **add**
  `external_id: Annotated[str | None, Field(max_length=MAX_EXTERNAL_ID_STR_LENGTH)] = None` (FR-013)
  and `enabled: bool = True` (FR-014). Drop `| None` from the non-nullable fields.
- [X] T023 [US4] FR-020 docstrings — update the `UpdateCategoryRequest` class docstring in
  `schemas.py` and the `handlers.update_category` docstring in `handlers.py` to state the single
  rule and the newly reachable `external_id`/`enabled` fields.
- [X] T024 [US4] Run T018–T021 and confirm all pass.

**Checkpoint**: All three external-identifier intents (preserve/replace/clear) are reachable
through both the item and category handlers (SC-005); category `enabled` is settable; category
conflicts surface as 409 (FR-015).

---

## Phase 8: Drift guard (FR-017)

**Purpose**: Guard the class of bug `mypy --strict` provably cannot see — a partial-update schema
field with no corresponding service parameter, which `**model_dump()` unpacking turns into a
runtime `TypeError`/500. Placed after US3+US4 so it runs against the final schema shapes.

- [X] T025 Create `tests/contrib/test_api_schema_service_parity.py` (NEW, FR-017): for each
  partial-update schema (`UpdateItemRequest`, `UpdateCategoryRequest`, `UpdateTagRequest`), assert
  every declared field name is an accepted keyword parameter of the corresponding service method
  (`update_item`, `update_category`, `update_tag`) — via `inspect.signature`. Fails if a schema
  declares a field the service cannot accept.

**Checkpoint**: Schema/service drift is caught by the suite, not by a 500 in production (SC-003 class guard).

---

## Phase 9: Polish, Release Record & Quality Gates

**Purpose**: FR-020 documentation completeness, FR-021 release record, and SC-008 gates.

- [X] T026 [P] FR-021 — add a CHANGELOG.md entry recording **both** breaking changes: (1) explicit
  `null` on a non-nullable partial-update field now fails validation instead of being ignored
  (FR-002); (2) an external-identifier conflict now returns 409 instead of 422 (FR-006). Note the
  two new category capabilities (external_id, enabled) and the lineage (supersedes 028 on three
  scoped points, per FR-019). Reference commits `e93ef5d` and `e049b68` as previously-merged,
  never-released behavior now shipping.
- [X] T027 [P] FR-021 — bump the package version in `pyproject.toml` from `0.1.0a46` to `0.1.0a47`
  following the established alpha convention.
- [X] T028 Run `quickstart.md` validation — walk its probes and confirm the observed behavior of
  omitting / setting / nulling each field matches the single rule.
- [X] T029 SC-008 quality gates — run and confirm all pass:
  `ruff check .` · `ruff format --check .` · `mypy --strict .` ·
  `pytest --cov=taxomesh --cov-fail-under=80` (run the full `tests/service/` directory so the
  Django parametrization finds its tables). Line length is 119.
- [X] T030 SC-007 verification — confirm that every pre-feature test passes unchanged **except**
  the four enumerated class-(b) tests rewritten in T012, T013, T021. No other pre-existing test
  may have changed; no class-(a) ("null silently ignored") test exists to change.

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup)**: none — start immediately.
- **Phase 2 (Foundational / FR-011)**: after T001. Tests only; blocks nothing but pins the invariant.
- **Phase 3 (US1)**: after T001. Independent — validation only.
- **Phase 4 (US2)**: after T001. Independent of US1.
- **Phase 5 (FR-006/FR-018)**: after T001. Independent of US1–US4; **US4 scenario 5 (T020) depends on T007**.
- **Phase 6 (US3)**: after T001. Independent of US2/US4. Tests T008–T013 before impl T014–T017.
- **Phase 7 (US4)**: after T001 and **Phase 5 (T007)** for the conflict-status test. Tests T018–T021 before impl T022–T024.
- **Phase 8 (FR-017 / T025)**: after Phase 6 and Phase 7 (needs final schema shapes).
- **Phase 9 (Polish/Gates)**: last — after all production and test changes land.

### User story independence

- **US1 (P1)**: fully independent — validation of merged code.
- **US2 (P1)**: independent — new parity test over merged code.
- **US3 (P2)**: independent production change to the item/tag schemas.
- **US4 (P2)**: independent production change to the category schema; consumes FR-006 for one test.

### TDD ordering (mandatory)

Within every story the test task(s) precede the implementation task and MUST be seen to fail
first: T005/T006 → T007; T008–T013 → T014–T017; T018–T021 → T022–T024.

---

## Parallel Opportunities

- **Phase 2 + Phase 3 + Phase 5 test-writing** can proceed together (different files, no shared deps):
  T002, T003, T005, T006.
- **US3 test-writing** T008, T009, T010, T011 are `[P]` (independent assertions; if split across
  files) — write before touching `schemas.py`.
- **US4 test-writing** T018, T019, T020 are `[P]`.
- **Release-record** T026 and T027 are `[P]` (CHANGELOG vs pyproject.toml).
- Serialize any tasks that edit the **same** file: T014/T015/T016/T022/T023 all touch
  `schemas.py` or `handlers.py` and must not run concurrently with each other.

---

## Implementation Strategy

### MVP (the two P1 data-integrity stories)

1. Phase 1 baseline → 2. Phase 2 invariant lock → 3. US1 validation (T003) → 4. US2 four-backend
parity (T004). At this checkpoint both silent-data-loss defects are proven fixed on every backend.

### Then close the live defect and the completeness gaps

5. Phase 5 (FR-006 conflict status + FR-018 guard) — the still-shipping 422/409 divergence.
6. US3 (retype item/tag schemas) → 7. US4 (category surface) → 8. FR-017 drift guard.

### Finish

9. CHANGELOG + version bump + quickstart + quality gates + SC-007 verification.

---

## Notes

- **No production code outside `taxomesh/contrib/api/{schemas,errors,handlers}.py`.** No domain,
  service, or repository changes (Work Classification; Constitution Check all PASS).
- **Mechanism is decided** (research.md Decision 1): inert default, not a widened type. For
  `external_id`, move `| None` inside `Annotated` so it stays nullable and length-bounded. No
  custom validators anywhere.
- **Do NOT alter** the historical spec directories `028`, `041`, or `043` (FR-019). Supersession
  is recorded only in this feature's own artifacts.
- **Parity tests belong under `tests/service/`** to inherit the parametrized `service` fixture;
  a parity test placed under `tests/contrib/` silently runs in-memory only.
- **SC-007 is enumerated, not estimated**: exactly four class-(b) tests change (T012, T013, T021);
  zero class-(a) tests exist.
- Commit spec artifacts (`specs/057-api-request-omission/tasks.md`) per CLAUDE.md — propose the
  message and file list, wait for approval, never commit without confirmation.
