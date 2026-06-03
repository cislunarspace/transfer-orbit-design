"""family_plot_orchestrator 可视化脚本。

本模块读取轨道、转移或星历修正 JSON 结果，并生成用于检查几何形态、稳定性或优化质量的图形。输入文件通常来自 output/ 下的生成、搜索或优化结果；输出为 Matplotlib 窗口或保存图片。

运行示例:
    .. code-block:: bash

       uv run python -m tod.plot.family_plot_orchestrator --help

多文件模式示例:

    .. code-block:: bash

       uv run python -m tod.plot.plot_orbits \\
         --json-file '[{"path": "a.json", "start": 0, "end": 10, "step": 1}, {"path": "b.json", "start": 5, "end": -1, "step": 2}]' \\
         --view-2d
"""


from __future__ import annotations

import argparse
import json as _json
import logging
import warnings
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

import matplotlib
try:
    matplotlib.use("TkAgg")
except (ImportError, ValueError):
    pass  # Backend unavailable or already finalized

from e2m2e.algorithms.stability import StabilityAnalysis
from e2m2e.core import CR3BP_System, Orbit, OrbitFamily
from e2m2e.visualization import FamilyPlotter

from tod.commons.constants import MU
from tod.commons.common import find_project_root
from tod.plot.config import apply_standard_plot_config

logger = logging.getLogger(__name__)


def build_argparser(description: str) -> argparse.ArgumentParser:
    """创建统一的轨道族绘图参数解析器。"""
    parser = argparse.ArgumentParser(description=description, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        "--json-file",
        type=str,
        default=None,
        help="轨道族 JSON 文件路径。支持两种格式：\n"
        "1. 单文件：直接传入文件路径，如 'output/halo/family.json'\n"
        "2. 多文件：传入 JSON 字符串数组，如 '[{\"path\": \"a.json\", \"start\": 0, \"end\": 10, \"step\": 1}]'",
    )
    parser.add_argument("--start", type=int, default=-1, help="起始轨道索引，-1 表示从第一条（仅单文件模式有效）")
    parser.add_argument("--end", type=int, default=-1, help="结束轨道索引（含），-1 表示到最后一条（仅单文件模式有效）")
    parser.add_argument("--plot-global-2d", "--view-2d", dest="plot_global_2d", action="store_true", help="绘制全局 2D 视图")
    parser.add_argument("--plot-global-3d", "--view-3d", dest="plot_global_3d", action="store_true", help="绘制全局 3D 视图")
    parser.add_argument(
        "--plot-jacobi-stability", "--jacobi-period-stability", dest="plot_jacobi_stability", action="store_true",
        help="绘制 Jacobi 常数与周期、稳定性的关系曲线",
    )
    parser.add_argument(
        "--plot-center", type=str, default="moon", choices=["moon", "earth", "emb"],
        help="3D 视图的绘图中心（仅 DRO 有效）",
    )
    parser.add_argument("--plot-elev", type=float, default=20.0, help="3D 视图仰角（度）")
    parser.add_argument("--plot-azim", type=float, default=-60.0, help="3D 视图方位角（度）")
    parser.add_argument("--step", type=int, default=1, help="绘制轨道的间隔步长，1 表示绘制全部（仅单文件模式有效）")
    parser.add_argument("--no-show", action="store_true", help="只保存图片，不弹窗显示")
    return parser


def resolve_plot_range(start: int, end: int, n_orbits: int) -> tuple[int, int]:
    """解析 --start/--end 参数，返回 (plot_start, plot_end) 索引。"""
    last = n_orbits - 1
    s = min(start, last) if start >= 0 else 0
    e = min(end, last) if end >= 0 else last
    return (s, max(s, e))


def compute_stability_indices(family: OrbitFamily) -> list[float]:
    """计算轨道族的 Broucke 稳定性指数。"""
    values: list[float] = []
    for i in range(len(family)):
        orbit = family[i]
        analysis = StabilityAnalysis(orbit=orbit)
        indices = analysis.compute_stability_index()
        values.append(indices.get("broucke") or 0.0)
    return values


