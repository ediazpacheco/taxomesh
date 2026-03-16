# Data Model: Service-Repository Behavioral Parity

This feature is pure test infrastructure. It introduces no new domain models,
no new database migrations, and no changes to any production source file. The
relevant "model" is the fixture contract described below.

## Fixture Contract

### `service` (parametrized)

| Attribute | Value |
|-----------|-------|
| Location | `tests/service/conftest.py` |
| Type | `pytest.fixture` |
| Scope | `function` (fresh instance per test) |
| Parameters | `in_memory`, `json`, `yaml` (P1); `django` (P2, optional) |
| Returns | `TaxomeshService` backed by the parameter's repository |
| Co-fixtures | `tmp_path` (for file-based backends) |

#### Parameter: `in_memory`
- Repository: `InMemoryRepository()` (no arguments)
- State persistence: none (in-memory only)
- Setup cost: negligible

#### Parameter: `json`
- Repository: `JsonRepository(tmp_path / "test.json")`
- State persistence: JSON file in pytest temp directory, cleaned up after test
- Setup cost: one file write

#### Parameter: `yaml`
- Repository: `YAMLRepository(tmp_path / "test.yaml")`
- State persistence: YAML file in pytest temp directory, cleaned up after test
- Setup cost: one file write

#### Parameter: `django` (P2 — optional)
- Repository: `DjangoRepository()`
- State persistence: Django ORM, SQLite in-memory (`:memory:`)
- Setup cost: Django ORM transaction setup via pytest-django `db` fixture
- Skip condition: if `import django` fails or pytest-django is not installed

## No Changes To

- `taxomesh/` — all production source files are untouched
- `taxomesh/ports/repository.py` — protocol unchanged
- Any domain model (`Category`, `Item`, `Tag`, `*Link`)
- Any adapter (`JsonRepository`, `YAMLRepository`, `DjangoRepository`)
- `tests/service/test_service_*.py` — behavioral test files are untouched
- `tests/service/test_json_repository*.py` — backend-specific tests are untouched
- `tests/service/test_yaml_repository*.py` — backend-specific tests are untouched
