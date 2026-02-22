def test_taxomesh_importable() -> None:
    import taxomesh  # noqa: F401

    assert taxomesh.__version__ is not None
