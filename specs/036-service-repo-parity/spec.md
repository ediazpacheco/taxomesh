# Feature Specification: Service-Repository Behavioral Parity

**Feature Branch**: `036-service-repo-parity`
**Created**: 2026-03-15
**Status**: Draft
**Input**: User description: "Validate that all TaxomeshService methods behave identically regardless of which repository backend is used (InMemoryRepository, JsonRepository, YAMLRepository, DjangoRepository). Currently, service-level behavioral tests only run against InMemoryRepository. The gap means repository-specific bugs in slug lookup, external ID, graph traversal, etc. are not caught by the behavioral test suite."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Service behavior verified across all file-based repositories (Priority: P1)

A developer who adds a new feature to `TaxomeshService` wants confidence that it
works correctly with every shipped repository backend — not just the in-memory fixture.
Today the service-level test suite only exercises `InMemoryRepository`, so a bug in
`JsonRepository.get_category_by_slug` or `YAMLRepository.list_items_by_external_id`
would go undetected until a user reports it.

With this feature, every behavioral test that today relies on the `service` fixture
(backed by `InMemoryRepository`) is also executed against `JsonRepository` and
`YAMLRepository` via a parametrized fixture. A single test function covers all three
backends.

**Why this priority**: File-based repositories are the default storage for end-users.
Behavioral gaps between them and the in-memory fixture represent real regression risk.

**Independent Test**: Can be fully tested by running the parametrized service test suite
and confirming all tests pass against `JsonRepository` and `YAMLRepository`, independent
of Django availability.

**Acceptance Scenarios**:

1. **Given** a parametrized `service` fixture covering `InMemoryRepository`, `JsonRepository`,
   and `YAMLRepository`, **When** any existing service behavioral test runs, **Then** the test
   executes three times — once per backend — and all three must pass.
2. **Given** a slug lookup test running against `JsonRepository`, **When** a category is created
   and then retrieved by slug, **Then** the result is identical to the in-memory result.
3. **Given** an external-ID lookup test running against `YAMLRepository`, **When** an item is
   created with an `external_id` and then looked up, **Then** the result matches the in-memory result.

---

### User Story 2 — Django repository included in parity coverage (Priority: P2)

A developer using the Django backend wants the same confidence. `DjangoRepository` has
its own test files today (`test_django_repository.py`, `test_django_repository_relations.py`,
etc.) but these do not systematically re-run the full service behavioral suite.

With this feature, the parametrized fixture optionally includes `DjangoRepository` when
the Django test environment is available. Tests skip the Django backend automatically
when the environment is absent.

**Why this priority**: Django is an optional dependency; skipping it gracefully is more
important than blocking P1. Django already has dedicated repository tests, so the
marginal risk is lower than for file-based backends.

**Independent Test**: Can be fully tested by running the service test suite in the
Django-enabled test environment and confirming all behavioral tests also execute with
the Django backend.

**Acceptance Scenarios**:

1. **Given** the Django test environment is configured, **When** the parametrized service test
   suite runs, **Then** each test also executes against `DjangoRepository`.
2. **Given** the Django test environment is NOT configured, **When** the parametrized service
   test suite runs, **Then** Django-backend test instances are skipped without error — all
   non-Django instances pass as normal.

---

### Edge Cases

- What happens when a repository backend raises `TaxomeshRepositoryError` during a
  behavioral test? The test must propagate the error and fail clearly — not silently pass.
- How does the system handle tests that are inherently backend-specific (e.g., persistence
  across restart, file format validation)? These tests are **excluded** from the parity
  suite and remain in their per-backend test files. Only behavior observable through the
  `TaxomeshService` API is parametrized.
- What if a new service method is added in the future without a parity test? The
  parametrized suite must be structured so that adding a new test once automatically
  covers all backends without any additional wiring.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The test suite MUST parametrize the `service` fixture to run all existing
  service behavioral tests against `InMemoryRepository`, `JsonRepository`, and `YAMLRepository`.
