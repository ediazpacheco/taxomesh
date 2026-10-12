"""What only ``YamlRepository`` does: an empty file is an empty store.

YAML parses empty text as no document, where JSON refuses it.
"""

from pathlib import Path

from taxomesh.adapters.repositories.yaml_repository import YamlRepository


def test_an_empty_file_loads_as_an_empty_store(tmp_path: Path) -> None:
    path = tmp_path / "store.yaml"
    path.write_text("", encoding="utf-8")
    repo = YamlRepository(path)
    assert repo.list_categories() == []
    assert repo.list_items() == []
    assert repo.list_tags() == []
    assert repo.list_category_parent_links() == []
    assert repo.list_item_parent_links() == []
