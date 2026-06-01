"""Tests for generate_halo_family ScriptEntry.

Halo family generator uses method-based parameter visibility:
- PAL mode: step-size-pal, n-orbits
- Natural mode: step-size, z-min, z-max
- Removed: --direction (hardcoded "both"), --step-size-negative (unused)
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

    # -- 已删除参数 --

    def test_direction_not_in_params(self, entry: ScriptEntry) -> None:
        """--direction 已删除（硬编码 "both"）。"""
        flags = [p.flag for p in entry.cli_params]
        assert "--direction" not in flags

    def test_step_size_negative_not_in_params(self, entry: ScriptEntry) -> None:
        """--step-size-negative 已删除（无用参数）。"""
        flags = [p.flag for p in entry.cli_params]
        assert "--step-size-negative" not in flags

    # -- PAL 专属参数 hidden_when --

    def test_step_size_pal_hidden_when_natural(self, entry: ScriptEntry) -> None:
        """PAL 步长在自然延拓方法下隐藏。"""
        param = next(p for p in entry.cli_params if p.flag == "--step-size-pal")
        assert param.hidden_when == "--method==natural"

    # -- 自然延拓预留参数 hidden_when --

    def test_step_size_hidden_when_pal(self, entry: ScriptEntry) -> None:
        """--step-size 预留给自然延拓，PAL 方法下隐藏。"""
        param = next(p for p in entry.cli_params if p.flag == "--step-size")
        assert param.hidden_when == "--method==pseudo_arclength"

    # -- 方法分流：PAL 参数 --

    def test_n_orbits_hidden_when_natural(self, entry: ScriptEntry) -> None:
        """PAL 模式下 n-orbits 可见，Natural 下隐藏。"""
        param = next(p for p in entry.cli_params if p.flag == "--n-orbits")
        assert param.hidden_when == "--method==natural"

    # -- 方法分流：Natural 参数 --

    def test_z_min_hidden_when_pal(self, entry: ScriptEntry) -> None:
        """z-min 仅在 Natural 模式下显示。"""
        param = next(p for p in entry.cli_params if p.flag == "--z-min")
        assert param.hidden_when == "--method==pseudo_arclength"

    def test_z_max_hidden_when_pal(self, entry: ScriptEntry) -> None:
        """z-max 仅在 Natural 模式下显示。"""
        param = next(p for p in entry.cli_params if p.flag == "--z-max")
        assert param.hidden_when == "--method==pseudo_arclength"

    # -- 默认值 --

    def test_amplitude_z_default_is_0_001(self, entry: ScriptEntry) -> None:
        """种子振幅默认 0.001（小种子利于 Richardson 收敛）。"""
        param = next(p for p in entry.cli_params if p.flag == "--amplitude-z")
        assert param.default == "0.001"

    def test_z_min_default_is_empty(self, entry: ScriptEntry) -> None:
        """z-min 默认空，不启用 z_range 模式。"""
        param = next(p for p in entry.cli_params if p.flag == "--z-min")
        assert param.default == ""

    def test_z_max_default_is_empty(self, entry: ScriptEntry) -> None:
        """z-max 默认空，不启用 z_range 模式。"""
        param = next(p for p in entry.cli_params if p.flag == "--z-max")
        assert param.default == ""

    def test_libration_point_options_are_l1_l2_only(self, entry: ScriptEntry) -> None:
        """Halo family 不应提供 L3 平动点选项。"""
        param = next(p for p in entry.cli_chip_params if p.flag == "--libration-point")
        assert param.options == {"L1": "L1", "L2": "L2"}

    def test_seed_file_pattern_excludes_l3_halo_seeds(self, entry: ScriptEntry) -> None:
        """种子文件选择器不应提供 L3 Halo 种子。"""
        param = next(p for p in entry.cli_params if p.flag == "--seed-file")
        assert param.name_pattern == "halo_L[12]_[NS]_[0-9]*.json"

    # -- 其他不变属性 --

    def test_halo_class_help_no_longer_mentions_shared_crossing(self, entry: ScriptEntry) -> None:
        param = next(p for p in entry.cli_chip_params if p.flag == "--halo-class")
        assert "交叉轨道" not in param.help
        assert "独立" in param.help

    def test_description_updated(self, entry: ScriptEntry) -> None:
        assert "伪弧长延拓" not in entry.description
        assert entry.description == "生成 Halo 轨道族"
