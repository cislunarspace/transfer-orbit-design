"""FacadeBridge -- e2m2e Facade 门面的薄封装（issue #375）。

三个计算工具（design_orbit / control_orbit / orbit_family_generation）统一走
Facade（ADR 0011 缓解措施 3 的既定清理）：#312 起 Facade 响应携带完整几何
字段，#475（e2m2e 5.8.0）起产物自动入轨道库 catalog 并返回 record_id，
control_orbit 支持 input_record_id 直连库中记录（Facade 解析星历并写谱系）。
轨道库读写（catalog_query/get/tag/promote/export/delete）也经本桥接层转发，
保持 e2m2e 接缝收敛到一处。

库目录：Config.catalog_dir 注入（默认仓库根 catalog/，见 commons.paths）；
kernel_dir 经 Config 注入（request 模型不接受该字段）。

English: FacadeBridge is a thin wrapper over the e2m2e Facade facade (issue #375).
The three compute tools (design_orbit / control_orbit / orbit_family_generation) all go
through the Facade (the established cleanup of ADR 0011 mitigation 3): since #312 the
Facade responses carry complete geometry fields; since #475 (e2m2e 5.8.0) products are
auto-ingested into the orbit catalog and return a record_id, and control_orbit supports
input_record_id linking directly to a catalog record (the Facade resolves the ephemeris
and writes lineage). Orbit-catalog reads/writes (catalog_query/get/tag/promote/export/delete)
also forward through this bridge, keeping the e2m2e seam converged to one place.

Library directory: injected via Config.catalog_dir (repo-root catalog/ by default, see
commons.paths); kernel_dir is injected via Config (request models do not accept that field).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from e2m2e.api.models import FamilyGenerationRequest
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# DTO
# ---------------------------------------------------------------------------


@dataclass
class OrbitDesignResultData:
    """轨道设计结果 DTO。

    纯数据类，不含 e2m2e 对象引用。
    numpy 数组通过引用传递，零拷贝。

    Orbit-design result DTO. Pure data class holding no e2m2e object
    references; numpy arrays pass by reference, zero-copy.
    """

    orbit_type: str
    epoch_utc: str
    duration_day: float
    initial_state: Any  # np.ndarray (6,)
    cr3bp_jacobi: float
    states: Any  # np.ndarray (n, 6) -- 从 cr3bp_orbit.states 提取
    # np.ndarray (n, 6) -- extracted from cr3bp_orbit.states
    times: Any  # np.ndarray (n,)   -- 从 cr3bp_orbit.times 提取
    # np.ndarray (n,) -- extracted from cr3bp_orbit.times
    correction_converged: bool
    correction_iterations: int
    mu: float | None = None  # CR3BP 质量比（从 cr3bp_orbit.system.mu 提取，缺失时 None）
    # CR3BP mass ratio (extracted from cr3bp_orbit.system.mu; None when absent).
    # design_orbit 产出的 GCRS 星历（control_orbit 的标准输入）。
    # GCRS ephemeris produced by design_orbit (the standard input to control_orbit).
    # None 表示算法层未返回 ephemeris（理论上不会，defensive）。
    # None means the algorithm layer returned no ephemeris (should not happen; defensive).
    ephemeris: dict | None = None  # {year, month, ..., times_jd_tdb}，值均为 ndarray
    # mapping {year, month, ..., times_jd_tdb}; all values are ndarrays.
    # 产物入库后的轨道库记录 id（e2m2e 5.8.0 自动入库；None = 未入库）。
    # Orbit-library record id of the ingested product (auto-ingestion since
    # e2m2e 5.8.0; None = not ingested).
    record_id: str | None = None

    # 带默认值的新字段一律放末尾，保持按位置构造的兼容。
    # New fields with defaults always go last, keeping positional construction compatible.


@dataclass
class FamilyResultData:
    """轨道族生成结果 DTO。纯数据类，不含 e2m2e 对象引用。

    族成员轨迹为等长采样（``states``/``times`` 均为 ``(m, n, ...)`` 三维数组）。
    5.7.1 起周期族成员只携带初态与周期（Rust 单次调用契约），桥接层按周期
    重采样到固定点数；Lissajous 拟周期成员本身边带等长完整轨迹。

    Orbit-family generation result DTO. Pure data class holding no e2m2e
    object references. Member trajectories are sampled to equal lengths
    (``states``/``times`` are both ``(m, n, ...)`` 3-D arrays). Since 5.7.1
    periodic members carry only an initial state and a period (the Rust
    single-call contract); the bridge resamples them per period to a fixed
    point count, while quasi-periodic Lissajous members already carry
    equal-length full trajectories.
    """

    orbit_type: str  # 显示名（"Halo"/"NRHO"/"Axial"/"Lissajous"/"SPO"/"LPO"/"Horseshoe"/"DRO"）
    # Display name ("Halo"/"NRHO"/"Axial"/"Lissajous"/"SPO"/"LPO"/"Horseshoe"/"DRO").
    libration_point: int | None  # None = 月心族（DRO），不绑定平动点
    # None = Moon-centered family (DRO), not tied to a libration point.
    n_orbits: int  # 实际生成的成员数（可能少于请求数，延拓终止或软失败保留部分族）
    # Number of members actually generated (may be fewer than requested;
    # continuation terminated or soft failure keeps a partial family).
    mu: float
    states: Any  # (m, n, 6) -- 各族成员 CR3BP 状态
    # (m, n, 6) -- CR3BP states of family members
    times: Any  # (m, n) -- 各族成员时间序列（无量纲 TU）
    # (m, n) -- time series per member (dimensionless TU)
    z0s: Any = None  # (m,)，仅 Halo：各族成员面外振幅 z0（北族为正、南族为负）；其它族 None
    # (m,) Halo only: out-of-plane amplitude z0 per member (positive north,
    # negative south); None for other families.
    family_type: str = "halo"  # e2m2e 规范族标识（小写）
    # Canonical e2m2e family identifier (lowercase).
    periodicity: str = "periodic"  # "periodic" / "quasi-periodic"（Lissajous）
    # "periodic" / "quasi-periodic" (Lissajous).
    status_message: str = ""  # 软失败（部分族）时的上游状态消息；全量收敛为 ""
    # Upstream status message on soft failure (partial family); "" when fully converged.
    member_parameters: list = field(default_factory=list)  # 各族成员的族参数 dict
    # Per-member family-parameter dicts.
    record_id: str | None = None  # 产物入库后的轨道库记录 id（未入库为 None）
    # Orbit-library record id of the ingested product (None when not ingested).


@dataclass
class TransferDesignResultData:
    """转移轨道设计结果 DTO（纯数据，不含 e2m2e 对象）。

    Transfer-design result DTO (pure data, no e2m2e objects).
    """

    transfer_type: str
    delta_v: float  # km/s
    message: str
    converged: bool
    # HMN 为地心惯性系状态序列 (n, 6)（km, km/s）；LGA/WSB 当前恒 None
    # trajectory holds HMN Earth-centered inertial states (n, 6) in km and km/s;
    # LGA/WSB are currently always None.
    trajectory: Any | None = None
    details: dict[str, Any] | None = None


@dataclass
class PropagationResultData:
    """轨道预报结果 DTO。纯数据类，不含 e2m2e 对象引用。

    轨道预报产物不入轨道库（e2m2e 未提供该工具的入库），落盘走
    ``persistence.save_propagation_result``（output/propagation/）。

    Orbit-propagation result DTO. Pure data class holding no e2m2e object
    references. Propagation products are not ingested into the orbit catalog
    (e2m2e provides no ingestion for this tool); persistence goes through
    ``persistence.save_propagation_result`` (output/propagation/).
    """

    epoch_utc: str  # 起始历元 ISO（epoch 为列表时由桥接层格式化）
    # Start epoch as ISO (formatted by the bridge when epoch is a list).
    duration_sec: float
    n_points: int
    times_et: Any  # (n,) ET 秒（times_jd_tdb − J2000 JD）× 86400，ADR 0013
    # (n,) ET seconds ((times_jd_tdb - J2000 JD) x 86400), ADR 0013.
    position_km: Any  # (n,3) GCRS km
    velocity_km_s: Any  # (n,3) GCRS km/s
    synodic_position: Any  # (n,3) 质心归一脉动会合系（画布槽位契约）
    # (n,3) barycenter-normalized pulsating rotating frame (canvas slot contract).
    final_state: Any  # (6,) 末端 [r; v]（km, km/s）
    # (6,) terminal state [r; v] in km and km/s.
    mu: float = 0.0  # 会合系转换所用质量比（默认地月）
    # Mass ratio used for the rotating-frame conversion (Earth-Moon default).


@dataclass
class StabilityResultData:
    """稳定性分析结果 DTO。纯数据，不含 e2m2e 对象引用。

    数组字段（monodromy/eigenvalues）保留 ndarray；落盘时由调用方
    tolist 序列化。

    Stability-analysis result DTO. Pure data, no e2m2e object references.
    Array fields (monodromy/eigenvalues) stay ndarray; callers serialize
    them with tolist when persisting.
    """

    monodromy_matrix: Any | None  # (6,6)
    eigenvalues: Any | None  # (6,)
    stability_indices: dict  # {nu1, nu2, nu3, broucke}
    classification: dict
    bifurcation: dict
    numerical_errors: dict


@dataclass
class ControlResultData:
    """轨道保持结果 DTO。纯数据，不含 e2m2e 对象引用。

    Station-keeping result DTO. Pure data, no e2m2e object references.
    """

    num_failed: int
    sk_statistic_rows: Any  # np.ndarray (n, k)，m/s；k=3 无角动量，k>=4 含
    # np.ndarray (n, k) in m/s; k=3 without angular momentum, k>=4 with it.
    maneuvers_mjd_tdb: Any  # np.ndarray (n,)
    maneuvers_delta_v_mps: Any  # np.ndarray (n,)，m/s
    # np.ndarray (n,) in m/s.
    controlled_states: Any  # (n,6) 质心归一 synodic 位置 (n,3) + 零速度列；全失败 None
    # (n,6): barycenter-normalized synodic positions (n,3) plus a zero velocity
    # column; None if all arcs failed.
    controlled_times: Any  # (n,) ET 秒（J2000 TDB）；None 若无受控星历
    # (n,) ET seconds (J2000 TDB); None when no controlled ephemeris exists.
    mu: float | None = None
    # GCRS 惯性位置 km（n,3）。controlled_states 为 None 时本字段也为 None。
    # P1 坐标系切换（会合系 ↔ GCRS）与 P2 帧动画需要真惯性坐标。
    # GCRS inertial positions in km (n,3); also None when controlled_states is
    # None. P1 frame switching (rotating <-> GCRS) and P2 frame animation need
    # true inertial coordinates.
    position_km: Any = None
    # 真物理时间（J2000 ET 秒，形状 (n,)）。controlled_states 为 None 时也为 None。
    # 与 controlled_times 同源；分两字段是为了让画布 times（任意单调数组）与
    # 物理时间解耦：P0 画布不读 times_et，但帧动画/webm 录制需要它定位真时刻。
    # True physical time (J2000 ET seconds, shape (n,)); also None when
    # controlled_states is None. Same source as controlled_times; split into
    # two fields so canvas times (any monotonic array) stay decoupled from
    # physical time: the P0 canvas ignores times_et, but frame animation and
    # webm recording need it to locate real epochs.
    times_et: Any = None
    record_id: str | None = None  # 产物入库后的轨道库记录 id（全失败无记录为 None）
    # Orbit-library record id of the ingested product (None when all arcs failed).


#: 周期族成员重采样点数（5.7.1 起周期族成员只携带初态与周期）。
#: Resample count for periodic family members (since 5.7.1 they carry only
#: an initial state and a period).
_FAMILY_MEMBER_SAMPLES = 200


#: SPICE ET 定义：J2000 历元（JD TDB 2451545.0）起的 TDB 秒。
#: SPICE ET definition: TDB seconds since the J2000 epoch (JD TDB 2451545.0).
_J2000_JD_TDB = 2451545.0

#: 地月系统默认特征时间（秒），SynodicJ2000System 在 CR3BP 系统未携带
#: characteristic_time 时使用同一默认值。
#: Default Earth-Moon characteristic time in seconds; SynodicJ2000System uses
#: the same default when its CR3BP system carries no characteristic_time.
_TU_SECONDS_FALLBACK = 4.34811305 * 86400.0


def _epoch_list_to_iso(epoch: Any) -> str | None:
    """[年,月,日,时,分,秒] → ISO 字符串；非 6 元序列返回 None。

    Convert [year,month,day,hour,minute,second] to an ISO string; return None
    for non-6-element sequences.
    """
    if not isinstance(epoch, (list, tuple)) or len(epoch) != 6:
        return None
    y, mo, d, h, mi, s = epoch
    return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}T{int(h):02d}:{int(mi):02d}:{float(s):06.3f}"


def gcrs_to_synodic(
    position_km: Any,
    velocity_km_s: Any,
    times_et: Any,
    mu: float | None = None,
    kernel_dir: str | None = None,
) -> Any:
    """GCRS km 状态序列 → 质心归一脉动会合系位置 (n,3)（画布槽位契约，ADR 0013）。

    复用 e2m2e ``SynodicJ2000System`` 的批量 Rust 转换：输出原点在质心
    （地球 −μ、月球 1−μ），与 ``centroid_normalized_states`` 同一约定。
    需要行星历内核：先经 ``load_design_kernels`` 确保 SPICEManager 已加载
    （预报链路通常已加载，重复调用由 SPICEManager 去重）。

    Convert GCRS km state sequences to barycenter-normalized pulsating
    rotating-frame positions (n,3) (the canvas slot contract, ADR 0013).
    Reuses e2m2e ``SynodicJ2000System`` batch Rust conversion: the output
    origin sits at the barycenter (Earth at −μ, Moon at 1−μ), the same
    convention as ``centroid_normalized_states``. Requires planetary
    ephemeris kernels: ensure SPICEManager is loaded via
    ``load_design_kernels`` first (the propagation chain usually has them
    loaded; SPICEManager dedupes repeat calls).
    """
    from e2m2e.algorithm.coordinate.synodic_j2000 import SynodicJ2000System
    from e2m2e.algorithm.design.design_orbit import load_design_kernels
    from e2m2e.data.kernels.manager import SPICEManager
    from e2m2e.data.templates.seed import EARTH_MOON_MU

    from src.engine.viz_adapter import build_cr3bp_system

    spice = SPICEManager()
    load_design_kernels(spice, kernel_dir)
    cr3bp = build_cr3bp_system(EARTH_MOON_MU if mu is None else float(mu))
    system = SynodicJ2000System(cr3bp, spice)
    tu = cr3bp.characteristic_time or _TU_SECONDS_FALLBACK
    et = np.asarray(times_et, dtype=float)
    t_syn = (et - et[0]) / tu
    states = np.hstack(
        [np.asarray(position_km, dtype=float), np.asarray(velocity_km_s, dtype=float)]
    )
    syn = system.batch_j2000_to_synodic(states, t_syn, float(et[0]))
    return np.asarray(syn, dtype=float)[:, :3]


def centroid_normalized_states(synodic_position: Any, mu: float | None) -> Any:
    """会合系位置（地心归一，月球在 +1）→ 画布质心归一状态 (n,6)（月球在 1−μ）。

    站保响应与 catalog 记录懒加载共用；mu 为 None（旧产物无 μ）时不偏移
    （保留旧行为，画布跳过标注）。速度列补零。

    Convert rotating-frame positions (Earth-centered normalized, Moon at
    +1) to canvas barycenter-normalized states (n,6) (Moon at 1−μ). Shared
    by station-keeping responses and lazy catalog-record loading; when mu is
    None (legacy products without μ) no shift is applied (old behavior
    kept; the canvas skips annotations). Velocity columns are zero-filled.
    """
    syn = np.asarray(synodic_position, dtype=float)
    states = np.zeros((syn.shape[0], 6))
    states[:, :3] = syn - (mu or 0.0)
    return states


def _ephemeris_table_from_mapping(mapping: dict) -> Any:
    """从 Facade 响应的星历 dict（JSON 兼容，值为 list/ndarray）重建 EphemerisTable。

    仅取 EphemerisTable 实际拥有的字段，忽略 times_et 等额外键与 None 值
    （times_jd_tdb 设计链路不填）。

    Rebuild an EphemerisTable from the Facade response's ephemeris dict
    (JSON-compatible, values list/ndarray). Only fields actually owned by
    EphemerisTable are taken; extra keys such as times_et and None values
    are ignored (times_jd_tdb is unfilled on the design chain).
    """
    from dataclasses import fields as dc_fields

    from e2m2e.data.types import EphemerisTable

    valid_keys = {f.name for f in dc_fields(EphemerisTable)}
    fields: dict[str, Any] = {
        k: np.asarray(v) for k, v in mapping.items() if k in valid_keys and v is not None
    }
    return EphemerisTable(**fields)


def resample_periodic_member(
    dynamics: Any,
    initial_state: Any,
    period: float,
    samples: int = _FAMILY_MEMBER_SAMPLES,
) -> tuple[Any, Any]:
    """按周期把单初态族成员重采样为整条轨迹（画布渲染契约）。

    5.7.1 起周期族成员只携带初态 (1,6) 与周期（Rust 单次调用契约），catalog
    族记录与 Facade 族响应同为该形态，画布需要整条轨迹，传播走 Rust 后端
    （毫秒级）。返回 ``(states (n,6), times (n,))``。

    Resample a single-initial-state periodic family member into a full
    trajectory by its period (the canvas rendering contract). Since 5.7.1
    periodic members carry only an initial state (1,6) and a period (the
    Rust single-call contract); catalog family records and Facade family
    responses share this shape, the canvas needs full trajectories, and
    propagation goes through the Rust backend (milliseconds). Returns
    ``(states (n,6), times (n,))``.
    """
    t_eval = np.linspace(0.0, float(period), samples)
    propagated = dynamics.propagate(np.asarray(initial_state), (0.0, float(period)), t_eval=t_eval)
    return np.asarray(propagated["states"]), t_eval


def _reconstruct_et_from_utc(eph: Any) -> np.ndarray:
    """从 EphemerisTable 的 UTC 拆分（year/month/day/hour/minute/second）重建 ET。

    EphemerisTable 只存 UTC 拆分，不直接暴露 ET；P0 起需要真物理时间
    （坐标切换、帧动画），故按 SPICE 历法换算逐点重建。复用 e2m2e
    SPICEManager 的闰秒内核加载机制（design_orbit/control_orbit 算法链路
    本身就构造 SPICEManager，本函数仅保证闰秒内核已 furnsh）。

    格式与 e2m2e.algorithm.station_keeping.monte_carlo._utc_iso 一致，
    second 含小数用 :06.3f（毫秒精度），保证 str2et 双向可复现。

    Rebuild ET from EphemerisTable's UTC components
    (year/month/day/hour/minute/second). EphemerisTable stores only the UTC
    split and does not expose ET directly; since P0 true physical time is
    needed (frame switching, frame animation), so each point is rebuilt via
    the SPICE calendar. Reuses e2m2e SPICEManager's leap-second kernel
    loading (the design_orbit/control_orbit chains already construct a
    SPICEManager; this function only ensures the leap-second kernel is
    furnished). The format matches
    e2m2e.algorithm.station_keeping.monte_carlo._utc_iso, with fractional
    seconds via :06.3f (millisecond precision) so str2et round-trips
    reproducibly.
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