def compute_view_bounds(
    all_states: np.ndarray,
    plane: str = "xz",
) -> tuple:
    """根据轨道状态数组计算 2D 与 3D 视图的边界参数。

    Args:
        all_states: Nx6 状态数组
        plane: 2D 投影平面 ("xy", "xz", "yz")

    Returns:
        (xlim_2d, ylim_2d, center_3d, radius_3d)
    """
    if all_states.size == 0:
        return (0.8, 1.2), (-0.3, 0.3), (1.0, 0.0, 0.0), 0.4

    x_min, x_max = all_states[:, 0].min(), all_states[:, 0].max()
    y_min, y_max = all_states[:, 1].min(), all_states[:, 1].max()
    z_min, z_max = all_states[:, 2].min(), all_states[:, 2].max()

    # 根据 plane 选择 2D 轴
    plane_lower = plane.lower()
    if plane_lower == "yz":
        h_min, h_max = y_min, y_max
        v_min, v_max = z_min, z_max
    elif plane_lower == "xy":
        h_min, h_max = x_min, x_max
        v_min, v_max = y_min, y_max
    else:  # default: xz
        h_min, h_max = x_min, x_max
        v_min, v_max = z_min, z_max

    h_pad = max(0.05, (h_max - h_min) * 0.1)
    v_pad = max(0.05, (v_max - v_min) * 0.1)

    xlim_2d = (float(h_min - h_pad), float(h_max + h_pad))
    ylim_2d = (float(v_min - v_pad), float(v_max + v_pad))

    center_3d = (
        float((x_min + x_max) / 2),
        float((y_min + y_max) / 2),
        float((z_min + z_max) / 2),
    )
    radius_3d = float(
        max(x_max - x_min, y_max - y_min, z_max - z_min) / 2 + max(h_pad, v_pad)
    )
    return xlim_2d, ylim_2d, center_3d, radius_3d


def _get_center_coordinates(center_type: str, mu: float) -> tuple[float, float, float]:
    if center_type == "moon":
        return (1.0 - mu, 0.0, 0.0)
    elif center_type == "earth":
        return (0.0, 0.0, 0.0)
    elif center_type == "emb":
        return (mu, 0.0, 0.0)
    raise ValueError(f"Unknown center type: {center_type}")


def _resolve_3d_center_radius(
    cfg: FamilyPlotConfig,
    args: argparse.Namespace,
    bounds: tuple | None,
) -> tuple[tuple[float, float, float], float]:
    """根据用户 --plot-center 选择和配置计算 3D 视图的中心与半径。

    始终使用 args.plot_center 确定视图中心（moon/earth/emb）。
    半径优先使用 dynamic_bounds 计算，回退到配置默认值。

    Args:
        cfg: 轨道族绘图配置
        args: 命令行参数（需包含 plot_center）
        bounds: compute_view_bounds 的返回值，可为 None

    Returns:
        (center, radius) 元组
    """
    center = _get_center_coordinates(args.plot_center, MU)

    if cfg.dynamic_bounds and bounds is not None:
        data_center = bounds[2]
        data_radius = bounds[3]
        offset = float(np.sqrt(sum((c - d) ** 2 for c, d in zip(center, data_center))))
        radius = offset + data_radius
    elif cfg.radius_3d is not None:
        radius = cfg.radius_3d
    else:
        radius = 1.0

    return center, radius


def _project_2d(xyz: Sequence[float] | np.ndarray, plane: str) -> tuple[float, float]:
    """将 3D 坐标投影到指定平面。"""
    if plane == "yz":
        return (xyz[1], xyz[2])
    elif plane == "xy":
        return (xyz[0], xyz[1])
    else:  # xz
        return (xyz[0], xyz[2])


