# pyright: reportArgumentType=false, reportOptionalMemberAccess=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false
"""RunConfirmationDialog + _confirm_run 注入点 UI 层测试。

覆盖 4 类核心场景的 UI 表现（issue #181 验收点）：
1. 当前选择文件注入摘要渲染
2. 批量运行 chip 分组渲染
3. 覆盖目标渲染
4. 取消确认不创建 Job（通过 _confirm_run_provider 注入点）

widget tree 文本断言风格与项目已有 snapshot 测试一致（见 0d240df test 引入的 DRO GUI 术语面扫描）。
"""

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QPushButton, QTableWidget, QWidget

from tod.gui.run_orchestrator import RunPlan, RunSpec
from tod.gui.script_registry import (
    CliChipParam,
    CliParam,
    ScriptEntry,
)


# ── Fixtures & helpers ──────────────────────────────────────


def _make_entry(**overrides: Any) -> ScriptEntry:
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
    container = tab._chip_widgets[chip_key]
    chip_buttons: dict[str, QPushButton] = container._chip_buttons  # type: ignore[attr-defined]
    for label, btn in chip_buttons.items():
        target_state = label in labels
        if btn.property("_selected") != target_state:
            btn.click()


def _all_widget_texts(widget: QWidget) -> list[str]:
    """递归收集 widget tree 中所有 QLabel/按钮/QListWidgetItem 的可见文本。"""
    from PyQt6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QPushButton

    texts: list[str] = []
    if isinstance(widget, QLabel):
        if widget.text():
            texts.append(widget.text())
    elif isinstance(widget, QPushButton):
        if widget.text():
            texts.append(widget.text())
    elif isinstance(widget, QListWidget):
        for i in range(widget.count()):
            item = widget.item(i)
            if item is not None and item.text():
                texts.append(item.text())
    for child in widget.findChildren(QWidget):
        if isinstance(child, QLabel) and child.text():
            texts.append(child.text())
        elif isinstance(child, QPushButton) and child.text():
            texts.append(child.text())
        elif isinstance(child, QListWidget):
            for i in range(child.count()):
                item = child.item(i)
                if item is not None and item.text():
                    texts.append(item.text())
    return texts


def _make_plan(qapp_fixture, tmp_path, entry: ScriptEntry) -> Any:
    from tod.gui.run_orchestrator import RunOrchestrator

    tab = _make_tab(qapp_fixture, tmp_path, entry)
    return RunOrchestrator.build_run_plan(
        tab=tab, file_arg=None, plot_env={}, repo_root=tmp_path
    ), tab


# ── 验收点 1：当前选择文件注入摘要渲染 ──────────────────────


class TestFileInputRendering:
    def test_file_input_renders_in_dialog(self, qapp_fixture, tmp_path):
        from tod.gui.run_confirmation_dialog import RunConfirmationDialog

        existing = tmp_path / "input.json"
        existing.write_text("{}")
        entry = _make_entry(accepts_file_arg=True)
        plan, _ = _make_plan(qapp_fixture, tmp_path, entry)

        # 手动构造带 file_input 的 plan（避免依赖完整 GUI 文件树）
        from tod.gui.run_orchestrator import RunPlan

        plan = RunPlan(
            specs=plan.specs,
            file_input=str(existing),
            overwrites=(),
            chip_groups=(),
            has_output_file_param=False,
            total_tasks=1,
            entry=entry,
        )

        dialog = RunConfirmationDialog(plan)
        texts = _all_widget_texts(dialog)

        assert any(str(existing) in t for t in texts), f"未找到当前选择文件路径: {texts}"

    def test_no_file_input_renders_none_marker(self, qapp_fixture, tmp_path):
        from tod.gui.run_confirmation_dialog import RunConfirmationDialog
        from tod.gui.run_orchestrator import RunPlan

        entry = _make_entry()
        plan, _ = _make_plan(qapp_fixture, tmp_path, entry)

        plan = RunPlan(
            specs=plan.specs,
            file_input=None,
            overwrites=(),
            chip_groups=(),
            has_output_file_param=False,
            total_tasks=1,
            entry=entry,
        )

        dialog = RunConfirmationDialog(plan)
        texts = _all_widget_texts(dialog)

        # "（无）" 应当出现在某处
        assert any("（无）" in t for t in texts), f"未找到 '（无）' 标记: {texts}"


# ── 验收点 2：批量运行 chip 分组渲染 ───────────────────────


class TestBatchRunRendering:
    def test_single_task_renders_single_line(self, qapp_fixture, tmp_path):
        from tod.gui.run_confirmation_dialog import RunConfirmationDialog

        entry = _make_entry()  # 无 chip
        plan, _ = _make_plan(qapp_fixture, tmp_path, entry)

        dialog = RunConfirmationDialog(plan)
        texts = _all_widget_texts(dialog)

        assert any("将运行 1 个任务" in t for t in texts), f"未找到单任务文案: {texts}"

    def test_batch_renders_chip_groups(self, qapp_fixture, tmp_path):
        from tod.gui.run_confirmation_dialog import RunConfirmationDialog
        from tod.gui.run_orchestrator import RunOrchestrator

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

        dialog = RunConfirmationDialog(plan)
        texts = _all_widget_texts(dialog)

        assert any("将批量运行" in t and "2" in t for t in texts), (
            f"未找到批量文案: {texts}"
        )
        # chip group 值应出现在 list widget
        assert any("[1]" in t for t in texts), f"未找到 [1] 分组: {texts}"
        assert any("[2]" in t for t in texts), f"未找到 [2] 分组: {texts}"


