# Storage Backends (Repositories)

Any class implementing `TaxomeshRepositoryBase` can be used as a storage backend.
`TaxomeshRepositoryBase` is defined as a `typing.Protocol` — no inheritance is required
(structural typing / protocol-based compatibility).

## YAMLRepository

Default backend when no repository is configured. Uses atomic writes.

```python
from pathlib import Path
from taxomesh.adapters.repositories.yaml_repository import YAMLRepository

svc = TaxomeshService(repository=YAMLRepository(Path("data/taxomesh.yaml")))
```

## JsonRepository

File-backed JSON backend with atomic writes.

```python
from pathlib import Path
from taxomesh.adapters.repositories.json_repository import JsonRepository

svc = TaxomeshService(repository=JsonRepository(Path("data/taxomesh.json")))
```

## DjangoRepository

ORM-backed backend for Django projects.
If Django integration is already configured (see [Django integration](django-integration.md)),
use `DjangoRepository` directly when you want explicit repository wiring:

```python
from taxomesh.adapters.repositories.django_repository import DjangoRepository

svc = TaxomeshService(repository=DjangoRepository())
```

## Custom backends

Implement `TaxomeshRepositoryBase` (a `typing.Protocol`) to use any storage system —
remote APIs, databases, in-memory caches, etc. No base class to inherit from; just
implement the required methods.

← [Back to README](../README.md)
