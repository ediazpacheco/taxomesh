"""The errors of the taxomesh library.

Every error class inherits ``TaxomeshError``, so the caller can catch one class, a branch of the
tree, or every error at once. Each class name starts with ``Taxomesh``, so the name tells which
library raised it.

Two branches are also standard exceptions, so a caller who knows only the standard library catches
them: a not-found error is a ``KeyError``, as for an absent key of a ``dict``, and a validation
error is a ``ValueError``, as ``int("x")`` raises.
"""


class TaxomeshError(Exception):
    """The base class of every taxomesh error."""


class TaxomeshNotFoundError(TaxomeshError, KeyError):
    """Raised when a key, a subject or a filter names an entity that is not stored.

    Also a ``KeyError``, so ``except KeyError`` catches it from ``coll[key]`` as it does from a
    ``dict``.
    """

    def __str__(self) -> str:
        """Return the message as written, without the quotes ``KeyError`` puts around it."""
        return BaseException.__str__(self)


class TaxomeshCategoryNotFoundError(TaxomeshNotFoundError):
    """Raised when an identifier names a category that is not stored."""


class TaxomeshItemNotFoundError(TaxomeshNotFoundError):
    """Raised when an identifier names an item that is not stored."""


class TaxomeshTagNotFoundError(TaxomeshNotFoundError):
    """Raised when an identifier names a tag that is not stored."""


class TaxomeshValidationError(TaxomeshError, ValueError):
    """Raised when a value of the right type is refused.

    Also a ``ValueError``, so ``except ValueError`` catches a refused value or argument.
    """


class TaxomeshCyclicDependencyError(TaxomeshValidationError):
    """Raised when a parent link would make a cycle in the category graph.

    A category that would be its own parent is the shortest cycle.
    """


class TaxomeshRelationError(TaxomeshValidationError):
    """Raised when an item-to-item relation is not valid.

    Two cases: the source and the target are the same item, or the relation type is empty or
    only whitespace.
    """


class TaxomeshDuplicateSlugError(TaxomeshValidationError):
    """Raised when another entity of the same kind already has the slug, which is not empty."""


class TaxomeshRepositoryError(TaxomeshError):
    """Raised when a repository cannot read or write its storage.

    The causes include: a file that cannot be read, parsed or written; a path that is a directory;
    a file that another writer changed after the repository read it; Django that is not installed
    or not configured; and a database error that Django raises in a member whose port docstring
    names this error. The other members of ``DjangoRepository`` let Django's ``DatabaseError``
    through.
    """


class TaxomeshConfigError(TaxomeshError):
    """Raised when a ``taxomesh.toml`` cannot be read or parsed, or names an unsupported repository type."""


class TaxomeshRootCategoryError(TaxomeshValidationError):
    """Raised when a category would have the reserved name of the implicit root, on create or on rename."""


class TaxomeshExternalIdConflictError(TaxomeshValidationError):
    """Raised when another entity of the same kind already has the external id, which is not ``None``."""


class TaxomeshVersionConflictError(TaxomeshError):
    """Raised when an update expects the stored row at a version that it is no longer at.

    It is a ``TaxomeshError`` and not a validation error: the request was valid, and the stored row
    changed, or was deleted, after the caller read it. To continue, read the row again and update
    it with its new version.
    """
