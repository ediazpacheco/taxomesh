# Research: Admin & Service Improvements — Feature 026

## Decision 1: Category Linked-Object Config Key

**Decision**: Introduce a new Django settings key `TAXOMESH_CATEGORY_LINKED_MODEL` (separate from the existing `TAXOMESH_LINKED_MODEL` used for Item). Store both as `Final[str]` constants.

**Rationale**: `linked_object_url` is currently shared between CategoryModelAdmin and ItemModelAdmin via a module-level `_resolve_linked_url(external_id)` helper that reads `settings.TAXOMESH_LINKED_MODEL`. Category and Item can legitimately link to different external domain models; a single shared setting cannot support both independently. Adding a dedicated setting is the smallest change that makes the link resolution per-entity.

**Alternatives considered**:
- Single setting with type dispatch (check if model links to Item or Category by runtime inspection): overly complex, fragile.
- Dict-style setting `TAXOMESH_LINKED_MODELS = {"item": ..., "category": ...}`: breaks all existing integrations, larger migration surface.
- Reuse `TAXOMESH_LINKED_MODEL` for Category when no category-specific setting is found (fallback chain): surprising behaviour; integrators would get unexpected Category→Item links.

---

## Decision 2: Partial UUID Search Strategy

**Decision**: Append the string representation of the primary key UUID field to `search_fields` on both `CategoryModelAdmin` and `ItemModelAdmin`. Use Django admin's built-in `__icontains` search behaviour.

**Rationale**: Django admin iterates `search_fields` and applies `icontains` (substring, case-insensitive) lookup for each field. UUID fields stored as `UUIDField` in Django produce their string representation for string comparisons. No custom queryset override is required; this is a one-line change per model admin.

**Alternatives considered**:
- Custom `get_search_results` override: more flexible but unnecessary for substring UUID matching.
- SearchVectorField (full-text index): overkill; UUID search requires simple substring, not ranked relevance.

---

## Decision 3: Better Admin Filters

**Decision**: Add two list filters:
1. `HasLinkedObjectListFilter(SimpleListFilter)` — on `CategoryModelAdmin`; shows "Has linked object" / "No linked object" choices based on `external_id` non-empty and the `TAXOMESH_CATEGORY_LINKED_MODEL` setting resolving successfully.
2. `TaxomeshCategoryListFilter(SimpleListFilter)` — available for external model admins using the `ItemCategoryAssignmentMixin`; filters the external model list by assigned taxomesh category slug/name.

**Rationale**: Both filters are pure Django admin `SimpleListFilter` subclasses — no ORM extension or custom middleware required. `HasLinkedObjectListFilter` is registered directly on `CategoryModelAdmin.list_filter`. `TaxomeshCategoryListFilter` is added to the mixin's default `list_filter` class attribute so integrators get it for free.

**Alternatives considered**:
- Queryset-level annotation for "has linked object": requires querying the external model's database within taxomesh admin, violating the boundary between taxomesh and the consumer's domain.
- `list_filter = ("external_id",)` (field-based filter): shows raw values, not user-friendly.

---

## Decision 4: show-relations Default Change

**Decision**: Change `show_relations` default from `False` to `True` in the CLI `graph_cmd`. For the admin graph, locate where the graph rendering decides whether to include relations and flip the default.

**Rationale**: Relations are core to the graph's value. The current `False` default hides them, causing confusion. Existing callers that pass the flag explicitly are unaffected.

**Alternatives considered**:
- Add a `taxomesh.toml` config key to control the default: adds indirection and config complexity for a simple UX change.
- Deprecation path with `--show-relations` changing to a positional flag: unnecessary; the flag already exists.

---

## Decision 5: TaxomeshService.list_categories with external_id

**Decision**: Add `external_id: str | None = None` keyword parameter. When `external_id` is provided, delegate to the existing `self._repo.list_categories_by_external_id(external_id)` repository method (same as `get_categories_by_external_id` does), then filter by `parent_id` if also provided. The existing `@memoize` decorator will cache by the combined `(parent_id, external_id)` key.

**Rationale**: The repository protocol already exposes `list_categories_by_external_id`. Reusing it avoids duplicating filter logic and keeps the repository as the single source of truth for storage queries. Cache keys are argument-tuples, so the new parameter naturally extends caching without conflict.

**Alternatives considered**:
- Filter Python-side after `list_categories(parent_id=None)`: loads all categories then discards non-matching ones; unnecessary overhead when the repo already has an indexed lookup.
- Add an `external_id` parameter to the repository's `list_categories` method itself: requires changing the protocol signature and all adapter implementations for a filtering concern better handled at the service layer.

---

## Decision 6: TaxomeshService.get_debug() and Repository debug info

**Decision**: Add `get_debug_info() -> dict[str, Any]` to the `TaxomeshRepositoryBase` Protocol. Each adapter implements it:
- `JsonRepository`: returns `{"path": str(self._path)}`
- `YamlRepository`: returns `{"path": str(self._path)}`
- `DjangoRepository`: returns `{"database_alias": self._using}`

`TaxomeshService` stores `_config_name: str | None = None` at init time (populated when reading `taxomesh.toml`). `get_debug()` combines: `importlib.metadata.version("taxomesh")`, `_config_name`, `type(self._repo).__name__`, and repo debug info.

**Rationale**: Adding a method to the protocol is the cleanest hexagonal-architecture approach: the service depends on the protocol, not on private adapter attributes. Storing `_config_name` on the service is minimal state — a single `str | None` set once during init.

**Alternatives considered**:
- `getattr(self._repo, "_path", None)`: accesses private adapter attributes from the service layer — violates Principle I (no cross-layer leaking of adapter internals).
- Separate `DebugInfoProvider` protocol: over-engineering for a single method.

---

## Decision 7: Admin Debug View

**Decision**: Follow the `CategoryGraphProxy` pattern. Create `TaxomeshDebugProxy` as a `proxy = True` model (no migration, no new table). Register `TaxomeshDebugProxyAdmin` under `app_label = APP_LABEL` so it appears in the TAXOMESH section. The changelist_view renders a custom template showing `TaxomeshService.get_debug()` data inline; no redirect needed (unlike `CategoryGraphProxy` which redirects to a separate graph URL).

**Rationale**: Proxy model pattern is already established in the codebase (`CategoryGraphProxy`). It costs nothing at the database level and integrates naturally with Django's admin app grouping. Rendering the debug data inline in changelist_view avoids adding a custom URL pattern.

**Alternatives considered**:
- Custom admin URL with a standalone view: requires registering extra URL patterns manually — more wiring for no benefit over the proxy pattern.
- Admin site-level `index_template` override: affects all apps in admin, not just TAXOMESH.
- New non-proxy Django model with a migration: unnecessary overhead; no data is persisted.

---

## Resolved Unknowns

| Question | Answer |
|----------|--------|
| Does `list_categories` cache clash with new `external_id` param? | No — `@memoize` caches by argument tuple; new param creates new cache keys |
| Does Category.external_id already exist in the domain? | Yes — `Annotated[str, Field(max_length=256)]` with default `""` |
| Does `linked_object_url` already appear on CategoryModelAdmin list? | Yes — it's in `list_display` and uses shared `_resolve_linked_url` which reads `TAXOMESH_LINKED_MODEL` only |
| Is there a stored `_config_name` attribute on TaxomeshService? | No — must be added during `__init__` |
| Do repositories expose their storage path publicly? | No — `_path` is private; best to add `get_debug_info()` to the protocol |
| What app_label groups admin entries under "TAXOMESH"? | `APP_LABEL = "taxomesh_contrib_django"` — the Django admin renders this as the group heading |
