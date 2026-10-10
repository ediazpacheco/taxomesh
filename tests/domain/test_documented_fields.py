"""Every row and read model documents each of its fields under ``Attributes:``.

``help(Category)`` is where a reader meets a row, and it lists the fields with their types only.
The class docstring's ``Attributes:`` section says what each one holds and who sets it, so the
answer is in the interpreter as well as in ``docs/python-api.md``. The section names every field,
and nothing that is not one, so it cannot drift from the class.

A row carries data and nothing else: its fields are all it adds to pydantic's ``BaseModel``, so
the section covers everything a reader can reach on it. What is done with a row lives on its
collection, and what it is connected to on the graph's node.
"""

import dataclasses
import inspect
import re

import pytest
from pydantic import BaseModel

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
from taxomesh.domain.related import RelatedItems

ROWS: list[type[BaseModel]] = [
    Category,
    Item,
    Tag,
    CategoryParentLink,
    ItemParentLink,
    ItemRelationLink,
    ItemTagLink,
]

DOCUMENTED: list[type] = [*ROWS, RelatedItems, TaxomeshInfo, RepositoryInfo]

_ENTRY = re.compile(r"(\w+):")


def field_names(cls: type) -> list[str]:
    """Return the class's fields: a pydantic model's or a dataclass's, in declaration order."""
    if issubclass(cls, BaseModel):
        return list(cls.model_fields)
    if dataclasses.is_dataclass(cls):
        return [field.name for field in dataclasses.fields(cls)]
    raise TypeError(f"{cls.__name__} is neither a model nor a dataclass")


def documented_names(cls: type) -> list[str]:
    """Return the names the class docstring's ``Attributes:`` section documents, in order.

    An entry is a line one level deeper than the heading that starts with a name and a colon; a
    deeper line continues the entry above it, and a line back at the heading's level ends the
    section.
    """
    lines = (inspect.getdoc(cls) or "").splitlines()
    if "Attributes:" not in lines:
        return []
    names: list[str] = []
    for line in lines[lines.index("Attributes:") + 1 :]:
        if line and not line.startswith(" "):
            break
        entry = _ENTRY.match(line.removeprefix("    "))
        if entry and not line.startswith("     "):
            names.append(entry.group(1))
    return names


@pytest.mark.parametrize("cls", DOCUMENTED, ids=lambda cls: cls.__name__)
def test_the_attributes_section_names_every_field_and_nothing_else(cls: type) -> None:
    """In declaration order, so the section reads as the class does."""
    assert documented_names(cls) == field_names(cls)


@pytest.mark.parametrize("row", ROWS, ids=lambda row: row.__name__)
def test_a_row_adds_no_public_attribute_beyond_its_fields(row: type[BaseModel]) -> None:
    """A property or a method on a row would be behaviour the ``Attributes:`` section never names."""
    added = {name for name in dir(row) if not name.startswith("_")} - set(dir(BaseModel))
    assert added - set(row.model_fields) == set()
