# Contract: `errors.to_tuple`

**Feature**: 059-safe-error-bodies | **Module**: `taxomesh.contrib.api.errors`

Constitution principle IX names `to_tuple` the sole error-mapping primitive. This
contract records what it guarantees after this feature. The signature and the status
mapping are unchanged from spec 057; only the 500 bodies and the logging behavior are
new.

## Signature

```python
def to_tuple(exc: TaxomeshError) -> tuple[int, dict[str, Any]]: ...
```

Unchanged (FR-008). The body always carries exactly one key, `detail`, of type `str`.

## Public names

| Name | Type | Meaning |
|---|---|---|
| `to_tuple` | function | The mapping primitive. |
| `GENERIC_SERVER_ERROR_DETAIL` | `Final[str]` | The only `detail` value a client ever receives for a 500. Importable so consumers can compare against it without copying the literal (FR-004). |

## Mapping

| Exception | Status | `detail` | Logs? |
|---|---|---|---|
| `TaxomeshDuplicateSlugError` | 409 | `str(exc)` | no |
| `TaxomeshExternalIdConflictError` | 409 | `str(exc)` | no |
| `TaxomeshNotFoundError` (and subclasses) | 404 | `str(exc)` | no |
| `TaxomeshValidationError` (and remaining subclasses) | 422 | `str(exc)` | no |
| `TaxomeshRepositoryError` | 500 | `GENERIC_SERVER_ERROR_DETAIL` | yes |
| any other `TaxomeshError` | 500 | `GENERIC_SERVER_ERROR_DETAIL` | yes |

Branch order is significant and unchanged: the two 409 subclasses are tested before
their `TaxomeshValidationError` parent, and `TaxomeshNotFoundError` before the parent
`TaxomeshError` fallback.

`TaxomeshConfigError` and `TaxomeshRootCategoryError` match no branch and therefore take
the fallback row — 500, redacted, logged.

## Guarantees

1. **G1 — No status changes.** Every exception maps to the same status as before this
   feature (FR-009).
2. **G2 — 4xx bodies are byte-identical to before.** `detail` is `str(exc)` exactly
   (FR-006).
3. **G3 — 5xx bodies are constant.** `detail is GENERIC_SERVER_ERROR_DETAIL` — the same
   object for every 500, independent of the exception, its args, its cause, and its
   traceback (FR-001, FR-002, FR-003).
4. **G4 — 5xx is logged exactly once.** One record on `taxomesh.contrib.api.errors` at
   `ERROR`, carrying the exception with traceback (FR-005).
5. **G5 — 4xx is never logged.** Client errors produce no records (FR-007).
6. **G6 — Silence by default.** An application that configures no logging sees no
   output; the `NullHandler` on the `taxomesh` logger covers this (SC-005).
7. **G7 — Total.** Every `TaxomeshError` subclass gets a status and a body; the function
   introduces no new raising path (FR-010).

## Compatibility

**Breaking for anyone who read the 500 `detail`.** A client that displayed it, logged it,
parsed it, or branched on its text now sees a fixed string. The status code was already
the contract; the text never was, but it was available, so this is a behavior change and
gets a changelog entry.

Not breaking for 4xx consumers — G2 keeps those bodies identical.

## Verification

Owned by `tests/contrib/test_api_errors.py`:

- The existing exhaustiveness guard (`EXPECTED_STATUS` + `_all_taxomesh_error_types`)
  proves G1 stays total over every subclass defined in `taxomesh.exceptions`.
- A marker-planting test proves G3 by absence, not just by equality (see research §8).
- `caplog`-based tests prove G4 and G5.
