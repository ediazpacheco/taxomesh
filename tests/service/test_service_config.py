"""Tests for TaxomeshService config_path parameter and repository property (FR-008–FR-012)."""

from pathlib import Path
from unittest.mock import patch

import pytest

from taxomesh import TaxomeshService
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
