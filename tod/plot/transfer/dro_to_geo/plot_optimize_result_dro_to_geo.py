"""plot_optimize_result_dro_to_geo 可视化脚本。

本模块读取轨道、转移或星历修正 JSON 结果，并生成用于检查几何形态、稳定性或优化质量的图形。输入文件通常来自 output/ 下的生成、搜索或优化结果；输出为 Matplotlib 窗口或保存图片。

运行示例:
    .. code-block:: bash

       uv run python -m tod.plot.transfer.dro_to_geo.plot_optimize_result_dro_to_geo --help
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
from tod.cli.input_file import (
    InputFileRequest,
    InputResolutionError,
    resolve_input_file,
)

project_root = find_project_root(Path(__file__))

try:
    matplotlib.use("TkAgg")
except ImportError:
    pass
import matplotlib.pyplot as plt  # noqa: E402

# 配置 matplotlib 以正确显示 CJK 字符（beamer 中消除方块字）
from tod.plot.config import apply_standard_plot_config  # noqa: E402

apply_standard_plot_config()

logger = logging.getLogger(__name__)


def load_optimization_results(path: Path) -> dict:
    """读取转移优化结果 JSON 文件。
    
    Args:
        path: 调用方传入的参数值。
    
    Returns:
        函数执行结果。
    """
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _latest_optimization_json() -> Path | None:
    transfer_dir = project_root / "output/transfer"
    candidates = sorted(transfer_dir.glob("optimization_dro_geo_*.json"))
    return candidates[-1] if candidates else None


def _resolve_opt_input(args) -> Path:
    """按 issue #183 契约解析 optimization_dro_geo_*.json。"""
    try:
        return resolve_input_file(
            InputFileRequest(
                explicit_path=Path(args.file) if args.file else None,
                auto_latest=bool(args.auto_latest),
                search_root=project_root / "output/transfer",
                pattern="optimization_dro_geo_*.json",
                flag="--file",
                auto_latest_flag="--auto-latest",
            )
        )
    except InputResolutionError as exc:
        parser = argparse.ArgumentParser(
            prog="plot_optimize_result_dro_to_geo",
            description="可视化 DRO→GEO 优化结果",
        )
        if exc.candidates or exc.remaining:
            parser.error(
                f"{exc}\n候选 (mtime new→old):\n{exc.format_candidates()}"
            )
        parser.error(str(exc))


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
    """执行脚本主流程。
    
    Returns:
        None。
    
    Raises:
        Exception: 当输入数据、文件或数值流程不满足脚本要求时抛出。
    """
    parser = argparse.ArgumentParser(description="可视化 DRO→GEO 优化结果", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--file", type=str, default=None, help="优化结果 JSON 路径")
    parser.add_argument("--auto-latest", action="store_true", help="显式 opt-in：按 mtime 选最新 optimization_dro_geo_*.json")
    parser.add_argument("--orbit", action="store_true", help="绘制转移轨道 3D 示意图")
    parser.add_argument("--time-dv", action="store_true", help="转移时间 vs Δv 散点图")
    parser.add_argument("--idx", type=str, default="best", help="选择索引")
    parser.add_argument("--save", type=str, default=None, help="保存图片路径")
    parser.add_argument("--max-points", type=int, default=500, help="最大绘制轨道数")
    parser.add_argument("--seed", type=int, default=0, help="随机种子")
    parser.add_argument("--dpi", type=int, default=150, help="图片 DPI")
    parser.add_argument("--no-show", action="store_true", help="生成图像后不弹窗显示（GUI 后台运行）")
    args = parser.parse_args()

    opt_path = _resolve_opt_input(args)
    if not opt_path.is_file():
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


# ------------------------------------------------------------------
# GUI 注册
# ------------------------------------------------------------------

from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='transfer',
    name='plot_optimize_result_dro_to_geo',
    description='绘制优化结果',
    script_path='tod/plot/transfer/dro_to_geo/plot_optimize_result_dro_to_geo.py',
    output_dir='output/transfer',
    group_label='DRO→GEO',
    cli_params=[
        CliParam('--file', '优化结果文件', 'str', '', help='优化结果 JSON 文件路径。', file_category='transfer'),
        CliParam('--auto-latest', '按 mtime 选最新（显式 opt-in）', 'bool', '', help='显式 opt-in：按 mtime 选最新 optimization_dro_geo_*.json；与 --file 互斥。', advanced=True),
        CliParam('--orbit', '转移轨道图（3D）', 'bool', '', help='重新积分并绘制转移轨道 3D 示意图，勾选后启用。'),
        CliParam('--time-dv', '转移时间-Δv 散点图', 'bool', '', help='转移时间 vs Δv 散点图，勾选后启用。'),
        CliParam('--idx', '选中轨道（--orbit 模式）', 'str', 'best', help='整数索引 / best / best:N / random / all，默认 best。'),
        CliParam('--save', '保存图片路径', 'str', '', help='不填则弹窗显示。'),
        CliParam('--max-points', '最大绘制轨道数', 'int', '500', help='--idx all 时最多绘制条数，默认 500。', advanced=True),
        CliParam('--seed', '随机种子', 'int', '0', help='子采样随机种子，默认 0。', advanced=True),
        CliParam('--dpi', '图片 DPI', 'int', '150', help='保存图片的分辨率，默认 150。', advanced=True),
    ],
)
