# pyright: reportArgumentType=false, reportOptionalMemberAccess=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false
"""RunPlan + build_run_plan 数据层测试。

覆盖 4 类核心场景（issue #181 验收点）：
1. 当前选择文件注入摘要
2. 批量运行摘要（按第一个 chip 分组）
3. 覆盖目标摘要
4. 取消 / 普通 run 不破坏既有行为

PR1 范围：纯数据层 + RunPlan 类型。RunConfirmationDialog（UI 层）测试在 PR2。
"""

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QPushButton, QTableWidget, QWidget

from tod.scripting import (
    CliChipParam,
    CliParam,
    MultiCliParam,
    PerFileField,
    ScriptEntry,
)


# ── Fixtures & helpers ──────────────────────────────────────


def _make_entry(**overrides: Any) -> ScriptEntry:
    """本地 entry 构造 helper（参考 test_run_orchestrator.py 风格）。"""
    defaults: dict[str, Any] = dict(
        module="halo",
        name="test_script",
        description="test description",
        script_path="tod/generates/cr3bp/halo/test_script.py",
    )
    defaults.update(overrides)
    return ScriptEntry(**defaults)


@pytest.fixture
def qapp_fixture():
    return QApplication.instance() or QApplication([])


def _make_tab(qapp_fixture, tmp_path, entry: ScriptEntry) -> QWidget:
    from tod.gui.script_tab_widget import ScriptTabWidget

    return ScriptTabWidget(
        entry=entry,
        files=[],
        repo_root=tmp_path,
        gui_defaults={},
        theme_mode="system",
    )


def _select_chip(tab: QWidget, chip_key: str, labels: list[str]) -> None:
    container = tab._store._chip_widgets[chip_key]
    chip_buttons: dict[str, QPushButton] = container._chip_buttons  # type: ignore[attr-defined]
    for label, btn in chip_buttons.items():
        target_state = label in labels
        if btn.property("_selected") != target_state:
            btn.click()


def _add_multi_file_row(tab: QWidget, multi_key: str, path: str) -> None:
    widget = tab._store._multi_file_widgets[multi_key]
    table = widget.findChild(QTableWidget)
    assert table is not None, "multi-file widget 未生成 QTableWidget"

    row = table.rowCount()
    table.insertRow(row)
    name_item = table.item(row, 0)
    if name_item is None:
        from PyQt6.QtWidgets import QTableWidgetItem
        name_item = QTableWidgetItem()
        table.setItem(row, 0, name_item)
    name_item.setData(Qt.ItemDataRole.UserRole, path)
    name_item.setText(os.path.basename(path))


# ── 类型导入测试（确保 RunPlan / OverwriteTarget / ChipGroup 公开） ───


class TestRunPlanTypes:
    def test_run_plan_module_exports_plan_types(self):
        """RunPlan / OverwriteTarget / ChipGroup 应当从 tod.gui.run.run_orchestrator 可导入。"""
        from tod.gui.run.run_orchestrator import (
            ChipGroup,
            OverwriteTarget,
            RunPlan,
        )

        assert RunPlan is not None
        assert OverwriteTarget is not None
        assert ChipGroup is not None

    def test_run_plan_is_frozen_dataclass(self):
        from dataclasses import FrozenInstanceError, fields
        from tod.gui.run.run_orchestrator import RunPlan

        # frozen=True 应当保证字段不可写
        plan = RunPlan(
            specs=(),
            file_input=None,
            overwrites=(),
            chip_groups=(),
            has_output_file_param=False,
            total_tasks=0,
            entry=_make_entry(),
        )
        with pytest.raises(FrozenInstanceError):
            plan.total_tasks = 99  # type: ignore[misc]

    def test_overwrite_target_is_frozen(self):
        from dataclasses import FrozenInstanceError
        from tod.gui.run.run_orchestrator import OverwriteTarget

        target = OverwriteTarget(path="/abs/x.json", shared_count=2)
        with pytest.raises(FrozenInstanceError):
            target.shared_count = 99  # type: ignore[misc]

    def test_chip_group_is_frozen(self):
        from dataclasses import FrozenInstanceError
        from tod.gui.run.run_orchestrator import ChipGroup, RunSpec

        group = ChipGroup(
            group_key="--libration-point",
            group_value="L1",
            specs=(),
        )
        with pytest.raises(FrozenInstanceError):
            group.group_value = "L2"  # type: ignore[misc]


