"""
可视化 grid_search 输出的 search_results.json

与论文搜索阶段对应：在 (出发点时间, α) 平面上看覆盖与最小距离；
转移时间 vs 最小距离散点（优化前代理图）。

用法:
    python plot_search_results.py
    python plot_search_results.py --input output/transfer/search_results.json --save output/transfer/figures/search
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np

project_root = Path(__file__).resolve().parent.parent.parent


def _f(x) -> float:
    if x is None:
        return np.nan
    return float(x)


def load_search_results(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_arrays(rows: list[dict]) -> dict[str, np.ndarray]:
    n = len(rows)
    departure_time = np.empty(n, dtype=np.float64)
    alpha = np.empty(n, dtype=np.float64)
    transfer_time = np.full(n, np.nan)
    min_distance = np.full(n, np.nan)
    local_min_dist = np.full(n, np.nan)
    is_feasible = np.zeros(n, dtype=bool)
    status = np.empty(n, dtype=object)

    for i, r in enumerate(rows):
        departure_time[i] = _f(r.get("departure_time"))
        alpha[i] = _f(r.get("alpha"))
        tt = r.get("transfer_time")
        md = r.get("min_distance")
        lmd = r.get("local_minimum_distance")
        if tt is not None:
            transfer_time[i] = float(tt)
        if md is not None:
            min_distance[i] = float(md)
        if lmd is not None:
            local_min_dist[i] = float(lmd)
        is_feasible[i] = bool(r.get("is_feasible", False))
        status[i] = r.get("status") or "unknown"

    return {
        "departure_time": departure_time,
        "alpha": alpha,
        "transfer_time": transfer_time,
        "min_distance": min_distance,
        "local_minimum_distance": local_min_dist,
        "is_feasible": is_feasible,
        "status": status,
    }


def subsample_indices(n: int, max_points: int | None, seed: int) -> np.ndarray:
    if max_points is None or n <= max_points:
        return np.arange(n)
    rng = np.random.default_rng(seed)
    return np.sort(rng.choice(n, size=max_points, replace=False))


def plot_departure_alpha(
    ax: plt.Axes,
    dep: np.ndarray,
    alpha: np.ndarray,
    min_distance: np.ndarray,
    feasible: np.ndarray,
    subsample: np.ndarray,
) -> None:
    dep_s = dep[subsample]
    alpha_s = alpha[subsample]
    md_s = min_distance[subsample]
    fe_s = feasible[subsample]

    ok = np.isfinite(md_s) & (md_s >= 0)
    bad = ~ok

    if np.any(bad):
        ax.scatter(
            dep_s[bad],
            alpha_s[bad],
            c="0.75",
            s=4,
            alpha=0.35,
            label="no min_distance",
            rasterized=True,
        )
    if np.any(ok):
        sc = ax.scatter(
            dep_s[ok],
            alpha_s[ok],
            c=np.clip(md_s[ok], 1e-12, None),
            s=8,
            cmap="viridis",
            norm=mcolors.LogNorm(),
            alpha=0.85,
            rasterized=True,
        )
        plt.colorbar(sc, ax=ax, label="min_distance (DU, log)")
    if np.any(fe_s):
        ax.scatter(
            dep_s[fe_s],
            alpha_s[fe_s],
            facecolors="none",
            edgecolors="crimson",
            s=22,
            linewidths=0.6,
            label="is_feasible",
            rasterized=True,
        )

    ax.set_xlabel("departure_time (TU)")
    ax.set_ylabel("alpha")
    ax.set_title("Search map: departure time vs alpha (color = min distance to RO)")
    ax.grid(True, alpha=0.3)


def plot_transfer_vs_min_dist(
    ax: plt.Axes,
    transfer_time: np.ndarray,
    min_distance: np.ndarray,
    feasible: np.ndarray,
    subsample: np.ndarray,
) -> None:
    tt = transfer_time[subsample]
    md = min_distance[subsample]
    fe = feasible[subsample]
    valid = np.isfinite(tt) & np.isfinite(md) & (md >= 0)
    if not np.any(valid):
        ax.text(
            0.5,
            0.5,
            "no valid transfer_time / min_distance",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
        return

    tt_v = tt[valid]
    md_v = md[valid]
    fe_v = fe[valid]
    # log scale: avoid exact zeros
    md_plot = np.maximum(md_v, 1e-18)

    ax.scatter(
        tt_v[~fe_v],
        md_plot[~fe_v],
        c="0.45",
        s=10,
        alpha=0.4,
        label="other",
        rasterized=True,
    )
    if np.any(fe_v):
        ax.scatter(
            tt_v[fe_v],
            md_plot[fe_v],
            c="darkorange",
            s=18,
            alpha=0.9,
            label="is_feasible",
            rasterized=True,
        )

    ax.set_yscale("log")
    ax.set_xlabel("transfer_time (TU)")
    ax.set_ylabel("min_distance (DU)")
    ax.set_title("Transfer time vs min distance (proxy; not paper Delta-v)")
    ax.grid(True, alpha=0.3, which="both")
    ax.legend(loc="best", fontsize=8)


def plot_status_counts(ax: plt.Axes, status: np.ndarray) -> None:
    """Full-sample counts (subsample would distort proportions)."""
    st = status
    labels, counts = np.unique(st, return_counts=True)
    order = np.argsort(-counts)
    labels, counts = labels[order], counts[order]
    ax.barh(np.arange(len(labels)), counts, color="steelblue", alpha=0.85)
    ax.set_yticks(np.arange(len(labels)))
    ax.set_yticklabels([str(x) for x in labels], fontsize=8)
    ax.set_xlabel("count")
    ax.set_title("status histogram")
    ax.grid(True, axis="x", alpha=0.3)


def main() -> None:
    parser = argparse.ArgumentParser(description="绘制 grid_search 的 search_results.json")
    parser.add_argument(
        "--input",
        type=Path,
        default=project_root / "output/transfer/search_results.json",
        help="search_results.json 路径",
    )
    parser.add_argument(
        "--save",
        type=str,
        default=None,
        help="保存图前缀（将生成 *_summary.png），不传则弹窗显示",
    )
    parser.add_argument(
        "--max-points",
        type=int,
        default=50000,
        help="散点最多绘制的点数（大文件随机子采样，避免过慢）",
    )
    parser.add_argument("--seed", type=int, default=0, help="子采样随机种子")
    parser.add_argument("--dpi", type=int, default=150)
    args = parser.parse_args()

    path = args.input
    if not path.is_file():
        raise FileNotFoundError(path)

    rows = load_search_results(path)
    ar = build_arrays(rows)
    n = len(rows)
    idx = subsample_indices(n, args.max_points, args.seed)

    fig = plt.figure(figsize=(12, 10))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.15, 1.0], hspace=0.28, wspace=0.28)

    ax1 = fig.add_subplot(gs[0, :])
    plot_departure_alpha(
        ax1,
        ar["departure_time"],
        ar["alpha"],
        ar["min_distance"],
        ar["is_feasible"],
        idx,
    )
    ax1.legend(loc="upper right", fontsize=8)

    ax2 = fig.add_subplot(gs[1, 0])
    plot_transfer_vs_min_dist(
        ax2,
        ar["transfer_time"],
        ar["min_distance"],
        ar["is_feasible"],
        idx,
    )

    ax3 = fig.add_subplot(gs[1, 1])
    plot_status_counts(ax3, ar["status"])

    fig.suptitle(f"Grid search summary (N={n}, points drawn={len(idx)})", fontsize=12, y=0.98)

    if args.save:
        base = Path(args.save).resolve()
        if base.suffix.lower() == ".png":
            png = base
        else:
            png = base.with_name(base.name + "_summary.png")
        png.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(png, dpi=args.dpi, bbox_inches="tight")
        print(f"Saved: {png}")
    else:
        plt.show()
    plt.close(fig)


if __name__ == "__main__":
    main()
