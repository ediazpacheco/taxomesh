# Research: Framework-Agnostic HTTP API Handlers

**Feature**: 028-contrib-api
**Date**: 2026-03-10

## Decision 1 — Module path: `contrib/api/` vs `adapters/api/`

**Decision**: Place the new module at `taxomesh/contrib/api/`, not `taxomesh/adapters/api/`.

**Rationale**: The existing `taxomesh/contrib/` package holds optional extras that extend taxomesh for specific ecosystems without being part of the core (e.g. `contrib/django/`). The HTTP handler helpers follow the same pattern — they are optional extras for consuming apps that want HTTP exposure, not a mandatory adapter. `adapters/` contains concrete storage adapters; the HTTP layer is conceptually different.

**Alternatives considered**:
- `adapters/api/` — matches constitution Principle IX wording, but conflates storage adapters with HTTP adapters. Constitution Principle IX itself predates the framework-agnostic approach and will be amended.
- `taxomesh/api/` — flat under root; would imply it is a core module, which it is not.

---

## Decision 2 — Handlers as module-level functions vs a class

**Decision**: Module-level functions. One function per `TaxomeshService` operation.

**Rationale**: Handlers are pure delegation stubs — `return service.some_method(...)`. They hold no state, share no configuration, and have no logical grouping that benefits from a class. The constitution (Principle XI) explicitly permits module-level functions when they are stateless and do not logically belong to a class. A `Handlers` class with 22 `@staticmethod` methods would add ceremony with zero benefit.

**Alternatives considered**:
- `class Handlers` with `@staticmethod` methods — adds boilerplate; still requires passing `service` on every call.
- Bound class that stores `service` in `__init__` — would require instantiation per-endpoint or as a singleton; complicates the consuming-app wiring without simplifying the implementation.

---

## Decision 3 — Pydantic `BaseModel` for schemas (not dataclasses or TypedDict)

**Decision**: `pydantic.BaseModel` subclasses for all request schemas.

**Rationale**: Pydantic v2 is already a direct runtime dependency. `BaseModel` provides `max_length` constraint enforcement, `.model_validate_json()` for framework-agnostic deserialization, and `.model_dump()` on domain models returned by handlers. No additional dependency is needed.

**Alternatives considered**:
- `dataclasses` — no built-in field validation; consuming apps would need to add their own.
- `TypedDict` — type-safe but no runtime validation; consuming apps would need to add their own validation layer.

---

## Decision 4 — `to_tuple` as a module-level function (not a mapper class)

**Decision**: Single module-level function `to_tuple(exc: TaxomeshError) -> tuple[int, dict[str, Any]]`.

**Rationale**: The mapping logic is a pure, stateless function with no configuration knobs. A class would add instantiation ceremony for no benefit. The constitution permits module-level functions for stateless utilities.

**Alternatives considered**:
- `ExceptionMapper` class — adds `__init__` and call overhead with no benefit; one function is clearer.
- Dictionary dispatch table — slightly less readable than an `isinstance` chain for a 4-entry mapping.

---

## Decision 5 — HTTP status code constants with `Final[int]`

**Decision**: Define `_HTTP_404`, `_HTTP_409`, `_HTTP_422`, `_HTTP_500` as `Final[int]` module-level constants.

**Rationale**: Constitution Principle X (Named Constants) forbids magic literals in business logic. HTTP status codes are domain-meaningful values that must be defined as named constants.

**Alternatives considered**:
- Inline integer literals — violates Principle X.
- Importing from an `http.HTTPStatus` enum — adds indirection without clarity; `_HTTP_404` is already self-documenting.

---

## Decision 6 — Remove FastAPI; add Pydantic as explicit dep

**Decision**: Remove `fastapi>=0.110` from `[project.dependencies]` and dev extras; add `pydantic>=2.0` explicitly.

**Rationale**: FastAPI was never imported in any taxomesh source file. It was listed only to pull Pydantic v2 transitively. Listing FastAPI as a runtime dep for a library that doesn't use it forces every consuming app to install a large web framework unnecessarily. Making Pydantic explicit achieves the same result (Pydantic v2 guaranteed) with zero unnecessary transitive deps.

**Alternatives considered**:
- Keep FastAPI and add Pydantic — redundant; FastAPI would still pull Pydantic, just with an extra dep entry.
- Use `pydantic>=2.0,<3` — the `>=2.0` constraint is sufficient; upper bound not needed until Pydantic v3 is a reality.
