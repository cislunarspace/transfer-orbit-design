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

import dataclasses
import math
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

from src.commons.units import DAYS_PER_YEAR, DU_KM, SECONDS_PER_YEAR, TU_SECONDS

# ---------------------------------------------------------------------------
# 每轨道类型的默认值 / 显示字段
# ---------------------------------------------------------------------------

#: 每轨道类型分支的形状参数默认值。多数与 e2m2e
#: ``algorithm/design/design_orbit.py::_validate_params`` 的 None 兜底默认值一致；
#: **DRO 例外**——e2m2e 兜底 10000 km 是 DFH 黄金样本标定值（近月紧凑、星历稳定），
#: 但在地月尺度画布上是贴着月球的点，不像用户认知里的"典型 DRO"。GUI 默认取
#: 60000 km（距月 54000–66000 km，ARTEMIS/Gateway 量级的中等 DRO），让用户打开即见
#: 典型形状。代价：大幅 DRO 在真实星历里不如紧凑 DRO 稳定（默认 1 个月星历会漂移），
#: 与 Halo 默认同理——画布画的是 CR3BP 周期轨道，星历漂移不影响形状观察。
#:
#: 键 = 轨道类型下拉显示名（须满足 ``display.upper()`` == e2m2e
#: ``DesignOrbitRequest`` model_validator 接受的 orbit_type token）。
ORBIT_TYPE_DEFAULTS: dict[str, dict[str, float | int]] = {
    "DRO": {"amplitude": 60000.0, "phase": 0.5001},
    "DPO": {"amplitude": 20000.0, "phase": 0.5001},
    "NRHO": {
        "collinear_point": 2,
        "north_south": 2,
        "perilune_height": 5000.0,
        "phase": 0.5,
    },
    "Halo": {"collinear_point": 2, "amplitude": 30000.0, "phase": 0.0},
    "Lissajous": {
        "collinear_point": 2,
        "amplitude_in": 2500.0,
        "amplitude_out": 7500.0,
        "phase_in": 0.01,
        "phase_out": 0.55,
    },
    "Axial": {"collinear_point": 2, "amplitude": 5000.0, "phase": 0.0},
    "L4": {
        "amplitude_in": 8000.0,
        "amplitude_out": 6000.0,
        "phase_in": 0.0,
        "phase_out": 0.0,
    },
    "L5": {
        "amplitude_in": 8000.0,
        "amplitude_out": 6000.0,
        "phase_in": 0.0,
        "phase_out": 0.0,
    },
    "L4_SPO": {"amplitude": 10000.0, "phase": 0.0},
    "L5_SPO": {"amplitude": 10000.0, "phase": 0.0},
    "L4_LPO": {"amplitude": 50000.0, "phase": 0.0},
    "L5_LPO": {"amplitude": 50000.0, "phase": 0.0},
    "L4_HORSESHOE": {"amplitude": 100000.0, "phase": 0.0},
    "L5_HORSESHOE": {"amplitude": 100000.0, "phase": 0.0},
    # ELFO（月心冻结轨道）形状参数。semi_major_axis 模型必填，GUI 取近月冻结
    # 代表值 6500 km；其余对齐 DesignOrbitRequest model_validator 的 ELFO 默认
    # （inclination=75、arg_of_pericenter=270、perilune_height=200）。
    "ELFO": {
        "semi_major_axis": 6500.0,
        "inclination": 75.0,
        "arg_of_pericenter": 270.0,
        "perilune_height": 200.0,
    },
}

#: 每轨道类型分支应显示的字段集（== 该分支默认值字段集）。
ORBIT_TYPE_FIELDS: dict[str, set[str]] = {
    "DRO": {"amplitude", "phase"},
    "DPO": {"amplitude", "phase"},
    "NRHO": {"collinear_point", "north_south", "perilune_height", "phase"},
    "Halo": {"collinear_point", "amplitude", "phase"},
    "Lissajous": {
        "collinear_point",
        "amplitude_in",
        "amplitude_out",
        "phase_in",
        "phase_out",
    },
    "Axial": {"collinear_point", "amplitude", "phase"},
    "L4": {"amplitude_in", "amplitude_out", "phase_in", "phase_out"},
    "L5": {"amplitude_in", "amplitude_out", "phase_in", "phase_out"},
    "L4_SPO": {"amplitude", "phase"},
    "L5_SPO": {"amplitude", "phase"},
    "L4_LPO": {"amplitude", "phase"},
    "L5_LPO": {"amplitude", "phase"},
    "L4_HORSESHOE": {"amplitude", "phase"},
    "L5_HORSESHOE": {"amplitude", "phase"},
    "ELFO": {"semi_major_axis", "inclination", "arg_of_pericenter", "perilune_height"},
}

# ---------------------------------------------------------------------------
# 轨道族生成（FamilyGenerationRequest，e2m2e 5.7.1 起七族）
# ---------------------------------------------------------------------------

#: 族类型下拉显示名（display.upper() == FamilyGenerationRequest 接受的 token）。
FAMILY_TYPES: tuple[str, ...] = ("Halo", "NRHO", "Axial", "Lissajous", "SPO", "LPO", "Horseshoe")

#: 每族分支应显示的族参数字段（公共字段 orbit_type/libration_point/n_orbits
#: 始终显示；sampling_mode 各族首版只有唯一规则，不进面板）。
#: 默认值与平动点域不在此表维护——apply_family_type_defaults /
#: family_libration_points 从 FamilyGenerationRequest 读取。
FAMILY_TYPE_FIELDS: dict[str, set[str]] = {
    "Halo": {"max_amplitude_km"},
    "NRHO": {"north_south", "perilune_height_max_km"},
    "Axial": {"max_amplitude_km"},
    "Lissajous": {"amplitude_in_km", "amplitude_out_km", "phase_in", "phase_out"},
    "SPO": {"min_amplitude_km", "max_amplitude_km", "continuation_direction", "match_tolerance_km"},
    "LPO": {"min_amplitude_km", "max_amplitude_km", "continuation_direction", "match_tolerance_km"},
    "Horseshoe": {
        "min_amplitude_km",
        "max_amplitude_km",
        "continuation_direction",
        "match_tolerance_km",
    },
}


def family_libration_points(family_type: str) -> tuple[int, ...]:
    """返回指定族可选平动点（从 FamilyGenerationRequest.valid_ranges 读取）。"""
    from e2m2e.api.models import FamilyGenerationRequest

    ranges = FamilyGenerationRequest.valid_ranges(family_type.upper())
    point_range = ranges["libration_point"]
    lo = point_range.minimum
    hi = point_range.maximum
    if lo is None or hi is None:
        raise ValueError(f"{family_type} 未声明平动点范围")
    return tuple(range(int(lo), int(hi) + 1))


