"""The YAML store reads and writes with libyaml when PyYAML has it, and with PyYAML's own codec when not.

libyaml, the C codec that PyYAML's wheels carry, is many times faster on a large store. Both codecs are
the safe ones, which build no arbitrary Python object. A store that one codec writes loads unchanged
with the other, and a store that libyaml wrote is the same text when PyYAML's own codec writes it again,
while its text keeps inside the Basic Multilingual Plane.
"""

from pathlib import Path
from typing import Any, Final

import pytest
import yaml

from taxomesh import TaxomeshService
from taxomesh.adapters.repositories.yaml_repository import YamlRepository

# Text that YAML quotes, escapes or folds. U+0085 is left out: PyYAML's own dumper writes it so that it
# loads back as a space, whichever codec reads it.
TEXTS: Final[tuple[str, ...]] = (
    "Café — Ñandú 中文",
    "line one\nline two\n",
    "  padded  ",
    "yes",
    "null",
    "1e3",
    "- dash",
    "a: b",
    "#hash",
    "'single'",
    '"double"',
    "~",
    "tab\there",
    "line separator",
    "word " * 40,
)

# Outside the Basic Multilingual Plane: libyaml writes it as an escape, PyYAML's codec as it is.
EMOJI: Final[str] = "Tango 🎵"

needs_libyaml = pytest.mark.skipif(not yaml.__with_libyaml__, reason="PyYAML is installed without libyaml")


@pytest.fixture
def codecs(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record the class name of each loader and dumper that PyYAML is called with."""
    used: list[str] = []
    load, dump_all = yaml.load, yaml.dump_all

    # Any: what PyYAML's loader returns, passed on unchanged.
    def recording_load(stream: str, Loader: type[yaml.SafeLoader] | type[yaml.CSafeLoader]) -> Any:  # noqa: N803
        used.append(Loader.__name__)
        return load(stream, Loader=Loader)

    # Any: PyYAML's options and its result, passed on unchanged.
    def recording_dump_all(documents: Any, stream: Any = None, Dumper: Any = yaml.Dumper, **options: Any) -> Any:  # noqa: N803
        used.append(Dumper.__name__)
        return dump_all(documents, stream, Dumper=Dumper, **options)

    monkeypatch.setattr(yaml, "load", recording_load)
    monkeypatch.setattr(yaml, "dump_all", recording_dump_all)
    return used


def _store(path: Path, texts: tuple[str, ...]) -> YamlRepository:
    """Store a category and an item for each text, the text in their names, descriptions and metadata, and a tag."""
    repo = YamlRepository(path)
    svc = TaxomeshService(repo, cache_ttl=0)
    svc.tags.create("tag")
    for n, text in enumerate(texts):
        svc.categories.create(text, description=text, metadata={"text": text, "n": n})
        svc.items.create(text, metadata={"nested": {"text": [text]}})
    return repo


@pytest.mark.parametrize(
    "libyaml",
    [pytest.param(True, marks=needs_libyaml, id="libyaml"), pytest.param(False, id="PyYAML")],
)
def test_the_store_reads_and_writes_with_the_codec_that_pyyaml_has(
    libyaml: bool, codecs: list[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(yaml, "__with_libyaml__", libyaml)
    path = tmp_path / "store.yaml"

    TaxomeshService(YamlRepository(path), cache_ttl=0)
    YamlRepository(path)

    assert set(codecs) == ({"CSafeLoader", "CSafeDumper"} if libyaml else {"SafeLoader", "SafeDumper"})


@needs_libyaml
@pytest.mark.parametrize(("written_by", "read_by"), [(True, False), (False, True)], ids=["libyaml", "PyYAML"])
def test_a_store_that_one_codec_writes_loads_unchanged_with_the_other(
    written_by: bool, read_by: bool, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "store.yaml"
    monkeypatch.setattr(yaml, "__with_libyaml__", written_by)
    written = _store(path, (*TEXTS, EMOJI))

    monkeypatch.setattr(yaml, "__with_libyaml__", read_by)
    read = YamlRepository(path)

    assert read.list_categories(enabled=None) == written.list_categories(enabled=None)
    assert read.list_items(enabled=None) == written.list_items(enabled=None)


@needs_libyaml
def test_a_store_that_libyaml_wrote_is_the_same_text_when_pyyamls_codec_writes_it_again(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "store.yaml"
    monkeypatch.setattr(yaml, "__with_libyaml__", True)
    _store(path, TEXTS)
    text = path.read_text(encoding="utf-8")

    monkeypatch.setattr(yaml, "__with_libyaml__", False)
    again = YamlRepository(path)
    again.save_tag(again.list_tags()[0])

    assert path.read_text(encoding="utf-8") == text
