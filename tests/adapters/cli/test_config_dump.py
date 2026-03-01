"""Tests for --show-config CLI flag and supporting functions."""

from __future__ import annotations

import tomllib
from pathlib import Path

from typer.testing import CliRunner

from taxomesh.adapters.cli.config import CONFIG_KEYS, SUPPORTED_REPO_TYPES, dump_config
from taxomesh.adapters.cli.main import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# T001 — CONFIG_KEYS shape and dump_config() unit tests
# ---------------------------------------------------------------------------


class TestConfigKeysShape:
    def test_config_keys_is_list_of_dotted_path_strings(self) -> None:
        """CONFIG_KEYS must be a list[str] where every element matches '<section>.<key>'."""
        assert isinstance(CONFIG_KEYS, list)
        assert len(CONFIG_KEYS) > 0
        for entry in CONFIG_KEYS:
            assert isinstance(entry, str)
            parts = entry.split(".")
            assert len(parts) == 2, f"Expected '<section>.<key>', got {entry!r}"


class TestDumpConfig:
    def test_dump_config_yaml_defaults_is_valid_toml(self) -> None:
        """dump_config with yaml defaults must produce parseable TOML."""
        output = dump_config("yaml", "data/taxomesh.yaml")
        tomllib.loads(output)  # must not raise

    def test_dump_config_json_defaults_is_valid_toml(self) -> None:
        """dump_config with json defaults must produce parseable TOML."""
        output = dump_config("json", "data/taxomesh.json")
        tomllib.loads(output)  # must not raise

    def test_dump_config_reflects_provided_type_and_path(self) -> None:
        """Output must contain the exact repo_type and repo_path values passed in."""
        output = dump_config("json", "/custom/path.json")
        assert 'type = "json"' in output
        assert 'path = "/custom/path.json"' in output

    def test_dump_config_each_key_has_comment_above(self) -> None:
        """Every TOML key in the output must have a '#'-prefixed comment line immediately above it."""
        output = dump_config("yaml", "data/taxomesh.yaml")
        lines = output.splitlines()
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Skip comment lines, section headers, empty lines
            if stripped.startswith("#") or stripped.startswith("[") or not stripped:
                continue
            # This is a key=value line — look for a comment somewhere above it
            assert i > 0, f"Key line at index {i} has no preceding line: {line!r}"
            preceding_lines = lines[:i]
            has_comment_above = any(ln.strip().startswith("#") for ln in reversed(preceding_lines) if ln.strip())
            assert has_comment_above, f"Key line {line!r} at index {i} has no comment above it"

    def test_dump_config_contains_all_config_keys_entries(self) -> None:
        """Every key emitted by dump_config must correspond to a dotted path in CONFIG_KEYS."""
        output = dump_config("yaml", "data/taxomesh.yaml")
        parsed = tomllib.loads(output)
        all_keys = set(CONFIG_KEYS)
        for section, val in parsed.items():
            if isinstance(val, dict):
                for key in val:
                    assert f"{section}.{key}" in all_keys, f"Key {section}.{key!r} not in CONFIG_KEYS"
            else:
                assert section in all_keys, f"Key {section!r} not in CONFIG_KEYS"


# ---------------------------------------------------------------------------
# T005 — US1: default-config CLI integration tests
# ---------------------------------------------------------------------------


