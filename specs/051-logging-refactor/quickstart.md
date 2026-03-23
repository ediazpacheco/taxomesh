# Quickstart: taxomesh Logging

## How taxomesh emits logs

taxomesh uses Python's standard `logging` module. All records are emitted under
the `"taxomesh"` logger hierarchy:

| Logger name | Source |
|---|---|
| `taxomesh.application.service` | Service-layer warnings (e.g. dangling relation links) |
| `taxomesh.contrib.django.admin` | Django admin integration warnings |

## Default behaviour

taxomesh registers a `NullHandler` on the `"taxomesh"` root logger at import
time. This means **no output appears by default** — the consuming application
decides where logs go and at what level.

## Capturing taxomesh logs in your application

```python
import logging

# Show all WARNING+ records from taxomesh on the console
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
logging.getLogger("taxomesh").addHandler(handler)
logging.getLogger("taxomesh").setLevel(logging.WARNING)
```

## Suppressing taxomesh logs

```python
import logging
logging.getLogger("taxomesh").setLevel(logging.ERROR)  # suppress WARNING; keep ERROR+
logging.getLogger("taxomesh").disabled = True           # suppress everything
```

## Timestamps

Timestamps are **not embedded** in taxomesh log messages. Use `%(asctime)s` in
your formatter (as shown above) to include them.

## Log records of interest

### `taxomesh.application.service` — WARNING

Emitted by `list_related_items_for_sources()` when `skip_on_error=True` and a
relation link points to a target item that no longer exists in the repository:

```
list_related_items_for_sources: dangling relation skipped — source: 🏷️ "Track A" (fea7bd50-... / track-a / EXT-001), target: <orphaned item 6a273a4c-...>, relation_type: 'music_by'
```

This means the target item was deleted from the repository while relation links
pointing to it still exist. Clean up the stale links to stop these warnings.

### `taxomesh.contrib.django.admin` — WARNING

Emitted by the Django admin URL-resolution helper when:

- A required settings key (e.g. `TAXOMESH_LINKED_ITEM_MODEL`) is not configured.
- URL resolution for the configured model fails (e.g. the model's admin URL is not registered).