# ---------------------------------------------------------------------------
# 特殊字段：epoch 6-spinbox 与 correction_method 下拉
# ---------------------------------------------------------------------------

#: epoch 字段名。仅当默认值是 6 元序列时渲染为 6 个 spinbox，
#: 避免误伤其它 Any 字段（如 control_orbit 的 input_ephemeris）。
_EPOCH_FIELD = "epoch"

#: correction_method 下拉取值，对齐 e2m2e DesignOrbitRequest 的公开契约。
#: segmented 由 e2m2e 对 Halo/NRHO/DPO 自动选用；GUI 桥接层也会为不稳定的
#: Lissajous 强制选用。该选项不在面板暴露，用户选择 two_level/standard 时
#: 对这些不稳定轨道会被自动重定向。
#:
#: e2m2e 5.8.0 已删除旧的 Python ``TwoLevelMultipleShooting``，稳定轨道路径中
#: ``standard`` 与 ``two_level`` 是同一 Rust 多重打靶实现的两个公开别名，
#: 不再是两种不同修正策略。界面只暴露唯一的稳定轨道方法，避免把同一算法
#: 显示成两个互斥选项。
CORRECTION_METHOD_OPTIONS: tuple[str, ...] = ("two_level",)

#: str 枚举类字段 -> 下拉选项（correction_method 与族延拓方向）。
#: continuation_direction 仅三角族（SPO/LPO/Horseshoe）有两个选项；
#: NRHO/Axial 的唯一固定方向不暴露（字段隐藏，模型自动填默认）。
_STR_ENUM_FIELDS: dict[str, tuple[str, ...]] = {
    "correction_method": CORRECTION_METHOD_OPTIONS,
    "continuation_direction": ("decrease-x0", "increase-x0"),
}

#: 整数枚举字段 -> (值, 显示名) 下拉选项。模型里这些字段是无语义的 int
#: （如 control_mode=1..6），裸 spinbox 对用户不友好；下拉让取值一目了然。
#: 值存在 QComboBox.itemData（int），收集时按数据取值而非文本。
_INT_COMBO_OPTIONS: dict[str, tuple[tuple[int, str], ...]] = {
    "collinear_point": ((1, "L1"), (2, "L2"), (3, "L3")),
    "libration_point": ((1, "L1"), (2, "L2")),
    "north_south": ((1, "北族"), (2, "南族")),
    "control_mode": (
        (1, "1 - 目标点（宽松）"),
        (2, "2 - 目标点（严格）"),
        (3, "3 - 特征点"),
        (4, "4 - 目标点宽松 + 角动量管理"),
        (5, "5 - 目标点严格 + 角动量管理"),
        (6, "6 - 特征点 + 角动量管理"),
    ),
    "is_nrho": ((0, "否"), (1, "是")),
    "special_mode": ((1, "Lissajous（ẋ=0）"), (2, "Halo/NRHO（ẋ=0 且 ż=0）")),
}

#: 模型未给约束的 int 字段的 GUI 临时范围（e2m2e 侧缺 Field 约束，已提 issue；
#: 这里只挡明显非法值，避免 QSpinBox 默认 0~99 把合法默认值截断）。
_INT_RANGE_OVERRIDES: dict[str, tuple[int, int]] = {
    "num_controls": (1, 10000),
    "num_monte_carlo": (1, 1000),
    "n_orbits": (1, 100),
}

#: epoch 6 个 spinbox 的取值范围；is_int=True -> QSpinBox，False -> QDoubleSpinBox。
_EPOCH_SPINBOX_SPECS: tuple[tuple[str, float, float, bool], ...] = (
    ("年", 1900, 2100, True),
    ("月", 1, 12, True),
    ("日", 1, 31, True),
    ("时", 0, 23, True),
    ("分", 0, 59, True),
    ("秒", 0.0, 59.0, False),
)

# ---------------------------------------------------------------------------
# 可切换显示单位（对齐 e2m2e 参数的标准单位，见 src/commons/units.py）
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class UnitOption:
    """单个显示单位。``display * to_standard = standard``。

    decimals/step 为该显示单位下 spinbox 的小数位与步长。
    """

    label: str
    to_standard: float
    decimals: int = 4
    step: float = 1.0