def _plot_bodies_and_libration(
    ax,
    plotter: FamilyPlotter,
    plane: str,
) -> None:
    """在 2D 坐标轴上绘制天体和 libration 点（支持任意投影平面）。"""
    plane_lower = plane.lower()

    # xy 平面：e2m2e helper 原生支持
    if plane_lower == "xy":
        plotter.plot_primary_bodies(ax=ax)
        plotter.plot_libration_points(ax=ax)
        return

    # xz / yz 平面：手动投影坐标
    mu = plotter.mu
    if mu is None:
        return

    # 天体位置（旋转坐标系）
    bodies = [
        ((-mu, 0.0, 0.0), "#2E86AB", "Earth", plotter.primary_body_size),
        ((1.0 - mu, 0.0, 0.0), "#95A5A6", "Moon", plotter.secondary_body_size),
    ]
    for pos_3d, color, name, size in bodies:
        h, v = _project_2d(pos_3d, plane_lower)
        ax.scatter(h, v, color=color, s=size, edgecolors="black", linewidth=1, zorder=10, label=name)

    # Libration 点
    system = plotter.system
    if system is not None and hasattr(system, "has_L_points"):
        if not system.has_L_points:
            system.compute_libration_points()
        if system.L_points is not None:
            from e2m2e.core import LibrationPoint
            for i, lp in enumerate(LibrationPoint):
                coord = system.L_points[lp]
                h, v = _project_2d(coord, plane_lower)
                color = plotter.libration_point_colors[i]
                marker = plotter.libration_point_markers[i]
                size = plotter.libration_point_sizes[i]
                label_text = plotter.libration_point_labels[i]
                ax.scatter(h, v, color=color, marker=marker, s=size, zorder=5)
                ax.annotate(
                    label_text, (h, v),
                    textcoords="offset points",
                    xytext=(5, 5),
                    fontsize=8,
                )


@dataclass(frozen=True)
class MultiFileConfig:
    """多文件绘制配置项。"""
    path: str
    start: int = -1
    end: int = -1
    step: int = 1


@dataclass(frozen=True)
class FamilyPlotConfig:
    """保存 FamilyPlotConfig 的配置字段。

    该类由脚本或 GUI 工作流内部使用，字段含义与调用处的参数保持一致。
    """
    family_type: str
    default_filename: str
    output_subdir: str
    plane: str = "xy"
    center_3d: tuple[float, float, float] | None = None
    radius_3d: float | None = None
    elev_3d: float = 20.0
    azim_3d: float = -60.0
    show_seed_overlay: bool = False
    target_period: float | None = None
    dynamic_bounds: bool = False
    libration_point_sizes: list[int] | None = None
    supports_center_choice: bool = False
    step: int = 5
    ratio: str | None = None

    @property
    def display_name(self) -> str:
        """返回用户可见的族名，含共振子类型。"""
        if self.ratio:
            return f"{self.family_type} ({self.ratio})"
        return self.family_type


def _parse_json_file_arg(arg_value: str | None) -> tuple[Path | None, list[MultiFileConfig]]:
    """解析 --json-file 参数。

    Args:
        arg_value: 参数值，可能是文件路径或 JSON 字符串

    Returns:
        (single_path, multi_configs)：
        - 如果是文件路径，single_path 不为 None，multi_configs 为空
        - 如果是 JSON 字符串，single_path 为 None，multi_configs 包含配置列表
    """
    if not arg_value:
        return None, []

    # 尝试解析为 JSON 数组
    try:
        data = _json.loads(arg_value)
        if isinstance(data, list):
            configs = []
            for item in data:
                path = item.get("path")
                if not path:
                    continue
                configs.append(MultiFileConfig(
                    path=path,
                    start=item.get("start", -1),
                    end=item.get("end", -1),
                    step=item.get("step", 1),
                ))
            return None, configs
    except (_json.JSONDecodeError, TypeError):
        pass

    # 作为文件路径处理
    return Path(arg_value), []


