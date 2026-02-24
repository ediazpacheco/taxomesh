# Research: YAML Repository

**Branch**: `007-yaml-repository` | **Date**: 2026-02-24

## R-001: YAML Library Choice

**Decision**: `pyyaml` with `yaml.safe_load` / `yaml.safe_dump` exclusively.

**Rationale**: pyyaml is already declared as an optional dependency in `pyproject.toml` (`pyyaml>=6.0`). Promoting it to required avoids adding a new library. `safe_*` variants prevent arbitrary Python object deserialization from untrusted YAML files (a critical security property — bare `yaml.load` / `yaml.dump` allow tag injection).

**Alternatives considered**:
- `ruamel.yaml` — preserves comments and round-trips cleanly, but adds complexity and is not already in the dependency tree.
- `strictyaml` — enforces schema validation at parse time, but is niche and introduces a new heavy dependency.
- Bare `yaml.load` / `yaml.dump` — rejected; unsafe without explicit Loader; mypy-flagged.

---

## R-002: Serialization Strategy — Pydantic → YAML

**Decision**: On write: call `model.model_dump(mode="json")` on every Pydantic model to obtain plain JSON-serializable dicts (UUIDs become strings, datetimes become ISO strings), then pass the full data dict to `yaml.safe_dump`. On read: call `yaml.safe_load` to get plain Python dicts, then call `Model.model_validate(dict)` per record — the exact same code path as `JsonRepository`.

**Rationale**: `yaml.safe_dump` of a raw Pydantic model or UUID object produces Python-tagged YAML (`!!python/object:uuid.UUID ...`) which is unreadable and non-portable. Using `model_dump(mode="json")` first ensures only plain strings, ints, lists, and dicts enter the YAML layer — output is clean and human-readable.

**Alternatives considered**:
- Custom YAML representers for UUID/datetime — works, but adds maintenance burden and complexity.
- Storing only JSON-primitive types and relying on repr() — loses type fidelity.

**YAML dump options**:
```python
yaml.safe_dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
```
- `default_flow_style=False` → block style (multi-line, readable)
- `allow_unicode=True` → category names in non-ASCII scripts render correctly
- `sort_keys=False` → preserves insertion order (categories before items etc.)

---

## R-003: mypy --strict Compatibility

**Decision**: Add `types-PyYAML` to `[project.optional-dependencies] dev` in `pyproject.toml`.

**Rationale**: pyyaml does not ship a `py.typed` marker or inline type stubs. Without `types-PyYAML`, all `yaml.*` calls resolve to `Any` and mypy strict emits implicit-Any errors. With stubs:
- `yaml.safe_load(stream)` → `Any` (must be explicitly annotated at the call site)
- `yaml.safe_dump(data, ...)` → `str` (when no stream argument)

**Implementation note**: The `_load()` method must annotate the `safe_load` return:
```python
raw: Any = yaml.safe_load(self._path.read_text(encoding="utf-8"))
if not isinstance(raw, dict):
    ...
data: dict[str, Any] = raw
```
This pattern (used identically in `JsonRepository._load()`) satisfies mypy strict without `# type: ignore`.

---

## R-004: TaxomeshService Default Repository — No Change (Principle II Compliance)

**Decision**: `TaxomeshService()` (called without a `repository` argument) continues to default to `JsonRepository`. Only the CLI `build()` factory in `taxomesh/adapters/cli/config.py` changes its default from `json` → `yaml`.

**Rationale**: Constitution Principle II explicitly states: "If no repository is provided, it defaults to `JsonRepository`." Changing this would require a MAJOR constitution amendment. The spec's FR-002 targets the CLI default specifically ("the CLI when no taxomesh.toml config file is present"), not the library API default.

**Trade-off**: A developer who calls `TaxomeshService()` directly without a repository still gets `JsonRepository`. This is a known asymmetry between the library API and the CLI. It is acceptable because:
1. The CLI is the primary end-user surface.
2. Library users constructing `TaxomeshService()` should explicitly choose their backend.
3. The constitution's intent (stable public API) is preserved.

**Documentation impact**: README must clearly note that `TaxomeshService()` still defaults to `JsonRepository`; to use YAML from Python code, pass `YAMLRepository` explicitly.

---

## R-005: Constitution Amendment — pyyaml Dependency Status

**Decision**: Update `.specify/memory/constitution.md` Toolchain section to reflect that pyyaml is now a required runtime dependency (not optional).

**Rationale**: The constitution's Toolchain table currently reads: "pyyaml is optional (`pip install taxomesh[yaml]`)". After this feature, pyyaml ships with every install. Leaving the constitution inconsistent with the codebase violates its role as authoritative documentation.

**Amendment type**: PATCH (clarification of dependency status; no architectural change).

**Steps**: Update the constitution Toolchain table entry for pyyaml. Remove the `[yaml]` extras reference. Bump constitution version from 1.2.1 → 1.2.2.

---

## R-006: YAML On-Disk File Schema

**Decision**: Mirror the JSON schema exactly — same top-level keys, same UUID-as-string key format, same Pydantic model dict shapes. Example:

```yaml
categories:
  3fa85f64-5717-4562-b3fc-2c963f66afa6:
    category_id: 3fa85f64-5717-4562-b3fc-2c963f66afa6
    name: Animals
    description: null

items:
  b1c2d3e4-...:
    item_id: b1c2d3e4-...
    external_id: lion
    enabled: true
    description: null

tags: {}

item_tag_links: []

category_parent_links:
- category_id: 3fa85f64-...
  parent_category_id: 00000000-...  # root
  sort_index: 0

item_parent_links:
- item_id: b1c2d3e4-...
  category_id: 3fa85f64-...
  sort_index: 0
```

**Rationale**: Using the identical schema as JSON means the two adapters are interchangeable by format conversion only. The same Pydantic `model_validate` calls work for both.

---

## R-007: Atomic Write Pattern

**Decision**: Identical to `JsonRepository._flush()`: use `tempfile.mkstemp(dir=self._path.parent, suffix=".tmp")`, write and `os.fsync`, then `os.replace(tmp_path, self._path)`.

**Rationale**: The pattern is already proven in the codebase. `os.replace` is POSIX-atomic. No reason to deviate.

---

## R-008: `examples/taxomesh_example.yaml` — Not in Wheel

**Decision**: The file lives at `examples/taxomesh_example.yaml` in the repo root. It is excluded from the installed wheel (hatchling does not include `examples/` by default). No `pyproject.toml` `[tool.hatch.build]` changes needed.

**Rationale**: The file is a documentation and onboarding artifact. Shipping it in the wheel would add unnecessary size without runtime benefit. The README links to it in the repository.
