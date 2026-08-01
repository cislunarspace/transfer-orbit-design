"""analyze_patch_point_sensitivity 脚本（仿真 5）。

固定 87.8 天 DRO→GEO 长弧（search_index=14），测试分段打靶不同
``points_per_segment`` 参数（默认 5/10/15/20）对收敛性、最终残差、
迭代次数与计算时间的影响，为分段打靶的参数选择提供依据。

采样与修正管线复用 ``correct_transfer_to_ephemeris.py`` 的函数，
保证与已生成修正轨迹（n_patch_points=30, adaptive 采样）设置一致。

运行示例:
    .. code-block:: bash

       uv run python -m tod.transfers.dro_to_geo.analyze_patch_point_sensitivity \
           --opt-file output/transfer/optimization_dro_geo_1785168810.json \
           --search-index 14 --reference-epoch 2025-06-21T11:00:06
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from tod.transfers.dro_to_geo.correct_transfer_to_ephemeris import (
    build_ephemeris_dynamics,
    build_forces_from_dynamics,
    sample_patch_points_adaptive,
)
from tod.transfers.dro_to_geo.transfer_to_ephemeris import (
    load_optimization_results,
    synodic_to_j2000_states,
)

project_root = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_SPICE_KERNEL_DIR = Path(
    os.environ.get("SPICE_KERNEL_DIR", str(project_root.parent / "e2m2e" / "kernels"))
)
DEFAULT_OPT_FILE = project_root / "output" / "transfer" / "optimization_dro_geo_1785168810.json"
DEFAULT_OUTPUT_JSON = project_root / "output" / "transfer" / "patch_point_sensitivity.json"
DEFAULT_PLOT = project_root / "figures" / "patch_point_sensitivity.png"


def parse_args():
    parser = argparse.ArgumentParser(
        description="分段打靶 points_per_segment 参数敏感性分析（仿真 5）",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--opt-file", type=str, default=str(DEFAULT_OPT_FILE),
        help="优化结果 JSON 文件路径（optimization_dro_geo_*.json）",
    )
    parser.add_argument(
        "--search-index", type=int, default=14,
        help="选用的 search_index（87.8 天长弧）",
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
        "--n-patch-points", type=int, default=30,
        help="patch points 数量（与已生成修正轨迹一致，adaptive 采样）",
    )
    parser.add_argument(
        "--pps-list", type=str, default="5,10,15,20",
        help="待测试的 points_per_segment 列表，逗号分隔",
    )
    parser.add_argument("--overlap-points", type=int, default=2, help="相邻段重叠点数")
    parser.add_argument("--max-iter", type=int, default=30, help="每段最大迭代次数")
    parser.add_argument("--tolerance", type=float, default=1e-3, help="位置残差容差（km）")
    parser.add_argument(
        "--output-file", type=str, default=str(DEFAULT_OUTPUT_JSON),
        help="输出 JSON 路径",
    )
    parser.add_argument(
        "--plot-save", type=str, default=str(DEFAULT_PLOT),
        help="输出图片路径",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    opt_path = Path(args.opt_file)
    if not opt_path.is_file():
        raise FileNotFoundError(f"未找到优化结果文件: {opt_path}")

    print(f"读取优化结果: {opt_path}")
    data = load_optimization_results(opt_path)

    matches = [
        r for r in data.get("results", [])
        if r.get("search_index") == args.search_index and r.get("nlp", {}).get("success")
    ]
    if not matches:
        raise ValueError(f"search_index={args.search_index} 无成功优化结果")
    best = matches[0]
    nlp = best["nlp"]

    import tod.commons.constants as _tod_constants
    from tod.commons.constants import TU

    print(f"\n=== 选中结果 ===")
    print(f"  search_index: {best['search_index']}")
    print(f"  transfer_time: {nlp['transfer_time']:.4f} TU = {nlp['transfer_time'] * TU:.1f} 天")

    # 1. CR3BP 前向积分 + adaptive 采样 patch points
    print(f"\n1. CR3BP 积分 + 采样 {args.n_patch_points} 个 patch points（adaptive）...")
    from e2m2e.core import CR3BP_System, CR3BP_Dynamics
    from tod.commons.orbits import compute_departure_velocity

    system = CR3BP_System(mu=_tod_constants.MU, primary="earth", secondary="moon")
    cr3bp_dynamics = CR3BP_Dynamics(system=system)
    cr3bp_dynamics.integrator = "DOP853"
    cr3bp_dynamics.rtol = 1e-12
    cr3bp_dynamics.atol = 1e-12
    cr3bp_dynamics.max_step = 1.0 / (24.0 * _tod_constants.TU)

    departure_state_raw = np.array(best["departure_state"], dtype=float)
    v_perturbed = compute_departure_velocity(departure_state_raw, nlp["alpha"])
    state0 = np.concatenate([departure_state_raw[:3], v_perturbed])
    transfer_time = nlp["transfer_time"]

    t_patch_syn, states_patch_syn = sample_patch_points_adaptive(
        cr3bp_dynamics, state0, transfer_time, args.n_patch_points, 1.0,
    )
    print(f"  采样完成：{len(t_patch_syn)} 个点")

    # 2. 加载 SPICE + synodic→J2000
    print("\n2. 加载 SPICE kernels...")
    from e2m2e.core.spice import SPICEManager

    spice = SPICEManager()
    eph_args = SimpleNamespace(
        spice_kernel_dir=args.spice_kernel_dir,
        bodies=args.bodies,
    )
    dynamics, bodies = build_ephemeris_dynamics(eph_args, spice)
    reference_et = float(spice.utc_to_et(args.reference_epoch))
    print(f"  参考历元 ET: {reference_et:.1f} s")

    print("\n3. Synodic → J2000 坐标转换...")
    states_patch_j2000 = synodic_to_j2000_states(
        states_patch_syn, t_patch_syn, reference_et, system, spice,
    )
    t_patch_et = reference_et + t_patch_syn * _tod_constants.TU * 86400

    forces = build_forces_from_dynamics(dynamics)
    origin = dynamics.system.origin

    # 4. 扫描 points_per_segment
    pps_list = [int(x) for x in args.pps_list.split(",") if x.strip()]
    print(f"\n4. 分段打靶参数扫描：points_per_segment ∈ {pps_list}")
    try:
        from e2m2e._integrators import segmented_shooting_correct_py
    except ModuleNotFoundError:
        raise RuntimeError(
            "当前 e2m2e 版本已移除 segmented_shooting_correct_py；"
            "分段打靶参数敏感性分析请改用 e2m2e algorithm/ephemeris_correction。"
        )

    results = []
    for pps in pps_list:
        print(f"\n  --- points_per_segment = {pps} ---")
        t0 = time.perf_counter()
        result = segmented_shooting_correct_py(
            forces=forces,
            observer=origin,
            t_patch=t_patch_et.tolist(),
            state_patch=states_patch_j2000.tolist(),
            points_per_segment=pps,
            overlap_points=args.overlap_points,
            enable_merging=True,
            max_iter_per_segment=args.max_iter,
            tolerance=args.tolerance,
            rtol=1e-10,
            verbose=False,
        )
        wall_time = time.perf_counter() - t0

        record = {
            "points_per_segment": pps,
            "converged": bool(result.converged),
            "max_residual_km": float(result.max_residual),
            "total_iterations": int(result.total_iterations),
            "n_segments": int(result.n_segments),
            "wall_time_s": wall_time,
        }
        results.append(record)
        print(
            f"    converged={record['converged']}，残差={record['max_residual_km']:.3e} km，"
            f"迭代={record['total_iterations']}，段数={record['n_segments']}，"
            f"耗时={wall_time:.2f} s"
        )

    # 5. 保存 JSON
    payload = {
        "metadata": {
            "source_file": str(opt_path),
            "search_index": best["search_index"],
            "reference_epoch": args.reference_epoch,
            "reference_et_s": reference_et,
            "bodies": list(bodies),
            "n_patch_points": args.n_patch_points,
            "sampling": "adaptive",
            "overlap_points": args.overlap_points,
            "max_iter_per_segment": args.max_iter,
            "tolerance_km": args.tolerance,
            "transfer_time_days": nlp["transfer_time"] * TU,
        },
        "results": results,
    }
    out_path = Path(args.output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"\n结果已保存: {out_path}")

    # 6. 绘图
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from tod.plot.config import apply_standard_plot_config
    apply_standard_plot_config()

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    ax = axes[0]
    ax.plot(pps_list, [r["max_residual_km"] for r in results], "b-o")
    ax.set_xlabel("points_per_segment")
    ax.set_ylabel("最大残差 (km)")
    ax.set_yscale("log")
    ax.set_title("最终残差")
    ax.grid(True, alpha=0.3)

    ax = axes[1]
    ax.plot(pps_list, [r["total_iterations"] for r in results], "g-s")
    ax.set_xlabel("points_per_segment")
    ax.set_ylabel("总迭代次数")
    ax.set_title("迭代次数")
    ax.grid(True, alpha=0.3)

    ax = axes[2]
    ax.plot(pps_list, [r["wall_time_s"] for r in results], "r-^")
    ax.set_xlabel("points_per_segment")
    ax.set_ylabel("计算时间 (s)")
    ax.set_title("计算时间")
    ax.grid(True, alpha=0.3)

    fig.suptitle("分段打靶 points_per_segment 参数敏感性（87.8 天 DRO→GEO 长弧）", fontsize=14)
    fig.tight_layout()

    plot_path = Path(args.plot_save)
    plot_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(plot_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"图片已保存: {plot_path}")

    # 7. 推荐参数：收敛前提下残差达标、耗时最短
    converged = [r for r in results if r["converged"]]
    if converged:
        recommended = min(converged, key=lambda r: r["wall_time_s"])
        print(
            f"\n推荐 points_per_segment = {recommended['points_per_segment']}"
            f"（收敛，耗时 {recommended['wall_time_s']:.2f} s，"
            f"残差 {recommended['max_residual_km']:.3e} km）"
        )
    else:
        print("\n警告：所有参数组合均未收敛，请检查 tolerance / max_iter 设置。")

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
    name='analyze_patch_point_sensitivity',
    description='分段打靶参数敏感性',
    script_path='tod/transfers/dro_to_geo/analyze_patch_point_sensitivity.py',
    output_dir='output/transfer',
    group_label='DRO→GEO',
    cli_params=[
        CliParam('--opt-file', '优化结果文件', 'str', '', help='优化结果 JSON 文件路径。', file_category='transfer'),
        CliParam('--search-index', 'search_index', 'int', '14', help='选用的 search_index。'),
        CliParam('--reference-epoch', '参考历元', 'str', '2025-06-21T11:00:06', help='UTC 参考历元。'),
        CliParam('--pps-list', 'pps 列表', 'str', '5,10,15,20', help='待测试的 points_per_segment 列表。'),
    ],
)
