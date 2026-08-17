"""tests for MainWindow 右边栏 -- 工具清单对齐 facade、分组、工具说明、重置按钮。

覆盖本轮右边栏更新：
- 工具下拉清单与 e2m2e facade mcp_tools 对齐，未接入工具灰显且 tooltip
  给出工具说明；
- 面板顶部展示当前工具说明（ToolSpec.description）；
- 参数按组展示（组表头 + 分隔线），轨道类型切换时整组隐藏；
- "重置参数"按钮重建面板恢复默认值；
- 新增轨道类型（DPO/Axial/SPO/LPO/HORSESHOE）分支可见性。
"""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture()
def qapp():
    try:
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app
    except ImportError:
        pytest.skip("QApplication 不可用")


def _make_window(qapp):
    """创建 MainWindow，mock 掉 discover_artifacts 避免扫描真实 output/。"""
    from src.app.main_window import MainWindow

    with patch("src.app.main_window.discover_artifacts", return_value=[]):
        return MainWindow()


class TestToolInventoryAlignment:
    def test_combo_lists_all_facade_tools(self, qapp):
        """工具下拉与 e2m2e facade 工具清单一致（含灰显的未接入工具）。"""
        from e2m2e.api import Facade, mcp_tools

        window = _make_window(qapp)
        keys = [
            window._tool_combo.itemData(i) for i in range(window._tool_combo.count())
        ]
        assert set(keys) == set(mcp_tools(Facade()))

    def test_enabled_first_and_default_selected(self, qapp):
        """enabled 工具排前，默认选中第一个 enabled（轨道设计）。"""
        window = _make_window(qapp)
        assert window._tool_combo.currentData() == "design_orbit"
        # 前三个是 enabled 工具
        assert window._tool_combo.itemData(0) == "design_orbit"
        assert window._tool_combo.itemData(1) == "control_orbit"
        assert window._tool_combo.itemData(2) == "orbit_family_generation"

    def test_disabled_items_have_description_tooltip(self, qapp):
        """灰显工具项的 tooltip 是工具说明（告知何时提供/占位状态）。"""
        from src.engine.facade_bridge import TOOL_REGISTRY

        window = _make_window(qapp)
        model = window._tool_combo.model()
        for i in range(window._tool_combo.count()):
            key = window._tool_combo.itemData(i)
            item = model.item(i)
            if item is None:
                continue
            spec = TOOL_REGISTRY[key]
            if not spec.enabled:
                assert not item.isEnabled()
                assert item.toolTip() == spec.description

    def test_tool_description_label_updates(self, qapp):
        """切换工具时面板顶部工具说明同步更新。"""
        from src.engine.facade_bridge import TOOL_REGISTRY

        window = _make_window(qapp)
        assert window._tool_desc_label.text() == TOOL_REGISTRY["design_orbit"].description

        idx = window._tool_combo.findData("orbit_family_generation")
        window._tool_combo.setCurrentIndex(idx)
        assert (
            window._tool_desc_label.text()
            == TOOL_REGISTRY["orbit_family_generation"].description
        )


