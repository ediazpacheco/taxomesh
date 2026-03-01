# Research: External-ID Lookup & Assignable Categories (013)

## Decision Log

### D-001: Lookup implementation strategy for YAML/JSON repositories

**Decision**: Python scan over in-memory dict values.

**Rationale**: Both `YAMLRepository` and `JsonRepository` hold all entities in memory
(`self._categories: dict[UUID, Category]`, `self._items: dict[UUID, Item]`) since
construction. Filtering with a list comprehension over `.values()` is O(n) but correct,
simple, and consistent with the existing scan pattern used by `list_category_parent_links()`
and `list_item_parent_links()`. Taxonomy sizes are assumed to be in the hundreds-to-thousands
range where O(n) is negligible.

**Alternatives considered**:
- Adding a secondary `dict[ExternalId, list[UUID]]` index: correct and O(1) lookup, but
  requires keeping two structures in sync on every write. Violates YAGNI — no evidence of
  performance problems at expected scale.
- Database-style indexing: not applicable to file-backed repos.

---

### D-002: Lookup implementation strategy for DjangoRepository

**Decision**: ORM `filter(external_id=ext_id_str, external_id_type=ext_id_type)` using
the serialized form produced by the existing `_serialize_external_id()` helper.

**Rationale**: The `external_id` and `external_id_type` columns already exist on both
`CategoryModel` and `ItemModel` (spec 012). The type discriminator (`"uuid"`, `"int"`,
`"str"`) stored alongside the serialised string is exactly the right predicate to achieve
exact-type matching at the database level, with no Python-side post-filtering.
The existing `_serialize_external_id()` helper is reused — single source of truth.

**Alternatives considered**:
- Python scan after `list_items()` / `list_categories()`: correct but loads all rows
  when only a subset is needed; wasteful for large datasets.
- Storing `external_id` as a native UUID/int column: would require schema changes and
  separate columns per type. Violates FR-009 (no migrations).

---

### D-003: `assignable_categories_qs()` protocol membership

**Decision**: Outside the protocol (`TaxomeshRepositoryBase`). Extra method on
`DjangoRepository` only.

**Rationale**: The return type is a Django `QuerySet[CategoryModel]` — a Django-specific
lazy collection with chainability semantics. There is no meaningful generic equivalent for
`YAMLRepository` or `JsonRepository` (which use in-memory lists, not lazy query objects).
Defining this in the protocol would force non-Django backends to return a fake queryset-like
object, adding complexity with no benefit.

**Alternatives considered**:
- Protocol method returning `list[Category]`: loses laziness; admin widget consumers
  need a real `QuerySet` for `.filter()`, `.order_by()`, pagination etc.
- Protocol method with different name returning `list[Category]` for non-Django: splits
  consumer code and adds an unnecessary abstraction layer.

---

### D-004: Source of `ROOT_CATEGORY_NAME` constant in DjangoRepository

**Decision**: Import `ROOT_CATEGORY_NAME` from `taxomesh.application.service` at module
level in `django_repository.py`.

**Rationale**: `ROOT_CATEGORY_NAME` is defined once in `service.py` as a
`Final[str]` constant (Principle X — no magic literals). Importing it at module level is
safe: `service.py` only imports `DjangoRepository` as a deferred import inside a function
body, so there is no circular import. The alternative (hardcoding `"__root__"`) would
duplicate a named constant across modules, violating Principle X.

**Alternatives considered**:
- Moving `ROOT_CATEGORY_NAME` to `taxomesh.domain.constants`: cleaner dependency direction
  (domain has no outward deps). Deferred to a future refactor as it would affect all
  existing usages across the codebase.
- Deferred import inside `assignable_categories_qs()` body: avoids any import-order
  concerns but adds unnecessary verbosity with no benefit.

---

### D-005: `assignable_categories_qs()` return type annotation

**Decision**: `-> Any` with an explicit `from typing import Any` at module level.

**Rationale**: Django is an optional dependency not installed in the dev environment.
`mypy --strict` runs against `django_repository.py` but cannot resolve `django.db.models.QuerySet`
or `taxomesh.contrib.django.models.CategoryModel` (the latter's module imports Django at
load time). Annotating as `Any` is explicit, valid under `--strict`
(`warn_return_any` warns only about *implicit* Any, not explicit), and avoids adding
`TYPE_CHECKING` guards for a file that is effectively runtime-only for its Django surface.

**Alternatives considered**:
- `TYPE_CHECKING` guard for `QuerySet` and `CategoryModel`: technically cleanest but
  requires `from __future__ import annotations` or careful string-annotation management;
  adds complexity that provides no benefit since mypy cannot resolve the Django types anyway.
- String literal annotation `"QuerySet[CategoryModel]"` + `# type: ignore[name-defined]`:
  equivalent in effect to `Any` but less readable.

---

### D-006: InMemoryRepository (test fixture) must be updated

**Decision**: Add `list_items_by_external_id` and `list_categories_by_external_id` to
`tests/service/conftest.py::InMemoryRepository`.

**Rationale**: `InMemoryRepository` is a Protocol-compliant test fixture. Adding two
protocol methods to `TaxomeshRepositoryBase` makes `InMemoryRepository` structurally
non-compliant until updated. mypy `--strict` detects this immediately. Implementation is
the same Python scan pattern used in YAML/JSON repos.

---

### D-007: Root exclusion in `get_categories_by_external_id` (post-clarification)

**Decision**: Root exclusion is applied at the service layer, not the repository layer.
`TaxomeshService.get_categories_by_external_id` filters out any result where
`category_id == self._root_id` before returning to the caller.

**Rationale**: The `__root__` category is stored with `external_id = ""` by default.
Without this filter, `get_categories_by_external_id("")` would return the root category,
leaking an internal implementation detail. The service layer is the correct location for this
filter because `self._root_id` is managed by the service and unknown to the backends. All
three backends are unchanged; the single-point-of-truth filter is in the service.

**Alternatives considered**:
- Filter at each repository backend: each backend would need to know about the root UUID;
  violates SRP — repositories manage storage, not business rules.
- Never allow root to be saved with `external_id = ""`: would require changing the `_ensure_root`
  call and adding a guard; over-engineered for this purpose.

---

## Technology Versions

| Technology | Version | Role |
|---|---|---|
| Python | 3.11 (targets 3.11–3.13) | Runtime |
| Pydantic v2 | transitive via FastAPI | Domain model validation |
| pytest + pytest-cov | ≥ 8.0 / ≥ 5.0 | Test runner + coverage |
| ruff | ≥ 0.4 | Lint + format |
| mypy | ≥ 1.10 | Strict type checking |
| Django | ≥ 4.2 (optional) | ORM backend |
| pytest-django | ≥ 4.8 (optional) | Django test integration |
