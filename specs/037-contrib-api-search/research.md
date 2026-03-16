# Research: 037-contrib-api-search

## Decision 1: Where to define DEFAULT_SEARCH_LIMIT for schemas

**Decision**: Import `DEFAULT_SEARCH_LIMIT` directly from `taxomesh.application.search` as the default value for the `limit` field in both request schemas.

**Rationale**: The constant already exists at `taxomesh.application.search.DEFAULT_SEARCH_LIMIT = 20`. Redefining it in `schemas.py` (or in `domain/constants.py`) would violate Principle X (single source of truth, no duplicate literals). Importing it from `application.search` keeps the two values in sync at zero cost.

**Alternatives considered**:
- Define a new `DEFAULT_SEARCH_LIMIT` in `domain/constants.py` — rejected because the same constant would then exist in two places.
- Hardcode `20` directly in `Field(default=20)` — rejected as a magic literal (Principle X).

---

## Decision 2: max_length constraint for the `q` (query) field

**Decision**: Add `MAX_SEARCH_QUERY_LENGTH: Final[int] = 500` to `taxomesh/domain/constants.py` and annotate `q` in both schemas as `Annotated[str, Field(max_length=MAX_SEARCH_QUERY_LENGTH)]`.

**Rationale**: Principle IV mandates an explicit `max_length` on every `str` field in a Pydantic model. There is no existing query-string constant. 500 characters is generous enough for any realistic search phrase while preventing trivially oversized inputs.

**Alternatives considered**:
- Reuse `MAX_ITEM_NAME_LENGTH` (256) — rejected because query strings are not names; 256 may be too short for multi-word searches over long names.
- No constraint (`str` without `max_length`) — rejected as a direct Principle IV violation.

---

## Decision 3: Location of new code (no new source files)

**Decision**: All additions extend the four existing `taxomesh/contrib/api/` modules (`schemas.py`, `handlers.py`, `serializers.py`). No new source files are created.

**Rationale**: The existing modules already have the correct structure and imports. Adding to them follows the same pattern as every prior contrib.api feature. YAGNI — no abstraction is needed for two new schemas, two new handlers, and two new serializers.

**Alternatives considered**:
- Create `taxomesh/contrib/api/search.py` — rejected as unnecessary indirection for six small additions.

---

## Decision 4: Test placement (extend existing test files)

**Decision**: New tests are added to the three existing contrib test files:
- `tests/contrib/test_api_schemas.py` — schema validation tests
- `tests/contrib/test_api_handlers.py` — handler delegation tests
- `tests/contrib/test_api_serializers.py` — serializer output tests

**Rationale**: Consistent with how prior contrib.api features were tested. The existing `conftest.py` `service` fixture (backed by `InMemoryRepository`) is sufficient for all new tests.

**Alternatives considered**:
- New files `test_api_search_*.py` — rejected; adding new sections to existing files avoids file proliferation and keeps related tests together.

---

## Decision 5: Handler return type — domain models, not serialized output

**Decision**: `search_items` returns `list[Item]` and `search_categories` returns `list[Category]`. The serializers are separate functions called explicitly by the consumer.

**Rationale**: Principle IX mandates that handlers return domain model instances directly. Serialization is a separate concern. This is identical to how all existing handlers behave.

**Alternatives considered**:
- Return serialized dicts from handlers — rejected as a direct Principle IX violation.