# ── 验收点 1：当前选择文件注入摘要 ──────────────────────────


class TestFileInputInjection:
    def test_file_input_none_when_no_arg(self, qapp_fixture, tmp_path):
        """entry.accepts_file_arg=False 或 file_arg=None 时，plan.file_input 应为 None。"""
        from tod.gui.run.run_orchestrator import RunOrchestrator

        entry = _make_entry()  # accepts_file_arg=False (default)
        tab = _make_tab(qapp_fixture, tmp_path, entry)

        plan = RunOrchestrator.build_run_plan(
            tab=tab, file_arg=None, plot_env={}, repo_root=tmp_path
        )

        assert plan.file_input is None
        assert plan.total_tasks == 1

    def test_file_input_recorded_when_provided(self, qapp_fixture, tmp_path):
        """file_arg 非空时，plan.file_input 应记录绝对路径字符串。"""
        from tod.gui.run.run_orchestrator import RunOrchestrator

        entry = _make_entry(accepts_file_arg=True)
        tab = _make_tab(qapp_fixture, tmp_path, entry)
        abs_path = "/abs/path/orbit.json"

        plan = RunOrchestrator.build_run_plan(
            tab=tab,
            file_arg=["--file", abs_path],
            plot_env={},
            repo_root=tmp_path,
        )

        assert plan.file_input == abs_path


# ── 验收点 2：批量运行摘要（按第一个 chip 分组）──────────────


class TestBatchRunGrouping:
    def test_single_task_no_grouping(self, qapp_fixture, tmp_path):
        """单任务时 chip_groups 应为空元组（无分组）。"""
        from tod.gui.run.run_orchestrator import RunOrchestrator

        entry = _make_entry()  # 无 chip
        tab = _make_tab(qapp_fixture, tmp_path, entry)

        plan = RunOrchestrator.build_run_plan(
            tab=tab, file_arg=None, plot_env={}, repo_root=tmp_path
        )

        assert plan.total_tasks == 1
        assert plan.chip_groups == ()

    def test_two_chips_l1_l2_yield_two_groups(self, qapp_fixture, tmp_path):
        """选 L1 + L2 时，chip_groups 应有 2 个 ChipGroup（按第一个 chip 分组）。"""
        from tod.gui.run.run_orchestrator import RunOrchestrator

        entry = _make_entry(
            cli_chip_params=[
                CliChipParam(
                    "--libration-point",
                    "平动点",
                    options={"L1": "1", "L2": "2"},
                )
            ]
        )
        tab = _make_tab(qapp_fixture, tmp_path, entry)
        _select_chip(tab, "libration_point", ["L1", "L2"])

        plan = RunOrchestrator.build_run_plan(
            tab=tab, file_arg=None, plot_env={}, repo_root=tmp_path
        )

        assert plan.total_tasks == 2
        assert len(plan.chip_groups) == 2
        # chip 的 group_value 是 CLI 值（"1"/"2"），不是显示标签（"L1"/"L2"）
        group_values = {g.group_value for g in plan.chip_groups}
        assert group_values == {"1", "2"}
        for group in plan.chip_groups:
            assert group.group_key == "--libration-point"
            assert len(group.specs) == 1

    def test_first_chip_unselected_falls_back_to_no_grouping(
        self, qapp_fixture, tmp_path
    ):
        """当第一个 chip 用户未选、第二个 chip 选了一个时，chip_groups 应降级为空。"""
        from tod.gui.run.run_orchestrator import RunOrchestrator

        entry = _make_entry(
            cli_chip_params=[
                CliChipParam(
                    "--libration-point",
                    "平动点",
                    options={"L1": "1", "L2": "2"},
                ),
                CliChipParam(
                    "--ratio",
                    "共振比",
                    options={"3:1": "1", "3:2": "2"},
                ),
            ]
        )
        tab = _make_tab(qapp_fixture, tmp_path, entry)
        # 用户没选第一个 chip (libration_point)，只选了第二个的 3:1
        _select_chip(tab, "ratio", ["3:1"])

        plan = RunOrchestrator.build_run_plan(
            tab=tab, file_arg=None, plot_env={}, repo_root=tmp_path
        )

        assert plan.total_tasks == 1
        # 降级：第一个 chip 没被选，不分组
        assert plan.chip_groups == ()


