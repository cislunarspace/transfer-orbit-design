"""自包含的脚本参数面板，每个打开的脚本对应一个 ScriptTabWidget 实例。

``ScriptTabWidget`` 仅作为组合层：把 ``ParamValueStore``（值/单位/可见性/高亮）、
``ScriptParamPanel``（UI 构建）、``ScriptParamCollector``（参数收集）三块组合
在一起。旧测试和外部代码需要的属性/方法都保留为 1-line shim 转发到 store 或 panel。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, cast

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QComboBox, QVBoxLayout, QWidget

from tod.gui.files.file_discovery import FileInfo
from tod.gui.params.param_value_store import ParamValueStore
from tod.gui.params.script_param_collector import ScriptParamCollector
from tod.gui.params.script_param_panel import ScriptParamPanel
from tod.scripting import CliParam, ScriptEntry


class ScriptTabWidget(QWidget):
    """单个脚本的完整参数面板：标题、描述、参数控件、运行按钮。

    持有 ``ParamValueStore`` 和 ``ScriptParamPanel``，对外保持原接口不变。
    """

    run_requested = pyqtSignal()
    doc_link_clicked = pyqtSignal(str)
    doc_link_missing = pyqtSignal(str)
    status_message = pyqtSignal(str, int)
    copy_path_requested = pyqtSignal(str, QWidget)
    defaults_changed = pyqtSignal()

    def __init__(
        self,
        entry: ScriptEntry,
        files: list[FileInfo],
        repo_root: Path,
        gui_defaults: dict[str, Any],
        theme_mode: str,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.entry = entry
        self._gui_defaults = gui_defaults

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 构造 store（_find_cli_param 由 widget 注入）
        self._store = ParamValueStore(
            files=files,
            find_cli_param=self._find_cli_param_for_store,
        )

        # 构造 panel（panel 内部调 store 构建 UI）
        self._panel = ScriptParamPanel(
            entry=entry,
            store=self._store,
            repo_root=repo_root,
            gui_defaults=gui_defaults,
            theme_mode=theme_mode,
            parent=self,
        )
        layout.addWidget(self._panel)

        # 转发 panel 的信号到外层
        self._panel.run_requested.connect(self.run_requested)
        self._panel.doc_link_clicked.connect(self.doc_link_clicked)
        self._panel.doc_link_missing.connect(self.doc_link_missing)
        self._panel.status_message.connect(self.status_message)
        self._panel.copy_path_requested.connect(self.copy_path_requested)
        self._panel.defaults_changed.connect(self.defaults_changed)

        # 暴露 _run_btn 兼容旧测试
        self._run_btn = self._panel._run_btn

    # ── store 注入的 _find_cli_param ───────────────────────────

    def _find_cli_param_for_store(self, key: str) -> CliParam | None:
        return self._find_cli_param(key)

    def _find_cli_param(self, key: str) -> CliParam | None:
        for p in self.entry.cli_params:
            if p.flag.lstrip("-").replace("-", "_") == key:
                return p
        return None

    def _on_save_defaults(self) -> None:
        self._panel._on_save_defaults()

    def _on_reset_defaults(self) -> None:
        self._panel._on_reset_defaults()

    # ── 公开接口：参数收集（委托到 ScriptParamCollector） ──────

    def collect_run_args(self) -> list[str]:
        return ScriptParamCollector.collect_run_args(
            entry=self.entry,
            cli_widgets=self._store._cli_widgets,
            cli_row_containers=self._store._row_containers,
            param_defaults=self._store._param_defaults,
            factory_defaults=self._store._factory_defaults,
            to_standard_unit=self._store.to_standard_unit,
            unit_combos=self._store._widget_factory.unit_combos,
            find_cli_param=self._find_cli_param,
            catalog_seed_selectors=self._store._catalog_seed_selectors,
        )

    def collect_env_overrides(self) -> dict[str, str]:
        return ScriptParamCollector.collect_env_overrides(
            entry=self.entry,
            env_widgets=self._store._env_widgets,
            cli_widgets=self._store._cli_widgets,
            param_defaults=self._store._param_defaults,
            find_cli_param=self._find_cli_param,
        )

    def collect_chip_selections(self) -> dict[str, list[str]]:
        return ScriptParamCollector.collect_chip_selections(
            entry=self.entry,
            chip_widgets=self._store._chip_widgets,
        )

    def collect_multi_file_configs(self) -> dict[str, list[dict]]:
        return ScriptParamCollector.collect_multi_file_configs(
            multi_file_widgets=self._store._multi_file_widgets,
        )

    def validate_params(self) -> bool:
        return ScriptParamCollector.validate_params(
            parent=self,
            entry=self.entry,
            cli_widgets=self._store._cli_widgets,
            cli_row_containers=self._store._row_containers,
            find_cli_param=self._find_cli_param,
            tr=self.tr,
        )

    # ── 公开接口：主题 & 文件刷新（委托到 ScriptParamPanel） ───

    def update_theme(self, mode: str) -> None:
        self._panel.update_theme(mode)

    def refresh_files(self, files: list[FileInfo]) -> None:
        self._panel.refresh_files(files)
