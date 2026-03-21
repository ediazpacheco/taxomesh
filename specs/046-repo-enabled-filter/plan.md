# Implementation Plan: Repository-Level Enabled Filtering

**Branch**: `046-repo-enabled-filter` | **Date**: 2026-03-21 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/046-repo-enabled-filter/spec.md`

## Summary

Add an `enabled: bool | None = True` parameter to `list_categories` and `list_items`
on the repository port and all adapters so that filtering by enabled state happens at
the storage level. Update the service layer, CLI, contrib API handlers/schemas, and
Django admin to apply `enabled=True` as the universal default, renaming the obsolete
`enabled_only` parameter to `enabled` throughout. Breaking backward compatibility is
intentional.

## Technical Context

**Language/Version**: Python 3.11 (targets 3.11–3.13)
**Primary Dependencies**: Pydantic v2, Typer ≥ 0.12, Rich ≥ 13.0, pyyaml ≥ 6.0, Django ≥ 4.2 (optional)
**Storage**: JsonRepository (JSON file), YAMLRepository (YAML file), DjangoRepository (Django ORM), InMemoryRepository (test fixture)
**Testing**: pytest, pytest-cov, mypy --strict, ruff
**Target Platform**: Linux/macOS server, Python library
**Project Type**: Library + CLI + optional Django admin contrib
**Performance Goals**: Django adapter must filter at ORM level (no full-table fetch for enabled filter)
**Constraints**: mypy --strict throughout; line length 119; ruff clean; ≥ 80% coverage
**Scale/Scope**: All four repository adapters; service layer; CLI; contrib API; Django admin

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Hexagonal Architecture | ✅ PASS | Port gains `enabled` param → adapters implement → service delegates. All dependencies point inward. No adapter import at module level added. |
| II. TaxomeshService as Facade | ✅ PASS | All listing methods on `TaxomeshService` gain `enabled` param; service remains the sole public entry point. |
| III. Repository as Protocol | ✅ PASS | Structural update to `TaxomeshRepositoryBase` protocol; all adapters implement the updated signature. mypy verifies compliance. |
| IV. Pydantic + mypy strict | ✅ PASS | `bool \| None` is properly typed; no `Any` introduced. Default values are self-evident booleans (Principle X exempts `True`/`False`). |
| V. Custom Exceptions | ✅ PASS | No new error cases; no silent failures introduced. |
| VI. DAG Integrity | ✅ PASS | Read-only change; no writes affected. |
| VII. Spec-Driven | ✅ PASS | Spec 046 exists. |
| VIII. Quality Gates | ✅ PASS | All gates enforced; tests updated. |
| IX. Framework-Agnostic HTTP | ✅ PASS | Handler functions updated; no HTTP framework imported in `contrib.api`. |
| X. Named Constants | ✅ PASS | `True`/`False`/`None` booleans are exempt from named-constant rule (self-evident in context). |
| XI. OO by Default | ✅ PASS | No new module-level functions; modifying existing class methods only. |

**Post-design re-check**: No constitution violations introduced. The `enabled=None`
sentinel (three-way boolean) is justified in research.md Decision 1 — the minimal
extension that supports corpus caching and admin use cases without new methods.

## Project Structure

### Documentation (this feature)

```text
specs/046-repo-enabled-filter/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── repository-port.md   # Phase 1 output
│   └── service-api.md       # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
taxomesh/
├── ports/
│   └── repository.py              # list_categories, list_items: add enabled param
├── application/
│   └── service.py                 # list_categories, list_items, list_categories_by_item,
│                                  # search_items, search_categories, get_graph,
│                                  # _get_item_corpus, _get_category_corpus
├── adapters/
│   ├── repositories/
│   │   ├── json_repository.py     # Implement enabled filter (Python if)
│   │   ├── yaml_repository.py     # Implement enabled filter (Python if)
│   │   └── django_repository.py  # Implement enabled filter (ORM .filter)
│   └── cli/
│       └── main.py                # --include-disabled on category list, item list, graph
└── contrib/
    ├── api/
    │   ├── handlers.py            # include_disabled param; enabled_only→enabled rename
    │   └── schemas.py             # enabled_only→enabled rename in search schemas;
    │                              # include_disabled in list query schemas
    └── django/
        └── admin.py               # Admin internal calls: use enabled=None where needed

tests/
└── service/
    └── conftest.py                # InMemoryRepository.list_categories, list_items
