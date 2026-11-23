# Configuration (`taxomesh.toml`)

`taxomesh.toml` is optional. It keeps the choice of storage out of application code, so the same
code runs on another backend in another environment. `TaxomeshService()` reads the one in the
working directory, or the one `config_path` names, and builds the repository it describes. When that
file does not exist, named or not, or has no `[repository]` section, the repository is a YAML file
at `data/taxomesh.yaml`. The service uses a repository that you pass as it is, and reads no file.

```toml
[taxomesh]
name = "catalog"             # optional; reported as svc.info.config_name

[repository]
type = "yaml"                # "yaml", "json" or "django"
path = "data/taxomesh.yaml"  # by default data/taxomesh.yaml, or data/taxomesh.json for json
```

A relative `path` starts from the working directory, not from the directory of `taxomesh.toml`.
`[taxomesh]` and `[repository]` must be tables, and `type`, `path`, `using` and `name` strings:
anything else among them raises `TaxomeshConfigError`. taxomesh ignores every other key and table,
so a misspelled `pth` gives the default path.

The Django backend names a database alias instead of a path, `"default"` unless given:

```toml
[repository]
type = "django"
using = "default"
```

The `taxomesh` command sets Django up itself, from the settings module that `DJANGO_SETTINGS_MODULE`
names ([CLI reference](cli.md)).

`taxomesh --show-config` prints the configuration in effect as TOML, which a file can hold as it
is. It shows the accepted values of `type`, and the default of each key that it prints. Redirect it to a
new file, such as `taxomesh --show-config > taxomesh.toml.new`. Never redirect it to the
`taxomesh.toml` in use. The shell empties that file before taxomesh reads it, and the file then
holds only the defaults.
[`taxomesh.toml.example`](../taxomesh.toml.example) is a ready-to-use template.

← [Back to README](../README.md)
