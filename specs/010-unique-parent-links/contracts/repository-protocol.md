# Contract: TaxomeshRepositoryBase — Link Upsert Semantics

**Feature**: 010-unique-parent-links
**Date**: 2026-02-27

## save_category_parent_link(link: CategoryParentLink) -> None

**Contract** (new — previously undocumented):

Upsert a category→parent relationship. If a link with the same
`(category_id, parent_category_id)` pair already exists, its `sort_index`
is updated in-place. No duplicate link is created.

**Composite key**: `(category_id, parent_category_id)`
**Mutable field**: `sort_index`

## save_item_parent_link(link: ItemParentLink) -> None

**Contract** (existing — formalized):

Upsert an item→category placement. If a link with the same
`(item_id, category_id)` pair already exists, its `sort_index`
is updated in-place. No duplicate link is created.

**Composite key**: `(item_id, category_id)`
**Mutable field**: `sort_index`

## Implementors

All repository implementations MUST enforce these contracts:

- `JsonRepository` (`taxomesh/adapters/repositories/json_repository.py`)
- `YAMLRepository` (`taxomesh/adapters/repositories/yaml_repository.py`)
- `InMemoryRepository` (`tests/service/conftest.py`) — test fixture
