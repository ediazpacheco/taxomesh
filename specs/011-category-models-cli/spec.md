# Feature Specification: Category Fields, Models Refactor & CLI Output Improvements

**Feature Branch**: `011-category-models-cli`
**Created**: 2026-02-27
**Status**: Draft
**Input**: User description: "Add `enabled` to Category class. Add `external_id` to Category class. Use one module for every class model, not in models.py but in models/ directory. In the CLI: show the external_id value both for items and categories. Remove current `enabled=<value>` in the string output and use colors (like red or green) and an icon to indicate if its enabled or not. For both items and categories."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Category Enabled & External ID Fields (Priority: P1)

A taxonomy administrator creates and manages categories that can be enabled
or disabled and optionally identified by a user-supplied external identifier.
`enabled` defaults to `True` and `external_id` defaults to an empty string
(optional — callers may omit it).

**Why this priority**: This is a data-model change that all downstream stories
depend on. The CLI cannot display `enabled` icons or `external_id` for
categories until these fields exist. Adding them also brings feature parity
with `Item`.

**Independent Test**: Create a category with `external_id="genre-rock"`,
verify it defaults to enabled. Set it to disabled, verify the change persists.
Load a pre-existing store without these fields and verify backward
compatibility.

**Acceptance Scenarios**:

1. **Given** no explicit `enabled` or `external_id` value, **When** a new
   category is created, **Then** it defaults to `enabled=True` and
   `external_id=""`.
2. **Given** an existing category, **When** its `enabled` field is set to
   `False`, **Then** the change persists across service restarts.
3. **Given** a store created before this feature (no `enabled` or
   `external_id` key on categories), **When** loaded, **Then** categories
   default to `enabled=True` and `external_id` defaults to an empty string.
4. **Given** a new category, **When** created with
   `external_id="genre-rock"`, **Then** the `external_id` value is persisted
   and retrievable.

---

### User Story 2 — Models Directory Refactor (Priority: P2)

A developer maintaining the codebase opens the `taxomesh/domain/` package
and finds each domain model in its own module rather than a single
`models.py` file. This makes it easier to locate, review, and modify
individual entities without scrolling through unrelated models.

**Why this priority**: Structural refactor that does not change behavior but
improves maintainability. It should happen early to minimize the number of
imports that later features must migrate.

**Independent Test**: All existing tests pass without modification to test
files. The import path `from taxomesh.domain.models import X` continues to
work for every public model class. Type checking passes.

**Acceptance Scenarios**:

1. **Given** the current single `models.py` file, **When** the refactor is
   complete, **Then** each public model class lives in its own module under
   a `models/` package directory.
2. **Given** existing code importing `from taxomesh.domain.models import Item`,
   **When** the refactor is complete, **Then** that import still resolves
   (backward-compatible re-exports from the package `__init__`).
3. **Given** the shared base class, **When** the refactor is complete,
   **Then** it lives in its own module and is importable from
   `taxomesh.domain.models`.

---

### User Story 3 — CLI Colored Enabled Icons (Priority: P3)

A user runs `taxomesh graph` and sees a clean, visual indicator next to each
item and category: a green icon for enabled, a red icon for disabled. The
previous `enabled=True` / `enabled=False` text label is replaced entirely by
this icon.

**Why this priority**: This is the primary visual improvement. It depends on
US1 (categories must have `enabled` to display it).

**Independent Test**: Run `taxomesh graph` with a mix of enabled and disabled
items and categories. Verify each line shows the correct colored icon and no
`enabled=<value>` text.

**Acceptance Scenarios**:

1. **Given** an enabled item in the graph, **When** rendered, **Then** a green
   icon appears on its line and no `enabled=True` text is present.
2. **Given** a disabled item in the graph, **When** rendered, **Then** a red
   icon appears on its line and no `enabled=False` text is present.
3. **Given** an enabled category in the graph, **When** rendered, **Then** a
   green icon appears on its line.
4. **Given** a disabled category in the graph, **When** rendered, **Then** a
   red icon appears on its line.

---

### User Story 4 — CLI External ID Display for Categories (Priority: P4)

A user runs `taxomesh graph` and sees the `external_id` displayed for both
items and categories. Items already show `external_id`; this story extends
the same treatment to categories.

**Why this priority**: Display-only change building on US1 (categories must
have `external_id` first). Lowest risk.

