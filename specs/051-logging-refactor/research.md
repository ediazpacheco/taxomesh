# Research: 051-logging-refactor

## Decision 1: NullHandler placement

**Decision**: Add `logging.getLogger("taxomesh").addHandler(logging.NullHandler())` to `taxomesh/__init__.py`.

**Rationale**: Python logging cookbook (PEP 282, official docs) states: "It is strongly advised that you do not add any handlers other than NullHandler to your library's loggers." The `__init__.py` is the natural composition root — it runs exactly once on import.

**Alternatives considered**:
- Adding it to `taxomesh/application/service.py` — wrong: only fires if the service module is imported; users importing only domain models would get "no handler" warnings.
- A dedicated `logging.py` module — unnecessary complexity for a two-line change.

---

## Decision 2: Improved dangling-link warning message structure

**Decision**: The warning message will include:
1. Method name: `list_related_items_for_sources`
2. Source item: call `str(source_item)` with a safe fallback if it raises
3. Target: `<orphaned item {uuid}>` — it is absent from the repo so no `str()` is possible
4. Relation type: unchanged

**Sample output**:
```
list_related_items_for_sources: dangling relation skipped — source: 🏷️ "Track A" (fea7bd50-... / track-a / EXT-001), target: <orphaned item 6a273a4c-...>, relation_type: 'music_by'
```

**Rationale**: The source item IS in `item_map` (loaded via `list_items()`), so `str()` is safe. The target is the orphan by definition — labelling it `<orphaned item {uuid}>` communicates this clearly without a second repository query.

**Safe fallback**: Wrap in `try/except Exception` and fall back to `f"<item {uuid} str() failed>"` if `str()` raises. This should never happen in practice but guards against future `__str__` bugs.

**Alternatives considered**:
- Including raw UUID fields as before — less actionable for the developer.
- Querying the repository for the target — would require a second DB call; the whole point is the target doesn't exist, so the query would fail anyway.

---

## Decision 3: DEBUG → WARNING for `_resolve_linked_url`

**Decision**: Upgrade both `logger.debug(...)` calls in `_resolve_linked_url` to `logger.warning(...)`.

**Rationale**:
- A missing settings key is a misconfiguration that the developer should know about. Silent `DEBUG` means it goes completely unnoticed in production.
- A URL resolution failure (exception path) is an operational error, not a routine diagnostic.
- Both are in an optional Django contrib module; the change has zero impact on non-Django users.

**Alternatives considered**:
- Keeping the exception path at `DEBUG` and only upgrading the missing-key case — both are worth surfacing; no reason to be asymmetric.

---

## Decision 4: Timestamps — no change needed

**Decision**: Do not embed timestamps in any log message string.

**Rationale**: Python's `LogRecord` already carries a `created` float (Unix timestamp) and an `asctime` attribute. Any consuming application can attach a `Formatter` with `%(asctime)s` to get timestamps. Embedding them in the message would duplicate information and override the consuming app's formatting choice.

**Action**: Document in `quickstart.md` how to configure timestamps.

---

## Decision 5: `getLogger(__name__)` — already compliant

**Decision**: No change needed. Both existing logger initialisations already use `logging.getLogger(__name__)`.

**Verified**: `taxomesh/application/service.py` and `taxomesh/contrib/django/admin.py` both use `__name__`. No hard-coded logger names found.

---

## Decision 6: Test approach

**Decision**: Use pytest's built-in `caplog` fixture throughout. No new test dependencies.

**Existing coverage**: `tests/service/test_service_list_related_resilience.py` already tests `caplog` against the dangling-link warning. It must be updated to assert the new message fields (method name, source str, orphaned label). New test file: `tests/test_logging.py` for the NullHandler and hierarchy. New tests in `tests/contrib/django/` for the WARNING upgrade.
