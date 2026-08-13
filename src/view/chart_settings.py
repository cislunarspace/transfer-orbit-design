"""图表设置：可调绘图参数 + QSettings 持久化 + 设置对话框。

MainWindow 持有一个 :class:`ChartSettings`，经 ``canvas.set_chart_settings()``
注入画布；设置对话框修改后写回 QSettings，重启后保留。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields

#: 可选的轨道颜色方案（matplotlib 定性 colormap 名）
COLORMAP_OPTIONS: list[str] = ["tab10", "tab20", "Set1", "Set2", "Dark2", "Paired"]

#: QSettings 的组织/应用名（与窗口标题一致），main_window 复用
ORG_NAME = "TransferOrbitDesign"
APP_NAME = "chart"


@dataclass
class ChartSettings:
    """图表渲染的可调参数。默认值与画布既有硬编码一致。"""

    #: 轨道线宽（含轨道族、惯性系近似视图、月球轨迹）
    orbit_linewidth: float = 0.8
    #: 轨道颜色方案（matplotlib 定性 colormap 名）
    colormap: str = "tab10"
    #: 地球标注大小（2D scatter 面积 / 3D markersize 基准）
    earth_size: float = 160.0
    #: 月球标注大小
    moon_size: float = 90.0
    #: L1-L5 平动点标注颜色
    lp_color: str = "#d62728"
    #: L1-L5 平动点标注大小
    lp_size: float = 80.0
    #: 轴标签/标题/标注字号
    label_fontsize: float = 10.0
    #: 等比模式下 Z 轴区间相对 XY 区间的最小比例（近平面轨道防压扁）
    z_ratio: float = 0.5


def load_settings(qsettings) -> ChartSettings:
    """从 QSettings 加载 ChartSettings；缺失键用默认值。

    QSettings ini 格式会把数值读回为 str（如 "0.8"），按字段类型显式转换；
    解析失败的值丢弃、用默认值。
    """
    raw = {f.name: qsettings.value(f.name) for f in fields(ChartSettings)}
    valid: dict = {}
    for f in fields(ChartSettings):
        v = raw[f.name]
        if v is None:
            continue
        if isinstance(v, str) and f.type in ("float", "int", "bool"):
            try:
                if f.type == "float":
                    v = float(v)
                elif f.type == "int":
                    v = int(v)
                else:  # bool
                    v = v.strip().lower() in ("true", "1", "yes", "on")
            except ValueError:
                continue  # 无法解析的值丢弃，用默认
        valid[f.name] = v
    return ChartSettings(**valid)


def save_settings(qsettings, settings: ChartSettings) -> None:
    """把 ChartSettings 写入 QSettings。"""
    for key, value in asdict(settings).items():
        qsettings.setValue(key, value)


def chart_settings_dialog(parent, current: ChartSettings) -> ChartSettings | None:
    """弹出图表设置对话框，返回新设置；取消返回 None。"""
    from PyQt6.QtWidgets import (
        QColorDialog,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QDoubleSpinBox,
        QFormLayout,
        QPushButton,
        QSpinBox,
    )

    dlg = QDialog(parent)
    dlg.setWindowTitle("图表设置")
    form = QFormLayout(dlg)

    linewidth = QDoubleSpinBox()
    linewidth.setRange(0.2, 3.0)
    linewidth.setSingleStep(0.1)
    linewidth.setDecimals(1)
    linewidth.setValue(current.orbit_linewidth)
    form.addRow("轨道线宽", linewidth)

    colormap = QComboBox()
    colormap.addItems(COLORMAP_OPTIONS)
    colormap.setCurrentText(current.colormap)
    form.addRow("颜色方案", colormap)

    def _size_spin(value: float) -> QSpinBox:
        sb = QSpinBox()
        sb.setRange(20, 500)
        sb.setValue(int(value))
        return sb

    earth_size = _size_spin(current.earth_size)
    form.addRow("地球标记大小", earth_size)
    moon_size = _size_spin(current.moon_size)
    form.addRow("月球标记大小", moon_size)

    lp_color = QPushButton()
    picked_color = {"value": current.lp_color}
    lp_color.setStyleSheet(
        f"background-color: {picked_color['value']}; min-width: 60px;"
    )

    def _pick_color() -> None:
        color = QColorDialog.getColor(parent=dlg)
        if color.isValid():
            picked_color["value"] = color.name()
            lp_color.setStyleSheet(
                f"background-color: {picked_color['value']}; min-width: 60px;"
            )

    lp_color.clicked.connect(_pick_color)
    form.addRow("L 点颜色", lp_color)

    lp_size = QSpinBox()
    lp_size.setRange(20, 300)
    lp_size.setValue(int(current.lp_size))
    form.addRow("L 点大小", lp_size)

    fontsize = QSpinBox()
    fontsize.setRange(6, 24)
    fontsize.setValue(int(current.label_fontsize))
    form.addRow("标注字号", fontsize)

    z_ratio = QDoubleSpinBox()
    z_ratio.setRange(0.1, 1.0)
    z_ratio.setSingleStep(0.05)
    z_ratio.setDecimals(2)
    z_ratio.setValue(current.z_ratio)
    form.addRow("Z 轴区间比例", z_ratio)

    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    form.addRow(buttons)

    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None

    return ChartSettings(
        orbit_linewidth=linewidth.value(),
        colormap=colormap.currentText(),
        earth_size=float(earth_size.value()),
        moon_size=float(moon_size.value()),
        lp_color=picked_color["value"],
        lp_size=float(lp_size.value()),
        label_fontsize=float(fontsize.value()),
        z_ratio=z_ratio.value(),
    )