#: 可切换单位字段 -> 单位选项（首个 = 标准单位，to_standard == 1.0）。
#: 标准单位 = e2m2e 参数契约单位（km/度/秒/天等），收集时换算回标准单位；
#: 国际单位（m/秒/rad）与归一化单位（DU/TU）作展示选项。
#: 独立于 ORBIT_TYPE_DEFAULTS/FIELDS，避免破坏现有默认值测试。
FIELD_UNIT_OPTIONS: dict[str, tuple[UnitOption, ...]] = {
    # 距离（标准 km）：m 为国际单位，DU 为归一化距离单位
    "amplitude": (
        UnitOption("km", 1.0),
        UnitOption("m", 1e-3, decimals=0, step=1000.0),
        UnitOption("DU", DU_KM, decimals=10, step=0.001),
    ),
    "perilune_height": (
        UnitOption("km", 1.0),
        UnitOption("m", 1e-3, decimals=0, step=1000.0),
        UnitOption("DU", DU_KM, decimals=10, step=0.001),
    ),
    "amplitude_in": (
        UnitOption("km", 1.0),
        UnitOption("m", 1e-3, decimals=0, step=1000.0),
        UnitOption("DU", DU_KM, decimals=10, step=0.001),
    ),
    "amplitude_out": (
        UnitOption("km", 1.0),
        UnitOption("m", 1e-3, decimals=0, step=1000.0),
        UnitOption("DU", DU_KM, decimals=10, step=0.001),
    ),
    "semi_major_axis": (
        UnitOption("km", 1.0),
        UnitOption("m", 1e-3, decimals=0, step=1000.0),
        UnitOption("DU", DU_KM, decimals=10, step=0.001),
    ),
    "max_amplitude_km": (
        UnitOption("km", 1.0),
        UnitOption("m", 1e-3, decimals=0, step=1000.0),
        UnitOption("DU", DU_KM, decimals=10, step=0.001),
    ),
    # 轨道族生成（FamilyGenerationRequest）的其余距离字段（标准 km）
    "min_amplitude_km": (
        UnitOption("km", 1.0),
        UnitOption("m", 1e-3, decimals=0, step=1000.0),
        UnitOption("DU", DU_KM, decimals=10, step=0.001),
    ),
    "perilune_height_max_km": (
        UnitOption("km", 1.0),
        UnitOption("m", 1e-3, decimals=0, step=1000.0),
        UnitOption("DU", DU_KM, decimals=10, step=0.001),
    ),
    "amplitude_in_km": (
        UnitOption("km", 1.0),
        UnitOption("m", 1e-3, decimals=0, step=1000.0),
        UnitOption("DU", DU_KM, decimals=10, step=0.001),
    ),
    "amplitude_out_km": (
        UnitOption("km", 1.0),
        UnitOption("m", 1e-3, decimals=0, step=1000.0),
        UnitOption("DU", DU_KM, decimals=10, step=0.001),
    ),
    "match_tolerance_km": (
        UnitOption("km", 1.0),
        UnitOption("m", 1e-3, decimals=0, step=1000.0),
        UnitOption("DU", DU_KM, decimals=10, step=0.001),
    ),
    # 相位（标准 周期份额，无量纲）：度/弧度为其角度表示
    "phase": (
        UnitOption("周期份额", 1.0, decimals=4, step=0.05),
        UnitOption("度", 1.0 / 360.0, decimals=1, step=5.0),
        UnitOption("弧度", 1.0 / (2.0 * math.pi), decimals=3, step=0.05),
    ),
    "phase_in": (
        UnitOption("周期份额", 1.0, decimals=4, step=0.05),
        UnitOption("度", 1.0 / 360.0, decimals=1, step=5.0),
        UnitOption("弧度", 1.0 / (2.0 * math.pi), decimals=3, step=0.05),
    ),
    "phase_out": (
        UnitOption("周期份额", 1.0, decimals=4, step=0.05),
        UnitOption("度", 1.0 / 360.0, decimals=1, step=5.0),
        UnitOption("弧度", 1.0 / (2.0 * math.pi), decimals=3, step=0.05),
    ),
    # 角度（标准 度）：rad 为国际单位
    "inclination": (
        UnitOption("度", 1.0, decimals=2, step=1.0),
        UnitOption("rad", 180.0 / math.pi, decimals=4, step=0.01),
    ),
    "arg_of_pericenter": (
        UnitOption("度", 1.0, decimals=2, step=1.0),
        UnitOption("rad", 180.0 / math.pi, decimals=4, step=0.01),
    ),
    # 时间（标准 年，GUI 契约；e2m2e 秒由 facade_bridge 换算）：秒为国际单位，
    # TU 为归一化时间单位
    "duration": (
        UnitOption("年", 1.0),
        UnitOption("月", 1.0 / 12, decimals=4, step=1.0),
        UnitOption("日", 1.0 / DAYS_PER_YEAR, decimals=4, step=1.0),
        UnitOption("时", 1.0 / (DAYS_PER_YEAR * 24.0), decimals=2, step=1.0),
        UnitOption("秒", 1.0 / SECONDS_PER_YEAR, decimals=0, step=86400.0),
        UnitOption("TU", TU_SECONDS / SECONDS_PER_YEAR, decimals=4, step=0.1),
    ),
    # 输出步长（标准 秒）：时/日为常用刻度，TU 为归一化时间单位
    "output_step": (
        UnitOption("秒", 1.0),
        UnitOption("时", 3600.0, decimals=2, step=0.5),
        UnitOption("日", 86400.0, decimals=3, step=0.1),
        UnitOption("TU", TU_SECONDS, decimals=4, step=0.001),
    ),
    # 控制间隔/反馈弧/卸载间隔（标准 天，e2m2e 契约）：秒为国际单位，TU 为归一化
    "control_interval": (
        UnitOption("天", 1.0, decimals=3, step=1.0),
        UnitOption("秒", 1.0 / 86400.0, decimals=0, step=86400.0),
        UnitOption("TU", TU_SECONDS / 86400.0, decimals=4, step=0.01),
    ),
    "feedback_arc": (
        UnitOption("天", 1.0, decimals=3, step=1.0),
        UnitOption("秒", 1.0 / 86400.0, decimals=0, step=86400.0),
        UnitOption("TU", TU_SECONDS / 86400.0, decimals=4, step=0.01),
    ),
    "momentum_interval": (
        UnitOption("天", 1.0, decimals=3, step=1.0),
        UnitOption("秒", 1.0 / 86400.0, decimals=0, step=86400.0),
        UnitOption("TU", TU_SECONDS / 86400.0, decimals=4, step=0.01),
    ),
    # SRP 压心偏移（标准 m，list 容器）：DU 为归一化距离单位
    "srp_offset_m": (
        UnitOption("m", 1.0),
        UnitOption("DU", DU_KM * 1000.0, decimals=10, step=0.001),
    ),
}

#: Optional 字段的 GUI 展示默认值：这些字段不包 Optional 容器（勾选框），直接
#: 展示为 spinbox 并填入默认值。它们是"通用字段"（不进 ORBIT_TYPE_DEFAULTS
#: 分支，不会被 apply_orbit_type_defaults 解包），需要 GUI 层自行给初值。
#:
#: duration：e2m2e 5.6.5 起 model default=None（让 model_validator 按 orbit_type
#: 填秒级默认）；GUI 仍展示 1 年短弧默认（issue #355），main_window 再覆盖到 1 月。
#: 此处默认值单位为年（FIELD_UNIT_OPTIONS["duration"] 的标准单位），facade
#: 构造 request 时换算成秒。
_OPTIONAL_FIELD_GUI_DEFAULTS: dict[str, float | int] = {
    "duration": 1.0,
    # FamilyGenerationRequest 的 Halo 默认值由上游模型在 None 时填充；GUI 直接
    # 展示同一组默认值，避免 Optional 包装把常用参数显示为空。
    "libration_point": 2,
    "max_amplitude_km": 30000.0,
}

# Qt 动态属性名：控件用 setProperty 存单位状态。拼错会静默破坏换算，故提为常量。
# 用单下划线前缀，避免双下划线带来的 name-mangling 语义误导（动态属性本身不参与
# mangling，但双下划线会让读者误以为有改写）。
_UNIT_ATTR = "_params_panel_unit"
_STD_MIN_ATTR = "_params_panel_std_min"
_STD_MAX_ATTR = "_params_panel_std_max"
#: 控件描述文本属性（Pydantic Field.description），范围提示拼接 tooltip 时用。
_DESC_ATTR = "_params_panel_desc"
#: 换算缓存：`(换算后的显示值, 精确标准值)`。QDoubleSpinBox 按 decimals 舍入
#: 存储值，切单位再切回会有累计精度损失（如 30 天→TU→天 变 30.000022 天）；
#: 自动换算时把精确标准值缓存下来，collect 时若显示值未被用户改动则取缓存。
_STD_VALUE_ATTR = "_params_panel_std_value"
#: 范围约束状态：`(has_lower, has_upper, note, strict_lower, strict_upper)`。
#: 范围提示按此区分"有真实约束（显示 min~max）"与"无约束（显示无范围约束，
#: 不拿 Qt 兜底值冒充）"；gt/lt 严格约束显示 >/<（Qt 会按 decimals 舍入
#: minimum，如 gt=0 的 1e-8 舍成 0，直接显示数值会误导为 ≥0 可含 0）。note
#: 为补充说明（如 GUI 临时范围）。list 容器存在容器上，子控件提示时传入。
_BOUNDS_ATTR = "_params_panel_bounds"

