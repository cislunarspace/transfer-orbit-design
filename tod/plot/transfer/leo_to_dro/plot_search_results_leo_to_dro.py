"""plot_search_results_leo_to_dro 可视化脚本。

本模块读取轨道、转移或星历修正 JSON 结果，并生成用于检查几何形态、稳定性或优化质量的图形。输入文件通常来自 output/ 下的生成、搜索或优化结果；输出为 Matplotlib 窗口或保存图片。

运行示例:
    .. code-block:: bash

       uv run python -m tod.plot.transfer.leo_to_dro.plot_search_results_leo_to_dro --help
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
from tod.cli.input_file import (
    InputFileRequest,
    InputResolutionError,
    resolve_input_file,
)
from tod.commons.constants import TU, VU
from tod.commons.common import find_project_root
from tod.plot.transfer.common import (
    feasible_alpha_and_departure_dv,
    feasible_transfer_time_and_dv,
    select_feasible_indices,
)

project_root = find_project_root(Path(__file__))

try:
    matplotlib.use("TkAgg")
except ImportError:
    pass
import matplotlib.pyplot as plt  # noqa: E402

logger = logging.getLogger(__name__)


def load_search_results(path: Path) -> dict:
    """读取转移搜索结果 JSON 文件。
    
    Args:
        path: 调用方传入的参数值。
    
    Returns:
        函数执行结果。
    """
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _latest_search_json() -> Path | None:
    transfer_dir = project_root / "output/transfer"
    candidates = sorted(transfer_dir.glob("search_leo_dro_*.json"))
    return candidates[-1] if candidates else None


def _resolve_search_input(args) -> Path:
    """按 issue #183 契约解析搜索结果文件。"""
    try:
        return resolve_input_file(
            InputFileRequest(
                explicit_path=Path(args.file) if args.file else None,
                auto_latest=bool(args.auto_latest),
                search_root=project_root / "output/transfer",
                pattern="search_leo_dro_*.json",
                flag="--file",
                auto_latest_flag="--auto-latest",
            )
        )
    except InputResolutionError as exc:
        parser = argparse.ArgumentParser(
            prog="plot_search_results_leo_to_dro",
            description="可视化 LEO→DRO 网格搜索结果",
        )
        if exc.candidates or exc.remaining:
            parser.error(
                f"{exc}\n候选 (mtime new→old):\n{exc.format_candidates()}"
            )
        parser.error(str(exc))


def _selected_feasible(feasible: list[dict], idx_arg: str, seed: int, max_points: int) -> list[dict]:
    indices = select_feasible_indices(feasible, idx_arg, seed=seed, max_indices=max_points)
    return [feasible[i] for i in indices]


def _plot_alpha_dv(feasible: list[dict], ax, max_points: int, seed: int) -> None:
    alphas, dvs = feasible_alpha_and_departure_dv(feasible)
    if len(alphas) == 0:
        ax.text(0.5, 0.5, "无可行解", ha="center", va="center", transform=ax.transAxes)
        return
    idx = (
        np.random.default_rng(seed).choice(len(alphas), size=max_points, replace=False)
        if max_points < len(alphas)
        else np.arange(len(alphas))
    )
    ax.scatter(alphas[idx], dvs[idx] * VU / 1000, s=6, alpha=0.6)
    ax.set_xlabel("α")
    ax.set_ylabel("Δv (km/s)")
    ax.set_title("LEO→DRO: α vs Δv (可行解)")
    ax.grid(True, alpha=0.3)


def _plot_time_dv(feasible: list[dict], ax, max_points: int, seed: int) -> None:
    times, dvs = feasible_transfer_time_and_dv(feasible)
    if len(times) == 0:
        ax.text(0.5, 0.5, "无可行解", ha="center", va="center", transform=ax.transAxes)
        return
    idx = (
        np.random.default_rng(seed).choice(len(times), size=max_points, replace=False)
        if max_points < len(times)
        else np.arange(len(times))
    )
    ax.scatter(times[idx] * TU, dvs[idx] * VU / 1000, s=6, alpha=0.6)
    ax.set_xlabel("转移时间 (天)")
    ax.set_ylabel("Δv (km/s)")
    ax.set_title("LEO→DRO: 转移时间 vs Δv (可行解)")
    ax.grid(True, alpha=0.3)


def _plot_orbit_selection(records: list[dict], ax) -> None:
    if not records:
        ax.text2D(0.5, 0.5, "无选中结果", ha="center", va="center", transform=ax.transAxes)
        return
    positions = [np.asarray(r.get("departure_state", [0, 0, 0]), dtype=float)[:3] for r in records]
    dvs = [float(r.get("dv_departure", 0)) * VU / 1000 for r in records]
    pts = np.asarray(positions)
    scatter = ax.scatter(pts[:, 0], pts[:, 1], pts[:, 2], c=dvs, cmap="viridis", s=35)
    plt.colorbar(scatter, ax=ax, label="出发 Δv (km/s)")
    ax.set_xlabel("x (DU)")
    ax.set_ylabel("y (DU)")
    ax.set_zlabel("z (DU)")
    ax.set_title(f"LEO→DRO: {len(records)} 条选中可行解出发点")
    ax.grid(True, alpha=0.3)


