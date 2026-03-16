# Implementation Plan: Service-Repository Behavioral Parity

**Branch**: `036-service-repo-parity` | **Date**: 2026-03-15 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/036-service-repo-parity/spec.md`

## Summary

Replace the single-backend `service` fixture in `tests/service/conftest.py` with a
parametrized fixture covering `InMemoryRepository`, `JsonRepository`, and
`YAMLRepository`. All eight behavioral test files that already use the `service`
fixture automatically gain parity coverage with zero changes to test functions.
`DjangoRepository` is added as an optional fourth backend (P2) via `pytest.importorskip`.

**Files changed**: `tests/service/conftest.py` (modified), `tests/service/test_parity_fixture.py` (added)

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: pytest (built-in fixtures: `tmp_path`, `request`), pytest-django (P2 — optional)
**Storage**: N/A — no production storage changes
**Testing**: pytest (parametrized fixtures)
**Target Platform**: developer workstation / CI
**Project Type**: library (test infrastructure only)
**Performance Goals**: N/A
**Constraints**: Must not change any production source file; must not break existing test isolation
**Scale/Scope**: ~250 existing behavioral test functions × 3 backends = ~750 parametrized instances

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Hexagonal Architecture | ✅ Pass | No production source changes; dependency direction unchanged |
| II. TaxomeshService is single facade | ✅ Pass | All tests still use `TaxomeshService`; no new public API |
| III. Repository as Protocol | ✅ Pass | Exactly validates this principle across backends |
| IV. Pydantic + mypy strict | ✅ Pass | Fixture uses proper type annotations (`pytest.FixtureRequest`, `Path`) |
| V. Custom exception hierarchy | ✅ Pass | No exception changes |
| VI. DAG integrity | ✅ Pass | No domain logic changes |
| VII. Spec-driven development | ✅ Pass | This plan fulfills the spec |
| VIII. Quality gates | ✅ Pass | All gates must pass after change |
| IX. Framework-agnostic handlers | ✅ Pass | Not applicable |
| X. Named constants | ✅ Pass | Parameter IDs are string literals in fixture definition only; acceptable |
| XI. OO by default | ✅ Pass | No new module-level mutable state introduced |

## Project Structure

### Documentation (this feature)

```text
specs/036-service-repo-parity/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── fixture-contract.md  # Phase 1 output
└── tasks.md             # Phase 2 output (not yet created)
```

### Source Code Changes (repository root)

```text
tests/
└── service/
    ├── conftest.py           # MODIFIED — service fixture becomes parametrized
    └── test_parity_fixture.py  # ADDED — pre-flight smoke tests for all backends
```

**Structure Decision**: Single-file change to `tests/service/conftest.py`. The
`service` fixture is the sole seam — replacing it propagates parity to all eight
behavioral test files without touching them.

## Implementation Phases

### Phase 1 — Parametrize `service` fixture (P1)

**Task T-001**: Update `tests/service/conftest.py`

Replace:
```python
@pytest.fixture
def service() -> TaxomeshService:
    """Return a TaxomeshService backed by a fresh InMemoryRepository."""
    return TaxomeshService(repository=InMemoryRepository())
```

With a parametrized fixture that:
1. Imports `JsonRepository` and `YAMLRepository` inside the fixture body (not at module level,
   to avoid pulling adapter imports into every test module)
2. Accepts `tmp_path: Path` as a co-fixture for file-based backends
3. Uses `request.param` to select the backend
4. Uses `ids=["in_memory", "json", "yaml"]` for readable pytest output

Required imports to add to `conftest.py`:
- `pytest.FixtureRequest` (typing only; already have `pytest`)
- `Path` from `pathlib` (already present)
- `JsonRepository` (lazy import inside fixture, or top-level — top-level is fine since conftest is not production code)
- `YAMLRepository`

The `InMemoryRepository` class definition in `conftest.py` is unchanged.
The `tmp_json_path` fixture is unchanged.

**Verification**: Run the quality gates:
```bash
ruff check .
ruff format --check .
mypy --strict .
pytest tests/service/ -v --tb=short
```

Expect three parametrized runs per behavioral test (`[in_memory]`, `[json]`, `[yaml]`).
All must pass.

---

### Phase 2 — Add Django backend (P2)

**Task T-002**: Extend `service` fixture with optional `django` parameter

1. Add `"django"` to the `params` list
2. Inside the fixture body for `"django"`:
   - Call `pytest.importorskip("django")` to auto-skip when Django is not installed
   - Call `request.getfixturevalue("db")` to activate pytest-django's transaction setup
   - Import and instantiate `DjangoRepository()`
3. Verify skip behavior in a non-Django environment and pass behavior in Django environment

**Verification**:
```bash
pytest tests/service/test_service_categories.py -v -k "django"
```
Expect either all `[django]` instances pass (Django environment) or all are skipped
(non-Django environment).

## Risk Analysis

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| File-backed backends have different sort/ordering behavior | Low | Medium | Tests that rely on list ordering must use `sort` or set-based assertions — already the case in most service tests |
| `TaxomeshService.__init__` creates root category on startup for all backends | Confirmed | None | This is consistent behavior; already accounted for in test assertions |
| Existing `test_service_search.py` uses `svc` alias for `service` — will it parametrize? | Confirmed yes | None | `svc` wraps `service`; parametrization propagates through the alias automatically |
| `test_service_config.py` accidentally picks up parity | Confirmed no | None | It does not use the `service` fixture; zero impact |
| `test_service_cache.py` accidentally picks up parity | Confirmed no | None | It uses `MagicMock`; zero impact |
| Django `DjangoRepository` needs `db` fixture for ORM | Confirmed | Medium (P2) | Handled by `request.getfixturevalue("db")` per Decision 5 in research.md |
