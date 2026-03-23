# Research: 050-related-items-resilience

**Status**: Complete — no unknowns required external research.

## Decision Log

### D-001: Parameter name

**Decision**: `skip_on_error: bool = True`
**Rationale**: Confirmed by user in `/speckit.clarify` session 2026-03-23. Matches
stdlib idiom (`shutil`, `zipfile`). Boolean flag with a safe-by-default value
(`True` = skip, don't raise).
**Alternatives considered**: `skip_if_error`, `raise_on_error` (inverse bool).

---

### D-002: Warning log fields

**Decision**: Include only `source_item_id`, `target_item_id`, `relation_type`.
**Rationale**: These three fields form the natural composite key of `ItemRelationLink`
and are sufficient to locate the broken record in any backend. Confirmed by user in
`/speckit.clarify` session 2026-03-23.
**Alternatives considered**: All five fields (`sort_index`, `metadata` included) — rejected
as they do not aid DB lookup and add noise to the log.

---

### D-003: Logger setup

**Decision**: Add `import logging` and `logger = logging.getLogger(__name__)` at
module level in `taxomesh/application/service.py`.
**Rationale**: `__name__` resolves to `taxomesh.application.service`, giving operators
fine-grained control via the Python logging hierarchy. No logger currently exists in
this module; it must be introduced.
**Alternatives considered**: Passing a logger as a parameter — rejected as over-engineering
for a single warning site; stdlib module logger is the conventional choice.

---

### D-004: Test file placement

**Decision**: New test file `tests/service/test_service_list_related_resilience.py`.
**Rationale**: `tests/service/test_service_item_relations.py` already exists and tests
the happy path. Creating a dedicated file keeps the new skip/log behaviour isolated and
follows the existing per-concern file convention in `tests/service/`.
**Alternatives considered**: Adding to existing `test_service_item_relations.py` — would
work but mixes concerns; new file preferred for clarity.
