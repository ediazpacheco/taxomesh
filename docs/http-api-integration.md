# HTTP API Integration

Use this when you already have a web application and want to expose taxonomy operations
without re-implementing request models, service delegation, and error mapping in every
endpoint.

`taxomesh` ships **no HTTP server**. Instead, it provides four framework-agnostic
modules in `taxomesh.contrib.api` that you wire into your existing application. The same
building blocks work in FastAPI, Django, Flask, or any other Python web framework.

```python
from taxomesh.contrib.api import schemas      # Pydantic request models (incl. search request schemas)
from taxomesh.contrib.api import handlers     # Pure delegation functions → TaxomeshService
from taxomesh.contrib.api import errors       # errors.to_tuple(exc) → (status_code, body)
from taxomesh.contrib.api import serializers  # graph_to_dict, items_to_list, categories_to_list
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

The same pattern applies to items, tags, and relationships — one handler function per operation.

For the graph endpoint, combine `handlers.get_graph` with `serializers.graph_to_dict` to produce
a fully JSON-serializable response:

```python
from taxomesh.contrib.api import handlers, serializers

@app.get("/graph")
def get_graph():
    return serializers.graph_to_dict(handlers.get_graph(service))
```

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
            [c.model_dump(mode="json") for c in handlers.list_categories(service)],
            safe=False,
        )

    def post(self, request):
        body = schemas.CreateCategoryRequest.model_validate_json(request.body)
        try:
            result = handlers.create_category(service, body)
            return JsonResponse(result.model_dump(mode="json"), status=201)
        except TaxomeshError as e:
            status, detail = errors.to_tuple(e)
            return JsonResponse(detail, status=status)


class CategoryDetailView(View):
    def get(self, request, category_id: str):
        try:
            result = handlers.get_category(service, UUID(category_id))
            return JsonResponse(result.model_dump(mode="json"))
        except TaxomeshError as e:
            status, detail = errors.to_tuple(e)
            return JsonResponse(detail, status=status)

    def patch(self, request, category_id: str):
        body = schemas.UpdateCategoryRequest.model_validate_json(request.body)
        try:
            result = handlers.update_category(service, UUID(category_id), body)
            return JsonResponse(result.model_dump(mode="json"))
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

For the graph endpoint, use `serializers.graph_to_dict` — handlers return a `TaxomeshGraph` dataclass
which is not directly JSON-serializable:

```python
from django.http import JsonResponse
from taxomesh.contrib.api import handlers, serializers

def graph_view(request):
    return JsonResponse(serializers.graph_to_dict(handlers.get_graph(service)))
```

## Search endpoints

Use `schemas.SearchItemsRequest` and `schemas.SearchCategoriesRequest` together with
`handlers.search_items` / `handlers.search_categories` and the `serializers.items_to_list` /
`serializers.categories_to_list` helpers to add ranked, fuzzy-tolerant search to any endpoint.

### FastAPI example

```python
from taxomesh.contrib.api import handlers, schemas, serializers

@app.get("/search/items")
def search_items(q: str, limit: int = 20, fuzzy: bool = True):
    params = schemas.SearchItemsRequest(q=q, limit=limit, fuzzy=fuzzy)
    items = handlers.search_items(service, params)
    return {"results": serializers.items_to_list(items)}

@app.get("/search/categories")
def search_categories(q: str, limit: int = 20, fuzzy: bool = True):
    params = schemas.SearchCategoriesRequest(q=q, limit=limit, fuzzy=fuzzy)
    categories = handlers.search_categories(service, params)
    return {"results": serializers.categories_to_list(categories)}
```

### Django example

```python
from django.http import JsonResponse
from taxomesh.contrib.api import handlers, schemas, serializers

def search_items_view(request):
    params = schemas.SearchItemsRequest(
        q=request.GET.get("q", ""),
        limit=int(request.GET.get("limit", 20)),
        fuzzy=request.GET.get("fuzzy", "true").lower() != "false",
    )
    items = handlers.search_items(service, params)
    return JsonResponse({"results": serializers.items_to_list(items)})
```

### SearchItemsRequest fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `q` | `str` | required | Search query (max 500 chars) |
| `limit` | `int` | `20` | Maximum results returned |
| `category_id` | `UUID \| None` | `None` | Restrict results to items in this category |
| `recursive` | `bool` | `False` | Include items in descendant categories |
| `enabled` | `bool` | `True` | Exclude disabled items |
| `fuzzy` | `bool` | `True` | Enable typo-tolerant fuzzy matching |

### SearchCategoriesRequest fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `q` | `str` | required | Search query (max 500 chars) |
| `limit` | `int` | `20` | Maximum results returned |
| `parent_id` | `UUID \| None` | `None` | Restrict to direct children of this parent |
| `enabled` | `bool` | `True` | Exclude disabled categories |
| `fuzzy` | `bool` | `True` | Enable typo-tolerant fuzzy matching |

### Serializers

`items_to_list(items)` and `categories_to_list(categories)` convert domain model lists to
plain JSON-serializable dicts (via `model_dump(mode="json")`). They are separate from the
handlers so you can apply additional processing (filtering, renaming) before serializing.

```python
from taxomesh.contrib.api.serializers import categories_to_list, items_to_list