def _coerce_engine_layout(layout: Any, control_mode: int) -> Any:
    """把面板收集的 engine_layout 规范化为算法层可消费的值。

    - ``control_mode < 4``：角动量管理未启用，engine_layout 无意义；e2m2e
      虽不使用但会无条件 validate（访问 ``.E_r``），字符串随手输入直接
      AttributeError，故置 None 忽略。
    - ``control_mode >= 4``：None 原样（e2m2e 会提示需提供 engine_layout，
      经翻译层给出清晰错误）；dict（``positions_m``/``directions``）构造
      ``EngineLayout``；``EngineLayout`` 实例原样；其余值（如 JSON 文本框
      里的 "4"）报 INVALID_PARAMS 清晰错误。

    Normalize the panel-collected engine_layout into a value the algorithm
    layer can consume:

    - ``control_mode < 4``: angular-momentum management is off and
      engine_layout is meaningless; e2m2e does not use it yet still
      validates unconditionally (accessing ``.E_r``), so arbitrary strings
      raise a raw AttributeError — hence set None to ignore.
    - ``control_mode >= 4``: None passes through unchanged (e2m2e prompts
      for engine_layout and the translation layer surfaces a clear error);
      a dict (``positions_m``/``directions``) constructs an
      ``EngineLayout``; an ``EngineLayout`` instance passes through as-is;
      any other value (e.g. the string "4" from a JSON text box) raises a
      clear INVALID_PARAMS error.
    """
    from e2m2e.algorithm.station_keeping import EngineLayout

    from src.engine.exceptions import OrbitError

    if control_mode < 4:
        return None
    # 空字符串（前端输入框未填写）归一为 None：透传空串同样会触发
    # e2m2e 的 validate（AttributeError），且 None 才能走到"需提供
    # engine_layout 的清晰报错路径
    # Normalize empty strings (frontend input left blank) to None: passing an
    # empty string through would likewise trip e2m2e's validate
    # (AttributeError), and only None reaches the clear "engine_layout
    # required" error path.
    if layout is None or (isinstance(layout, str) and not layout.strip()):
        return None
    if isinstance(layout, str):
        try:
            layout = json.loads(layout)
        except json.JSONDecodeError as exc:
            raise OrbitError("INVALID_PARAMS", f"engine_layout JSON 无效: {exc}") from exc
    if isinstance(layout, EngineLayout):
        return layout
    if isinstance(layout, dict):
        try:
            return EngineLayout(**layout)
        except (TypeError, ValueError) as exc:
            raise OrbitError("INVALID_PARAMS", f"engine_layout 无效: {exc}") from exc
    raise OrbitError(
        "INVALID_PARAMS",
        f"engine_layout 需为发动机布局 JSON（positions_m/directions）或留空，当前 {layout!r}",
    )


