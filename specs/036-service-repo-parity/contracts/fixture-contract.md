# Fixture Contract: `service` (Parametrized)

**File**: `tests/service/conftest.py`
**Replaces**: existing single-backend `service` fixture

## Signature

```python
@pytest.fixture(params=["in_memory", "json", "yaml"], ids=["in_memory", "json", "yaml"])
def service(request: pytest.FixtureRequest, tmp_path: Path) -> TaxomeshService:
    ...
```

## Behaviour Per Parameter

| `request.param` | Repository instantiated | State |
|-----------------|------------------------|-------|
| `"in_memory"` | `InMemoryRepository()` | volatile (lost after test) |
| `"json"` | `JsonRepository(tmp_path / "test.json")` | temp file, auto-cleaned |
| `"yaml"` | `YAMLRepository(tmp_path / "test.yaml")` | temp file, auto-cleaned |

## Invariants

1. Each test receives a **fresh** `TaxomeshService` with an **empty** repository (no
   pre-existing categories, items, or tags — except the auto-created root category,
   which `TaxomeshService.__init__` always creates).
2. The fixture returns a fully initialized `TaxomeshService` instance ready for use.
3. File-backed repositories write to isolated paths under `tmp_path`; no test can
   observe another test's data.

## Pytest Output Format

Test IDs take the form `<test_name>[<param_id>]`:

```
tests/service/test_service_categories.py::test_create_category_returns_category_with_id[in_memory]
tests/service/test_service_categories.py::test_create_category_returns_category_with_id[json]
tests/service/test_service_categories.py::test_create_category_returns_category_with_id[yaml]
```

## P2 Extension: Django Backend

When P2 is implemented, a fourth parameter `"django"` is added:

```python
@pytest.fixture(
    params=["in_memory", "json", "yaml", "django"],
    ids=["in_memory", "json", "yaml", "django"],
)
def service(request: pytest.FixtureRequest, tmp_path: Path) -> TaxomeshService:
    if request.param == "django":
        django = pytest.importorskip("django")  # skip if Django not installed
        request.getfixturevalue("db")           # enable ORM access
        ...
```

Tests that run with `[django]` automatically get database access via the `db` fixture.
Tests that run without Django installed are collected but skipped with reason
`"django not installed"`.
