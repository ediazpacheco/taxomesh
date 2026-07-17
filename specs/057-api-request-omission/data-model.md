# Phase 1 Data Model: API Request Omission and Explicit-Null Semantics

**Feature**: `057-api-request-omission` | **Date**: 2026-07-16

This feature adds no entity and changes no stored field. It corrects the *request* schemas
so each field's accepted value domain matches the stored field's value domain, as FR-003
requires. The table below is therefore the whole design: everything else is a consequence.

## Stored value domains (authoritative, from the domain models)

Introspected from `taxomesh.domain.models`, not transcribed from memory:

| Entity | Field | Stored type | Stored default | Null in domain? |
|---|---|---|---|---|
| `Item` | `name` | `str` | `""` | no |
| `Item` | `external_id` | `str \| None` | `None` | **yes** |
| `Item` | `slug` | `str` | `""` | no |
| `Item` | `enabled` | `bool` | `True` | no |
| `Item` | `metadata` | `dict[str, Any]` | — | no |
| `Category` | `name` | `str` | required | no |
| `Category` | `description` | `str` | `""` | no |
| `Category` | `external_id` | `str \| None` | `None` | **yes** |
| `Category` | `slug` | `str` | `""` | no |
| `Category` | `enabled` | `bool` | `True` | no |
| `Category` | `metadata` | `dict[str, Any]` | — | no |
| `Tag` | `name` | `str` | required | no |

**`external_id` is the only nullable field on either entity.** This is the fact FR-008 is
scoped to — not the field's name. It is why null means "clear" for that field and is invalid
everywhere else, and it is the whole of the asymmetry a reader might otherwise mistake for a
special case.

## Request field domains — required end state

A request field's accepted domain must equal its stored field's domain (FR-003). Optionality
is expressed by the presence of a default, never by widening the type. The default is inert:
handlers forward only fields the caller set, so it is never read.

### `UpdateItemRequest`

| Field | Current | Required | Change |
|---|---|---|---|
| `name` | `Annotated[str, …] \| None = None` | `Annotated[str, …] = ""` | drop `\| None` |
| `external_id` | `Annotated[str, …] \| None = None` | `Annotated[str \| None, …] = None` | move `\| None` **inside** `Annotated` — the field stays nullable; the annotation now says the *value* may be null rather than that the field may be absent |
| `enabled` | `bool \| None = None` | `bool = True` | drop `\| None` |
| `slug` | `Annotated[str, …] \| None = None` | `Annotated[str, …] = ""` | drop `\| None` |
| `metadata` | `dict[str, Any] \| None = None` | `dict[str, Any] = Field(default_factory=dict)` | drop `\| None` |

### `UpdateCategoryRequest`

| Field | Current | Required | Change |
|---|---|---|---|
| `name` | `Annotated[str, …] \| None = None` | `Annotated[str, …] = ""` | drop `\| None` |
| `description` | `Annotated[str, …] \| None = None` | `Annotated[str, …] = ""` | drop `\| None` |
| `slug` | `Annotated[str, …] \| None = None` | `Annotated[str, …] = ""` | drop `\| None` |
| `metadata` | `dict[str, Any] \| None = None` | `dict[str, Any] = Field(default_factory=dict)` | drop `\| None` |
| `external_id` | **absent** | `Annotated[str \| None, Field(max_length=MAX_EXTERNAL_ID_STR_LENGTH)] = None` | **new** (FR-013) |
| `enabled` | **absent** | `bool = True` | **new** (FR-014) |

### `UpdateTagRequest`

| Field | Current | Required | Change |
|---|---|---|---|
| `name` | `Annotated[str, …] \| None = None` | `Annotated[str, …] = ""` | drop `\| None` |

### Create requests — no change

`CreateItemRequest`, `CreateCategoryRequest`, and `CreateTagRequest` already satisfy the
rule and are listed only to record that this was verified, not assumed. Each expresses
optionality with a real default and never widens a non-nullable field, so each already
rejects a null `name` or `slug` and accepts a null `external_id`. FR-011 locks this in with
regression tests; the spec's Assumptions forbid budgeting implementation effort here.

## Inert default selection

Each inert default mirrors its stored field's default (`""`, `True`, `{}`). The value is
unreachable by construction, so this is a readability convention rather than a behavioral
one — but it means a reader comparing the request schema to the domain model sees agreement
rather than an arbitrary placeholder, and it keeps the blast radius smallest if
presence-filtering were ever dropped. Principle X's carve-out for self-evident literals
covers these values explicitly.

`Category.name` is required in the domain but takes an inert `""` default in the request,
because a partial update must permit omitting the name. This is not a domain-versus-request
divergence: the *domain* of `name` is `str` in both, which is what FR-003 constrains. What
differs is optionality, which FR-003 requires be expressed independently of the domain —
and this is precisely that separation working.

## The presence/value matrix

The complete behavioral contract, derived from the single rule with no field-specific
branches. SC-004 requires a table-driven test enumerating exactly this per field.

| Field kind | Omitted | Present, valid value | Present, `null` |
|---|---|---|---|
| Non-nullable (`name`, `slug`, `enabled`, `description`, `metadata`) | stored value untouched | assigned | **rejected** — null is outside the field's domain |
| Nullable (`external_id`) | stored value untouched | assigned | **cleared** — null is inside the field's domain |

Clearing a non-nullable field, where meaningful, uses that field's own empty value from
inside its domain: `slug` is cleared with `""`, `metadata` with `{}`. No field is cleared
with null unless null is one of its values.

## Entities

No new entity. No migration. No repository change. The four backends are touched only as
verification targets for FR-016.
