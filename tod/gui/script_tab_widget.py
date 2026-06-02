"""自包含的脚本参数面板，每个打开的脚本对应一个 ScriptTabWidget 实例。

``ScriptTabWidget`` 仅作为组合层：把 ``ParamValueStore``（值/单位/可见性/高亮）、
``ScriptParamPanel``（UI 构建）、``ScriptParamCollector``（参数收集）三块组合
在一起。旧测试和外部代码需要的属性/方法都保留为 1-line shim 转发到 store 或 panel。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, cast

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QComboBox, QLineEdit, QVBoxLayout, QWidget

from tod.gui.file_discovery import FileInfo
from tod.gui.param_value_store import ParamValueStore
from tod.gui.script_param_collector import ScriptParamCollector
from tod.gui.script_param_panel import ScriptParamPanel
from tod.gui.script_registry import CliParam, ScriptEntry


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

    # ── 旧接口属性 shim（兼容 test_script_tab_widget 的访问） ──

    @property
    def _cli_widgets(self) -> dict[str, QWidget]:
        return self._store._cli_widgets

    @property
    def _env_widgets(self) -> dict[str, QComboBox]:
        return self._store._env_widgets

    @property
    def _chip_widgets(self) -> dict[str, QWidget]:
        return self._store._chip_widgets

    @property
    def _multi_file_widgets(self) -> dict[str, QWidget]:
        return self._store._multi_file_widgets

    @property
    def _catalog_seed_selectors(self):
        return self._store._catalog_seed_selectors

    @property
    def _param_defaults(self) -> dict[QWidget, str]:
        return self._store._param_defaults

    @property
    def _factory_defaults(self) -> dict[QWidget, str]:
        return self._store._factory_defaults

    @property
    def _cli_row_containers(self) -> dict[str, QWidget]:
        return self._store._row_containers

    @property
    def _cli_row_labels(self) -> dict[str, QWidget]:
        return self._store._row_labels

    @property
    def _widget_factory(self):
        return self._store._widget_factory

    # ── 旧接口方法 shim（兼容 test_script_tab_widget 的调用） ──

    def _setup_conditional_visibility(self, entry: ScriptEntry) -> None:
        """兼容旧测试的 bound-method 调用形式。

        既支持 ``tab._setup_conditional_visibility(entry)``（普通 widget 实例），
        也支持 ``ScriptTabWidget._setup_conditional_visibility(harness, entry)``
        （把方法当作 unbound 函数绑定到 _Harness 等外部对象上）。后者没有
        ``_store``，所以直接用 self 上的 dict 走 store 逻辑。
        """
        store = getattr(self, "_store", None)
        if isinstance(store, ParamValueStore):
            store.setup_conditional_visibility(entry)
            return

        find_cli_param = cast(Callable[[str], CliParam | None], getattr(self, "_find_cli_param"))
        harness_store = ParamValueStore(files=[], find_cli_param=find_cli_param)
        harness_store.setup_conditional_visibility(
            entry,
            cli_widgets=getattr(self, "_cli_widgets", {}),
            row_containers=getattr(self, "_cli_row_containers", {}),
            row_labels=getattr(self, "_cli_row_labels", {}),
        )

    def _set_widget_std_value(self, widget: QWidget, std_val_str: str) -> None:
        self._store.set_widget_std_value(widget, std_val_str)

    def _to_standard_unit(self, line_edit: QLineEdit) -> str:
        return self._store.to_standard_unit(line_edit)

    def _on_path_mode_changed(self, file_combo, mode_combo) -> None:
        self._store.on_path_mode_changed(file_combo, mode_combo)

    def _on_unit_changed(self, line_edit, combo, group_name) -> None:
        self._store.on_unit_changed(line_edit, combo, group_name)

    def _find_cli_param(self, key: str) -> CliParam | None:
        for p in self.entry.cli_params:
            if p.flag.lstrip("-").replace("-", "_") == key:
                return p
        return None

    def _connect_param_highlight(self, widget: QWidget) -> None:
        self._store.connect_param_highlight(widget)

    def _update_param_highlight(self, widget: QWidget) -> None:
        self._store.update_param_highlight(widget)

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
