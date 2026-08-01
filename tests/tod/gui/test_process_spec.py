"""ProcessSpec / ProcessSpecBuilder / ToolExecutor 执行缝单测。

覆盖：
- ProcessSpec frozen dataclass 契约（不可变、字段）
- for_script legacy 行为（program=sys.executable, argv[0]=script_path）
- for_e2m2e_cli 行为（program 可注入, argv[0]=subcommand）
- resolve_subcommand 映射与未映射时的 ValueError
- LegacyScriptExecutor / E2m2eCliExecutor 的 build_spec
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from tod.gui.jobs.process_spec import ProcessSpec
from tod.gui.jobs.process_spec_builder import (
    for_e2m2e_cli,
    for_script,
    resolve_subcommand,
)
from tod.gui.run.tool_executor import E2m2eCliExecutor, LegacyScriptExecutor
from tod.scripting import ScriptEntry


def _make_entry(name: str = "generate_dro_orbit", script_path: str | None = None) -> ScriptEntry:
    return ScriptEntry(
        module="dro",
        name=name,
        description="test",
        script_path=script_path or "tod/generates/cr3bp/dro/generate_dro_orbit.py",
    )


# ── ProcessSpec ────────────────────────────────────────────────


class TestProcessSpec:
    def test_frozen(self):
        spec = ProcessSpec(program="py", argv=("a",), working_dir=".")
        with pytest.raises(AttributeError):
            spec.program = "other"  # type: ignore[misc]

    def test_to_list_merges_program_and_argv(self):
        spec = ProcessSpec(program="py", argv=("a", "b"), working_dir=".")
        assert spec.to_list() == ["py", "a", "b"]


# ── for_script ─────────────────────────────────────────────────


class TestForScript:
    def test_uses_sys_executable_and_script_path(self):
        spec = for_script(_make_entry(), repo_root=".")
        assert spec.program == sys.executable
        assert spec.argv[0] == "tod/generates/cr3bp/dro/generate_dro_orbit.py"
        assert spec.is_legacy_script is True

    def test_appends_extra_args(self):
        spec = for_script(_make_entry(), extra_args=["--jacobi", "3.1"], repo_root=".")
        assert spec.argv == (
            "tod/generates/cr3bp/dro/generate_dro_orbit.py",
            "--jacobi",
            "3.1",
        )

    def test_injects_default_env_and_overrides(self):
        spec = for_script(
            _make_entry(),
            env={"DRO_FILE": "/x/dro.json"},
            repo_root=".",
        )
        assert spec.env["PYTHONUNBUFFERED"] == "1"
        assert spec.env["PYTHONIOENCODING"] == "utf-8"
        assert spec.env["DRO_FILE"] == "/x/dro.json"

    def test_working_dir_is_repo_root(self):
        spec = for_script(_make_entry(), repo_root="/repo")
        assert spec.working_dir == "/repo"


# ── for_e2m2e_cli ──────────────────────────────────────────────


class TestForE2m2eCli:
    def test_uses_injected_cli_program_and_subcommand(self):
        spec = for_e2m2e_cli(
            "orbit_design",
            _make_entry(),
            args=["--jacobi", "3.1"],
            repo_root=".",
            cli_program="/fake/e2m2e",
        )
        assert spec.program == "/fake/e2m2e"
        assert spec.argv == ("orbit_design", "--jacobi", "3.1")
        assert spec.is_legacy_script is False

    def test_working_dir_and_env(self):
        spec = for_e2m2e_cli(
            "orbit_design",
            _make_entry(),
            env={"E2M2E_BODY_ICON_SCALE": "0.3"},
            repo_root="/repo",
            cli_program="/fake/e2m2e",
        )
        assert spec.working_dir == "/repo"
        assert spec.env["E2M2E_BODY_ICON_SCALE"] == "0.3"


# ── resolve_subcommand ─────────────────────────────────────────


class TestResolveSubcommand:
    def test_mapped_entry_returns_subcommand(self):
        assert resolve_subcommand(_make_entry("generate_dro_orbit")) == "orbit_design"

    def test_unmapped_entry_raises_value_error(self):
        with pytest.raises(ValueError, match="尚未映射"):
            resolve_subcommand(_make_entry("plot_dro_family"))


# ── ToolExecutor ───────────────────────────────────────────────


class TestLegacyScriptExecutor:
    def test_build_spec_matches_legacy(self):
        exe = LegacyScriptExecutor(repo_root=".")
        spec = exe.build_spec(_make_entry())
        assert spec.program == sys.executable
        assert spec.argv[0] == "tod/generates/cr3bp/dro/generate_dro_orbit.py"

    def test_display_name_is_script_path(self):
        exe = LegacyScriptExecutor()
        assert exe.display_name(_make_entry()) == (
            "tod/generates/cr3bp/dro/generate_dro_orbit.py"
        )


class TestE2m2eCliExecutor:
    def test_build_spec_for_mapped_entry(self):
        exe = E2m2eCliExecutor(repo_root=".", cli_program="/fake/e2m2e")
        spec = exe.build_spec(_make_entry("generate_dro_orbit"))
        assert spec.program == "/fake/e2m2e"
        assert spec.argv[0] == "orbit_design"

    def test_unmapped_entry_raises(self):
        exe = E2m2eCliExecutor(cli_program="/fake/e2m2e")
        with pytest.raises(ValueError):
            exe.build_spec(_make_entry("plot_dro_family"))

    def test_display_name_falls_back_on_unmapped(self):
        exe = E2m2eCliExecutor(cli_program="/fake/e2m2e")
        assert exe.display_name(_make_entry("plot_dro_family")) == (
            "tod/generates/cr3bp/dro/generate_dro_orbit.py"
        )
        assert exe.display_name(_make_entry("generate_dro_orbit")) == "e2m2e orbit_design"
