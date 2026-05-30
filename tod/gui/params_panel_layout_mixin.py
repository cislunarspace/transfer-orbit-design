"""参数面板布局构建 Mixin。

提供参数面板的 UI 构建方法（控件创建、表单布局、多文件参数面板等），
由 MainWindow 通过多重继承混入。
"""


from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, cast

from PyQt6.QtCore import QCoreApplication, Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from tod.gui.doc_link_mixin import DocLinkMixin, make_doc_link_label
from tod.gui.file_discovery import FileInfo, filter_files
from tod.gui.script_registry import (
    MultiCliParam,
    ScriptEntry,
)
from tod.gui.theme_utils import resolve_theme as _resolve_theme

if TYPE_CHECKING:
    from tod.gui.cli_widget_factory import CliWidgetFactory


class ParamsPanelLayoutMixin(DocLinkMixin):
    """提供参数面板的布局构建方法，由 MainWindow 通过多重继承混入。"""

    _files: list[FileInfo]
    _widget_factory: CliWidgetFactory
    _cli_widgets: dict[str, QWidget]
    _param_defaults: dict[QWidget, str]
    _factory_defaults: dict[QWidget, str]
    _cli_row_containers: dict[str, QWidget]
    _params_layout: QFormLayout
    _cli_row_labels: dict[str, QWidget]
    _current_script: ScriptEntry | None
    _gui_defaults: dict[str, Any]
    _save_gui_defaults: Callable[..., None]
    _repo_root: Path
    _multi_file_widgets: dict[str, QWidget]
    _multi_file_config_panels: dict[str, QWidget]
    _current_theme_mode: str
    _env_widgets: dict[str, QComboBox]
    _chip_widgets: dict[str, QWidget]
    _copy_path_to_clipboard: Callable[..., None]
    _status_bar: Any
    _file_label: QLabel
    _start_spin: QSpinBox
    _end_spin: QSpinBox
    _step_spin: QSpinBox

    def _make_cli_widget(self, cli_param):
        """执行 _make_cli_widget 对应的处理逻辑。

        Returns:
            函数执行结果。
        """
        return self._widget_factory.make_widget(cli_param)

    def _display_widget(self, widget: QWidget) -> QWidget:
        """返回用于布局的显示控件（可能已被包裹）。"""
        return self._widget_factory.display_widget(widget)

    def _add_cli_param_row(self, cli_param) -> None:
        """创建控件并添加到参数面板的当前表单布局中。"""
        key, widget = self._make_cli_widget(cli_param)
        display = self._display_widget(widget)
        self._cli_widgets[key] = widget
        self._param_defaults[widget] = cli_param.default or ""
        self._factory_defaults[widget] = cli_param.default or ""
        self._connect_param_highlight(widget)

        # 包裹到容器中以支持 hidden_when
        row_container = QWidget()
        row_layout = QHBoxLayout(row_container)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(display)
        self._cli_row_containers[key] = row_container

        if cli_param.param_type == "bool":
            self._params_layout.addRow(row_container)
        else:
            self._params_layout.addRow(f"{cli_param.label}:", row_container)
            label = self._params_layout.labelForField(row_container)
            if label is not None:
                self._cli_row_labels[key] = label

    def _add_multi_file_param(self, multi_param: MultiCliParam) -> None:
        """创建多文件参数控件（ListWidget + 索引配置面板）。

        Args:
            multi_param: 多文件参数定义
        """
        key, widget = self._widget_factory.make_multi_file_widget(
            multi_param,
            str(self._repo_root),
        )
        self._multi_file_widgets[key] = widget

        # 索引配置面板（初始为空）
        config_panel = self._create_config_panel(key, multi_param)
        self._multi_file_config_panels[key] = config_panel

        # 连接选择变化回调
        widget._multi_file_cb = (  # type: ignore[attr-defined]
            lambda k, cfg: self._on_multi_file_selection_changed(k, cfg)
        )

        # 垂直布局：ListWidget 在上，配置面板在下
        container = QWidget()
        container.setObjectName(f"multi_file_param_{key}")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(widget)
        layout.addWidget(config_panel)

        row_container = QWidget()
        row_layout = QHBoxLayout(row_container)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(container)
        self._cli_row_containers[key] = row_container

        self._params_layout.addRow(f"{multi_param.label}:", row_container)
        label = self._params_layout.labelForField(row_container)
        if label is not None:
            self._cli_row_labels[key] = label

    def _create_config_panel(
        self,
        key: str,
        multi_param: MultiCliParam,
    ) -> QWidget:
        """创建索引配置面板。

        Args:
            key: 参数 key
            multi_param: 多文件参数定义

        Returns:
            配置面板 widget
        """
        panel = QWidget()
        panel.setObjectName(f"config_panel_{key}")
        panel.setVisible(False)

        layout = QFormLayout(panel)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        # 文件信息标签
        file_label = QLabel(QCoreApplication.translate("ParamsPanelLayoutMixin", "未选择文件"))
        file_label.setObjectName("file_info_label")
        layout.addRow("", file_label)

        # 起始索引
        start_spin = QSpinBox()
        start_spin.setRange(-99999, 99999)
        start_spin.setValue(-1)
        start_spin.setToolTip(
            QCoreApplication.translate("ParamsPanelLayoutMixin", "起始轨道索引，-1 表示从第一条")
        )
        start_spin.setObjectName("start_spin")
        layout.addRow(
            QCoreApplication.translate("ParamsPanelLayoutMixin", "起始索引:"), start_spin
        )

        # 结束索引
        end_spin = QSpinBox()
        end_spin.setRange(-99999, 99999)
        end_spin.setValue(-1)
        end_spin.setToolTip(
            QCoreApplication.translate("ParamsPanelLayoutMixin", "结束轨道索引（含），-1 表示到最后一条")
        )
        end_spin.setObjectName("end_spin")
        layout.addRow(
            QCoreApplication.translate("ParamsPanelLayoutMixin", "结束索引:"), end_spin
        )

        # 绘制间隔
        step_spin = QSpinBox()
        step_spin.setRange(1, 99999)
        step_spin.setValue(1)
        step_spin.setToolTip(
            QCoreApplication.translate("ParamsPanelLayoutMixin", "每隔 N 条轨道绘制 1 条，1 表示绘制全部")
        )
        step_spin.setObjectName("step_spin")
        layout.addRow(
            QCoreApplication.translate("ParamsPanelLayoutMixin", "绘制间隔:"), step_spin
        )

        # 存储引用到 panel
        panel._file_label = file_label  # type: ignore[attr-defined]
        panel._start_spin = start_spin  # type: ignore[attr-defined]
        panel._end_spin = end_spin  # type: ignore[attr-defined]
        panel._step_spin = step_spin  # type: ignore[attr-defined]

        return panel

    def _on_multi_file_selection_changed(
        self,
        key: str,
        config: dict | None,
    ) -> None:
        """多文件列表选中项变化时，更新配置面板。

        Args:
            key: 参数 key
            config: 当前选中文件的配置，None 表示未选中
        """
        panel = self._multi_file_config_panels.get(key)
        widget = self._multi_file_widgets.get(key)
        if panel is None or widget is None:
            return

        if config is None:
            panel.setVisible(False)
            return

        # 断开旧连接
        try:
            panel._start_spin.valueChanged.disconnect()  # type: ignore[attr-defined]
            panel._end_spin.valueChanged.disconnect()  # type: ignore[attr-defined]
            panel._step_spin.valueChanged.disconnect()  # type: ignore[attr-defined]
        except Exception:
            pass

        # 更新面板内容
        panel.setVisible(True)
        file_label = panel._file_label  # type: ignore[attr-defined]
        path = config.get("path", "")

        # 尝试获取文件中的轨道数量
        orbit_count = ""
        try:
            from e2m2e.core import OrbitFamily  # type: ignore[import-untyped]
            from tod.commons.constants import MU
            from e2m2e.core import CR3BP_System  # type: ignore[import-untyped]

            system = CR3BP_System(mu=MU, primary="earth", secondary="moon")
            family = OrbitFamily.load_from_file(Path(path), system)
            orbit_count = QCoreApplication.translate(
                "ParamsPanelLayoutMixin", " ({n} 条轨道)"
            ).format(n=len(family))
        except Exception:
            pass

        file_label.setText(f"{Path(path).name}{orbit_count}")

        # 更新控件值
        panel._start_spin.setValue(config.get("start", -1))  # type: ignore[attr-defined]
        panel._end_spin.setValue(config.get("end", -1))  # type: ignore[attr-defined]
        panel._step_spin.setValue(config.get("step", 1))  # type: ignore[attr-defined]

        # 连接 spin box 变化，更新 list widget 数据
        def _update_config() -> None:
            list_widget = widget.findChild(QListWidget)  # type: ignore
            if list_widget is None:
                return
            current_item = list_widget.currentItem()
            if current_item is None:
                return
            path = current_item.data(Qt.ItemDataRole.UserRole)
            if path in list_widget._file_items:  # type: ignore[attr-defined]
                list_widget._file_items[path]["start"] = panel._start_spin.value()  # type: ignore[attr-defined]
                list_widget._file_items[path]["end"] = panel._end_spin.value()  # type: ignore[attr-defined]
                list_widget._file_items[path]["step"] = panel._step_spin.value()  # type: ignore[attr-defined]

        panel._start_spin.valueChanged.connect(_update_config)  # type: ignore[attr-defined]
        panel._end_spin.valueChanged.connect(_update_config)  # type: ignore[attr-defined]
        panel._step_spin.valueChanged.connect(_update_config)  # type: ignore[attr-defined]

    def _on_doc_link_clicked(self, entry: ScriptEntry, doc_url: str | None) -> None:
        """Handle click on the documentation link."""
        if doc_url is None:
            sb = self._status_bar
            if sb:
                sb.showMessage(QCoreApplication.translate("ParamsPanelLayoutMixin", "⚠ 文档未构建：运行 sphinx-build 生成文档后再试"), 5000)
            return
        self.doc_link_clicked.emit(entry.script_path)  # type: ignore[attr-defined]

    def _rebuild_params_panel(self, entry: ScriptEntry) -> None:
        """根据选中的脚本重建运行参数面板。"""
        # 清空旧控件
        while self._params_layout.count():
            item = self._params_layout.takeAt(0)
            if item is not None:
                w = item.widget()
                if w is not None:
                    w.setParent(None)

        self._env_widgets.clear()
        self._cli_widgets.clear()
        self._chip_widgets.clear()
        self._multi_file_widgets.clear()
        self._multi_file_config_panels.clear()
        self._param_defaults.clear()
        self._factory_defaults.clear()
        self._cli_row_containers.clear()
        self._cli_row_labels.clear()
        self._widget_factory.reset()
        self._widget_factory._files = self._files

        self._params_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self._params_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        # Get doc URL for clickable title
        doc_url = self._get_doc_url(entry.script_path)
        title = make_doc_link_label(entry.name, doc_url)
        # Always connect clicked signal - doc_url determines if doc exists, not clickability
        title.clicked.connect(lambda ep=entry, du=doc_url: self._on_doc_link_clicked(ep, du))
        self._params_layout.addRow(title)

        if entry.description:
            desc_label = QLabel(entry.description)
            if _resolve_theme(self._current_theme_mode) == "dark":
                desc_label.setStyleSheet(
                    "font-size: 12px; padding: 6px 10px; border-radius: 4px; color: #aaaaaa;"
                    "background-color: #252525;"
                )
            else:
                desc_label.setStyleSheet(
                    "font-size: 12px; padding: 6px 10px; border-radius: 4px; color: #444444;"
                    "background-color: #f0f0f0;"
                )
            desc_label.setWordWrap(True)
            self._params_layout.addRow(desc_label)

        # 命令行容器（含 label + 复制按钮）
        cmd_label = QLabel(f"python {entry.script_path}")
        if _resolve_theme() == "dark":
            cmd_bg = "#2d2d2d"
            cmd_color = "#bbbbbb"
            cmd_accent = "#4da6ff"
        else:
            cmd_bg = "#e8e8e8"
            cmd_color = "#333333"
            cmd_accent = "#1976d2"

        cmd_label.setStyleSheet(
            f"font-family: 'Cascadia Code', 'Consolas', 'Menlo', 'DejaVu Sans Mono', 'Liberation Mono', monospace; "
            f"font-size: 9pt; color: {cmd_color}; background-color: {cmd_bg}; "
            f"padding: 6px 10px; border-radius: 4px; border-left: 3px solid {cmd_accent};"
        )
        cmd_label.setWordWrap(False)
        cmd_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        # 绝对路径复制按钮
        cmd_abs_btn = QPushButton(QCoreApplication.translate("ParamsPanelLayoutMixin", "复制路径"))
        cmd_abs_btn.setStyleSheet(
            "QPushButton { padding: 2px 8px; font-size: 9pt; }"
            "QPushButton:flat { border: none; }"
        )
        cmd_abs_btn.setToolTip(QCoreApplication.translate("ParamsPanelLayoutMixin", "复制绝对路径"))
        abs_cmd_path = str(self._repo_root / entry.script_path)
        cmd_abs_btn.clicked.connect(
            lambda _, p=abs_cmd_path, b=cmd_abs_btn: self._copy_path_to_clipboard(p, b)
        )

        # 相对路径复制按钮
        cmd_rel_btn = QPushButton(QCoreApplication.translate("ParamsPanelLayoutMixin", "复制相对路径"))
        cmd_rel_btn.setStyleSheet(
            "QPushButton { padding: 2px 8px; font-size: 9pt; }"
            "QPushButton:flat { border: none; }"
        )
        cmd_rel_btn.setToolTip(QCoreApplication.translate("ParamsPanelLayoutMixin", "复制相对路径（相对于项目根目录）"))
        cmd_rel_btn.clicked.connect(
            lambda _, p=entry.script_path, b=cmd_rel_btn: self._copy_path_to_clipboard(p, b)
        )

        # 水平布局：label + 按钮组
        cmd_row_widget = QWidget()
        cmd_row_layout = QHBoxLayout(cmd_row_widget)
        cmd_row_layout.setContentsMargins(0, 0, 0, 0)
        cmd_row_layout.setSpacing(4)
        cmd_row_layout.addWidget(cmd_label)
        cmd_row_layout.addWidget(cmd_abs_btn)
        cmd_row_layout.addWidget(cmd_rel_btn)
        cmd_row_layout.addStretch()

        self._params_layout.addRow(QCoreApplication.translate("ParamsPanelLayoutMixin", "命令:"), cmd_row_widget)

        if entry.output_dir:
            out_label = QLabel(entry.output_dir)
            if _resolve_theme(self._current_theme_mode) == "dark":
                out_bg = "#2d2d2d"
                out_color = "#bbbbbb"
                out_accent = "#4caf50"
            else:
                out_bg = "#e8e8e8"
                out_color = "#333333"
                out_accent = "#388e3c"

            out_label.setStyleSheet(
                f"font-family: 'Cascadia Code', 'Consolas', 'Menlo', 'DejaVu Sans Mono', 'Liberation Mono', monospace; "
                f"font-size: 9pt; color: {out_color}; background-color: {out_bg}; "
                f"padding: 6px 10px; border-radius: 4px; border-left: 3px solid {out_accent};"
            )
            out_label.setWordWrap(False)
            out_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

            out_abs_btn = QPushButton(QCoreApplication.translate("ParamsPanelLayoutMixin", "复制路径"))
            out_abs_btn.setStyleSheet(
                "QPushButton { padding: 2px 8px; font-size: 9pt; }"
                "QPushButton:flat { border: none; }"
            )
            out_abs_btn.setToolTip(QCoreApplication.translate("ParamsPanelLayoutMixin", "复制绝对路径"))
            abs_out_path = str(self._repo_root / entry.output_dir)
            out_abs_btn.clicked.connect(
                lambda _, p=abs_out_path, b=out_abs_btn: self._copy_path_to_clipboard(p, b)
            )

            out_rel_btn = QPushButton(QCoreApplication.translate("ParamsPanelLayoutMixin", "复制相对路径"))
            out_rel_btn.setStyleSheet(
                "QPushButton { padding: 2px 8px; font-size: 9pt; }"
                "QPushButton:flat { border: none; }"
            )
            out_rel_btn.setToolTip(QCoreApplication.translate("ParamsPanelLayoutMixin", "复制相对路径（相对于项目根目录）"))
            out_rel_btn.clicked.connect(
                lambda _, p=entry.output_dir, b=out_rel_btn: self._copy_path_to_clipboard(p, b)
            )

            out_row_widget = QWidget()
            out_row_layout = QHBoxLayout(out_row_widget)
            out_row_layout.setContentsMargins(0, 0, 0, 0)
            out_row_layout.setSpacing(4)
            out_row_layout.addWidget(out_label)
            out_row_layout.addWidget(out_abs_btn)
            out_row_layout.addWidget(out_rel_btn)
            out_row_layout.addStretch()

            self._params_layout.addRow(QCoreApplication.translate("ParamsPanelLayoutMixin", "输出目录:"), out_row_widget)

        # 分隔线
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("margin: 4px 0 8px 0;")
        self._params_layout.addRow(divider)

        has_any = False

        # 多选芯片参数（位于参数面板顶部，如平动点、Halo类别）
        if entry.cli_chip_params:
            for chip_param in entry.cli_chip_params:
                key, widget = self._widget_factory.make_chip_widget(chip_param)
                self._chip_widgets[key] = widget
                self._params_layout.addRow(f"{chip_param.label}:", widget)
            has_any = True

        # 多文件参数（ListWidget + 索引配置面板）
        if entry.multi_cli_params:
            for multi_param in entry.multi_cli_params:
                self._add_multi_file_param(multi_param)
            has_any = True

        # 环境变量参数（文件选择下拉框）
        if entry.env_params:
            section_label = QLabel(QCoreApplication.translate("ParamsPanelLayoutMixin", "数据文件"))
            section_label.setStyleSheet("font-weight: bold; font-size: 12px; padding: 4px 0;")
            self._params_layout.addRow(section_label)

            for key, env_param in entry.env_params.items():
                combo = QComboBox()
                combo.addItem(QCoreApplication.translate("ParamsPanelLayoutMixin", "（使用脚本默认值）"), None)

                matching = filter_files(
                    self._files,
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
                self._env_widgets[key] = combo

            has_any = True

        # 命令行参数
        if entry.cli_params:
            regular_params = [p for p in entry.cli_params if not p.advanced]
            advanced_params = [p for p in entry.cli_params if p.advanced]

            if regular_params:
                section_label = QLabel(QCoreApplication.translate("ParamsPanelLayoutMixin", "运行参数"))
                section_label.setStyleSheet("font-weight: bold; font-size: 12px; padding: 4px 0;")
                self._params_layout.addRow(section_label)

                for cli_param in regular_params:
                    self._add_cli_param_row(cli_param)

            if advanced_params:
                adv_group = QGroupBox(QCoreApplication.translate("ParamsPanelLayoutMixin", "高级选项"))
                adv_group.setCheckable(True)
                adv_group.setChecked(False)
                adv_layout = QFormLayout()
                adv_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
                adv_layout.setFieldGrowthPolicy(
                    QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
                )

                for cli_param in advanced_params:
                    key, widget = self._make_cli_widget(cli_param)
                    display = self._display_widget(widget)
                    self._cli_widgets[key] = widget
                    self._param_defaults[widget] = cli_param.default or ""
                    self._factory_defaults[widget] = cli_param.default or ""
                    self._connect_param_highlight(widget)

                    row_container = QWidget()
                    row_layout = QHBoxLayout(row_container)
                    row_layout.setContentsMargins(0, 0, 0, 0)
                    row_layout.addWidget(display)
                    self._cli_row_containers[key] = row_container

                    if cli_param.param_type == "bool":
                        adv_layout.addRow(row_container)
                    else:
                        adv_layout.addRow(f"{cli_param.label}:", row_container)
                        label = adv_layout.labelForField(row_container)
                        if label is not None:
                            self._cli_row_labels[key] = label

                adv_group.setLayout(adv_layout)
                self._params_layout.addRow(adv_group)

            has_any = True

        # 应用用户保存的自定义默认值（存储为标准单位）
        saved = self._gui_defaults.get(entry.name, {})
        if saved:
            for key, widget in self._cli_widgets.items():
                cli_param = self._find_cli_param(key)
                if cli_param is None or cli_param.flag not in saved:
                    continue
                val = saved[cli_param.flag]
                self._set_widget_std_value(widget, val)
                self._param_defaults[widget] = val

        # 设置条件可见性（hidden_when）
        self._setup_conditional_visibility(entry)

        # 保存/恢复默认值按钮
        if has_any:
            btn_layout = QHBoxLayout()
            btn_layout.setContentsMargins(0, 8, 0, 0)
            save_btn = QPushButton(QCoreApplication.translate("ParamsPanelLayoutMixin", "保存为默认值"))
            save_btn.setToolTip(QCoreApplication.translate("ParamsPanelLayoutMixin", "将当前参数值保存为此脚本的默认值"))
            save_btn.clicked.connect(self._on_save_defaults)
            reset_btn = QPushButton(QCoreApplication.translate("ParamsPanelLayoutMixin", "恢复出厂默认"))
            reset_btn.setToolTip(QCoreApplication.translate("ParamsPanelLayoutMixin", "恢复为系统预设的默认参数值"))
            reset_btn.clicked.connect(self._on_reset_defaults)
            btn_layout.addWidget(save_btn)
            btn_layout.addWidget(reset_btn)
            btn_layout.addStretch()
            btn_wrapper = QWidget()
            btn_wrapper.setLayout(btn_layout)
            self._params_layout.addRow(btn_wrapper)

        if not has_any:
            label = QLabel(QCoreApplication.translate("ParamsPanelLayoutMixin", "此脚本无可配置参数"))
            label.setStyleSheet("color: #999; font-style: italic;")
            self._params_layout.addRow(label)