**Independent Test**: Run `taxomesh graph` with categories that have
`external_id` values. Verify `external_id` appears on each category line.

**Acceptance Scenarios**:

1. **Given** an item with `external_id="song-42"` in the graph, **When**
   rendered, **Then** `song-42` is visible on the item line.
2. **Given** a category with `external_id="genre-rock"` in the graph,
   **When** rendered, **Then** `genre-rock` is visible on the category line.
3. **Given** a category with an empty `external_id` (legacy data), **When**
   rendered, **Then** the category line does not show a blank or broken
   identifier — the `external_id` portion is simply omitted.

---

### User Story 5 — Memoize Utility & Service Cache (Priority: P5)

A developer adds a reusable `memoize` decorator with TTL support to a new
`taxomesh/utils/` package. All read-only methods on `TaxomeshService` are
decorated so that repeated calls with the same arguments return cached
results for a configurable duration (default 5 seconds).

**Why this priority**: Performance optimization that depends on the service
layer being stable. All prior stories (US1–US4) must be complete before
adding caching, since they modify the data model and CLI output that the
service returns.

**Independent Test**: Call a read-only service method twice with the same
arguments within the TTL window. Verify the repository is only called once.
Call again after TTL expires. Verify the repository is called again.

**Acceptance Scenarios**:

1. **Given** a memoize decorator with `ttl=5`, **When** the same function
   is called twice with identical arguments within 5 seconds, **Then** the
   second call returns the cached result without re-executing the function.
2. **Given** a memoize decorator with `ttl=5`, **When** the same function
   is called after 5 seconds have elapsed, **Then** the function is
   re-executed and a fresh result is returned.
3. **Given** a memoize decorator, **When** the function is called with
   different arguments, **Then** each argument combination is cached
   independently.
4. **Given** `TaxomeshService`, **When** `get_category()` is called twice
   with the same `category_id`, **Then** the repository is only queried
   once (within TTL).
5. **Given** `TaxomeshService`, **When** `list_categories()`,
   `get_item()`, `list_items()`, `list_tags()`, and `get_graph()` are each
   called twice, **Then** each caches its result within the TTL window.
6. **Given** a cached `get_category()` result, **When** any write operation
   (e.g. `create_category`, `update_item`, `delete_category`) is called,
   **Then** the entire read cache is cleared and the next read call hits
   the repository.

---

### Edge Cases

- **Backward compatibility (stores)**: Existing JSON/YAML stores without
  `enabled` or `external_id` on categories must load without error,
  defaulting to `enabled=True` and `external_id=""`.
- **Backward compatibility (imports)**: All existing imports of
  `from taxomesh.domain.models import X` must continue to work after the
  models directory refactor.
- **Terminal without color support**: The colored icon should degrade
  gracefully (Rich handles this automatically).
- **Category enabled + graph rendering**: A disabled category's children
  and items are still shown in the graph (disabling is a flag, not a filter).
- **Empty external_id on category**: Legacy categories without an
  `external_id` should display gracefully — omit the identifier rather than
  showing an empty string.
- **Memoize with unhashable arguments**: If a decorated method receives
  arguments that are not hashable (e.g. mutable objects), the decorator
  should skip caching and call the function directly.
- **Cache isolation**: Each decorated method has its own independent cache.
  Caching `get_category()` does not affect `list_categories()`.
- **Cache invalidation on writes**: Any write operation on `TaxomeshService`
  (create, update, delete for categories, items, tags, and link operations)
  clears the entire read cache across all cached methods.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The `Category` model MUST have an `enabled` field of type
  `bool`, defaulting to `True`.
- **FR-002**: The `Category` model MUST have an `external_id` field of the
  same type as `Item.external_id`, but optional with a default of empty
  string. Callers may omit it when creating a category.
- **FR-003**: All repository implementations MUST persist and load both
  `enabled` and `external_id` for categories.
- **FR-004**: Existing stores without `enabled` or `external_id` on
  categories MUST load successfully with defaults (`True` and `""`
  respectively).
- **FR-005**: The `models.py` module MUST be refactored into a `models/`
  package with one module per model class.
- **FR-006**: The `models/` package MUST re-export all public names so that
  existing imports continue to work.
