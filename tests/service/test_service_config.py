"""Tests for TaxomeshService config_path parameter and repository property."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from taxomesh import TaxomeshService
from taxomesh.adapters.repositories.django_repository import DjangoRepository
from taxomesh.exceptions import TaxomeshConfigError


def test_no_args_no_config_file_falls_back_to_yaml_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TaxomeshService() with no config_path and no taxomesh.toml in CWD uses YamlRepository."""
    monkeypatch.chdir(tmp_path)
    TaxomeshService()
    assert (tmp_path / "data" / "taxomesh.yaml").exists()


def test_auto_discovers_toml_from_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TaxomeshService() auto-discovers taxomesh.toml from CWD and reads it."""
    monkeypatch.chdir(tmp_path)
    custom = tmp_path / "my_data.yaml"
    (tmp_path / "taxomesh.toml").write_text(f'[repository]\ntype = "yaml"\npath = "{custom}"\n', encoding="utf-8")
    TaxomeshService()
    assert custom.exists()


def test_explicit_config_path_yaml(tmp_path: Path) -> None:
    """TaxomeshService(config_path=...) reads YAML config and creates YamlRepository."""
    custom_db = tmp_path / "custom.yaml"
    cfg = tmp_path / "my.toml"
    cfg.write_text(f'[repository]\ntype = "yaml"\npath = "{custom_db}"\n', encoding="utf-8")
    TaxomeshService(config_path=cfg)
    assert custom_db.exists()


def test_explicit_config_path_json(tmp_path: Path) -> None:
    """TaxomeshService(config_path=...) reads JSON config and creates JsonRepository."""
    custom_db = tmp_path / "custom.json"
    cfg = tmp_path / "my.toml"
    cfg.write_text(f'[repository]\ntype = "json"\npath = "{custom_db}"\n', encoding="utf-8")
    TaxomeshService(config_path=cfg)
    assert custom_db.exists()


def test_explicit_config_path_accepts_str(tmp_path: Path) -> None:
    """TaxomeshService(config_path=str) accepts a string path."""
    custom_db = tmp_path / "custom.yaml"
    cfg = tmp_path / "my.toml"
    cfg.write_text(f'[repository]\ntype = "yaml"\npath = "{custom_db}"\n', encoding="utf-8")
    TaxomeshService(config_path=str(cfg))
    assert custom_db.exists()


def test_explicit_config_path_overrides_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit config_path takes precedence over auto-discovered taxomesh.toml in CWD."""
    monkeypatch.chdir(tmp_path)
    cwd_db = tmp_path / "cwd.yaml"
    (tmp_path / "taxomesh.toml").write_text(f'[repository]\ntype = "yaml"\npath = "{cwd_db}"\n', encoding="utf-8")
    explicit_db = tmp_path / "explicit.json"
    explicit_cfg = tmp_path / "other.toml"
    explicit_cfg.write_text(f'[repository]\ntype = "json"\npath = "{explicit_db}"\n', encoding="utf-8")
    TaxomeshService(config_path=explicit_cfg)
    assert explicit_db.exists()
    assert not cwd_db.exists()


def test_repository_kwarg_bypasses_config(tmp_path: Path) -> None:
    """TaxomeshService(repository=repo) ignores config_path entirely."""
    from taxomesh.adapters.repositories.json_repository import JsonRepository  # noqa: PLC0415

    cfg = tmp_path / "taxomesh.toml"
    cfg.write_text(
        f'[repository]\ntype = "yaml"\npath = "{tmp_path / "should_not_exist.yaml"}"\n',
        encoding="utf-8",
    )
    repo = JsonRepository(tmp_path / "real.json")
    svc = TaxomeshService(repository=repo, config_path=cfg)
    assert not (tmp_path / "should_not_exist.yaml").exists()
    assert svc.repository is repo


def test_invalid_toml_raises_config_error(tmp_path: Path) -> None:
    """TaxomeshService(config_path=bad.toml) raises TaxomeshConfigError."""
    bad_cfg = tmp_path / "bad.toml"
    bad_cfg.write_text("this is NOT toml !!!", encoding="utf-8")
    with pytest.raises(TaxomeshConfigError):
        TaxomeshService(config_path=bad_cfg)


def test_unsupported_type_raises_config_error(tmp_path: Path) -> None:
    """TaxomeshService with unsupported repository type raises TaxomeshConfigError."""
    cfg = tmp_path / "bad_type.toml"
    cfg.write_text('[repository]\ntype = "sqlite"\n', encoding="utf-8")
    with pytest.raises(TaxomeshConfigError):
        TaxomeshService(config_path=cfg)


