"""
Transfer Visualization Module for DRO-RO Transfer Analysis

Generates figures from the paper:
- Fig. 6: Solution planes (T vs Δv) for 4 transfer combinations
- Fig. 8, 9, 10: Transfer trajectory plots in rotating and inertial frames
- Fig. 11: Quartile map of departure and insertion points

论文: Cui et al. (2025) - Two-impulse transfers from lunar distant retrograde orbits to resonant orbits
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from typing import List, Dict, Optional, Tuple
import json

from e2m2e.core.system import CR3BP_System
from e2m2e.core.dynamics import CR3BP_Dynamics
from e2m2e.core.orbit import Orbit
from e2m2e.transfer import load_orbit_from_json
from scripts.utils.common import MU, DU, TU, VU


MU = 1.21506683e-2
DU = 3.84405000e5
TU = 4.34811305
VU = 1023.23281


def _load_transfer_search_result():
    from e2m2e.transfer.transfer_search import Dict
    return Dict


class TransferVisualizer:
    """Transfer visualization class for generating paper figures"""

    def __init__(
        self,
        system: CR3BP_System,
        dro_orbit: Orbit,
        ro_orbit: Orbit,
        results: List[Dict],
    ):
        self.system = system
        self.mu = system.mu
        self.dro_orbit = dro_orbit
        self.ro_orbit = ro_orbit
        self.results = results

        self.dro_states = dro_orbit.states
        self.ro_states = ro_orbit.states

    def compute_delta_v(
        self, result: Dict
    ) -> Tuple[float, float, float]:
        """计算ΔV1, ΔV2和总ΔV

        返回:
            (ΔV1, ΔV2, 总ΔV) 单位: m/s
        """
        if result.transfer_trajectory is None or len(result.transfer_trajectory) < 2:
            return 0.0, 0.0, 0.0

        traj = result.transfer_trajectory

        dv1 = np.linalg.norm(traj[0, 3:] - result.departure_state[3:]) * VU
        dv2 = np.linalg.norm(traj[-1, 3:] - result.departure_state[3:]) * VU

        return dv1, dv2, dv1 + dv2

    def classify_transfer_type(self, result: Dict) -> str:
        """分类转移类型: direct, LGA, external"""
        if result.transfer_trajectory is None:
            return "unknown"

        traj = result.transfer_trajectory
        x_max_traj = np.max(traj[:, 0])
        transfer_time_days = result.transfer_time * TU

        if transfer_time_days < 20 and x_max_traj < 1.5:
            return "direct"
        elif x_max_traj > 3.0:
            return "external"
        else:
            return "LGA"

    def plot_solution_plane(
        self,
        save_path: Optional[str] = None,
        transfer_type: Optional[str] = None,
    ) -> plt.Figure:
        """绘制解平面 (论文Fig. 6)

        参数:
            save_path: 保存路径
            transfer_type: 筛选特定转移类型 ('direct', 'LGA', 'external')

        返回:
            matplotlib Figure对象
        """
        fig, axes = plt.subplots(2, 2, figsize=(14, 12))
        fig.suptitle("Solution Planes: DRO to RO Transfers in CR3BP", fontsize=14)

        titles = [
            "2:1 DRO → 3:2 RO",
            "3:1 DRO → 3:2 RO",
            "2:1 DRO → 3:1 RO",
            "3:1 DRO → 3:1 RO",
        ]

        for idx, ax in enumerate(axes.flat):
            dro_data = self.dro_states
            ro_data = self.ro_states

            dro_x = dro_data[:, 0]
            ro_x = ro_data[:, 0]

            ax.set_title(titles[idx])
            ax.set_xlabel("Transfer Time (days)")
            ax.set_ylabel("Total Impulse Cost ΔV (m/s)")

            ax.grid(True, alpha=0.3)

            if transfer_type:
                filtered_results = [
                    r
                    for r in self.results
                    if self.classify_transfer_type(r) == transfer_type
                ]
                self._plot_results_on_axis(ax, filtered_results)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches="tight")
            print(f"解平面图已保存: {save_path}")

        return fig

    def _plot_results_on_axis(self, ax, results: List[Dict]) -> None:
        """在axis上绘制结果点"""
        times_days = []
        costs = []
        types = []

        for r in results:
            if r.transfer_trajectory is None:
                continue

            dv1, dv2, total_dv = self.compute_delta_v(r)
            if total_dv > 0:
                times_days.append(r.transfer_time * TU)
                costs.append(total_dv)
                types.append(self.classify_transfer_type(r))

        times_days = np.array(times_days)
        costs = np.array(costs)

        type_colors = {
            "direct": "blue",
            "LGA": "green",
            "external": "red",
            "unknown": "gray",
        }

        for t_type in ["direct", "LGA", "external"]:
            mask = np.array([x == t_type for x in types])
            if np.any(mask):
                ax.scatter(
                    times_days[mask],
                    costs[mask],
                    c=type_colors[t_type],
                    s=10,
                    alpha=0.6,
                    label=t_type.upper(),
                )

        ax.legend()

    def plot_transfer_trajectory_2d(
        self,
        result: Dict,
        ax: plt.Axes,
        frame: str = "rotating",
        show_orbits: bool = True,
    ) -> None:
        """在2D axis上绘制转移轨道

        参数:
            result: 搜索结果
            ax: matplotlib axes
            frame: 'rotating' 或 'inertial'
            show_orbits: 是否显示DRO和RO轨道
        """
        traj = result.transfer_trajectory
        if traj is None or len(traj) == 0:
            return

        if frame == "rotating":
            x = traj[:, 0]
            y = traj[:, 1]
            xlabel = "x (DU)"
            ylabel = "y (DU)"

            if show_orbits:
                ax.plot(
                    self.dro_states[:, 0],
                    self.dro_states[:, 1],
                    "b-",
                    linewidth=1.5,
                    alpha=0.7,
                    label="2:1 DRO",
                )
                ax.plot(
                    self.ro_states[:, 0],
                    self.ro_states[:, 1],
                    "g-",
                    linewidth=1.5,
                    alpha=0.7,
                    label="3:2 RO",
                )

            earth_pos = (0, 0)
            moon_pos = (1 - self.mu, 0)

        else:
            raise NotImplementedError("Inertial frame not yet implemented")

        ax.plot(x, y, "r-", linewidth=2, label="Transfer Trajectory")
        ax.plot(x[0], y[0], "ro", markersize=10, label="Departure")
        ax.plot(x[-1], y[-1], "go", markersize=10, label="Insertion")

        ax.plot(*earth_pos, "ko", markersize=15, label="Earth")
        ax.plot(*moon_pos, "o", color="gray", markersize=8, label="Moon")

        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_aspect("equal")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper right")

    def plot_quartile_map(
        self,
        save_path: Optional[str] = None,
    ) -> plt.Figure:
        """绘制四分位图 (论文Fig. 11)

        显示出发点插入点的距离分布

        返回:
            matplotlib Figure对象
        """
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle("Quartile Map: Departure and Insertion Points", fontsize=14)

        pathways = [
            ("2:1 DRO → 3:2 RO", "blue"),
            ("3:1 DRO → 3:2 RO", "green"),
            ("2:1 DRO → 3:1 RO", "orange"),
            ("3:1 DRO → 3:1 RO", "red"),
        ]

        for idx, (ax, (title, color)) in enumerate(zip(axes.flat, pathways)):
            ax.set_title(title)
            ax.set_ylabel("Distance to Earth (DU)")

            departure_distances = []
            insertion_distances = []

            for r in self.results:
                if r.transfer_trajectory is None:
                    continue

                dep_dist = np.sqrt(
                    r.departure_state[0] ** 2 + r.departure_state[1] ** 2
                )
                ins_dist = np.sqrt(
                    r.transfer_trajectory[-1, 0] ** 2
                    + r.transfer_trajectory[-1, 1] ** 2
                )

                departure_distances.append(dep_dist)
                insertion_distances.append(ins_dist)

            if departure_distances:
                dep_arr = np.array(departure_distances)
                ins_arr = np.array(insertion_distances)

                positions = [1, 2]
                data_dep = [dep_arr]
                data_ins = [ins_arr]

                bp_dep = ax.boxplot(
                    data_dep,
                    positions=[1],
                    widths=0.6,
                    patch_artist=True,
                )
                bp_ins = ax.boxplot(
                    data_ins,
                    positions=[2],
                    widths=0.6,
                    patch_artist=True,
                )

                for patch in bp_dep["boxes"]:
                    patch.set_facecolor(color)
                    patch.set_alpha(0.5)
                for patch in bp_ins["boxes"]:
                    patch.set_facecolor(color)
                    patch.set_alpha(0.5)

                ax.set_xticks([1, 2])
                ax.set_xticklabels(["Departure", "Insertion"])
                ax.grid(True, alpha=0.3, axis="y")

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches="tight")
            print(f"四分位图已保存: {save_path}")

        return fig

    def plot_all_transfer_types(
        self,
        save_dir: Optional[str] = None,
    ) -> Dict[str, plt.Figure]:
        """绘制所有转移类型的典型轨迹

        返回:
            dict: 类型到Figure的映射
        """
        figures = {}

        categorized = {"direct": [], "LGA": [], "external": []}

        for r in self.results:
            t_type = self.classify_transfer_type(r)
            if t_type in categorized:
                categorized[t_type].append(r)

        for t_type, type_results in categorized.items():
            if not type_results:
                continue

            fig, axes = plt.subplots(1, 2, figsize=(16, 6))
            fig.suptitle(f"{t_type.upper()} Transfer Trajectories", fontsize=14)

            sorted_results = sorted(
                type_results,
                key=lambda r: self.compute_delta_v(r)[2],
            )

            best_result = sorted_results[0]

            self.plot_transfer_trajectory_2d(
                best_result,
                axes[0],
                frame="rotating",
                show_orbits=True,
            )
            axes[0].set_title(
                f"Best {t_type.upper()} Transfer (ΔV={self.compute_delta_v(best_result)[2]:.1f} m/s)"
            )

            all_traj = np.array(
                [
                    r.transfer_trajectory
                    for r in sorted_results[:5]
                    if r.transfer_trajectory is not None
                ]
            )
            if len(all_traj) > 0:
                for traj in all_traj:
                    axes[1].plot(traj[:, 0], traj[:, 1], alpha=0.5)
                axes[1].plot(
                    self.dro_states[:, 0],
                    self.dro_states[:, 1],
                    "b-",
                    linewidth=2,
                    label="DRO",
                )
                axes[1].plot(
                    self.ro_states[:, 0],
                    self.ro_states[:, 1],
                    "g-",
                    linewidth=2,
                    label="RO",
                )
                axes[1].plot(0, 0, "ko", markersize=15, label="Earth")
                axes[1].plot(
                    1 - self.mu, 0, "o", color="gray", markersize=8, label="Moon"
                )
                axes[1].set_aspect("equal")
                axes[1].grid(True, alpha=0.3)
                axes[1].legend()
                axes[1].set_title(f"Top 5 {t_type.upper()} Transfers")

            plt.tight_layout()

            if save_dir:
                save_path = Path(save_dir) / f"{t_type}_transfers.png"
                plt.savefig(save_path, dpi=150, bbox_inches="tight")
                print(f"{t_type}转移轨迹图已保存: {save_path}")

            figures[t_type] = fig

        return figures


class NLPResultVisualizer:
    """NLP优化结果可视化类，支持绘制转移轨道、解平面、统计图"""

    def __init__(
        self,
        system: CR3BP_System,
        dro_orbit: Orbit,
        ro_orbit: Orbit,
        nlp_results: List[Dict],
    ):
        self.system = system
        self.mu = system.mu
        self.dro_orbit = dro_orbit
        self.ro_orbit = ro_orbit
        self.results = nlp_results

        self.dro_states = np.array(dro_orbit.states)
        self.ro_states = np.array(ro_orbit.states)

    def get_success_cases(self) -> List[Dict]:
        return [r for r in self.results if r.get("nlp") and r["nlp"].get("success")]

    def get_failed_cases(self) -> List[Dict]:
        return [r for r in self.results if r.get("nlp") and not r["nlp"].get("success")]

    def plot_transfer_trajectory_2d(
        self,
        nlp_result: Dict,
        ax: plt.Axes,
        show_orbits: bool = True,
        color: str = "red",
    ) -> None:
        traj_data = nlp_result.get("nlp")
        if not traj_data:
            return
        traj = traj_data.get("transfer_trajectory")
        if traj is None or len(traj) == 0:
            return
        traj = np.array(traj)

        if show_orbits:
            ax.plot(
                self.dro_states[:, 0],
                self.dro_states[:, 1],
                "b-",
                linewidth=1.5,
                alpha=0.7,
                label="DRO",
            )
            ax.plot(
                self.ro_states[:, 0],
                self.ro_states[:, 1],
                "g-",
                linewidth=1.5,
                alpha=0.7,
                label="RO",
            )

        ax.plot(traj[:, 0], traj[:, 1], "-", color=color, linewidth=2, label="Transfer")
        ax.plot(traj[0, 0], traj[0, 1], "o", color=color, markersize=10, label="Departure")
        ax.plot(traj[-1, 0], traj[-1, 1], "s", color=color, markersize=10, label="Insertion")

        ax.plot(0, 0, "ko", markersize=15, label="Earth")
        ax.plot(1 - self.mu, 0, "o", color="gray", markersize=8, label="Moon")

        ax.set_xlabel("x (DU)")
        ax.set_ylabel("y (DU)")
        ax.set_aspect("equal")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper right")

    def plot_transfer_trajectory_3d(
        self,
        nlp_result: Dict,
        ax: plt.Axes,
        show_orbits: bool = True,
        color: str = "red",
    ) -> None:
        traj_data = nlp_result.get("nlp")
        if not traj_data:
            return
        traj = traj_data.get("transfer_trajectory")
        if traj is None or len(traj) == 0:
            return
        traj = np.array(traj)

        if show_orbits:
            ax.plot(
                self.dro_states[:, 0],
                self.dro_states[:, 1],
                self.dro_states[:, 2],
                "b-",
                linewidth=1.5,
                alpha=0.7,
                label="DRO",
            )
            ax.plot(
                self.ro_states[:, 0],
                self.ro_states[:, 1],
                self.ro_states[:, 2],
                "g-",
                linewidth=1.5,
                alpha=0.7,
                label="RO",
            )

        ax.plot(traj[:, 0], traj[:, 1], traj[:, 2], "-", color=color, linewidth=2, label="Transfer")
        ax.scatter(traj[0, 0], traj[0, 1], traj[0, 2], color=color, s=100, marker="o", label="Departure")
        ax.scatter(traj[-1, 0], traj[-1, 1], traj[-1, 2], color=color, s=100, marker="s", label="Insertion")

        ax.set_xlabel("x (DU)")
        ax.set_ylabel("y (DU)")
        ax.set_zlabel("z (DU)")
        ax.legend()

    def plot_all_success_trajectories(
        self,
        save_path: Optional[str] = None,
    ) -> plt.Figure:
        successes = self.get_success_cases()
        if not successes:
            print("No successful cases to plot")
            return None

        n = len(successes)
        n_cols = min(3, n)
        n_rows = (n + n_cols - 1) // n_cols

        fig, axes = plt.subplots(n_rows, n_cols, figsize=(6 * n_cols, 6 * n_rows))
        if n == 1:
            axes = np.array([axes])
        axes = axes.flatten()

        colors = plt.cm.rainbow(np.linspace(0, 1, n))

        for idx, (result, ax, color) in enumerate(zip(successes, axes, colors)):
            nlp = result["nlp"]
            traj = np.array(nlp["transfer_trajectory"])

            ax.plot(self.dro_states[:, 0], self.dro_states[:, 1], "b-", linewidth=1, alpha=0.5, label="DRO")
            ax.plot(self.ro_states[:, 0], self.ro_states[:, 1], "g-", linewidth=1, alpha=0.5, label="RO")
            ax.plot(traj[:, 0], traj[:, 1], "-", color=color, linewidth=2)
            ax.plot(traj[0, 0], traj[0, 1], "o", color=color, markersize=8)
            ax.plot(traj[-1, 0], traj[-1, 1], "s", color=color, markersize=8)

            ax.plot(0, 0, "ko", markersize=10)
            ax.plot(1 - self.mu, 0, "o", color="gray", markersize=6)

            total_dv = nlp.get("objective_value", 0) * VU
            ax.set_title(
                f"Case {idx+1}: {nlp.get('transfer_type', 'unknown').upper()}, "
                f"ΔV={total_dv:.1f} m/s"
            )
            ax.set_aspect("equal")
            ax.grid(True, alpha=0.3)

        for ax in axes[n:]:
            ax.set_visible(False)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches="tight")
            print(f"所有成功轨迹图已保存: {save_path}")

        return fig

    def plot_solution_plane(
        self,
        save_path: Optional[str] = None,
    ) -> plt.Figure:
        successes = self.get_success_cases()
        if not successes:
            print("No successful cases")
            return None

        fig, ax = plt.subplots(figsize=(10, 6))

        direct = []
        lga = []

        for r in successes:
            nlp = r["nlp"]
            t_days = nlp["transfer_time"] * TU
            dv = nlp["objective_value"] * VU
            if nlp.get("transfer_type") == "direct":
                direct.append((t_days, dv))
            else:
                lga.append((t_days, dv))

        if direct:
            d = np.array(direct)
            ax.scatter(d[:, 0], d[:, 1], c="blue", s=50, alpha=0.7, label=f"Direct ({len(direct)})")
        if lga:
            l = np.array(lga)
            ax.scatter(l[:, 0], l[:, 1], c="green", s=50, alpha=0.7, label=f"LGA ({len(lga)})")

        ax.set_xlabel("Transfer Time (days)")
        ax.set_ylabel("Total ΔV (m/s)")
        ax.set_title("Solution Plane: NLP Optimization Results")
        ax.grid(True, alpha=0.3)
        ax.legend()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches="tight")
            print(f"解平面图已保存: {save_path}")

        return fig

    def plot_statistics(
        self,
        save_path: Optional[str] = None,
    ) -> plt.Figure:
        total = len(self.results)
        successes = len(self.get_success_cases())
        failed = total - successes

        fig, axes = plt.subplots(1, 3, figsize=(15, 5))

        # 成功率饼图
        axes[0].pie(
            [successes, failed],
            labels=["Success", "Failed"],
            autopct="%1.1f%%",
            colors=["green", "red"],
            explode=(0.05, 0),
        )
        axes[0].set_title(f"Optimization Success Rate\n({total} cases)")

        # ΔV 分布
        success_dvs = []
        for r in self.get_success_cases():
            dv = r["nlp"]["objective_value"] * VU
            success_dvs.append(dv)

        if success_dvs:
            axes[1].hist(success_dvs, bins=20, color="steelblue", edgecolor="black", alpha=0.7)
            axes[1].set_xlabel("Total ΔV (m/s)")
            axes[1].set_ylabel("Count")
            axes[1].set_title(f"ΔV Distribution (Success: {len(success_dvs)})")
            axes[1].grid(True, alpha=0.3)

            # 标注统计值
            axes[1].axvline(np.mean(success_dvs), color="red", linestyle="--", label=f"Mean: {np.mean(success_dvs):.1f}")
            axes[1].axvline(np.median(success_dvs), color="orange", linestyle="--", label=f"Median: {np.median(success_dvs):.1f}")
            axes[1].legend()

        # 转移类型分布
        type_counts = {}
        for r in self.results:
            if r.get("nlp"):
                t = r["nlp"].get("transfer_type", "unknown")
                type_counts[t] = type_counts.get(t, 0) + 1

        if type_counts:
            bars = axes[2].bar(type_counts.keys(), type_counts.values(), color=["steelblue", "green", "orange"][:len(type_counts)])
            axes[2].set_xlabel("Transfer Type")
            axes[2].set_ylabel("Count")
            axes[2].set_title("Transfer Type Distribution")
            for bar, count in zip(bars, type_counts.values()):
                axes[2].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5, str(count), ha="center")

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches="tight")
            print(f"统计图已保存: {save_path}")

        return fig


def load_nlp_results(filepath: str) -> Dict:
    """加载NLP优化结果JSON文件"""
    with open(filepath, "r") as f:
        data = json.load(f)
    return data


def load_search_results(filepath: str) -> List[Dict]:
    """从JSON文件加载搜索结果"""
    with open(filepath, "r") as f:
        data = json.load(f)

    results = []
    for item in data:
        result = Dict(
            departure_orbit_name=item.get("departure_orbit_name", ""),
            arrival_orbit_name=item.get("arrival_orbit_name", ""),
            departure_time_index=item.get("departure_time_index", 0),
            alpha=item.get("alpha", 0.0),
            beta=item.get("beta", 0.0),
            departure_time=item.get("departure_time", 0.0),
            transfer_time=item.get("transfer_time", 0.0),
            intersection_found=item.get("intersection_found", False),
            min_distance=item.get("min_distance", float("inf")),
            local_minimum_found=item.get("local_minimum_found", False),
            collision_found=item.get("collision_found", False),
            status=item.get("status", ""),
        )
        results.append(result)

    return results


def main():
    """主函数 - 生成所有可视化图像"""
    import argparse

    parser = argparse.ArgumentParser(description="生成转移轨道可视化图像")
    parser.add_argument("--results", type=str, help="搜索结果JSON文件或NLP优化结果JSON文件")
    parser.add_argument("--dro", type=str, help="DRO轨道JSON文件")
    parser.add_argument("--ro", type=str, help="RO轨道JSON文件")
    parser.add_argument(
        "--output-dir", type=str, default="output/transfer/figures", help="输出目录"
    )
    parser.add_argument(
        "--type",
        type=str,
        choices=["search", "nlp"],
        default="nlp",
        help="结果类型: search(网格搜索) 或 nlp(优化结果)",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("加载数据...")
    dro_orbit = load_orbit_from_json(args.dro)
    ro_orbit = load_orbit_from_json(args.ro)
    system = CR3BP_System(mu=MU, primary="earth", secondary="moon")

    if args.type == "nlp":
        nlp_data = load_nlp_results(args.results)
        nlp_results = nlp_data.get("results", [])

        print(f"加载了 {len(nlp_results)} 个NLP优化结果")

        success_count = len([r for r in nlp_results if r.get("nlp") and r["nlp"].get("success")])
        print(f"成功案例: {success_count}")

        visualizer = NLPResultVisualizer(system, dro_orbit, ro_orbit, nlp_results)

        print("\n生成所有成功轨迹图...")
        visualizer.plot_all_success_trajectories(
            save_path=str(output_dir / "nlp_all_trajectories.png")
        )

        print("\n生成解平面图...")
        visualizer.plot_solution_plane(save_path=str(output_dir / "nlp_solution_plane.png"))

        print("\n生成统计图...")
        visualizer.plot_statistics(save_path=str(output_dir / "nlp_statistics.png"))

    else:
        results = load_search_results(args.results)
        print(f"加载了 {len(results)} 个搜索结果")

        visualizer = TransferVisualizer(system, dro_orbit, ro_orbit, results)

        print("\n生成解平面图 (Fig. 6)...")
        visualizer.plot_solution_plane(
            save_path=str(output_dir / "fig6_solution_plane.png")
        )

        print("\n生成转移轨迹图...")
        visualizer.plot_all_transfer_types(save_dir=str(output_dir))

        print("\n生成四分位图 (Fig. 11)...")
        visualizer.plot_quartile_map(save_path=str(output_dir / "fig11_quartile_map.png"))

    print(f"\n所有图像已保存到: {output_dir}")


if __name__ == "__main__":
    main()
