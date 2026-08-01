"""analyze_stm_condition_number 脚本（仿真 4）。

沿分段打靶修正后的 DRO→GEO 转移轨迹，逐段传播状态转移矩阵（STM），
计算每段 STM 条件数 κ(Φ) = ‖Φ‖·‖Φ⁻¹‖ 以及从出发时刻起的累积 STM 条件数，
绘制条件数随时间变化曲线，为标准多重打靶在长弧段不收敛提供数值依据。

运行示例:
    .. code-block:: bash

       uv run python -m tod.transfers.dro_to_geo.analyze_stm_condition_number \
           --input output/transfer/corrected_transfer_1785255430.json
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np

project_root = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_SPICE_KERNEL_DIR = Path(
    os.environ.get("SPICE_KERNEL_DIR", str(project_root.parent / "e2m2e" / "kernels"))
)
DEFAULT_INPUT = project_root / "output" / "transfer" / "corrected_transfer_1785255430.json"
DEFAULT_OUTPUT_JSON = project_root / "output" / "transfer" / "stm_condition_number.json"
DEFAULT_PLOT = project_root / "figures" / "stm_condition_number.png"


def parse_args():
    parser = argparse.ArgumentParser(
        description="DRO→GEO 转移轨迹 STM 条件数分析（仿真 4）",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--input", type=str, default=str(DEFAULT_INPUT),
        help="分段打靶修正轨迹 JSON（corrected_transfer_*.json）",
    )
    parser.add_argument(
        "--spice-kernel-dir", type=str, default=str(DEFAULT_SPICE_KERNEL_DIR),
        help="SPICE kernel 目录",
    )
    parser.add_argument(
        "--bodies", type=str, default="EARTH,MOON,SUN",
        help="参与的天体列表，逗号分隔",
    )
    parser.add_argument("--rtol", type=float, default=1e-12, help="积分相对容差")
    parser.add_argument("--atol", type=float, default=1e-12, help="积分绝对容差")
    parser.add_argument(
        "--output-file", type=str, default=str(DEFAULT_OUTPUT_JSON),
        help="输出 JSON 路径",
    )
    parser.add_argument(
        "--plot-save", type=str, default=str(DEFAULT_PLOT),
        help="输出图片路径",
    )
    return parser.parse_args()


def compute_stm_condition_number(stm_flat) -> float:
    """计算 STM 条件数：κ(Φ) = ‖Φ‖·‖Φ⁻¹‖（Frobenius 范数）。"""
    stm_matrix = np.array(stm_flat, dtype=float).reshape(6, 6)
    norm_stm = np.linalg.norm(stm_matrix)
    norm_stm_inv = np.linalg.norm(np.linalg.inv(stm_matrix))
    return float(norm_stm * norm_stm_inv)


def main():
    args = parse_args()

    input_path = Path(args.input)
    if not input_path.is_file():
        raise FileNotFoundError(f"未找到修正轨迹文件: {input_path}")

    print(f"读取修正轨迹: {input_path}")
    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    correction = data["correction"]
    t_patch = np.array(correction["corrected_times_et_s"], dtype=float)
    state_patch = np.array(correction["corrected_states_km"], dtype=float)
    n_segments = len(t_patch) - 1
    print(f"  patch points: {len(t_patch)}，分段数: {n_segments}")
    print(f"  弧段总时长: {(t_patch[-1] - t_patch[0]) / 86400:.2f} 天")

    # 加载 SPICE + 构建星历系统（取 GM，避免硬编码）
    print("\n1. 加载 SPICE kernels...")
    import spiceypy
    from e2m2e.core.ephemeris_system import EphemerisSystem
    from e2m2e.core.spice import SPICEManager
    from e2m2e.mbse.data.enums import ReferenceFrame

    spice = SPICEManager()
    spice_kernel_dir = Path(args.spice_kernel_dir)
    kernel_path = spice.find_ephemeris_kernel(str(spice_kernel_dir))
    spiceypy.furnsh(str(spice_kernel_dir / "naif0012.tls"))
    spice.load_kernel(kernel_path)

    bodies = [b.upper() for b in args.bodies.split(",") if b.strip()]
    eph_system = EphemerisSystem(
        bodies=bodies,
        spice=spice,
        origin="EARTH",
        frame=ReferenceFrame.J2000,
    )
    gm_values = [float(gm) for gm in eph_system.get_gm_values()]
    print(f"  bodies: {bodies}")

    # 2. 逐段传播 STM 并计算条件数
    try:
        from e2m2e._integrators import propagate_with_stm_py
    except ModuleNotFoundError:
        raise RuntimeError(
            "当前 e2m2e 版本已移除 propagate_with_stm_py；"
            "STM 条件数分析请改用 e2m2e algorithm/ 对应能力。"
        )

    print(f"\n2. 逐段传播 STM（rtol=atol={args.rtol:.0e}）...")
    segments = []
    kappa_cumulative = []
    stm_cumulative = np.eye(6)

    for i in range(n_segments):
        result = propagate_with_stm_py(
            bodies=bodies,
            origin="EARTH",
            gm_values=gm_values,
            t_span=(float(t_patch[i]), float(t_patch[i + 1])),
            t_eval=[float(t_patch[i]), float(t_patch[i + 1])],
            initial_state=state_patch[i].tolist(),
            rtol=args.rtol,
            atol=args.atol,
        )
        stm_seg = np.array(result["stm"][-1], dtype=float).reshape(6, 6)
        kappa_seg = float(np.linalg.norm(stm_seg) * np.linalg.norm(np.linalg.inv(stm_seg)))

        # 累积 STM：Φ(t_{i+1}, t_0) = Φ(t_{i+1}, t_i) · Φ(t_i, t_0)
        stm_cumulative = stm_seg @ stm_cumulative
        kappa_cum = float(
            np.linalg.norm(stm_cumulative) * np.linalg.norm(np.linalg.inv(stm_cumulative))
        )
        kappa_cumulative.append(kappa_cum)

        duration_days = (t_patch[i + 1] - t_patch[i]) / 86400.0
        elapsed_days = (t_patch[i + 1] - t_patch[0]) / 86400.0
        segments.append({
            "segment_index": i,
            "t_start_et_s": float(t_patch[i]),
            "t_end_et_s": float(t_patch[i + 1]),
            "duration_days": duration_days,
            "elapsed_days_from_departure": elapsed_days,
            "kappa_segment": kappa_seg,
            "kappa_cumulative": kappa_cum,
        })
        print(
            f"  段 {i + 1:2d}/{n_segments}: Δt={duration_days:5.2f} 天，"
            f"κ_段={kappa_seg:.3e}，κ_累积={kappa_cum:.3e}"
        )

    kappas_seg = [s["kappa_segment"] for s in segments]

    # 3. 保存 JSON
    payload = {
        "metadata": {
            "source_file": str(input_path),
            "bodies": bodies,
            "origin": "EARTH",
            "rtol": args.rtol,
            "atol": args.atol,
            "n_patch_points": len(t_patch),
            "n_segments": n_segments,
            "arc_duration_days": (t_patch[-1] - t_patch[0]) / 86400.0,
        },
        "segments": segments,
        "summary": {
            "kappa_segment_max": max(kappas_seg),
            "kappa_segment_mean": float(np.mean(kappas_seg)),
            "kappa_segment_min": min(kappas_seg),
            "kappa_cumulative_final": kappa_cumulative[-1],
        },
    }
    out_path = Path(args.output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"\n结果已保存: {out_path}")

    # 4. 绘图
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from tod.plot.config import apply_standard_plot_config
    apply_standard_plot_config()

    elapsed = [s["elapsed_days_from_departure"] for s in segments]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.semilogy(elapsed, kappas_seg, "b-o", ms=4, lw=1.2, label="分段 STM 条件数")
    ax.semilogy(elapsed, kappa_cumulative, "r-s", ms=4, lw=1.2, label="累积 STM 条件数")
    ax.set_xlabel("距出发时刻时间 (天)")
    ax.set_ylabel("STM 条件数 κ(Φ)")
    ax.set_title("DRO→GEO 转移轨迹 STM 条件数分析")
    ax.grid(True, alpha=0.3, which="both")
    ax.legend()
    fig.tight_layout()

    plot_path = Path(args.plot_save)
    plot_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(plot_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"图片已保存: {plot_path}")

    print("\n=== 汇总 ===")
    print(f"  分段条件数 max/mean/min: {max(kappas_seg):.3e} / {np.mean(kappas_seg):.3e} / {min(kappas_seg):.3e}")
    print(f"  全弧累积条件数: {kappa_cumulative[-1]:.3e}")

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
    name='analyze_stm_condition_number',
    description='STM 条件数分析',
    script_path='tod/transfers/dro_to_geo/analyze_stm_condition_number.py',
    output_dir='output/transfer',
    group_label='DRO→GEO',
    cli_params=[
        CliParam('--input', '修正轨迹文件', 'str', '', help='分段打靶修正轨迹 JSON。', file_category='transfer'),
        CliParam('--rtol', '相对容差', 'float', '1e-12', help='积分相对容差。'),
        CliParam('--atol', '绝对容差', 'float', '1e-12', help='积分绝对容差。'),
    ],
)