# ── 验收点 3：覆盖目标摘要 ──────────────────────────────


class TestOverwriteDetection:
    def test_no_output_file_param_yields_empty_overwrites(
        self, qapp_fixture, tmp_path
    ):
        """无 kind=file_output 的 CliParam 时，overwrites 应为空。"""
        from tod.gui.run.run_orchestrator import RunOrchestrator

        entry = _make_entry()  # 无 output file param
        tab = _make_tab(qapp_fixture, tmp_path, entry)

        plan = RunOrchestrator.build_run_plan(
            tab=tab, file_arg=None, plot_env={}, repo_root=tmp_path
        )

        assert plan.overwrites == ()
        assert plan.has_output_file_param is False

    def test_output_file_pointing_to_existing_file_yields_overwrite(
        self, qapp_fixture, tmp_path
    ):
        """--output-file 指向 repo_root 下的已存在文件时，overwrites 应记录该路径。"""
        from tod.gui.run.run_orchestrator import RunOrchestrator

        existing = tmp_path / "existing.json"
        existing.write_text("{}")

        entry = _make_entry(
            cli_params=[
                CliParam(
                    "--output-file",
                    "输出文件",
                    "str",
                    default="",  # 出厂空
                    kind="file_output",
                )
            ]
        )
        tab = _make_tab(qapp_fixture, tmp_path, entry)
        # 用户在 QLineEdit 里填入已存在文件路径（与 default 不同，触发 collect）
        tab._store._cli_widgets["output_file"].setText(str(existing))  # type: ignore[attr-defined]

        plan = RunOrchestrator.build_run_plan(
            tab=tab, file_arg=None, plot_env={}, repo_root=tmp_path
        )

        assert plan.has_output_file_param is True
        assert len(plan.overwrites) == 1
        assert plan.overwrites[0].path == str(existing)
        assert plan.overwrites[0].shared_count == 1

    def test_output_file_pointing_to_missing_file_yields_no_overwrite(
        self, qapp_fixture, tmp_path
    ):
        """--output-file 指向不存在文件时，overwrites 应为空（这是"将创建"不是"将覆盖"）。"""
        from tod.gui.run.run_orchestrator import RunOrchestrator

        missing = tmp_path / "missing.json"
        assert not missing.exists()

        entry = _make_entry(
            cli_params=[
                CliParam(
                    "--output-file",
                    "输出文件",
                    "str",
                    default="",
                    kind="file_output",
                )
            ]
        )
        tab = _make_tab(qapp_fixture, tmp_path, entry)
        tab._store._cli_widgets["output_file"].setText(str(missing))  # type: ignore[attr-defined]

        plan = RunOrchestrator.build_run_plan(
            tab=tab, file_arg=None, plot_env={}, repo_root=tmp_path
        )

        assert plan.has_output_file_param is True
        assert plan.overwrites == ()

    def test_output_file_empty_value_yields_no_overwrite(
        self, qapp_fixture, tmp_path
    ):
        """--output-file 用户清空时（空字符串），应视为"未指定输出文件"。"""
        from tod.gui.run.run_orchestrator import RunOrchestrator

        entry = _make_entry(
            cli_params=[
                CliParam(
                    "--output-file",
                    "输出文件",
                    "str",
                    default="",  # 用户清空
                    kind="file_output",
                )
            ]
        )
        tab = _make_tab(qapp_fixture, tmp_path, entry)

        plan = RunOrchestrator.build_run_plan(
            tab=tab, file_arg=None, plot_env={}, repo_root=tmp_path
        )

        assert plan.has_output_file_param is True  # 参数存在
        assert plan.overwrites == ()  # 但用户没填值

    def test_relative_output_file_path_resolved_against_repo_root(
        self, qapp_fixture, tmp_path
    ):
        """--output-file 相对路径应相对于 repo_root 解析（与子进程 cwd 行为对齐）。"""
        from tod.gui.run.run_orchestrator import RunOrchestrator

        existing_rel = tmp_path / "rel_existing.json"
        existing_rel.write_text("{}")

        entry = _make_entry(
            cli_params=[
                CliParam(
                    "--output-file",
                    "输出文件",
                    "str",
                    default="",
                    kind="file_output",
                )
            ]
        )
        tab = _make_tab(qapp_fixture, tmp_path, entry)
        tab._store._cli_widgets["output_file"].setText("rel_existing.json")  # type: ignore[attr-defined]

        plan = RunOrchestrator.build_run_plan(
            tab=tab, file_arg=None, plot_env={}, repo_root=tmp_path
        )

        assert len(plan.overwrites) == 1
        assert plan.overwrites[0].path == "rel_existing.json"

    def test_shared_overwrite_count_aggregated(self, qapp_fixture, tmp_path):
        """多个 spec 共享同一输出文件时，shared_count 应汇总。"""
        from tod.gui.run.run_orchestrator import RunOrchestrator

        existing = tmp_path / "shared.json"
        existing.write_text("{}")

        entry = _make_entry(
            cli_chip_params=[
                CliChipParam(
                    "--libration-point",
                    "平动点",
                    options={"L1": "1", "L2": "2"},
                )
            ],
            cli_params=[
                CliParam(
                    "--output-file",
                    "输出文件",
                    "str",
                    default="",
                    kind="file_output",
                )
            ],
        )
        tab = _make_tab(qapp_fixture, tmp_path, entry)
        _select_chip(tab, "libration_point", ["L1", "L2"])
        tab._store._cli_widgets["output_file"].setText(str(existing))  # type: ignore[attr-defined]

        plan = RunOrchestrator.build_run_plan(
            tab=tab, file_arg=None, plot_env={}, repo_root=tmp_path
        )

        assert plan.total_tasks == 2
        assert len(plan.overwrites) == 1
        assert plan.overwrites[0].shared_count == 2