- **FR-007**: The `taxomesh graph` command MUST display a colored icon (green
  for enabled, red for disabled) for each item.
- **FR-008**: The `taxomesh graph` command MUST display a colored icon (green
  for enabled, red for disabled) for each category.
- **FR-009**: The `taxomesh graph` command MUST NOT display the text
  `enabled=True` or `enabled=False` — the icon replaces the text label.
- **FR-010**: The `taxomesh graph` command MUST display `external_id` for
  both items and categories.
- **FR-011**: When a category's `external_id` is empty, the graph output
  MUST omit it rather than displaying a blank value.
- **FR-012**: A `memoize` decorator with TTL support MUST be provided in
  a `taxomesh/utils/` package.
- **FR-013**: The `memoize` decorator MUST accept a `ttl` parameter
  (seconds) controlling how long cached results are retained.
- **FR-014**: All read-only methods on `TaxomeshService` (`get_category`,
  `list_categories`, `get_item`, `list_items`, `list_tags`, `get_graph`)
  MUST be decorated with `memoize` using a default TTL of 5 seconds.
- **FR-015**: The default TTL value (5 seconds) MUST be defined as a
  named constant in `taxomesh/application/service.py` (module-level,
  publicly accessible as `service.DEFAULT_CACHE_TTL`).
- **FR-016**: The `memoize` decorator MUST use a closure-based
  (function-based) implementation — the idiomatic Python pattern for
  decorators. This is a justified exception to Constitution Principle XI
  (Object-Oriented by Default) since the decorator is a standard Python
  idiom and class-based decorators introduce unnecessary complexity.
- **FR-017**: All write operations on `TaxomeshService` (create, update,
  delete for categories, items, tags, and link operations) MUST clear the
  entire memoize cache for all read methods upon completion.

### Key Entities

- **Category**: Gains `enabled: bool = True` and `external_id` (same type
  as `Item.external_id`, but optional with default `""`). All other fields
  unchanged.
- **Item**: Unchanged. Already has `enabled` and `external_id`.
- **ModelBase, CategoryParentLink, ItemParentLink, ItemTagLink, Tag**: Each
  extracted to its own module within `models/`.
- **memoize**: A decorator function in `taxomesh/utils/memoize.py` that
  caches return values by arguments with a configurable TTL.

## Assumptions

- The icon for enabled/disabled uses Unicode characters (e.g. checkmark /
  cross) styled with Rich markup. Exact icon choice is an implementation
  detail.
- The `models/` refactor preserves the shared base class as importable from
  `taxomesh.domain.models`.
- Disabling a category does not filter it from graph output — it is still
  displayed, just visually marked.
- The service API for creating/updating categories will accept both new
  parameters, following the same patterns as items.
- `Category.external_id` is optional with default `""` for both new
  categories and legacy stores. Unlike `Item.external_id` (which is required),
  categories do not require an external identifier.
- The `memoize` decorator uses a closure-based implementation (justified
  exception to Principle XI — see FR-016 and plan.md Constitution Check).
  It lives in `taxomesh/utils/memoize.py`, establishing a new `utils/`
  package for cross-cutting utilities.

## Clarifications

### Session 2026-02-27

- Q: Is `external_id` required when creating a new Category? → A: Optional with default `""` for both new and legacy categories. Callers may omit it.
- Q: Should write operations invalidate the memoize cache? → A: Yes — write operations clear the entire cache for all read methods.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `Category` instances carry `enabled` (defaulting to `True`)
  and `external_id` fields.
- **SC-002**: All existing imports of `from taxomesh.domain.models import X`
  resolve after the refactor — zero import errors across the codebase.
- **SC-003**: The `taxomesh graph` output shows a colored icon (not text)
  for the enabled/disabled state of every item and category.
- **SC-004**: The `taxomesh graph` output shows `external_id` for both items
  and categories.
- **SC-005**: Existing stores without the new category fields load without
  error and apply correct defaults.
- **SC-006**: All existing tests pass after the refactor — no regressions.
- **SC-007**: All read-only service methods are cached — calling the same
  method twice with identical arguments within 5 seconds results in only
  one repository call.
- **SC-008**: Cache entries expire after the TTL — calling a method after
  the TTL elapses results in a fresh repository call.
- **SC-009**: Any write operation on the service clears the entire read
  cache — the next read call after a write hits the repository.