```

**Structure Decision**: Single library project; no structural reorganisation needed.
All changes are in-place modifications to existing files.

## Implementation Phases

### Phase 1 — Repository Port & Adapters (Foundation)

**Goal**: Establish the new contract. All other phases depend on this.

#### 1a. Port: `taxomesh/ports/repository.py`

Update signatures:

```python
def list_categories(self, *, enabled: bool | None = True) -> list[Category]: ...
def list_items(self, *, enabled: bool | None = True) -> list[Item]: ...
```

Update docstrings to document the three-way `enabled` semantics.

#### 1b. `JsonRepository`

`list_categories(*, enabled=True)`:
```python
cats = [_dict_to_category(v) for v in self._data["categories"].values()]
if enabled is not None:
    cats = [c for c in cats if c.enabled == enabled]
return sorted([c for c in cats if c.name != ROOT_CATEGORY_NAME],
              key=lambda c: (c.name, c.category_id))
```

`list_items(*, enabled=True)`: same pattern.

#### 1c. `YAMLRepository`

Same pattern as `JsonRepository` — Python-level filter after deserializing the YAML
dict values.

#### 1d. `DjangoRepository`

`list_categories(*, enabled=True)`:
```python
qs = self._CategoryModel.objects.using(self._using).exclude(name=ROOT_CATEGORY_NAME)
if enabled is not None:
    qs = qs.filter(enabled=enabled)
return [_row_to_category(row) for row in qs.order_by("name", "category_id")]
```

`list_items(*, enabled=True)`: same ORM pattern.

#### 1e. `InMemoryRepository` (test fixture: `tests/service/conftest.py`)

Same pattern as `JsonRepository`.

---

### Phase 2 — Service Layer

**Goal**: Propagate the `enabled` parameter through all affected service methods.

#### 2a. `list_categories`

Add `enabled: bool | None = True` parameter. Pass it to `repo.list_categories(enabled=enabled)` and `repo.get_category_by_external_id()` result filtering (external_id path already fetches one record — no change there; the `list_category_parent_links` path calls `list_categories` indirectly via individual `get_category()` calls — apply `enabled` filter after collecting results).

Wait — re-examining: `list_categories` with `parent_id` path calls `get_category()` per link. Apply the `enabled` filter after collecting: `[c for c in results if enabled is None or c.enabled == enabled]`.

#### 2b. `list_items`

Add `enabled: bool | None = True` parameter. Pass to `repo.list_items(enabled=enabled)`.
For the `category_id` path: collects items via `get_item()` per link → apply Python-level enabled filter after collection.

#### 2c. `list_categories_by_item`

Add `enabled: bool | None = True`. After collecting categories via `get_category()` per link, apply:
```python
if enabled is not None:
    cats = [c for c in cats if c.enabled == enabled]
```
Update docstring to remove "disabled categories are included; filtering by enabled state is the caller's responsibility."

#### 2d. `search_items`

Rename `enabled_only: bool = True` → `enabled: bool = True`. Replace all references to `enabled_only` with `enabled` in the method body. Corpus slice: `[sc for sc in corpus if sc.obj.enabled == enabled]`.

#### 2e. `search_categories`

Same rename as `search_items`.

#### 2f. `get_graph`

Add `enabled: bool | None = True`. Pass to both internal repo calls:
```python
all_cats = {c.category_id: c for c in self._repo.list_categories(enabled=enabled)
            if c.category_id != self._root_id}
...
items_map = {i.item_id: i for i in self._repo.list_items(enabled=enabled)}
```

#### 2g. `_get_item_corpus` (private)

Change `self._repo.list_items()` → `self._repo.list_items(enabled=None)`.

#### 2h. `_get_category_corpus` (private)

Change `self._repo.list_categories()` → `self._repo.list_categories(enabled=None)`.

---

### Phase 3 — CLI

**Goal**: Expose `--include-disabled` on the three list-type commands.

#### 3a. `category list`

Add `include_disabled: bool = typer.Option(False, "--include-disabled", ...)`.
Pass: `svc.list_categories(parent_id=parent_id, enabled=None if include_disabled else True)`.

#### 3b. `item list`

Same pattern: `svc.list_items(category_id=category_id, enabled=None if include_disabled else True)`.

#### 3c. `graph` command

Add `--include-disabled` flag.
Pass: `result.service.get_graph(enabled=None if include_disabled else True)`.

Also: `list_items()` called on line 547 for relations — add `enabled=None if include_disabled else True`.

---

### Phase 4 — Contrib API Handlers & Schemas

#### 4a. `handlers.py` — `list_categories`

```python
def list_categories(
    service: TaxomeshService,
    parent_id: UUID | None = None,
    include_disabled: bool = False,
) -> list[Category]:
    return service.list_categories(
        parent_id=parent_id,
        enabled=None if include_disabled else True,
    )
