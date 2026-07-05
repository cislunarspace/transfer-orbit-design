# pyright: reportArgumentType=false, reportOptionalMemberAccess=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false
"""RunOrchestrator — build_run_specs 与 dispatch 的接口测试。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QCheckBox, QPushButton, QSpinBox, QTableWidget, QWidget

from tod.scripting import (
    CliChipParam,
    CliParam,
    MultiCliParam,
    PerFileField,
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
    app = QApplication.instance() or QApplication([])
    return app


def _make_tab(qapp_fixture, tmp_path, entry: ScriptEntry) -> QWidget:
    """构造最小 ScriptTabWidget，注入 qapp + 临时 repo_root。"""
    from tod.gui.script_tab_widget import ScriptTabWidget

    return ScriptTabWidget(
        entry=entry,
        files=[],
        repo_root=tmp_path,
        gui_defaults={},
        theme_mode="system",
    )


def _select_chip(tab: QWidget, chip_key: str, labels: list[str]) -> None:
    """在 ScriptTabWidget._chip_widgets 中切换 chip 按钮状态。"""
    container = tab._chip_widgets[chip_key]
    chip_buttons: dict[str, QPushButton] = container._chip_buttons  # type: ignore[attr-defined]
    for label, btn in chip_buttons.items():
        target_state = label in labels
        if btn.property("_selected") != target_state:
            btn.click()


def _add_multi_file_row(tab: QWidget, multi_key: str, path: str) -> None:
    """向 ScriptTabWidget 的多文件表格注入一行（path, start, end, step）。"""
    widget = tab._multi_file_widgets[multi_key]
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


class _FakeJobManager:
    """Record start_job calls so we can assert dispatch behavior."""

    def __init__(self):
        self.calls: list[dict[str, Any]] = []
        self._counter = 0

    def start_job(self, script_entry, extra_args=None, env_overrides=None):
        self._counter += 1
        job_id = f"job-{self._counter}"
        self.calls.append(
            {
                "entry": script_entry,
                "args": list(extra_args) if extra_args else [],
                "env": dict(env_overrides) if env_overrides else {},
            }
        )
        return job_id


# ── Tests ────────────────────────────────────────────────────


class TestBuildRunSpecsBasic:
    def test_no_chips_returns_single_spec_with_all_non_default_args(
        self, qapp_fixture, tmp_path
    ):
        from tod.gui.run_orchestrator import RunOrchestrator

        entry = _make_entry(
            cli_params=[
                CliParam("--verbose", "详细输出", "bool"),
                CliParam("--orbit-index", "轨道索引", "int", default="3"),
            ]
        )
        tab = _make_tab(qapp_fixture, tmp_path, entry)

        # verbose=True 触发 flag；--orbit-index 改为 5（非默认 3）。
        assert isinstance(tab._cli_widgets["verbose"], QCheckBox)
        assert isinstance(tab._cli_widgets["orbit_index"], QSpinBox)
        tab._cli_widgets["verbose"].setChecked(True)  # type: ignore[attr-defined]
        tab._cli_widgets["orbit_index"].setValue(5)  # type: ignore[attr-defined]

        specs = RunOrchestrator.build_run_specs(
            tab=tab, file_arg=None, plot_env={}
        )

        assert len(specs) == 1
        args = list(specs[0].args)
        # 默认值不出现（"orbit_index" 已被改成 5），verbose flag 出现
        assert "--verbose" in args
        assert "5" in args
        # 出现形式：["--verbose", "--orbit-index", "5"]（顺序无关，但应是 flag+value 对）
        assert args.index("--verbose") < args.index("5")
        assert "--orbit-index" in args
        # 没有 --file 注入
        assert "--file" not in args

    def test_no_chips_omits_default_int_value(self, qapp_fixture, tmp_path):
        """int 参数保持出厂默认时不应出现在 args 中。"""
        from tod.gui.run_orchestrator import RunOrchestrator

        entry = _make_entry(
            cli_params=[
                CliParam("--orbit-index", "轨道索引", "int", default="3"),
            ]
        )
        tab = _make_tab(qapp_fixture, tmp_path, entry)

        specs = RunOrchestrator.build_run_specs(
            tab=tab, file_arg=None, plot_env={}
        )

        assert len(specs) == 1
        args = list(specs[0].args)
        assert "--orbit-index" not in args
        assert "3" not in args


class TestBuildRunSpecsChipExpansion:
    def test_l1_and_l2_selected_yields_two_specs(
        self, qapp_fixture, tmp_path
    ):
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

        specs = RunOrchestrator.build_run_specs(
            tab=tab, file_arg=None, plot_env={}
        )

        assert len(specs) == 2
        arg_lists = [list(s.args) for s in specs]
        # 每个 spec 各自带一个 --libration-point 值
        flags_with_values = [
            (args[args.index("--libration-point") + 1] if "--libration-point" in args else None)
            for args in arg_lists
        ]
        assert "1" in flags_with_values
        assert "2" in flags_with_values
        # 没有任何 spec 同时出现 "1" 和 "2"
        for args in arg_lists:
            count = sum(1 for v in ("1", "2") if v in args)
            assert count == 1, f"期望每个 spec 只有一个 chip 值，args={args}"

    def test_no_chip_selected_returns_single_spec(
        self, qapp_fixture, tmp_path
    ):
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
        # 故意不点选任何 chip

        specs = RunOrchestrator.build_run_specs(
            tab=tab, file_arg=None, plot_env={}
        )
        assert len(specs) == 1
        assert "--libration-point" not in specs[0].args


class TestBuildRunSpecsFileArgAndEnv:
    def test_file_arg_prepended_to_every_spec(self, qapp_fixture, tmp_path):
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

        specs = RunOrchestrator.build_run_specs(
            tab=tab,
            file_arg=["--file", "/abs/path/orbit.json"],
            plot_env={},
        )

        assert len(specs) == 2
        for spec in specs:
            args = list(spec.args)
            assert args[0] == "--file"
            assert args[1] == "/abs/path/orbit.json"

    def test_file_arg_with_single_chip(self, qapp_fixture, tmp_path):
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
        _select_chip(tab, "libration_point", ["L1"])

        specs = RunOrchestrator.build_run_specs(
            tab=tab,
            file_arg=["--file", "/data/x.json"],
            plot_env={},
        )
        assert len(specs) == 1
        args = list(specs[0].args)
        assert args[:2] == ["--file", "/data/x.json"]

    def test_plot_env_merged_into_every_spec(self, qapp_fixture, tmp_path):
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

        plot_env = {"PLOT_FONT_FAMILY": "Sans", "PLOT_THEME": "dark"}
        specs = RunOrchestrator.build_run_specs(
            tab=tab, file_arg=None, plot_env=plot_env
        )

        assert len(specs) == 2
        for spec in specs:
            env = dict(spec.env)
            assert env["PLOT_FONT_FAMILY"] == "Sans"
            assert env["PLOT_THEME"] == "dark"


class TestBuildRunSpecsMultiCli:
    def test_multi_file_row_injects_json_into_args(
        self, qapp_fixture, tmp_path
    ):
        from tod.gui.run_orchestrator import RunOrchestrator

        entry = _make_entry(
            multi_cli_params=[
                MultiCliParam(
                    flag="--json-file",
                    label="JSON 文件",
                    per_file_fields=[
                        PerFileField(key="start", label="起始", field_type="int", default="0"),
                    ],
                )
            ]
        )
        tab = _make_tab(qapp_fixture, tmp_path, entry)
        _add_multi_file_row(tab, "json_file", "/abs/orbit_a.json")

        specs = RunOrchestrator.build_run_specs(
            tab=tab, file_arg=None, plot_env={}
        )

        assert len(specs) == 1
        args = list(specs[0].args)
        assert "--json-file" in args
        idx = args.index("--json-file")
        import json as _json
        configs = _json.loads(args[idx + 1])
        assert len(configs) == 1
        assert configs[0]["path"] == "/abs/orbit_a.json"


class TestDispatch:
    def test_each_spec_triggers_exactly_one_start_job(
        self, qapp_fixture, tmp_path
    ):
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

        specs = RunOrchestrator.build_run_specs(
            tab=tab, file_arg=None, plot_env={}
        )
        jm = _FakeJobManager()
        result = RunOrchestrator.dispatch(specs, entry, jm)

        assert len(result.created_job_ids) == 2
        assert len(jm.calls) == 2
        assert result.is_batch is True
        assert result.total_tasks == 2
        for jid in result.created_job_ids:
            assert jid.startswith("job-")

    def test_dispatch_passes_entry_args_and_env(
        self, qapp_fixture, tmp_path
    ):
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

        plot_env = {"PLOT_THEME": "dark"}
        specs = RunOrchestrator.build_run_specs(
            tab=tab, file_arg=None, plot_env=plot_env
        )
        jm = _FakeJobManager()
        result = RunOrchestrator.dispatch(specs, entry, jm)

        assert len(result.created_job_ids) == 2
        assert len(jm.calls) == 2
        # 每次调用都必须带上 entry 引用、args list、env dict
        for call in jm.calls:
            assert call["entry"] is entry
            assert isinstance(call["args"], list)
            assert isinstance(call["env"], dict)
            assert call["env"].get("PLOT_THEME") == "dark"
            assert "--libration-point" in call["args"]

    def test_dispatch_args_and_env_are_copies_not_references(
        self, qapp_fixture, tmp_path
    ):
        """dispatch 后的 args/env 不应再与 spec 共享同一对象。"""
        from tod.gui.run_orchestrator import RunOrchestrator

        entry = _make_entry(
            cli_chip_params=[
                CliChipParam(
                    "--libration-point",
                    "平动点",
                    options={"L1": "1"},
                )
            ]
        )
        tab = _make_tab(qapp_fixture, tmp_path, entry)
        _select_chip(tab, "libration_point", ["L1"])

        specs = RunOrchestrator.build_run_specs(
            tab=tab, file_arg=None, plot_env={"X": "Y"}
        )

        jm = _FakeJobManager()
        result = RunOrchestrator.dispatch(specs, entry, jm)

        assert len(result.created_job_ids) == 1
        # 修改 fake 收到的 args/env 不应反向影响 spec（dispatch 内部 to_dispatch_kwargs 已拷贝）
        call_args = jm.calls[0]["args"]
        call_env = jm.calls[0]["env"]
        call_args.append("MUTATED")
        call_env["X"] = "MUTATED"
        assert "MUTATED" not in specs[0].args
        env_dict = dict(specs[0].env)
        assert env_dict.get("X") != "MUTATED"
