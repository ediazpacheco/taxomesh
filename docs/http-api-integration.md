# HTTP API Integration

taxomesh ships **no HTTP server**. Instead, it provides three framework-agnostic modules
in `taxomesh.contrib.api` that you wire into your existing application with ≤10 lines per
endpoint — and the same code works in FastAPI, Django, Flask, or any other framework.

```python
from taxomesh.contrib.api import schemas   # Pydantic request models
from taxomesh.contrib.api import handlers  # Pure delegation functions → TaxomeshService
from taxomesh.contrib.api import errors    # errors.to_tuple(exc) → (status_code, body)
```

## FastAPI example

```python
from taxomesh import TaxomeshService
from taxomesh.contrib.api import errors, handlers, schemas
from taxomesh.exceptions import TaxomeshError
from fastapi import FastAPI, HTTPException

app = FastAPI()
service = TaxomeshService()  # auto-discovers taxomesh.toml

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

The same pattern applies to items, tags, relationships, and graph — one handler function per operation.

## Django example

```python
# myapp/views.py
from uuid import UUID
from django.http import JsonResponse
from django.views import View

from taxomesh import TaxomeshService
from taxomesh.contrib.api import errors, handlers, schemas
from taxomesh.exceptions import TaxomeshError

service = TaxomeshService()  # initialise once (e.g. in AppConfig.ready)


class CategoryListView(View):
    def get(self, request):
        return JsonResponse(
            [c.model_dump() for c in handlers.list_categories(service)],
            safe=False,
        )

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

## Error mapping

`errors.to_tuple(exc)` maps any `TaxomeshError` to `(status_code, {"detail": "..."})`:

| Exception | HTTP status |
|-----------|-------------|
| `TaxomeshDuplicateSlugError` | 409 Conflict |
| `TaxomeshNotFoundError` (+ subclasses) | 404 Not Found |
| `TaxomeshValidationError` (+ subclasses) | 422 Unprocessable Entity |
| `TaxomeshRepositoryError` | 500 Internal Server Error |
| `TaxomeshError` (base fallback) | 500 Internal Server Error |

## Available handlers

| Group | Handlers |
|-------|---------|
| Categories | `list_categories`, `get_category`, `get_category_by_slug`, `create_category`, `update_category`, `delete_category` |
| Items | `list_items`, `get_item`, `get_item_by_slug`, `get_items_by_external_id`, `create_item`, `update_item`, `delete_item` |
| Tags | `list_tags`, `create_tag`, `update_tag`, `delete_tag` |
| Relationships | `add_category_parent`, `remove_category_parent`, `place_item_in_category`, `remove_item_from_category`, `assign_tag`, `remove_tag_from_item` |
| Graph | `get_graph` |

## Installation note

`taxomesh` ships `pydantic>=2.0` as a direct runtime dependency.
No FastAPI installation is required to use `taxomesh.contrib.api`.

```bash
pip install taxomesh           # pydantic included; no fastapi required
pip install "taxomesh[django]" # + Django ORM adapter
```

← [Back to README](../README.md)
