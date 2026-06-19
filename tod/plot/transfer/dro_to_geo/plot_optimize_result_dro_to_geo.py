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
from e2m2e.transfer import load_orbit_from_json
from tod.generates.artifacts import find_latest_single_dro
from tod.plot.transfer.common import (
    reintegrate_transfer,
    plot_single_transfer_orbit_2d,
    plot_celestial_bodies,
    set_equal_aspect_3d,
    geo_circle_points,
    build_transfer_dynamics,
)

project_root = find_project_root(Path(__file__))

try:
    matplotlib.use("TkAgg")
except ImportError:
    pass
import matplotlib.pyplot as plt  # noqa: E402

# 配置 matplotlib 以正确显示 CJK 字符（beamer 中消除方块字）
from tod.plot.config import apply_standard_plot_config  # noqa: E402

PLOT_CONFIG = apply_standard_plot_config()

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


def _resolve_dro_input(args) -> Path:
    """DRO 文件解析优先级: CLI --dro-file > --auto-latest-dro > env DRO_FILE > find_latest_single_dro。"""
    if args.dro_file:
        return Path(args.dro_file).expanduser().resolve()
    if args.auto_latest_dro:
        try:
            return find_latest_single_dro(project_root)
        except FileNotFoundError as exc:
            raise FileNotFoundError(str(exc)) from exc
    # 默认行为：尝试自动发现最新单轨道 DRO 文件
    try:
        return find_latest_single_dro(project_root)
    except FileNotFoundError:
        parser = argparse.ArgumentParser(
            prog="plot_optimize_result_dro_to_geo",
            description="可视化 DRO→GEO 优化结果",
        )
        parser.error("未找到 DRO 轨道文件，请用 --dro-file 指定")


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


def _resolve_figsize_cm(arg: str | None) -> tuple[float, float] | None:
    """将 '--figsize' 参数（厘米）转为 matplotlib 英寸尺寸。"""
    if not arg:
        return None
    parts = [float(x) for x in arg.replace("，", ",").split(",")]
    if len(parts) == 1:
        parts = [parts[0], parts[0]]
    if len(parts) != 2:
        raise ValueError(f"--figsize 需 '宽,高'（厘米），收到 {arg!r}")
    w, h = parts
    return (w / 2.54, h / 2.54)


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


def _plot_orbit_2d(
    departure_orbit,
    transfer_states: np.ndarray,
    departure_state: np.ndarray,
    dv_departure: float,
    dv_insertion: float,
    transfer_time: float,
    alpha: float,
    system,
    save_path: str | None = None,
    dpi: int = 300,
    figsize: tuple[float, float] | None = None,
    title: str | None = None,
    caption: str | None = None,
) -> None:
    """在 XY 平面绘制单条转移轨道（论文版图）。"""
    fig_size = figsize or (8.5 / 2.54, 8.5 / 2.54)
    fig, ax = plt.subplots(figsize=fig_size)
    plot_single_transfer_orbit_2d(
        departure_orbit=departure_orbit,
        transfer_states=transfer_states,
        departure_state=departure_state,
        dv_departure=dv_departure,
        dv_insertion=dv_insertion,
        transfer_time=transfer_time,
        alpha=alpha,
        system=system,
        config=PLOT_CONFIG,
        fig=fig,
        ax=ax,
        title=title,
    )
    fig.tight_layout()
    if caption:
        fig.text(0.5, -0.02, caption, ha="center", va="top",
                 fontsize=PLOT_CONFIG.tick)
    if save_path:
        png = Path(save_path)
        png.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(png, dpi=dpi, bbox_inches="tight")
        logger.info("Saved: %s", png)
    else:
        plt.show()
    plt.close(fig)


