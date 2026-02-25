"""Custom exception hierarchy for the taxomesh library.

All library errors inherit from TaxomeshError, allowing callers to catch at
any granularity — from the root base class to the most specific leaf class.
Every exception name carries the ``Taxomesh`` prefix for unambiguous identification
in multi-library codebases.
"""


class TaxomeshError(Exception):
    """Base class for all taxomesh library errors."""


class TaxomeshNotFoundError(TaxomeshError):
    """Raised when a requested entity does not exist in the repository."""


class TaxomeshCategoryNotFoundError(TaxomeshNotFoundError):
    """Raised when a category with the given identifier does not exist."""


class TaxomeshItemNotFoundError(TaxomeshNotFoundError):
    """Raised when an item with the given identifier does not exist."""


class TaxomeshTagNotFoundError(TaxomeshNotFoundError):
    """Raised when a tag with the given identifier does not exist."""


class TaxomeshValidationError(TaxomeshError):
    """Raised when a domain constraint is violated."""


class TaxomeshCyclicDependencyError(TaxomeshValidationError):
    """Raised when a cyclic dependency is detected in the category DAG."""


class TaxomeshRepositoryError(TaxomeshError):
    """Raised when a storage I/O or parse failure occurs in a repository adapter."""


class TaxomeshConfigError(TaxomeshError):
    """Raised when a taxomesh.toml configuration file is invalid or specifies an unsupported option."""


class TaxomeshRootCategoryError(TaxomeshError):
    """Raised when a mutating operation is attempted on the reserved root category."""
