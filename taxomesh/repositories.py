"""The storage backends a ``TaxomeshService`` can be given.

::

    from taxomesh import TaxomeshService
    from taxomesh.repositories import YamlRepository

    service = TaxomeshService(YamlRepository("catalog.yaml"))

Importing this module imports no Django. ``DjangoRepository`` needs the ``django`` extra only when
it is constructed, and its error says so when Django is not installed. The module of each adapter
can also be imported on its own.
"""

from taxomesh.adapters.repositories.django_repository import DjangoRepository
from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.adapters.repositories.yaml_repository import YamlRepository

__all__ = ["DjangoRepository", "JsonRepository", "YamlRepository"]
