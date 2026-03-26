"""
可视化 grid_search 输出的搜索结果 JSON：仅绘制可行解的 α 与出发 Δv 散点图。

在下方 ``RESULTS_JSON`` 中指定要绘制的 grid_search 输出 JSON（相对仓库根目录或绝对路径均可）。

Δv 优先使用 JSON 中的 dv_departure，否则由 departure_state 与 α 按搜索阶段速度扰动模型计算。

用法:
    python plot_search_results.py
    python plot_search_results.py --save output/transfer/figures/search_alpha_dv.png
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
import numpy as np

project_root = Path(__file__).resolve().parent.parent.parent

# =============================================================================
# 数据文件：grid_search 输出的 JSON
# =============================================================================
RESULTS_JSON = project_root / "output/transfer/search_results_200-101-0.5-2.5-2.299848_3857330924.json"
# 示例: RESULTS_JSON = project_root / "output/transfer/search_results_10-101-0.5-2.5-2.298634_3857123456.json"


def departure_delta_v_norm(state6: np.ndarray, alpha: float) -> float:
    """与 e2m2e DROTransferSearch._compute_departure_velocity 一致，返回 ‖v'−v‖（无量纲速度）。"""
    pos = np.asarray(state6[:3], dtype=np.float64)
    vel = np.asarray(state6[3:6], dtype=np.float64)
    r_xy = float(np.sqrt(pos[0] ** 2 + pos[1] ** 2))
    if r_xy < 1e-10:
        return float("nan")
    tangential = np.array([-pos[1], pos[0], 0.0]) / r_xy
    radial = pos / np.linalg.norm(pos)
    v_radial_comp = float(np.dot(vel, radial))
    v_tangential_comp = float(np.dot(vel, tangential))
    new_vel = v_radial_comp * radial + alpha * v_tangential_comp * tangential
    return float(np.linalg.norm(new_vel - vel))


def feasible_alpha_and_departure_dv(rows: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    """仅可行解；优先使用 JSON 中的 dv_departure（标量），否则由 departure_state 与 alpha 计算。"""
    alphas: list[float] = []
    dvs: list[float] = []
    for r in rows:
        if not r.get("is_feasible"):
            continue
        alpha = r.get("alpha")
        if alpha is None:
            continue
        dv_raw = r.get("dv_departure")
        if dv_raw is not None:
            dv_arr = np.asarray(dv_raw, dtype=np.float64).ravel()
            dv = float(dv_arr[0]) if dv_arr.size == 1 else float(np.linalg.norm(dv_arr))
        else:
            ds = r.get("departure_state")
            if ds is None:
                continue
            dv = departure_delta_v_norm(np.asarray(ds, dtype=np.float64), float(alpha))
        if np.isfinite(dv):
            alphas.append(float(alpha))
            dvs.append(dv)
    return np.asarray(alphas, dtype=np.float64), np.asarray(dvs, dtype=np.float64)


def load_search_results(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def subsample_indices(n: int, max_points: int | None, seed: int) -> np.ndarray:
    if max_points is None or n <= max_points:
        return np.arange(n)
    rng = np.random.default_rng(seed)
    return np.sort(rng.choice(n, size=max_points, replace=False))


def plot_alpha_delta_v(
    ax: Axes,
    alpha: np.ndarray,
    delta_v: np.ndarray,
) -> None:
    if len(alpha) == 0:
        ax.text(
            0.5,
            0.5,
            "no feasible points",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
        ax.set_title("Feasible: departure Δv vs α")
        return
    ax.scatter(
        alpha,
        delta_v,
        c="crimson",
        s=16,
        alpha=0.75,
        edgecolors="darkred",
        linewidths=0.3,
        rasterized=True,
    )
    ax.set_xlabel("α")
    ax.set_ylabel("Δv (departure, ‖Δv‖)")
    ax.set_title("Feasible solutions: departure Δv vs α")
    ax.grid(True, alpha=0.3)


def main() -> None:
    parser = argparse.ArgumentParser(description="绘制 grid_search 的 α–Δv 散点图（search_results_*.json）")
    parser.add_argument(
        "--save",
        type=str,
        default=None,
        help="保存 PNG 路径；不传则弹窗显示",
    )
    parser.add_argument(
        "--max-points",
        type=int,
        default=50000,
        help="散点最多绘制的可行点数（过多时随机子采样）",
    )
    parser.add_argument("--seed", type=int, default=0, help="子采样随机种子")
    parser.add_argument("--dpi", type=int, default=150)
    args = parser.parse_args()

    path = Path(RESULTS_JSON).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    print(f"读取: {path}")

    rows = load_search_results(path)
    alpha_all, dv_all = feasible_alpha_and_departure_dv(rows)
    n_feas = len(alpha_all)
    idx = subsample_indices(n_feas, args.max_points, args.seed)
    alpha = alpha_all[idx]
    dv = dv_all[idx]

    fig, ax = plt.subplots(figsize=(7, 5))
    plot_alpha_delta_v(ax, alpha, dv)
    fig.suptitle(
        f"N={len(rows)} rows, {n_feas} feasible, {len(idx)} points drawn",
        fontsize=11,
        y=1.02,
    )
    fig.tight_layout()

    if args.save:
        png = Path(args.save).expanduser().resolve()
        if png.suffix.lower() != ".png":
            png = png.with_suffix(".png")
        png.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(png, dpi=args.dpi, bbox_inches="tight")
        print(f"Saved: {png}")
    else:
        plt.show()
    plt.close(fig)


if __name__ == "__main__":
    main()
