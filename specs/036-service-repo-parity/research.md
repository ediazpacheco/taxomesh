# Research: Service-Repository Behavioral Parity

## Decision 1: Fixture Replacement vs New Fixture

**Decision**: Replace the existing single-backend `service` fixture in
`tests/service/conftest.py` with a parametrized version. Do **not** create a separate
`parity_service` fixture or a new `tests/service/parity/` subdirectory.

**Rationale**: Every behavioral test that already uses `service` automatically gets
parity coverage with zero changes to the test files themselves. This satisfies FR-006
(new tests automatically cover all backends) and FR-007 (defined once, no per-file
duplication). A renamed fixture would require updating every test function signature.

**Alternatives considered**:
- New `parity_service` fixture: forces updating every test file's parameter list.
- New `tests/service/parity/` subdirectory: requires moving or copying test files,
  risks import path breakage, adds directory maintenance overhead.

---

## Decision 2: Fixture Parameter IDs

**Decision**: Parametrize with `ids=["in_memory", "json", "yaml"]` for P1.

**Rationale**: `ids` labels appear in pytest output (e.g., `test_create_category[json]`),
satisfying FR-002. Using lowercase strings avoids pytest auto-mangling of class names.

**Alternatives considered**:
- Using class objects directly as params: pytest auto-generates ugly IDs from class paths.
- Using enum values: unnecessary complexity for a 3-way parameter.

---

## Decision 3: Temporary Paths for File-Based Backends

**Decision**: The parametrized `service` fixture accepts `tmp_path` as a co-fixture.
`JsonRepository` and `YAMLRepository` are given a temp-directory path via `tmp_path`.

**Rationale**: `tmp_path` is a built-in pytest fixture that provides a fresh per-test
temporary directory. Both `JsonRepository(path)` and `YAMLRepository(path)` accept a
`Path` argument, making this wiring trivial. Each test gets a clean file store.

**Alternatives considered**:
- Using `tempfile.mkdtemp()` manually: bypasses pytest's cleanup and makes test
  teardown fragile.

---

## Decision 4: Scope of Impact — Which Tests Are Affected

**Decision**: The following `tests/service/` test files use the `service` fixture and
will automatically gain parametrized parity:

| File | Uses `service` fixture? | Gets parity? |
|------|------------------------|--------------|
| `test_service_categories.py` | yes | ✅ yes |
| `test_service_items.py` | yes | ✅ yes |
| `test_service_tags.py` | yes | ✅ yes |
| `test_service_graph.py` | yes | ✅ yes |
| `test_service_slug.py` | yes | ✅ yes |
| `test_service_item_relations.py` | yes | ✅ yes |
| `test_service_reorder_reparent.py` | yes (class method params) | ✅ yes |
| `test_service_search.py` | yes (via `svc` alias fixture) | ✅ yes |
| `test_service_config.py` | no (uses `tmp_path`, `monkeypatch`) | ✅ excluded per FR-009 |
| `test_service_cache.py` | no (uses `MagicMock` directly) | ✅ excluded per FR-009 |
| `test_custom_backend.py` | no (builds own `TaxomeshService`) | unaffected |
| `test_category_parent_upsert.py` | no (builds own instances) | unaffected |
| `test_item_parent_upsert.py` | no (builds own instances) | unaffected |
| `test_json_repository.py` | no (uses `tmp_json_path`) | unaffected |
| `test_yaml_repository.py` | no (uses `tmp_yaml_path`) | unaffected |

**Rationale**: The config/cache tests have no dependency on the `service` conftest
fixture, so parametrizing it has zero effect on them — no exclusion mechanism needed.

---

## Decision 5: Django Backend Inclusion (P2)

**Decision**: Add `DjangoRepository` as an optional fourth backend using
`request.getfixturevalue("db")` to dynamically invoke pytest-django's database setup.
Guard with `pytest.importorskip("django")` to skip cleanly when Django is absent.

**Rationale**: `request.getfixturevalue("db")` is the standard pytest-django pattern
for dynamically enabling database access inside a fixture. This avoids requiring
`@pytest.mark.django_db` on every test function while still setting up transactions
correctly.

**Alternatives considered**:
- Adding `@pytest.mark.django_db` to all test files: invasive, touches many files.
- A separate conftest in `tests/contrib/django/` that re-exports parity tests: requires
  duplicating or importing test functions, violating DRY.

---

## Decision 6: Fixture Scope

**Decision**: Keep the `service` fixture scope as `function` (the pytest default).

**Rationale**: File-based backends flush to disk on every write, so sharing a single
repository instance across tests would cause state leakage. Function scope ensures each
test starts with a clean store. `InMemoryRepository` already relies on this.

**Alternatives considered**:
- `scope="class"`: Would leak state across tests in the same class (e.g.,
  `TestReorderItemsInCategory`). Not safe.

---

## Decision 7: `InMemoryRepository` Location

**Decision**: Keep `InMemoryRepository` in `tests/service/conftest.py`. Do not move it.

**Rationale**: It is currently imported by `test_custom_backend.py` and
`test_category_parent_upsert.py` via `from tests.service.conftest import InMemoryRepository`.
Moving it would break those imports.