#: JSON 文本框（str/Any 无约束字段）为空时的占位提示：告知参数可填内容格式。
#: 数值控件不用此表——它们的占位提示由 `_apply_range_hint` 按 min/max 生成。
_FIELD_PLACEHOLDERS: dict[str, str] = {
    "perturbation": ('JSON 摄动开关，例如 {"sun_body": 1, "planets": 1}（留空=默认全开）'),
    "dyb": "JSON 数组，9 分量面质比系数，dyb[0] 为等效面质比（m²/kg），留空=默认",
    "engine_layout": (
        "JSON 发动机布局，例如 "
        '{"positions_m":[[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1]], '
        '"directions":[[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1]]} '
        "（模式 4-6 必填）"
    ),
}

# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _get_field_meta(field: Any) -> dict[str, Any]:
    """从 Pydantic v2 FieldInfo 提取约束元数据。

    annotated_types 约束（Ge/Le/Gt/Lt/...）是带 ``slots=True`` 的 frozen
    dataclass，没有 ``__dict__``，须用 ``dataclasses.fields`` 提取。
    """
    meta: dict[str, Any] = {}
    if not hasattr(field, "metadata"):
        return meta
    for constraint in field.metadata:
        if dataclasses.is_dataclass(constraint):
            for f in dataclasses.fields(constraint):
                value = getattr(constraint, f.name)
                if value is not None:
                    meta[f.name] = value
            continue
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
# 显示单位辅助
# ---------------------------------------------------------------------------


def get_field_units(field_name: str) -> tuple[UnitOption, ...] | None:
    """返回字段的可切换单位选项；字段不支持单位切换时返回 None。"""
    return FIELD_UNIT_OPTIONS.get(field_name)


def _find_unit_option(field_name: str, unit: str) -> UnitOption | None:
    """按单位名查找 UnitOption；未知单位返回 None（不静默回退到首个）。

    调用方传入的 unit 通常来自控件属性或单位下拉（必是 options 中的 label），
    返回 None 仅在收到非法 unit 时发生，由调用方自行决定是否中止。
    """
    options = get_field_units(field_name)
    if not options:
        return None
    for opt in options:
        if opt.label == unit:
            return opt
    return None


def _current_unit_option(field_name: str, widget: QWidget) -> UnitOption | None:
    """读取控件当前显示单位（属性缺失时视为标准单位）。"""
    options = get_field_units(field_name)
    if not options:
        return None
    unit = widget.property(_UNIT_ATTR) or options[0].label
    return _find_unit_option(field_name, unit)


def set_spinbox_unit(widget: QWidget, field_name: str, unit: str) -> None:
    """切换数值控件的显示单位：换算当前值并缩放范围/步长/小数位。

    支持单 spinbox（QDoubleSpinBox）、list[float] 容器及其 Optional 包装：
    单位状态存于容器/控件属性 ``_params_panel_unit``（当前显示单位）、
    ``_params_panel_std_min/_params_panel_std_max``（标准单位下的范围，
    控件生成时从约束写入）。换算后同步刷新范围占位提示。
    """
    options = get_field_units(field_name)
    if not options:
        return
    new_opt = _find_unit_option(field_name, unit)
    if new_opt is None:
        return
    # Optional 包装：换算其内部控件（单位状态存在内部控件上）
    if widget.property("__params_panel_kind") == "optional":
        inner = _find_inner_widget(widget)
        if inner is None:
            return
        widget = inner
    if widget.property("__params_panel_kind") == "list_float":
        old_opt = _current_unit_option(field_name, widget)
        if old_opt is None or old_opt is new_opt:
            return
        std_min = widget.property(_STD_MIN_ATTR)
        std_max = widget.property(_STD_MAX_ATTR)
        # 先更新容器单位状态，再换算子控件：范围提示按新单位生成。
        # 子 spinbox 自身无单位/约束属性（状态在容器上），显式传入。
        widget.setProperty(_UNIT_ATTR, new_opt.label)
        bounds = widget.property(_BOUNDS_ATTR) or (True, True, "", False, False)
        for child in widget.findChildren(QDoubleSpinBox):
            _convert_spinbox(
                child,
                old_opt,
                new_opt,
                std_min,
                std_max,
                field_name,
                unit_label=new_opt.label,
                bounds=bounds,
            )
        return
    old_opt = _current_unit_option(field_name, widget)
    if old_opt is None or old_opt is new_opt:
        return
    if not isinstance(widget, QDoubleSpinBox):
        return  # 非数值控件无单位状态（防御，正常路径不会到这里）
    std_min = widget.property(_STD_MIN_ATTR)
    std_max = widget.property(_STD_MAX_ATTR)
    widget.setProperty(_UNIT_ATTR, new_opt.label)
    _convert_spinbox(widget, old_opt, new_opt, std_min, std_max, field_name)


def _convert_spinbox(
    sb: QDoubleSpinBox,
    old_opt: UnitOption,
    new_opt: UnitOption,
    std_min: float | None,
    std_max: float | None,
    field_name: str,
    *,
    unit_label: str | None = None,
    bounds: tuple | None = None,
) -> None:
    """把单个 spinbox 从 old_opt 显示单位换到 new_opt（范围/步长/小数位/值）。

    精确标准值写入 ``_STD_VALUE_ATTR`` 缓存（含换算后显示值），避免多次切单位
    的舍入误差累积。``unit_label``/``bounds`` 供范围提示使用（list 容器子控件
    自身无单位/约束属性，由调用方显式传入）。
    """
    standard = _standard_value_of(sb, old_opt.to_standard)
    sb.setDecimals(new_opt.decimals)
    sb.setSingleStep(new_opt.step)
    if std_min is not None:
        sb.setMinimum(float(std_min) / new_opt.to_standard)
    if std_max is not None:
        sb.setMaximum(float(std_max) / new_opt.to_standard)
    sb.setValue(standard / new_opt.to_standard)
    sb.setProperty(_STD_VALUE_ATTR, (float(sb.value()), standard))
    _apply_range_hint(sb, field_name, unit_label, bounds)


def _standard_value_of(sb: QDoubleSpinBox, fallback_factor: float) -> float:
    """读取 spinbox 的精确标准值：显示值未改动时用缓存，否则按当前单位换算。"""
    cached = sb.property(_STD_VALUE_ATTR)
    if cached is not None and float(cached[0]) == float(sb.value()):
        return float(cached[1])
    return float(sb.value()) * fallback_factor