```

#### 4b. `handlers.py` — `list_items`

```python
def list_items(
    service: TaxomeshService,
    category_id: UUID | None = None,
    include_disabled: bool = False,
) -> list[Item]:
    return service.list_items(
        category_id=category_id,
        enabled=None if include_disabled else True,
    )
```

#### 4c. `handlers.py` — `get_graph`

```python
def get_graph(
    service: TaxomeshService,
    include_disabled: bool = False,
) -> TaxomeshGraph:
    return service.get_graph(enabled=None if include_disabled else True)
```

#### 4d. `handlers.py` — `search_items`, `search_categories`

Rename `params.enabled_only` → `params.enabled` in both handler bodies.

#### 4e. `schemas.py` — search schemas

Rename `enabled_only: bool = True` → `enabled: bool = True` in `SearchItemsRequest`
and `SearchCategoriesRequest`.

---

### Phase 5 — Django Admin

**Goal**: Update admin-internal repo/service calls that need all records.

Affected call sites in `taxomesh/contrib/django/admin.py`:

| Line (approx) | Current call | Updated call | Reason |
|----------------|-------------|-------------|--------|
| ~1014 | `repo.list_categories()` | `repo.list_categories(enabled=None)` | Needs root category regardless of state |
| ~1044 | `repo.list_categories()` | `repo.list_categories(enabled=None)` | Import/sync needs all categories |
| ~1124 | `svc.list_categories(parent_id=...)` | `svc.list_categories(parent_id=..., enabled=None)` | Admin drag-drop tree: show all |
| ~1125 | `svc.list_items(category_id=...)` | `svc.list_items(category_id=..., enabled=None)` | Admin drag-drop tree: show all |

**No change needed**: Admin Category and Item changeview list filters (`list_filter =
("enabled", ...)`) already exist — they work directly via Django ORM, unaffected by
this feature.

---

### Phase 6 — Tests

**Goal**: Update `InMemoryRepository` (Phase 1e), add tests for all new `enabled`
parameter behaviours, update existing tests that assumed all records were returned by
default.

#### 6a. Tests to add

For each of: `JsonRepository`, `YAMLRepository`, `DjangoRepository`, `InMemoryRepository`:
- `test_list_categories_default_returns_only_enabled`
- `test_list_categories_enabled_false_returns_only_disabled`
- `test_list_categories_enabled_none_returns_all`
- `test_list_items_default_returns_only_enabled`
- `test_list_items_enabled_false_returns_only_disabled`
- `test_list_items_enabled_none_returns_all`

For service:
- `test_list_categories_service_enabled_default`
- `test_list_items_service_enabled_default`
- `test_list_categories_by_item_enabled_default`
- `test_search_items_enabled_param_renamed` (no `enabled_only` kwarg)
- `test_get_graph_excludes_disabled_by_default`
- `test_get_graph_enabled_none_includes_all`

Parity (cross-backend) tests in `tests/service/`:
- `test_list_categories_enabled_filter_parity` — same result across all backends

#### 6b. Tests to update

Any test that calls `list_categories()`, `list_items()`, `list_categories_by_item()`,
`get_graph()`, `search_items(enabled_only=...)`, or `search_categories(enabled_only=...)`
without specifying `enabled=None` and expects disabled records in the result.

---

### Phase 7 — Documentation

**Goal**: Update all docstrings and remove `enabled_only` references.

- `ports/repository.py`: update `list_categories` and `list_items` docstrings.
- `application/service.py`: update all affected method docstrings; remove the
  "disabled categories are included; caller's responsibility" note from
  `list_categories_by_item`.
- `adapters/cli/main.py`: update `category list`, `item list`, `graph` command
  docstrings and help strings.
- `contrib/api/handlers.py`: update `list_categories`, `list_items`, `get_graph`,
  `search_items`, `search_categories` docstrings.
- `contrib/api/schemas.py`: update `SearchItemsRequest`, `SearchCategoriesRequest`
  field docstrings.
- `README.md`: update public API surface description where listing methods are
  documented.

---

## Complexity Tracking

No constitution violations requiring justification.

The `bool | None` three-way sentinel is the minimal design that avoids N+1 queries
for the "all records" use case. The alternative (two separate calls + merge) would
add complexity with no benefit.
