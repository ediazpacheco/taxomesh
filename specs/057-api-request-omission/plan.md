# Implementation Plan: API Request Omission and Explicit-Null Semantics

**Branch**: `057-api-request-omission` | **Date**: 2026-07-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/057-api-request-omission/spec.md`

## Summary

Align the public request contract in `taxomesh.contrib.api` with the external-identifier
semantics that 041 and 043 established at the domain and service layers, by enforcing one
rule at the HTTP boundary: **an omitted field carries no instruction; a present field means
"assign this value" and is rejected if the value is invalid for that field.**

The technical approach is a **subtraction, not an addition**. The partial-update schemas
currently express "you may omit this field" by widening the field's type to `X | None`,
which is what makes a supplied null indistinguishable from an unmentioned field. Removing
that widening — giving each field its true type and an inert default — makes Pydantic reject
null natively, makes the published schema truthful, and requires no custom validation code.
The creation schemas already do exactly this, which is why they never had the bug.

Two of the four user stories are already implemented and merged; the plan validates them
and closes their coverage gap. Two are new work. See **Work Classification** below — this
distinction is load-bearing and the spec forbids collapsing it.

## Technical Context

**Language/Version**: Python 3.11 (targets 3.11–3.13)
**Primary Dependencies**: Pydantic v2 (existing direct dep) — **no new dependencies**
**Storage**: N/A for the change itself. Verification spans all four backends: `InMemoryRepository` (test fixture), `JsonRepository`, `YAMLRepository`, `DjangoRepository`
**Testing**: pytest; `pytest-django` for the Django-backed parametrization; the backend-parametrized `service` fixture from `036-service-repo-parity` at `tests/service/conftest.py:343`
**Target Platform**: Library (framework-agnostic; consumers supply the HTTP framework)
**Project Type**: Library with optional Django contrib
**Performance Goals**: N/A — no hot path is touched; schema validation cost is unchanged
**Constraints**: `mypy --strict`, `ruff` line-length 119, coverage ≥ 80%. `contrib.api` MUST NOT import any HTTP framework (Principle IX)
**Scale/Scope**: 3 partial-update schemas, 1 error-mapping function, 3 handler docstrings. No domain, service, or repository changes

## Work Classification

The spec (Context → "Scope honesty") requires the plan to state honestly what already
exists. Presenting this feature as uniformly retrospective or uniformly greenfield would
both be false.

| Item | Status in `main` | Work required here |
|---|---|---|
| US1 — create without external ID | **Implemented** (`e93ef5d`) | **None.** Parity test already exists at `tests/service/test_api_create_item_parity.py` and covers all four backends. Validation only — confirm it passes. |
| US2 — omitted PATCH fields preserved | **Implemented** (`e049b68`) | **Tests only.** Behavior is correct but proven on `InMemoryRepository` alone. Add the missing four-backend parity coverage (FR-016). |
| US3 — present field assigned or rejected | **Not implemented** | **New production code.** Retype the three partial-update schemas (FR-003). |
| US4 — category external ID + enabled | **Not implemented** | **New production code.** Extend `UpdateCategoryRequest` (FR-013, FR-014). |
| FR-006 — conflict status | **Not implemented** | **New production code.** One branch in `errors.to_tuple`. |
| FR-017 — drift guard | **Not implemented** | **New test.** Closes a gap `mypy --strict` provably cannot see. |
| FR-018 — mapping completeness guard | **Not implemented** | **New test.** Prevents FR-006's defect recurring. |
| FR-011 — creation conformance | **Already conformant** | **Regression tests only.** The spec's Assumptions forbid budgeting implementation effort here. |

Neither merged commit bumped the version or the CHANGELOG, so **neither has shipped in a
release**. This feature ships all of it together, and FR-021 covers the record.

## SC-007 Enumeration — Tests That Must Change

SC-007 requires these to be enumerated, not estimated. Audited against the current tree:

**Class (a) — tests asserting an explicit null is silently ignored: _zero_.**
The only test constructing a partial-update request with an explicit null is
`tests/contrib/test_api_handlers.py:255` (`UpdateItemRequest(external_id=None)`), which
asserts the *correct* clear-semantics. `external_id` remains genuinely nullable, so this
test is unaffected. **No test encodes the FR-002 defect.**

**Class (b) — tests asserting the default value of an omitted field: _four tests, ten assertions._**

| Test | Assertions affected |
|---|---|
| `tests/contrib/test_api_schemas.py::TestUpdateCategoryRequest::test_all_none_is_valid` | `name`, `description`, `slug`, `metadata` are `None` (4) |
| `tests/contrib/test_api_schemas.py::TestUpdateCategoryRequest::test_partial_update` | `description is None` (1) |
| `tests/contrib/test_api_schemas.py::TestUpdateItemRequest::test_all_none_is_valid` | `name`, `enabled`, `slug`, `metadata` are `None` (4). `external_id is None` still holds. |
| `tests/contrib/test_api_schemas.py::TestUpdateTagRequest::test_all_none_is_valid` | `name is None` (1) |

These tests are themselves artifacts of the conflation this feature removes: each is named
`test_all_none_is_valid` and documented as "all fields may be None", yet each constructs a
request with all fields **omitted** and then asserts a *default value*. They test an
implementation detail that the new design makes inert. They must be rewritten to assert
presence (`model_fields_set`), which is the property that actually carries meaning, and
renamed accordingly.

**FR-006 impact: zero tests.** Confirmed by inspection — `tests/contrib/test_api_errors.py`
contains no reference to `TaxomeshExternalIdConflictError`. The 422 it currently returns is
asserted nowhere, which is precisely why the divergence survived. SC-007 required this be
confirmed rather than assumed; it is confirmed.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design — see below.*

| Principle | Verdict | Notes |
|---|---|---|
| I — Hexagonal, dependency direction | **PASS** | Changes confined to `taxomesh/contrib/api/` plus tests. No domain, application, or adapter changes. Dependency direction untouched. |
| II — `TaxomeshService` single facade | **PASS** | No service change. Handlers still delegate exclusively. |
| III — Repository as Protocol | **PASS** | No repository change. |
| IV — Pydantic + mypy strict | **PASS** | Schemas remain Pydantic v2. `Annotated[str, Field(max_length=...)]` preserved on every string field. `X \| None` union syntax retained where the field is genuinely nullable. |
| V — Exception hierarchy, no silent failures | **PASS, and advances it** | FR-002 removes a silent failure the constitution already forbids. FR-005 explicitly forbids adding a hierarchy member for request validation. No new exception type. |
| VI — DAG integrity | **N/A** | Not touched. |
| VII — Spec-driven development | **PASS, and repays a debt** | `e93ef5d` and `e049b68` merged with no spec, contrary to this principle. This feature is that spec. Recorded openly rather than backfilled silently. |
| VIII — Quality gates | **PASS** (SC-008) | Gates run locally before the commit is proposed. |
| IX — Framework-agnostic handlers | **PASS** | No HTTP framework import. `to_tuple`'s signature is unchanged — FR-006 adds a branch, and FR-005 explicitly forbids widening the accepted input. Handlers still take `TaxomeshService` first and return domain models. |
| X — Named constants | **PASS** | The inert defaults (`""`, `{}`, `False`) fall under Principle X's own carve-out for values that are "self-evident in context and carry no risk of divergent copies (e.g. `""`, `0`, `1`, `True`/`False`)". `errors.py` already defines `_HTTP_409` / `_HTTP_422` as `Final[int]`; FR-006 reuses `_HTTP_409`. |
| XI — Object-oriented by default | **PASS** | Schemas are classes. Handlers remain module-level stateless functions, as established by 028 and permitted by this principle. |

**Result: no violations. Complexity Tracking is intentionally empty.**

### Post-design re-check (after Phase 1)

Re-evaluated against the finished design in `research.md`, `data-model.md`, and
`contracts/api-request-contract.md`. Still no violations. Three points are worth recording
because they were live risks that the design resolved rather than assumed away:

- **Principle IX survived the mechanism choice.** The chosen mechanism (Decision 1) needs no
  custom validation code and no framework import — Pydantic's native type check does the
  rejection. The rejected alternative would have added validator code to every non-nullable
  field; that would still have passed the principle, but the chosen one keeps `contrib.api`
  thinner rather than thicker.
- **Principle X is satisfied by its own carve-out, not by an exemption.** The inert defaults
  are `""`, `True`, and `{}` — the exact literal kinds the principle names as permitted
  ("self-evident in context and carrying no risk of divergent copies"). `data-model.md`
  further ties each one to its stored field's default, so no value is arbitrary. No new
  constant is warranted; `_HTTP_409` already exists for FR-006.
- **Principle IV's string-length rule is preserved through the retyping.** Every `str` field
  keeps its `Annotated[str, Field(max_length=…)]`. For `external_id` the union moves
  *inside* the annotation (`Annotated[str | None, Field(max_length=…)]`) rather than being
  dropped — the field stays nullable and stays length-bounded. This is the one edit where a
  careless change would silently drop a constraint, and `data-model.md` calls it out.

Design phase surfaced two defects **in the spec itself**, both corrected there rather than
worked around here — recorded so `/speckit.analyze` sees why the spec moved after
`/speckit.clarify` closed:

1. **FR-019 was self-contradictory**, requiring 028's contract document to be "marked as
   superseded" while also requiring 028's directory to remain unaltered. Rewritten to record
   the supersession in this feature's own artifacts, following 041's precedent.
2. **SC-007 licensed the wrong class of test.** It permitted updating only tests that assert
   an explicit null is ignored — of which there are **zero**. The tests that actually must
   change assert *default values of omitted fields*, a class SC-007 did not cover. Rewritten
   to name both classes and to require enumeration rather than estimation. The enumeration is
   above.

## Project Structure

### Documentation (this feature)

```text
specs/057-api-request-omission/
├── plan.md              # This file
├── research.md          # Phase 0 output — mechanism decision + rejected alternatives
├── data-model.md        # Phase 1 output — per-field value domains
├── quickstart.md        # Phase 1 output — consumer-facing behavior of the single rule
├── contracts/
│   └── api-request-contract.md   # Phase 1 output — the superseding contract
├── checklists/
│   └── requirements.md  # From /speckit.specify
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
taxomesh/contrib/api/
├── schemas.py     # CHANGED — retype the 3 partial-update requests; extend UpdateCategoryRequest
├── handlers.py    # CHANGED — docstrings only; delegation logic is already correct
└── errors.py      # CHANGED — one branch: external-ID conflict → 409