# ---------------------------------------------------------------------------
# ToolSpec + TOOL_REGISTRY
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ToolSpec:
    """工具描述：绑定 Pydantic Request 模型、facade 方法名、UI 标签。

    Tool descriptor: binds a Pydantic Request model, the facade method name,
    and UI labels.
    """

    request_model: type[BaseModel] | None  # Pydantic 模型（None = 无正式模型）
    # Pydantic model (None = no formal model).
    # e2m2e facade 方法名（== TOOL_REGISTRY 键，与 mcp_tools 清单对齐）。
    # 注意：FacadeBridge 方法名另见 FacadeBridge 类（design_orbit/control_orbit/
    # generate_family/analyze_stability），与本字段不一一同名。
    # e2m2e facade method name (== TOOL_REGISTRY key, aligned with the mcp_tools
    # inventory). Note: FacadeBridge method names live on the FacadeBridge class
    # (design_orbit/control_orbit/generate_family/analyze_stability) and are not
    # all identical to this field.
    facade_method: str
    label: str  # UI 显示名
    # UI display name.
    description: str  # 工具说明（面板顶部展示，用用户概念而非实现术语）
    # Tool description (shown atop the panel; user concepts, not implementation jargon).
    enabled: bool  # 是否启用（False = 工具下拉灰显，悬停显示工具说明）
    # Enabled flag (False = grayed out in the tool dropdown, tooltip shows the description).


