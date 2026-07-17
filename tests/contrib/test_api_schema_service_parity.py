"""FR-017 drift guard — every partial-update schema field must be accepted by its service method.

Handlers forward partial-update fields as ``**body.model_dump(exclude_unset=True)``. Unpacking a
``dict[str, Any]`` erases the keyword names, so a schema field with no matching service parameter
passes ``mypy --strict`` cleanly and fails only at runtime as a ``TypeError`` surfacing to the
caller as a 500. Static type checking provably cannot see this, so it is guarded by a test.
"""

import inspect
from typing import Any

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.contrib.api.schemas import (
    UpdateCategoryRequest,
    UpdateItemRequest,
    UpdateTagRequest,
)

# Each partial-update schema paired with the service method its handler forwards to.
SCHEMA_SERVICE_PAIRS: list[tuple[type[Any], str]] = [
    (UpdateItemRequest, "update_item"),
    (UpdateCategoryRequest, "update_category"),
    (UpdateTagRequest, "update_tag"),
]


@pytest.mark.parametrize(
    ("schema", "method_name"),
    SCHEMA_SERVICE_PAIRS,
    ids=[method for _, method in SCHEMA_SERVICE_PAIRS],
)
def test_schema_fields_are_accepted_service_kwargs(schema: type[Any], method_name: str) -> None:
    """Every schema field name is a keyword parameter of the corresponding service method."""
    accepted = set(inspect.signature(getattr(TaxomeshService, method_name)).parameters)
    schema_fields = set(schema.model_fields)
    unknown = schema_fields - accepted
    assert not unknown, (
        f"{schema.__name__} declares field(s) {sorted(unknown)} that "
        f"TaxomeshService.{method_name} cannot accept — these would fail at runtime, not under mypy."
    )
