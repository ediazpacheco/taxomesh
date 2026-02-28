"""Base model class for all taxomesh domain entities."""

from pydantic import BaseModel, ConfigDict


class ModelBase(BaseModel):
    """Shared base for all taxomesh Pydantic models."""

    model_config = ConfigDict(populate_by_name=True, validate_assignment=True)
