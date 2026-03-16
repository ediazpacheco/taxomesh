# Implementation Plan: Batch Item Relation Lookup

**Branch**: `038-batch-item-relations` | **Date**: 2026-03-16 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/038-batch-item-relations/spec.md`

## Summary

Add a batch API (`list_item_relation_links_for_sources` on the repository protocol; `list_related_items_for_sources` on `TaxomeshService`) that retrieves outgoing item relation links for multiple source items in a single storage operation, eliminating the N+1 query pattern. All three adapters (JSON, YAML, Django ORM) implement the new protocol method. The service resolves target `Item` objects in one `list_items()` call and returns a nested `dict[UUID, dict[str, list[Item]]]`. Existing per-item APIs are untouched.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Pydantic v2, pyyaml ≥ 6.0, Django ≥ 4.2 (optional adapter)
**Storage**: JSON file (`JsonRepository`), YAML file (`YAMLRepository`), Django ORM (`DjangoRepository`)
**Testing**: pytest, pytest-django (Django adapter tests)
**Target Platform**: Library (Python 3.11–3.13, all platforms)
**Project Type**: Library
**Performance Goals**: Reduce item-relation queries from N (one per source item) to 1 per batch call
**Constraints**: Backward-compatible; mypy `--strict`; no new runtime dependencies; line length 119
**Scale/Scope**: Hundreds to thousands of source item IDs per call; no pagination in this feature

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment | Notes |
|-----------|------------|-------|
| I — Hexagonal Architecture | ✅ Pass | New method declared in `ports/`, implemented in `adapters/`, called from `application/`. No inward violations. |
| II — TaxomeshService is single facade | ✅ Pass | New method added to `TaxomeshService`; no secondary facade introduced. |
| III — Repository as Protocol | ✅ Pass | `list_item_relation_links_for_sources` declared in `TaxomeshRepositoryBase` (Protocol); all three adapters implement it; mypy validates structurally. |
| IV — Pydantic + mypy strict | ✅ Pass | `Collection[UUID]`, `Collection[str] | None`, `dict[UUID, dict[str, list[Item]]]` — all fully typed. `typing.Collection` imported from stdlib. |
| V — Exception hierarchy | ✅ Pass | `TaxomeshItemNotFoundError` raised if a target item is missing; no silent failures. |
| VI — DAG integrity | ✅ Pass | Read-only feature; no writes; DAG rules not applicable. |
| VII — Spec-driven | ✅ Pass | This plan is produced from spec 038. |
| VIII — Quality gates | ✅ Pass | All changes must pass ruff, mypy --strict, pytest ≥ 80% coverage. |
| IX — Framework-agnostic handlers | ✅ Pass | No `contrib.api` changes in this feature. |
| X — Named constants | ✅ Pass | No new magic literals; ordering key string `"source_item_id"` etc. are ORM field names, not domain constants. |
| XI — OO by default | ✅ Pass | Methods added to existing classes; no new module-level functions. |

**Post-design re-check**: No violations found. All new code follows hexagonal layers.

## Project Structure

### Documentation (this feature)

```text
specs/038-batch-item-relations/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions on target resolution, caching, ordering
├── data-model.md        # Phase 1 — method signatures, return shape
├── contracts/
│   └── batch-relation-api.md  # Phase 1 — full API contract
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
taxomesh/
├── ports/
│   └── repository.py               # ADD: list_item_relation_links_for_sources to TaxomeshRepositoryBase
├── adapters/
│   └── repositories/
│       ├── json_repository.py      # ADD: list_item_relation_links_for_sources
│       ├── yaml_repository.py      # ADD: list_item_relation_links_for_sources
│       └── django_repository.py   # ADD: list_item_relation_links_for_sources
└── application/
    └── service.py                  # ADD: list_related_items_for_sources

tests/
├── service/
│   ├── test_json_repository_relations.py    # ADD: batch tests
│   ├── test_yaml_repository_relations.py   # ADD: batch tests
│   └── test_service_item_relations.py      # ADD: service batch tests
└── contrib/
    └── django/
        └── test_django_repository_relations.py  # ADD: batch tests
```

**Structure Decision**: Single-project library layout; no new packages or modules created. All additions are new methods in existing files.

## Implementation Design

### Layer 1: Repository Protocol (`ports/repository.py`)

Add the following method declaration to `TaxomeshRepositoryBase` immediately after `list_item_relation_links`:

```python
def list_item_relation_links_for_sources(
    self,
    source_item_ids: Collection[UUID],
    *,
    relation_types: Collection[str] | None = None,
) -> list[ItemRelationLink]:
```

Required imports to add to `ports/repository.py`: `Collection` from `typing` (or `collections.abc`).

---

### Layer 2: JSON Repository (`adapters/repositories/json_repository.py`)

Filter `self._item_relation_links` in-memory. Algorithm:

```
source_set = set of source_item_ids
if relation_types is truthy:
    type_set = set of relation_types (already normalized by caller)
