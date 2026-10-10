# HTTP API Integration

`taxomesh` ships **no HTTP server**. `taxomesh.contrib.api` gives an application that already has
one the request models, the calls into the service and the error mapping, so no endpoint
re-implements them. The handlers do no authentication, no authorization and no rate limiting: your
application does them. The modules depend on no web framework:

```python
from taxomesh.contrib.api import schemas      # Pydantic request models, search included
from taxomesh.contrib.api import handlers     # one function per collection member
from taxomesh.contrib.api import errors       # errors.to_tuple(exc) -> (status_code, body)
from taxomesh.contrib.api import serializers  # graph_to_dict, items_to_list, categories_to_list
```

## The handlers, without a framework

Each handler is named `<namespace>_<member>` after the member it calls, and answers what that member
answers: `handlers.categories_get_by_slug(service, slug)` is `service.categories.get_by_slug(slug)`.
A lookup returns `None` on a miss, which your application turns into its 404. A subject or a filter
that names an entity that is not stored raises the not-found error of that entity. A handler's
arguments are typed as its member's are, so parse what arrives as text: a query string's
`enabled="true"` is a `TypeError`, not a filter. The search schemas parse text:
`SearchItemsRequest(query="blue", enabled="false", limit="5")` holds `False` and `5`. Over HTTP
only, `query` is at most `MAX_SEARCH_QUERY_LENGTH` characters (`taxomesh.domain.constants`).

```python
from taxomesh import TaxomeshService, TaxomeshVersionConflictError
from taxomesh.exceptions import TaxomeshError

service = TaxomeshService()  # auto-discovers taxomesh.toml, else a YAML file in ./data/

music = handlers.categories_create(service, body=schemas.CreateCategoryRequest(name="Music", external_id="cat-music"))
jazz = handlers.categories_create(service, body=schemas.CreateCategoryRequest(name="Jazz"))
handlers.categories_add_parent(service, jazz.category_id, body=schemas.AddCategoryParentRequest(parent_id=music.category_id))
item = handlers.items_create(service, body=schemas.CreateItemRequest(name="Kind of Blue", slug="kind-of-blue"))
handlers.items_place_in(service, item.item_id, body=schemas.PlaceItemRequest(category_id=jazz.category_id))
live = handlers.tags_create(service, body=schemas.CreateTagRequest(name="live"))
handlers.items_tag(service, item.item_id, tag_id=live.tag_id)

# Listings take the member's filters, spelled with _id as HTTP names an entity.
assert {c.name for c in handlers.categories_list(service)} == {"Music", "Jazz"}
assert [c.name for c in handlers.categories_roots(service)] == ["Music"]
assert [i.name for i in handlers.items_list(service, category_id=music.category_id, recursive=True)] == ["Kind of Blue"]
assert [t.name for t in handlers.tags_list(service, item_id=item.item_id)] == ["live"]

# A lookup answers None on a miss.
assert handlers.categories_get_by_external_id(service, "cat-music") == music
assert handlers.items_get_by_slug(service, "no-such-slug") is None

# An omitted update field is left as it is stored.
renamed = handlers.categories_update(service, jazz.category_id, body=schemas.UpdateCategoryRequest(name="Modal Jazz"))
assert renamed.enabled and renamed.name == "Modal Jazz"

# Search takes the member's parameters; serializers turn rows and graphs into JSON-ready values.
found = handlers.items_search(service, params=schemas.SearchItemsRequest(query="blue"))
assert serializers.items_to_list(found)[0]["name"] == "Kind of Blue"
assert [root["category"]["name"] for root in serializers.graph_to_dict(handlers.graph(service))["roots"]] == ["Music"]

# A refused write maps to a status: a cycle is a validation error, 422.
try:
    handlers.categories_add_parent(service, music.category_id, body=schemas.AddCategoryParentRequest(parent_id=jazz.category_id))
except TaxomeshError as exc:
    assert errors.to_tuple(exc)[0] == 422
else:
    raise AssertionError("a cycle is refused")
assert errors.to_tuple(TaxomeshVersionConflictError("stale"))[0] == 409
```

An update request is partial: the handler forwards only the fields that the caller set, and the
JSON Schema publishes no default for a stored field. The schema refuses a `null` on a field that
cannot be `None`, and `"external_id": null` clears the external id.

## Available handlers

