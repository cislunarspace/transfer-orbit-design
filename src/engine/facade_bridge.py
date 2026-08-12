"""FacadeBridge -- e2m2e 算法层直调的薄封装。

直接调用 algorithm 层而非 Facade 门面，因为 Facade 返回的 DesignOrbitResponse
剥离了轨道数据（只返回标量汇总），而 GUI 需要完整的 Orbit 对象用于可视化。
详见 docs/adr/0011-algorithm-layer-direct-call.md。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from pydantic import BaseModel


# ---------------------------------------------------------------------------
# DTO
# ---------------------------------------------------------------------------


@dataclass
class OrbitDesignResultData:
    """跨线程传递的轨道设计结果 DTO。

    纯数据类，不含 e2m2e 对象引用。
    numpy 数组通过引用传递，零拷贝。
    """

    orbit_type: str
    epoch_utc: str
    duration_day: float
    initial_state: Any  # np.ndarray (6,)
    cr3bp_jacobi: float
    states: Any  # np.ndarray (n, 6) -- 从 cr3bp_orbit.states 提取
    times: Any  # np.ndarray (n,)   -- 从 cr3bp_orbit.times 提取
    correction_converged: bool
    correction_iterations: int
    mu: float | None = None  # CR3BP 质量比（从 cr3bp_orbit.system.mu 提取，缺失时 None）
    # design_orbit 产出的 GCRS 星历（control_orbit 的标准输入）。
    # None 表示算法层未返回 ephemeris（理论上不会，defensive）。
    ephemeris: dict | None = None  # {year, month, ..., times_jd_tdb}，值均为 ndarray

    # 注意：mu / ephemeris 带默认值放在末尾，保证旧代码按位置/关键字构造 DTO 时不传也能工作。


@dataclass
class ControlResultData:
    """跨线程传递的轨道保持结果 DTO。纯数据，不含 e2m2e 对象引用。"""

    num_failed: int
    sk_statistic_rows: Any  # np.ndarray (n, k)，m/s；k=3 无角动量，k>=4 含
    maneuvers_mjd_tdb: Any  # np.ndarray (n,)
    maneuvers_delta_v_mps: Any  # np.ndarray (n,)，m/s
    controlled_states: Any  # (n,6) 质心归一 synodic 位置 (n,3) + 零速度列；全失败 None
    controlled_times: Any  # (n,) ET 秒（J2000 TDB）；None 若无受控星历
    mu: float | None = None
    # GCRS 惯性位置 km（n,3）。controlled_states 为 None 时本字段也为 None。
    # P1 坐标系切换（会合系 ↔ GCRS）与 P2 帧动画需要真惯性坐标。
    position_km: Any = None
    # 真物理时间（J2000 ET 秒，形状 (n,)）。controlled_states 为 None 时也为 None。
    # 与 controlled_times 同源；分两字段是为了让画布 times（任意单调数组）与
    # 物理时间解耦：P0 画布不读 times_et，但帧动画/GIF 需要它定位真时刻。
    times_et: Any = None


def _reconstruct_et_from_utc(eph: Any) -> np.ndarray:
    """从 EphemerisTable 的 UTC 拆分（year/month/day/hour/minute/second）重建 ET。

    EphemerisTable 只存 UTC 拆分，不直接暴露 ET；P0 起需要真物理时间
    （坐标切换、帧动画），故按 SPICE 历法换算逐点重建。复用 e2m2e
    SPICEManager 的闰秒内核加载机制（design_orbit/control_orbit 算法链路
    本身就构造 SPICEManager，本函数仅保证闰秒内核已 furnsh）。

    格式与 e2m2e.algorithm.station_keeping.monte_carlo._utc_iso 一致，
    second 含小数用 :06.3f（毫秒精度），保证 str2et 双向可复现。
    """
    from e2m2e.data.kernels._spice_loader import get_spiceypy
    from e2m2e.data.kernels.manager import SPICEManager

    SPICEManager()._ensure_leapseconds()
    spice = get_spiceypy()
    n = len(eph)
    et = np.empty(n, dtype=float)
    for k in range(n):
        iso = (
            f"{int(eph.year[k]):04d}-{int(eph.month[k]):02d}-{int(eph.day[k]):02d}"
            f"T{int(eph.hour[k]):02d}:{int(eph.minute[k]):02d}"
            f":{float(eph.second[k]):06.3f}"
        )
        et[k] = spice.str2et(iso)
    return et


# ---------------------------------------------------------------------------
# ToolSpec + TOOL_REGISTRY
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ToolSpec:
    """工具描述：绑定 Pydantic Request 模型、FacadeBridge 方法名、UI 标签。"""

    request_model: type[BaseModel] | None  # Pydantic 模型（None = 无正式模型）
    facade_method: str  # FacadeBridge 方法名
    label: str  # UI 显示名
    enabled: bool  # 是否启用


def _build_tool_registry() -> dict[str, ToolSpec]:
    """延迟构建 TOOL_REGISTRY，避免在 e2m2e 未安装时 import 失败。"""
    try:
        from e2m2e.api.models import ControlOrbitRequest, DesignOrbitRequest
    except ImportError:
        DesignOrbitRequest = None  # type: ignore[misc,assignment]
        ControlOrbitRequest = None  # type: ignore[misc,assignment]

    return {
        "design_orbit": ToolSpec(
            request_model=DesignOrbitRequest,
            facade_method="design_orbit",
            label="轨道设计",
            enabled=True,
        ),
        "control_orbit": ToolSpec(
            request_model=ControlOrbitRequest,
            facade_method="control_orbit",
            label="轨道保持",
            enabled=True,
        ),
        "orbit_family_generation": ToolSpec(
            request_model=None,
            facade_method="generate_family",
            label="轨道族生成",
            enabled=False,
        ),
        "orbit_stability": ToolSpec(
            request_model=None,
            facade_method="analyze_stability",
            label="稳定性分析",
            enabled=False,
        ),
    }


TOOL_REGISTRY: dict[str, ToolSpec] = _build_tool_registry()


# ---------------------------------------------------------------------------
# FacadeBridge
# ---------------------------------------------------------------------------


class FacadeBridge:
    """e2m2e 算法层的薄封装。

    职责：
    - 接收 GUI 参数，调用 e2m2e 算法层
    - 将算法层返回的富对象转换为跨线程 DTO
    - 异常翻译（e2m2e 异常 -> 结构化错误消息）

    不负责：
    - 线程管理（由 QThread Worker 处理）
    - 结果持久化（由 persistence 模块处理）
    """

    def __init__(self, kernel_dir: str | None = None) -> None:
        self._kernel_dir = kernel_dir

    def design_orbit(self, **kwargs: Any) -> OrbitDesignResultData:
        """调用 e2m2e.algorithm.design.design_orbit，返回跨线程 DTO。

        e2m2e 5.6.5 起 ``design_orbit`` 第一个参数为 ``DesignOrbitRequest``
        （散字段不再支持），本方法把 GUI 收集的 kwargs 包成 request 再调用。
        ``kernel_dir`` 不是 request 字段（``extra="forbid"``），单独传入。

        单位换算：GUI ``duration`` 标准单位为年（见
        ``params_panel.FIELD_UNIT_OPTIONS``），e2m2e 5.6.5 起 ``duration`` 字段
        单位为秒，本方法做年→秒换算（``* SECONDS_PER_YEAR``）。

        异常经 translate_exception() 翻译为 OrbitError 后抛出。

        Returns:
            OrbitDesignResultData -- 可安全跨线程传递的纯数据对象。

        Raises:
            OrbitError: 经翻译的结构化错误。
        """
        from e2m2e.algorithm.design import design_orbit
        from e2m2e.api.models import DesignOrbitRequest
        from e2m2e.data.templates import ConvergenceState

        from src.commons.units import SECONDS_PER_YEAR
        from src.engine.exceptions import translate_exception

        # kernel_dir 不是 DesignOrbitRequest 字段（extra="forbid"），单独拎出。
        # 其余 kwargs 都是 collect_params 按 model_fields 收集的合法 request 字段。
        kernel_dir = kwargs.pop("kernel_dir", self._kernel_dir)
        # GUI duration 单位年 -> e2m2e duration 单位秒
        if kwargs.get("duration") is not None:
            kwargs["duration"] = float(kwargs["duration"]) * SECONDS_PER_YEAR
        try:
            request = DesignOrbitRequest(**kwargs)
            result = design_orbit(request, kernel_dir=kernel_dir)
        except Exception as e:
            raise translate_exception(e) from e

        cr3bp_orbit = result.cr3bp_orbit
        if cr3bp_orbit is None:
            # ELFO 场景无 CR3BP 周期轨道（设计结果不携带），GUI 用不到
            raise translate_exception(
                ValueError("设计结果不含 CR3BP 轨道（ELFO 场景不支持 GUI 可视化）")
            ) from None
        # mu 从 cr3bp_orbit.system.mu 提取（design_orbit.py 构造 Orbit 时绑定了
        # CR3BP_System）；三重 getattr 防御 system 缺失或未绑定。
        mu = getattr(getattr(cr3bp_orbit, "system", None), "mu", None)
        eph = getattr(result, "ephemeris", None)
        ephemeris_dict = None
        if eph is not None:
            ephemeris_dict = {
                "year": np.asarray(eph.year),
                "month": np.asarray(eph.month),
                "day": np.asarray(eph.day),
                "hour": np.asarray(eph.hour),
                "minute": np.asarray(eph.minute),
                "second": np.asarray(eph.second),
                "position_km": np.asarray(eph.position_km),
                "velocity_mps": np.asarray(eph.velocity_mps),
                "synodic_position": np.asarray(eph.synodic_position),
                # times_jd_tdb 当前版本不存在，getattr 防御；未来版本若有则存入
                "times_jd_tdb": np.asarray(tjd)
                if (tjd := getattr(eph, "times_jd_tdb", None)) is not None
                else None,
                # 真物理时间（ET 秒）：从 UTC 拆分用 SPICE str2et 重建。
                # control_orbit 用其做会合→惯性坐标转换；帧动画也用它定位真时刻。
                "times_et": _reconstruct_et_from_utc(eph),
            }
        # e2m2e 5.6.6 起 EphemerisCorrectionResult 废除 converged 方言，
        # 收敛判定走统一结果契约 status == ConvergenceState.CONVERGED
        # （上游 #351）。correction 为 None 是 ELFO 场景（无星历修正），视为未收敛。
        correction = result.correction
        correction_converged = (
            correction is not None and correction.status is ConvergenceState.CONVERGED
        )
        return OrbitDesignResultData(
            orbit_type=result.orbit_type,
            epoch_utc=result.epoch_utc,
            duration_day=result.duration_day,
            initial_state=result.initial_state,
            cr3bp_jacobi=result.cr3bp_jacobi,
            mu=mu,
            states=np.asarray(cr3bp_orbit.states),
            times=np.asarray(cr3bp_orbit.times),
            correction_converged=correction_converged,
            correction_iterations=correction.iterations if correction is not None else 0,
            ephemeris=ephemeris_dict,
        )

    def control_orbit(
        self, ephemeris_data: dict, source_mu: float | None, **params: Any
    ) -> ControlResultData:
        """调用 e2m2e.algorithm.station_keeping.control_orbit，返回跨线程 DTO。

        Args:
            ephemeris_data: 来自 orbit Artifact 的 extra["ephemeris"]，
                含重建 EphemerisTable 所需的全字段 ndarray。
            source_mu: 源 orbit Artifact 的 CR3BP 质量比（extra["mu"]）。
                ControlOrbitResult 不暴露 mu，受控星历画地月标注所需，
                由调用方注入，直接写入 DTO（见 plan §5.1）。
            **params: ControlOrbitRequest 的标量字段（control_mode 等），
                由参数面板收集。input_ephemeris 不在其中（由本方法注入）。
        """
        from dataclasses import fields as dc_fields

        from e2m2e.algorithm.station_keeping import control_orbit as _control
        from e2m2e.data.types import EphemerisTable

        from src.engine.exceptions import translate_exception

        # 仅传入 EphemerisTable 实际拥有的字段，排除 times_jd_tdb 等额外键
        valid_keys = {f.name for f in dc_fields(EphemerisTable)}
        eph = EphemerisTable(
            **{k: v for k, v in ephemeris_data.items() if k in valid_keys and v is not None}
        )
        params.setdefault("kernel_dir", self._kernel_dir)
        try:
            result = _control(eph, **params)
        except Exception as e:
            raise translate_exception(e) from e

        controlled = result.controlled_ephemeris
        if controlled is not None and controlled.synodic_position is not None:
            n = len(controlled)
            states = np.zeros((n, 6))
            # 会合系原点偏移：controlled.synodic_position 是地心归一（月球在 +1），
            # 画布地月标注是质心归一（月球在 1−μ）。减 source_mu 后两者对齐，
            # 轨迹与月球标记不再差 μ·DU ≈ 4690 km。source_mu 为 None（旧 Artifact
            # 无 μ）时不偏移（保留旧行为，画布跳过标注）。
            states[:, :3] = controlled.synodic_position - (source_mu or 0.0)
            # 真物理时间：替代旧 np.arange(n) 索引，供坐标切换/帧动画定位真时刻。
            times_et = _reconstruct_et_from_utc(controlled)
            times = times_et
            position_km = np.asarray(controlled.position_km)
        else:
            states = None
            times = None
            times_et = None
            position_km = None

        return ControlResultData(
            num_failed=result.num_failed,
            sk_statistic_rows=np.asarray(result.sk_statistic.rows),
            maneuvers_mjd_tdb=np.asarray(result.maneuvers.mjd_tdb),
            maneuvers_delta_v_mps=np.asarray(result.maneuvers.delta_v_mps),
            controlled_states=states,
            controlled_times=times,
            mu=source_mu,
            position_km=position_km,
            times_et=times_et,
        )