# ---------------------------------------------------------------------------
# 范围占位提示
# ---------------------------------------------------------------------------


def _apply_range_hint(
    widget: QWidget,
    field_name: str,
    unit_label: str | None = None,
    bounds: tuple | None = None,
) -> None:
    """给数值控件写范围提示：占位文本 + tooltip。

    - 内部 QLineEdit 设 placeholder：框内文本清空时显示可填范围，随约束状态
      区分——有约束显示"可填范围: min ~ max 单位"，仅单侧约束显示 ≥/≤，
      双侧约束分别显示下界和上界的严格性；无约束显示"无范围约束"（不拿 Qt
      兜底值冒充真实范围）；
    - tooltip = 字段描述 + 同样的范围提示（描述经 ``_DESC_ATTR`` 属性传入）；
    - list[float] 容器：逐个子 spinbox 应用（单位/约束状态在容器上）。
    """
    if widget.property("__params_panel_kind") == "list_float":
        if unit_label is None:
            opt = _current_unit_option(field_name, widget)
            unit_label = opt.label if opt else None
        if bounds is None:
            bounds = widget.property(_BOUNDS_ATTR) or (True, True, "", False, False)
        for child in widget.findChildren(QDoubleSpinBox):
            _apply_range_hint(child, field_name, unit_label, bounds)
        return
    if not isinstance(widget, (QDoubleSpinBox, QSpinBox)):
        return
    desc = str(widget.property(_DESC_ATTR) or "")
    if unit_label is None:
        opt = _current_unit_option(field_name, widget)
        unit_label = opt.label if opt else None
    if bounds is None:
        bounds = widget.property(_BOUNDS_ATTR)
    if bounds is None:
        bounds = (True, True, "", False, False)
    has_lower, has_upper, note, strict_lower, strict_upper = bounds
    lo, hi = widget.minimum(), widget.maximum()
    unit_suffix = f" {unit_label}" if unit_label else ""
    if not has_lower and not has_upper:
        hint = "无范围约束"
    elif not has_upper:
        prefix = ">" if strict_lower else "≥"
        hint = f"可填范围: {prefix} {lo:g}{unit_suffix}"
    elif not has_lower:
        prefix = "<" if strict_upper else "≤"
        hint = f"可填范围: {prefix} {hi:g}{unit_suffix}"
    elif strict_lower or strict_upper:
        lower_prefix = ">" if strict_lower else "≥"
        upper_prefix = "<" if strict_upper else "≤"
        hint = f"可填范围: {lower_prefix} {lo:g}{unit_suffix} 且 {upper_prefix} {hi:g}{unit_suffix}"
    else:
        hint = f"可填范围: {lo:g} ~ {hi:g}{unit_suffix}"
    if note:
        hint += f"（{note}）"
    line_edit = widget.lineEdit()
    if line_edit is not None:
        line_edit.setPlaceholderText(hint)
    widget.setToolTip(f"{desc}\n{hint}" if desc else hint)


# ---------------------------------------------------------------------------
# 单类型控件工厂
# ---------------------------------------------------------------------------


def _make_float_field(field_name: str, field: Any, meta: dict[str, Any]) -> QDoubleSpinBox:
    widget = QDoubleSpinBox()
    widget.setDecimals(4)
    has_lower = "ge" in meta or "gt" in meta
    has_upper = "le" in meta or "lt" in meta
    if "ge" in meta:
        widget.setMinimum(float(meta["ge"]))
    elif "gt" in meta:
        widget.setMinimum(float(meta["gt"]) + 1e-8)
    if "le" in meta:
        widget.setMaximum(float(meta["le"]))
    elif "lt" in meta:
        widget.setMaximum(float(meta["lt"]) - 1e-8)
    widget.setSingleStep(1.0)
    # 无上界约束时 Qt 默认 max=99.99 过小；Optional 字段也可能在 GUI 填入
    # 默认值或用户值，故不能只在模型 default 非 None 时扩上界。
    if not has_upper:
        widget.setMaximum(1e12)
    if not field.is_required() and field.default is not None:
        default = float(field.default)
        # 有上界约束时仍保留"扩 max 容纳默认值"的兜底。
        if has_upper and default > widget.maximum():
            widget.setMaximum(default)
        widget.setValue(default)
    elif widget.minimum() <= 0.0 <= widget.maximum():
        widget.setValue(0.0)

    # 范围约束状态：范围提示据此区分真实约束与 Qt 兜底值；gt/lt 记严格性
    widget.setProperty(_BOUNDS_ATTR, (has_lower, has_upper, "", "gt" in meta, "lt" in meta))

    # 可切换单位字段：写入标准单位下的范围属性 + 默认显示单位（标准单位）
    options = get_field_units(field_name)
    if options is not None:
        std = options[0]
        widget.setProperty(_STD_MIN_ATTR, float(widget.minimum()))
        widget.setProperty(_STD_MAX_ATTR, float(widget.maximum()))
        widget.setProperty(_UNIT_ATTR, std.label)
        widget.setDecimals(std.decimals)
        widget.setSingleStep(std.step)
    return widget


def _make_int_field(field_name: str, field: Any, meta: dict[str, Any]) -> QSpinBox:
    widget = QSpinBox()
    has_lower = "ge" in meta or "gt" in meta
    has_upper = "le" in meta or "lt" in meta
    if "ge" in meta:
        widget.setMinimum(int(meta["ge"]))
    elif "gt" in meta:
        widget.setMinimum(int(meta["gt"]) + 1)
    if "le" in meta:
        widget.setMaximum(int(meta["le"]))
    elif "lt" in meta:
        widget.setMaximum(int(meta["lt"]) - 1)
    # 模型缺约束的 int 字段（如 num_controls 无上界）用 GUI 临时范围逐边界
    # 兜底——只补缺失的边界，不覆盖模型已有约束（e2m2e 侧缺 Field 约束，
    # 已提 issue #408）。
    note = ""
    override = _INT_RANGE_OVERRIDES.get(field_name)
    if override is not None:
        if not has_lower:
            widget.setMinimum(override[0])
            has_lower = True
        if not has_upper:
            widget.setMaximum(override[1])
            has_upper = True
        note = "部分边界模型未声明，GUI 临时"
    if not field.is_required() and field.default is not None:
        default = int(field.default)
        # 无上界约束时 Qt 默认 max=99，扩到能容纳默认值
        if default > widget.maximum():
            widget.setMaximum(default)
        widget.setValue(default)
    elif widget.minimum() <= 0 <= widget.maximum():
        widget.setValue(0)
    widget.setProperty(_BOUNDS_ATTR, (has_lower, has_upper, note, False, False))
    return widget


