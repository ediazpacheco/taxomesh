# Data Model: 016-admin-service-layer

This feature does not introduce new domain entities or change storage schemas.
All entities (Category, Item, Tag, CategoryParentLink, ItemParentLink, ItemTagLink)
remain unchanged in structure.

The only data-layer changes are **new operations** added to the repository Protocol
and all adapter implementations to enable the new service methods.

## New Repository Port Methods

### `delete_category_parent_link(category_id, parent_category_id) -> bool`

Removes the directed edge from `category_id` → `parent_category_id` in the
category DAG.

| Attribute | Value |
|---|---|
| Signature | `(category_id: UUID, parent_category_id: UUID) -> bool` |
| Returns | `True` if the link was found and deleted; `False` if it did not exist |
| Side effects | Removes exactly one row from the category-parent-link store |
| Idempotent | Yes — calling twice on the same pair is safe (second call returns `False`) |

### `delete_item_parent_link(item_id, category_id) -> bool`

Removes the placement of `item_id` from `category_id`.

| Attribute | Value |
|---|---|
| Signature | `(item_id: UUID, category_id: UUID) -> bool` |
| Returns | `True` if the placement was found and deleted; `False` if it did not exist |
| Side effects | Removes exactly one row from the item-parent-link store |
| Idempotent | Yes |

## New Service Methods

### `remove_category_parent(category_id, parent_id) -> None`

Removes a parent relationship from a category. Validates both categories exist
before delegating deletion to the repository.

| Attribute | Value |
|---|---|
| Signature | `(category_id: UUID, parent_id: UUID) -> None` |
| Returns | `None` |
| Raises | `TaxomeshCategoryNotFoundError` if either category does not exist |
| Side effects | Calls `repo.delete_category_parent_link()`; clears memoize cache |
| No-op behaviour | If the link does not exist, no error is raised |

### `remove_item_from_category(item_id, category_id) -> None`

Removes an item's placement from a category. Validates both entities exist before
delegating deletion to the repository.

| Attribute | Value |
|---|---|
| Signature | `(item_id: UUID, category_id: UUID) -> None` |
| Returns | `None` |
| Raises | `TaxomeshItemNotFoundError` if item does not exist; `TaxomeshCategoryNotFoundError` if category does not exist |
| Side effects | Calls `repo.delete_item_parent_link()`; clears memoize cache |
| No-op behaviour | If the placement does not exist, no error is raised |

## Affected Files Summary

| File | Change Type |
|---|---|
| `taxomesh/ports/repository.py` | Add 2 new Protocol methods |
| `taxomesh/adapters/repositories/django_repository.py` | Implement 2 new methods |
| `taxomesh/adapters/repositories/json_repository.py` | Implement 2 new methods |
| `taxomesh/adapters/repositories/yaml_repository.py` | Implement 2 new methods |
| `taxomesh/application/service.py` | Add 2 new service methods |
| `taxomesh/contrib/django/admin.py` | Major refactor (see plan.md) |
| `tests/contrib/django/test_admin.py` | Update + extend existing tests |
| `tests/service/test_category_parent_upsert.py` | Add tests for `remove_category_parent` |
| `tests/service/test_item_parent_upsert.py` | Add tests for `remove_item_from_category` |
| New: `tests/contrib/django/test_admin_service_routing.py` | New test file for service-routing behaviour |
