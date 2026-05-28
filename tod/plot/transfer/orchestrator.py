"""transfer 画图编排器。

为 transfer 画图脚本提供共享的 argparse、配置、保存/显示和
数据加载逻辑。参考 ``FamilyPlotOrchestrator`` 的模式，使每条
transfer 管线的画图脚本变为 ~40 行的配置 + orchestrator 包装。

本模块当前仅提供共享基础——迁移在各管线独立的切片中完成。
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import matplotlib
from tod.commons.common import find_project_root
from tod.plot.config import apply_standard_plot_config

logger = logging.getLogger(__name__)

# =============================================================================
# 配置
# =============================================================================


@dataclass
class TransferPlotConfig:
    """Transfer 画图脚本的共享配置。

    Attributes:
        direction: 转移方向标签（如 ``"DRO→GEO"``）。
        default_search_file: 默认搜索结果 JSON 文件名。
        output_subdir: output/ 下的子目录。
        default_max_points: 散点图最多可行点数。
        default_dpi: 输出图片 DPI。
        default_seed: 子采样随机种子。
    """

    direction: str = ""
    default_search_file: str = ""
    output_subdir: str = "transfer"
    default_max_points: int = 50000
    default_dpi: int = 150
    default_seed: int = 0


# =============================================================================
# 共享 argparse
# =============================================================================


def build_transfer_argparser(
    description: str,
    config: TransferPlotConfig,
) -> argparse.ArgumentParser:
    """创建 transfer 画图脚本的统一参数解析器。

    包含所有 transfer 画图脚本共用的标志。各管线可在此基础上
    添加特定参数。

    Args:
        description: 脚本描述文本。
        config: 画图配置。

    Returns:
        预配置的 ArgumentParser。
    """
    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--file", type=str, default=None, help="搜索结果 JSON 路径"
    )
    parser.add_argument(
        "--save", type=str, default=None, help="保存 PNG 路径"
    )
    parser.add_argument(
        "--max-points",
        type=int,
        default=config.default_max_points,
        help="散点最多可行点数",
    )
    parser.add_argument(
        "--seed", type=int, default=config.default_seed, help="子采样随机种子"
    )
    parser.add_argument("--dpi", type=int, default=config.default_dpi)
    parser.add_argument(
        "--no-show", action="store_true", help="生成图像后不弹窗显示"
    )
    return parser


# =============================================================================
# 共享工具
# =============================================================================


def load_and_filter_results(
    path: Path,
    *,
    project_root: Path | None = None,
) -> tuple[list[dict], list[dict]]:
    """加载搜索结果 JSON 并分离可行解。

    Args:
        path: JSON 文件路径。
        project_root: 项目根目录（用于安全校验）。

    Returns:
        (all_rows, feasible_rows) 元组。
    """
    import json

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict) and "results" in data:
        rows = data["results"]
    elif isinstance(data, list):
        rows = data
    else:
        raise ValueError(f"无法识别的搜索结果格式: {type(data)}")

    feasible_rows = [r for r in rows if r.get("is_feasible")]
    logger.info("总行数=%d，可行解=%d", len(rows), len(feasible_rows))
    return rows, feasible_rows


def save_or_show(
    fig: Any,
    args: argparse.Namespace,
    *,
    close: bool = True,
) -> None:
    """保存图片到文件或弹窗显示。

    所有 transfer 画图脚本中此函数实现完全相同。

    Args:
        fig: matplotlib Figure。
        args: 解析后的命令行参数（需有 ``save``、``dpi``、``no_show`` 属性）。
        close: 是否在处理后关闭 figure。
    """
    if getattr(args, "save", None):
        png = Path(args.save).expanduser().resolve()
        if png.suffix.lower() != ".png":
            png = png.with_suffix(".png")
        png.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(png, dpi=getattr(args, "dpi", 150), bbox_inches="tight")
        logger.info("Saved: %s", png)
    elif not getattr(args, "no_show", False):
        import matplotlib.pyplot as plt

        plt.show()
    if close:
        import matplotlib.pyplot as plt

        plt.close(fig)


# =============================================================================
# 调试入口
# =============================================================================


def inject_debug_args(
    argv: list[str],
    defaults: list[str],
    description: str = "使用代码内置调试参数",
) -> None:
    """IDE 调试模式：F5 直跑时注入默认命令行参数。"""
    if len(argv) == 1:
        argv += defaults
        logger.debug(description)


# =============================================================================
# Orchestrator 基类
# =============================================================================


class TransferPlotOrchestrator:
    """Transfer 画图编排器基类。

    子类覆盖 ``run`` 方法实现具体的画图逻辑。基类提供：
    - ``_init_matplotlib()``：设置 TkAgg 后端和标准样式。
    - ``_build_parser()``：创建统一的 argparse。

    用法::

        class DroToGeoOptimizePlot(TransferPlotOrchestrator):
            def run(self, args):
                # pipeline-specific rendering
                ...

        orch = DroToGeoOptimizePlot(config)
        orch.run(args)
    """

    def __init__(self, config: TransferPlotConfig) -> None:
        self.config = config
        self._project_root: Path | None = None

    @property
    def project_root(self) -> Path:
        if self._project_root is None:
            self._project_root = find_project_root(Path(__file__))
        return self._project_root

    def _init_matplotlib(self) -> None:
        """初始化 matplotlib 后端和标准样式。"""
        try:
            matplotlib.use("TkAgg")
        except ImportError:
            pass
        apply_standard_plot_config()

    def _build_parser(self, description: str) -> argparse.ArgumentParser:
        """创建标准 transfer 画图 argparse。"""
        return build_transfer_argparser(description, self.config)

    def run(self, args: argparse.Namespace) -> None:
        """执行画图（子类必须覆盖）。"""
        raise NotImplementedError("subclass must implement run()")