def _make_int_combo(field: Any, options: tuple[tuple[int, str], ...]) -> QComboBox:
    """整数枚举字段 -> QComboBox，值存 itemData（int），按默认值选中。"""
    combo = QComboBox()
    for value, text in options:
        combo.addItem(text, value)
    if not field.is_required() and field.default is not None:
        idx = combo.findData(int(field.default))
        if idx >= 0:
            combo.setCurrentIndex(idx)
    return combo


def _make_str_field(field: Any) -> QLineEdit:
    widget = QLineEdit()
    if not field.is_required() and field.default is not None:
        widget.setText(str(field.default))
    return widget


def _make_combo_from_literal(tp: Any, field: Any) -> QComboBox:
    widget = QComboBox()
    values = [str(v) for v in typing.get_args(tp)]
    widget.addItems(values)
    if not field.is_required() and field.default is not None:
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


def _make_list_float_field(field_name: str, field: Any, meta: dict[str, Any]) -> QWidget:
    """list[float] -> 水平排列的 N 个 QDoubleSpinBox。

    可切换单位字段（如 srp_offset_m）的单位状态存在容器上
    （``_UNIT_ATTR``/``_STD_MIN_ATTR``/``_STD_MAX_ATTR``），换算时全部子
    spinbox 一起缩放。
    """
    args = typing.get_args(field.annotation)
    n = args[1] if len(args) > 1 and isinstance(args[1], int) else 3

    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)

    defaults: list[float] = list(field.default) if field.default is not None else [0.0] * n

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
    # 容器范围无模型约束（±1e12 仅为 Qt 兜底），范围提示如实显示"无范围约束"
    container.setProperty(_BOUNDS_ATTR, (False, False, "", False, False))
    options = get_field_units(field_name)
    if options is not None:
        std = options[0]
        container.setProperty(_STD_MIN_ATTR, -1e12)
        container.setProperty(_STD_MAX_ATTR, 1e12)
        container.setProperty(_UNIT_ATTR, std.label)
        for sb in container.findChildren(QDoubleSpinBox):
            sb.setDecimals(std.decimals)
            sb.setSingleStep(std.step)
    return container


def _is_epoch_default(value: Any) -> bool:
    """判断默认值是否为 [年,月,日,时,分,秒] 六元序列。"""
    return isinstance(value, (tuple, list)) and len(value) == 6


def _make_epoch_field(field: Any) -> QWidget:
    """epoch -> 水平排列的 6 个 spinbox（年/月/日/时/分 整数，秒浮点）。

    调用方（``_make_field_widget``）仅在 ``_is_epoch_default(field.default)``
    为真时路由进来，故此处 default 必为 6 元序列，无需兜底。
    """
    defaults = [float(v) for v in field.default]
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)

    for (_, lo, hi, is_int), default in zip(_EPOCH_SPINBOX_SPECS, defaults, strict=True):
        if is_int:
            sb = QSpinBox()
            sb.setRange(int(lo), int(hi))
            sb.setValue(int(default))
        else:
            sb = QDoubleSpinBox()
            sb.setDecimals(3)
            sb.setRange(float(lo), float(hi))
            sb.setValue(float(default))
        layout.addWidget(sb)

    container.setProperty("__params_panel_kind", "epoch")
    return container


def _make_str_enum_combo(field: Any, options: tuple[str, ...]) -> QComboBox:
    """str 枚举字段 -> QComboBox，选中项对齐字段默认值。"""
    combo = QComboBox()
    combo.addItems(list(options))
    if not field.is_required() and field.default is not None:
        default = str(field.default)
        if default in options:
            combo.setCurrentIndex(options.index(default))
    return combo


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------


def _make_field_widget(field_name: str, field: Any) -> QWidget | None:
    """根据 Pydantic 字段类型和约束创建对应 Qt 控件。"""
    inner_tp, is_optional = _unwrap_optional(field.annotation)

    # 特判 1：epoch（[年,月,日,时,分,秒]）-> 6-spinbox 容器。
    # 仅当默认值是 6 元序列才命中，避免误伤其它 Any 字段（如 input_ephemeris）。
    if field_name == _EPOCH_FIELD and inner_tp is Any and _is_epoch_default(field.default):
        return _make_epoch_field(field)

    # 特判 2：str 枚举类字段（correction_method）-> QComboBox。
    options = _STR_ENUM_FIELDS.get(field_name)
    if inner_tp is str and options:
        return _make_str_enum_combo(field, options)

    origin = typing.get_origin(inner_tp)
    meta = _get_field_meta(field)

    # 基础控件选择
    base_widget: QWidget | None = None

    if _is_literal(inner_tp):
        base_widget = _make_combo_from_literal(inner_tp, field)
    elif origin is list:
        args = typing.get_args(inner_tp)
        if args and args[0] is float:
            base_widget = _make_list_float_field(field_name, field, meta)
    elif inner_tp is float or origin is float:
        base_widget = _make_float_field(field_name, field, meta)
    elif inner_tp is int or origin is int:
        int_options = _INT_COMBO_OPTIONS.get(field_name)
        if int_options is not None:
            base_widget = _make_int_combo(field, int_options)
        else:
            base_widget = _make_int_field(field_name, field, meta)
    elif inner_tp is str:
        base_widget = _make_str_field(field)
    else:
        # Any / 其它 -> QLineEdit（JSON）
        # 无注解局部变量承接：pyright 对 PyQt6 类型不做赋值收窄（已知限制），
        # 带 `| None` 注解的 base_widget 赋值后仍视为可为 None，故换名新建。
        line_edit = QLineEdit()
        if not field.is_required() and field.default is not None:
            line_edit.setText(str(field.default))
        base_widget = line_edit

    if base_widget is None:
        return None

    # G7: Optional 包装
    if is_optional and field.default is None:
        # 通用 Optional 字段（如 duration）：模型 default=None（让 e2m2e
        # model_validator 兜底），但 GUI 始终展示 spinbox + 合理默认值，不走
        # 勾选框式 Optional 容器。这些字段不在 ORBIT_TYPE_DEFAULTS 分支，不会被
        # apply_orbit_type_defaults 解包，故在此直接给 spinbox。
        gui_default = _OPTIONAL_FIELD_GUI_DEFAULTS.get(field_name)
        if gui_default is not None:
            if isinstance(base_widget, QDoubleSpinBox):
                base_widget.setValue(float(gui_default))
            elif isinstance(base_widget, QSpinBox):
                base_widget.setValue(int(gui_default))
            elif isinstance(base_widget, QComboBox):
                index = base_widget.findData(int(gui_default))
                if index >= 0:
                    base_widget.setCurrentIndex(index)
            return base_widget
        return _make_optional_wrapper(base_widget, field)

    return base_widget


