# Data Model: Safe HTTP 500 response bodies

**Feature**: 059-safe-error-bodies | **Date**: 2026-09-09

This feature introduces no domain entity, no persisted field, and no migration. The
only structures involved are the transient value returned by `to_tuple` and the log
record it emits.

## Error body

The `dict[str, Any]` half of `to_tuple`'s return value.

| Key | Type | Value |
|---|---|---|
| `detail` | `str` | For 404/409/422, `str(exc)`. For 500, `GENERIC_SERVER_ERROR_DETAIL`. |

Shape is unchanged by this feature: one key, always present, always a string. What
changes is which value the 500 branches put in it.

Not persisted. Constructed per call, owned by the caller once returned.

## `GENERIC_SERVER_ERROR_DETAIL`

| Property | Value |
|---|---|
| Module | `taxomesh.contrib.api.errors` |
| Type | `Final[str]` |
| Value | `"An internal error occurred."` |
| Visibility | Public — no leading underscore, unlike the module's `_HTTP_*` constants |

Public because FR-004 requires consumers and tests to reference it rather than duplicate
the literal. The `_HTTP_*` status constants stay private: callers get status codes from
the return value, so they never need to name them.

## Log record

Emitted only on the two 500 branches.

| Attribute | Value |
|---|---|
| Logger | `taxomesh.contrib.api.errors` (via `__name__`) |
| Level | `ERROR` |
| Message | A static string — never interpolated with `str(exc)`, so the message itself carries no backend text |
| `exc_info` | The mapped exception, giving type, message, traceback, and chained cause |

The backend detail lives in `exc_info`, not in the message, which keeps the formatted
message safe for a handler that logs only `record.getMessage()`.

## State transitions

None. `to_tuple` is a pure mapping apart from the log emission; it holds no state
between calls and mutates nothing it is given.
