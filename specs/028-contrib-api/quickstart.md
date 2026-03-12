# Quickstart: `taxomesh.contrib.api`

**Feature**: 028-contrib-api
**Date**: 2026-03-10

## What this is

`taxomesh.contrib.api` provides three framework-agnostic artefacts that let you expose `TaxomeshService` operations over HTTP with minimal boilerplate:

- **`schemas`** — Pydantic request models (validated input, no framework coupling)
- **`handlers`** — Pure delegation functions: each calls one `TaxomeshService` method
- **`errors`** — `to_tuple(exc)` maps any `TaxomeshError` to `(status_code, body_dict)`

taxomesh ships **no HTTP server**. You register routes; taxomesh provides the logic.

---

## FastAPI integration

```python
from taxomesh import TaxomeshService
from taxomesh.contrib.api import errors, handlers, schemas
from taxomesh.exceptions import TaxomeshError
from fastapi import FastAPI, HTTPException

app = FastAPI()
service = TaxomeshService()  # auto-discovers taxomesh.toml

# ---- Categories ----

@app.get("/categories")
def list_categories():
    return handlers.list_categories(service)

@app.post("/categories", status_code=201)
def create_category(body: schemas.CreateCategoryRequest):
    try:
        return handlers.create_category(service, body)
    except TaxomeshError as e:
        status, detail = errors.to_tuple(e)
        raise HTTPException(status_code=status, detail=detail)

@app.get("/categories/{category_id}")
def get_category(category_id: str):
    from uuid import UUID
    try:
        return handlers.get_category(service, UUID(category_id))
    except TaxomeshError as e:
        status, detail = errors.to_tuple(e)
        raise HTTPException(status_code=status, detail=detail)

@app.patch("/categories/{category_id}")
def update_category(category_id: str, body: schemas.UpdateCategoryRequest):
    from uuid import UUID
    try:
        return handlers.update_category(service, UUID(category_id), body)
    except TaxomeshError as e:
        status, detail = errors.to_tuple(e)
        raise HTTPException(status_code=status, detail=detail)

@app.delete("/categories/{category_id}", status_code=204)
def delete_category(category_id: str):
    from uuid import UUID
    try:
        handlers.delete_category(service, UUID(category_id))
    except TaxomeshError as e:
        status, detail = errors.to_tuple(e)
        raise HTTPException(status_code=status, detail=detail)
```

---

## Django integration

```python
# myapp/views.py
import json
from uuid import UUID

from django.http import JsonResponse
from django.views import View

from taxomesh import TaxomeshService
from taxomesh.contrib.api import errors, handlers, schemas
from taxomesh.exceptions import TaxomeshError

service = TaxomeshService()  # initialise once (e.g. in AppConfig.ready)


class CategoryListView(View):
    def get(self, request):
        return JsonResponse([c.model_dump() for c in handlers.list_categories(service)], safe=False)

    def post(self, request):
        body = schemas.CreateCategoryRequest.model_validate_json(request.body)
        try:
            result = handlers.create_category(service, body)
            return JsonResponse(result.model_dump(), status=201)
        except TaxomeshError as e:
            status, detail = errors.to_tuple(e)
            return JsonResponse(detail, status=status)


class CategoryDetailView(View):
    def get(self, request, category_id: str):
        try:
            result = handlers.get_category(service, UUID(category_id))
            return JsonResponse(result.model_dump())
        except TaxomeshError as e:
            status, detail = errors.to_tuple(e)
            return JsonResponse(detail, status=status)

    def patch(self, request, category_id: str):
        body = schemas.UpdateCategoryRequest.model_validate_json(request.body)
        try:
            result = handlers.update_category(service, UUID(category_id), body)
            return JsonResponse(result.model_dump())
        except TaxomeshError as e:
            status, detail = errors.to_tuple(e)
            return JsonResponse(detail, status=status)

    def delete(self, request, category_id: str):
        try:
            handlers.delete_category(service, UUID(category_id))
            return JsonResponse({}, status=204)
        except TaxomeshError as e:
            status, detail = errors.to_tuple(e)
            return JsonResponse(detail, status=status)
```

---

## Error mapping table

| taxomesh exception | HTTP status | Meaning |
|--------------------|-------------|---------|
| `TaxomeshDuplicateSlugError` | 409 Conflict | Slug already in use |
| `TaxomeshNotFoundError` (+ subclasses) | 404 Not Found | Entity does not exist |
| `TaxomeshValidationError` (+ subclasses) | 422 Unprocessable | Domain rule violated (e.g. cyclic DAG) |
| `TaxomeshRepositoryError` | 500 Internal Error | Storage failure |
| `TaxomeshError` (base fallback) | 500 Internal Error | Unexpected error |

---

## Installation note

`taxomesh` ships `pydantic>=2.0` as a direct runtime dependency. No FastAPI installation is required to use `taxomesh.contrib.api`.

```bash
pip install taxomesh           # plain install — pydantic included
pip install "taxomesh[django]" # + Django ORM adapter
```