- **FR-002**: Each parametrized test instance MUST be independently identified in pytest
  output by its backend name (e.g., `[in_memory]`, `[json]`, `[yaml]`).
- **FR-003**: The `DjangoRepository` backend MUST be included as an optional fourth
  parameter, and any test instance using it MUST be skipped when the Django test
  environment is absent.
- **FR-004**: Tests that are backend-specific (file creation, format validation, persistence
  across restart, atomic write behavior) MUST remain in their existing per-backend test
  files and MUST NOT be moved into the parity suite.
- **FR-005**: The parity suite MUST cover all service operation groups: categories, items,
  tags, tag assignment, category parent links, item parent links, graph traversal, slug
  lookup, external-ID lookup, item relations, reorder/reparent, and fuzzy search. Cache
  tests (`test_service_cache.py`) are excluded — they test memoization logic via `MagicMock`
  and are independent of repository backend.
- **FR-006**: Adding a new behavioral test to the parity suite MUST automatically run it
  against all configured backends without requiring any per-backend changes.
- **FR-007**: The parity fixture infrastructure MUST be defined once and shared across all
  parity test modules — no per-file duplication of backend setup logic.
- **FR-008**: All parity tests MUST pass the existing quality gates (`ruff`, `mypy --strict`,
  `pytest --cov=taxomesh --cov-fail-under=80`).
- **FR-009**: Config/debug tests (`get_config_summary`, `get_debug_info`) MUST be excluded
  from the parity suite because these methods intentionally return backend-specific values.

### Key Entities

- **Parity fixture**: A pytest parametrized fixture that yields a `TaxomeshService` instance
  backed by each configured repository. Defined once, shared by all parity test modules.
- **Backend parameter**: An identifier (`in_memory`, `json`, `yaml`, `django`) used to label
  parametrized test instances in pytest output.
- **Parity test module**: A test file containing service behavioral tests that use the parity
  fixture instead of the single-backend `service` fixture. Each test in such a module runs
  once per backend.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every test currently in `tests/service/test_service_*.py` (excluding config and
  cache tests) is executed against at least `InMemoryRepository`, `JsonRepository`, and
  `YAMLRepository` — verified by pytest output showing three parametrized instances per test.
- **SC-002**: All tests introduced or modified by this feature pass with zero failures and zero
  errors across all three non-Django backends. Pre-existing failures unrelated to this feature
  (e.g., Django-dependent tests in other suites) are out of scope.
- **SC-003**: Any future behavioral test added to the parity suite automatically produces
  three (or four, if Django is available) parametrized runs — no additional wiring needed.
- **SC-004**: The Django backend runs are skipped gracefully (not failed) when Django is not
  configured in the test environment.
- **SC-005**: Overall test coverage remains at or above 80% after the parity suite is introduced.

## Assumptions

- `InMemoryRepository` (defined in `tests/service/conftest.py`) continues to serve as the
  canonical reference implementation — it is one of the three required backends.
- The Django repository tests use `pytest-django` with settings from `tests/django_settings.py`;
  the parity fixture will reuse the same mechanism for the optional Django backend.
- The fuzzy-search tests (`test_service_search.py`) are included in the parity suite because
  `TaxomeshService.search()` behavior is observable through the public API regardless of backend.
- The cache tests (`test_service_cache.py`) are **excluded** from the parity suite. They use
  `MagicMock` throughout and do not use the `service` fixture — they test memoization and
  cache-invalidation logic, which is independent of which repository backend is used.
  `MagicMock` is the correct tool for those tests.
- Config/debug tests (`test_service_config.py`) are excluded from the parity suite because
  `get_config_summary()` and `get_debug_info()` return backend-specific strings by design.

## Clarifications

### Session 2026-03-15

- Q: Should `test_service_cache.py` be rewritten to use real backends for parity, or left as-is with `MagicMock`? → A: Leave as-is. Cache tests validate memoization/invalidation logic, which is independent of repository backend. Excluded from parity suite.
