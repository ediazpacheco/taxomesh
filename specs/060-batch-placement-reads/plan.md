# Implementation Plan: Batch resolution for the placement read paths

**Branch**: `060-batch-placement-reads` | **Date**: 2026-09-09 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/060-batch-placement-reads/spec.md`

## Summary

Three read paths on `TaxomeshService` resolve one stored row per result row.
Replace the per-row resolution with one batch resolve, and give the
category-link listing a parent filter so the children path stops reading every
link in the store. Two port additions, four adapters, three service methods,
and the query-count gates that keep it fixed.

The shape is already proven in this codebase: `list_related_items`
(`service.py:1155-1167`) reads its links, calls `get_items_by_ids` once with
`enabled=None`, then walks the ordered id list looking each id up in the
returned map and raising on a miss. All three rewrites adopt that shape
verbatim, which is also what makes FR-012 (raise on missing endpoint) the
behaviour-preserving choice — the error type and message text already match.

## Technical Context

**Language/Version**: Python 3.13 (`requires-python = ">=3.13"`, ruff `target-version = "py313"`)
**Primary Dependencies**: Pydantic v2 (domain models), Django ≥ 6.0 (optional adapter), pyyaml ≥ 6.0 — **no new dependencies**
**Storage**: `JsonRepository`, `YAMLRepository`, `DjangoRepository`, plus the `InMemoryRepository` test fixture — all four must implement both port additions
**Testing**: pytest, pytest-cov, pytest-django; `django.test.utils.CaptureQueriesContext` for query counts; the `service` fixture in `tests/service/conftest.py:351` already parametrises over all four backends
**Target Platform**: Library (importable package); no runtime service
**Project Type**: Single library, hexagonal layering
**Performance Goals**: Storage round-trips per call constant with respect to result size; the children path additionally reads only its own parent's links
**Constraints**: No public facade signature change (FR-017); no storage migration; no new runtime dependency; `mypy --strict` clean; ruff line length 119
**Scale/Scope**: 1 new port method, 1 port signature extension, 4 adapter implementations of each, 3 service method rewrites, plus test gates

## Constitution Check

*GATE: evaluated before Phase 0 and re-evaluated after Phase 1 design.*

| Principle | Verdict | Note |
| --- | --- | --- |
| I. Hexagonal — dependency direction | PASS | Change flows `ports` → `adapters` + `application`. No new outward import; the Django adapter keeps its lazy `django.db` imports inside the method body. |
| II. `TaxomeshService` single facade | PASS | No new public method, no signature change. FR-017. |
| III. Repository as Protocol (`Base` suffix) | PASS **with a compatibility note** | See "Protocol widening" below — this is the one consequence worth a decision at review time. |
| IV. Pydantic models + mypy strict | PASS | New return type `dict[UUID, Category]`; no `Any`; `X \| None` unions. |
| V. Exception hierarchy, no silent failures | PASS | `TaxomeshRepositoryError` on storage failure (FR-005, FR-006a); the not-found raise is preserved rather than downgraded to a skip (FR-012). |
| VI. DAG integrity in the domain layer | PASS | Cycle detection untouched. The new parent filter is a read filter; `check_no_cycle` keeps its unfiltered call at `service.py:775`. |
| VII. Spec-driven development | PASS | Spec and clarifications complete; zero open markers. |
| VIII. Quality gates | PASS | ruff, ruff format, mypy --strict, pytest ≥ 80% coverage all run before the commit is proposed. |
| IX. Framework-agnostic HTTP handlers | N/A | `contrib.api` untouched. |
| X. Named constants, no magic literals | PASS | No production literal introduced. Test corpus sizes are test data, not business values. |
| XI. Object-oriented by default | PASS | Methods added to existing classes; no new module-level function. |

### Protocol widening — the one thing to decide at review

`TaxomeshRepositoryBase` is a `typing.Protocol` (Principle III), so conformance
is structural: **any repository a consumer wrote themselves becomes
non-conforming the moment a method is added to the port.** Their code keeps
running — Protocols are not enforced at runtime — but `mypy --strict` in
*their* project starts failing where they pass their repository to
`TaxomeshService`.

This feature adds one method and widens another's signature, so it is a
breaking change for external implementers and a minor-version concern, even
though nothing in taxomesh's own public facade changes. The signature widening
is the milder half: it adds a keyword argument with a default, so an existing
implementation without it still satisfies calls that omit it, but not the call
`service.py` will now make. Recorded here so the CHANGELOG entry and version
decision are made deliberately rather than discovered by a consumer.

## Project Structure

### Documentation (this feature)

```text
specs/060-batch-placement-reads/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── repository-port.md
├── checklists/
│   └── requirements.md  # written by /speckit.specify
├── spec.md
└── tasks.md             # /speckit.tasks output — NOT created here
```

### Source code (repository root)

```text
taxomesh/
├── ports/
│   └── repository.py                     # + get_categories_by_ids (mirrors :332)
│                                         # ~ list_category_parent_links (:225) gains parent filter
├── application/
│   └── service.py                        # ~ list_categories        (:294-348)
│                                         # ~ list_items             (:503-529)
│                                         # ~ list_categories_by_item(:531-565)
└── adapters/repositories/
    ├── json_repository.py                # + batch get (~:624 shape), ~ link listing (:375)
    ├── yaml_repository.py                # + batch get (~:648 shape), ~ link listing (:399)
    └── django_repository.py              # + batch get (~:779 shape), ~ link listing (:597)

tests/
├── service/
│   ├── conftest.py                       # ~ InMemoryRepository (:139 link listing, + batch get)
│   ├── test_service_no_full_scan.py      # ~ RecordingRepository (:18) + new call-count gates
│   ├── test_parity_enabled_filter.py     # + enabled-filter parity for the three paths
│   ├── test_service_cache.py             # + cold-measurement / invalidation coverage
│   └── test_batch_placement_reads.py     # NEW — ordering, empty, dangling-link, port conformance
└── contrib/django/
    └── test_django_placement_queries.py  # NEW — query-count gates, oversized input, storage failure
```

**Structure Decision**: No new package or module. The feature is an additive
port change plus a rewrite in place, so every path above is an existing file
except the two new test modules. Test placement follows the existing split:
backend-agnostic behaviour under `tests/service/`, database query counting
under `tests/contrib/django/` where `pytest.mark.django_db` and
`CaptureQueriesContext` are already in use.

## Constitution re-check (post-design)

Re-evaluated after Phase 1. No verdict changed. Two design outputs are worth
recording against specific principles:

- **Principle X (named constants)** stays PASS after design. The per-path query
  constants in research.md R3 live in test assertions, not production code, and
  no splitting threshold is introduced — the user's decision that nothing splits
  removed the one place this feature would have needed a tunable value.
- **Principle V (no silent failures)** is strengthened, not merely preserved:
  FR-006a makes the oversized-input failure surface as `TaxomeshRepositoryError`
  rather than leaking a raw `django.db` exception through the port. The existing
  `except DatabaseError` wrapper already provides this; the contract now names
  it.

## Complexity Tracking

No constitution violations requiring justification. The Protocol-widening note
above is a compatibility consequence, not a principle violation — Principle III
defines the port as a Protocol and this change stays within that design.
