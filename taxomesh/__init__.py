"""taxomesh — Flexible taxonomy management for generic items.

Organize arbitrary items into multi-parent category hierarchies with
per-parent sort indexes, free-form tags, and pluggable storage backends.
"""

from taxomesh.application.service import TaxomeshService
from taxomesh.exceptions import (
    TaxomeshCategoryNotFoundError,
    TaxomeshConfigError,
    TaxomeshCyclicDependencyError,
    TaxomeshDuplicateSlugError,
    TaxomeshError,
    TaxomeshItemNotFoundError,
    TaxomeshNotFoundError,
    TaxomeshRelationError,
    TaxomeshRepositoryError,
    TaxomeshTagNotFoundError,
    TaxomeshValidationError,
)

__VERSION__ = "0.1.0a22"
__version__ = __VERSION__

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
    "TaxomeshRelationError",
    "TaxomeshRepositoryError",
    "TaxomeshConfigError",
]
