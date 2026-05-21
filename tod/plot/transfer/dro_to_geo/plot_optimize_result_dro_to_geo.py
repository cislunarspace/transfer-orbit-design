"""
DRO → GEO 优化结果可视化

可视化 optimize_dro_to_geo.py 的输出结果。
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )

import matplotlib  # noqa: E402
import numpy as np
from tod.commons.constants import TU, VU
from tod.commons.common import find_project_root

project_root = find_project_root(Path(__file__))

try:
    matplotlib.use("TkAgg")
except ImportError:
    pass
import matplotlib.pyplot as plt  # noqa: E402

logger = logging.getLogger(__name__)


def load_optimization_results(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _latest_optimization_json() -> Path | None:
    transfer_dir = project_root / "output/transfer"
    candidates = sorted(transfer_dir.glob("optimization_dro_geo_*.json"))
    return candidates[-1] if candidates else None


def _successful_records(results: list[dict]) -> list[dict]:
    return [r for r in results if r.get("nlp", {}).get("success", False)]


def _record_objective(record: dict) -> float:
    return float(record.get("nlp", {}).get("objective_value", float("inf")))


def _select_records(records: list[dict], idx_arg: str, seed: int, max_points: int) -> list[dict]:
    if idx_arg == "all":
        if len(records) > max_points:
            rng = np.random.default_rng(seed)
            indices = sorted(rng.choice(len(records), size=max_points, replace=False).tolist())
            return [records[i] for i in indices]
        return records
    if idx_arg.startswith("best"):
        parts = idx_arg.split(":")
        top_n = int(parts[1]) if len(parts) == 2 else 1
        return sorted(records, key=_record_objective)[:top_n]
    if idx_arg == "random":
        rng = np.random.default_rng(seed)
        return [records[int(rng.integers(0, len(records)))]] if records else []
    idx = int(idx_arg)
    return [records[idx]] if 0 <= idx < len(records) else []


def _plot_time_dv(records: list[dict], ax) -> None:
    if not records:
        ax.text(0.5, 0.5, "无成功结果", ha="center", va="center", transform=ax.transAxes)
        return
    tts = [r.get("nlp", {}).get("transfer_time", 0) * TU for r in records]
    dvs = [r.get("nlp", {}).get("objective_value", 0) * VU / 1000 for r in records]
    ax.scatter(tts, dvs, s=10, alpha=0.6)
    ax.set_xlabel("转移时间 (天)")
    ax.set_ylabel("总 Δv (km/s)")
    ax.set_title("DRO→GEO: 转移时间 vs Δv")
    ax.grid(True, alpha=0.3)


def _plot_orbit_selection(records: list[dict], ax) -> None:
    if not records:
        ax.text2D(0.5, 0.5, "无选中结果", ha="center", va="center", transform=ax.transAxes)
        return
    positions = [np.asarray(r.get("departure_state", [0, 0, 0]), dtype=float)[:3] for r in records]
    dvs = [r.get("nlp", {}).get("objective_value", 0) * VU / 1000 for r in records]
    pts = np.asarray(positions)
    scatter = ax.scatter(pts[:, 0], pts[:, 1], pts[:, 2], c=dvs, cmap="plasma", s=35)
    plt.colorbar(scatter, ax=ax, label="总 Δv (km/s)")
    ax.set_xlabel("x (DU)")
    ax.set_ylabel("y (DU)")
    ax.set_zlabel("z (DU)")
    ax.set_title(f"DRO→GEO: {len(records)} 条选中优化结果出发点")
    ax.grid(True, alpha=0.3)


def main() -> None:
    parser = argparse.ArgumentParser(description="可视化 DRO→GEO 优化结果")
    parser.add_argument("--file", type=str, default=None, help="优化结果 JSON 路径")
    parser.add_argument("--orbit", action="store_true", help="绘制转移轨道 3D 示意图")
    parser.add_argument("--time-dv", action="store_true", help="转移时间 vs Δv 散点图")
    parser.add_argument("--idx", type=str, default="best", help="选择索引")
    parser.add_argument("--save", type=str, default=None, help="保存图片路径")
    parser.add_argument("--max-points", type=int, default=500, help="最大绘制轨道数")
    parser.add_argument("--seed", type=int, default=0, help="随机种子")
    parser.add_argument("--dpi", type=int, default=150, help="图片 DPI")
    parser.add_argument("--no-show", action="store_true", help="生成图像后不弹窗显示（GUI 后台运行）")
    args = parser.parse_args()

    opt_path = Path(args.file).expanduser().resolve() if args.file else _latest_optimization_json()
    if opt_path is None or not opt_path.is_file():
        raise FileNotFoundError("未找到优化结果 JSON")

    logger.info(f"读取: {opt_path}")
    data = load_optimization_results(opt_path)
    results = data.get("results", [])
    success = _successful_records(results)
    logger.info(f"结果总数: {len(results)}, 成功: {len(success)}")

    if args.orbit:
        selected = _select_records(success, args.idx, args.seed, args.max_points)
        fig = plt.figure(figsize=(10, 7))
        ax = fig.add_subplot(111, projection="3d")
        _plot_orbit_selection(selected, ax)
    else:
        fig, ax = plt.subplots(figsize=(10, 6))
        _plot_time_dv(success, ax)
    fig.tight_layout()

    if args.save:
        Path(args.save).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(args.save, dpi=args.dpi, bbox_inches="tight")
        logger.info(f"Saved: {args.save}")
    elif not args.no_show:
        plt.show()
    plt.close(fig)


if __name__ == "__main__":
    main()
