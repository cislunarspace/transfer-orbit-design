"""脚本参数面板的 UI 构建层。

负责把 ``ScriptEntry`` 转换成实际的 Qt 控件并放入 ``QFormLayout``。
所有控件字典、默认值、可见性逻辑都委托给 ``ParamValueStore``。
"""

from __future__ import annotations

from pathlib import Path
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any, cast

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QCheckBox,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from tod.gui.doc_link_mixin import make_doc_link_label
from tod.gui.files.file_discovery import FileInfo, filter_files
from tod.gui.i18n import qt_format
from tod.gui.params.param_value_store import CatalogSeedSelectorState, ParamValueStore
from tod.scripting import CliParam, MultiCliParam, ScriptEntry
from tod.gui.theme_utils import RUN_BTN_STYLE_READY
from tod.gui.theme_utils import resolve_theme as _resolve_theme
from tod.generates.cr3bp.importer import OrbitRecord

class ScriptParamPanel(QWidget):
    """脚本参数面板 UI：标题/描述/控件 dicts/默认值/运行按钮。

    持有 ``ParamValueStore``，并把所有信号转发到外层 ScriptTabWidget。
    """

    run_requested = pyqtSignal()
    doc_link_clicked = pyqtSignal(str)
    doc_link_missing = pyqtSignal(str)
    status_message = pyqtSignal(str, int)
    copy_path_requested = pyqtSignal(str, QWidget)
    defaults_changed = pyqtSignal()

    _RUN_STYLE_READY = RUN_BTN_STYLE_READY

    def __init__(
        self,
        entry: ScriptEntry,
        store: ParamValueStore,
        repo_root: Path,
        gui_defaults: dict[str, Any],
        theme_mode: str,
        parent: QWidget | None = None,
        catalog_seed_loader: Callable[[Path, str], Iterable[object]] | None = None,
    ):
        super().__init__(parent)
        self.entry = entry
        self._store = store
        self._repo_root = repo_root
        self._gui_defaults = gui_defaults
        self._theme_mode = theme_mode
        self._catalog_seed_loader = catalog_seed_loader

        self._setup_ui()
        self.build_params()

    # ── UI 搭建 ───────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._params_container = QWidget()
        self._params_layout = QFormLayout(self._params_container)
        self._params_layout.setContentsMargins(12, 12, 12, 12)
        self._params_layout.setSpacing(8)
        scroll.setWidget(self._params_container)
        self._scroll_area = scroll

        layout.addWidget(scroll, stretch=1)

        self._run_btn = QPushButton(self.tr("运行"))
        self._run_btn.setEnabled(True)
        self._run_btn.clicked.connect(self._on_run_clicked)
        self._run_btn.setStyleSheet(self._RUN_STYLE_READY)
        self._run_btn.setMinimumHeight(36)
        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(12, 8, 12, 8)
        btn_layout.addWidget(self._run_btn)
        layout.addWidget(btn_container)

    # ── 构建参数面板 ──────────────────────────────────────────

    def build_params(self) -> None:
        entry = self.entry
        self._params_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self._params_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        # 标题（可点击文档链接）
        doc_url = self.get_doc_url(entry.script_path)
        title = make_doc_link_label(entry.name, doc_url)
        title.clicked.connect(lambda du=doc_url: self._on_doc_link_clicked(du))
        self._params_layout.addRow(title)

        # 描述（配色由主题 QSS 的 #scriptDescLabel 规则提供）
        if entry.description:
            desc_label = QLabel(entry.description)
            desc_label.setObjectName("scriptDescLabel")
            desc_label.setWordWrap(True)
            self._params_layout.addRow(desc_label)

        # 命令行
        self.add_command_row(entry)

        # 输出目录
        if entry.output_dir:
            self.add_output_dir_row(entry)

        # 分隔线
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("margin: 4px 0 8px 0;")
        self._params_layout.addRow(divider)

        has_any = False

        # 芯片参数
        if entry.cli_chip_params:
            for chip_param in entry.cli_chip_params:
                key, widget = self._store.widget_factory.make_chip_widget(chip_param)
                self._store._chip_widgets[key] = widget
                self._params_layout.addRow(f"{chip_param.label}:", widget)
            has_any = True

        # 多文件参数
        if entry.multi_cli_params:
            for multi_param in entry.multi_cli_params:
                self.add_multi_file_param(multi_param)
            has_any = True

        # 环境变量参数
        if entry.env_params:
            section_label = QLabel(self.tr("数据文件"))
            section_label.setStyleSheet("font-weight: bold; font-size: 12px; padding: 4px 0;")
            self._params_layout.addRow(section_label)
            for key, env_param in entry.env_params.items():
                self.add_env_param(key, env_param)
            has_any = True

        # 命令行参数
        if entry.cli_params:
            regular = [p for p in entry.cli_params if not p.advanced]
            advanced = [p for p in entry.cli_params if p.advanced]

            if regular:
                section_label = QLabel(self.tr("运行参数"))
                section_label.setStyleSheet("font-weight: bold; font-size: 12px; padding: 4px 0;")
                self._params_layout.addRow(section_label)
                for p in regular:
                    self.add_cli_param_row(p)

            if advanced:
                self.add_advanced_group(advanced)

            has_any = True

        if entry.catalog_seed_selectors:
            for selector in entry.catalog_seed_selectors:
                self.add_catalog_seed_selector(selector)
            has_any = True

        # 用户保存的默认值
        saved = self._gui_defaults.get(entry.name, {})
        if saved:
            for key, widget in self._store._cli_widgets.items():
                cli_param = self._store._find_cli_param(key)
                if cli_param is None or cli_param.flag not in saved:
                    continue
                val = saved[cli_param.flag]
                self._store.set_widget_std_value(widget, val)
                self._store._param_defaults[widget] = val

        # 条件可见性
        self._store.setup_conditional_visibility(entry)

        # 保存/恢复按钮
        if has_any:
            self.add_defaults_buttons()

        if not has_any:
            label = QLabel(self.tr("此工具无可配置参数"))
            label.setStyleSheet("color: #999; font-style: italic;")
            self._params_layout.addRow(label)

    def add_command_row(self, entry: ScriptEntry) -> None:
        cmd_label = QLabel(f"python {entry.script_path}")
        if _resolve_theme(self._theme_mode) == "dark":
            cmd_bg, cmd_color, cmd_accent = "#2d2d2d", "#bbbbbb", "#4da6ff"
        else:
            cmd_bg, cmd_color, cmd_accent = "#e8e8e8", "#333333", "#1976d2"

        cmd_label.setStyleSheet(
            f"font-family: 'Cascadia Code', 'Consolas', 'Menlo', 'DejaVu Sans Mono', "
            f"'Liberation Mono', monospace; font-size: 9pt; color: {cmd_color}; "
            f"background-color: {cmd_bg}; padding: 6px 10px; border-radius: 4px; "
            f"border-left: 3px solid {cmd_accent};"
        )
        cmd_label.setWordWrap(False)
        cmd_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        abs_cmd_path = str(self._repo_root / entry.script_path)

        cmd_abs_btn = QPushButton(self.tr("复制路径"))
        cmd_abs_btn.setStyleSheet(
            "QPushButton { padding: 2px 8px; font-size: 9pt; }"
            "QPushButton:flat { border: none; }"
        )
        cmd_abs_btn.clicked.connect(
            lambda _, p=abs_cmd_path, b=cmd_abs_btn: self.copy_path_requested.emit(p, b)
        )

        cmd_rel_btn = QPushButton(self.tr("复制相对路径"))
        cmd_rel_btn.setStyleSheet(
            "QPushButton { padding: 2px 8px; font-size: 9pt; }"
            "QPushButton:flat { border: none; }"
        )
        cmd_rel_btn.clicked.connect(
            lambda _, p=entry.script_path, b=cmd_rel_btn: self.copy_path_requested.emit(p, b)
        )

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(4)
        row_layout.addWidget(cmd_label)
        row_layout.addWidget(cmd_abs_btn)
        row_layout.addWidget(cmd_rel_btn)
        row_layout.addStretch()

        self._params_layout.addRow(self.tr("命令:"), row)

    def add_output_dir_row(self, entry: ScriptEntry) -> None:
        out_label = QLabel(entry.output_dir)
        if _resolve_theme(self._theme_mode) == "dark":
            out_bg, out_color, out_accent = "#2d2d2d", "#bbbbbb", "#4caf50"
        else:
            out_bg, out_color, out_accent = "#e8e8e8", "#333333", "#388e3c"

        out_label.setStyleSheet(
            f"font-family: 'Cascadia Code', 'Consolas', 'Menlo', 'DejaVu Sans Mono', "
            f"'Liberation Mono', monospace; font-size: 9pt; color: {out_color}; "
            f"background-color: {out_bg}; padding: 6px 10px; border-radius: 4px; "
            f"border-left: 3px solid {out_accent};"
        )
        out_label.setWordWrap(False)
        out_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        abs_out_path = str(self._repo_root / (entry.output_dir or "."))

        out_abs_btn = QPushButton(self.tr("复制路径"))
        out_abs_btn.setStyleSheet(
            "QPushButton { padding: 2px 8px; font-size: 9pt; }"
            "QPushButton:flat { border: none; }"
        )
        out_abs_btn.clicked.connect(
            lambda _, p=abs_out_path, b=out_abs_btn: self.copy_path_requested.emit(p, b)
        )

        out_rel_btn = QPushButton(self.tr("复制相对路径"))
        out_rel_btn.setStyleSheet(
            "QPushButton { padding: 2px 8px; font-size: 9pt; }"
            "QPushButton:flat { border: none; }"
        )
        out_rel_btn.clicked.connect(
            lambda _, p=entry.output_dir, b=out_rel_btn: self.copy_path_requested.emit(p, b)
        )

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(4)
        row_layout.addWidget(out_label)
        row_layout.addWidget(out_abs_btn)
        row_layout.addWidget(out_rel_btn)
        row_layout.addStretch()

        self._params_layout.addRow(self.tr("输出目录:"), row)

    def add_env_param(self, key: str, env_param) -> None:
        combo = QComboBox()
        combo.addItem(self.tr("（使用工具默认值）"), None)
        matching = filter_files(
            self._store._files,
            category=env_param.file_category,
            file_type=env_param.file_type,
            name_pattern=env_param.name_pattern,
        )
        for fi in matching:
            combo.addItem(fi.name, fi.abs_path)
        combo.setToolTip(env_param.env_var)
        combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        combo.setMinimumWidth(100)
        self._params_layout.addRow(f"{env_param.label}:", combo)
        self._store._env_widgets[key] = combo

    def add_cli_param_row(self, cli_param: CliParam) -> None:
        key, widget = self._store.widget_factory.make_widget(cli_param)
        display = self._store.widget_factory.display_widget(widget)
        self._store._cli_widgets[key] = widget
        self._store._param_defaults[widget] = cli_param.default or ""
        self._store._factory_defaults[widget] = cli_param.default or ""
        self._store.connect_param_highlight(widget)

        row_container = QWidget()
        row_layout = QHBoxLayout(row_container)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(display)
        self._store._row_containers[key] = row_container

        if cli_param.param_type == "bool":
            self._params_layout.addRow(row_container)
        else:
            self._params_layout.addRow(f"{cli_param.label}:", row_container)
            label = self._params_layout.labelForField(row_container)
            if label is not None:
                self._store._row_labels[key] = label

    def add_catalog_seed_selector(self, selector) -> None:
        """添加 catalog seed selector 的默认关闭占位控件。"""
        enabled = QCheckBox(selector.enabled_label)
        enabled.setChecked(selector.default_enabled)
        selector_widget = QComboBox()
        selector_widget.setEditable(True)
        selector_widget.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        if selector_widget.completer() is not None:
            selector_widget.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        selector_widget.addItem(self.tr("（启用后加载参考数据集）"))
        selector_widget.setEnabled(selector.default_enabled)
        mode_widget = QComboBox()
        mode_widget.addItem(self.tr("按参考记录编号选择"), selector.mode_record_id_key)
        mode_widget.addItem(self.tr("按 Jacobi 常数匹配"), selector.mode_jacobi_key)
        mode_widget.setEnabled(selector.default_enabled)
        jacobi_widget = QLineEdit()
        jacobi_widget.setPlaceholderText(self.tr("Jacobi"))
        tolerance_widget = QLineEdit()
        tolerance_widget.setPlaceholderText(self.tr("Jacobi tolerance（可选）"))
        jacobi_widget.setEnabled(False)
        tolerance_widget.setEnabled(False)
        preview_label = QLabel(self.tr("未选择参考初值"))
        preview_label.setWordWrap(True)
        row = QWidget()
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(4)
        row_layout.addWidget(enabled)
        row_layout.addWidget(mode_widget)
        row_layout.addWidget(selector_widget)
        row_layout.addWidget(jacobi_widget)
        row_layout.addWidget(tolerance_widget)
        row_layout.addWidget(preview_label)
        self._params_layout.addRow(f"{selector.label}:", row)
        manual_keys = tuple(flag.lstrip("-").replace("-", "_") for flag in selector.manual_flags)

        def is_jacobi_mode() -> bool:
            return mode_widget.currentData() == selector.mode_jacobi_key

        def apply_enabled_state(is_enabled: bool) -> None:
            mode_widget.setEnabled(is_enabled)
            jacobi = is_jacobi_mode()
            selector_widget.setEnabled(is_enabled and not jacobi)
            preview_label.setEnabled(is_enabled and not jacobi)
            jacobi_widget.setEnabled(is_enabled and jacobi)
            tolerance_widget.setEnabled(is_enabled and jacobi)
            for manual_key in manual_keys:
                manual_widget = self._store._cli_widgets.get(manual_key)
                if manual_widget is None:
                    continue
                manual_widget.setEnabled(not is_enabled)
                self._store.widget_factory.display_widget(manual_widget).setEnabled(not is_enabled)

        def on_enabled_toggled(is_enabled: bool) -> None:
            apply_enabled_state(is_enabled)
            if is_enabled and not is_jacobi_mode():
                try:
                    self._load_catalog_seed_options(selector, selector_widget)
                except Exception as exc:  # pragma: no cover - Qt slot must not leak exceptions
                    preview_label.setText(qt_format(self.tr("参考数据集加载失败：%1\n请检查参考数据集路径。用于手动模式时可取消勾选。"), str(exc)))

        apply_enabled_state(selector.default_enabled)
        enabled.toggled.connect(on_enabled_toggled)
        mode_widget.currentTextChanged.connect(lambda _text: apply_enabled_state(enabled.isChecked()))
        self._store._catalog_seed_selectors[selector.key] = CatalogSeedSelectorState(
            enabled_checkbox=enabled,
            selector_widget=selector_widget,
            preview_label=preview_label,
            mode_widget=mode_widget,
            jacobi_widget=jacobi_widget,
            tolerance_widget=tolerance_widget,
            manual_keys=manual_keys,
        )

    def _load_catalog_seed_options(self, selector, selector_widget: QComboBox) -> None:
        if selector_widget.property("_catalog_seed_loaded"):
            return

        def _default_loader(repo_root: Path, orbit_type: str) -> list[OrbitRecord]:
            from tod.generates.cr3bp.importer import import_cr3bp_xlsx_catalog, load_cr3bp_catalog

            normalized_dir = repo_root / "data" / "cr3bp_data" / "normalized"
            raw_dir = repo_root / "data" / "cr3bp_data" / "raw"
            index_file = normalized_dir / "index.csv"
            family_file = normalized_dir / "families" / f"{orbit_type}.csv"
            if not index_file.exists() or not family_file.exists():
                import_cr3bp_xlsx_catalog(raw_dir, normalized_dir, overwrite=False)
            catalog = load_cr3bp_catalog(normalized_dir)
            return list(catalog.records(orbit_type=orbit_type))

        loader: Callable[[Path, str], list[OrbitRecord]] = cast(
            Callable[[Path, str], list[OrbitRecord]],
            self._catalog_seed_loader if self._catalog_seed_loader is not None else _default_loader,
        )

        records = list(loader(self._repo_root, selector.orbit_type))
        selector_widget.clear()
        for record in records:
            orbit_id = getattr(record, "orbit_id")
            jacobi = getattr(record, "jacobi", None)
            period = getattr(record, "period", None)
            details = []
            if jacobi is not None:
                details.append(f"C={jacobi:g}")
            if period is not None:
                details.append(f"T={period:g}")
            label = orbit_id if not details else f"{orbit_id} | {' | '.join(details)}"
            selector_widget.addItem(label, orbit_id)
            selector_widget.setItemData(selector_widget.count() - 1, record, Qt.ItemDataRole.UserRole + 1)
        selector_widget.currentIndexChanged.connect(lambda _idx, w=selector_widget: self._update_catalog_seed_preview(w))
        self._update_catalog_seed_preview(selector_widget)
        selector_widget.setProperty("_catalog_seed_loaded", True)

    def _update_catalog_seed_preview(self, selector_widget: QComboBox) -> None:
        record = selector_widget.currentData(Qt.ItemDataRole.UserRole + 1)
        preview_label = None
        for state in self._store._catalog_seed_selectors.values():
            if state.selector_widget is selector_widget:
                preview_label = state.preview_label
                break
        if preview_label is None:
            return
        if record is None:
            preview_label.setText(self.tr("未选择参考初值"))
            return
        state = getattr(record, "state", None)
        source_file = getattr(record, "source_file", "")
        source_row = getattr(record, "source_row", "")
        preview_label.setText(
            f"{getattr(record, 'orbit_id')} | C={getattr(record, 'jacobi'):g} | T={getattr(record, 'period'):g}\n"
            f"state={state}\nsource={source_file} row {source_row}"
        )

    def add_advanced_group(self, advanced_params: list[CliParam]) -> None:
        adv_group = QGroupBox(self.tr("高级选项"))
        adv_group.setCheckable(True)
        adv_group.setChecked(False)
        adv_layout = QFormLayout()
        adv_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        adv_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        for cli_param in advanced_params:
            key, widget = self._store.widget_factory.make_widget(cli_param)
            display = self._store.widget_factory.display_widget(widget)
            self._store._cli_widgets[key] = widget
            self._store._param_defaults[widget] = cli_param.default or ""
            self._store._factory_defaults[widget] = cli_param.default or ""
            self._store.connect_param_highlight(widget)

            row_container = QWidget()
            row_layout = QHBoxLayout(row_container)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.addWidget(display)
            self._store._row_containers[key] = row_container

            if cli_param.param_type == "bool":
                adv_layout.addRow(row_container)
            else:
                adv_layout.addRow(f"{cli_param.label}:", row_container)
                label = adv_layout.labelForField(row_container)
                if label is not None:
                    self._store._row_labels[key] = label

        adv_group.setLayout(adv_layout)
        self._params_layout.addRow(adv_group)

    def add_multi_file_param(self, multi_param: MultiCliParam) -> None:
        """创建多文件参数控件（表格，每行含文件名 + per-file 字段）。"""
        key, widget = self._store.widget_factory.make_multi_file_widget(
            multi_param, str(self._repo_root)
        )
        self._store._multi_file_widgets[key] = widget

        row_container = QWidget()
        row_layout = QHBoxLayout(row_container)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(widget)
        self._store._row_containers[key] = row_container

        self._params_layout.addRow(f"{multi_param.label}:", row_container)
        label = self._params_layout.labelForField(row_container)
        if label is not None:
            self._store._row_labels[key] = label

    def add_defaults_buttons(self) -> None:
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 8, 0, 0)
        save_btn = QPushButton(self.tr("保存为用户默认值"))
        save_btn.clicked.connect(self._on_save_defaults)
        reset_btn = QPushButton(self.tr("恢复工具默认值"))
        reset_btn.setToolTip(self.tr("清除您的自定义设置，恢复为工具内置默认参数"))
        reset_btn.clicked.connect(self._on_reset_defaults)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(reset_btn)
        btn_layout.addStretch()
        wrapper = QWidget()
        wrapper.setLayout(btn_layout)
        self._params_layout.addRow(wrapper)

    # ── 默认值按钮回调 ────────────────────────────────────────

    def _on_save_defaults(self) -> None:
        self._store.save_defaults(self.entry, self._gui_defaults)
        self.defaults_changed.emit()
        self.status_message.emit(self.tr("用户默认值已保存"), 3000)

    def _on_reset_defaults(self) -> None:
        self._store.reset_defaults(self.entry, self._gui_defaults)
        self.defaults_changed.emit()
        self.status_message.emit(self.tr("已恢复工具默认值"), 3000)

    # ── 主题 / 文件刷新 ───────────────────────────────────────

    def update_theme(self, mode: str) -> None:
        """更新主题相关的样式——重新构建整个参数面板。"""
        self._theme_mode = mode

        # 清空旧布局
        while self._params_layout.count():
            item = self._params_layout.takeAt(0)
            if item is not None:
                w = item.widget()
                if w is not None:
                    w.setParent(None)

        self._store.clear()
        self.build_params()

    def refresh_files(self, files: list[FileInfo]) -> None:
        """更新文件列表并刷新所有文件下拉框。"""
        self._store.set_files(files)

        # 刷新环境变量参数下拉框
        for key, env_param in self.entry.env_params.items():
            combo = self._store._env_widgets.get(key)
            if combo is None:
                continue
            current_data = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(self.tr("（使用工具默认值）"), None)
            matching = filter_files(
                self._store._files,
                category=env_param.file_category,
                file_type=env_param.file_type,
                name_pattern=env_param.name_pattern,
            )
            for fi in matching:
                combo.addItem(fi.name, fi.abs_path)
            # 尝试恢复之前选中的文件
            if current_data:
                idx = combo.findData(current_data)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            combo.blockSignals(False)

    def _on_doc_link_clicked(self, doc_url: str | None) -> None:
        """处理文档链接点击：文档存在时打开，不存在时发出警告。"""
        if doc_url is None:
            self.doc_link_missing.emit(
                self.tr("⚠ 文档未构建：运行 sphinx-build 生成文档后再试")
            )
            return
        self.doc_link_clicked.emit(self.entry.script_path)

    def get_doc_url(self, script_path: str) -> str | None:
        doc_rel = script_path
        if doc_rel.endswith(".py"):
            doc_rel = doc_rel[:-3]
        doc_path = self._repo_root / "docs" / "build" / "html" / f"{doc_rel}.html"
        if doc_path.exists():
            return doc_path.absolute().as_uri()
        return None

    def _on_run_clicked(self) -> None:
        self.run_requested.emit()
