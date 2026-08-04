"""参数面板自动化 -- 从 Pydantic Request 模型生成 Qt 控件。

Pydantic -> Qt 映射：
- float + ge/le/gt/lt   -> QDoubleSpinBox
- int   + ge/le/gt/lt   -> QSpinBox
- str   + Literal        -> QComboBox
- str   无约束            -> QLineEdit
- Optional[T]            -> QCheckBox + 对应控件（未勾选返回 None）
- list[float]            -> N 个 QDoubleSpinBox（水平排列）
- Any                    -> QLineEdit（JSON 文本）

约束语义差异：
- Pydantic ``gt=0``  ->  QDoubleSpinBox.setMinimum(0 + eps)
- Pydantic ``lt=1``  ->  QDoubleSpinBox.setMaximum(1 - eps)
"""

from __future__ import annotations

import types
import typing
from typing import Any

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLineEdit,
    QSpinBox,
    QWidget,
)

# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _get_field_meta(field: Any) -> dict[str, Any]:
    """从 Pydantic v2 FieldInfo 提取约束元数据。"""
    meta: dict[str, Any] = {}
    if not hasattr(field, "metadata"):
        return meta
    for constraint in field.metadata:
        if not hasattr(constraint, "__dict__"):
            continue
        for key, value in constraint.__dict__.items():
            if value is not None:
                meta[key] = value
    return meta


def _unwrap_optional(tp: Any) -> tuple[Any, bool]:
    """解包 Optional[T] -> (T, True)，非 Optional 返回 (tp, False)。"""
    origin = typing.get_origin(tp)
    if origin is typing.Union or isinstance(tp, types.UnionType):
        args = [a for a in typing.get_args(tp) if a is not type(None)]
        if len(args) == 1:
            return args[0], True
    return tp, False


def _is_literal(tp: Any) -> bool:
    """判断类型是否为 Literal。"""
    return typing.get_origin(tp) is typing.Literal


# ---------------------------------------------------------------------------
# 单类型控件工厂
# ---------------------------------------------------------------------------


def _make_float_field(field: Any, meta: dict[str, Any]) -> QDoubleSpinBox:
    widget = QDoubleSpinBox()
    widget.setDecimals(4)
    if "ge" in meta:
        widget.setMinimum(float(meta["ge"]))
    elif "gt" in meta:
        widget.setMinimum(float(meta["gt"]) + 1e-8)
    if "le" in meta:
        widget.setMaximum(float(meta["le"]))
    elif "lt" in meta:
        widget.setMaximum(float(meta["lt"]) - 1e-8)
    widget.setSingleStep(1.0)
    if field.default is not None and field.default is not ...:
        widget.setValue(float(field.default))
    elif widget.minimum() <= 0.0 <= widget.maximum():
        widget.setValue(0.0)
    return widget


def _make_int_field(field: Any, meta: dict[str, Any]) -> QSpinBox:
    widget = QSpinBox()
    if "ge" in meta:
        widget.setMinimum(int(meta["ge"]))
    elif "gt" in meta:
        widget.setMinimum(int(meta["gt"]) + 1)
    if "le" in meta:
        widget.setMaximum(int(meta["le"]))
    elif "lt" in meta:
        widget.setMaximum(int(meta["lt"]) - 1)
    if field.default is not None and field.default is not ...:
        widget.setValue(int(field.default))
    elif widget.minimum() <= 0 <= widget.maximum():
        widget.setValue(0)
    return widget


def _make_str_field(field: Any) -> QLineEdit:
    widget = QLineEdit()
    if field.default is not None and field.default is not ...:
        widget.setText(str(field.default))
    return widget


def _make_combo_from_literal(tp: Any, field: Any) -> QComboBox:
    widget = QComboBox()
    values = [str(v) for v in typing.get_args(tp)]
    widget.addItems(values)
    if field.default is not None and field.default is not ...:
        idx = values.index(str(field.default)) if str(field.default) in values else 0
        widget.setCurrentIndex(idx)
    return widget


# ---------------------------------------------------------------------------
# 复合控件工厂 (G6, G7)
# ---------------------------------------------------------------------------


def _make_optional_wrapper(
    inner_widget: QWidget,
    field: Any,
) -> QWidget:
    """Optional[T] -> QCheckBox + 内部控件容器。

    未勾选时内部控件 disabled，collect_params 返回 None。
    """
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)

    cb = QCheckBox()
    cb.setChecked(field.default is not None)
    layout.addWidget(cb)
    layout.addWidget(inner_widget)

    inner_widget.setEnabled(field.default is not None)
    cb.toggled.connect(inner_widget.setEnabled)

    container.setProperty("__params_panel_kind", "optional")
    return container


