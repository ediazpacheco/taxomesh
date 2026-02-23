from typing import Annotated, TypeAlias
from uuid import UUID

from pydantic import Field

ExternalId: TypeAlias = UUID | Annotated[str, Field(max_length=256)] | int
