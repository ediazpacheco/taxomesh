# Feature Specification: Framework-Agnostic HTTP API Handlers

**Feature Branch**: `028-contrib-api`
**Created**: 2026-03-10
**Status**: Complete
**Input**: User description: "028-contrib-api — remove fastapi as dependency, add pydantic explicitly; expose TaxomeshService operations via framework-agnostic handlers in taxomesh/contrib/api/; update README.md documenting the API integration as a core feature."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consuming App Wires taxomesh into a FastAPI Route (Priority: P1)

A developer building a FastAPI application wants a `/categories` REST endpoint backed by taxomesh. They import taxomesh's request schemas, handler functions, and error mapper; register one route; and the endpoint is complete. They write no input validation models, no exception-to-status mappings, and no service-call logic — taxomesh provides all of that.

**Why this priority**: The primary value of this feature. A developer must be able to add a fully functional taxomesh-backed HTTP endpoint with ≤10 lines of integration code.

**Independent Test**: Create a minimal FastAPI app that wires `handlers.create_category` into a POST route using `schemas.CreateCategoryRequest`. Confirm the endpoint creates a category and returns 200. Confirm that a missing `name` field returns 422. Confirm that a duplicate slug raises `TaxomeshDuplicateSlugError` which maps to 409 via `errors.to_tuple`.

**Acceptance Scenarios**:

1. **Given** a FastAPI app with `TaxomeshService` injected, **When** a developer registers a POST route using `schemas.CreateCategoryRequest` and `handlers.create_category`, **Then** the endpoint validates the request body, creates the category, and returns the domain model — with no taxomesh framework-specific code in the handler.
2. **Given** a POST request with a missing required field (`name`), **When** Pydantic validates `CreateCategoryRequest`, **Then** a 422 Unprocessable Entity is returned before the handler is called.
3. **Given** a POST request for a category whose slug is already taken, **When** `handlers.create_category` raises `TaxomeshDuplicateSlugError`, **Then** `errors.to_tuple(exc)` returns `(409, {"detail": "..."})` which the consuming app wraps into an `HTTPException`.

---

### User Story 2 - Consuming App Wires taxomesh into a Django View (Priority: P2)

A developer building a Django application uses the same schemas and handlers — unchanged — to build a class-based view. No additional framework adapter is needed because the artefacts have no framework dependency.

**Why this priority**: Validates framework-agnosticism. The same module must work identically in both FastAPI and Django, proving that taxomesh ships no framework coupling.

**Independent Test**: Create a Django `View.post` method that parses `request.body` into `CreateCategoryRequest`, calls `handlers.create_category`, and returns `JsonResponse(result.model_dump())`. Confirm success returns 200. Confirm `TaxomeshNotFoundError` maps to 404 via `errors.to_tuple`.

**Acceptance Scenarios**:

1. **Given** a Django view that parses `request.body` into `CreateCategoryRequest`, **When** the handler succeeds, **Then** `result.model_dump()` is passed to `JsonResponse` with status 200.
2. **Given** a `TaxomeshNotFoundError` raised by any handler, **When** the view calls `errors.to_tuple(exc)`, **Then** it receives `(404, {"detail": "..."})` and returns a 404 `JsonResponse`.

---

### User Story 3 - Developer Discovers the API Integration in the README (Priority: P3)

A developer reading the taxomesh README immediately understands that the library ships HTTP integration helpers and sees exactly how to wire them into their preferred framework. They can copy-paste the FastAPI or Django example and have a working endpoint without reading source code.

**Why this priority**: Without documentation, the feature is invisible. The README must position the API integration as a first-class capability.

**Independent Test**: A developer unfamiliar with the codebase reads only the "HTTP API integration" README section and successfully produces a working FastAPI or Django endpoint from the example alone.

**Acceptance Scenarios**:

1. **Given** the README "HTTP API integration" section, **When** a developer copies the FastAPI snippet, **Then** it runs without modification against a fresh `TaxomeshService`.
2. **Given** the README error mapping table, **When** a developer encounters a `TaxomeshDuplicateSlugError`, **Then** they already know it maps to 409 without inspecting library source code.
3. **Given** the README installation section, **When** a developer checks the listed runtime dependencies, **Then** `fastapi` does not appear and `pydantic` appears as the direct dependency.

---

### Edge Cases

