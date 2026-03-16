"""Shared field-length constraints for taxomesh domain models.

These constants are the single source of truth for all ``max_length`` values
used in Pydantic domain models and Django ORM models. Importing from this
module ensures that the two layers stay in sync without duplicating magic
number literals.
"""

from typing import Final

# Maximum character length for a category name.
MAX_CATEGORY_NAME_LENGTH: Final[int] = 256

# Maximum character length for a tag name.
MAX_TAG_NAME_LENGTH: Final[int] = 25

# Maximum character length for a category description.
MAX_DESCRIPTION_LENGTH: Final[int] = 100_000

# Maximum character length for an ExternalId when stored as a plain string.
MAX_EXTERNAL_ID_STR_LENGTH: Final[int] = 256

# Default value for Category.description — empty string means "no description".
DEFAULT_DESCRIPTION: Final[str] = ""

# Default value for Category.external_id — empty string means "no external ID".
DEFAULT_CATEGORY_EXTERNAL_ID: Final[str] = ""

# Default value for Item.external_id — empty string means "no external reference".
# Items that do not yet have (or do not need) a link to an external entity use this sentinel.
DEFAULT_ITEM_EXTERNAL_ID: Final[str] = ""

# Reserved name for the internal root category node.  Categories with this
# name must never be exposed to end users or administrators.
ROOT_CATEGORY_NAME: Final[str] = "__root__"

# Maximum character length for an item name.
MAX_ITEM_NAME_LENGTH: Final[int] = 256

# Maximum character length for a slug (URL-friendly short identifier).
MAX_SLUG_LENGTH: Final[int] = 256

# Maximum character length for a search query string.
MAX_SEARCH_QUERY_LENGTH: Final[int] = 500

# Default value for slug — empty string means "no slug".
DEFAULT_SLUG: Final[str] = ""

# Maximum character length for a relation type string.
RELATION_TYPE_MAX_LENGTH: Final[int] = 256

# Direction constant for outgoing item relations (source → target).
DIRECTION_OUTGOING: Final[str] = "outgoing"

# Direction constant for incoming item relations (target ← source).
DIRECTION_INCOMING: Final[str] = "incoming"