| Namespace | Handlers |
|-------|---------|
| Categories | `categories_list`, `categories_roots`, `categories_get`, `categories_get_by_slug`, `categories_get_by_external_id`, `categories_create`, `categories_update`, `categories_delete`, `categories_add_parent`, `categories_remove_parent`, `categories_search` |
| Items | `items_list`, `items_get`, `items_get_by_slug`, `items_get_by_external_id`, `items_create`, `items_update`, `items_delete`, `items_place_in`, `items_remove_from`, `items_tag`, `items_untag`, `items_search` |
| Tags | `tags_list`, `tags_get`, `tags_create`, `tags_update`, `tags_delete` |
| Graph | `graph`, which calls `service.graph()` |

No handler calls the batch lookups (`get_many`, `get_many_by_external_id`, `get_many_related`),
`move`, `reorder` or the relation members (`relate`, `unrelate`, `list_relations`,
`list_related`), and `graph` takes `enabled` only, not `root` or `include_items`.
`serializers.graph_to_dict` starts at `graph.roots`, the top-level categories, so a category that no
top-level category reaches is not in the document, though the graph holds it and `walk()` yields it.
A category with several parents is written once for each path to it, and past
`serializers.MAX_EMITTED_NODES` nodes, `graph_to_dict` raises `TaxomeshGraphTooLargeError`.

## FastAPI example

```python notest
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from taxomesh import TaxomeshService
from taxomesh.contrib.api import errors, handlers, schemas, serializers
from taxomesh.exceptions import TaxomeshError

app = FastAPI()
service = TaxomeshService()


@app.exception_handler(TaxomeshError)
def taxomesh_error(request, exc):
    status, body = errors.to_tuple(exc)
    return JSONResponse(body, status_code=status)


@app.post("/categories", status_code=201)
def create_category(body: schemas.CreateCategoryRequest):
    return handlers.categories_create(service, body=body)


@app.get("/categories/{category_id}")
def get_category(category_id: UUID):
    category = handlers.categories_get(service, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail=f"Category not found: {category_id}")
    return category


@app.patch("/categories/{category_id}")
def update_category(category_id: UUID, body: schemas.UpdateCategoryRequest):
    return handlers.categories_update(service, category_id, body=body)


@app.delete("/categories/{category_id}", status_code=204)
def delete_category(category_id: UUID):
    handlers.categories_delete(service, category_id)


@app.get("/search/items")
def search_items(q: str, limit: int = 20):
    return serializers.items_to_list(handlers.items_search(service, params=schemas.SearchItemsRequest(query=q, limit=limit)))


@app.get("/graph")
def get_graph():
    return serializers.graph_to_dict(handlers.graph(service))
```

A Django view makes the same calls. It returns `JsonResponse(row.model_dump(mode="json"))` for a
row, and the serializers' output for a listing, a search or the graph: `graph_to_dict` returns a
dict, `items_to_list` and `categories_to_list` a list, which needs `JsonResponse(..., safe=False)`.
A request schema refuses bad input with `pydantic.ValidationError`. Neither that error nor a
`TypeError` is a `TaxomeshError`, so `errors.to_tuple` does not map them. FastAPI answers 422
itself when the schema is a parameter of the endpoint. Where your code builds the schema, as
`search_items` does, and in a Django view, catch the error.

## Error mapping

| Exception | HTTP status | `detail` |
|-----------|-------------|----------|
| `TaxomeshDuplicateSlugError`, `TaxomeshExternalIdConflictError`, `TaxomeshVersionConflictError` | 409 | the exception's message |
| `TaxomeshNotFoundError` and its subclasses | 404 | the exception's message |
| `TaxomeshValidationError` and its subclasses | 422 | the exception's message |
| any other `TaxomeshError`, `TaxomeshRepositoryError` and `TaxomeshGraphTooLargeError` included | 500 | `errors.GENERIC_SERVER_ERROR_DETAIL` |

A client error's message is written by taxomesh from the caller's own input, so it is safe to show.
A server error's is not: `TaxomeshRepositoryError` carries the backend's message verbatim, table
names and file paths included. So a 500's body is a fixed string. The original exception and its
traceback go to one `ERROR` log record on the `taxomesh.contrib.api.errors` logger. The log record
propagates to `taxomesh`, which has only a `NullHandler`: attach a handler, as
[Errors](python-api.md#errors) shows. On Django, the `django.request` log record of the same 500
carries no traceback, and [Logging](django-integration.md#logging) mails the taxomesh log record.

← [Back to README](../README.md)
