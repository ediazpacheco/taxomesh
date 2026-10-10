"""The limits and the defaults of the taxomesh models.

Each ``max_length`` of a Pydantic model and of a Django ORM model comes from this module. The two
layers import the same constants, so their limits are the same and no number is written twice.
"""

from datetime import UTC, datetime
from typing import Final

# Maximum character length for a category name.
MAX_CATEGORY_NAME_LENGTH: Final[int] = 256

# Maximum character length for a tag name.
MAX_TAG_NAME_LENGTH: Final[int] = 25

# Maximum character length for a category description.
MAX_DESCRIPTION_LENGTH: Final[int] = 100_000

# Maximum character length for an external id, which is stored as text.
MAX_EXTERNAL_ID_STR_LENGTH: Final[int] = 256

# Default value for Category.description — empty string means "no description".
DEFAULT_DESCRIPTION: Final[str] = ""

# Default value for Category.external_id — None means "no external id".
DEFAULT_CATEGORY_EXTERNAL_ID: Final[str | None] = None

# Default value for Item.external_id — None means "no external id": the item stands for no record
# of your own system.
DEFAULT_ITEM_EXTERNAL_ID: Final[str | None] = None

# The reserved name of the implicit root. No member returns the implicit root, and ``create`` and
# ``update`` refuse this name for a category.
ROOT_CATEGORY_NAME: Final[str] = "__root__"

# Maximum character length for an item name.
MAX_ITEM_NAME_LENGTH: Final[int] = 256

# Maximum character length for a slug, a text key for URLs.
MAX_SLUG_LENGTH: Final[int] = 256

# Maximum character length for a search query string.
MAX_SEARCH_QUERY_LENGTH: Final[int] = 500

# Default value for slug — empty string means "no slug".
DEFAULT_SLUG: Final[str] = ""

# Maximum character length for a relation type string.
RELATION_TYPE_MAX_LENGTH: Final[int] = 256

# Default created_at/updated_at for a row stored without them.
AUDIT_EPOCH: Final[datetime] = datetime(1970, 1, 1, tzinfo=UTC)

# The version of a row built without one, such as the row that ``create`` stores.
DEFAULT_VERSION: Final[int] = 0
