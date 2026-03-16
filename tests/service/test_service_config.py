"""Tests for TaxomeshService config_path parameter and repository property (FR-008–FR-012)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from taxomesh import TaxomeshService
from taxomesh.adapters.repositories.django_repository import DjangoRepository
from taxomesh.exceptions import TaxomeshConfigError


def test_no_args_no_config_file_falls_back_to_yaml_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TaxomeshService() with no config_path and no taxomesh.toml in CWD uses YAMLRepository."""
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
    """TaxomeshService(config_path=...) reads YAML config and creates YAMLRepository."""
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
    """When config_path points to a non-existent file, falls back to YAMLRepository."""
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
    """PermissionError during config file read raises TaxomeshConfigError with chaining (FR-011)."""
    cfg = tmp_path / "taxomesh.toml"
    cfg.write_text('[repository]\ntype = "yaml"\n', encoding="utf-8")
    with (
        patch.object(Path, "read_text", side_effect=PermissionError("access denied")),
        pytest.raises(TaxomeshConfigError) as exc_info,
    ):
        TaxomeshService(config_path=cfg)
    assert isinstance(exc_info.value.__cause__, PermissionError)


# ---------------------------------------------------------------------------
# US6 — TOML config: type = "django" (FR-013, FR-014)
# ---------------------------------------------------------------------------


def test_build_repo_from_config_django_type(tmp_path: Path) -> None:
    """type = "django" in config constructs a DjangoRepository instance."""
    cfg = tmp_path / "taxomesh.toml"
    cfg.write_text('[repository]\ntype = "django"\n', encoding="utf-8")

    mock_repo = MagicMock(spec=DjangoRepository)
    mock_repo.list_categories.return_value = []

    with patch(
        "taxomesh.adapters.repositories.django_repository.DjangoRepository",
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
        "taxomesh.adapters.repositories.django_repository.DjangoRepository",
    ) as MockDjangoRepo:
        MockDjangoRepo.return_value = mock_repo
        TaxomeshService(config_path=cfg)
        MockDjangoRepo.assert_called_once_with(using="secondary")


def test_build_repo_from_config_unsupported_type_lists_django_in_error(tmp_path: Path) -> None:
    """Error message for unsupported type mentions 'django' as supported option (FR-014)."""
    cfg = tmp_path / "bad_type.toml"
    cfg.write_text('[repository]\ntype = "mongodb"\n', encoding="utf-8")
    with pytest.raises(TaxomeshConfigError, match="'django'"):
        TaxomeshService(config_path=cfg)


# ---------------------------------------------------------------------------
# T001 — DJANGO_REPO_TYPE named constant
# ---------------------------------------------------------------------------


def test_django_repo_type_importable_and_equals_django() -> None:
    """DJANGO_REPO_TYPE must be importable from django_repository and equal 'django'."""
    from taxomesh.adapters.repositories.django_repository import DJANGO_REPO_TYPE  # noqa: PLC0415

    assert DJANGO_REPO_TYPE == "django"


# ---------------------------------------------------------------------------
# T002 — get_debug_info() on JsonRepository and YAMLRepository
# ---------------------------------------------------------------------------


def test_json_repository_get_debug_info(tmp_path: Path) -> None:
    """JsonRepository.get_debug_info() returns a dict with a 'path' key."""
    from taxomesh.adapters.repositories.json_repository import JsonRepository  # noqa: PLC0415

    repo = JsonRepository(tmp_path / "t.json")
    info = repo.get_debug_info()
    assert isinstance(info, dict)
    assert "path" in info
    assert str(tmp_path / "t.json") in info["path"]


def test_yaml_repository_get_debug_info(tmp_path: Path) -> None:
    """YAMLRepository.get_debug_info() returns a dict with a 'path' key."""
    from taxomesh.adapters.repositories.yaml_repository import YAMLRepository  # noqa: PLC0415

    repo = YAMLRepository(tmp_path / "t.yaml")
    info = repo.get_debug_info()
    assert isinstance(info, dict)
    assert "path" in info
    assert str(tmp_path / "t.yaml") in info["path"]


# ---------------------------------------------------------------------------
# T032-T033 — TaxomeshService.get_debug()
# ---------------------------------------------------------------------------


def test_get_debug_returns_required_keys(tmp_path: Path) -> None:
    """TaxomeshService.get_debug() returns a dict with all required keys."""
    from taxomesh.adapters.repositories.json_repository import JsonRepository  # noqa: PLC0415

    repo = JsonRepository(tmp_path / "t.json")
    svc = TaxomeshService(repository=repo)
    info = svc.get_debug()
    assert "version" in info
    assert "config_name" in info
    assert "repository_type" in info
    assert "working_path" in info
    assert "repository_info" in info


def test_get_debug_repository_type_matches_class(tmp_path: Path) -> None:
    """get_debug()['repository_type'] matches the class name of the active repo."""
    from taxomesh.adapters.repositories.json_repository import JsonRepository  # noqa: PLC0415

    repo = JsonRepository(tmp_path / "t.json")
    svc = TaxomeshService(repository=repo)
    info = svc.get_debug()
    assert info["repository_type"] == "JsonRepository"
    assert info["working_path"] is not None


def test_get_debug_django_repo_has_none_working_path(request: pytest.FixtureRequest) -> None:
    """get_debug() with DjangoRepository returns None for working_path."""
    pytest.importorskip("django", reason="django not installed")
    request.getfixturevalue("db")
    svc = TaxomeshService(repository=DjangoRepository())
    info = svc.get_debug()
    assert info["repository_type"] == "DjangoRepository"
    assert info["working_path"] is None


def test_get_debug_config_name_none_when_no_config(tmp_path: Path) -> None:
    """get_debug()['config_name'] is None when no TOML config was loaded."""
    from taxomesh.adapters.repositories.json_repository import JsonRepository  # noqa: PLC0415

    repo = JsonRepository(tmp_path / "t.json")
    svc = TaxomeshService(repository=repo)
    assert svc.get_debug()["config_name"] is None