class TestParamGroups:
    def test_design_groups(self, qapp):
        """design_orbit 面板含 形状参数/传播参数/修正参数 组表头。"""
        window = _make_window(qapp)
        assert set(window._group_headers) == {"形状参数", "传播参数", "修正参数"}

    def test_control_groups(self, qapp):
        """control_orbit 面板按控制、误差、力模型与角动量管理分组。"""
        window = _make_window(qapp)
        idx = window._tool_combo.findData("control_orbit")
        window._tool_combo.setCurrentIndex(idx)
        assert set(window._group_headers) == {"控制参数", "仿真与误差", "力模型", "角动量管理"}

    def test_family_panel_seven_families(self, qapp):
        """5.7.1 起族生成面板暴露七族下拉，sampling_mode 不进面板。"""
        window = _make_window(qapp)
        idx = window._tool_combo.findData("orbit_family_generation")
        window._tool_combo.setCurrentIndex(idx)
        assert set(window._group_headers) == {"族参数"}
        assert "sampling_mode" not in window._param_widgets
        orbit_combo = window._param_widgets["orbit_type"]
        assert [orbit_combo.itemText(i) for i in range(orbit_combo.count())] == [
            "Halo",
            "NRHO",
            "Axial",
            "Lissajous",
            "SPO",
            "LPO",
            "Horseshoe",
        ]

    def test_family_field_visibility_follows_type(self, qapp):
        """按族显示参数字段：Halo 只显示振幅上限；切三角族换成范围+延拓方向+容差。"""
        window = _make_window(qapp)
        idx = window._tool_combo.findData("orbit_family_generation")
        window._tool_combo.setCurrentIndex(idx)
        # 默认 Halo：max_amplitude_km 可见，三角族字段隐藏
        assert not window._param_rows["max_amplitude_km"][0].isHidden()
        assert window._param_rows["min_amplitude_km"][0].isHidden()
        assert window._param_rows["north_south"][0].isHidden()
        orbit_combo = window._param_widgets["orbit_type"]
        orbit_combo.setCurrentText("SPO")
        assert not window._param_rows["min_amplitude_km"][0].isHidden()
        assert not window._param_rows["match_tolerance_km"][0].isHidden()
        assert not window._param_rows["continuation_direction"][0].isHidden()
        assert window._param_rows["perilune_height_max_km"][0].isHidden()
        # 三角族平动点下拉为 L4/L5，且默认值已填入
        point_combo = window._param_widgets["libration_point"]
        assert [point_combo.itemData(i) for i in range(point_combo.count())] == [4, 5]
        assert point_combo.currentData() == 4
        # 切回 Halo：平动点回到 L1/L2
        orbit_combo.setCurrentText("Halo")
        point_combo = window._param_widgets["libration_point"]
        assert [point_combo.itemData(i) for i in range(point_combo.count())] == [1, 2]

    def test_family_request_params_filter(self, qapp):
        """族生成参数过滤：只留当前族适用字段，剔除隐藏分支残留值与 None。"""
        from src.app.main_window import _family_request_params

        params = {
            "orbit_type": "NRHO",
            "libration_point": 2,
            "n_orbits": 50,
            "north_south": 2,
            "perilune_height_max_km": 20000.0,
            # Halo 分支残留值与未勾选 Optional 的 None 都应被过滤
            "max_amplitude_km": 30000.0,
            "amplitude_in_km": None,
            "phase_in": None,
        }
        assert _family_request_params(params, "NRHO") == {
            "orbit_type": "NRHO",
            "libration_point": 2,
            "n_orbits": 50,
            "north_south": 2,
            "perilune_height_max_km": 20000.0,
        }

    def test_group_header_hidden_when_branch_fields_hidden(self, qapp):
        """ELFO 分支：形状参数组只剩 ELFO 字段（其余分支字段隐藏），组表头仍可见；
        切到 DRO 后形状参数组同样可见（含 amplitude/phase）。"""
        window = _make_window(qapp)
        orbit_combo = window._param_widgets["orbit_type"]
        orbit_combo.setCurrentText("ELFO")
        # ELFO 分支：semi_major_axis 可见，amplitude 隐藏
        assert not window._param_rows["semi_major_axis"][0].isHidden()
        assert window._param_rows["amplitude"][0].isHidden()
        # 形状参数组仍可见（ELFO 字段在该组）
        assert not window._group_headers["形状参数"][0].isHidden()
        # 修正参数组所有字段可见
        assert not window._group_headers["修正参数"][0].isHidden()

    def test_new_orbit_types_visible(self, qapp):
        """新增轨道类型（DPO/Axial/SPO/LPO/HORSESHOE）进入下拉且分支字段正确。"""
        from PyQt6.QtWidgets import QComboBox

        window = _make_window(qapp)
        combo = window._param_widgets["orbit_type"]
        assert isinstance(combo, QComboBox)
        items = [combo.itemText(i) for i in range(combo.count())]
        for name in (
            "DPO",
            "Axial",
            "L4_SPO",
            "L5_SPO",
            "L4_LPO",
            "L5_LPO",
            "L4_HORSESHOE",
            "L5_HORSESHOE",
        ):
            assert name in items

        combo.setCurrentText("DPO")
        assert not window._param_rows["amplitude"][0].isHidden()
        assert not window._param_rows["phase"][0].isHidden()
        assert window._param_rows["amplitude_in"][0].isHidden()

        combo.setCurrentText("Axial")
        assert not window._param_rows["collinear_point"][0].isHidden()
        assert not window._param_rows["amplitude"][0].isHidden()

        combo.setCurrentText("L4_SPO")
        assert not window._param_rows["amplitude"][0].isHidden()
        assert window._param_rows["amplitude_in"][0].isHidden()


class TestResetButton:
    def test_reset_restores_defaults(self, qapp):
        """重置按钮重建面板：修改后的值与单位选择恢复默认。"""
        from PyQt6.QtWidgets import QDoubleSpinBox

        from src.engine.facade_bridge import TOOL_REGISTRY
        from src.view.params_panel import collect_params

        window = _make_window(qapp)
        # 修改 amplitude 值 + 切单位到 DU
        amp = window._param_rows["amplitude"][1]
        assert isinstance(amp, QDoubleSpinBox)
        amp.setValue(12345.0)
        unit_combo = window._param_rows["amplitude"][2]
        unit_combo.setCurrentText("DU")

        window._on_reset_params()

        amp = window._param_rows["amplitude"][1]
        assert isinstance(amp, QDoubleSpinBox)
        assert amp.value() == pytest.approx(60000.0)  # DRO 默认恢复
        assert window._param_rows["amplitude"][2].currentText() == "km"
        params = collect_params(
            window._param_widgets, TOOL_REGISTRY["design_orbit"].request_model
        )
        assert params["amplitude"] == pytest.approx(60000.0)

    def test_reset_control_restores_interval(self, qapp):
        """control_orbit 面板重置后恢复 GUI 短弧默认（0.25/0.125 天）。"""
        window = _make_window(qapp)
        idx = window._tool_combo.findData("control_orbit")
        window._tool_combo.setCurrentIndex(idx)
        window._param_rows["control_interval"][1].setValue(1.0)
        window._param_rows["feedback_arc"][1].setValue(2.0)

        window._on_reset_params()

        assert window._param_rows["control_interval"][1].value() == pytest.approx(0.25)
        assert window._param_rows["feedback_arc"][1].value() == pytest.approx(0.125)
