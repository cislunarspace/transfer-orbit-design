"""correct_transfer_to_ephemeris 脚本。

将 DRO→GEO 优化后的转移轨迹从 CR3BP synodic 坐标系转换到星历模型（J2000），
沿转移弧段采样 patch points，执行多重打靶星历修正，并可选对比 Rust 与
SciPy 两条 STM 路径的 wall time。

与 ``transfer_to_ephemeris.py`` 的区别：后者只做坐标转换 + 前向传播展示，
不做残差修正；本脚本真正调用 ``correct_ephemeris_patch_points`` 收敛 patch
points，得到满足星历模型连续性的修正轨迹。

运行示例:
    .. code-block:: bash

       uv run python -m tod.transfers.dro_to_geo.correct_transfer_to_ephemeris \
           --opt-file output/transfer/optimization_dro_geo_1781070822.json \
           --reference-epoch 2025-06-21T11:00:06
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from tod.transfers._common import forward_integrate
from tod.transfers.dro_to_geo.transfer_to_ephemeris import (
    load_optimization_results,
    select_best_result,
    synodic_to_j2000_states,
)

project_root = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_SPICE_KERNEL_DIR = Path(project_root.parent / "e2m2e" / "kernels")


def parse_args():
    parser = argparse.ArgumentParser(
        description="DRO→GEO 转移轨迹星历修正（多重打靶）",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--opt-file", type=str, required=True,
        help="优化结果 JSON 文件路径（optimization_dro_geo_*.json）",
    )
    parser.add_argument(
        "--select-by", choices=["transfer_time", "objective"], default="objective",
        help="选择标准：transfer_time=选最短转移时间，objective=选最优目标函数",
    )
    parser.add_argument(
        "--search-index", type=int, default=None,
        help="指定选用的 search_index（覆盖 --select-by）",
    )
    parser.add_argument(
        "--reference-epoch", type=str, default="2025-06-21T11:00:06",
        help="UTC 参考历元，用于 synodic→J2000 转换",
    )
    parser.add_argument(
        "--spice-kernel-dir", type=str, default=str(DEFAULT_SPICE_KERNEL_DIR),
        help="SPICE kernel 目录",
    )
    parser.add_argument(
        "--bodies", type=str, default="EARTH,MOON,SUN",
        help="参与的天体列表，逗号分隔",
    )
    parser.add_argument(
        "--n-patch-points", type=int, default=8,
        help="patch points 数量（沿转移弧段均匀采样）",
    )
    parser.add_argument(
        "--method", choices=("standard", "two_level", "homotopy", "segmented"), default="two_level",
        help="星历修正方法（segmented=分段打靶拼接法）",
    )
    parser.add_argument(
        "--sampling", choices=("uniform", "adaptive"), default="adaptive",
        help="patch points 采样方式：uniform=时间等距；adaptive=按轨迹曲率自适应"
        "（高动态区加密，对齐 cyj-code 的 patch_ratios，显著改善两层法收敛）",
    )
    parser.add_argument(
        "--adaptive-alpha", type=float, default=1.0,
        help="adaptive 采样的曲率权重指数，越大高动态区加密越强",
    )
    parser.add_argument("--position-tol", type=float, default=1e-3, help="位置残差容差（km）")
    parser.add_argument("--velocity-tol", type=float, default=1e-6, help="速度残差容差（km/s）")
    parser.add_argument("--max-iter", type=int, default=50, help="最大迭代次数")
    parser.add_argument("--n-workers", type=int, default=1, help="并行 worker 数")
    parser.add_argument(
        "--output-file", type=str, default=None,
        help="输出 JSON 路径，默认自动生成",
    )
    parser.add_argument(
        "--compare-python", action="store_true",
        help="额外跑一遍 SciPy 路径做 wall time 对比（默认只跑 Rust）",
    )
    parser.add_argument(
        "--var-time", action="store_true",
        help="时间节点也作为自由变量（直接调 MultipleShooting，适合长弧段转移）",
    )
    parser.add_argument(
        "--inner-method", choices=("standard", "two_level"), default="standard",
        help="homotopy 的内层修正方法（仅 --method homotopy 生效）",
    )
    parser.add_argument(
        "--points-per-segment", type=int, default=10,
        help="分段打靶每段的 patch points 数量（仅 --method segmented 生效）",
    )
    parser.add_argument(
        "--overlap-points", type=int, default=2,
        help="分段打靶相邻段重叠点数（仅 --method segmented 生效）",
    )
    parser.add_argument(
        "--enable-merging", action="store_true", default=True,
        help="分段打靶是否启用逐步合并（仅 --method segmented 生效）",
    )
    return parser.parse_args()


def sample_patch_points_from_arc(
    dynamics,
    state0: np.ndarray,
    transfer_time: float,
    n_points: int,
) -> tuple[np.ndarray, np.ndarray]:
    """沿转移弧段均匀采样 n_points 个 patch points（synodic 系，无量纲）。

    先用细分辨率前向积分得到完整轨迹，再等距抽取 n_points 个点，
    保证采样点精确落在积分轨迹上（无插值误差）。
    """
    states_fine, times_fine = forward_integrate(dynamics, state0, transfer_time)
    n_total = len(states_fine)
    if n_total < n_points:
        raise ValueError(
            f"积分点数 {n_total} 少于请求的 patch points {n_points}，请减小 --n-patch-points"
        )
    indices = np.linspace(0, n_total - 1, n_points, dtype=int)
    return times_fine[indices], states_fine[indices]


def sample_patch_points_adaptive(
    dynamics,
    state0: np.ndarray,
    transfer_time: float,
    n_points: int,
    alpha: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """按轨迹动态强度自适应采样 patch points（synodic 系，无量纲）。

    转移弧在近地/近月区速度、曲率剧变，时间等距采样会在这些高动态区
    留下过长弧段，导致两层法 Level 2 修正发散。这里按弧长与曲率的加权
    密度做再参数化，在高动态区自动加密节点，对齐 cyj-code 的 patch_ratios
    思路。采样点取自积分轨迹，无插值误差。
    """
    states_fine, times_fine = forward_integrate(dynamics, state0, transfer_time)
    n_total = len(states_fine)
    if n_total < n_points:
        raise ValueError(
            f"积分点数 {n_total} 少于请求的 patch points {n_points}，请减小 --n-patch-points"
        )

    pos = states_fine[:, :3]
    vel = states_fine[:, 3:6]
    seg_len = np.linalg.norm(np.diff(pos, axis=0), axis=1)          # 每小段弧长
    speed = np.linalg.norm(vel, axis=1)
    accel = np.linalg.norm(np.gradient(vel, times_fine, axis=0), axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        curvature = np.where(speed > 0, accel / np.maximum(speed, 1e-12), 0.0)
    # 密度 = 单位弧长权重 × (1 + α·归一化曲率)，高动态区权重更高
    curvature_n = curvature / (curvature.max() + 1e-30)
    density = 1.0 + alpha * curvature_n[:-1]
    weights = seg_len * density
    s = np.concatenate([[0.0], np.cumsum(weights)])
    s /= s[-1]
    targets = np.linspace(0.0, 1.0, n_points)
    indices = np.searchsorted(s, targets)
    indices = np.clip(indices, 0, n_total - 1)
    indices[0], indices[-1] = 0, n_total - 1
    return times_fine[indices], states_fine[indices]


def build_ephemeris_dynamics(args, spice):
    """构建星历动力学模型并加载 SPICE 内核。"""
    import spiceypy
    from e2m2e.core.ephemeris_dynamics import EphemerisDynamics
    from e2m2e.core.ephemeris_system import EphemerisSystem
    from e2m2e.mbse.data.enums import ReferenceFrame

    spice_kernel_dir = Path(args.spice_kernel_dir)
    kernel_path = spice.find_ephemeris_kernel(str(spice_kernel_dir))
    leapseconds_path = spice_kernel_dir / "naif0012.tls"
    spiceypy.furnsh(str(leapseconds_path))
    spice.load_kernel(kernel_path)

    bodies = tuple(b.upper() for b in args.bodies.split(",") if b.strip())
    eph_system = EphemerisSystem(
        bodies=list(bodies),
        spice=spice,
        origin="EARTH",
        frame=ReferenceFrame.J2000,
    )
    return EphemerisDynamics(system=eph_system), bodies


def build_forces_from_dynamics(dynamics):
    """从 EphemerisDynamics 提取 forces 元组列表，用于 Rust 打靶函数。

    返回格式：[("third_body", body_name, mu_value), ...]
    对应 Rust CompiledForce::ThirdBody 变体。
    """
    system = dynamics.system
    bodies = list(system.bodies)
    origin = system.origin
    gm_values = system.get_gm_values()

    forces = []
    for body, gm in zip(bodies, gm_values):
        if body != origin:
            forces.append(("third_body", body, float(gm)))
    return forces


def run_correction(args, t_patch_j2000, states_j2000, dynamics, spice):
    """执行一次星历修正，返回 (result, wall_time_s)。

    ``--var-time`` 时直接调 ``MultipleShooting.correct(var_time=True)``，
    让时间节点也参与修正——给长弧段转移（模型误差累积大）更多自由度。
    ``--method segmented`` 时调用分段打靶拼接法。
    否则走 ``correct_ephemeris_patch_points`` 分发器（standard/two_level/homotopy）。
    """
    t0 = time.perf_counter()

    if args.method == "segmented":
        # 分段打靶拼接法：直接调用 Rust 实现
        from e2m2e._integrators import segmented_shooting_correct_py

        print(f"\n分段打靶拼接法：{args.points_per_segment} 点/段，重叠 {args.overlap_points} 点")

        # 构造 forces 参数
        forces = build_forces_from_dynamics(dynamics)
        origin = dynamics.system.origin

        result = segmented_shooting_correct_py(
            forces=forces,
            observer=origin,
            t_patch=t_patch_j2000.tolist(),
            state_patch=states_j2000.tolist(),
            points_per_segment=args.points_per_segment,
            overlap_points=args.overlap_points,
            enable_merging=args.enable_merging,
            max_iter_per_segment=args.max_iter,
            tolerance=args.position_tol,
            rtol=1e-10,
            verbose=True,
        )

        # 包装结果，兼容后续处理代码
        class _SegmentedResultWrapper:
            def __init__(self, rust_result):
                self.converged = rust_result.converged
                self.max_residual = rust_result.max_residual
                self.iterations = rust_result.total_iterations
                self.residual_history = rust_result.stage_residuals
                self.t_patch = np.array(rust_result.t_patch)
                self.state_patch = np.array(rust_result.state_patch)
                self.stage_residuals = rust_result.stage_residuals
                self.n_segments = rust_result.n_segments

        elapsed = time.perf_counter() - t0
        return _SegmentedResultWrapper(result), elapsed

    if args.var_time:
        from e2m2e.algorithms import MultipleShooting

        ms = MultipleShooting(
            dynamics,
            n_workers=args.n_workers,
            kernel_dir=str(args.spice_kernel_dir),
        )
        result = ms.correct(
            t_patch=t_patch_j2000,
            state_patch=states_j2000,
            var_time=True,
            max_iter=args.max_iter,
            tolerance=args.position_tol,
            verbose=True,
        )
        elapsed = time.perf_counter() - t0
        return result, elapsed

    from e2m2e.algorithms.ephemeris_correction import correct_ephemeris_patch_points

    # 显式 keyword args：CI pyright 拒绝 ``dict[str, object] -> TypedDict`` 的 ``**kwargs`` 解包。
    is_homotopy = args.method == "homotopy"
    result = correct_ephemeris_patch_points(
        args.method, dynamics, t_patch_j2000, states_j2000,
        tolerance=args.position_tol, max_iter=args.max_iter, verbose=True,
        n_workers=args.n_workers, kernel_dir=str(args.spice_kernel_dir),
        velocity_tolerance=args.velocity_tol,
        base_bodies=["EARTH", "MOON"] if is_homotopy else None,
        inner_method=args.inner_method if is_homotopy else "standard",
    )
    elapsed = time.perf_counter() - t0
    return result, elapsed


def set_rust_stm(enabled: bool) -> bool:
    """切换 EphemerisDynamics 的 Rust STM 路径，返回切换前的状态。"""
    import e2m2e.core.ephemeris_dynamics as ed

    previous = ed._HAS_RUST_STM
    ed._HAS_RUST_STM = enabled
    return previous


def main():
    args = parse_args()

    opt_path = Path(args.opt_file)
    if not opt_path.is_file():
        raise FileNotFoundError(f"未找到优化结果文件: {opt_path}")

    print(f"读取优化结果: {opt_path}")
    data = load_optimization_results(opt_path)

    if args.search_index is not None:
        results = data.get("results", [])
        matches = [r for r in results if r.get("search_index") == args.search_index
                   and r.get("nlp", {}).get("success")]
        if not matches:
            raise ValueError(f"search_index={args.search_index} 无成功优化结果")
        best = matches[0]
    else:
        best = select_best_result(data, args.select_by)
    nlp = best["nlp"]

    from tod.commons.constants import TU, VU

    dv_total = nlp["objective_value"] * VU  # VU ≈ 1023 m/s
    print(f"\n=== 选中结果 ({args.select_by}) ===")
    print(f"  search_index: {best['search_index']}")
    print(f"  alpha: {nlp['alpha']:.4f}")
    print(f"  transfer_time: {nlp['transfer_time']:.4f} TU = {nlp['transfer_time'] * TU:.1f} 天")
    print(f"  objective_value: {nlp['objective_value']:.4f} VU = {dv_total:.0f} m/s")

    # 1. CR3BP 前向积分 + patch points 采样
    print(f"\n1. CR3BP 积分 + 采样 {args.n_patch_points} 个 patch points（{args.sampling}）...")
    from e2m2e.core import CR3BP_System, CR3BP_Dynamics
    from tod.commons.orbits import compute_departure_velocity
    import tod.commons.constants as _tod_constants

    system = CR3BP_System(mu=_tod_constants.MU, primary="earth", secondary="moon")
    cr3bp_dynamics = CR3BP_Dynamics(system=system)
    cr3bp_dynamics.integrator = "DOP853"
    cr3bp_dynamics.rtol = 1e-12
    cr3bp_dynamics.atol = 1e-12
    cr3bp_dynamics.max_step = 1.0 / (24.0 * _tod_constants.TU)

    departure_state_raw = np.array(best["departure_state"], dtype=float)
    alpha = nlp["alpha"]
    v_perturbed = compute_departure_velocity(departure_state_raw, alpha)
    state0 = np.concatenate([departure_state_raw[:3], v_perturbed])
    transfer_time = nlp["transfer_time"]

    if args.sampling == "adaptive":
        t_patch_syn, states_patch_syn = sample_patch_points_adaptive(
            cr3bp_dynamics, state0, transfer_time, args.n_patch_points, args.adaptive_alpha,
        )
    else:
        t_patch_syn, states_patch_syn = sample_patch_points_from_arc(
            cr3bp_dynamics, state0, transfer_time, args.n_patch_points,
        )
    print(f"  采样完成：{len(t_patch_syn)} 个点，跨度 [{t_patch_syn[0]:.4f}, {t_patch_syn[-1]:.4f}] TU")

    # 2. 加载 SPICE + 参考历元（须先 furnsh 闰秒内核才能 utc_to_et）
    print(f"\n2. 加载 SPICE kernels...")
    from e2m2e.core.spice import SPICEManager

    spice = SPICEManager()
    dynamics, bodies = build_ephemeris_dynamics(args, spice)
    reference_et = float(spice.utc_to_et(args.reference_epoch))
    print(f"  参考历元 ET: {reference_et:.1f} s")

    # 3. Synodic → J2000 转换
    print(f"\n3. Synodic → J2000 坐标转换...")
    states_patch_j2000 = synodic_to_j2000_states(
        states_patch_syn, t_patch_syn, reference_et, system, spice,
    )
    t_patch_et = reference_et + t_patch_syn * _tod_constants.TU * 86400
    print(f"  出发点 J2000 (km): [{states_patch_j2000[0, 0]:.1f}, {states_patch_j2000[0, 1]:.1f}, {states_patch_j2000[0, 2]:.1f}]")
    print(f"  终点 J2000 (km): [{states_patch_j2000[-1, 0]:.1f}, {states_patch_j2000[-1, 1]:.1f}, {states_patch_j2000[-1, 2]:.1f}]")

    # 4. 星历修正

    import e2m2e.core.ephemeris_dynamics as _ed
    rust_available = _ed._HAS_RUST_STM

    method_label = f"var_time={args.var_time}" if args.var_time else f"method={args.method}"
    print(f"\n4. 星历修正（{method_label}, Rust STM={'on' if rust_available else 'off'}）...")
    result, elapsed = run_correction(args, t_patch_et, states_patch_j2000, dynamics, spice)

    # 两种结果类型字段兼容：MultipleShootingResult 用 outer_iterations，
    # EphemerisCorrectionResult 用 iterations；velocity_residual 仅后者有。
    n_iter = getattr(result, "outer_iterations", None) or getattr(result, "iterations", 0)
    vel_res = getattr(result, "velocity_residual", None)

    print(f"\n=== 修正结果（Rust 路径）===")
    print(f"  converged: {result.converged}")
    print(f"  iterations: {n_iter}")
    print(f"  max_residual: {result.max_residual:.3e} km")
    print(f"  velocity_residual: {vel_res}")
    print(f"  wall time: {elapsed:.2f} s")
    print(f"  residual history: {[f'{r:.2e}' for r in result.residual_history]}")

    payload = {
        "metadata": {
            "source_file": str(opt_path),
            "select_by": args.select_by,
            "selected_search_index": best["search_index"],
            "reference_epoch": args.reference_epoch,
            "reference_et_s": reference_et,
            "bodies": list(bodies),
            "method": args.method,
            "n_patch_points": args.n_patch_points,
            "sampling": args.sampling,
            "adaptive_alpha": args.adaptive_alpha,
            "position_tol_km": args.position_tol,
            "velocity_tol_km_s": args.velocity_tol,
            "max_iter": args.max_iter,
            "rust_available": bool(rust_available),
        },
        "cr3bp": {
            "alpha": nlp["alpha"],
            "transfer_time_TU": nlp["transfer_time"],
            "transfer_time_days": nlp["transfer_time"] * _tod_constants.TU,
            "objective_value_m_s": dv_total,
            "t_patch_synodic": t_patch_syn.tolist(),
            "states_patch_synodic": states_patch_syn.tolist(),
        },
        "j2000_initial": {
            "t_patch_et_s": t_patch_et.tolist(),
            "states_patch_km": states_patch_j2000.tolist(),
        },
        "correction": {
            "converged": bool(result.converged),
            "iterations": int(n_iter),
            "max_residual_km": float(result.max_residual),
            "velocity_residual": vel_res,
            "var_time": bool(args.var_time),
            "residual_history": list(result.residual_history),
            "corrected_states_km": np.asarray(result.state_patch).tolist(),
            "corrected_times_et_s": np.asarray(result.t_patch).tolist(),
            "wall_time_s": elapsed,
            "backend": "rust" if rust_available else "scipy",
        },
    }

    # 5. 可选：Rust vs Python 对比
    if args.compare_python and rust_available:
        print(f"\n5. SciPy 路径对比（禁用 Rust）...")
        prev = set_rust_stm(False)
        try:
            # 重建 dynamics 以确保干净状态
            dynamics_py, _ = build_ephemeris_dynamics(args, spice)
            result_py, elapsed_py = run_correction(
                args, t_patch_et, states_patch_j2000, dynamics_py, spice,
            )
        finally:
            set_rust_stm(prev)

        n_iter_py = getattr(result_py, "outer_iterations", None) or getattr(result_py, "iterations", 0)

        print(f"\n=== 修正结果（SciPy 路径）===")
        print(f"  converged: {result_py.converged}")
        print(f"  iterations: {n_iter_py}")
        print(f"  max_residual: {result_py.max_residual:.3e} km")
        print(f"  wall time: {elapsed_py:.2f} s")

        speedup = elapsed_py / elapsed if elapsed > 0 else float("inf")
        print(f"\n=== Rust vs SciPy ===")
        print(f"  Rust:  {elapsed:.2f} s")
        print(f"  SciPy: {elapsed_py:.2f} s")
        print(f"  加速比: {speedup:.2f}x")

        payload["correction_scipy"] = {
            "converged": bool(result_py.converged),
            "iterations": int(n_iter_py),
            "max_residual_km": float(result_py.max_residual),
            "residual_history": list(result_py.residual_history),
            "wall_time_s": elapsed_py,
            "backend": "scipy",
        }
        payload["comparison"] = {
            "rust_wall_time_s": elapsed,
            "scipy_wall_time_s": elapsed_py,
            "speedup": speedup,
        }

    # 保存
    if args.output_file:
        out_path = Path(args.output_file)
    else:
        out_path = project_root / "output" / "transfer" / f"corrected_transfer_{int(time.time())}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"\n结果已保存: {out_path}")

    import spiceypy
    spiceypy.kclear()

    print("\n完成。")


if __name__ == "__main__":
    main()

# ------------------------------------------------------------------
# GUI 注册
# ------------------------------------------------------------------

from tod.scripting import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='transfer',
    name='correct_transfer_to_ephemeris',
    description='星历修正',
    script_path='tod/transfers/dro_to_geo/correct_transfer_to_ephemeris.py',
    output_dir='output/transfer',
    group_label='DRO→GEO',
    cli_params=[
        CliParam('--opt-file', '优化结果文件', 'str', '', help='优化结果 JSON 文件路径。', file_category='transfer'),
        CliParam('--reference-epoch', '参考历元', 'str', '2025-06-21T11:00:06', help='UTC 参考历元。'),
        CliParam('--n-patch-points', 'patch points', 'int', '8', help='patch points 数量。'),
        CliParam('--method', '修正方法', 'str', 'two_level', help='星历修正方法（standard/two_level/homotopy）。'),
        CliParam('--position-tol', '位置容差', 'float', '1e-3', help='位置残差容差（km）。', unit_group='distance', default_unit='km'),
        CliParam('--velocity-tol', '速度容差', 'float', '1e-6', help='速度残差容差（km/s）。'),
        CliParam('--max-iter', '最大迭代', 'int', '50', help='最大迭代次数。'),
        CliParam('--compare-python', '对比 SciPy', 'bool', '', help='额外跑 SciPy 路径做 wall time 对比。'),
    ],
)
