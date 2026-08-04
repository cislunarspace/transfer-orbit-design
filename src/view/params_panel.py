"""参数面板自动化 -- 从 Pydantic Request 模型生成 Qt 控件。

Pydantic -> Qt 映射：
- float + ge/le/gt/lt   -> QDoubleSpinBox
- int   + ge/le/gt/lt   -> QSpinBox
- str   + Literal        -> QComboBox
- str   无约束            -> QLineEdit
- Optional[T]            -> 对应控件（默认值预填，nullable 标记）
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
    QComboBox,
    QDoubleSpinBox,
    QLineEdit,
    QSpinBox,
    QWidget,
)


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
    # Python 3.10+ uses typing.Union; Python 3.10+ also has types.UnionType for T | None
    if origin is typing.Union or isinstance(tp, types.UnionType):
        args = [a for a in typing.get_args(tp) if a is not type(None)]
        if len(args) == 1:
            return args[0], True
    return tp, False


def _is_literal(tp: Any) -> bool:
    """判断类型是否为 Literal。"""
    return typing.get_origin(tp) is typing.Literal


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


def _make_field_widget(field_name: str, field: Any) -> QWidget | None:
    """根据 Pydantic 字段类型和约束创建对应 Qt 控件。"""
    inner_tp, _is_optional = _unwrap_optional(field.annotation)

    # Literal -> QComboBox
    if _is_literal(inner_tp):
        return _make_combo_from_literal(inner_tp, field)

    origin = typing.get_origin(inner_tp)
    meta = _get_field_meta(field)

    # float
    if inner_tp is float or origin is float:
        return _make_float_field(field, meta)

    # int
    if inner_tp is int or origin is int:
        return _make_int_field(field, meta)

    # str
    if inner_tp is str:
        return _make_str_field(field)

    # Any / 其它 -> QLineEdit（JSON）
    widget = QLineEdit()
    if field.default is not None and field.default is not ...:
        widget.setText(str(field.default))
    return widget


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
            widgets[name] = widget
    return widgets


def _read_widget_value(name: str, field: Any, widget: QWidget) -> Any:
    """从单个控件读取当前值，按字段类型转换。"""
    inner_tp, _is_optional = _unwrap_optional(field.annotation)

    if isinstance(widget, QComboBox):
        val = widget.currentText()
    elif isinstance(widget, (QDoubleSpinBox, QSpinBox)):
        val = widget.value()
    elif isinstance(widget, QLineEdit):
        val = widget.text()
    else:
        val = widget  # 不可达（防御）

    # 对可选字段：保持类型一致，None 由 Pydantic 默认值处理
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