def _interactive_browse(records: list[dict]) -> None:
    selected = sorted(records, key=lambda r: float(r.get("dv_departure", float("inf"))))
    if not selected:
        logger.info("无可行解可浏览")
        return
    logger.info("交互浏览：Enter=下一条, q=退出")
    for i, row in enumerate(selected, start=1):
        logger.info(
            f"[{i}/{len(selected)}] alpha={row.get('alpha')}, "
            f"T={float(row.get('transfer_time', 0)) * TU:.2f} 天, "
            f"dv={float(row.get('dv_departure', 0)) * VU / 1000:.6f} km/s"
        )
        try:
            if input("> ").strip().lower() == "q":
                break
        except (EOFError, KeyboardInterrupt):
            break


def main() -> None:
    """执行脚本主流程。
    
    Returns:
        None。
    
    Raises:
        Exception: 当输入数据、文件或数值流程不满足脚本要求时抛出。
    """
    parser = argparse.ArgumentParser(description="可视化 LEO→DRO 网格搜索结果", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--file", type=str, default=None, help="搜索结果 JSON 路径")
    parser.add_argument("--auto-latest", action="store_true", help="显式 opt-in：按 mtime 选最新搜索结果 JSON")
    parser.add_argument("--orbit", action="store_true", help="绘制转移轨道 3D 示意图")
    parser.add_argument("--time-dv", action="store_true", help="转移时间 vs Δv 散点图")
    parser.add_argument("--interactive", action="store_true", help="交互式逐条浏览")
    parser.add_argument("--idx", type=str, default="best:10", help="选择索引")
    parser.add_argument("--save", type=str, default=None, help="保存图片路径")
    parser.add_argument("--max-points", type=int, default=50000, help="最大散点数")
    parser.add_argument("--seed", type=int, default=0, help="随机种子")
    parser.add_argument("--dpi", type=int, default=150, help="图片 DPI")
    parser.add_argument("--no-show", action="store_true", help="生成图像后不弹窗显示（GUI 后台运行）")
    args = parser.parse_args()

    search_path = _resolve_search_input(args)
    if not search_path.is_file():
        raise FileNotFoundError("未找到 LEO→DRO 搜索结果 JSON")
    logger.info(f"读取: {search_path}")
    data = load_search_results(search_path)
    results = data.get("results", [])
    feasible = [r for r in results if r.get("is_feasible")]
    logger.info(f"总候选解: {len(results)}, 可行解: {len(feasible)}")

    if not feasible:
        logger.warning("无可行解")
        return

    if args.interactive:
        _interactive_browse(feasible)
        return

    if args.orbit:
        selected = _selected_feasible(feasible, args.idx, args.seed, args.max_points)
        fig = plt.figure(figsize=(10, 7))
        ax = fig.add_subplot(111, projection="3d")
        _plot_orbit_selection(selected, ax)
    else:
        fig, ax = plt.subplots(figsize=(10, 6))
        if args.time_dv:
            _plot_time_dv(feasible, ax, args.max_points, args.seed)
        else:
            _plot_alpha_dv(feasible, ax, args.max_points, args.seed)
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


# ------------------------------------------------------------------
# GUI 注册
# ------------------------------------------------------------------

from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='transfer',
    name='plot_search_results_leo_to_dro',
    description='绘制搜索结果',
    script_path='tod/plot/transfer/leo_to_dro/plot_search_results_leo_to_dro.py',
    output_dir='output/transfer',
    group_label='LEO→DRO',
    cli_params=[
        CliParam('--file', '搜索结果文件', 'str', '', help='搜索结果 JSON 文件路径。', file_category='transfer'),
        CliParam('--auto-latest', '自动选最新结果', 'bool', '', help='选最新的 search_leo_dro_*.json；与 --file 互斥。', advanced=True),
        CliParam('--orbit', '转移轨道图（3D）', 'bool', '', help='重新积分并绘制转移轨道 3D 示意图。'),
        CliParam('--time-dv', '转移时间-Δv 散点图', 'bool', '', help='绘制转移时间 vs Δv 散点图。'),
        CliParam('--interactive', '逐条浏览模式', 'bool', '', help='按转移时间排序逐条浏览。'),
        CliParam('--idx', '选中轨道（--orbit 模式）', 'str', 'best:10', help='all、best、best:N、random 或序号。'),
        CliParam('--save', '保存图片路径', 'str', '', help='不填则弹窗显示。'),
        CliParam('--max-points', '最大散点数', 'int', '50000', help='散点子采样上限，避免过多点导致卡顿。', advanced=True),
        CliParam('--seed', '随机种子', 'int', '0', help='子采样随机种子。', advanced=True),
        CliParam('--dpi', '图片 DPI', 'int', '150', help='保存图片的分辨率。', advanced=True),
    ],
)
