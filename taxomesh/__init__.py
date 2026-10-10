"""taxomesh stores a graph of categories in a YAML file, a JSON file or the Django ORM, and a category
can have more than one parent. In Python, you read and delete categories, items and tags with five
forms that a dict also has: subscript, get, in, len and del.

You place items in categories, tag them, and relate them to other items. A category has its own sort
index under each parent, and an item under each category. A storage backend of your own implements
``TaxomeshRepositoryBase``.
"""

import logging
from importlib.metadata import version

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.graph import CategoryNode, TaxomeshGraph
from taxomesh.domain.info import RepositoryInfo, TaxomeshInfo
from taxomesh.domain.models import (
    Category,
    CategoryParentLink,
    Item,
    ItemParentLink,
    ItemRelationLink,
    ItemTagLink,
    Tag,
)
from taxomesh.domain.refs import CategoryRef, ItemRef, TagRef
from taxomesh.domain.related import RelatedItems
from taxomesh.domain.types import UNSET, Direction, ExternalId, UnsetType
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
    TaxomeshRootCategoryError,
    TaxomeshTagNotFoundError,
    TaxomeshValidationError,
    TaxomeshVersionConflictError,
)
from taxomesh.ports.repository import TaxomeshRepositoryBase

__version__ = version("taxomesh")

# When no handler is found, Python's last-resort handler writes each WARNING log record to stderr.
# This NullHandler stops that, so no log record is written until the application configures logging.
logging.getLogger("taxomesh").addHandler(logging.NullHandler())

__all__ = [
    # Service
    "TaxomeshService",
    # Exceptions — the full hierarchy
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
    "TaxomeshRootCategoryError",
    "TaxomeshVersionConflictError",
    # Domain models
    "Category",
    "Item",
    "Tag",
    "CategoryParentLink",
    "ItemParentLink",
    "ItemRelationLink",
    "ItemTagLink",
    # Read models
    "TaxomeshGraph",
    "CategoryNode",
    "RelatedItems",
    "TaxomeshInfo",
    "RepositoryInfo",
    # Repository port
    "TaxomeshRepositoryBase",
    # Public types
    "ExternalId",
    "UnsetType",
    "UNSET",
    "Direction",
    "CategoryRef",
    "ItemRef",
    "TagRef",
]
