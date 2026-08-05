"""参数定义与解析。"""

from __future__ import annotations

import argparse


def build_argparser(description: str) -> argparse.ArgumentParser:
    """创建统一的轨道族绘图参数解析器。"""
    parser = argparse.ArgumentParser(
        description=description, formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--json-file",
        type=str,
        default=None,
        help=(
            "轨道族 JSON 文件路径。支持两种格式：\n"
            "1. 单文件：直接传入文件路径，如 'output/halo/family.json'\n"
            '2. 多文件：传入 JSON 字符串数组，如 \'[{"path": "a.json", '
            '"start": 0, "end": 10, "step": 1}]\''
        ),
    )
    parser.add_argument(
        "--start", type=int, default=-1, help="起始轨道索引，-1 表示从第一条（仅单文件模式有效）"
    )
    parser.add_argument(
        "--end",
        type=int,
        default=-1,
        help="结束轨道索引（含），-1 表示到最后一条（仅单文件模式有效）",
    )
    parser.add_argument(
        "--plot-global-2d",
        "--view-2d",
        dest="plot_global_2d",
        action="store_true",
        help="绘制全局 2D 视图",
    )
    parser.add_argument(
        "--plot-global-3d",
        "--view-3d",
        dest="plot_global_3d",
        action="store_true",
        help="绘制全局 3D 视图",
    )
    parser.add_argument(
        "--plot-jacobi-stability",
        "--jacobi-period-stability",
        dest="plot_jacobi_stability",
        action="store_true",
        help="绘制 Jacobi 常数与周期、稳定性的关系曲线",
    )
    parser.add_argument(
        "--plot-center",
        type=str,
        default="moon",
        choices=["moon", "earth", "emb"],
        help="3D 视图的绘图中心（仅 DRO 有效）",
    )
    parser.add_argument("--plot-elev", type=float, default=20.0, help="3D 视图仰角（度）")
    parser.add_argument("--plot-azim", type=float, default=-60.0, help="3D 视图方位角（度）")
    parser.add_argument(
        "--step", type=int, default=1, help="绘制轨道的间隔步长，1 表示绘制全部（仅单文件模式有效）"
    )
    parser.add_argument("--no-show", action="store_true", help="只保存图片，不弹窗显示")
    return parser


def resolve_plot_range(start: int, end: int, n_orbits: int) -> tuple[int, int]:
    """解析 --start/--end 参数，返回 (plot_start, plot_end) 索引。"""
    last = n_orbits - 1
    s = min(start, last) if start >= 0 else 0
    e = min(end, last) if end >= 0 else last
    return (s, max(s, e))