def _decorate_widget(widget: QWidget, name: str, description: str) -> None:
    """G2: 控件装饰——描述存属性、范围提示写占位/tooltip、JSON 占位提示。

    Optional 包装控件要穿透到内部控件装饰（勾选框 + 内部控件的组合体自身
    不承载数值）。
    """
    widget.setProperty(_DESC_ATTR, description or "")
    kind = widget.property("__params_panel_kind")
    if isinstance(widget, (QDoubleSpinBox, QSpinBox)):
        _apply_range_hint(widget, name)
        return
    if kind == "list_float":
        _apply_range_hint(widget, name)
        return
    if kind == "optional":
        inner = _find_inner_widget(widget)
        if inner is not None:
            _decorate_widget(inner, name, description)
        return
    if isinstance(widget, QLineEdit):
        placeholder = _FIELD_PLACEHOLDERS.get(name)
        if placeholder and not widget.text():
            widget.setPlaceholderText(placeholder)


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
            _decorate_widget(widget, name, field.description or "")
            widgets[name] = widget
    return widgets


# ---------------------------------------------------------------------------
# 默认值填充（per-orbit_type）
# ---------------------------------------------------------------------------


def _find_inner_widget(container: QWidget) -> QWidget | None:
    """从 Optional 容器中找出唯一的非 QCheckBox 子控件。"""
    inner_widgets = container.findChildren(QWidget)
    return next(
        (w for w in inner_widgets if not isinstance(w, QCheckBox)),
        None,
    )


def _unwrap_optional_widget(widget: QWidget) -> QWidget:
    """若控件是 Optional 容器（QCheckBox + 内部控件），解包返回内部控件。

    解包时把内部控件脱离容器父级，避免容器被 Python 回收时连带删除内部控件。
    非 Optional 容器原样返回。
    """
    if widget.property("__params_panel_kind") != "optional":
        return widget
    inner = _find_inner_widget(widget)
    if inner is not None:
        inner.setParent(None)
        return inner
    return widget


def _apply_branch_defaults(widgets: dict[str, QWidget], defaults: dict[str, Any]) -> None:
    """把分支默认值填入 widgets 对应控件。

    分支字段若是 Optional 容器（QCheckBox + 内部控件），解包为内部控件并
    用分支默认值 setValue（去掉勾选框，直接可调）。字段缺失时静默跳过。
    按控件类型而非模型字段类型设值（int 默认值 -> QSpinBox，float 默认值
    -> QDoubleSpinBox，str 默认值 -> QComboBox/QLineEdit）。
    """
    for field_name, value in defaults.items():
        widget = widgets.get(field_name)
        if widget is None:
            continue
        widget = _unwrap_optional_widget(widget)
        widget.setEnabled(True)
        widgets[field_name] = widget
        if isinstance(widget, QDoubleSpinBox):
            value_f = float(value)  # type: ignore[arg-type]
            # 标准单位默认值 -> 当前显示单位
            opt = _current_unit_option(field_name, widget)
            if opt is not None:
                value_f /= opt.to_standard
            widget.setValue(value_f)
        elif isinstance(widget, QSpinBox):
            widget.setValue(int(value))  # type: ignore[arg-type]
        elif isinstance(widget, QComboBox):
            if isinstance(value, int):
                # 整数枚举下拉：按 itemData（int）选中
                idx = widget.findData(value)
                if idx >= 0:
                    widget.setCurrentIndex(idx)
                else:
                    widget.setCurrentText(str(value))
            else:
                widget.setCurrentText(str(value))
        elif isinstance(widget, QLineEdit):
            widget.setText(str(value))


def apply_orbit_type_defaults(
    widgets: dict[str, QWidget],
    orbit_type: str,
) -> None:
    """把 orbit_type 分支的默认值填入 widgets 对应控件。

    未知 orbit_type 或字段缺失时静默跳过（无分支则不做任何事）。
    解包/设值机制见 ``_apply_branch_defaults``。
    """
    defaults = ORBIT_TYPE_DEFAULTS.get(orbit_type)
    if not defaults:
        return
    _apply_branch_defaults(widgets, defaults)


def apply_family_type_defaults(
    widgets: dict[str, QWidget],
    family_type: str,
) -> None:
    """把轨道族分支的默认值填入 widgets。

    默认值直接从 ``FamilyGenerationRequest(orbit_type=...)`` 构造结果读取，
    不在 GUI 维护第二份默认表——上游改默认时面板自动跟随。
    """
    from e2m2e.api.models import FamilyGenerationRequest

    try:
        request = FamilyGenerationRequest(orbit_type=family_type)
    except Exception:  # noqa: BLE001 -- 未知族类型静默跳过
        return
    fields = FAMILY_TYPE_FIELDS.get(family_type, set()) | {"libration_point", "n_orbits"}
    defaults: dict[str, Any] = {}
    for name in fields:
        value = getattr(request, name, None)
        if value is not None:
            defaults[name] = value
    if not defaults:
        return
    _apply_branch_defaults(widgets, defaults)


def _apply_numeric_range(
    widget: QDoubleSpinBox | QSpinBox,
    field_name: str,
    numeric_range: Any,
) -> None:
    """把上游 ``NumericRange``（标准单位）写成控件的 Qt 范围、约束状态与提示。

    Qt 上下限按当前显示单位换算；标准单位范围同步写进 ``_STD_MIN_ATTR`` /
    ``_STD_MAX_ATTR``，保证后续单位切换不丢约束。严格边界（开区间）按既有
    gt/lt 惯例内缩 1e-8；排除值（如 Halo 振幅不含 0）Qt 表达不了，写进
    提示说明，留给模型校验拦截。
    """
    lo, hi = numeric_range.minimum, numeric_range.maximum
    std_lo = float(lo) if lo is not None else -1e12
    std_hi = float(hi) if hi is not None else 1e12
    if isinstance(widget, QDoubleSpinBox):
        if lo is not None and not numeric_range.minimum_inclusive:
            std_lo += 1e-8
        if hi is not None and not numeric_range.maximum_inclusive:
            std_hi -= 1e-8
    opt = _current_unit_option(field_name, widget)
    factor = opt.to_standard if opt is not None else 1.0
    if isinstance(widget, QSpinBox):
        widget.setMinimum(int(std_lo))
        widget.setMaximum(int(std_hi))
    else:
        widget.setMinimum(std_lo / factor)
        widget.setMaximum(std_hi / factor)
    widget.setProperty(_STD_MIN_ATTR, std_lo)
    widget.setProperty(_STD_MAX_ATTR, std_hi)
    excluded = getattr(numeric_range, "excluded_values", ())
    note = "不含 " + "/".join(f"{v:g}" for v in excluded) if excluded else ""
    widget.setProperty(
        _BOUNDS_ATTR,
        (
            lo is not None,
            hi is not None,
            note,
            not numeric_range.minimum_inclusive,
            not numeric_range.maximum_inclusive,
        ),
    )
    _apply_range_hint(widget, field_name)


