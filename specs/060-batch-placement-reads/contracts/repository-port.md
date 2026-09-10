# Contract: `TaxomeshRepositoryBase` additions

**Feature**: `060-batch-placement-reads` | **Date**: 2026-09-09

Two changes to `taxomesh/ports/repository.py`. Both are read-only. Every
implementer — `JsonRepository`, `YAMLRepository`, `DjangoRepository`, and the
`InMemoryRepository` test fixture — must satisfy both identically (FR-008).

---

## 1. `get_categories_by_ids` — new

```python
def get_categories_by_ids(
    self,
    category_ids: Collection[UUID],
    *,
    enabled: bool | None = None,
) -> dict[UUID, Category]:
    ...
```

Mirrors `get_items_by_ids` (`ports/repository.py:332-359`) clause for clause.

| Rule | Behaviour | Requirement |
| --- | --- | --- |
| Input normalisation | Pre-normalised by the caller; the adapter MUST NOT deduplicate or validate further | FR-002 |
| Empty input | Returns `{}` **without reaching storage** | FR-004 |
| Missing ids | Silently absent from the mapping; never raises | FR-003 |
| Duplicate ids | Collapse naturally into the mapping; not an error | FR-002 |
| `enabled=None` (default) | All matching rows regardless of state | FR-007 |
| `enabled=True` / `False` | Only rows in that state | FR-007 |
| Storage failure | Raises `TaxomeshRepositoryError` | FR-005 |
| Oversized input | Passed to the store as **one** request; **no internal splitting**. The store's own per-query limit is the library's limit, and exceeding it surfaces as `TaxomeshRepositoryError`, never a raw backend exception | FR-006, FR-006a, FR-006b |

**Adapter notes**

- JSON / YAML: dict lookup per id over the loaded document — the shape at
  `json_repository.py:642-647`.
- Django: one `category_id__in=…` queryset, matching
  `django_repository.py:807-811`. The existing `except DatabaseError → TaxomeshRepositoryError`
  wrapper is what satisfies FR-006a, including the "too many SQL variables"
  case.
- In-memory fixture: mirror the JSON shape.

---

## 2. `list_category_parent_links` — signature widened

```python
def list_category_parent_links(
    self,
    *,
    parent_category_ids: Collection[UUID] | None = None,
) -> list[CategoryParentLink]:
    ...
```

Previously took no arguments (`ports/repository.py:225`).

| Rule | Behaviour | Requirement |
| --- | --- | --- |
| `None` (default) | No filter — every link, exactly as today | FR-009 |
| Non-empty collection | Only links whose `parent_category_id` is a member | FR-009 |
| **Empty collection** | Returns `[]` — "match nothing", **not** "no filter" | FR-010 |
| Ordering | `(parent_category_id ASC, sort_index ASC, category_id ASC)` holds under every filter combination | FR-010 |
| Storage failure | Raises `TaxomeshRepositoryError` | Principle V |

The empty-collection rule is not a free choice: it is the rule already
documented for `category_ids` on `list_item_parent_links`
(`ports/repository.py:285-288`), and divergence between two sibling filters
would be a trap.

**Backward compatibility**: keyword-only with a `None` default, so all eleven
existing call sites compile and behave identically — four in
`taxomesh/contrib/django/admin.py`, seven in `taxomesh/application/service.py`.
Only `service.py:343` and `:331-336` adopt the filter.

**Not added**: a `category_id` filter for the reverse child→parents direction.
Legitimate in a multi-parent DAG, but nothing in scope issues that query
(FR-009a).

---

## 3. Public facade — unchanged

```python
TaxomeshService.list_items(*, category_id=None, enabled=True)          -> list[Item]
TaxomeshService.list_categories(*, parent_id=None, external_id=None, enabled=True) -> list[Category]
TaxomeshService.list_categories_by_item(item_id, *, enabled=True)     -> list[Category]
```

Signatures, return types, ordering, and raised exception types are all
unchanged (FR-017). The only externally visible difference is how many times
storage is consulted.

---

## Downstream impact

`TaxomeshRepositoryBase` is a `typing.Protocol` (Principle III). Adding a method
and widening a signature means a consumer's own repository implementation stops
conforming under `mypy --strict` in *their* project, though runtime is
unaffected. This is a minor-version concern and a required CHANGELOG entry —
see plan.md, "Protocol widening".