- What happens when a consuming app sends an unknown field in the request body? Pydantic v2 ignores extra fields by default; the schema silently discards them. Consuming apps may enforce stricter validation in their own wrappers.
- What happens when `name` exceeds `MAX_CATEGORY_NAME_LENGTH` (256 chars)? `CreateCategoryRequest` declares `max_length=256`; Pydantic raises `ValidationError` before the handler is reached.
- What happens when `errors.to_tuple` receives `TaxomeshDuplicateSlugError`? Despite being a subclass of `TaxomeshValidationError`, it maps to **409** because the check order in `to_tuple` tests `TaxomeshDuplicateSlugError` before `TaxomeshValidationError`.
- What happens when a future `TaxomeshError` subclass is not in the mapping? It falls through to the base `TaxomeshError` branch and returns 500.

## Requirements *(mandatory)*

### Functional Requirements

**Dependency cleanup**

- **FR-001**: `fastapi>=0.110` MUST be removed from `[project.dependencies]` in `pyproject.toml`.
- **FR-002**: `fastapi>=0.110` MUST be removed from `[project.optional-dependencies.dev]` in `pyproject.toml`.
- **FR-003**: `pydantic>=2.0` MUST be added as an explicit entry in `[project.dependencies]`.

**`schemas.py` — request models**

- **FR-004**: `CreateCategoryRequest` MUST declare `name` (required, `max_length=MAX_CATEGORY_NAME_LENGTH`), `description` (default `""`, `max_length=MAX_DESCRIPTION_LENGTH`), `slug` (default `""`, `max_length=MAX_SLUG_LENGTH`), and `metadata` (default `{}`).
- **FR-005**: `UpdateCategoryRequest` MUST declare all fields as optional (`None` by default); handlers apply only non-`None` values.
- **FR-006**: `CreateItemRequest` MUST declare `name` (required), `external_id` (default `""`), `slug` (default `""`), `metadata` (default `{}`). All string fields MUST carry `max_length` constraints matching domain constants.
- **FR-007**: `UpdateItemRequest` MUST declare `name`, `external_id`, `enabled`, `slug`, and `metadata` — all optional. `TaxomeshService.update_item()` MUST be extended to accept an `external_id` parameter so the handler can propagate it; the field MUST NOT be silently discarded.
- **FR-008**: `CreateTagRequest` MUST declare `name` (required, `max_length=MAX_TAG_NAME_LENGTH`) and `metadata` (default `{}`).
- **FR-009**: `UpdateTagRequest` MUST declare `name` as optional.
- **FR-010**: `AddParentRequest` MUST declare `parent_id: UUID` (required) and `sort_index: int` (default `0`).
- **FR-011**: `PlaceInCategoryRequest` MUST declare `category_id: UUID` (required) and `sort_index: int` (default `0`).

**`handlers.py` — service delegation functions**

- **FR-012**: Each handler function MUST accept `TaxomeshService` as its first positional argument and delegate exclusively to the service — no business logic in handlers.
- **FR-013**: Category handlers MUST cover: `list_categories`, `get_category`, `get_category_by_slug`, `create_category`, `update_category`, `delete_category`.
- **FR-014**: Item handlers MUST cover: `list_items`, `get_item`, `get_item_by_slug`, `get_items_by_external_id`, `create_item`, `update_item`, `delete_item`.
- **FR-015**: Tag handlers MUST cover: `list_tags`, `create_tag`, `update_tag`, `delete_tag`.
- **FR-016**: Relationship handlers MUST cover: `add_category_parent`, `remove_category_parent`, `place_item_in_category`, `remove_item_from_category`, `assign_tag`, `remove_tag_from_item`.
- **FR-017**: Graph handler MUST cover: `get_graph`.
- **FR-018**: Handlers MUST return domain model instances directly (`Category`, `Item`, `Tag`, `CategoryParentLink`, `ItemParentLink`, `TaxomeshGraph`). No serialization, no response wrapping.
- **FR-019**: Handlers MUST NOT import or depend on any HTTP framework.

**`errors.py` — exception mapping**

- **FR-020**: `to_tuple(exc: TaxomeshError) -> tuple[int, dict[str, Any]]` MUST implement the following mapping, checked in the exact order listed (`TaxomeshDuplicateSlugError` is a subclass of `TaxomeshValidationError`; reversing the order would swallow the 409 mapping):
  - `TaxomeshDuplicateSlugError` → 409
  - `TaxomeshNotFoundError` (and subclasses) → 404
  - `TaxomeshValidationError` (and remaining subclasses, including `TaxomeshCyclicDependencyError`) → 422
  - `TaxomeshRepositoryError` → 500
  - `TaxomeshError` (base fallback) → 500
