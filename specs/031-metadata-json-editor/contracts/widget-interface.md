# Contract: JsonEditorWidget

**Branch**: `031-metadata-json-editor` | **Date**: 2026-03-14

This is an internal Django admin widget. It has no public HTTP API. The contract documented here is the **Python widget interface** consumed by `CategoryModelAdmin` and `ItemModelAdmin`.

---

## Construction

```python
JsonEditorWidget(height: str = "300px")
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `height` | `str` | `"300px"` | CSS height of the Ace editor div. Any valid CSS length string. |

---

## `render(name, value, attrs, renderer)` contract

**Inputs**:

| Parameter | Type | Notes |
|---|---|---|
| `name` | `str` | HTML `name` attribute for the hidden textarea (form submission key) |
| `value` | `object \| None` | Current field value — Python `dict`/`list`/scalar, or `None`, or already-serialised JSON string |
| `attrs` | `dict[str, Any] \| None` | HTML attribute overrides; must include `"id"` when called by Django (guaranteed for ModelAdmin) |
| `renderer` | `object \| None` | Django form renderer (passed through; not used) |

**Output**: Safe HTML string containing:
1. `<textarea name="{name}" id="{id}" style="display:none">{json_value}</textarea>` — hidden; carries the submitted value.
2. `<div id="ace__{id}" style="width:100%;height:{height};border:1px solid #ccc"></div>` — Ace mount point.
3. `<script>(function(){ ... })();</script>` — IIFE initialising the Ace instance, syncing it to the textarea, and installing the submit guard.

**Value normalisation**:
- `None` → `"{}"`
- `dict` / `list` / scalar → `json.dumps(value, indent=2, ensure_ascii=False)`
- Already a `str` → used as-is (assumed to be valid JSON from a prior round-trip)

---

## `class Media` contract

```python
class Media:
    js = (ACE_EDITOR_CDN_URL,)   # one CDN URL; Django deduplicates across instances
```

No CSS declared. Ace's default styling is inline.

---

## Admin Integration Contract

Both `CategoryModelAdmin` and `ItemModelAdmin` declare:

```python
formfield_overrides = {
    models.JSONField: {"widget": JsonEditorWidget},
}
```

This applies `JsonEditorWidget` to **all** `JSONField` columns on those two models' admin change forms. Per the spec, the affected fields are:
- `CategoryModel.metadata`
- `ItemModel.metadata`

No other admin classes are modified.