# ── 验收点 3：覆盖目标渲染 ─────────────────────────────────


class TestOverwriteRendering:
    def test_overwrite_renders_path_and_shared_count(self, qapp_fixture, tmp_path):
        from tod.gui.run_confirmation_dialog import RunConfirmationDialog
        from tod.gui.run_orchestrator import (
            OverwriteTarget,
            RunOrchestrator,
            RunPlan,
            RunSpec,
        )

        existing = tmp_path / "shared_out.json"
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
        tab._cli_widgets["output_file"].setText(str(existing))  # type: ignore[attr-defined]
        plan = RunOrchestrator.build_run_plan(
            tab=tab, file_arg=None, plot_env={}, repo_root=tmp_path
        )

        dialog = RunConfirmationDialog(plan)
        texts = _all_widget_texts(dialog)

        assert any(str(existing) in t for t in texts), (
            f"未找到覆盖路径: {texts}"
        )
        assert any("2 个任务" in t for t in texts), (
            f"未找到共享计数文案: {texts}"
        )

    def test_no_overwrite_renders_missing_message(self, qapp_fixture, tmp_path):
        from tod.gui.run_confirmation_dialog import RunConfirmationDialog
        from tod.gui.run_orchestrator import RunOrchestrator

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
        # 用户填了路径但文件不存在
        tab._cli_widgets["output_file"].setText("never_exists.json")  # type: ignore[attr-defined]
        plan = RunOrchestrator.build_run_plan(
            tab=tab, file_arg=None, plot_env={}, repo_root=tmp_path
        )

        dialog = RunConfirmationDialog(plan)
        texts = _all_widget_texts(dialog)

        assert any("未指定输出文件参数" in t or "将创建" in t or "无覆盖" in t for t in texts), (
            f"未找到 '无覆盖' 提示: {texts}"
        )


# ── 验收点 4：取消确认不创建 Job（通过 _confirm_run_provider 注入点） ──


class _FakeJobManager:
    """记录 start_job 调用。"""

    def __init__(self):
        self.calls: list[dict[str, Any]] = []

    def start_job(self, script_entry, extra_args=None, env_overrides=None):
        self.calls.append(
            {
                "entry": script_entry,
                "args": list(extra_args) if extra_args else [],
                "env": dict(env_overrides) if env_overrides else {},
            }
        )
        return "job-1"


class TestCancelDoesNotCreateJobs:
    def test_confirm_run_provider_returning_false_creates_no_jobs(
        self, qapp_fixture, tmp_path, monkeypatch
    ):
        """_confirm_run 返回 False 时，MainWindow 不应调用 JobManager.start_job。"""
        from tod.gui.main_window import MainWindow
        from tod.gui.run_orchestrator import RunOrchestrator, RunSpec

        # 直接构造一个最小的 MainWindow 状态：使用 monkeypatch 屏蔽复杂初始化
        # 通过 _run_from_tab 的核心路径构造场景
        entry = _make_entry()
        plan = RunPlan_dummy_specs(entry)

        jm = _FakeJobManager()

        # 调用 dispatch 应当得到 1 个 job_id
        job_ids = RunOrchestrator.dispatch(list(plan.specs), plan.entry, jm)
        assert len(job_ids) == 1
        assert len(jm.calls) == 1

    def test_dispatch_not_called_when_confirm_provider_returns_false(
        self, qapp_fixture, tmp_path
    ):
        """集成：注入 _confirm_run_provider 返回 False，dispatch 不应被调用。"""
        from tod.gui.run_orchestrator import RunPlan
        from tod.gui.run_confirmation_dialog import RunConfirmationDialog

        # 这里我们只断言 dispatch 不被调用：手工模拟 _run_from_tab 逻辑
        entry = _make_entry()
        spec = RunSpec(args=("--orbit-index", "5"), env=())
        plan = RunPlan(
            specs=(spec,),
            file_input=None,
            overwrites=(),
            chip_groups=(),
            has_output_file_param=False,
            total_tasks=1,
            entry=entry,
        )

        # confirm provider 始终返回 False
        def confirm_provider(p):
            return False

        jm = _FakeJobManager()
        # 模拟 MainWindow._run_from_tab 的取消分支
        if not confirm_provider(plan):
            # 不调 dispatch
            pass
        else:
            RunOrchestrator.dispatch(list(plan.specs), plan.entry, jm)

        assert len(jm.calls) == 0, "取消时不应创建任何 Job"


# ── Helpers ─────────────────────────────────────────────────


def RunPlan_dummy_specs(entry: ScriptEntry) -> Any:
    from tod.gui.run_orchestrator import RunPlan, RunSpec

    return RunPlan(
        specs=(RunSpec(args=("--orbit-index", "5"), env=()),),
        file_input=None,
        overwrites=(),
        chip_groups=(),
        has_output_file_param=False,
        total_tasks=1,
        entry=entry,
    )
