"""Every request schema carries exactly the arguments of the collection member it feeds, in its order.

A handler forwards each schema field to its member under the member's own keyword, so a field the
member cannot take fails at runtime, and a member argument no field carries cannot be reached over
HTTP at all. Neither shows up under ``mypy --strict``, which sees each schema and each member on its
own, so the correspondence is asserted here. The order is asserted too: an OpenAPI page lists the
fields as the schema declares them, and it then reads as ``help()`` of the member does.

HTTP names a row by its identifier, so a field ending in ``_id`` feeds the parameter named by the
noun: ``parent_id`` feeds ``parent``, ``category_id`` feeds ``category``. ``external_id`` is not a
row's identifier and keeps its name on both sides. The member's subject, which a handler takes from
the path rather than the body, is not a field.
"""

import inspect
from collections.abc import Callable

import pytest
from pydantic import BaseModel

from taxomesh.application.collections.categories import CategoryCollection
from taxomesh.application.collections.items import ItemCollection
from taxomesh.application.collections.tags import TagCollection
from taxomesh.contrib.api.schemas import (
    AddCategoryParentRequest,
    CreateCategoryRequest,
    CreateItemRequest,
    CreateTagRequest,
    PlaceItemRequest,
    SearchCategoriesRequest,
    SearchItemsRequest,
    UpdateCategoryRequest,
    UpdateItemRequest,
    UpdateTagRequest,
)

# Each schema, the member its handler calls, and that member's subject (None when it has none).
SCHEMA_MEMBERS: list[tuple[type[BaseModel], Callable[..., object], str | None]] = [
    (CreateCategoryRequest, CategoryCollection.create, None),
    (UpdateCategoryRequest, CategoryCollection.update, "category"),
    (AddCategoryParentRequest, CategoryCollection.add_parent, "category"),
    (SearchCategoriesRequest, CategoryCollection.search, None),
    (CreateItemRequest, ItemCollection.create, None),
    (UpdateItemRequest, ItemCollection.update, "item"),
    (PlaceItemRequest, ItemCollection.place_in, "item"),
    (SearchItemsRequest, ItemCollection.search, None),
    (CreateTagRequest, TagCollection.create, None),
    (UpdateTagRequest, TagCollection.update, "tag"),
]


def _parameter_for(field: str) -> str:
    """The member parameter a schema field feeds: a row's identifier feeds the noun."""
    if field.endswith("_id") and field != "external_id":
        return field.removesuffix("_id")
    return field


@pytest.mark.parametrize(
    ("schema", "member", "subject"),
    SCHEMA_MEMBERS,
    ids=[schema.__name__ for schema, _, _ in SCHEMA_MEMBERS],
)
def test_schema_fields_are_the_members_arguments(
    schema: type[BaseModel], member: Callable[..., object], subject: str | None
) -> None:
    """The fields, read as parameters, are the member's arguments apart from its subject, in its order."""
    arguments = [name for name in inspect.signature(member).parameters if name not in ("self", subject)]
    fed = [_parameter_for(field) for field in schema.model_fields]
    assert set(fed) == set(arguments), (
        f"{schema.__name__} feeds {sorted(set(fed) - set(arguments))} that {member.__qualname__} does not take, "
        f"and leaves out {sorted(set(arguments) - set(fed))}"
    )
    assert fed == arguments, f"{schema.__name__} lists {fed}, where {member.__qualname__} takes {arguments}"