# ── 验收点 4：普通 run 不破坏既有行为 ──────────────────────


class TestNoRegressionForSimpleRun:
    def test_simple_run_with_only_file_arg(self, qapp_fixture, tmp_path):
        """无 chip、无 multi-file 的普通 run 应产出 1 个 spec，args 与 build_run_specs 一致。"""
        from tod.gui.run.run_orchestrator import RunOrchestrator

        entry = _make_entry(
            accepts_file_arg=True,
            cli_params=[
                CliParam("--orbit-index", "轨道索引", "int", default="3"),
            ],
        )
        tab = _make_tab(qapp_fixture, tmp_path, entry)
        tab._store._cli_widgets["orbit_index"].setValue(5)  # type: ignore[attr-defined]

        plan = RunOrchestrator.build_run_plan(
            tab=tab,
            file_arg=["--file", "/abs/orbit.json"],
            plot_env={},
            repo_root=tmp_path,
        )

        assert plan.total_tasks == 1
        assert len(plan.specs) == 1
        # --file 应在 args 头部（与 build_run_specs 行为一致）
        args = list(plan.specs[0].args)
        assert args[0] == "--file"
        assert args[1] == "/abs/orbit.json"
        assert "--orbit-index" in args
        assert "5" in args

    def test_build_run_specs_still_works_unchanged(self, qapp_fixture, tmp_path):
        """build_run_specs 应当继续工作（不影响现有 11 个测试）。"""
        from tod.gui.run.run_orchestrator import RunOrchestrator

        entry = _make_entry(
            cli_params=[
                CliParam("--verbose", "详细输出", "bool"),
            ]
        )
        tab = _make_tab(qapp_fixture, tmp_path, entry)
        tab._store._cli_widgets["verbose"].setChecked(True)  # type: ignore[attr-defined]

        specs = RunOrchestrator.build_run_specs(
            tab=tab, file_arg=None, plot_env={}
        )

        assert len(specs) == 1
        assert "--verbose" in list(specs[0].args)
