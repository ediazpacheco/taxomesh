# Service API Contract: External ID Clear Support (043)

**Branch**: `043-clear-external-id` | **Date**: 2026-03-21

This document defines the behavioural contract for the two modified `TaxomeshService` methods.

---

## `TaxomeshService.update_item`

### Signature (after change)

```python
def update_item(
    self,
    item_id: UUID,
    enabled: bool | None = None,
    slug: str | None = None,
    name: str | None = None,
    external_id: str | None | _UnsetType = _UNSET,
    metadata: dict[str, Any] | None = None,
) -> Item
```

### `external_id` parameter semantics

| Caller passes | Meaning | Effect on stored `external_id` |
|---------------|---------|-------------------------------|
| *(omitted / default)* | "leave unchanged" | Field is not touched |
| `None` | "clear this field" | Field is set to `None` |
| `"some-string"` | "set to this value" | Field is set to `"some-string"` |

### Behaviour invariants

1. When `external_id` is omitted, the item's `external_id` after the call equals its value before the call.
2. When `external_id=None` is passed, the item's `external_id` after the call is `None`.
3. When a non-None string is passed and no other item holds it, the item's `external_id` is set to that string.
4. When a non-None string is passed and another item already holds it, `TaxomeshExternalIdConflictError` is raised and the item is not modified.
5. After any successful call, a lookup by the old `external_id` value returns `None` if the field was cleared.
6. After any successful call, the in-process lookup cache is invalidated.

### Raises

| Exception | Condition |
|-----------|-----------|
| `TaxomeshItemNotFoundError` | No item with `item_id` exists |
| `TaxomeshDuplicateSlugError` | `slug` is non-empty and already used by another item |
| `TaxomeshExternalIdConflictError` | A non-None `external_id` string is already held by a different item |

---

## `TaxomeshService.update_category`

### Signature (after change)

```python
def update_category(
    self,
    category_id: UUID,
    name: str | None = None,
    description: str | None = None,
    slug: str | None = None,
    metadata: dict[str, Any] | None = None,
    external_id: str | None | _UnsetType = _UNSET,
) -> Category
```

### `external_id` parameter semantics

| Caller passes | Meaning | Effect on stored `external_id` |
|---------------|---------|-------------------------------|
| *(omitted / default)* | "leave unchanged" | Field is not touched |
| `None` | "clear this field" | Field is set to `None` |
| `"some-string"` | "set to this value" | Field is set to `"some-string"` |

### Behaviour invariants

Same as `update_item` but applied to categories. Additionally:

7. `category_id` MUST NOT be the root category ID — `TaxomeshRootCategoryError` is raised if it is (existing behaviour, unchanged).

### Raises

| Exception | Condition |
|-----------|-----------|
| `TaxomeshCategoryNotFoundError` | No category with `category_id` exists |
| `TaxomeshRootCategoryError` | Attempt to update the root category |
| `TaxomeshDuplicateSlugError` | `slug` is non-empty and already used by another category |
| `TaxomeshExternalIdConflictError` | A non-None `external_id` string is already held by a different category |

---

## Backwards Compatibility

This change is **backwards-compatible** for all existing callers that omit `external_id` (the default is the sentinel `_UNSET`, which preserves the old "no-op" behaviour). The sentinel default is transparently invisible to callers.

Callers that currently pass `external_id=None` explicitly were previously receiving a silent no-op. After this change, they will receive a field-clear. This is a **bug fix** — the previous behaviour was contrary to the documented intent (`external_id=None` should mean "no external ID").

---

## What this contract does NOT define

- `_UnsetType` and `_UNSET` are private implementation details. They are not part of the public contract and MUST NOT be imported or used by callers.
- The three-state semantics are conveyed entirely through the `external_id` parameter value. No separate flag or method is introduced.