tests/contrib/
├── test_api_schemas.py             # CHANGED — rewrite the 4 tests in SC-007 class (b)
├── test_api_handlers.py            # CHANGED — add null-rejection + category external_id/enabled
├── test_api_errors.py              # CHANGED — conflict status + FR-018 completeness guard
└── test_api_schema_service_parity.py   # NEW — FR-017 drift guard

tests/service/
├── test_api_create_item_parity.py  # UNCHANGED — already covers US1 on 4 backends
└── test_api_patch_parity.py        # NEW — FR-016; must live here to inherit the
                                    #       parametrized `service` fixture from 036

CHANGELOG.md       # CHANGED — FR-021, both breaking changes
pyproject.toml     # CHANGED — version bump (FR-021)
```

**Structure Decision**: The existing layout is used unchanged. The one placement decision
that matters is `tests/service/test_api_patch_parity.py`: backend parametrization is
supplied by the `service` fixture in `tests/service/conftest.py`, and `tests/contrib/`
overrides it with an in-memory-only fixture. A parity test physically located under
`tests/contrib/` would therefore silently run against one backend and report success —
which is exactly how US2's coverage gap arose. `e93ef5d` already set this precedent for the
create-side parity test; the PATCH-side test follows it.

**Note for implementation**: per the recorded environment quirk, Django-parametrized service
tests require `tests/service/test_parity_fixture.py` to run first, or the Django backend
reports "no such table". Run the full `tests/service/` directory rather than the new file
alone.

## Complexity Tracking

No constitutional violations. Nothing to justify.
