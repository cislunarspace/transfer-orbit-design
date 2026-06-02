"""transfer 管线共享模块。

为 4 条 transfer 管线（dro_to_ro / dro_to_geo / geo_to_dro / leo_to_dro）的
grid_search 和 optimize 脚本提供共享辅助函数、数据类和配置。

本模块当前仅提供共享工具——不修改任何现有消费者。迁移在各管线独立的
切片中完成。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from e2m2e.core import CR3BP_Dynamics, CR3BP_System
from tod.commons.constants import DU, MU, TU
from tod.transfers.optimize_config import (
    apply_blas_env_for_child_processes,
    blas_threads_per_worker,
)

logger = logging.getLogger(__name__)

# =============================================================================
# 默认配置
# =============================================================================

# 积分器默认值（所有管线统一）
DEFAULT_INTEGRATOR: str = "DOP853"
DEFAULT_RTOL: float = 1e-12
DEFAULT_ATOL: float = 1e-12
# 默认最大步长 = 1 小时（无量纲 TU）
DEFAULT_MAX_STEP: float = 1.0 / (24.0 * TU)

# 碰撞检测半径（无量纲 DU）
DEFAULT_EARTH_RADIUS: float = 200.0 / DU
DEFAULT_MOON_RADIUS: float = 100.0 / DU
DEFAULT_MIN_DISTANCE: float = 100.0 / DU

# =============================================================================
# 数据类
# =============================================================================


@dataclass
class TransferSearchConfig:
    """网格搜索的共享配置。

    各管线可以从此基配置派生或直接使用。
    """

    mu: float = MU
    integrator: str = DEFAULT_INTEGRATOR
    rtol: float = DEFAULT_RTOL
    atol: float = DEFAULT_ATOL
    max_step: float = DEFAULT_MAX_STEP
    earth_radius: float = DEFAULT_EARTH_RADIUS
    moon_radius: float = DEFAULT_MOON_RADIUS

    # 搜索参数默认值（各管线可覆盖）
    n_departure: int = 200
    n_alpha: int = 100
    alpha_min: float = 0.5
    alpha_max: float = 2.5
    max_transfer_time: Optional[float] = None  # None = 由管线计算
    intersection_threshold: Optional[float] = None
    min_distance_threshold: Optional[float] = None


@dataclass
class TransferOptimizeConfig:
    """NLP 优化的共享配置。

    各管线可以从此基配置派生或直接使用。
    """

    # 动力学
    mu: float = MU
    integrator: str = DEFAULT_INTEGRATOR
    rtol: float = DEFAULT_RTOL
    atol: float = DEFAULT_ATOL
    max_step: float = DEFAULT_MAX_STEP

    # 碰撞
    earth_radius: float = DEFAULT_EARTH_RADIUS
    moon_radius: float = DEFAULT_MOON_RADIUS

    # NLP
    nlp_maxiter: int = 100
    nlp_ftol: float = 1e-6

    # 搜索范围
    alpha_min: float = 0.5
    alpha_max: float = 2.5

    # 并行
    n_workers: Optional[int] = None
    parallel_backend: str = "processes"

    # 速度容差
    use_relaxed_velocity: bool = True
    velocity_angle_tol: float = 0.05

    # COPT
    use_copt: bool = False
    fallback_to_scipy: bool = True

    # 筛选
    top_k_feasible: Optional[int] = None
    max_cases: Optional[int] = None


# =============================================================================
# CR3BP 动力学构建
# =============================================================================


def build_cr3bp_dynamics(
    mu: float = MU,
    integrator: str = DEFAULT_INTEGRATOR,
    rtol: float = DEFAULT_RTOL,
    atol: float = DEFAULT_ATOL,
    max_step: float = DEFAULT_MAX_STEP,
) -> tuple[CR3BP_System, CR3BP_Dynamics]:
    """构建标准地月 CR3BP 系统与动力学对象。

    Args:
        mu: 质量比，默认从 e2m2e 获取地球-月球值。
        integrator: 积分器类型。
        rtol: 相对容差。
        atol: 绝对容差。
        max_step: 最大积分步长（无量纲 TU）。

    Returns:
        (system, dynamics) 元组。
    """
    system = CR3BP_System(mu=mu, primary="earth", secondary="moon")
    dynamics = CR3BP_Dynamics(system=system)
    dynamics.integrator = integrator
    dynamics.rtol = rtol
    dynamics.atol = atol
    dynamics.max_step = max_step
    return system, dynamics


def apply_default_blas_env() -> None:
    """为子进程设置 BLAS 环境变量（限制每 worker 线程数）。"""
    apply_blas_env_for_child_processes(blas_threads_per_worker())


# =============================================================================
# JSON 序列化
# =============================================================================


def json_safe(x: Any) -> Any:
    """递归将 numpy 标量/数组及嵌套结构转换为 JSON 可序列化的 Python 原生类型。

    所有 grid_search 脚本中此函数的实现完全相同。集中在此处避免
    4 份副本漂移。

    Args:
        x: 任意 Python 或 NumPy 值。

    Returns:
        JSON 可序列化的等价对象。
    """
    if x is None:
        return None
    if isinstance(x, np.generic):
        return x.item()
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, dict):
        return {k: json_safe(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [json_safe(i) for i in x]
    return x


def serialize_nlp_result(res: Any) -> Dict[str, Any]:
    """将 NLPOptimizationResult 序列化为 JSON 安全的字典。

    所有 optimize 脚本中此函数完全相同。集中在此处避免 4 份副本漂移。

    Args:
        res: e2m2e.transfer.NLPOptimizationResult 实例。

    Returns:
        JSON 可序列化的字典。
    """
    return {
        "success": res.success,
        "alpha": float(res.alpha),
        "transfer_time": float(res.transfer_time),
        "t_ins": float(res.t_ins) if hasattr(res, "t_ins") else None,
        "objective_value": float(res.objective_value),
        "delta_v1": float(res.delta_v1),
        "delta_v2": float(res.delta_v2),
        "message": res.message,
        "constraints_violation": {
            k: float(v) for k, v in (res.constraints_violation or {}).items()
        },
        "transfer_type": res.transfer_type.value if res.transfer_type else None,
    }


# =============================================================================
# 文件 I/O
# =============================================================================


def load_search_results(filepath: Path) -> List[Dict[str, Any]]:
    """读取网格搜索结果 JSON 文件。

    Args:
        filepath: 搜索结果文件路径。

    Returns:
        解析后的 JSON 数据列表。
    """
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)


def find_project_root() -> Path:
    """获取项目根目录。

    从 ``tod/transfers/_pipeline.py`` 向上走 3 级到项目根
    （等价于各管线的 ``Path(__file__).resolve().parent.parent.parent.parent``
    因为它们多一层子目录）。
    """
    return Path(__file__).resolve().parent.parent.parent


# =============================================================================
# 调试入口
# =============================================================================


def inject_debug_args(
    argv: List[str],
    defaults: List[str],
    description: str = "使用代码内置调试参数",
) -> None:
    """IDE 调试模式：F5 直跑时注入默认命令行参数。

    所有 transfer 脚本的 ``if __name__ == "__main__"`` 块中此模式完全相同。
    集中在此处避免 9 份副本漂移。

    用法::

        if __name__ == "__main__":
            inject_debug_args(sys.argv, [
                "--n-departure", "200",
                "--alpha-min", "0.5",
            ])
            main()

    Args:
        argv: ``sys.argv`` 列表（会被原地修改）。
        defaults: 偶数长度的键值对列表，追加到 argv。
        description: 注入时记录的调试信息。
    """
    if len(argv) == 1:
        argv += defaults
        logger.debug(description)
