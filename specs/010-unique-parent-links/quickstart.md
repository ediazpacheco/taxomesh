# Quickstart: Unique Parent Link Constraint

**Feature**: 010-unique-parent-links
**Date**: 2026-02-27

## What Changes

`save_category_parent_link()` in all repository implementations gains upsert
semantics matching the existing `save_item_parent_link()` pattern.

## Implementation Pattern

The fix follows the same pattern already used by `save_item_parent_link()`
in all three repositories:

```python
def save_category_parent_link(self, link: CategoryParentLink) -> None:
    for i, existing in enumerate(self._category_parent_links):
        if (existing.category_id == link.category_id
                and existing.parent_category_id == link.parent_category_id):
            self._category_parent_links[i] = link
            self._flush()  # omit for InMemoryRepository
            return
    self._category_parent_links.append(link)
    self._flush()  # omit for InMemoryRepository
```

## Files to Modify

1. `taxomesh/ports/repository.py` — Update docstring for `save_category_parent_link()`
2. `taxomesh/adapters/repositories/json_repository.py` — Add upsert logic
3. `taxomesh/adapters/repositories/yaml_repository.py` — Add upsert logic
4. `tests/service/conftest.py` — Add upsert logic to InMemoryRepository
5. `taxomesh/application/service.py` — Update docstrings for idempotency

## Test Strategy

- Test `save_category_parent_link()` upsert directly on each repository
- Test `add_category_parent()` idempotency at service level
- Verify `save_item_parent_link()` upsert still works (regression guard)
- Verify `taxomesh graph` shows no duplicates after repeated link saves
