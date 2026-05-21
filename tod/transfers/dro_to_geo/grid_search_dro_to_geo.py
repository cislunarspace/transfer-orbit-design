"""
DRO → GEO 转移轨道网格搜索

从 DRO 出发，搜索到达 GEO（地球静止轨道）的转移轨道。
复用 TransferSearch，departure=DRO，arrival=GEO（近似圆轨道）。

运行: python -m tod.transfers.dro_to_geo.grid_search_dro_to_geo

Windows 多进程需要 ``if __name__ == "__main__"``。
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

from e2m2e.core import CR3BP_System, CR3BP_Dynamics
from e2m2e.core.orbit import Orbit
from e2m2e.transfer import TransferSearch, load_orbit_from_json
from e2m2e.orbits.geo import (
    R_GEO,
    T_GEO,
    EARTH_CENTER,
    geo_circular_velocity_rotating,
)
from tod.commons.constants import DU, MU, TU, VU
from tod.generates.artifacts import (
    OrbitArtifactNotFoundError,
    find_latest_single_dro,
)
from tod.transfers.optimize_config import apply_blas_env_for_child_processes, blas_threads_per_worker
import logging

logger = logging.getLogger(__name__)

project_root = Path(__file__).resolve().parent.parent.parent.parent


# =====================================================================
# 配置默认值
# =====================================================================

# 搜索参数
N_DEPARTURE = 200
N_ALPHA = 100
ALPHA_MIN = 0.5
ALPHA_MAX = 2.5
MAX_TRANSFER_TIME = 100.0 / TU  # 最大转移时间（无量纲）

# 检测阈值
INTERSECTION_THRESHOLD = 100.0 / DU
MIN_DISTANCE_THRESHOLD = 100.0 / DU
EARTH_RADIUS = 200.0 / DU
MOON_RADIUS = 100.0 / DU

# 积分参数
INTEGRATION_DT = 1.0 / (24.0 * TU)

# GEO 轨道采样点数
GEO_N_POINTS = 1000


def _json_safe(x):
    """递归将 numpy 标量/数组、嵌套 dict/list 转换为可 JSON 序列化的 Python 原生类型。"""
    if x is None:
        return None
    if isinstance(x, np.generic):
        return x.item()
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, dict):
        return {k: _json_safe(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_json_safe(i) for i in x]
    return x


def serialize_result(r: dict, *, is_feasible: bool) -> dict:
    """将单条 TransferSearch 结果字典序列化为 JSON 安全的字段子集。

    下游兼容：``plot_search_results_dro_to_geo.py`` / ``optimize_dro_to_geo.py`` /
    ``plot/transfer/common.py`` 仍读取旧字段 ``dv_insertion``，故双写
    ``dv_arrival`` 与 ``dv_insertion``（同值）。待下游统一迁移到 ``dv_arrival``
    后可移除 ``dv_insertion``。

    issue #71 引入 4 个 ``first_*`` 字段供下游绘图按"首次可行点"截断；
    e2m2e 旧版本无这些字段时为 ``None``，绘图端 ``_resolve_truncation`` 自动 fallback。

    Args:
        r: ``TransferSearch.search()`` 返回的单条 result dict。
        is_feasible: 由调用方根据 ``searcher.get_feasible_results()`` 派生（避免
            依赖私有 ``_is_feasible``）。

    Returns:
        JSON 安全的字段子集（仅 Python 原生类型）。
    """
    dv_arrival_val = r.get("dv_arrival")
    serialized: dict = _json_safe(  # type: ignore[assignment]
        {
            "departure_time_index": r.get("departure_time_index"),
            "departure_time": r.get("departure_time"),
            "alpha": r.get("alpha"),
            "transfer_time": r.get("transfer_time"),
            "dv_departure": r.get("dv_departure"),
            "dv_arrival": dv_arrival_val,
            "dv_insertion": dv_arrival_val,  # 向后兼容旧字段名
            "min_distance": r.get("min_distance"),
            "intersection_found": r.get("intersection_found"),
            # 首次可行性字段（issue #71）。e2m2e 旧版本无此字段时为 None。
            "first_intersection_idx": r.get("first_intersection_idx"),
            "first_intersection_time": r.get("first_intersection_time"),
            "first_min_distance_idx": r.get("first_min_distance_idx"),
            "first_min_distance_time": r.get("first_min_distance_time"),
            "collision_found": r.get("collision_found"),
            "collision_body": r.get("collision_body"),
            "local_minimum_found": r.get("local_minimum_found"),
            "local_minimum_distance": r.get("local_minimum_distance"),
            "status": r.get("status"),
            "is_feasible": bool(is_feasible),
        }
    )
    departure_state = r.get("departure_state")
    if departure_state is not None:
        serialized["departure_state"] = _json_safe(departure_state)
    return serialized


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DRO→GEO 转移轨道网格搜索")
    parser.add_argument(
        "--dro-file", type=str, default=None, help="DRO 轨道 JSON 文件路径"
    )
    parser.add_argument(
        "--n-departure", type=int, default=N_DEPARTURE, help="出发时间网格数"
    )
    parser.add_argument(
        "--n-alpha", type=int, default=N_ALPHA, help="alpha 网格密度"
    )
    parser.add_argument(
        "--alpha-min", type=float, default=ALPHA_MIN, help="alpha 搜索下界"
    )
    parser.add_argument(
        "--alpha-max", type=float, default=ALPHA_MAX, help="alpha 搜索上界"
    )
    parser.add_argument(
        "--max-transfer-time",
        type=float,
        default=MAX_TRANSFER_TIME,
        help="最大转移时间（无量纲）",
    )
    parser.add_argument(
        "--intersection-threshold",
        type=float,
        default=INTERSECTION_THRESHOLD,
        help="GEO 相交判定距离阈值",
    )
    parser.add_argument(
        "--min-distance",
        type=float,
        default=MIN_DISTANCE_THRESHOLD,
        help="候选解最小距离阈值",
    )
    parser.add_argument(
        "--earth-radius",
        type=float,
        default=EARTH_RADIUS,
        help="地球碰撞检测半径",
    )
    parser.add_argument(
        "--moon-radius",
        type=float,
        default=MOON_RADIUS,
        help="月球碰撞检测半径",
    )
    parser.add_argument(
        "--geo-n-points",
        type=int,
        default=GEO_N_POINTS,
        help="GEO 轨道采样点数",
    )
    return parser.parse_args()


# =====================================================================
# GEO 轨道生成（与 geo_to_dro 保持一致）
# =====================================================================


def generate_geo_orbit(n_points: int = GEO_N_POINTS) -> Orbit:
    """在 CR3BP 旋转系中生成 GEO 近似圆轨道。

    GEO 被建模为以地心为圆心、半径为 R_GEO 的圆轨道。
    速度通过 geo_circular_velocity_rotating 计算（包含 Coriolis 修正）。
    """
    theta = np.linspace(0, 2 * np.pi, n_points, endpoint=False)
    states = np.zeros((n_points, 6))

    for i, th in enumerate(theta):
        x = EARTH_CENTER[0] + R_GEO * np.cos(th)
        y = R_GEO * np.sin(th)
        z = 0.0

        pos = np.array([x, y, z])
        vel = geo_circular_velocity_rotating(pos)

        states[i] = [x, y, z, vel[0], vel[1], vel[2]]

    times = np.linspace(0, T_GEO, n_points, endpoint=False)

    orbit = Orbit(states, times)
    orbit.period = T_GEO
    return orbit


def main() -> None:
    args = parse_args()

    # =========================================================================
    # 初始化
    # =========================================================================
    apply_blas_env_for_child_processes(blas_threads_per_worker())

    dro_file_path = args.dro_file or os.environ.get("DRO_FILE")
    if dro_file_path:
        dro_file = Path(dro_file_path)
        if not dro_file.exists():
            logger.error("DRO 轨道文件不存在: %s", dro_file)
            return
    else:
        try:
            dro_file = find_latest_single_dro(project_root)
        except OrbitArtifactNotFoundError as e:
            logger.error("%s", e)
            return
        logger.info("自动选取最新 DRO 文件: %s", dro_file)

    n_departure = args.n_departure
    n_alpha = args.n_alpha
    alpha_min = args.alpha_min
    alpha_max = args.alpha_max
    max_transfer_time = args.max_transfer_time
    intersection_threshold = args.intersection_threshold
    min_distance_threshold = args.min_distance
    earth_radius = args.earth_radius
    moon_radius = args.moon_radius
    geo_n_points = args.geo_n_points

    system = CR3BP_System(mu=MU, primary="earth", secondary="moon")
    dynamics = CR3BP_Dynamics(system=system)
    dynamics.integrator = "DOP853"
    dynamics.rtol = 1e-12
    dynamics.atol = 1e-12
    dynamics.max_step = INTEGRATION_DT

    # 加载 DRO 轨道
    dro_orbit = load_orbit_from_json(str(dro_file))
    with open(dro_file) as f:
        dro_data = json.load(f)
    dro_orbit.period = dro_data.get("properties", {}).get("period", None)

    # 生成 GEO 轨道（作为到达轨道）
    geo_orbit = generate_geo_orbit(n_points=geo_n_points)

    # =========================================================================
    # 执行搜索
    # =========================================================================
    logger.info("\n" + "=" * 70)
    logger.info("DRO → GEO 网格搜索")
    logger.info("=" * 70)
    logger.info(
        "  DRO 轨道: %d 点, 周期=%s TU",
        dro_orbit.states.shape[0],
        dro_orbit.period,
    )
    logger.info(
        "  GEO 轨道: %d 点, R=%.6f DU = %.0f km",
        geo_n_points,
        R_GEO,
        R_GEO * DU,
    )
    logger.info("  α 范围: [%s, %s], n=%d", alpha_min, alpha_max, n_alpha)
    logger.info("  出发点数量: %d", n_departure)
    logger.info(
        "  最大转移时间: %.4f TU = %.1f 天",
        max_transfer_time,
        max_transfer_time * TU,
    )
    logger.info("=" * 70)

    searcher = TransferSearch(dynamics)
    results = searcher.search(
        departure_orbit=dro_orbit,
        arrival_orbit=geo_orbit,
        alpha_min=alpha_min,
        alpha_max=alpha_max,
        n_alpha=n_alpha,
        n_departure=n_departure,
        max_transfer_time=max_transfer_time,
        intersection_threshold=intersection_threshold,
        min_distance_threshold=min_distance_threshold,
        collision_earth_radius=earth_radius,
        collision_moon_radius=moon_radius,
        integration_dt=INTEGRATION_DT,
        verbose=True,
        n_workers=None,
    )

    feasible = searcher.get_feasible_results()
    logger.info(
        "\n搜索完成: %d 个候选解, %d 个可行解", len(results), len(feasible)
    )

    # 用 id-set 派生 is_feasible，避免依赖 searcher._is_feasible 私有 API
    feasible_ids = {id(r) for r in feasible}

    # =========================================================================
    # 保存结果
    # =========================================================================
    output_dir = project_root / "output/transfer"
    output_file = output_dir / (
        f"search_dro_geo_{n_departure}-{n_alpha}-{alpha_min:g}-{alpha_max:g}-"
        f"{max_transfer_time:.4f}_{int(time.time())}.json"
    )

    results_data = [serialize_result(r, is_feasible=id(r) in feasible_ids) for r in results]

    output_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "direction": "DRO_to_GEO",
        "dro_file": str(dro_file),
        "geo_radius": float(R_GEO),
        "geo_period": float(T_GEO),
        "search_params": {
            "n_departure": n_departure,
            "n_alpha": n_alpha,
            "alpha_min": alpha_min,
            "alpha_max": alpha_max,
            "max_transfer_time": max_transfer_time,
            "intersection_threshold": intersection_threshold,
            "min_distance_threshold": min_distance_threshold,
            "collision_earth_radius": earth_radius,
            "collision_moon_radius": moon_radius,
        },
        "n_total": len(results_data),
        "n_feasible": len(feasible),
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(
            {"meta": meta, "results": results_data},
            f,
            indent=2,
            ensure_ascii=False,
        )

    logger.info("\n结果已保存到: %s", output_file)
    logger.info("  总候选解: %d", len(results_data))
    logger.info("  可行解: %d", len(feasible))

    if feasible:
        logger.info("\n可行解摘要（前 10 个）:")
        sorted_feasible = sorted(
            feasible, key=lambda r: r.get("min_distance", float("inf"))
        )
        for i, r in enumerate(sorted_feasible[:10]):
            md = r.get("min_distance", float("inf"))
            dv = r.get("dv_departure", 0)
            tt = r.get("transfer_time", 0)
            al = r.get("alpha", 0)
            logger.info(
                "  #%d: dep_idx=%s, α=%.4f, T=%.2f TU (%.1f 天), "
                "dv_dep=%.4f VU (%.0f m/s), min_dist=%.6f DU (%.0f km), 相交=%s",
                i + 1,
                r.get("departure_time_index"),
                al,
                tt,
                tt * TU,
                dv,
                dv * VU,
                md,
                md * DU,
                r.get("intersection_found", False),
            )


if __name__ == "__main__":
    # IDE 调试模式：F5 直跑（无命令行参数）时注入下列参数；
    # 命令行调用时不影响。
    if len(sys.argv) == 1:
        sys.argv += [
            "--n-departure", "200",                              # 出发时间网格数
            "--n-alpha", "100",                                  # alpha 网格密度
            "--alpha-min", "0.5",                                # alpha 搜索下界
            "--alpha-max", "2.5",                                # alpha 搜索上界
            "--max-transfer-time", "22.998482090701266",         # 最大转移时间（无量纲，100.0/TU）
            "--intersection-threshold", "0.0002601422978369168", # GEO 相交距离阈值（100.0/DU）
            "--min-distance", "0.0002601422978369168",           # 候选解最小距离（100.0/DU）
            "--earth-radius", "0.0005202845956738336",           # 地球碰撞检测半径（200.0/DU）
            "--moon-radius", "0.0002601422978369168",            # 月球碰撞检测半径（100.0/DU）
            "--geo-n-points", "1000",                            # GEO 轨道采样点数
        ]
        logger.debug("使用代码内置调试参数")
    main()