class FamilyPlotOrchestrator:
    """表示 FamilyPlotOrchestrator 相关的数据结构或行为。

    该类由脚本或 GUI 工作流内部使用，字段含义与调用处的参数保持一致。
    """
    def __init__(self, config: FamilyPlotConfig, args: argparse.Namespace) -> None:
        self.config = config
        self.args = args

    def run(self) -> None:
        """执行 run 对应的处理逻辑。

        Returns:
            None。

        Raises:
            Exception: 当输入数据、文件或数值流程不满足脚本要求时抛出。
        """
        a = self.args
        want_2d = a.plot_global_2d
        want_3d = a.plot_global_3d
        want_stab = a.plot_jacobi_stability

        if not want_2d and not want_3d and not want_stab:
            logger.warning("未选择任何图表，跳过绘制")
            return

        system = CR3BP_System(mu=MU, primary="earth", secondary="moon")
        output_dir = find_project_root(Path(__file__)) / "output" / self.config.output_subdir
        output_dir.mkdir(parents=True, exist_ok=True)

        # 解析多文件参数
        single_path, multi_configs = _parse_json_file_arg(a.json_file)

        if multi_configs:
            # 多文件模式
            self._run_multi(system, multi_configs, output_dir, want_2d, want_3d, want_stab)
        else:
            # 单文件模式
            self._run_single(system, single_path, output_dir, want_2d, want_3d, want_stab)

    def _run_single(
        self,
        system: CR3BP_System,
        single_path: Path | None,
        output_dir: Path,
        want_2d: bool,
        want_3d: bool,
        want_stab: bool,
    ) -> None:
        """单文件绘制模式。"""
        a = self.args
        cfg = self.config

        family, family_name = self._load_single_family(system, single_path, output_dir)
        n_orbits = len(family)
        logger.info(f"加载了 {n_orbits} 条 {cfg.display_name} 轨道")

        start, end = resolve_plot_range(a.start, a.end, n_orbits)
        subset = self._build_subset(family, start, end)

        jacobi_values = family.get_jacobi_constants().tolist()
        jacobi_subset = jacobi_values[start : end + 1]
        logger.info(f"Jacobi 常数范围: {min(jacobi_subset):.6f} ~ {max(jacobi_subset):.6f}")

        stability_subset: list[float] = []
        if want_stab:
            logger.info("正在计算稳定性指数...")
            stability_subset = compute_stability_indices(subset)

        step = a.step if a.step is not None else cfg.step
        if step < 1:
            raise ValueError("--step must be >= 1")

        plot_config = apply_standard_plot_config()
        plotter = FamilyPlotter(system, plot_config)
        if cfg.libration_point_sizes is not None:
            plotter.libration_point_sizes = cfg.libration_point_sizes

        bounds = None
        if cfg.dynamic_bounds:
            all_states = np.vstack([orbit.states for orbit in subset])
            bounds = compute_view_bounds(all_states, plane=cfg.plane)

        if want_2d:
            self._render_2d(plotter, subset, jacobi_subset, bounds, output_dir, family_name, n_orbits, step)
        if want_3d:
            self._render_3d(plotter, subset, jacobi_subset, bounds, output_dir, family_name, n_orbits, step)
        if want_stab:
            self._render_jacobi_stability(
                plotter, subset, jacobi_subset, stability_subset, output_dir, family_name, n_orbits
            )

    def _run_multi(
        self,
        system: CR3BP_System,
        multi_configs: list[MultiFileConfig],
        output_dir: Path,
        want_2d: bool,
        want_3d: bool,
        want_stab: bool,
    ) -> None:
        """多文件绘制模式。"""
        cfg = self.config

        # 加载所有文件并聚合
        all_subsets: list[OrbitFamily] = []
        all_jacobi: list[list[float]] = []
        all_steps: list[int] = []
        family_names: list[str] = []
        total_orbits = 0

        for i, config in enumerate(multi_configs):
            family_path = Path(config.path)
            if not family_path.exists():
                logger.warning(f"文件不存在，跳过: {family_path}")
                continue

            try:
                family = self._load_orbit_data(family_path, system)
            except Exception as e:
                logger.warning(f"加载文件失败 {family_path}: {e}")
                continue

            n_orbits = len(family)
            start, end = resolve_plot_range(config.start, config.end, n_orbits)
            subset = self._build_subset(family, start, end)

            jacobi_values = family.get_jacobi_constants().tolist()
            jacobi_subset = jacobi_values[start : end + 1]

            step = config.step if config.step >= 1 else 1
            all_steps.append(step)

            all_subsets.append(subset)
            all_jacobi.append(jacobi_subset)
            family_names.append(family_path.stem)
            total_orbits += len(subset)

            logger.info(f"[{i+1}/{len(multi_configs)}] 加载 {family_path.stem}: {len(subset)} 条轨道")

        if not all_subsets:
            logger.error("没有成功加载任何文件")
            return

        # 合并所有 family
        merged_family = OrbitFamily(system=system)
        merged_jacobi: list[float] = []
        for subset, jacobi in zip(all_subsets, all_jacobi):
            for orbit in subset.orbits:
                merged_family.add_orbit(orbit)
            merged_jacobi.extend(jacobi)

        # 合并 family 名称
        combined_name = "_vs_".join(family_names[:3])
        if len(family_names) > 3:
            combined_name += f"_and_{len(family_names) - 3}_more"

        logger.info(f"合并后共 {total_orbits} 条轨道，Jacobi 范围: {min(merged_jacobi):.6f} ~ {max(merged_jacobi):.6f}")

        stability_subset: list[float] = []
        if want_stab:
            logger.info("正在计算稳定性指数...")
            stability_subset = compute_stability_indices(merged_family)

        plot_config = apply_standard_plot_config()
        plotter = FamilyPlotter(system, plot_config)
        if cfg.libration_point_sizes is not None:
            plotter.libration_point_sizes = cfg.libration_point_sizes

        # 多文件模式始终使用动态边界
        all_states = np.vstack([orbit.states for orbit in merged_family])
        bounds = compute_view_bounds(all_states, plane=cfg.plane)

        if want_2d:
            self._render_2d_multi(
                plotter, all_subsets, all_jacobi, all_steps, bounds, output_dir, combined_name, total_orbits
            )
        if want_3d:
            self._render_3d_multi(
                plotter, all_subsets, all_jacobi, all_steps, bounds, output_dir, combined_name, total_orbits
            )
        if want_stab:
            self._render_jacobi_stability(
                plotter, merged_family, merged_jacobi, stability_subset, output_dir, combined_name, total_orbits
            )

    def _load_orbit_data(
        self,
        file_path: Path,
        system: CR3BP_System,
    ) -> OrbitFamily:
        """加载轨道数据，自动检测家族/单条轨道格式。"""
        with open(file_path, "r") as f:
            data = _json.load(f)
        if "orbits" in data:
            return OrbitFamily.load_from_file(filename=file_path, system=system)
        if "states" in data:
            orbit = Orbit.load_from_file(filename=file_path, system=system)
            family = OrbitFamily(system=system)
            family.add_orbit(orbit)
            return family
        return OrbitFamily.load_from_file(filename=file_path, system=system)

    def _load_single_family(
        self,
        system: CR3BP_System,
        single_path: Path | None,
        output_dir: Path,
    ) -> tuple[OrbitFamily, str]:
        """加载单个轨道族文件。"""
        cfg = self.config

        if single_path:
            family_path = single_path
            family_name = family_path.stem
        else:
            family_name = cfg.default_filename
            family_path = output_dir / f"{family_name}.json"

        if not family_path.exists():
            logger.info(f"数据文件不存在: {family_path}")
            raise SystemExit(1)

        family = self._load_orbit_data(family_path, system)
        return family, family_name

    def _build_subset(self, family: OrbitFamily, start: int, end: int) -> OrbitFamily:
        system = family.system
        subset = OrbitFamily(system=system)
        for i in range(start, end + 1):
            subset.add_orbit(family[i])
        return subset

    def _render_2d(
        self,
        plotter: FamilyPlotter,
        subset: OrbitFamily,
        jacobi: list[float],
        bounds: tuple | None,
        output_dir: Path,
        family_name: str,
        n_orbits: int,
        step: int,
    ) -> None:
        import matplotlib.pyplot as plt

        cfg = self.config
        a = self.args
        jmin, jmax = min(jacobi), max(jacobi)

        kwargs: dict = dict(
            plane=cfg.plane,
            show_bodies=True,
            show_libration=True,
            show_colorbar=True,
            step=step,
            show=False,
        )
        if cfg.dynamic_bounds and bounds is not None:
            kwargs["xlim"] = bounds[0]
            kwargs["ylim"] = bounds[1]

        if cfg.show_seed_overlay:
            kwargs["title"] = (
                f"{cfg.display_name.upper()} Orbit Family ({cfg.plane.upper()} Plane) - {n_orbits} orbits\n"
                f"C = [{jmin:.4f}, {jmax:.4f}]"
            )
        else:
            kwargs["title"] = (
                f"{cfg.display_name.upper()} Orbit Family ({cfg.plane.upper()} Plane) - {n_orbits} orbits\n"
                f"C = [{jmin:.4f}, {jmax:.4f}]"
            )

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=".*Tight layout.*")
            fig, ax = plotter.plot_family_2d(subset, jacobi, **kwargs)

        if cfg.show_seed_overlay and len(subset) > 0:
            seed_orbit = subset[0]
            plotter.plot_2d_projection(
                seed_orbit, color="red",
                label=f"Seed (C={jacobi[0]:.4f})", ax=ax,
            )
            plt.tight_layout()

        plt.savefig(output_dir / f"{family_name}_2d_view.png", dpi=300, bbox_inches="tight")
        if not a.no_show:
            plt.show()
        else:
            plt.close(fig)

    def _render_2d_multi(
        self,
        plotter: FamilyPlotter,
        subsets: list[OrbitFamily],
        jacobis: list[list[float]],
        steps: list[int],
        bounds: tuple,
        output_dir: Path,
        family_name: str,
        total_orbits: int,
    ) -> None:
        import matplotlib.pyplot as plt
        import matplotlib.cm as cm
        import matplotlib.colors as mcolors

        cfg = self.config
        a = self.args

        # 合并所有 jacobi 值用于计算范围
        all_jacobi = [j for jacobi in jacobis for j in jacobi]
        jmin, jmax = min(all_jacobi), max(all_jacobi)

        # 确定 plane (使用字符串，plot_2d_projection 支持字符串)
        plane = cfg.plane.lower()

        # 确定坐标轴标签
        if plane == "xz":
            xlabel = "X (nondimensional)"
            ylabel = "Z (nondimensional)"
        elif plane == "yz":
            xlabel = "Y (nondimensional)"
            ylabel = "Z (nondimensional)"
        else:
            xlabel = "X (nondimensional)"
            ylabel = "Y (nondimensional)"

        # 创建图形和坐标轴
        fig, ax = plt.subplots(figsize=(12, 8))

        # 设置边界
        if bounds:
            ax.set_xlim(bounds[0])
            ax.set_ylim(bounds[1])

        # 设置标题
        ax.set_title(
            f"{cfg.display_name.upper()} Orbit Families ({plane.upper()} Plane) - {total_orbits} orbits\n"
            f"C = [{jmin:.4f}, {jmax:.4f}]"
        )

        # 计算 jacobi 颜色映射
        norm = mcolors.Normalize(vmin=min(all_jacobi), vmax=max(all_jacobi))
        cmap = cm.get_cmap('viridis')

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=".*Tight layout.*")

            # 为每个 family 分别绘制到同一个坐标轴（使用各自 step）
            for subset, jacobi, step in zip(subsets, jacobis, steps):
                for i, orbit in enumerate(subset.orbits):
                    if i % step != 0:
                        continue
                    color = mcolors.to_hex(cmap(norm(jacobi[i])))
                    plotter.plot_2d_projection(
                        orbit,
                        plane=plane,
                        color=color,
                        ax=ax,
                        show_start=False,
                    )

            # 绘制天体和 libration 点（按 plane 投影）
            _plot_bodies_and_libration(ax, plotter, plane)

            # 添加强制相等的坐标轴比例
            ax.set_aspect('equal', adjustable='box')
            ax.grid(True, alpha=0.3)
            ax.set_xlabel(xlabel)
            ax.set_ylabel(ylabel)

            plt.tight_layout()

        plt.savefig(output_dir / f"{family_name}_2d_view.png", dpi=300, bbox_inches="tight")
        if not a.no_show:
            plt.show()
        else:
            plt.close(fig)

    def _render_3d(
        self,
        plotter: FamilyPlotter,
        subset: OrbitFamily,
        jacobi: list[float],
        bounds: tuple | None,
        output_dir: Path,
        family_name: str,
        n_orbits: int,
        step: int,
    ) -> None:
        import matplotlib.pyplot as plt

        cfg = self.config
        a = self.args
        jmin, jmax = min(jacobi), max(jacobi)

        center, radius = _resolve_3d_center_radius(cfg, a, bounds)
        elev = a.plot_elev
        azim = a.plot_azim

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=".*Tight layout.*")
            fig, ax = plotter.plot_family_3d(
                subset, jacobi,
                title=(
                    f"{cfg.display_name.upper()} Orbit Family (3D) - {n_orbits} orbits\n"
                    f"C = [{jmin:.4f}, {jmax:.4f}]"
                ),
                center=center, radius=radius,
                elev=elev, azim=azim,
                show_bodies=True, show_libration=True, show_colorbar=True,
                step=step, show=False,
            )

        if cfg.show_seed_overlay and len(subset) > 0:
            seed_orbit = subset[0]
            plotter.plot_3d_orbit(
                seed_orbit, color="red",
                label=f"Seed (C={jacobi[0]:.4f})", ax=ax,
                show_start=True,
            )
            plt.tight_layout()

        plt.savefig(output_dir / f"{family_name}_3d_view.png", dpi=300, bbox_inches="tight")
        if not a.no_show:
            plt.show()
        else:
            plt.close(fig)

    def _render_3d_multi(
        self,
        plotter: FamilyPlotter,
        subsets: list[OrbitFamily],
        jacobis: list[list[float]],
        steps: list[int],
        bounds: tuple,
        output_dir: Path,
        family_name: str,
        total_orbits: int,
    ) -> None:
        import matplotlib.pyplot as plt
        import matplotlib.cm as cm
        import matplotlib.colors as mcolors

        cfg = self.config
        a = self.args

        # 合并所有 jacobi 值用于计算范围
        all_jacobi = [j for jacobi in jacobis for j in jacobi]
        jmin, jmax = min(all_jacobi), max(all_jacobi)

        center, radius = _resolve_3d_center_radius(cfg, a, bounds)
        elev = a.plot_elev
        azim = a.plot_azim

        # 创建 3D 图形和坐标轴
        fig = plt.figure(figsize=(12, 10))
        ax = fig.add_subplot(111, projection='3d')

        # 设置视角
        ax.view_init(elev=elev, azim=azim)

        # 设置轴范围
        ax.set_xlim(center[0] - radius, center[0] + radius)
        ax.set_ylim(center[1] - radius, center[1] + radius)
        ax.set_zlim(center[2] - radius, center[2] + radius)

        # 计算 jacobi 颜色映射
        norm = mcolors.Normalize(vmin=min(all_jacobi), vmax=max(all_jacobi))
        cmap = cm.get_cmap('viridis')

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=".*Tight layout.*")

            # 为每个 family 分别绘制到同一个坐标轴（使用各自 step）
            for subset, jacobi, step in zip(subsets, jacobis, steps):
                for i, orbit in enumerate(subset.orbits):
                    if i % step != 0:
                        continue
                    color = mcolors.to_hex(cmap(norm(jacobi[i])))
                    plotter.plot_3d_orbit(
                        orbit,
                        color=color,
                        ax=ax,
                        show_start=False,
                    )

            # 绘制中心和 libration 点（3D 模式）
            plotter.plot_primary_bodies(ax=ax, is_3d=True)
            plotter.plot_libration_points(ax=ax, is_3d=True)

            # 设置标题
            ax.set_title(
                f"{cfg.display_name.upper()} Orbit Families (3D) - {total_orbits} orbits\n"
                f"C = [{jmin:.4f}, {jmax:.4f}]",
                fontsize=12,
            )

            # 设置轴标签
            ax.set_xlabel('X (nondimensional)')
            ax.set_ylabel('Y (nondimensional)')
            ax.set_zlabel('Z (nondimensional)')

            plt.tight_layout()

        plt.savefig(output_dir / f"{family_name}_3d_view.png", dpi=300, bbox_inches="tight")
        if not a.no_show:
            plt.show()
        else:
            plt.close(fig)

    def _render_jacobi_stability(
        self,
        plotter: FamilyPlotter,
        subset: OrbitFamily,
        jacobi: list[float],
        stability: list[float],
        output_dir: Path,
        family_name: str,
        n_orbits: int,
    ) -> None:
        cfg = self.config

        sort_idx = np.argsort(jacobi)
        jacobi_sorted = np.array(jacobi)[sort_idx].tolist()
        periods_sorted = np.array(subset.periods)[sort_idx].tolist()
        stability_sorted = np.array(stability)[sort_idx].tolist()

        kwargs: dict = dict(
            title=f"{cfg.display_name.upper()} Orbit Family - Period and Stability (n = {n_orbits})",
            save_path=str(output_dir / f"{family_name}_period_stability.png"),
            show=not self.args.no_show,
        )
        if cfg.target_period is not None:
            kwargs["target_period"] = cfg.target_period

        plotter.plot_jacobi_period_stability(
            jacobi_sorted, periods_sorted, stability_sorted, **kwargs
        )
