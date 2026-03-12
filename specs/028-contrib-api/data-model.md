# Data Model: Framework-Agnostic HTTP API Handlers

**Feature**: 028-contrib-api
**Date**: 2026-03-10

## Overview

This feature introduces no new domain entities and no new storage. All entities returned by handlers are existing domain models. The new artefacts are input schemas (request validation models) and a functional error mapper.

---

## Request Schemas (`taxomesh/contrib/api/schemas.py`)

Each schema is a `pydantic.BaseModel` subclass. All `str` fields carry explicit `max_length` constraints imported from `taxomesh.domain.constants`.

### `CreateCategoryRequest`

| Field | Type | Required | Default | Constraint |
|-------|------|----------|---------|------------|
| `name` | `str` | Yes | — | `max_length=MAX_CATEGORY_NAME_LENGTH` (256) |
| `description` | `str` | No | `""` | `max_length=MAX_DESCRIPTION_LENGTH` (100 000) |
| `slug` | `str` | No | `""` | `max_length=MAX_SLUG_LENGTH` (256) |
| `metadata` | `dict[str, Any]` | No | `{}` | — |

### `UpdateCategoryRequest`

All fields optional; handler applies only non-`None` values.

| Field | Type | Default |
|-------|------|---------|
| `name` | `str \| None` | `None` |
| `description` | `str \| None` | `None` |
| `slug` | `str \| None` | `None` |
| `metadata` | `dict[str, Any] \| None` | `None` |

### `CreateItemRequest`

| Field | Type | Required | Default | Constraint |
|-------|------|----------|---------|------------|
| `name` | `str` | Yes | — | `max_length=MAX_ITEM_NAME_LENGTH` (256) |
| `external_id` | `str` | No | `""` | `max_length=MAX_EXTERNAL_ID_STR_LENGTH` (256) |
| `slug` | `str` | No | `""` | `max_length=MAX_SLUG_LENGTH` (256) |
| `metadata` | `dict[str, Any]` | No | `{}` | — |

### `UpdateItemRequest`

All fields optional.

| Field | Type | Default |
|-------|------|---------|
| `name` | `str \| None` | `None` |
| `external_id` | `str \| None` | `None` |
| `enabled` | `bool \| None` | `None` |
| `slug` | `str \| None` | `None` |
| `metadata` | `dict[str, Any] \| None` | `None` |

### `CreateTagRequest`

| Field | Type | Required | Default | Constraint |
|-------|------|----------|---------|------------|
| `name` | `str` | Yes | — | `max_length=MAX_TAG_NAME_LENGTH` (25) |
| `metadata` | `dict[str, Any]` | No | `{}` | — |

### `UpdateTagRequest`

| Field | Type | Default |
|-------|------|---------|
| `name` | `str \| None` | `None` |

### `AddParentRequest`

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `parent_id` | `UUID` | Yes | — |
| `sort_index` | `int` | No | `0` |

### `PlaceInCategoryRequest`

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `category_id` | `UUID` | Yes | — |
| `sort_index` | `int` | No | `0` |

---

## Return Types (`taxomesh/contrib/api/handlers.py`)

Handlers return existing domain model instances directly. No new types introduced.

| Handler group | Return type |
|---------------|-------------|
| `list_categories` | `list[Category]` |
| `get_category`, `create_category`, `update_category` | `Category` |
| `delete_category` | `None` |
| `list_items` | `list[Item]` |
| `get_item`, `create_item`, `update_item` | `Item` |
| `get_items_by_external_id` | `list[Item]` |
| `delete_item` | `None` |
| `list_tags` | `list[Tag]` |
| `create_tag`, `update_tag` | `Tag` |
| `delete_tag` | `None` |
| `add_category_parent` | `CategoryParentLink` |
| `remove_category_parent` | `None` |
| `place_item_in_category` | `ItemParentLink` |
| `remove_item_from_category` | `None` |
| `assign_tag`, `remove_tag_from_item` | `None` |
| `get_graph` | `TaxomeshGraph` |

---

## Error Mapping (`taxomesh/contrib/api/errors.py`)

`to_tuple(exc: TaxomeshError) -> tuple[int, dict[str, Any]]`

| Exception class | HTTP status | Checked before |
|-----------------|-------------|----------------|
| `TaxomeshDuplicateSlugError` | 409 | `TaxomeshValidationError` (parent) |
| `TaxomeshNotFoundError` (+ subclasses) | 404 | — |
| `TaxomeshValidationError` (+ subclasses) | 422 | — |
| `TaxomeshRepositoryError` | 500 | — |
| `TaxomeshError` (base fallback) | 500 | — |

Body always: `{"detail": str(exc)}`

Constants: `_HTTP_404`, `_HTTP_409`, `_HTTP_422`, `_HTTP_500` — `Final[int]` (Principle X).