def _prepare_transfer_data(args, rec: dict):
    """从优化结果记录中提取转移参数，加载 DRO 并重积分转移轨道。

    Returns:
        (dep_state, alpha, transfer_time, dv1, dv2, dro_orbit, system, dynamics, transfer_states)
    """
    nlp = rec.get("nlp", {})
    alpha = float(nlp.get("alpha", rec.get("alpha", 0)))
    transfer_time = float(nlp.get("transfer_time", rec.get("transfer_time", 0)))
    dv1 = float(nlp.get("delta_v1", rec.get("dv_departure", 0)))
    dv2 = float(nlp.get("delta_v2", 0))
    dep_state = np.asarray(rec["departure_state"], dtype=np.float64)

    dro_path = _resolve_dro_input(args)
    dro_orbit = load_orbit_from_json(str(dro_path))

    system, dynamics = build_transfer_dynamics()
    transfer_states, _ = reintegrate_transfer(dynamics, dep_state, alpha, transfer_time)

    return dep_state, alpha, transfer_time, dv1, dv2, dro_orbit, system, dynamics, transfer_states


def _save_or_show(fig, args, dpi: int | None = None) -> None:
    """保存或显示图片。"""
    if args.save:
        png = Path(args.save).expanduser().resolve()
        png.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(png, dpi=dpi or args.dpi, bbox_inches="tight")
        logger.info("Saved: %s", png)
    elif not args.no_show:
        plt.show()
    plt.close(fig)


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
    parser.add_argument("--orbit-2d", action="store_true", help="绘制 XY 平面转移轨道图（论文用）")
    parser.add_argument("--paper", action="store_true", help="论文模式：DPI=300、单栏尺寸、无标题")
    parser.add_argument("--dro-file", type=str, default=None, help="DRO 轨道 JSON 路径")
    parser.add_argument("--auto-latest-dro", action="store_true", help="显式 opt-in：按 mtime 选最新 dro_*.json")
    parser.add_argument("--figsize", type=str, default=None, help="图尺寸（厘米），格式 '宽,高'，如 '8.5,8.5'")
    parser.add_argument("--no-title", action="store_true", help="不显示图标题（论文配图用）")
    parser.add_argument("--caption", type=str, default=None, help="图注文字，置于图下方")
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
        dpi = 300 if args.paper else args.dpi
        figsize_cm = _resolve_figsize_cm(args.figsize)
        figsize = figsize_cm or (
            (12 / 2.54, 8 / 2.54) if args.paper else (10, 7)
        )

        if len(selected) == 1:
            rec = selected[0]
            (dep_state, alpha, transfer_time, dv1, dv2,
             dro_orbit, system, dynamics, transfer_states) = _prepare_transfer_data(args, rec)

            fig = plt.figure(figsize=figsize)
            ax = fig.add_subplot(111, projection="3d")

            gx, gy = geo_circle_points()
            ax.plot(gx, gy, np.zeros_like(gx), color="gray", ls="--",
                    lw=0.8, label="GEO")
            ax.plot(dro_orbit.states[:, 0], dro_orbit.states[:, 1],
                    dro_orbit.states[:, 2], color="royalblue", lw=0.8,
                    label="DRO")
            ax.plot(transfer_states[:, 0], transfer_states[:, 1],
                    transfer_states[:, 2], color="crimson", lw=1.2,
                    label="转移轨道")
            ax.scatter(*dep_state[:3], color="green", s=40, zorder=5,
                       label="出发点")
            ax.scatter(*transfer_states[-1, :3], color="orange", s=40,
                       marker="s", zorder=5, label="到达点")
            plot_celestial_bodies(ax, system, PLOT_CONFIG)

            ax.set_xlabel("x (DU)")
            ax.set_ylabel("y (DU)")
            ax.set_zlabel("z (DU)")

            if not (args.paper or args.no_title):
                dv1_km = dv1 * VU / 1000
                dv2_km = dv2 * VU / 1000
                title_str = (
                    f"DRO→GEO  α={alpha:.4f}  "
                    f"T={transfer_time:.2f} TU "
                    f"({transfer_time * TU:.1f}天)\n"
                    f"Δv₁={dv1_km:.4f} km/s  "
                    f"Δv₂={dv2_km:.4f} km/s  "
                    f"Δv总={dv1_km + dv2_km:.4f} km/s"
                )
                ax.set_title(title_str, fontsize=PLOT_CONFIG.title)

            ax.legend(fontsize=PLOT_CONFIG.legend, loc="upper left")
            all_pts = np.concatenate(
                [transfer_states[:, :3], dro_orbit.states[:, :3]]
            )
            set_equal_aspect_3d(ax, all_pts)
            fig.tight_layout()

            if args.caption:
                fig.text(0.5, -0.02, args.caption, ha="center", va="top",
                         fontsize=PLOT_CONFIG.tick)
        else:
            fig = plt.figure(figsize=figsize)
            ax = fig.add_subplot(111, projection="3d")
            _plot_orbit_selection(selected, ax)

        _save_or_show(fig, args, dpi)
    elif args.orbit_2d:
        selected = _select_records(success, args.idx, args.seed, args.max_points)
        if not selected:
            logger.warning("无选中记录，跳过 2D 绘图")
            return

        rec = selected[0]
        (dep_state, alpha, transfer_time, dv1, dv2,
         dro_orbit, system, dynamics, transfer_states) = _prepare_transfer_data(args, rec)

        figsize_cm = _resolve_figsize_cm(args.figsize)
        figsize = figsize_cm or (
            (12 / 2.54, 8 / 2.54) if args.paper else None
        )
        title = "" if (args.paper or args.no_title) else None
        dpi = 300 if args.paper else args.dpi

        _plot_orbit_2d(
            departure_orbit=dro_orbit,
            transfer_states=transfer_states,
            departure_state=dep_state,
            dv_departure=dv1,
            dv_insertion=dv2,
            transfer_time=transfer_time,
            alpha=alpha,
            system=system,
            save_path=args.save,
            dpi=dpi,
            figsize=figsize,
            title=title,
            caption=args.caption,
        )
    else:
        fig, ax = plt.subplots(figsize=(10, 6))
        _plot_time_dv(success, ax)
        fig.tight_layout()

        _save_or_show(fig, args)


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
        CliParam('--orbit-2d', 'XY 平面轨道图', 'bool', '', help='在地月旋转系 XY 平面绘制转移轨道，勾选后启用。'),
        CliParam('--paper', '论文模式', 'bool', '', help='DPI=300、单栏尺寸、无标题。'),
        CliParam('--time-dv', '转移时间-Δv 散点图', 'bool', '', help='转移时间 vs Δv 散点图，勾选后启用。'),
        CliParam('--idx', '选中轨道（--orbit 模式）', 'str', 'best', help='整数索引 / best / best:N / random / all，默认 best。'),
        CliParam('--save', '保存图片路径', 'str', '', help='不填则弹窗显示。'),
        CliParam('--dro-file', 'DRO 文件', 'str', '', help='DRO 轨道 JSON 文件路径。', file_category='dro', name_pattern='dro_[0-9]*.json'),
        CliParam('--auto-latest-dro', '按 mtime 选最新 DRO（显式 opt-in）', 'bool', '', help='显式 opt-in：按 mtime 选最新 dro_*.json。', advanced=True),
        CliParam('--figsize', '图尺寸(厘米)', 'str', '', help="图尺寸，格式 '宽,高'（厘米）。", advanced=True),
        CliParam('--no-title', '隐藏标题', 'bool', '', help='勾选后不显示图标题。', advanced=True),
        CliParam('--caption', '图注', 'str', '', help='图片下方图注文字。', advanced=True),
        CliParam('--max-points', '最大绘制轨道数', 'int', '500', help='--idx all 时最多绘制条数，默认 500。', advanced=True),
        CliParam('--seed', '随机种子', 'int', '0', help='子采样随机种子，默认 0。', advanced=True),
        CliParam('--dpi', '图片 DPI', 'int', '150', help='保存图片的分辨率，默认 150。', advanced=True),
    ],
)