def sync_family_point_params(
    widgets: dict[str, QWidget],
    family_type: str,
    libration_point: int,
) -> None:
    """平动点切换后同步族参数：刷新范围约束（Qt 上下限 + 提示），再把超出
    新点合法范围的当前值替换为该点默认值。

    合法范围与该点默认值都从 ``FamilyGenerationRequest`` 读取（valid_ranges /
    按点构造的模型实例），不在 GUI 维护第二份表。当前值仍在新点范围内的
    用户输入保持不变——例如 Halo 默认 30000 km 是 L2 默认值，切到 L1 后
    超出 L1 折叠点范围（±26908 km），刷新为 L1 默认 25000 km；而用户手输
    的 20000 km 在两点范围内，原样保留。带符号范围（Halo/Axial 负值表
    南族/下族）同步后 Qt 下限放开，负振幅可输入。
    """
    from e2m2e.api.models import FamilyGenerationRequest

    try:
        request = FamilyGenerationRequest(orbit_type=family_type, libration_point=libration_point)
        ranges = FamilyGenerationRequest.valid_ranges(
            family_type.upper(), libration_point=libration_point
        )
    except Exception:  # noqa: BLE001 -- 未知族/点组合静默跳过
        return
    for name in FAMILY_TYPE_FIELDS.get(family_type, set()):
        numeric_range = ranges.get(name)
        widget = widgets.get(name)
        if numeric_range is None or widget is None:
            continue
        widget = _unwrap_optional_widget(widget)
        if not isinstance(widget, (QDoubleSpinBox, QSpinBox)):
            continue
        # 先取当前值（标准单位）：刷新 Qt 范围可能钳位显示值
        current = float(widget.value())
        opt = _current_unit_option(name, widget)
        if opt is not None:
            current *= opt.to_standard
        _apply_numeric_range(widget, name, numeric_range)
        if numeric_range.contains(current):
            continue
        default = getattr(request, name, None)
        if default is not None:
            _apply_branch_defaults(widgets, {name: default})


# ---------------------------------------------------------------------------
# 值读取
# ---------------------------------------------------------------------------


def _read_list_float(widget: QWidget) -> list[float]:
    """从 list_float 容器读取所有 QDoubleSpinBox 值。"""
    result: list[float] = []
    for child in widget.findChildren(QDoubleSpinBox):
        result.append(float(child.value()))
    return result


def _read_epoch(widget: QWidget) -> list[float]:
    """从 epoch 容器按布局顺序读取 6 个 spinbox 值，返回 [年,月,日,时,分,秒]。

    对日历合法性做校验（挡 Feb 30 等 spinbox 范围挡不住的非法日期），
    让收集阶段立即报友好错误，而非等到 SPICE str2et 解析失败。
    """
    import datetime

    values: list[float] = []
    layout = widget.layout()
    if layout is not None:
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item is None:
                continue
            w = item.widget()
            if isinstance(w, (QSpinBox, QDoubleSpinBox)):
                values.append(float(w.value()))

    if len(values) == 6:
        y, mo, d, h, mi, s = (int(v) for v in values)
        try:
            datetime.datetime(y, mo, d, h, mi, s)
        except ValueError as exc:
            raise ValueError(f"非法历元: {exc}") from exc
    return values


def _read_widget_value(name: str, field: Any, widget: QWidget) -> Any:
    """从单个控件读取当前值，按字段类型转换。"""
    inner_tp, is_optional = _unwrap_optional(field.annotation)

    # G7: Optional 容器
    if widget.property("__params_panel_kind") == "optional":
        cb = widget.findChild(QCheckBox)
        if cb and not cb.isChecked():
            return None
        # 找到非 QCheckBox 的内部控件
        inner = _find_inner_widget(widget)
        if inner is not None:
            return _read_widget_value(name, field, inner)

    # epoch 容器（6 个 spinbox）
    if widget.property("__params_panel_kind") == "epoch":
        return _read_epoch(widget)

    # G6: list[float] 容器
    if widget.property("__params_panel_kind") == "list_float":
        values = _read_list_float(widget)
        # 显示单位 -> 标准单位（可切换单位字段，如 srp_offset_m）；
        # 换算缓存（_STD_VALUE_ATTR）避免多次切单位的舍入累积
        opt = _current_unit_option(name, widget)
        if opt is not None:
            out: list[float] = []
            for child, v in zip(widget.findChildren(QDoubleSpinBox), values, strict=False):
                cached = child.property(_STD_VALUE_ATTR)
                if cached is not None and float(cached[0]) == float(v):
                    out.append(float(cached[1]))
                else:
                    out.append(float(v) * opt.to_standard)
            values = out
        return values

    if isinstance(widget, QComboBox):
        data = widget.currentData()
        # 整数枚举下拉：值存 itemData；文本下拉按文本取值
        val = data if isinstance(data, int) else widget.currentText()
    elif isinstance(widget, (QDoubleSpinBox, QSpinBox)):
        val = widget.value()
    elif isinstance(widget, QLineEdit):
        val = widget.text()
    else:
        val = widget  # 不可达（防御）

    if inner_tp is float and isinstance(val, (int, float)):
        result = float(val)
        # 显示单位 -> 标准单位（可切换单位字段）；换算缓存避免舍入累积
        opt = _current_unit_option(name, widget)
        if opt is not None and isinstance(widget, QDoubleSpinBox):
            result = _standard_value_of(widget, opt.to_standard)
        return result
    if inner_tp is int and isinstance(val, (int, float)):
        return int(val)
    return val


def collect_params(widgets: dict[str, QWidget], model_class: type) -> dict[str, Any]:
    """从控件字典收集参数值，返回可传给 FacadeBridge 的 dict。

    ``model_class`` 用于查找字段类型以做正确转换。控件字典若含模型外字段，
    按控件类型直接取值。
    """
    params: dict[str, Any] = {}
    for name, widget in widgets.items():
        field = model_class.model_fields.get(name)
        if field is None:
            # 模型外字段按控件类型取值；可切换单位字段按 FIELD_UNIT_OPTIONS
            # 换算为标准单位。
            opt = _current_unit_option(name, widget)
            if isinstance(widget, QDoubleSpinBox) and opt is not None:
                params[name] = _standard_value_of(widget, opt.to_standard)
            else:
                params[name] = widget.value()  # type: ignore[union-attr]
            continue
        params[name] = _read_widget_value(name, field, widget)
    return params
