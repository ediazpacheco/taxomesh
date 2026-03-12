# Configuration (`taxomesh.toml`)

`taxomesh.toml` is optional. If present, `TaxomeshService()` reads it from the current
working directory and uses it to select and configure the storage backend automatically.

This is the simplest way to keep application code free of repository wiring, especially
when you want the same code to run against different backends in different environments.

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