class TestShowConfigDefaults:
    def test_show_config_no_config_file_contains_yaml_defaults(self, tmp_path: Path) -> None:
        """With no config file, --show-config must output yaml defaults."""
        missing = tmp_path / "no_such.toml"
        result = runner.invoke(app, ["--config", str(missing), "--show-config"])
        assert 'type = "yaml"' in result.stdout
        assert 'path = "data/taxomesh.yaml"' in result.stdout

    def test_show_config_exit_code_zero(self, tmp_path: Path) -> None:
        """--show-config with no config file must exit 0."""
        missing = tmp_path / "no_such.toml"
        result = runner.invoke(app, ["--config", str(missing), "--show-config"])
        assert result.exit_code == 0

    def test_show_config_stdout_is_valid_toml(self, tmp_path: Path) -> None:
        """--show-config output must be parseable by tomllib."""
        missing = tmp_path / "no_such.toml"
        result = runner.invoke(app, ["--config", str(missing), "--show-config"])
        assert result.exit_code == 0
        tomllib.loads(result.stdout)  # must not raise

    def test_show_config_no_stderr_on_success(self, tmp_path: Path) -> None:
        """--show-config on success must produce no stderr output."""
        missing = tmp_path / "no_such.toml"
        result = runner.invoke(app, ["--config", str(missing), "--show-config"])
        assert result.exit_code == 0
        assert result.stderr == ""

    def test_show_config_exits_before_subcommand(self, tmp_path: Path) -> None:
        """--show-config must exit before executing a subcommand."""
        missing = tmp_path / "no_such.toml"
        result = runner.invoke(app, ["--config", str(missing), "--show-config", "category", "list"])
        assert result.exit_code == 0
        # Output should be TOML only — no category listing markers
        assert "--- Categories ---" not in result.stdout
        assert "--- Total:" not in result.stdout
        # Must still be valid TOML
        tomllib.loads(result.stdout)


# ---------------------------------------------------------------------------
# T009 — US2: partial-config and error CLI integration tests
# ---------------------------------------------------------------------------


class TestShowConfigPartialAndErrors:
    def test_show_config_json_type_uses_json_default_path(self, tmp_path: Path) -> None:
        """With type=json and no path, --show-config must use the json default path."""
        toml_file = tmp_path / "taxomesh.toml"
        toml_file.write_text('[repository]\ntype = "json"\n')
        result = runner.invoke(app, ["--config", str(toml_file), "--show-config"])
        assert result.exit_code == 0
        assert 'type = "json"' in result.stdout
        assert 'path = "data/taxomesh.json"' in result.stdout

    def test_show_config_yaml_type_with_custom_path(self, tmp_path: Path) -> None:
        """With type=yaml and custom path, --show-config must reflect that path."""
        toml_file = tmp_path / "taxomesh.toml"
        toml_file.write_text('[repository]\ntype = "yaml"\npath = "custom/store.yaml"\n')
        result = runner.invoke(app, ["--config", str(toml_file), "--show-config"])
        assert result.exit_code == 0
        assert 'type = "yaml"' in result.stdout
        assert 'path = "custom/store.yaml"' in result.stdout

    def test_show_config_with_explicit_config_flag(self, tmp_path: Path) -> None:
        """--config <path> --show-config must reflect the explicit file's values."""
        toml_file = tmp_path / "myconfig.toml"
        toml_file.write_text('[repository]\ntype = "json"\npath = "explicit/path.json"\n')
        result = runner.invoke(app, ["--config", str(toml_file), "--show-config"])
        assert result.exit_code == 0
        assert 'type = "json"' in result.stdout
        assert 'path = "explicit/path.json"' in result.stdout

    def test_show_config_empty_config_file_uses_all_defaults(self, tmp_path: Path) -> None:
        """Empty config file must produce the same output as no file (all defaults)."""
        toml_file = tmp_path / "taxomesh.toml"
        toml_file.write_text("")
        result = runner.invoke(app, ["--config", str(toml_file), "--show-config"])
        assert result.exit_code == 0
        assert 'type = "yaml"' in result.stdout
        assert 'path = "data/taxomesh.yaml"' in result.stdout

    def test_show_config_path_only_no_type_defaults_to_yaml(self, tmp_path: Path) -> None:
        """With only path overridden (no type), --show-config must default type to yaml (US2 AC2)."""
        toml_file = tmp_path / "taxomesh.toml"
        toml_file.write_text('[repository]\npath = "custom/override.yaml"\n')
        result = runner.invoke(app, ["--config", str(toml_file), "--show-config"])
        assert result.exit_code == 0
        assert 'type = "yaml"' in result.stdout
        assert 'path = "custom/override.yaml"' in result.stdout

    def test_show_config_malformed_toml_exits_nonzero(self, tmp_path: Path) -> None:
        """Malformed TOML file must cause --show-config to exit with non-zero code."""
        toml_file = tmp_path / "taxomesh.toml"
        toml_file.write_text("this is not valid toml = [[[\n")
        result = runner.invoke(app, ["--config", str(toml_file), "--show-config"])
        assert result.exit_code != 0

    def test_show_config_malformed_toml_error_to_stderr(self, tmp_path: Path) -> None:
        """Malformed TOML must produce empty stdout and non-empty stderr."""
        toml_file = tmp_path / "taxomesh.toml"
        toml_file.write_text("this is not valid toml = [[[\n")
        result = runner.invoke(app, ["--config", str(toml_file), "--show-config"])
        assert result.stdout == ""
        assert result.stderr != ""


