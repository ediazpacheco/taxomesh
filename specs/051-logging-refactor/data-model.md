# Data Model: 051-logging-refactor

No new domain entities or storage changes. This feature is a pure behavioural
change to existing logging calls and a one-time library initialisation.

## Affected Code Paths

### `taxomesh/__init__.py`

One new line at module level (after imports):

```
logging.getLogger("taxomesh").addHandler(logging.NullHandler())
```

### `taxomesh/application/service.py` — `list_related_items_for_sources`

The warning call at the dangling-link check changes from:

```
Dangling item relation link skipped:
  source_item_id={uuid}
  target_item_id={uuid}
  relation_type={str}
```

to:

```
list_related_items_for_sources: dangling relation skipped —
  source: {str(source_item) or safe fallback}
  target: <orphaned item {target_uuid}>
  relation_type: {str}
```

`source_item` is retrieved via `item_map.get(link.source_item_id)`. If absent
(defensive edge case), the source slot uses `<unknown source item {uuid}>`.
The `str()` call is wrapped in a `try/except Exception` for safety.

### `taxomesh/contrib/django/admin.py` — `_resolve_linked_url`

Two `logger.debug(...)` calls become `logger.warning(...)`. Message text
is unchanged; only the log level changes.

## Test Surface

| File | Change |
|---|---|
| `tests/test_logging.py` | New: NullHandler present after import; logger hierarchy `"taxomesh.*"`; no timestamp in message text |
| `tests/service/test_service_list_related_resilience.py` | Update: assert new message fields (method name, `str(source)`, orphaned label) |
| `tests/contrib/django/test_admin_logging.py` | New: assert WARNING emitted for missing setting key and for URL resolution failure |
