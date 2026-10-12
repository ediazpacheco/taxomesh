"""The typed read models that describe a service and its repository.

:class:`RepositoryInfo` describes a repository. Repositories report different facts: a file
repository has a path, and a Django repository has a database alias. So the model names the facts
that every repository has, and keeps a small typed mapping for the others.

:class:`TaxomeshInfo` describes a service. It names every field, and contains the model of the
repository instead of a free-form dict. So neither model uses ``Any``.
"""

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RepositoryInfo:
    """What a repository reports about itself.

    Frozen and slotted, because it is a read model and not an entity: the caller holds a snapshot,
    and a snapshot that accepted writes would suggest that the writes go somewhere. So it is a
    standard dataclass and not a Pydantic model, which has no ``__slots__``.

    It is not the type that a service reports about itself. A service reports its version and its
    corpus sizes; a repository reports where its data is. One class for both would contain an
    object of its own class.

    Attributes:
        backend: The class name of the repository, such as ``"JsonRepository"``.
        path: The path of the storage file, or ``None`` for a backend that has no file: Django and
            the in-memory test backend report ``None``. Here ``None`` is an answer, not an absent
            value: the backend has no file.
        diagnostics: The facts of one backend that other backends do not have, such as Django's
            ``{"database_alias": "default"}``. Empty on the file repositories, whose only fact is
            the path above. The value type is narrowed, so that the model does not use ``Any``.
    """

    backend: str
    path: str | None
    diagnostics: Mapping[str, str | int | None]


@dataclass(frozen=True, slots=True)
class TaxomeshInfo:
    """What a ``TaxomeshService`` reports about itself.

    Frozen and slotted, and a standard dataclass, for the same reasons as :class:`RepositoryInfo`.
    The corpus sizes show why. They are true at one moment: the next create, update or delete of a
    category or an item through the service drops the corpus of that kind, and changes its size.
    An object that accepted writes would suggest that it changes with the service; it does not.

    ``repository`` contains the model of the repository, and this model does not copy its fields:
    the name and the path of the backend are ``repository.backend`` and ``repository.path``.

    Attributes:
        version: The version of the installed distribution.
        config_name: The name that the ``taxomesh.toml`` of this service declares, or ``None``
            when the service was given a repository, found no config file, or read one that
            declares no name.
        item_corpus_size: How many items the held search corpus holds, or ``None`` when no corpus
            is held: it was not built, its lifetime (the service's ``cache_ttl``) ended, or a
            create, update or delete of an item through this service dropped it. ``0`` means that
            the corpus is built and empty. That is a different state, so the type is ``int | None``.
        category_corpus_size: The same, for the category corpus, which a create, update or delete
            of a category through this service drops.
        repository: What the repository of the service reports about itself.
    """

    version: str
    config_name: str | None
    item_corpus_size: int | None
    category_corpus_size: int | None
    repository: RepositoryInfo