# ---------------------------------------------------------------------------
# T011 — US3: CONFIG_KEYS completeness invariant tests
# ---------------------------------------------------------------------------


class TestConfigKeysInvariant:
    def _flatten_toml(self, parsed: dict[str, object]) -> set[str]:
        """Flatten a single-level nested dict to dotted-path keys."""
        result: set[str] = set()
        for section, value in parsed.items():
            if isinstance(value, dict):
                for key in value:
                    result.add(f"{section}.{key}")
            else:
                result.add(section)
        return result

    def test_config_keys_covers_all_dump_output_keys(self) -> None:
        """Every dotted path in the dump output must appear in CONFIG_KEYS."""
        output = dump_config("yaml", "data/taxomesh.yaml")
        parsed = tomllib.loads(output)
        dumped_keys = self._flatten_toml(parsed)
        assert dumped_keys <= set(CONFIG_KEYS)

    def test_dump_output_has_no_keys_outside_config_keys(self) -> None:
        """No key in the parsed dump output may be absent from CONFIG_KEYS."""
        output = dump_config("yaml", "data/taxomesh.yaml")
        parsed = tomllib.loads(output)
        dumped_keys = self._flatten_toml(parsed)
        extra = dumped_keys - set(CONFIG_KEYS)
        assert extra == set(), f"Keys in dump but not in CONFIG_KEYS: {extra}"

    def test_config_keys_has_no_duplicates(self) -> None:
        """CONFIG_KEYS must not contain duplicate entries."""
        assert len(CONFIG_KEYS) == len(set(CONFIG_KEYS))


# ---------------------------------------------------------------------------
# SC-001 — End-to-end: pipe dump output as config file, then run a command
# ---------------------------------------------------------------------------


class TestShowConfigEndToEnd:
    def test_dump_output_usable_as_config_file(self, tmp_path: Path) -> None:
        """Piping --show-config output to taxomesh.toml must allow subsequent commands (SC-001).

        Writes the dump output to a taxomesh.toml in tmp_path, then invokes a
        read-only CLI command (category list) using that file.  The command must
        exit 0, confirming the output is a valid, working configuration.
        """
        missing = tmp_path / "no_such.toml"
        dump_result = runner.invoke(app, ["--config", str(missing), "--show-config"])
        assert dump_result.exit_code == 0

        config_file = tmp_path / "taxomesh.toml"
        config_file.write_text(dump_result.stdout)

        run_result = runner.invoke(app, ["--config", str(config_file), "category", "list"])
        assert run_result.exit_code == 0


# ---------------------------------------------------------------------------
# T005 (b) — TestDumpConfigDjango
# ---------------------------------------------------------------------------


