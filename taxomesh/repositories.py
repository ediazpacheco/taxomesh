"""The repository classes of the three shipped storage backends, for a ``TaxomeshService``.

::

    from taxomesh import TaxomeshService
    from taxomesh.repositories import YamlRepository

    service = TaxomeshService(YamlRepository("catalog.yaml"))

Importing this module imports no Django. ``DjangoRepository`` needs the ``django`` extra only when
the caller constructs it. When Django is not installed, its error says so. A caller can also import
the module of each adapter on its own.
"""

from taxomesh.adapters.repositories.django_repository import DjangoRepository
from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.adapters.repositories.yaml_repository import YamlRepository

__all__ = ["DjangoRepository", "JsonRepository", "YamlRepository"]