- **FR-021**: The body dict MUST always contain `{"detail": str(exc)}`.
- ~~**FR-022**~~: *(removed — merged into FR-021 during spec refinement)*

**Module organisation**

- **FR-023**: `taxomesh/contrib/api/__init__.py` MUST re-export the `schemas`, `handlers`, and `errors` modules as module objects (not individual symbols), enabling `from taxomesh.contrib.api import schemas`.
- **FR-024**: All files in `taxomesh/contrib/api/` MUST pass `mypy --strict` with zero errors.
- **FR-025**: Unit tests MUST cover `schemas`, `handlers`, and `errors` using `InMemoryRepository` — no HTTP server, no framework dependency in the test suite.

**README.md**

- **FR-026**: README MUST include a new "HTTP API integration" section, placed prominently as a core feature section (not in advanced topics).
- **FR-027**: The section MUST include a self-contained FastAPI wiring example (route + schema + handler + error handling).
- **FR-028**: The section MUST include a self-contained Django view wiring example (view + schema + handler + error handling).
- **FR-029**: The section MUST include an exception-to-HTTP-status mapping table covering all `TaxomeshError` subclasses.
- **FR-030**: The README installation / dependency listing MUST reflect `pydantic` as the direct runtime dependency; `fastapi` must not appear as a taxomesh dependency.

### Key Entities

- **`schemas`** (`taxomesh/contrib/api/schemas.py`): Pydantic `BaseModel` subclasses providing the HTTP request contract. No framework imports; reusable across FastAPI, Django, Flask, etc.
- **`handlers`** (`taxomesh/contrib/api/handlers.py`): Pure Python functions — one per `TaxomeshService` operation — that accept a validated schema and return domain model instances. No serialization, no framework coupling.
- **`errors`** (`taxomesh/contrib/api/errors.py`): Single public function `to_tuple`. Maps the taxomesh exception hierarchy to `(status_code, body_dict)` pairs for any HTTP framework to wrap.

## Clarifications

### Session 2026-03-10

- Q: FR-007 specifies `UpdateItemRequest` includes `external_id`, but the field was silently dropped by the handler (service.update_item has no such parameter). Remove the field or extend the service? → A: Extend `TaxomeshService.update_item()` to accept `external_id`; keep the field in the schema so API consumers can update it.
- Q: SC-004 claims 100% line coverage for `taxomesh/contrib/api/`; the constitution mandates ≥80%. What target should SC-004 enforce? → A: ≥90% of lines in `taxomesh/contrib/api/`.
- Note: Constitution Principle IX (FastAPI mandatory) conflicted with this feature. Amendment applied directly in `028-contrib-api` — Principle IX updated to "Framework-Agnostic HTTP Handlers" and FastAPI removed from the Toolchain table. No follow-up spec required.

## Assumptions

- Schema `max_length` values are imported from `taxomesh.domain.constants` to keep a single source of truth; they are not duplicated in `schemas.py`.
- Consuming apps call `.model_dump()` on returned Pydantic domain models; taxomesh does not control HTTP response serialization.
- `TaxomeshGraph` and `CategoryNode` are dataclasses (not Pydantic models); consuming apps must serialize them manually (e.g. via `dataclasses.asdict`). This limitation is acknowledged but out of scope.
- mypy excludes `taxomesh/contrib/django/` but not `taxomesh/contrib/api/`; the new module is fully type-checked under `mypy --strict`.
- The `taxomesh/contrib/api/` tests use the same `InMemoryRepository` defined in `tests/service/conftest.py`; a `tests/contrib/conftest.py` imports it to expose a `service` fixture.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A consuming app can add a fully functional taxomesh-backed HTTP endpoint by writing ≤10 non-blank, non-import lines of integration code per endpoint (route decorator, request body parsing, handler call, try/except with `errors.to_tuple`, and response construction).
- **SC-002**: Installing `taxomesh` does not pull in FastAPI as a transitive dependency; `pip show taxomesh` lists `pydantic`, not `fastapi`, under `Requires`.
- **SC-003**: `mypy --strict .` reports zero errors across all files in `taxomesh/contrib/api/`.
- **SC-004**: The `tests/contrib/test_api_*.py` suite covers ≥90% of lines in `taxomesh/contrib/api/`; total project coverage remains ≥ 80%.
- **SC-005**: The same `schemas`, `handlers`, and `errors` modules work without modification in both the FastAPI and Django README examples.
- **SC-006**: A developer reading only the README "HTTP API integration" section can produce a working endpoint without consulting taxomesh source code.