def _make_list_float_field(field: Any, meta: dict[str, Any]) -> QWidget:
    """list[float] -> 水平排列的 N 个 QDoubleSpinBox。"""
    args = typing.get_args(field.annotation)
    n = args[1] if len(args) > 1 and isinstance(args[1], int) else 3

    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)

    defaults: list[float] = (
        list(field.default) if field.default is not None else [0.0] * n
    )

    for i in range(n):
        sb = QDoubleSpinBox()
        sb.setDecimals(4)
        sb.setSingleStep(1.0)
        sb.setMinimum(-1e12)
        sb.setMaximum(1e12)
        if i < len(defaults):
            sb.setValue(float(defaults[i]))
        layout.addWidget(sb)

    container.setProperty("__params_panel_kind", "list_float")
    return container


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------


def _make_field_widget(field_name: str, field: Any) -> QWidget | None:
    """根据 Pydantic 字段类型和约束创建对应 Qt 控件。"""
    inner_tp, is_optional = _unwrap_optional(field.annotation)

    origin = typing.get_origin(inner_tp)
    meta = _get_field_meta(field)

    # 基础控件选择
    base_widget: QWidget | None = None

    if _is_literal(inner_tp):
        base_widget = _make_combo_from_literal(inner_tp, field)
    elif origin is list:
        args = typing.get_args(inner_tp)
        if args and args[0] is float:
            base_widget = _make_list_float_field(field, meta)
    elif inner_tp is float or origin is float:
        base_widget = _make_float_field(field, meta)
    elif inner_tp is int or origin is int:
        base_widget = _make_int_field(field, meta)
    elif inner_tp is str:
        base_widget = _make_str_field(field)
    else:
        # Any / 其它 -> QLineEdit（JSON）
        base_widget = QLineEdit()
        if field.default is not None and field.default is not ...:
            base_widget.setText(str(field.default))

    if base_widget is None:
        return None

    # G7: Optional 包装
    if is_optional and field.default is None:
        return _make_optional_wrapper(base_widget, field)

    return base_widget


def build_params_from_model(
    model_class: type,
    parent: QWidget | None = None,
) -> dict[str, QWidget]:
    """从 Pydantic 模型自动生成参数面板控件。

    Returns:
        字段名 -> Qt 控件字典。调用方负责将控件加入布局。
    """
    widgets: dict[str, QWidget] = {}
    for name, field in model_class.model_fields.items():
        widget = _make_field_widget(name, field)
        if widget is not None:
            if parent is not None:
                widget.setParent(parent)
            # G2: Field.description -> tooltip
            if field.description:
                widget.setToolTip(field.description)
            widgets[name] = widget
    return widgets


# ---------------------------------------------------------------------------
# 值读取
# ---------------------------------------------------------------------------


def _read_list_float(widget: QWidget) -> list[float]:
    """从 list_float 容器读取所有 QDoubleSpinBox 值。"""
    result: list[float] = []
    for child in widget.findChildren(QDoubleSpinBox):
        result.append(float(child.value()))
    return result


def _read_widget_value(name: str, field: Any, widget: QWidget) -> Any:
    """从单个控件读取当前值，按字段类型转换。"""
    inner_tp, is_optional = _unwrap_optional(field.annotation)

    # G7: Optional 容器
    if widget.property("__params_panel_kind") == "optional":
        cb = widget.findChild(QCheckBox)
        if cb and not cb.isChecked():
            return None
        # 找到非 QCheckBox 的内部控件
        inner_widgets = widget.findChildren(QWidget)
        inner = next(
            (w for w in inner_widgets if not isinstance(w, QCheckBox)),
            None,
        )
        if inner is not None:
            return _read_widget_value(name, field, inner)

    # G6: list[float] 容器
    if widget.property("__params_panel_kind") == "list_float":
        return _read_list_float(widget)

    if isinstance(widget, QComboBox):
        val = widget.currentText()
    elif isinstance(widget, (QDoubleSpinBox, QSpinBox)):
        val = widget.value()
    elif isinstance(widget, QLineEdit):
        val = widget.text()
    else:
        val = widget  # 不可达（防御）

    if inner_tp is float and isinstance(val, (int, float)):
        return float(val)
    if inner_tp is int and isinstance(val, (int, float)):
        return int(val)
    return val


def collect_params(widgets: dict[str, QWidget], model_class: type) -> dict[str, Any]:
    """从控件字典收集参数值，返回可传给 FacadeBridge 的 dict。

    ``model_class`` 用于查找字段类型以做正确转换。
    """
    params: dict[str, Any] = {}
    for name, widget in widgets.items():
        field = model_class.model_fields[name]
        params[name] = _read_widget_value(name, field, widget)
    return params
