# pyright: reportArgumentType=false, reportOptionalMemberAccess=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false, reportInvalidTypeForm=false, reportCallIssue=false, reportPrivateImportUsage=false
"""plot_halo_ephemeris_correction 可视化脚本。

本模块读取轨道、转移或星历修正 JSON 结果，并生成用于检查几何形态、稳定性或优化质量的图形。输入文件通常来自 output/ 下的生成、搜索或优化结果；输出为 Matplotlib 窗口或保存图片。

运行示例:
    .. code-block:: bash

       uv run python -m tod.plot.ephemeris.plot_halo_ephemeris_correction --help
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np

if TYPE_CHECKING:
    from matplotlib.figure import Figure

logger = logging.getLogger(__name__)

_REQUIRED_KEYS = frozenset({
    "orbit_type",
    "method",
    "converged",
    "iterations",
    "max_residual",
    "residual_history",
    "reference_epoch",
    "n_patch_points",
    "bodies",
    "cr3bp_halo",
    "position_errors_km",
    "corrected_states",
    "corrected_times_et",
    "full_trajectory_states",
    "full_trajectory_times_et",
})

def load_halo_correction_data(json_path: Path) -> dict:
    """加载并验证 Halo 星历修正 JSON 文件。

    Returns:
        dict，其中 corrected_states / corrected_times_et /
        full_trajectory_states / full_trajectory_times_et 已转为 np.ndarray。
    """
    if not json_path.is_file():
        raise FileNotFoundError(f"数据文件不存在: {json_path}")

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    missing = _REQUIRED_KEYS - data.keys()
    if missing:
        raise KeyError(f"JSON 缺少必需字段: {missing}")

    data["corrected_states"] = np.array(data["corrected_states"])
    data["corrected_times_et"] = np.array(data["corrected_times_et"])
    data["full_trajectory_states"] = np.array(data["full_trajectory_states"])
    data["full_trajectory_times_et"] = np.array(data["full_trajectory_times_et"])

    return data

def plot_residual_convergence(
    fig: Figure,
    residual_history: list[float],
    velocity_residual_history: list[float] | None = None,
    *,
    tolerance: float = 1e-3,
) -> None:
    """在 fig 上绘制位置残差和速度残差收敛曲线。

    Args:
        fig: matplotlib Figure，函数会向其添加 1×2 子图。
        residual_history: 每次迭代的位置残差列表。
        velocity_residual_history: 每次迭代的速度残差列表，None 则隐藏速度轴。
        tolerance: 容差参考线。
    """
    ax_pos = fig.add_subplot(121)
    ax_vel = fig.add_subplot(122)

    iters = range(1, len(residual_history) + 1)
    ax_pos.semilogy(
        iters,
        residual_history,
        "o-",
        color="royalblue",
        linewidth=2,
        markersize=5,
        label="Position residual",
    )
    ax_pos.axhline(
        y=tolerance,
        color="red",
        linestyle="--",
        linewidth=1,
        label=f"Tolerance ({tolerance:.0e} km)",
    )
    ax_pos.set_xlabel("Iteration")
    ax_pos.set_ylabel("Max position residual (km)")
    ax_pos.set_title("Position Residual Convergence")
    ax_pos.legend()
    ax_pos.grid(True, alpha=0.3)

    if velocity_residual_history is not None:
        vel_iters = range(1, len(velocity_residual_history) + 1)
        ax_vel.semilogy(
            vel_iters,
            velocity_residual_history,
            "o-",
            color="crimson",
            linewidth=2,
            markersize=5,
            label="Velocity residual",
        )
        ax_vel.axhline(
            y=1e-6,
            color="red",
            linestyle="--",
            linewidth=1,
            label="Tolerance (1e-6 km/s)",
        )
        ax_vel.set_xlabel("Iteration")
        ax_vel.set_ylabel("Max velocity residual (km/s)")
        ax_vel.set_title("Velocity Residual Convergence")
        ax_vel.legend()
        ax_vel.grid(True, alpha=0.3)
    else:
        ax_vel.set_visible(False)

def plot_xy_projection_comparison(
    fig: Figure,
    pre_xy: np.ndarray,
    post_xy: np.ndarray,
    patch_xy: np.ndarray,
) -> None:
    """绘制修正前后 XY 投影对比（两个子图）。

    Args:
        fig: matplotlib Figure。
        pre_xy: 修正前轨迹 (N, 2)，列为 X, Y。
        post_xy: 修正后轨迹 (N, 2)，列为 X, Y。
        patch_xy: patch points 位置 (M, 2)。
    """
    ax_pre = fig.add_subplot(121)
    ax_post = fig.add_subplot(122)

    ax_pre.plot(pre_xy[:, 0], pre_xy[:, 1], color="royalblue", linewidth=1.2, alpha=0.8)
    ax_pre.scatter(
        patch_xy[:, 0],
        patch_xy[:, 1],
        color="red",
        s=40,
        zorder=5,
        label="Patch points",
    )
    ax_pre.set_xlabel("X")
    ax_pre.set_ylabel("Y")
    ax_pre.set_title("Before Correction")
    ax_pre.legend()
    ax_pre.set_aspect("equal")
    ax_pre.grid(True, alpha=0.3)

    ax_post.plot(
        post_xy[:, 0], post_xy[:, 1], color="crimson", linewidth=1.2, alpha=0.8,
    )
    ax_post.scatter(
        patch_xy[:, 0],
        patch_xy[:, 1],
        color="red",
        s=40,
        zorder=5,
        label="Patch points",
    )
    ax_post.set_xlabel("X")
    ax_post.set_ylabel("Y")
    ax_post.set_title("After Correction")
    ax_post.legend()
    ax_post.set_aspect("equal")
    ax_post.grid(True, alpha=0.3)

def plot_3d_trajectory_comparison(
    fig: Figure,
    cr3bp_states: np.ndarray,
    eph_states: np.ndarray,
    patch_states: np.ndarray,
    mu: float,
) -> None:
    """绘制 3D 轨迹对比图（Synodic 坐标系）。

    Args:
        fig: matplotlib Figure。
        cr3bp_states: CR3BP Halo 轨道状态 (N, 3)，列 X, Y, Z（归一化）。
        eph_states: 修正后星历轨迹 (M, 3)，列 X, Y, Z（归一化）。
        patch_states: patch points 位置 (K, 3)。
        mu: 质量参数（用于标注地球/月球位置）。
    """
    ax = fig.add_subplot(111, projection="3d")

    ax.plot(
        cr3bp_states[:, 0],
        cr3bp_states[:, 1],
        cr3bp_states[:, 2],
        color="royalblue",
        linewidth=1.2,
        alpha=0.7,
        label="CR3BP Halo",
    )
    ax.plot(
        eph_states[:, 0],
        eph_states[:, 1],
        eph_states[:, 2],
        color="crimson",
        linewidth=1.5,
        alpha=0.9,
        label="Ephemeris corrected",
    )

    ax.scatter(
        patch_states[:, 0],
        patch_states[:, 1],
        patch_states[:, 2],
        color="orange",
        s=30,
        zorder=5,
        label="Patch points",
    )

    ax.scatter(-mu, 0, 0, color="blue", s=200, zorder=5, label="Earth")
    ax.scatter(1 - mu, 0, 0, color="silver", s=80, zorder=5, label="Moon")

    l1_x = 1 - mu - (mu / 3) ** (1 / 3)
    l2_x = 1 - mu + (mu / 3) ** (1 / 3)
    ax.scatter(l1_x, 0, 0, color="green", marker="^", s=40, zorder=5, label="L1")
    ax.scatter(l2_x, 0, 0, color="green", marker="^", s=40, zorder=5, label="L2")

    ax.set_xlabel("X (n.d.)")
    ax.set_ylabel("Y (n.d.)")
    ax.set_zlabel("Z (n.d.)")
    ax.set_title("Halo CR3BP vs Ephemeris Correction")
    ax.legend(loc="upper left")
    ax.view_init(elev=25, azim=-60)

def generate_plots(
    json_path: Path,
    output_dir: Path | None = None,
) -> list[Path]:
    """从 JSON 文件生成全部三张图并保存为 PNG。

    Args:
        json_path: Halo 星历修正 JSON 文件路径。
        output_dir: PNG 输出目录，默认与 JSON 同目录。

    Returns:
        保存的 PNG 文件路径列表。
    """
    from tod.commons.constants import MU

    if output_dir is None:
        output_dir = json_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    data = load_halo_correction_data(json_path)
    stem = json_path.stem
    saved: list[Path] = []

    # 图 1：残差收敛
    fig_res = plt.figure(figsize=(16, 6))
    plot_residual_convergence(
        fig_res,
        data["residual_history"],
        data.get("velocity_residual_history"),
    )
    fig_res.tight_layout()
    path_res = output_dir / f"{stem}_residual.png"
    fig_res.savefig(path_res, dpi=300, bbox_inches="tight")
    plt.close(fig_res)
    saved.append(path_res)

    # 图 2：XY 投影对比
    full_states = data["full_trajectory_states"]
    corrected = data["corrected_states"]
    pre_xy = full_states[:, :2]
    post_xy = full_states[:, :2]
    patch_xy = corrected[:, :2]

    fig_xy = plt.figure(figsize=(14, 6))
    plot_xy_projection_comparison(fig_xy, pre_xy=pre_xy, post_xy=post_xy, patch_xy=patch_xy)
    fig_xy.tight_layout()
    path_xy = output_dir / f"{stem}_xy.png"
    fig_xy.savefig(path_xy, dpi=300, bbox_inches="tight")
    plt.close(fig_xy)
    saved.append(path_xy)

    # 图 3：3D 轨迹对比
    cr3bp_xy = full_states[:, :3]
    eph_xy = full_states[:, :3]
    patch_3d = corrected[:, :3]

    fig_3d = plt.figure(figsize=(12, 9))
    plot_3d_trajectory_comparison(
        fig_3d,
        cr3bp_states=cr3bp_xy,
        eph_states=eph_xy,
        patch_states=patch_3d,
        mu=MU,
    )
    fig_3d.tight_layout()
    path_3d = output_dir / f"{stem}_3d.png"
    fig_3d.savefig(path_3d, dpi=300, bbox_inches="tight")
    plt.close(fig_3d)
    saved.append(path_3d)

    logger.info("已保存 %d 张图:", len(saved))
    for p in saved:
        logger.info("  %s", p)

    return saved

def parse_args() -> argparse.Namespace:
    """解析命令行参数。
    
    Returns:
        解析后的命令行参数命名空间。
    """
    parser = argparse.ArgumentParser(description="绘制 Halo 轨道星历修正结果", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        "--ephemeris-file",
        type=str,
        default=None,
        help="Halo 星历修正 JSON 文件路径",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="PNG 输出目录",
    )
    return parser.parse_args()

def main() -> None:
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    args = parse_args()

    from tod.commons.paths import find_project_root

    project_root = find_project_root(Path(__file__))
    if args.ephemeris_file:
        json_path = Path(args.ephemeris_file)
    else:
        output_dir = project_root / "output" / "ephemeris"
        candidates = sorted(
            output_dir.glob("halo_ephemeris_correction_*.json"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            logger.error("未找到 halo_ephemeris_correction_*.json 文件")
            sys.exit(1)
        json_path = candidates[0]

    output_dir = Path(args.output_dir) if args.output_dir else json_path.parent
    logger.info("输入: %s", json_path)

    generate_plots(json_path, output_dir=output_dir)

if __name__ == "__main__":
    main()
