# Configuration (`taxomesh.toml`)

`taxomesh.toml` is optional. It keeps the choice of storage out of application code, so the same
code runs on another storage backend in another environment. `TaxomeshService()` reads the one in
the working directory, or the one `config_path` names, and builds the repository it describes.
With no file, or a file with no `[repository]` section, the repository is a YAML file at
`data/taxomesh.yaml`. A repository passed to the service is used as given, and no file is read.

```toml
[taxomesh]
name = "catalog"             # optional; reported as svc.info.config_name

[repository]
type = "yaml"                # "yaml", "json" or "django"
path = "data/taxomesh.yaml"  # by default data/taxomesh.yaml, or data/taxomesh.json for json
```

A relative `path` is resolved from the working directory, not from the directory of
`taxomesh.toml`.

The Django backend names a database alias instead of a path, `"default"` unless given:

```toml
[repository]
type = "django"
using = "default"
```

`taxomesh --show-config` prints the configuration in effect, each key with its accepted values
and its default. [`taxomesh.toml.example`](../taxomesh.toml.example) is a ready-to-use template.

← [Back to README](../README.md)