def test_nonexistent_config_path_falls_back_to_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When config_path points to a non-existent file, falls back to YamlRepository."""
    monkeypatch.chdir(tmp_path)
    nonexistent = tmp_path / "does-not-exist.toml"
    TaxomeshService(config_path=nonexistent)
    assert (tmp_path / "data" / "taxomesh.yaml").exists()


def test_repository_property_returns_active_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """svc.repository property returns the active storage backend."""
    monkeypatch.chdir(tmp_path)
    svc = TaxomeshService()
    assert svc.repository is not None


def test_repository_property_returns_injected_repo(tmp_path: Path) -> None:
    """svc.repository returns the same instance as the injected repository."""
    from taxomesh.adapters.repositories.json_repository import JsonRepository  # noqa: PLC0415

    repo = JsonRepository(tmp_path / "test.json")
    svc = TaxomeshService(repository=repo)
    assert svc.repository is repo


def test_os_error_on_config_read_raises_config_error_with_chain(tmp_path: Path) -> None:
    """PermissionError during config file read raises TaxomeshConfigError with chaining."""
    cfg = tmp_path / "taxomesh.toml"
    cfg.write_text('[repository]\ntype = "yaml"\n', encoding="utf-8")
    with (
        patch.object(Path, "read_text", side_effect=PermissionError("access denied")),
        pytest.raises(TaxomeshConfigError) as exc_info,
    ):
        TaxomeshService(config_path=cfg)
    assert isinstance(exc_info.value.__cause__, PermissionError)


# ---------------------------------------------------------------------------
# TOML config: type = "django"
# ---------------------------------------------------------------------------


def test_build_repo_from_config_django_type(tmp_path: Path) -> None:
    """type = "django" in config constructs a DjangoRepository instance."""
    cfg = tmp_path / "taxomesh.toml"
    cfg.write_text('[repository]\ntype = "django"\n', encoding="utf-8")

    mock_repo = MagicMock(spec=DjangoRepository)
    mock_repo.list_categories.return_value = []

    with patch(
        "taxomesh._config.DjangoRepository",
        return_value=mock_repo,
    ):
        svc = TaxomeshService(config_path=cfg)

    assert svc.repository is mock_repo


def test_build_repo_from_config_django_type_with_using(tmp_path: Path) -> None:
    """Optional 'using' key is passed to DjangoRepository constructor."""
    cfg = tmp_path / "taxomesh.toml"
    cfg.write_text('[repository]\ntype = "django"\nusing = "secondary"\n', encoding="utf-8")

    mock_repo = MagicMock(spec=DjangoRepository)
    mock_repo.list_categories.return_value = []

    with patch(
        "taxomesh._config.DjangoRepository",
    ) as MockDjangoRepo:
        MockDjangoRepo.return_value = mock_repo
        TaxomeshService(config_path=cfg)
        MockDjangoRepo.assert_called_once_with(using="secondary")


def test_build_repo_from_config_unsupported_type_lists_django_in_error(tmp_path: Path) -> None:
    """Error message for unsupported type mentions 'django' as supported option."""
    cfg = tmp_path / "bad_type.toml"
    cfg.write_text('[repository]\ntype = "mongodb"\n', encoding="utf-8")
    with pytest.raises(TaxomeshConfigError, match="'django'"):
        TaxomeshService(config_path=cfg)


# ---------------------------------------------------------------------------
# DJANGO_REPO_TYPE named constant
# ---------------------------------------------------------------------------


def test_django_repo_type_importable_and_equals_django() -> None:
    """DJANGO_REPO_TYPE must be importable from django_repository and equal 'django'."""
    from taxomesh.adapters.repositories.django_repository import DJANGO_REPO_TYPE  # noqa: PLC0415

    assert DJANGO_REPO_TYPE == "django"


# ---------------------------------------------------------------------------
# describe() on JsonRepository and YamlRepository
# ---------------------------------------------------------------------------


def test_json_repository_describe(tmp_path: Path) -> None:
    """JsonRepository.describe() reports its class, its path and no extras."""
    from taxomesh.adapters.repositories.json_repository import JsonRepository  # noqa: PLC0415

    repo = JsonRepository(tmp_path / "t.json")
    info = repo.describe()
    assert info.backend == "JsonRepository"
    assert info.path is not None
    assert str(tmp_path / "t.json") in info.path
    assert info.diagnostics == {}


def test_yaml_repository_describe(tmp_path: Path) -> None:
    """YamlRepository.describe() reports its class, its path and no extras."""
    from taxomesh.adapters.repositories.yaml_repository import YamlRepository  # noqa: PLC0415

    repo = YamlRepository(tmp_path / "t.yaml")
    info = repo.describe()
    assert info.backend == "YamlRepository"
    assert info.path is not None
    assert str(tmp_path / "t.yaml") in info.path
    assert info.diagnostics == {}


# ---------------------------------------------------------------------------
# TaxomeshService.info
# ---------------------------------------------------------------------------


def test_info_populates_every_field(tmp_path: Path) -> None:
    """``svc.info`` populates every field it declares.

    The dataclass declares the fields, and ``tests/domain/test_info_models.py`` pins the list, so
    this test asserts what the declaration cannot: that the *service* populates each field rather
    than leaving it empty.
    """
    from taxomesh.adapters.repositories.json_repository import JsonRepository  # noqa: PLC0415

    repo = JsonRepository(tmp_path / "t.json")
    svc = TaxomeshService(repository=repo)
    info = svc.info
    assert info.version
    assert info.repository.backend == "JsonRepository"
    assert info.repository.path is not None


def test_info_repository_backend_matches_class(tmp_path: Path) -> None:
    """``info.repository.backend`` matches the class name of the active repo."""
    from taxomesh.adapters.repositories.json_repository import JsonRepository  # noqa: PLC0415

    repo = JsonRepository(tmp_path / "t.json")
    svc = TaxomeshService(repository=repo)
    info = svc.info
    assert info.repository.backend == "JsonRepository"
    assert info.repository.path is not None


@pytest.mark.django_db
def test_info_django_repo_has_no_path() -> None:
    """``info.repository.path`` is None with DjangoRepository, which has no file."""
    pytest.importorskip("django", reason="django not installed")
    svc = TaxomeshService(repository=DjangoRepository())
    info = svc.info
    assert info.repository.backend == "DjangoRepository"
    assert info.repository.path is None


def test_info_config_name_none_when_no_config(tmp_path: Path) -> None:
    """``info.config_name`` is None when no TOML config was loaded."""
    from taxomesh.adapters.repositories.json_repository import JsonRepository  # noqa: PLC0415

    repo = JsonRepository(tmp_path / "t.json")
    svc = TaxomeshService(repository=repo)
    assert svc.info.config_name is None
