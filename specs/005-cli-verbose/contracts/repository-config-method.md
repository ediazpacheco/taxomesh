# Repository Contract: `get_config_summary()`

**Feature**: 005-cli-verbose  
**Date**: 2026-02-23

---

## Protocol Method (19th)

### Location
`taxomesh/ports/repository.py` — `TaxomeshRepositoryBase` Protocol

### Signature
```python
def get_config_summary(self) -> str: ...
```

### Contract

| Property           | Requirement                                                         |
|--------------------|---------------------------------------------------------------------|
| Return type        | `str`                                                               |
| Empty string       | FORBIDDEN — must return a non-empty string                          |
| Raises             | FORBIDDEN — must never raise under any circumstances                |
| Secrets/passwords  | FORBIDDEN — implementation must omit or mask sensitive values       |
| Newlines           | Allowed but not required; single-line preferred for display clarity |

### `JsonRepository` Implementation Contract

Returns `str(self._path)` — the path as supplied at construction.  
No secrets possible (file path only).

### Future Implementation Guidelines

Any new repository backend MUST:
1. Return a non-empty string.
2. Include enough information for a developer to identify the target store
   (e.g., hostname + database name for SQL, endpoint URL for cloud storage).
3. Exclude: passwords, API keys, tokens, connection string secrets.
4. Example for a hypothetical SQLite backend: `"sqlite:///path/to/db.sqlite3"`
5. Example for a hypothetical PostgreSQL backend: `"postgresql://user@host:5432/dbname"`
   (password omitted).
