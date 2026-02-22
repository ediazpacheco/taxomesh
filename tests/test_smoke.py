import taxomesh


def test_taxomesh_importable() -> None:
    assert taxomesh.__version__ is not None
