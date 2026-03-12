# Configuration (`taxomesh.toml`)

`taxomesh.toml` is optional. If present, `TaxomeshService()` reads it from the current
working directory and uses it to select and configure the storage backend automatically.

## YAML backend

```toml
[repository]
type = "yaml"
path = "data/taxomesh.yaml"
```

## JSON backend

```toml
[repository]
type = "json"
path = "data/taxomesh.json"
```

## Django backend

```toml
[repository]
type = "django"
using = "default"
```

See also: [`taxomesh.toml.example`](../taxomesh.toml.example) for a ready-to-use template.

← [Back to README](../README.md)