#: GUI 已接入工具的元数据（label/description/enabled/request_model 绑定）。
#: Metadata for tools wired into the GUI (label/description/enabled/request_model bindings).
#: 表外 facade 工具自动灰显（悬停显示工具说明），e2m2e 新增工具时
#: GUI 清单零改动跟随。facade 工具清单见 ``e2m2e.api.Facade.mcp_tools()``。
#: Unlisted facade tools gray out automatically (tooltip shows their status);
#: when e2m2e adds tools the GUI list follows with zero changes. See
#: ``e2m2e.api.Facade.mcp_tools()`` for the facade tool inventory.
_TOOL_META: dict[str, dict[str, Any]] = {
    "design_orbit": {
        "label": "轨道设计",
        "description": "在 CR3BP 模型中生成周期轨道并修正到星历模型；"
        "结果与标称星历叠加显示在画布。",
        "enabled": True,
        "model": "DesignOrbitRequest",
    },
    "control_orbit": {
        "label": "轨道保持",
        "description": "以选中轨道工件的标称星历为输入，做带导航、机动与"
        "光压误差的蒙特卡洛轨道保持仿真，输出受控星历与机动 Δv 统计。",
        "enabled": True,
        "model": "ControlOrbitRequest",
    },
    "orbit_family_generation": {
        "label": "轨道族生成",
        "description": "生成 CR3BP 轨道族：Halo/NRHO/Axial/SPO/LPO/Horseshoe/DRO 为周期"
        "延拓族（DRO 为月心族、不绑定平动点），Lissajous 为拟周期轨迹参数采样；"
        "画布按成员逐条叠加渲染。",
        "enabled": True,
        "model": "FamilyGenerationRequest",
    },
    "orbit_stability": {
        "label": "稳定性分析",
        "description": "对选中轨道的 CR3BP 周期解做稳定性分析：Floquet 乘子、"
        "稳定性指数与分岔检测。右键轨道工件触发，不进工具下拉。",
        "enabled": False,
        "model": None,
    },
    "transfer_design": {
        "label": "转移设计",
        "description": "从地球停泊轨道出发设计地月转移轨道：直接霍曼转移，"
        "或经月球引力辅助进入选中轨道工件的目标点；输出总 Δv 与转移轨迹。",
        "enabled": True,
        "model": "TransferDesignRequest",
    },
    "orbit_propagation": {
        "label": "轨道预报",
        "description": "以 GCRS 初值做高精度力模型数值外推（默认三体），"
        "输出星历轨迹，惯性系/会合系叠加显示在画布；选中星历工件时初值"
        "预填为其末端状态。",
        "enabled": True,
        "model": "PropagationRequest",
    },
    "spacetime_transform": {
        "label": "时空坐标转换",
        "description": "时空坐标转换",
        "enabled": False,
        "model": None,
    },
    "transfer_search": {
        "label": "转移搜索",
        "description": "转移网格搜索",
        "enabled": False,
        "model": None,
    },
    "low_thrust_design": {
        "label": "小推力设计",
        "description": "小推力转移设计",
        "enabled": False,
        "model": None,
    },
    "manifold_analysis": {
        "label": "不变流形分析",
        "description": "不变流形分析",
        "enabled": False,
        "model": None,
    },
    "low_energy_transfer": {
        "label": "低能转移",
        "description": "低能转移",
        "enabled": False,
        "model": None,
    },
    "relative_motion": {
        "label": "相对运动",
        "description": "相对运动",
        "enabled": False,
        "model": None,
    },
}

#: GUI 下拉展示顺序（enabled 工具在前；表外 facade 工具按方法名排序追加）。
#: GUI dropdown order (enabled tools first; unlisted facade tools appended sorted by name).
_TOOL_ORDER: tuple[str, ...] = (
    "design_orbit",
    "control_orbit",
    "orbit_family_generation",
    "orbit_stability",
    "transfer_design",
    "orbit_propagation",
    "spacetime_transform",
    "transfer_search",
    "low_thrust_design",
    "manifold_analysis",
    "low_energy_transfer",
    "relative_motion",
)


_GUI_INTEGRATED_TOOLS = frozenset(
    {
        "design_orbit",
        "control_orbit",
        "orbit_family_generation",
        "orbit_stability",
        "transfer_design",
        "orbit_propagation",
    }
)
_TOOL_STATUS_DESCRIPTIONS = {
    "implemented": "e2m2e 已实现，GUI 尚未接入",
    "placeholder": "e2m2e 占位，未实现",
}


def _build_tool_registry() -> dict[str, ToolSpec]:
    """构建 TOOL_REGISTRY，与 e2m2e facade 工具清单及实现状态对齐。

    e2m2e 更新后新 facade 工具自动出现在清单中（灰显，悬停显示实现状态）；
    已接入 GUI 的工具仍由本地元数据定义标签与说明。

    Build TOOL_REGISTRY aligned with the e2m2e facade tool inventory and
    implementation status. After an e2m2e update new facade tools appear in
    the registry automatically (grayed out; hovering shows implementation
    status); tools already wired into the GUI still get labels and
    descriptions from local metadata.
    """
    inventory: dict[str, Any] = {}
    models: dict[str, type[BaseModel] | None] = {
        "DesignOrbitRequest": None,
        "ControlOrbitRequest": None,
        "FamilyGenerationRequest": FamilyGenerationRequest,
    }
    try:
        from e2m2e.api import Facade, tool_inventory

        inventory = {info.name: info for info in tool_inventory(Facade())}
        for info in inventory.values():
            if info.request_model is not None:
                models[info.request_model.__name__] = info.request_model
    except Exception:  # noqa: BLE001 -- facade 异常时退回本地最小清单 / fallback to local list
        inventory = {
            name: None for name in ("design_orbit", "control_orbit", "orbit_family_generation")
        }

    facade_names = list(inventory)
    ordered = [n for n in _TOOL_ORDER if n in facade_names]
    ordered += sorted(set(facade_names) - set(ordered))

    registry: dict[str, ToolSpec] = {}
    for name in ordered:
        meta = _TOOL_META.get(name, {})
        description = meta.get("description", "该工具")
        info = inventory.get(name)
        if name not in _GUI_INTEGRATED_TOOLS and info is not None:
            status = _TOOL_STATUS_DESCRIPTIONS.get(info.status, "当前状态未知")
            description = f"{description}（{status}）。"
        elif "description" not in meta:
            description = "该工具暂不可用，当前界面尚未提供入口。"
        model_key = meta.get("model")
        registry[name] = ToolSpec(
            request_model=models.get(model_key) if model_key else None,
            facade_method=name,
            label=meta.get("label", name),
            description=description,
            enabled=bool(meta.get("enabled", False)),
        )
    return registry


TOOL_REGISTRY: dict[str, ToolSpec] = _build_tool_registry()


#: e2m2e 规范族标识（小写）-> GUI 显示名。
#: Canonical e2m2e family identifier (lowercase) -> GUI display name.
_FAMILY_DISPLAY_NAMES = {
    "halo": "Halo",
    "nrho": "NRHO",
    "axial": "Axial",
    "lissajous": "Lissajous",
    "spo": "SPO",
    "lpo": "LPO",
    "horseshoe": "Horseshoe",
    "dro": "DRO",
}


