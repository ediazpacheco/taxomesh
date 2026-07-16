# Quickstart: API Request Omission and Explicit-Null Semantics

**Feature**: `057-api-request-omission` | **Date**: 2026-07-16

What a consumer of `taxomesh.contrib.api` needs to know, and how to verify each claim
against the running code.

## The one thing to know

**Omitting a field and sending it as `null` are different messages.**

```jsonc
// "rename it, leave everything else alone"
{"name": "New name"}

// "rename it AND erase its external identifier"
{"name": "New name", "external_id": null}
```

Before this feature the first request did what the second one says. That was the bug.

## What each request does

```jsonc
{}                          // valid; changes nothing
{"name": "x"}               // sets name; every other field untouched
{"name": null}              // 422 — a name has no null value. Omit it instead.
{"slug": ""}                // clears the slug — "" is a valid slug
{"slug": null}              // 422 — a slug has no null value
{"external_id": "ext-1"}    // sets the external identifier
{"external_id": null}       // clears it — null IS a valid external identifier
```

`external_id` is not a special case. It is the only field whose value domain includes null,
so it is the only field where "assign null" means anything. Every other field rejects null
for the same reason it would reject `{"enabled": "yes"}`: wrong type.

**To clear a field, give it its own empty value** — `""` for a slug, `{}` for metadata.
Only `external_id` is cleared with null.

## Migrating

Two changes can break existing callers. Both were accidents being corrected.

**1. Nulls that used to be silently ignored now fail.**

```jsonc
{"name": null, "enabled": true}   // was: 200, only enabled changed
                                  // now: 422
{"enabled": true}                 // do this instead — it is what you meant
```

If you were sending nulls to mean "skip this field", omit the field. If you built request
bodies by serializing a partial object with null holes, filter them out before sending.

**2. An external-ID conflict returns 409, not 422.**

```python
# before
except HTTPError as e:
    if e.status == 409: ...   # slug conflict
    if e.status == 422: ...   # external-id conflict, among other things

# after — both uniqueness conflicts are 409, consistently
except HTTPError as e:
    if e.status == 409: ...   # slug OR external-id conflict
```

## Where the 422 comes from

taxomesh ships no HTTP server, so it does not produce the 422 itself. It guarantees the
request model **refuses to be constructed** with an invalid value:

```python
from taxomesh.contrib.api.schemas import UpdateItemRequest

UpdateItemRequest.model_validate({"name": None})   # raises ValidationError
```

Any framework that validates request models turns that into a 422 for you. With FastAPI,
declaring `body: UpdateItemRequest` on the route is all that is required — no error-handling
code. `errors.to_tuple` is not involved and deliberately does not accept these errors: it
maps taxomesh's own exceptions, and a request that never became a request is not one of them.

## Verifying the behavior

Every claim above is executable. Presence, not value, drives the update:

```python
from taxomesh.contrib.api.schemas import UpdateItemRequest

UpdateItemRequest.model_validate({"name": "x"}).model_dump(exclude_unset=True)
# {'name': 'x'}          -> service is told to set the name

UpdateItemRequest.model_validate({}).model_dump(exclude_unset=True)
# {}                     -> service is told nothing; nothing changes

UpdateItemRequest.model_validate({"external_id": None}).model_dump(exclude_unset=True)
# {'external_id': None}  -> service is told to clear it
```

The published schema is truthful about all of this — `name` is advertised as a string, not
as a nullable string, so a generated client will reject a null before the request is even
sent:

```python
UpdateItemRequest.model_json_schema()["properties"]["name"]
# {'default': '', 'title': 'Name', 'type': 'string'}
```

## Running the tests

Behavior is identical across the in-memory, JSON, YAML, and Django backends, and is proven
so rather than assumed:

```bash
pytest tests/contrib/test_api_schemas.py tests/contrib/test_api_handlers.py \
       tests/contrib/test_api_errors.py
pytest tests/service/            # backend-parametrized parity; run the whole directory
```

Run the whole `tests/service/` directory, not the parity file alone: the Django
parametrization needs `test_parity_fixture.py` to run first, or the Django backend reports
"no such table".
