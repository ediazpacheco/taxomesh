"""taxomesh — Flexible taxonomy management for generic items.

Organize arbitrary items into multi-parent category hierarchies with
per-parent sort indexes, free-form tags, and pluggable storage backends.
"""

from taxomesh.application.service import TaxomeshService
from taxomesh.exceptions import (
    TaxomeshCategoryNotFoundError,
    TaxomeshConfigError,
    TaxomeshCyclicDependencyError,
    TaxomeshError,
    TaxomeshItemNotFoundError,
    TaxomeshNotFoundError,
    TaxomeshRepositoryError,
    TaxomeshTagNotFoundError,
    TaxomeshValidationError,
)

__version__ = "0.1.0a4"

__all__ = [
    "TaxomeshService",
    "TaxomeshError",
    "TaxomeshNotFoundError",
    "TaxomeshCategoryNotFoundError",
    "TaxomeshItemNotFoundError",
    "TaxomeshTagNotFoundError",
    "TaxomeshValidationError",
    "TaxomeshCyclicDependencyError",
    "TaxomeshRepositoryError",
    "TaxomeshConfigError",
]
