"""Tests for generate_halo_family ScriptEntry.

Updated after restoring --method parameter: Halo uses PAL continuation,
with method selector for future extensibility.
"""

import pytest

from tod.gui.script_registry import SCRIPTS, ScriptEntry


def _find_halo_family_entry() -> ScriptEntry:
    for entry in SCRIPTS.get("generates", []):
        if entry.name == "generate_halo_family":
            return entry
    pytest.fail("generate_halo_family ScriptEntry not found in generates category")


class TestGenerateHaloFamilyParams:
    """Tests for generate_halo_family CLI parameters."""

    @pytest.fixture
    def entry(self) -> ScriptEntry:
        return _find_halo_family_entry()

    # --method 参数 --

    def test_method_param_exists(self, entry: ScriptEntry) -> None:
        """--method 参数存在。"""
        flags = [p.flag for p in entry.cli_params]
        assert "--method" in flags

    def test_method_default_is_pseudo_arclength(self, entry: ScriptEntry) -> None:
        param = next(p for p in entry.cli_params if p.flag == "--method")
        assert param.default == "伪弧长延拓"

    def test_method_choices_contain_pal(self, entry: ScriptEntry) -> None:
        param = next(p for p in entry.cli_params if p.flag == "--method")
        assert param.choices is not None
        assert "伪弧长延拓" in param.choices
        assert param.choice_values is not None
        assert param.choice_values["伪弧长延拓"] == "pseudo_arclength"

    def test_method_has_no_hidden_when(self, entry: ScriptEntry) -> None:
        param = next(p for p in entry.cli_params if p.flag == "--method")
        assert param.hidden_when is None

    # -- 共享参数无条件隐藏 --

    def test_direction_has_no_hidden_when(self, entry: ScriptEntry) -> None:
        direction_param = next(p for p in entry.cli_params if p.flag == "--direction")
        assert direction_param.hidden_when is None

    def test_z_min_has_no_hidden_when(self, entry: ScriptEntry) -> None:
        z_min_param = next(p for p in entry.cli_params if p.flag == "--z-min")
        assert z_min_param.hidden_when is None

    def test_z_max_has_no_hidden_when(self, entry: ScriptEntry) -> None:
        z_max_param = next(p for p in entry.cli_params if p.flag == "--z-max")
        assert z_max_param.hidden_when is None

    def test_n_orbits_has_no_hidden_when(self, entry: ScriptEntry) -> None:
        param = next(p for p in entry.cli_params if p.flag == "--n-orbits")
        assert param.hidden_when is None

    # -- PAL 专属参数 hidden_when --

    def test_step_size_pal_hidden_when_natural(self, entry: ScriptEntry) -> None:
        """PAL 步长在自然延拓方法下隐藏。"""
        param = next(p for p in entry.cli_params if p.flag == "--step-size-pal")
        assert param.hidden_when == "--method==natural"

    def test_step_size_negative_hidden_when_natural(self, entry: ScriptEntry) -> None:
        """负向支步长在自然延拓方法下隐藏。"""
        param = next(p for p in entry.cli_params if p.flag == "--step-size-negative")
        assert param.hidden_when == "--method==natural"

    # -- 自然延拓预留参数 hidden_when --

    def test_step_size_hidden_when_pal(self, entry: ScriptEntry) -> None:
        """--step-size 预留给自然延拓，PAL 方法下隐藏。"""
        param = next(p for p in entry.cli_params if p.flag == "--step-size")
        assert param.hidden_when == "--method==pseudo_arclength"

    # -- 其他不变属性 --

    def test_direction_default_is_both(self, entry: ScriptEntry) -> None:
        param = next(p for p in entry.cli_params if p.flag == "--direction")
        assert param.default == "both"

    def test_halo_class_help_no_longer_mentions_shared_crossing(self, entry: ScriptEntry) -> None:
        param = next(p for p in entry.cli_chip_params if p.flag == "--halo-class")
        assert "交叉轨道" not in param.help
        assert "独立" in param.help

    def test_description_updated(self, entry: ScriptEntry) -> None:
        assert "伪弧长延拓" not in entry.description
        assert entry.description == "生成 Halo 轨道族"