filter: lnk.source_item_id in source_set AND (no type_set or lnk.relation_type in type_set)
sort: (lnk.source_item_id, lnk.relation_type, lnk.sort_index, lnk.target_item_id)
```

Required imports: `Collection` from `collections.abc` (already used in file or add).

---

### Layer 3: YAML Repository (`adapters/repositories/yaml_repository.py`)

Identical algorithm to JSON repository (both share the in-memory list pattern).

---

### Layer 4: Django Repository (`adapters/repositories/django_repository.py`)

Use a single ORM query:

```python
qs = self._ItemRelationLinkModel.objects.using(self._using).filter(
    source_item_id__in=source_item_ids
)
if relation_types:
    qs = qs.filter(relation_type__in=relation_types)
qs = qs.order_by("source_item_id", "relation_type", "sort_index", "target_item_id")
return [self._row_to_item_relation_link(row) for row in qs]
```

Wrap with `DatabaseError → TaxomeshRepositoryError` as per existing pattern.

---

### Layer 5: Service (`application/service.py`)

```
1. If source_item_ids is empty → return {}
2. Deduplicate: unique_ids = set(source_item_ids)
3. Normalize relation_types: [t.strip().lower() for t in relation_types] if truthy, else None
4. links = self._repo.list_item_relation_links_for_sources(unique_ids, relation_types=normalized_types)
5. If no links → return {}
6. Collect all unique target UUIDs from links
7. item_map = {item.item_id: item for item in self._repo.list_items()}
   (one call; raises TaxomeshItemNotFoundError if any target_item_id missing from item_map)
8. Build result dict:
   for each link (already ordered by source_item_id, relation_type, sort_index, target_item_id):
       result[link.source_item_id][link.relation_type].append(item_map[link.target_item_id])
9. Return result
```

`list_items()` is used (not the memoized service method, to avoid double-caching confusion) — call `self._repo.list_items()` directly. No `@memoize` decorator on the new method.

---

## Test Design

### JSON / YAML Repository Tests (shared contract)

File pattern: `test_{json,yaml}_repository_relations.py` — append to existing file.

| Test | Assertion |
|------|-----------|
| `test_list_for_sources_returns_links_for_multiple_sources` | Two sources each with 2 links → all 4 returned |
| `test_list_for_sources_filters_by_relation_types` | Only links matching the type filter are returned |
| `test_list_for_sources_empty_ids_returns_empty` | `[]` input → `[]` output |
| `test_list_for_sources_no_filter_returns_all_types` | `relation_types=None` → all types included |
| `test_list_for_sources_empty_filter_returns_all_types` | `relation_types=[]` → all types included |
| `test_list_for_sources_ordering` | sort_index and stable tie-break by target_id respected |
| `test_list_for_sources_unknown_source_returns_empty` | Source UUID with no links → not in result |

### Django Repository Tests

File: `tests/contrib/django/test_django_repository_relations.py` — append to existing file.

Same contract tests as JSON/YAML, plus:

| Test | Assertion |
|------|-----------|
| `test_list_for_sources_uses_single_query` | `django.test.utils.CaptureQueriesContext` confirms 1 DB query |

### Service Tests

File: `tests/service/test_service_item_relations.py` — append to existing file.

| Test | Assertion |
|------|-----------|
| `test_list_related_items_for_sources_grouped` | Returns `{source_id: {rel_type: [Item]}}` correctly |
| `test_list_related_items_for_sources_filters_types` | `relation_types=["x"]` → only "x" keys in result |
| `test_list_related_items_for_sources_empty_ids` | Empty input → `{}` with no repo call |
| `test_list_related_items_for_sources_omits_empty_sources` | Source with no links absent from result |
| `test_list_related_items_for_sources_deduplicates_input` | Duplicate source IDs → treated as one |
| `test_list_related_items_for_sources_preserves_order` | Item list per type respects sort_index |
| `test_list_related_items_for_sources_resolves_items_correctly` | Target items match expected Item objects |

### Regression Tests

All existing tests for `list_item_relation_links`, `list_item_relations`, and `list_related_items` must continue to pass without modification. No fixture changes required.

---

## Complexity Tracking

No constitution violations. No complexity justifications required.
