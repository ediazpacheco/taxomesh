"""taxomesh — Flexible taxonomy management for generic items.

Organize arbitrary items into multi-parent category hierarchies with
per-parent sort indexes, free-form tags, and pluggable storage backends.
"""

import logging
from importlib.metadata import version

from taxomesh.application.service import TaxomeshService
from taxomesh.exceptions import (
    TaxomeshCategoryNotFoundError,
    TaxomeshConfigError,
    TaxomeshCyclicDependencyError,
    TaxomeshDuplicateSlugError,
    TaxomeshError,
    TaxomeshExternalIdConflictError,
    TaxomeshItemNotFoundError,
    TaxomeshNotFoundError,
    TaxomeshRelationError,
    TaxomeshRepositoryError,
    TaxomeshTagNotFoundError,
    TaxomeshValidationError,
)

__version__ = version("taxomesh")

# Register a NullHandler so taxomesh never emits "no handlers" warnings in
# consuming applications that have not configured logging.
logging.getLogger("taxomesh").addHandler(logging.NullHandler())

__all__ = [
    "TaxomeshService",
    "TaxomeshError",
    "TaxomeshNotFoundError",
    "TaxomeshCategoryNotFoundError",
    "TaxomeshItemNotFoundError",
    "TaxomeshTagNotFoundError",
    "TaxomeshValidationError",
    "TaxomeshCyclicDependencyError",
    "TaxomeshDuplicateSlugError",
    "TaxomeshExternalIdConflictError",
    "TaxomeshRelationError",
    "TaxomeshRepositoryError",
    "TaxomeshConfigError",
]
