"""
绘制 Halo 轨道族（仅读取已有 JSON，不生成轨道）

与 transfer-orbit-design 中 ``plot_dro_family.py`` 的用法一致：在脚本顶部配置
``FAMILY_JSON_PATH`` 指向 ``generate_halo_family.py`` 已保存的文件，或通过命令行传入路径。

数据流::

    generate_halo_family.py  ->  *.json  ->  本脚本  ->  *.png

用法::

    # 1）修改本文件中的 FAMILY_JSON_PATH 后直接运行
    python scripts/halo/plot/plot_halo_family.py

    # 2）命令行指定 JSON（相对项目根或绝对路径）
    python scripts/halo/plot/plot_halo_family.py output/halo/halo_L1_N_family_3857325361.json

    # 3）使用某目录下最新的 halo_*_family_*.json
    python scripts/halo/plot/plot_halo_family.py --latest

    # 仅保存 PNG、不弹窗
    python scripts/halo/plot/plot_halo_family.py path/to/family.json --no-show
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent

import matplotlib
import numpy as np

from e2m2e.core import OrbitFamily, CR3BP_System
from e2m2e.visualization import PlotConfig, FamilyPlotter, compute_stability_for_family

from scripts.utils.common import MU

# =============================================================================
# 用户配置：已生成的轨道族 JSON（与 generate_halo_family.py 输出一致）
# 命令行未传入路径且未使用 --latest 时，使用此处路径。
# =============================================================================
FAMILY_JSON_PATH = project_root / "output" / "halo" / "halo_L1_N_family_3857325998.json"

DEFAULT_HALO_DIR = project_root / "output" / "halo"


def find_latest_family_json(directory: Path) -> Path | None:
    """在目录中按修改时间选取最新的 halo_*_family_*.json。"""
    candidates = sorted(
        directory.glob("halo_*_family_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="从 JSON 读取 Halo 轨道族并绘图（不生成轨道，仅 OrbitFamily.load_from_file）",
    )
    parser.add_argument(
        "json_file",
        nargs="?",
        default=None,
        help="轨道族 JSON 路径；省略则使用脚本中的 FAMILY_JSON_PATH",
    )
    parser.add_argument(
        "--file",
        "-f",
        type=str,
        default=None,
        help="与位置参数等价，便于兼容旧用法",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help=f"使用 {DEFAULT_HALO_DIR} 下最新的 halo_*_family_*.json（显式选用，非默认行为）",
    )
    parser.add_argument(
        "--dir",
        type=str,
        default=str(DEFAULT_HALO_DIR),
        help="与 --latest 配合：在此目录下搜索（默认 output/halo）",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        default=None,
        help="PNG 输出目录，默认与 JSON 同目录",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=-1,
        help="起始轨道索引，-1 表示从第一条",
    )
    parser.add_argument(
        "--end",
        type=int,
        default=-1,
        help="结束轨道索引（含），-1 表示到最后一条",
    )
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="只保存图片，不调用 plt.show()",
    )
    return parser.parse_args()


def plot_halo_family(
    family_path: Path,
    output_dir: Path,
    plot_start: int = -1,
    plot_end: int = -1,
    show: bool = True,
) -> None:
    import matplotlib.pyplot as plt

    system = CR3BP_System(mu=MU, primary="earth", secondary="moon")

    family_result = OrbitFamily.load_from_file(filename=str(family_path), system=system)
    n_orbits = len(family_result)
    family_name = family_path.stem

    print(f"已加载: {family_path}")
    print(f"轨道条数: {n_orbits}")

    if plot_start == -1 and plot_end == -1:
        ps, pe = 0, n_orbits - 1
    elif plot_start == -1:
        ps, pe = 0, min(plot_end, n_orbits - 1)
    elif plot_end == -1:
        ps, pe = min(plot_start, n_orbits - 1), n_orbits - 1
    else:
        ps = min(plot_start, n_orbits - 1)
        pe = min(plot_end, n_orbits - 1)

    print(f"绘制索引 [{ps}, {pe}]，共 {pe - ps + 1} 条")

    subset_family = OrbitFamily(system=system)
    for i in range(ps, pe + 1):
        subset_family.add_orbit(family_result[i])

    print("正在计算 Jacobi 常数...")
    jacobi_values = family_result.get_jacobi_constants().tolist()
    jacobi_subset = [jacobi_values[i] for i in range(ps, pe + 1)]
    print(f"Jacobi 范围: {min(jacobi_subset):.6f} ~ {max(jacobi_subset):.6f}")

    print("正在计算稳定性指数（可能较慢）...")
    stability_values = compute_stability_for_family(family_result, family_result.system)
    stability_subset = [stability_values[i] for i in range(ps, pe + 1)]
    print(f"λmax 范围: {min(stability_subset):.6f} ~ {max(stability_subset):.6f}")

    sort_idx = np.argsort(jacobi_subset)
    jacobi_sorted = np.array(jacobi_subset)[sort_idx].tolist()
    periods_sorted = np.array(subset_family.periods)[sort_idx].tolist()
    stability_sorted = np.array(stability_subset)[sort_idx].tolist()

    config = PlotConfig(
        title=32, label=28, tick=26, legend=28, colorbar=26, suptitle=36, lp_label=32,
        title_y_offset=-0.12, title_y_offset_3d=-0.08, title_y_offset_dual=-0.18,
        title_y_offset_subplot=-0.15,
    )
    config.apply_rcparams()

    plotter = FamilyPlotter(system, config)

    jmin, jmax = min(jacobi_subset), max(jacobi_subset)
    smin, smax = min(stability_subset), max(stability_subset)
    seed_orbit = family_result[0]
    seed_jacobi = jacobi_values[0]
    seed_stability = stability_values[0]

    # ---------- 1. XZ ----------
    fig_2d, ax_2d = plotter.plot_family_2d(
        subset_family, jacobi_subset,
        title=f"Halo Orbit Family (XZ) — {n_orbits} orbits\n"
              f"C = [{jmin:.4f}, {jmax:.4f}], λmax = [{smin:.4f}, {smax:.4f}]",
        plane="xz",
        show_bodies=True, show_libration=True, show_colorbar=True,
        show=False,
    )
    plotter.plot_2d_projection(
        seed_orbit, plane="xz", color="red",
        label=f"Seed Halo (C={seed_jacobi:.4f}, λmax={seed_stability:.4f})",
        ax=ax_2d,
    )
    plt.tight_layout()
    plt.savefig(output_dir / f"{family_name}_2d_view.png", dpi=300, bbox_inches="tight")
    if show:
        plt.show()
    else:
        plt.close(fig_2d)

    # ---------- 2. 3D ----------
    fig_3d, ax_3d = plotter.plot_family_3d(
        subset_family, jacobi_subset,
        title=f"Halo Orbit Family (3D) — {n_orbits} orbits\n"
              f"C = [{jmin:.4f}, {jmax:.4f}], λmax = [{smin:.4f}, {smax:.4f}]",
        center=(0.9, 0, 0), radius=0.4, elev=20, azim=-60,
        show=False,
    )
    plotter.plot_3d_orbit(
        seed_orbit, color="red",
        label=f"Seed Halo (C={seed_jacobi:.4f})",
        ax=ax_3d, show_start=True,
    )
    plt.tight_layout()
    plt.savefig(output_dir / f"{family_name}_3d_view.png", dpi=300, bbox_inches="tight")
    if show:
        plt.show()
    else:
        plt.close(fig_3d)

    # ---------- 3. Period & stability ----------
    plotter.plot_jacobi_period_stability(
        jacobi_sorted, periods_sorted, stability_sorted,
        title=f"Halo Orbit Family — Period and Stability (n = {n_orbits})",
        save_path=output_dir / f"{family_name}_period_stability.png",
        show=show,
    )

    # ---------- 4. Overview ----------
    plotter.plot_family_overview(
        subset_family, jacobi_subset, subset_family.periods, stability_subset,
        suptitle=f"Halo Orbit Family Overview — Earth–Moon CR3BP (n = {n_orbits})",
        plane="xz", center_3d=(0.9, 0, 0), radius_3d=0.4,
        elev=20, azim=-60,
        save_path=output_dir / f"{family_name}_overview.png",
        show=show,
    )

    print(f"\n图表已保存至: {output_dir}")
    print(f"  - {family_name}_2d_view.png")
    print(f"  - {family_name}_3d_view.png")
    print(f"  - {family_name}_period_stability.png")
    print(f"  - {family_name}_overview.png")


def _resolve_json_path(user_path: str) -> Path:
    p = Path(user_path)
    return p.resolve() if p.is_absolute() else (project_root / p).resolve()


def main() -> None:
    args = parse_args()
    if args.no_show or not os.environ.get("DISPLAY"):
        matplotlib.use("Agg")

    if args.latest:
        search_dir = Path(args.dir)
        if not search_dir.is_absolute():
            search_dir = (project_root / search_dir).resolve()
        found = find_latest_family_json(search_dir)
        if found is None:
            print(f"[error] 在 {search_dir} 未找到 halo_*_family_*.json")
            print("请先生成: python scripts/halo/generate/generate_halo_family.py")
            sys.exit(1)
        family_path = found
        print(f"[info] --latest: 使用 {family_path}")
    elif args.json_file:
        family_path = _resolve_json_path(args.json_file)
    elif args.file:
        family_path = _resolve_json_path(args.file)
    else:
        family_path = Path(FAMILY_JSON_PATH)
        if not family_path.is_absolute():
            family_path = (project_root / family_path).resolve()
        else:
            family_path = family_path.resolve()
        print(f"[info] 使用脚本内 FAMILY_JSON_PATH: {family_path}")

    if not family_path.is_file():
        print(f"[error] 文件不存在: {family_path}")
        print("请修改本脚本顶部的 FAMILY_JSON_PATH，或传入 JSON 路径，或使用 --latest。")
        sys.exit(1)

    output_dir = Path(args.output_dir) if args.output_dir else family_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    plot_halo_family(
        family_path=family_path,
        output_dir=output_dir,
        plot_start=args.start,
        plot_end=args.end,
        show=not args.no_show,
    )


if __name__ == "__main__":
    main()
