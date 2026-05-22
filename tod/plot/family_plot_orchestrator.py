"""Unified orbit family plotting orchestrator.

Provides :class:`FamilyPlotConfig` for declarative per-family configuration
and :class:`FamilyPlotOrchestrator` for the shared plotting pipeline.
"""

from __future__ import annotations

import argparse
import logging
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from e2m2e.algorithms.stability import StabilityAnalysis
from e2m2e.core import CR3BP_System, Orbit, OrbitFamily
from e2m2e.visualization import FamilyPlotter

from tod.commons.constants import MU
from tod.commons.common import find_project_root
from tod.plot.config import apply_standard_plot_config

logger = logging.getLogger(__name__)


def build_argparser(description: str) -> argparse.ArgumentParser:
    """Create a unified argument parser for orbit family plotting."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--json-file", type=str, default=None, help="轨道族 JSON 文件路径")
    parser.add_argument("--start", type=int, default=-1, help="起始轨道索引，-1 表示从第一条")
    parser.add_argument("--end", type=int, default=-1, help="结束轨道索引（含），-1 表示到最后一条")
    parser.add_argument("--plot-global-2d", action="store_true", help="绘制全局 2D 视图")
    parser.add_argument("--plot-global-3d", action="store_true", help="绘制全局 3D 视图")
    parser.add_argument(
        "--plot-jacobi-stability", action="store_true",
        help="绘制 Jacobi 常数与周期、稳定性的关系曲线",
    )
    parser.add_argument(
        "--plot-center", type=str, default="moon", choices=["moon", "earth", "emb"],
        help="3D 视图的绘图中心（仅 DRO 有效）",
    )
    parser.add_argument("--plot-elev", type=float, default=20.0, help="3D 视图仰角（度）")
    parser.add_argument("--plot-azim", type=float, default=-60.0, help="3D 视图方位角（度）")
    parser.add_argument("--step", type=int, default=1, help="绘制轨道的间隔步长，1 表示绘制全部")
    parser.add_argument("--no-show", action="store_true", help="只保存图片，不弹窗显示")
    return parser


def resolve_plot_range(start: int, end: int, n_orbits: int) -> tuple[int, int]:
    """解析 --start/--end 参数，返回 (plot_start, plot_end) 索引。"""
    last = n_orbits - 1
    s = min(start, last) if start >= 0 else 0
    e = min(end, last) if end >= 0 else last
    return (s, e)


def compute_stability_indices(family: OrbitFamily) -> list[float]:
    """计算轨道族的 Broucke 稳定性指数。"""
    values: list[float] = []
    for i in range(len(family)):
        orbit = family[i]
        analysis = StabilityAnalysis(orbit=orbit)
        indices = analysis.compute_stability_index()
        values.append(indices.get("broucke", 0.0))
    return values


def compute_view_bounds(all_states: np.ndarray) -> tuple:
    """根据轨道状态数组计算 2D 与 3D 视图的边界参数。

    Returns:
        (xlim_2d, ylim_2d, center_3d, radius_3d)
    """
    if all_states.size == 0:
        return (0.8, 1.2), (-0.3, 0.3), (1.0, 0.0, 0.0), 0.4

    x_min, x_max = all_states[:, 0].min(), all_states[:, 0].max()
    y_min, y_max = all_states[:, 1].min(), all_states[:, 1].max()
    z_min, z_max = all_states[:, 2].min(), all_states[:, 2].max()

    x_pad = max(0.05, (x_max - x_min) * 0.1)
    z_pad = max(0.05, (z_max - z_min) * 0.1)

    xlim_2d = (float(x_min - x_pad), float(x_max + x_pad))
    ylim_2d = (float(z_min - z_pad), float(z_max + z_pad))

    center_3d = (
        float((x_min + x_max) / 2),
        float((y_min + y_max) / 2),
        float((z_min + z_max) / 2),
    )
    radius_3d = float(
        max(x_max - x_min, y_max - y_min, z_max - z_min) / 2 + max(x_pad, z_pad)
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


@dataclass(frozen=True)
class FamilyPlotConfig:
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
    allow_single_orbit: bool = False
    step: int = 5


class FamilyPlotOrchestrator:
    def __init__(self, config: FamilyPlotConfig, args: argparse.Namespace) -> None:
        self.config = config
        self.args = args

    def run(self) -> None:
        a = self.args
        want_2d = a.plot_global_2d
        want_3d = a.plot_global_3d
        want_stab = a.plot_jacobi_stability

        if not want_2d and not want_3d and not want_stab:
            logger.warning("未选择任何图表，跳过绘制")
            return

        system = CR3BP_System(mu=MU, primary="earth", secondary="moon")
        family, family_name, output_dir = self._load_family(system)
        n_orbits = len(family)
        logger.info(f"加载了 {n_orbits} 条 {self.config.family_type} 轨道")

        start, end = resolve_plot_range(a.start, a.end, n_orbits)
        subset = self._build_subset(family, start, end)

        jacobi_values = family.get_jacobi_constants().tolist()
        jacobi_subset = jacobi_values[start : end + 1]
        logger.info(f"Jacobi 常数范围: {min(jacobi_subset):.6f} ~ {max(jacobi_subset):.6f}")

        stability_subset: list[float] = []
        if want_stab:
            logger.info("正在计算稳定性指数...")
            stability_subset = compute_stability_indices(subset)

        step = self.args.step if self.args.step is not None else self.config.step

        plot_config = apply_standard_plot_config()
        plotter = FamilyPlotter(system, plot_config)
        if self.config.libration_point_sizes is not None:
            plotter.libration_point_sizes = self.config.libration_point_sizes

        bounds = None
        if self.config.dynamic_bounds:
            all_states = np.vstack([orbit.states for orbit in subset])
            bounds = compute_view_bounds(all_states)

        if want_2d:
            self._render_2d(plotter, subset, jacobi_subset, bounds, output_dir, family_name, n_orbits, step)
        if want_3d:
            self._render_3d(plotter, subset, jacobi_subset, bounds, output_dir, family_name, n_orbits, step)
        if want_stab:
            self._render_jacobi_stability(
                plotter, subset, jacobi_subset, stability_subset, output_dir, family_name, n_orbits
            )

    def _load_family(self, system: CR3BP_System) -> tuple[OrbitFamily, str, Path]:
        import json as _json

        a = self.args
        cfg = self.config
        output_dir = find_project_root(Path(__file__)) / "output" / cfg.output_subdir

        if a.json_file:
            family_path = Path(a.json_file)
            family_name = family_path.stem
        else:
            family_name = cfg.default_filename
            family_path = output_dir / f"{family_name}.json"

        if not family_path.exists():
            logger.info(f"数据文件不存在: {family_path}")
            raise SystemExit(1)

        if cfg.allow_single_orbit:
            with open(family_path, "r") as f:
                data = _json.load(f)
            if "orbits" in data:
                family = OrbitFamily.load_from_file(filename=family_path, system=system)
            else:
                orbit = Orbit.load_from_file(filename=family_path, system=system)
                family = OrbitFamily(system=system)
                family.add_orbit(orbit)
        else:
            family = OrbitFamily.load_from_file(filename=family_path, system=system)

        return family, family_name, output_dir

    def _build_subset(self, family: OrbitFamily, start: int, end: int) -> OrbitFamily:
        system = family.system
        subset = OrbitFamily(system=system)
        for i in range(start, end + 1):
            subset.add_orbit(family[i])
        return subset

    def _render_2d(self, plotter, subset, jacobi, bounds, output_dir, family_name, n_orbits, step):
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
                f"{cfg.family_type.upper()} Orbit Family ({cfg.plane.upper()} Plane) - {n_orbits} orbits\n"
                f"C = [{jmin:.4f}, {jmax:.4f}]"
            )
        else:
            kwargs["title"] = (
                f"{cfg.family_type.upper()} Orbit Family ({cfg.plane.upper()} Plane) - {n_orbits} orbits\n"
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

    def _render_3d(self, plotter, subset, jacobi, bounds, output_dir, family_name, n_orbits, step):
        import matplotlib.pyplot as plt

        cfg = self.config
        a = self.args
        jmin, jmax = min(jacobi), max(jacobi)

        if cfg.dynamic_bounds and bounds is not None:
            center = bounds[2]
            radius = bounds[3]
        elif cfg.supports_center_choice:
            center = _get_center_coordinates(a.plot_center, MU)
            radius = cfg.radius_3d or 1.5
        else:
            center = cfg.center_3d or (0.0, 0.0, 0.0)
            radius = cfg.radius_3d or 1.0

        elev = a.plot_elev
        azim = a.plot_azim

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=".*Tight layout.*")
            fig, ax = plotter.plot_family_3d(
                subset, jacobi,
                title=(
                    f"{cfg.family_type.upper()} Orbit Family (3D) - {n_orbits} orbits\n"
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

    def _render_jacobi_stability(self, plotter, subset, jacobi, stability, output_dir, family_name, n_orbits):
        cfg = self.config

        sort_idx = np.argsort(jacobi)
        jacobi_sorted = np.array(jacobi)[sort_idx].tolist()
        periods_sorted = np.array(subset.periods)[sort_idx].tolist()
        stability_sorted = np.array(stability)[sort_idx].tolist()

        kwargs: dict = dict(
            title=f"{cfg.family_type.upper()} Orbit Family - Period and Stability (n = {n_orbits})",
            save_path=str(output_dir / f"{family_name}_period_stability.png"),
            show=not self.args.no_show,
        )
        if cfg.target_period is not None:
            kwargs["target_period"] = cfg.target_period

        plotter.plot_jacobi_period_stability(
            jacobi_sorted, periods_sorted, stability_sorted, **kwargs
        )
