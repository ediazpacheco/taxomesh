# Contract: Public Request Semantics for `taxomesh.contrib.api`

**Feature**: `057-api-request-omission` | **Date**: 2026-07-16
**Status**: Supersedes parts of `028-contrib-api/contracts/api-contract.md` — see Lineage.

## Lineage and supersession

This document is the current word on three points of the public request contract. It does
**not** amend `028-contrib-api`, `041-unique-external-id`, or `043-clear-external-id`: those
directories are an append-only historical record and remain untouched by design (FR-019).
A reader of 028 alone will still find the superseded text; that is the cost of an immutable
record and is accepted deliberately. This follows the precedent 041 set when it recorded its
supersession of 013, 021, and 032 in its own Dependencies rather than by editing theirs.

Superseded from 028, and **only** these three points:

| Point | 028 said | This contract says |
|---|---|---|
| Item-creation external ID | `external_id: Annotated[str, …] = ""` | `Annotated[str \| None, …] = None`. Empty string is not an absence marker; absence is null. |
| Partial-update null handling | "handlers apply only non-`None` values" (FR-005) | A present field is assigned or rejected. Null is accepted only where the field's value domain includes it. |
| External-ID conflict status | *(unstated — the error postdates 028)* | 409, identically to the slug conflict. |

Everything else in 028's contract stands unchanged and is not restated here: the
framework-agnostic rule, handler signatures, `TaxomeshService` as the first positional
argument, domain models returned directly, the `{"detail": str(exc)}` body shape, and the
stability guarantee as applied to every point not listed above.

**Note on the stability guarantee.** 028 guarantees the `to_tuple` mapping and states that
breaking changes require a major version bump. The third point above falls inside that
guarantee. It is superseded knowingly, not overlooked: the project is in a pre-1.0 alpha
series, both affected behaviors were accidents rather than decisions, and recording the
supersession here is the alternative to leaving the guarantee quietly false.

## The rule

> **An omitted field carries no instruction. A present field means "assign exactly this
> value", and is rejected if that value is not valid for that field.**

This holds for every public request schema, creation and partial update alike, with no
field-specific exceptions. Two facts about a field are independent and must not be
conflated:

- **May it be absent?** A property of the request envelope. Every partial-update field may.
- **May it be null?** A property of the field's value domain. Only `external_id` may.

## Guaranteed behavior

### Presence

| Caller sends | Guarantee |
|---|---|
| field omitted | the stored value is not read, not written, and not touched |
| `{}` (no fields) | valid; a no-op on every stored value |
| unknown field | ignored, not rejected (unchanged from 028) |

### Values

| Caller sends | `name`, `slug`, `description`, `enabled`, `metadata` | `external_id` |
|---|---|---|
| a valid value | assigned | assigned |
| `null` | **rejected** | **cleared** |
| absent | unchanged | unchanged |

Clearing, where meaningful, uses a value from inside the field's own domain: `slug` is
cleared with `""`, `metadata` with `{}`. Only `external_id` is cleared with null, because
only `external_id` has null in its domain.

### Errors

| Condition | Surfaced as | Who produces it |
|---|---|---|
| a field carries a value outside its domain | a validation error raised when the request is constructed | **the consuming framework.** taxomesh guarantees the request refuses to be built; mapping that to a status is the framework's step, and under a framework that validates request models automatically it is free. |
| external identifier already held by another record | `TaxomeshExternalIdConflictError` → **409** | `errors.to_tuple` |
| slug already held by another record | `TaxomeshDuplicateSlugError` → **409** | `errors.to_tuple` |
| other validation failure from the service | `TaxomeshValidationError` → 422 | `errors.to_tuple` |

`errors.to_tuple` remains the sole error-mapping primitive and its signature is unchanged:
it accepts a `TaxomeshError` and nothing else. Request-validation errors are outside the
taxomesh exception hierarchy by design and MUST NOT be added to it (FR-005).

## Stability of this contract

The rule is the contract. Individual field types follow from it mechanically, so adding a
field requires no new specification:

- a **non-nullable** field rejects null with no new logic;
- a **nullable** field accepts null as "clear" with no new logic.

A future field that needs to be clearable should be given a domain that contains an empty
value, and that value clears it. Making a field nullable purely to express that it may be
omitted is the defect this contract exists to prevent, and is prohibited by FR-003.

## Consumer-visible breaking changes

Both are corrections of unintended behavior; neither has a known dependent.

1. **`{"name": null}` and equivalents now fail validation** instead of returning success and
   changing nothing. A caller relying on null-as-no-op must omit the field instead — which
   is what it meant all along.
2. **An external-ID conflict now returns 409** instead of 422. A caller branching on 422 for
   this case must branch on 409, alongside the slug conflict it already handles there.
