"""Tests for generate_halo_family ScriptEntry — issue #123."""

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

    def test_has_method_param(self, entry: ScriptEntry) -> None:
        flags = [p.flag for p in entry.cli_params]
        assert "--method" in flags

        method_param = next(p for p in entry.cli_params if p.flag == "--method")
        assert method_param.choices == ("natural", "pseudo_arclength")
        assert method_param.default == "pseudo_arclength"

    def test_method_has_no_hidden_when(self, entry: ScriptEntry) -> None:
        method_param = next(p for p in entry.cli_params if p.flag == "--method")
        assert method_param.hidden_when is None

    def test_direction_has_hidden_when(self, entry: ScriptEntry) -> None:
        direction_param = next(p for p in entry.cli_params if p.flag == "--direction")
        assert direction_param.hidden_when == "--method==pseudo_arclength"

    def test_z_min_has_hidden_when(self, entry: ScriptEntry) -> None:
        z_min_param = next(p for p in entry.cli_params if p.flag == "--z-min")
        assert z_min_param.hidden_when == "--method==pseudo_arclength"

    def test_z_max_has_hidden_when(self, entry: ScriptEntry) -> None:
        z_max_param = next(p for p in entry.cli_params if p.flag == "--z-max")
        assert z_max_param.hidden_when == "--method==pseudo_arclength"

    def test_step_size_negative_has_hidden_when(self, entry: ScriptEntry) -> None:
        ssn_param = next(p for p in entry.cli_params if p.flag == "--step-size-negative")
        assert ssn_param.hidden_when == "--method==natural"

    def test_n_orbits_has_no_hidden_when(self, entry: ScriptEntry) -> None:
        param = next(p for p in entry.cli_params if p.flag == "--n-orbits")
        assert param.hidden_when is None

    def test_step_size_has_hidden_when(self, entry: ScriptEntry) -> None:
        param = next(p for p in entry.cli_params if p.flag == "--step-size")
        assert param.hidden_when == "--method==pseudo_arclength"

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
