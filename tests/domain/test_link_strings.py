"""A link reads as a short sentence that names its two ends by identifier.

``str()`` of a row names the row; ``str()`` of a link says how its two rows are joined, in the form
the command line prints a relation, so a link in a log line or a message is readable. ``repr()`` keeps
every field.
"""

from uuid import UUID

from taxomesh.domain.models import CategoryParentLink, ItemParentLink, ItemRelationLink, ItemTagLink

A = UUID("00000000-0000-4000-8000-00000000000a")
B = UUID("00000000-0000-4000-8000-00000000000b")


def test_a_parent_link_names_the_child_under_its_parent() -> None:
    link = CategoryParentLink(category_id=A, parent_category_id=B, sort_index=2)

    assert str(link) == f"{A} under {B} (sort_index: 2)"


def test_a_placement_names_the_item_in_its_category() -> None:
    assert str(ItemParentLink(item_id=A, category_id=B)) == f"{A} in {B} (sort_index: 0)"


def test_a_tag_link_names_the_tag_on_its_item() -> None:
    assert str(ItemTagLink(item_id=A, tag_id=B)) == f"{B} on {A}"


def test_a_relation_reads_as_the_command_line_prints_it() -> None:
    link = ItemRelationLink(source_item_id=A, target_item_id=B, relation_type="covers", sort_index=1)

    assert str(link) == f"{A} --[covers]--> {B} (sort_index: 1)"


def test_repr_keeps_every_field() -> None:
    link = ItemRelationLink(source_item_id=A, target_item_id=B, relation_type="covers", metadata={"year": 1941})

    assert "metadata" in repr(link)