class TestDumpConfigDjango:
    def test_dump_config_django_is_valid_toml(self) -> None:
        """dump_config('django', 'default') must produce parseable TOML."""
        result = dump_config("django", "default")
        tomllib.loads(result)  # must not raise

    def test_dump_config_django_has_using_key(self) -> None:
        """dump_config('django', ...) output must contain 'using = "default"'."""
        result = dump_config("django", "default")
        assert 'using = "default"' in result

    def test_dump_config_django_has_no_path_key(self) -> None:
        """dump_config('django', ...) output must NOT contain a 'path =' key."""
        result = dump_config("django", "default")
        assert "path =" not in result

    def test_dump_config_django_accepted_values_lists_all_types(self) -> None:
        """The accepted-values comment in dump_config output must include 'django'."""
        result = dump_config("django", "default")
        assert '"django"' in result


# ---------------------------------------------------------------------------
# T005 (c) — TestSupportedRepoTypes
# ---------------------------------------------------------------------------


class TestSupportedRepoTypes:
    def test_supported_repo_types_is_tuple(self) -> None:
        """SUPPORTED_REPO_TYPES must be a tuple."""
        assert isinstance(SUPPORTED_REPO_TYPES, tuple)

    def test_supported_repo_types_contains_yaml_json_django(self) -> None:
        """SUPPORTED_REPO_TYPES must contain 'yaml', 'json', and 'django'."""
        assert "yaml" in SUPPORTED_REPO_TYPES
        assert "json" in SUPPORTED_REPO_TYPES
        assert "django" in SUPPORTED_REPO_TYPES


# ---------------------------------------------------------------------------
# T005 (d) & T006 — Django show-config tests (added to module scope)
# ---------------------------------------------------------------------------


class TestShowConfigDjango:
    def test_show_config_django_type_has_using_key(self, tmp_path: Path) -> None:
        """With type=django, --show-config must output 'using = \"default\"'."""
        toml_file = tmp_path / "taxomesh.toml"
        toml_file.write_text('[repository]\ntype = "django"\n', encoding="utf-8")
        result = runner.invoke(app, ["--config", str(toml_file), "--show-config"])
        assert result.exit_code == 0
        assert 'using = "default"' in result.stdout

    def test_show_config_django_type_has_no_path_key(self, tmp_path: Path) -> None:
        """With type=django, --show-config output must NOT contain 'path ='."""
        toml_file = tmp_path / "taxomesh.toml"
        toml_file.write_text('[repository]\ntype = "django"\n', encoding="utf-8")
        result = runner.invoke(app, ["--config", str(toml_file), "--show-config"])
        assert result.exit_code == 0
        assert "path =" not in result.stdout

    def test_show_config_django_type_is_valid_toml(self, tmp_path: Path) -> None:
        """With type=django, --show-config output must be valid TOML."""
        toml_file = tmp_path / "taxomesh.toml"
        toml_file.write_text('[repository]\ntype = "django"\n', encoding="utf-8")
        result = runner.invoke(app, ["--config", str(toml_file), "--show-config"])
        assert result.exit_code == 0
        tomllib.loads(result.stdout)  # must not raise

    def test_show_config_django_type_with_custom_using(self, tmp_path: Path) -> None:
        """With type=django and using=secondary, --show-config reflects the custom alias."""
        toml_file = tmp_path / "taxomesh.toml"
        toml_file.write_text('[repository]\ntype = "django"\nusing = "secondary"\n', encoding="utf-8")
        result = runner.invoke(app, ["--config", str(toml_file), "--show-config"])
        assert result.exit_code == 0
        assert 'using = "secondary"' in result.stdout

    def test_show_config_django_does_not_require_django_settings(self, tmp_path: Path) -> None:
        """--show-config with type=django must exit 0 and produce valid TOML
        without requiring DJANGO_SETTINGS_MODULE (no repo is instantiated)."""
        toml_file = tmp_path / "taxomesh.toml"
        toml_file.write_text('[repository]\ntype = "django"\n', encoding="utf-8")
        result = runner.invoke(app, ["--config", str(toml_file), "--show-config"])
        assert result.exit_code == 0
        tomllib.loads(result.stdout)  # must not raise