items_to_list([item])        # [{"item_id": "...", "name": "...", ...}]
categories_to_list([cat])    # [{"category_id": "...", "name": "...", ...}]
items_to_list([])            # []
```

---

## Error mapping

`errors.to_tuple(exc)` maps any `TaxomeshError` to `(status_code, {"detail": "..."})`:

| Exception | HTTP status | `detail` |
|-----------|-------------|----------|
| `TaxomeshDuplicateSlugError` | 409 Conflict | the exception message |
| `TaxomeshExternalIdConflictError` | 409 Conflict | the exception message |
| `TaxomeshNotFoundError` (+ subclasses) | 404 Not Found | the exception message |
| `TaxomeshValidationError` (+ subclasses) | 422 Unprocessable Entity | the exception message |
| `TaxomeshRepositoryError` | 500 Internal Server Error | generic — see below |
| `TaxomeshError` (base fallback) | 500 Internal Server Error | generic — see below |

### 500 bodies are generic

Client errors (404/409/422) carry the exception's own message. It is written by taxomesh
from your caller's own input, so it is safe to show and it is what lets the caller fix
the request.

Server errors do not. `TaxomeshRepositoryError` wraps the backend's message verbatim —
ORM constraint, table and column names, or the absolute path of a JSON/YAML data file —
so returning it would hand your storage layout to the client. Both 500 branches return a
fixed string instead:

```python notest
from taxomesh.contrib.api.errors import GENERIC_SERVER_ERROR_DETAIL

status, body = errors.to_tuple(exc)
# (500, {"detail": "An internal error occurred."})
assert body["detail"] == GENERIC_SERVER_ERROR_DETAIL
```

Compare against `GENERIC_SERVER_ERROR_DETAIL` rather than the literal, or better, branch
on the status code — that was always the contract.

The detail is not discarded, it is logged. Every 500 emits one `ERROR` record on the
`taxomesh` logger with the original exception and its traceback attached, so attach a
handler to see it:

```python notest
import logging

logging.getLogger("taxomesh").addHandler(logging.StreamHandler())
logging.getLogger("taxomesh").setLevel(logging.ERROR)
```

An application that configures no logging stays silent — taxomesh registers a
`NullHandler` at import.

### On Django, this logger is the only copy of the traceback

Worth stating plainly, because the obvious alternative does not work. When a
taxomesh error reaches a Django view and your middleware turns it into a 500
response, Django's own `log_response` emits a record on the `django.request`
logger for that response. If you route `django.request` to `mail_admins`, that
email arrives with **`Traceback: None`** and no exception type: by the time
`log_response` runs, `sys.exc_info()` has already been cleared, so there is no
exception left for it to format.

So after this release the failure mode is two half-records — an alert with no
traceback on `django.request`, and the real traceback on the `taxomesh` logger
going wherever you pointed it. If you pointed it nowhere, Python's
`logging.lastResort` writes it to stderr unformatted, with no timestamp and no
context.

Route the `taxomesh` logger somewhere you actually read, and if that destination
is email, rate-limit it — a database outage emits one record per request:

```python notest
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "taxomesh_rate_limit": {
            "()": "myapp.logging.RateLimitFilter",  # your own; one per interval
            "rate_seconds": 3600,
        },
    },
    "handlers": {
        "taxomesh_mail": {
            "class": "django.utils.log.AdminEmailHandler",
            "level": "ERROR",
            "filters": ["taxomesh_rate_limit"],
            "include_html": False,
        },
    },
    "loggers": {
        "taxomesh": {"handlers": ["taxomesh_mail"], "level": "ERROR", "propagate": False},
    },
}
```

`AdminEmailHandler` formats `exc_info`, so this email names the actual fault —
the one the `django.request` email cannot.

## Available handlers

| Group | Handlers |
|-------|---------|
| Categories | `list_categories`, `get_category`, `get_category_by_slug`, `create_category`, `update_category`, `delete_category` |
| Items | `list_items`, `get_item`, `get_item_by_slug`, `get_item_by_external_id`, `create_item`, `update_item`, `delete_item` |
| Tags | `list_tags`, `create_tag`, `update_tag`, `delete_tag` |
| Relationships | `add_category_parent`, `remove_category_parent`, `place_item_in_category`, `remove_item_from_category`, `assign_tag`, `remove_tag_from_item` |
| Graph | `get_graph` |
| Search | `search_items`, `search_categories` |

## Installation note

`taxomesh` ships `pydantic>=2.0` as a direct runtime dependency.
No FastAPI installation is required to use `taxomesh.contrib.api`.

```bash
pip install taxomesh           # pydantic included; no fastapi required
pip install "taxomesh[django]" # + Django ORM adapter
```

← [Back to README](../README.md)