# ---------------------------------------------------------------------------
# FacadeBridge
# ---------------------------------------------------------------------------


class FacadeBridge:
    """e2m2e Facade 的薄封装。

    职责：
    - 接收 GUI 参数，经 Facade 调用 e2m2e（产物自动入轨道库）
    - 将 Facade 响应转换为纯数据 DTO
    - 轨道库读写转发（catalog_query/get/tag/promote/export/delete）
    - 异常翻译（e2m2e 异常 -> 结构化错误消息）

    不负责：
    - 线程/进程管理（界面链路经 Tauri 壳与 sidecar 子进程完成）
    - Artifact 语义（由 catalog 模块处理）

    kernel_dir / catalog_dir 经 ``e2m2e.api.config.Config`` 注入 Facade
    （request 模型不接受这两个字段）；Facade 按需惰性构造（catalog 首次
    使用才产生目录副作用）。

    A thin wrapper over the e2m2e Facade. Responsibilities: take GUI
    parameters and call e2m2e through the Facade (products auto-ingest into
    the orbit catalog); convert Facade responses into pure-data DTOs;
    forward orbit-catalog reads/writes
    (catalog_query/get/tag/promote/export/delete); translate exceptions
    (e2m2e exceptions -> structured error messages). Not responsible for:
    thread/process management (the UI chain goes through the Tauri shell
    and the sidecar child process) or Artifact semantics (handled by the
    catalog module). kernel_dir / catalog_dir are injected into the Facade
    via ``e2m2e.api.config.Config`` (request models accept neither field);
    the Facade is constructed lazily on demand (catalog directory
    side effects appear only on first use).
    """

    def __init__(
        self,
        kernel_dir: str | None = None,
        catalog_dir: str | None = None,
    ) -> None:
        self._kernel_dir = kernel_dir
        if catalog_dir is None:
            from src.commons.paths import CATALOG_DIR

            catalog_dir = str(CATALOG_DIR)
        self._catalog_dir = catalog_dir
        self._facade_obj: Any | None = None

    def _facade(self) -> Any:
        """按需构造 Facade（Config 注入 kernel_dir / catalog_dir）。

        Construct the Facade on demand (kernel_dir / catalog_dir injected via
        Config).
        """
        if self._facade_obj is None:
            from e2m2e.api import Facade
            from e2m2e.api.config import Config

            config = Config()
            if self._kernel_dir:
                config.kernel_dir = self._kernel_dir
            if self._catalog_dir:
                config.catalog_dir = self._catalog_dir
            self._facade_obj = Facade(config=config)
        return self._facade_obj

    def _translated(self, call: Any) -> Any:
        """执行 Facade 调用并把异常翻译为 OrbitError（catalog 接缝统一出口）。

        Run a Facade call and translate exceptions into OrbitError (the unified
        outlet of the catalog seam).
        """
        from src.engine.exceptions import translate_exception

        try:
            return call()
        except Exception as e:
            raise translate_exception(e) from e

    def design_orbit(self, **kwargs: Any) -> OrbitDesignResultData:
        """经 Facade 调用 design_orbit，返回纯数据 DTO（产物自动入库）。

        ``kernel_dir`` 不是 request 字段（``extra="forbid"``），经 Config 注入；
        其余 kwargs 是 collect_params 按 model_fields 收集的合法 request 字段。

        单位换算：前端 ``duration`` 标准单位为年，e2m2e 的 ``duration`` 字段
        单位为秒，本方法做年→秒换算（``* SECONDS_PER_YEAR``）。

        Lissajous 与 Halo/NRHO/DPO 同为不稳定轨道，e2m2e 仅自动把 Halo/NRHO/DPO 重定向
        到 segmented；Lissajous 若沿用 standard/two_level，一圈修正后的自由外推
        会沿不稳定流形发散。GUI 不暴露 segmented，因此在此固定走分段修正，
        保持整段标称星历有界。

        异常经 translate_exception() 翻译为 OrbitError 后抛出。

        English: call design_orbit through the Facade and return a
        pure-data DTO (products auto-ingest). ``kernel_dir`` is not a
        request field (``extra="forbid"``) and is injected via Config; the
        other kwargs are legitimate request fields collected by
        collect_params per model_fields. Unit conversion: the frontend
        ``duration`` canonical unit is years while e2m2e's ``duration`` is
        seconds, so this method converts years to seconds. Lissajous
        orbits are unstable like Halo/NRHO/DPO, but e2m2e only
        auto-redirects Halo/NRHO/DPO to segmented; with standard/
        two_level the free propagation after one-loop correction diverges
        along the unstable manifold. The GUI does not expose segmented, so
        segmented correction is fixed here to keep the whole nominal
        ephemeris bounded. Exceptions are translated into OrbitError via
        translate_exception().

        Returns:
            OrbitDesignResultData -- 可安全跨边界传递的纯数据对象。
            Pure-data object safe to pass across boundaries.

        Raises:
            OrbitError: 经翻译的结构化错误。Translated structured error.
        """
        from e2m2e.data.templates import ConvergenceState

        from src.commons.units import SECONDS_PER_YEAR
        from src.engine.exceptions import translate_exception

        # 兼容旧调用习惯：kwargs 携带 kernel_dir 时丢弃（经 Config 注入）
        # Legacy-call compatibility: drop kernel_dir from kwargs (injected via Config).
        kwargs.pop("kernel_dir", None)
        # GUI duration 单位年 -> e2m2e duration 单位秒
        # GUI duration in years -> e2m2e duration in seconds.
        if kwargs.get("duration") is not None:
            kwargs["duration"] = float(kwargs["duration"]) * SECONDS_PER_YEAR
        orbit_type = kwargs.get("orbit_type")
        if isinstance(orbit_type, str) and orbit_type.upper() == "LISSAJOUS":
            kwargs["correction_method"] = "segmented"
        try:
            response = self._facade().design_orbit(**kwargs)
        except Exception as e:
            raise translate_exception(e) from e

        if not response.states:
            # ELFO 场景无 CR3BP 周期轨道（设计结果不携带），GUI 用不到
            # ELFO scenarios have no CR3BP periodic orbit (absent from the result);
            # the GUI cannot use them.
            raise translate_exception(
                ValueError("设计结果不含 CR3BP 轨道（ELFO 场景不支持 GUI 可视化）")
            ) from None
        # Facade 的星历 dict 是 JSON 兼容形态（list），重建 EphemerisTable 后
        # 统一经 _reconstruct_et_from_utc 补 times_et（星历段不落盘该字段）
        # The Facade ephemeris dict is JSON-compatible (lists); rebuild an
        # EphemerisTable, then backfill times_et uniformly via
        # _reconstruct_et_from_utc (the segment does not persist that field).
        ephemeris_dict = None
        if response.ephemeris:
            ephemeris_dict = {
                k: np.asarray(v) for k, v in response.ephemeris.items() if v is not None
            }
            ephemeris_dict["times_et"] = _reconstruct_et_from_utc(
                _ephemeris_table_from_mapping(response.ephemeris)
            )
        # 5.6.6 起收敛判定走统一结果契约 status == ConvergenceState.CONVERGED
        # Convergence check uses the unified result contract since 5.6.6:
        # status == ConvergenceState.CONVERGED.
        return OrbitDesignResultData(
            orbit_type=response.orbit_type,
            epoch_utc=response.epoch_utc,
            duration_day=response.duration_day,
            initial_state=np.asarray(response.initial_state, dtype=float),
            cr3bp_jacobi=response.cr3bp_jacobi,
            mu=response.mu,
            states=np.asarray(response.states, dtype=float),
            times=np.asarray(response.times, dtype=float),
            correction_converged=response.status is ConvergenceState.CONVERGED,
            correction_iterations=response.correction_iterations,
            ephemeris=ephemeris_dict,
            record_id=response.record_id,
        )

    def control_orbit(
        self, ephemeris_data: dict | None, source_mu: float | None, **params: Any
    ) -> ControlResultData:
        """经 Facade 调用 control_orbit，返回跨线程 DTO（产物自动入库）。

        Args:
            ephemeris_data: 来自 orbit Artifact 的 extra["ephemeris"]，
                含重建 EphemerisTable 所需的全字段 ndarray。仅在
                ``input_record_id`` 未提供时使用（None 允许）。
            source_mu: 源 orbit Artifact 的 CR3BP 质量比（extra["mu"]）。
                经 request.mu 透传到响应（画地月标注所需，算法层不消费）。
            **params: ControlOrbitRequest 的标量字段（control_mode 等），
                由参数面板收集；``input_record_id`` 由调用方注入（库中记录
                直连，Facade 解析星历段并写谱系 source_record_id）。

        English: call control_orbit through the Facade and return a
        cross-thread DTO (products auto-ingest). ``ephemeris_data`` comes
        from the orbit Artifact's extra["ephemeris"] and holds all-field
        ndarrays needed to rebuild an EphemerisTable; it is used only when
        ``input_record_id`` is absent (None allowed). ``source_mu`` is the
        source orbit Artifact's CR3BP mass ratio (extra["mu"]), passed
        through to the response via request.mu (needed to draw Earth-Moon
        annotations; not consumed by the algorithm layer). ``**params``
        are scalar ControlOrbitRequest fields (control_mode etc.)
        collected by the parameter panel; ``input_record_id`` is injected
        by the caller (direct catalog-record link; the Facade resolves the
        ephemeris segment and writes lineage source_record_id).
        """
        from src.engine.exceptions import OrbitError, translate_exception

        params.pop("kernel_dir", None)  # 经 Config 注入，request 不接受
        # injected via Config; not accepted by the request
        if params.get("input_record_id"):
            # 记录直连：Facade 负责取星历段与写谱系，ephemeris_data 不用
            # Record direct link: the Facade fetches the ephemeris segment and writes
            # lineage; ephemeris_data is unused.
            params.setdefault("mu", source_mu)
        else:
            if not ephemeris_data:
                raise OrbitError(
                    "INVALID_PARAMS", "缺少站保输入：既无 input_record_id 也无星历数据"
                )
            params["input_ephemeris"] = _ephemeris_table_from_mapping(ephemeris_data)
            params["mu"] = source_mu
        # engine_layout 面板是 JSON 文本框：control_mode < 4（无角动量管理）时
        # e2m2e 虽不使用但会无条件 validate（访问 .E_r），字符串随手输入直接
        # AttributeError；置 None 忽略。>= 4 时 dict 构造 EngineLayout，其他
        # 值报清晰错误。
        # The engine_layout panel is a JSON text box: with control_mode < 4 (no
        # angular-momentum management) e2m2e does not use it yet still validates
        # unconditionally (accessing .E_r), so arbitrary strings raise a raw
        # AttributeError; set None to ignore. With >= 4, build EngineLayout from a
        # dict and surface a clear error for other values.
        layout = params.pop("engine_layout", None)
        control_mode = params.get("control_mode", 1)
        params["engine_layout"] = _coerce_engine_layout(layout, control_mode)
        try:
            response = self._facade().control_orbit(**params)
        except Exception as e:
            raise translate_exception(e) from e

        controlled = response.controlled_ephemeris
        mu = response.mu
        if controlled is not None and controlled.get("synodic_position") is not None:
            # 会合系原点偏移：减 source_mu 对齐画布质心归一（见
            # centroid_normalized_states；控制律在算法层内部用地心归一）
            # Rotating-frame origin shift: subtract source_mu to align with the
            # canvas barycenter normalization (see centroid_normalized_states;
            # the control law uses Earth-centered normalization inside the
            # algorithm layer).
            states = centroid_normalized_states(controlled["synodic_position"], mu)
            # 真物理时间：替代旧 np.arange(n) 索引，供坐标切换/帧动画定位真时刻
            # True physical time: replaces the old np.arange(n) index, locating real
            # epochs for frame switching and animation.
            times_et = _reconstruct_et_from_utc(_ephemeris_table_from_mapping(controlled))
            times = times_et
            position_km = np.asarray(controlled["position_km"], dtype=float)
        else:
            states = None
            times = None
            times_et = None
            position_km = None

        return ControlResultData(
            num_failed=response.num_failed,
            sk_statistic_rows=np.asarray(response.sk_statistic["rows"]),
            maneuvers_mjd_tdb=np.asarray(response.maneuvers["mjd_tdb"]),
            maneuvers_delta_v_mps=np.asarray(response.maneuvers["delta_v_mps"]),
            controlled_states=states,
            controlled_times=times,
            mu=mu,
            position_km=position_km,
            times_et=times_et,
            record_id=response.record_id,
        )

    def transfer_design(
        self, target_states: Any | None = None, **params: Any
    ) -> TransferDesignResultData:
        """经 Facade 调用 transfer_design，返回跨线程 DTO。

        Args:
            target_states: 选中轨道工件的 CR3BP 状态序列（会合系无量纲，
                (n, 6)）。LGA 转移的目标态取末行并换算到会合系物理单位
                （km / km/s），e2m2e 的 ``target_ephemeris`` 契约是会合系
                物理态（e2m2e#516），直接喂惯性星历会几何全错。HMN 不用。
            **params: TransferDesignRequest 字段（由参数面板收集）。
                ``tli_epoch`` 接受 [年,月,日,时,分,秒]（epoch 控件产出）
                或 ISO 字符串，统一转为 ISO 字符串透传（仅作记录，搜索
                为 CR3BP 几何搜索）。

        English: call transfer_design through the Facade and return a
        cross-thread DTO. ``target_states`` is the selected orbit
        Artifact's CR3BP state sequence (rotating frame, dimensionless,
        (n, 6)); for LGA transfers the target state is the last row
        converted to rotating-frame physical units (km / km/s) because
        e2m2e's ``target_ephemeris`` contract expects rotating-frame
        physical states (e2m2e#516) — feeding inertial ephemeris directly
        breaks the geometry entirely. Unused for HMN. ``**params`` are
        TransferDesignRequest fields (collected by the parameter panel);
        ``tli_epoch`` accepts [year,month,day,hour,minute,second] (from
        the epoch control) or an ISO string, normalized to an ISO string
        and passed through (record-keeping only; the search itself is a
        CR3BP geometric search).
        """
        from datetime import datetime as _dt

        from src.commons.units import DU_KM, TU_SECONDS
        from src.engine.exceptions import translate_exception

        params.pop("kernel_dir", None)  # 经 Config 注入，request 不接受
        # injected via Config; not accepted by the request
        # LGA 默认搜索网格（50 相位点）太稀，漏掉窄可行窗口（同目标态
        # 360 点可收敛），注入 e2m2e 测试同款加密网格作为 GUI 默认
        # The default LGA search grid (50 phase points) is too coarse and misses
        # narrow feasible windows (360 points converge for the same target
        # state); inject the denser grid used in e2m2e's tests as the GUI default.
        if params.get("transfer_type") == "LGA" and not params.get("lga_search_params"):
            from e2m2e.algorithm.transfer import LgaSearchParams

            params["lga_search_params"] = LgaSearchParams(n_departure_phase=360, n_tof=5)
        tli_epoch = params.get("tli_epoch")
        if isinstance(tli_epoch, (list, tuple)) and len(tli_epoch) >= 6:
            epoch_vals = [float(v) for v in tli_epoch[:6]]
            params["tli_epoch"] = _dt(
                int(epoch_vals[0]),
                int(epoch_vals[1]),
                int(epoch_vals[2]),
                int(epoch_vals[3]),
                int(epoch_vals[4]),
                int(epoch_vals[5]),
            ).strftime("%Y-%m-%dT%H:%M:%S")
        if target_states is not None:
            last = np.asarray(target_states, dtype=float)[-1]
            params["target_ephemeris"] = np.concatenate(
                [last[:3] * DU_KM, last[3:] * (DU_KM / TU_SECONDS)]
            ).reshape(1, 6)
        try:
            response = self._facade().transfer_design(**params)
        except Exception as e:
            raise translate_exception(e) from e
        from e2m2e.data.templates import ConvergenceState

        trajectory = (
            np.asarray(response.trajectory, dtype=float)
            if response.trajectory is not None
            else None
        )
        return TransferDesignResultData(
            transfer_type=response.transfer_type,
            delta_v=response.delta_v,
            message=response.message or "",
            converged=response.status is ConvergenceState.CONVERGED,
            trajectory=trajectory,
            details=response.details,
        )

    def orbit_propagation(self, **params: Any) -> PropagationResultData:
        """经 Facade 调用 orbit_propagation，返回纯数据 DTO。

        换算与接缝：前端 duration 标准单位年 → e2m2e 秒；force_config 为
        None 时剔除（走模型默认三体），dict 由调用方解析 JSON。会合系位置
        由 GCRS km 经 ``gcrs_to_synodic`` 转换（产物不入轨道库，落盘走
        persistence）。

        English: call orbit_propagation through the Facade and return a
        pure-data DTO. Conversions and seams: frontend duration
        canonical unit years -> e2m2e seconds; force_config is dropped
        when None (model-default three-body); a dict is JSON-parsed by the
        caller. Rotating-frame positions are converted from GCRS km via
        ``gcrs_to_synodic`` (products do not enter the orbit catalog;
        persistence goes through persistence).
        """
        from e2m2e.data.templates import ConvergenceState
        from e2m2e.data.templates.seed import EARTH_MOON_MU

        from src.commons.units import SECONDS_PER_YEAR
        from src.engine.exceptions import OrbitError, translate_exception

        params.pop("kernel_dir", None)  # 经 Config 注入，request 不接受
        # injected via Config; not accepted by the request
        if params.get("force_config") is None:
            params.pop("force_config", None)
        # GUI duration 单位年 -> e2m2e duration 单位秒
        # GUI duration in years -> e2m2e duration in seconds.
        if params.get("duration") is not None:
            params["duration"] = float(params["duration"]) * SECONDS_PER_YEAR
        epoch = params.get("epoch")
        epoch_iso = epoch if isinstance(epoch, str) else _epoch_list_to_iso(epoch)
        try:
            response = self._facade().orbit_propagation(**params)
        except Exception as e:
            raise translate_exception(e) from e

        if response.status is not ConvergenceState.CONVERGED:
            raise OrbitError("PROPAGATION_FAILED", response.message or "轨道预报未收敛")

        # times_et 重建：ADR 0013 决策 5 的"后续"路径，算法层已填 times_jd_tdb，
        # 直读换算（SPICE ET ≡ J2000 JD TDB 2451545.0 起的 TDB 秒），与 str2et
        # 等价且免去闰秒换算；不修改上游。
        # times_et reconstruction: the "follow-up" path of ADR 0013 decision 5;
        # the algorithm layer already filled times_jd_tdb, so convert by direct
        # read (SPICE ET = TDB seconds since J2000 JD TDB 2451545.0), equivalent
        # to str2et without leap-second conversion; the upstream stays untouched.
        jd = np.asarray(response.times_jd_tdb, dtype=float)
        times_et = (jd - _J2000_JD_TDB) * 86400.0
        position_km = np.asarray(response.position_km, dtype=float)
        velocity_km_s = np.asarray(response.velocity_km_s, dtype=float)
        mu = EARTH_MOON_MU
        synodic = gcrs_to_synodic(position_km, velocity_km_s, times_et, mu, self._kernel_dir)
        return PropagationResultData(
            epoch_utc=epoch_iso or "",
            duration_sec=float(response.duration_sec),
            n_points=int(response.n_points),
            times_et=times_et,
            position_km=position_km,
            velocity_km_s=velocity_km_s,
            synodic_position=synodic,
            final_state=np.asarray(response.final_state, dtype=float),
            mu=mu,
        )

    def generate_family(self, **kwargs: Any) -> FamilyResultData:
        """生成轨道族（各族统一入口），返回跨线程 DTO（产物自动入库）。

        走 ``Facade.orbit_family_generation``：e2m2e 5.7.1 起 Facade 响应
        （``FamilyGenerationResponse``）携带完整 Orbit 成员与状态三元组，软失败
        保留部分族，七族统一入口省去桥接层自行分派。纯 CR3BP 计算，不需要
        SPICE 内核；5.8.0 起族记录自动入轨道库（一族一条，成员参数在记录内）。

        两个 5.7.1 适配点：

        - ``FamilyGenerationRequest`` 按 ``model_fields_set`` 拒绝跨族字段，
          None 值也算已设置，面板对未勾选的 Optional 字段会传 None（语义为
          "用模型默认"），故入参先剔除 None。
        - 周期族成员只携带初态（``states (1,6)``）与周期，画布需要整条
          轨迹，在此按周期重采样到固定点数；Lissajous 拟周期成员已携带
          等长完整轨迹，原样堆叠。

        English: generate an orbit family (unified entry for all
        families) and return a cross-thread DTO (products auto-ingest).
        Goes through ``Facade.orbit_family_generation``: since e2m2e 5.7.1
        the Facade response (``FamilyGenerationResponse``) carries
        complete Orbit members with status triples, soft failures keep a
        partial family, and the unified entry for all seven families
        spares the bridge from dispatching itself. Pure CR3BP compute,
        no SPICE kernels needed; since 5.8.0 family records auto-ingest
        into the orbit catalog (one record per family; member parameters
        live inside the record). Two 5.7.1 adaptation points:
        ``FamilyGenerationRequest`` rejects cross-family fields per
        ``model_fields_set`` — None counts as set, and the panel passes
        None for unchecked Optional fields (meaning "use the model
        default"), so None entries are stripped first. Periodic members
        carry only an initial state (``states (1,6)``) and a period; the
        canvas needs full trajectories, so they are resampled per period
        to a fixed point count here, while quasi-periodic Lissajous
        members already carry equal-length full trajectories and stack
        as-is.
        """
        from e2m2e.data.templates import ConvergenceState

        from src.engine.exceptions import OrbitError, translate_exception

        params = {k: v for k, v in kwargs.items() if v is not None}
        params.setdefault("orbit_type", "HALO")
        try:
            response = self._facade().orbit_family_generation(**params)
        except Exception as e:
            raise translate_exception(e) from e

        orbits = list(response.orbits)
        if not orbits:
            raise OrbitError("FAMILY_FAILED", f"轨道族生成未产出成员: {response.message}")

        family_type = str(response.family_type or params["orbit_type"]).lower()
        periodicity = str(response.metadata.get("periodicity", "periodic"))
        # 周期族成员只携带初态与周期：按周期重采样供画布渲染（传播走 Rust
        # 后端，50 条成员为毫秒级）。成员携带多点轨迹时（Lissajous）原样采用。
        # Periodic members carry only an initial state and a period: resample per
        # period for canvas rendering (propagation goes through the Rust backend,
        # milliseconds for 50 members). Members that already carry multi-point
        # trajectories (Lissajous) are used as-is.
        need_sampling = any(
            np.asarray(o.states).shape[0] == 1 and getattr(o, "period", None) for o in orbits
        )
        dynamics = None
        if need_sampling:
            from e2m2e.algorithm.dynamics import CR3BP_Dynamics

            dynamics = CR3BP_Dynamics(response.system)
        states_list: list[Any] = []
        times_list: list[Any] = []
        for orbit in orbits:
            raw = np.asarray(orbit.states)
            period = getattr(orbit, "period", None)
            if dynamics is not None and raw.shape[0] == 1 and period:
                sampled_states, sampled_times = resample_periodic_member(dynamics, raw[0], period)
                states_list.append(sampled_states)
                times_list.append(sampled_times)
            else:
                states_list.append(raw)
                times_list.append(np.asarray(orbit.times))

        status_message = ""
        if response.status is not ConvergenceState.CONVERGED:
            status_message = str(response.message)
        z0s = None
        if family_type == "halo":
            z0s = np.array([float(np.asarray(o.states)[0, 2]) for o in orbits])
        return FamilyResultData(
            orbit_type=_FAMILY_DISPLAY_NAMES.get(family_type, family_type),
            # DRO 月心族成员参数无 libration_point
            # DRO Moon-centered members carry no libration_point parameter.
            libration_point=(
                int(orbits[0].parameters["libration_point"])
                if "libration_point" in orbits[0].parameters
                else None
            ),
            n_orbits=len(orbits),
            mu=float(response.system.mu),
            states=np.stack(states_list),
            times=np.stack(times_list),
            z0s=z0s,
            family_type=family_type,
            periodicity=periodicity,
            status_message=status_message,
            member_parameters=[dict(getattr(o, "parameters", None) or {}) for o in orbits],
            record_id=response.record_id,
        )

    # ---- 轨道库 catalog（e2m2e 5.8.0，ADR 0031 接缝）------------------------
    # ---- Orbit-library catalog (e2m2e 5.8.0, ADR 0031 seam) ------------------

    def catalog_query(self, **params: Any) -> list[Any]:
        """多维过滤查询，返回 ``CatalogRecordSummary`` 列表（轻量，不含数组段）。

        过滤字段见 ``e2m2e.api.models.CatalogQueryRequest``（族 / 平动点 /
        Jacobi 区间 / 振幅区间 / 段存在性 / status / tags，逻辑与组合）。

        Multi-dimensional filtered query returning a list of
        ``CatalogRecordSummary`` (lightweight, no array segments). Filter
        fields are documented in ``e2m2e.api.models.CatalogQueryRequest``
        (family / libration point / Jacobi range / amplitude range /
        segment existence / status / tags, combined with logical AND).
        """
        response = self._translated(lambda: self._facade().catalog_query(**params))
        return list(response.records)

    def catalog_get(self, record_id: str) -> Any:
        """按 record_id 取完整记录（含数组段）；不存在抛 RECORD_NOT_FOUND。

        Fetch the full record by record_id (including array segments); raises
        RECORD_NOT_FOUND if absent.
        """
        return self._translated(lambda: self._facade().catalog_get(record_id=record_id))

    def catalog_delete(self, record_id: str) -> None:
        """删除记录（文件与索引条目），不可撤销。

        Delete a record (files and index entry); irreversible.
        """
        self._translated(lambda: self._facade().catalog_delete(record_id=record_id))

    def catalog_tag(self, record_id: str, tags: list[str], note: str | None = None) -> None:
        """写教学标注（tags 整体替换，note=None 保留原注释）。

        Write teaching annotations (tags replaced wholesale; note=None keeps the
        existing note).
        """
        self._translated(
            lambda: self._facade().catalog_tag(record_id=record_id, tags=list(tags), note=note)
        )

    def catalog_promote(self, record_id: str, member_index: int) -> str:
        """把族成员提升为独立记录（source_record_id 指向所属族），返回新 record_id。

        Promote a family member to a standalone record (source_record_id points at
        the owning family); returns the new record_id.
        """
        response = self._translated(
            lambda: self._facade().catalog_promote(record_id=record_id, member_index=member_index)
        )
        return response.record.record_id

    def catalog_export(self, dest: str, **filters: Any) -> int:
        """把过滤子集打包导出（dest 以 .zip 结尾出 zip，否则出目录），返回条数。

        Package and export the filtered subset (a .zip dest yields a zip,
        otherwise a directory); returns the exported count.
        """
        response = self._translated(lambda: self._facade().catalog_export(dest=dest, **filters))
        return int(response.exported_count)

    def analyze_stability(self, states: Any, times: Any, mu: float | None) -> StabilityResultData:
        """对 CR3BP 周期轨道做稳定性分析，返回跨线程 DTO。

        从 Artifact 数据构造 e2m2e Orbit + CR3BP_System（mu 取自 Artifact
        extra，缺失时按地月系统默认值兜底，见 viz_adapter.build_cr3bp_system），
        调 ``algorithm/stability.StabilityAnalysis``。纯 CR3BP 计算，不需要
        SPICE 内核。

        English: run stability analysis on a CR3BP periodic orbit and
        return a cross-thread DTO. Builds an e2m2e Orbit + CR3BP_System
        from the Artifact data (mu taken from Artifact extra, falling
        back to the Earth-Moon default when absent — see
        viz_adapter.build_cr3bp_system) and calls
        ``algorithm/stability.StabilityAnalysis``. Pure CR3BP compute, no
        SPICE kernels needed. Args: ``states`` — CR3BP periodic-orbit
        states (n,6) (Artifact.state_data); ``times`` — time series (n,)
        (Artifact.times); ``mu`` — mass ratio (Artifact.extra["mu"]),
        default Earth-Moon system when None. Returns
        StabilityResultData — monodromy matrix / Floquet multipliers /
        stability indices / classification / bifurcation (arrays stay
        ndarray). Raises OrbitError — translated structured error.

        Args:
            states: CR3BP 周期轨道状态 (n,6)（Artifact.state_data）。
                CR3BP periodic-orbit states (n,6) (Artifact.state_data).
            times: 时间序列 (n,)（Artifact.times）。
                Time series (n,) (Artifact.times).
            mu: 质量比（Artifact.extra["mu"]），None 时用默认地月系统。
                Mass ratio (Artifact.extra["mu"]); Earth-Moon default when None.

        Returns:
            StabilityResultData -- 单值矩阵 / Floquet 乘子 / 稳定性指数 /
            分类 / 分岔（数组保持 ndarray）。
            Monodromy matrix / Floquet multipliers / stability indices /
            classification / bifurcation (arrays stay ndarray).

        Raises:
            OrbitError: 经翻译的结构化错误。Translated structured error.
        """
        from e2m2e.algorithm.dynamics import CR3BP_Dynamics
        from e2m2e.algorithm.stability import StabilityAnalysis
        from e2m2e.data.templates.seed import EARTH_MOON_MU
        from e2m2e.data.types import Orbit

        from src.engine.exceptions import translate_exception
        from src.engine.viz_adapter import build_cr3bp_system

        try:
            system = build_cr3bp_system(mu if mu is not None else EARTH_MOON_MU)
            dynamics = CR3BP_Dynamics(system)
            orbit = Orbit(states=states, times=times, system=system)
            result = StabilityAnalysis(orbit=orbit, dynamics=dynamics).analyze()
        except Exception as e:
            raise translate_exception(e) from e

        return StabilityResultData(
            monodromy_matrix=(
                np.asarray(result.monodromy_matrix) if result.monodromy_matrix is not None else None
            ),
            eigenvalues=(
                np.asarray(result.eigenvalues) if result.eigenvalues is not None else None
            ),
            stability_indices=result.stability_indices,
            classification=result.classification,
            bifurcation=result.bifurcation,
            numerical_errors=result.numerical_errors,
        )
