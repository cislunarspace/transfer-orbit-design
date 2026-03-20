"""
[已废弃] 阶段一：基线轨道生成 — 共振轨道族 (RO)

本脚本已废弃，功能已拆分为：
  - generate_ro_family.py: 生成RO轨道族
  - plot_ro_family.py: 可视化RO轨道族

请使用新的脚本：
  python scripts/generate_ro_family.py --family both
  python scripts/plot_ro_family.py --family both --plots all
"""

import argparse
import datetime
import os
import sys

import matplotlib
import matplotlib.pyplot as plt
import e2m2e
from e2m2e.core import Orbit, OrbitFamily
import numpy as np
from scipy.integrate import solve_ivp

# 检查新脚本是否存在
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GENERATE_SCRIPT = os.path.join(SCRIPT_DIR, "generate_ro_family.py")
PLOT_SCRIPT = os.path.join(SCRIPT_DIR, "plot_ro_family.py")

# ============================================================
# 系统参数（论文Table 1）
# ============================================================
MU = 1.21506683e-2
DU = 3.84405e5  # km
TU = 4.34811305  # days
VU = 1023.23281  # m/s

T_MOON = 2 * np.pi  # 月球恒星周期(无量纲)

# 目标共振轨道周期
T_RO_32 = 2 * T_MOON  # 4π ≈ 12.566
T_RO_31 = 1 * T_MOON  # 2π ≈  6.283

# 输出目录
OUTPUT_DIR = "output/phase1_ro"
FAMILY_FILENAME_32 = "ro_32_family.json"
FAMILY_FILENAME_31 = "ro_31_family.json"


# ============================================================
# 种子搜索结果（通过微分修正收敛后的状态量）
# ============================================================
# RO是关于x轴对称的周期轨道
# 论文Table 2中的x,y是y幅值点（vy=0），不是x轴交点
# x轴交点应该在更靠近L3/L4的位置（x值比y幅值点小）
#
# 对于3:2 RO：
#   - y幅值点: x=-1.1453, y=0.4633 (此处vy=0)
#   - x轴交点应该在 x < -1.1453 的位置（约-0.9到-1.0之间）
#   - 轨道周期 T = 4π ≈ 12.566 TU
#
# 对于3:1 RO：
#   - y幅值点: x=-0.8805, y=0.3921 (此处vy=0)
#   - x轴交点应该在 x < -0.8805 的位置
#   - 轨道周期 T = 2π ≈ 6.283 TU
#
# 使用 setup_2D_symmetric_x_fixed_x0 配置（与DRO相同）：
#   固定初始x坐标x0，自由变量为 [y_dot0, T_half]
#   约束条件：y(T/2)=0, x_dot(T/2)=0
#
# RO是顺行轨道(prograde)，y_dot0 > 0

# 论文Table 2中的固定初值（y幅值点）
RO_SEEDS = {
    "3:2": {
        "x0": -1.1453,  # y幅值点x坐标（论文Table 2）
        "y0": 0.4633,  # y幅值点y坐标（论文Table 2）
        "y_dot0": None,  # 需要通过微分修正确定
        "period": 2 * T_MOON,  # T = 4π ≈ 12.566 TU
    },
    "3:1": {
        "x0": -0.8805,  # y幅值点x坐标（论文Table 2）
        "y0": 0.3921,  # y幅值点y坐标（论文Table 2）
        "y_dot0": None,  # 需要通过微分修正确定
        "period": 1 * T_MOON,  # T = 2π ≈ 6.283 TU
    },
}


# ============================================================
# 辅助函数
# ============================================================
def ensure_output_dir():
    """确保输出目录存在"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def find_converged_seed(dynamics, seed_dict, system, max_attempts=30):
    """使用阻尼迭代找到收敛的种子轨道

    共振轨道与DRO具有相同的x轴对称性，从x轴垂直出发（y=0, x_dot=0），
    经过半周期T/2后再次穿越x轴（y=0, x_dot=0）。
    使用 setup_2D_symmetric_x_fixed_x0 配置，自由变量为 [y_dot0, T_half]。

    参数:
        dynamic: CR3BP_Dynamics对象
        seed_dict: dict, 包含x0_range, y_dot0_range, period
        system: CR3BP_System对象
        max_attempts: 最大尝试次数

    返回:
        收敛的Orbit或None
    """

    x0_range = seed_dict["x0_range"]
    y_dot0_range = seed_dict["y_dot0_range"]
    period = seed_dict["period"]

    # 微分修正器配置 - 固定x0，自由变量[y_dot0, T_half]
    corrector = e2m2e.algorithms.DifferentialCorrection(
        dynamics
    )  # //TODO 这里需要新创建一个corrector实例吗？
    corrector.tolerance = 1e-12
    corrector.max_iterations = 100

    # 收集所有收敛的轨道，选择周期最接近目标的
    best_orbit = None
    best_period_error = float("inf")

    # 尝试不同的x0值，在给定范围内搜索（更密集的网格）
    x0_candidates = np.linspace(x0_range[0], x0_range[1], 20)

    for x0 in x0_candidates:
        corrector.setup_2D_symmetric_x_fixed_x0(x0)

        # 尝试不同的y_dot0值，步长更细
        y_dot0_candidates = np.linspace(y_dot0_range[0], y_dot0_range[1], max_attempts)

        for y_dot0_guess in y_dot0_candidates:
            # 创建种子Orbit - 从x轴垂直出发
            initial_state = [x0, 0.0, 0.0, 0.0, y_dot0_guess, 0.0]
            t_eval = np.linspace(0, period, 500)
            res = solve_ivp(
                dynamics.equations_of_motion,
                (0, period),
                initial_state,
                method="DOP853",
                t_eval=t_eval,
                rtol=1e-10,
                atol=1e-10,
            )

            if not res.success:
                continue

            orbit = Orbit(res.y.T, res.t, system=system)
            orbit.period = period

            # 尝试修正
            corrected_orbit = corrector.iterate_correction(
                orbit, verbose=True
            )  # //TODO 这里修正的是什么轨道？

            if corrected_orbit is not None and corrected_orbit.correction_success:
                # 检查周期是否接近目标（允许5%偏差）
                period_error = abs(corrected_orbit.period - period) / period
                if period_error < 0.05 and period_error < best_period_error:
                    best_orbit = corrected_orbit
                    best_period_error = period_error
                    print(
                        f"  找到候选种子: x0={x0:.6f}, y_dot0={corrected_orbit.states[0, 4]:.6f}, "
                        f"T={corrected_orbit.period:.6f} (目标: {period:.6f}, 误差: {period_error:.2%})"
                    )

    if best_orbit is not None:
        print(
            f"  选择最佳种子: T={best_orbit.period:.6f}, 周期误差={best_period_error:.2%}"
        )
    return best_orbit


def create_propagated_seed_orbit(dynamics, seed_dict, system):
    """创建包含完整积分的种子Orbit

    参数:
        dynamic: CR3BP_Dynamics对象
        seed_dict: dict, 包含x0, y0, y_dot0, period
        system: CR3BP_System对象

    返回:
        Orbit对象
    """

    x0 = seed_dict["x0"]
    y0 = seed_dict.get("y0", 0.0)
    y_dot0 = seed_dict["y_dot0"]
    period = seed_dict["period"]

    initial_state = [x0, y0, 0.0, 0.0, y_dot0, 0.0]
    t_eval = np.linspace(0, period, 1000)
    res = solve_ivp(
        dynamics.equations_of_motion,
        (0, period),
        initial_state,
        method="DOP853",
        t_eval=t_eval,
        rtol=1e-12,
        atol=1e-12,
    )

    orbit = Orbit(res.y.T, res.t, system=system)
    orbit.period = period
    orbit.is_periodic = True
    return orbit


def save_family(system, family_result, filename):
    """保存轨道族到文件"""
    ensure_output_dir()

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    family_dir = os.path.join(OUTPUT_DIR, timestamp)
    os.makedirs(family_dir, exist_ok=True)

    family_path = os.path.join(family_dir, filename)
    family_result.save_to_file(family_path)
    print(f"轨道族已保存: {family_path}")

    latest_path = os.path.join(OUTPUT_DIR, filename)
    import shutil

    shutil.copy(family_path, latest_path)
    print(f"最新轨道族: {latest_path}")

    return family_dir


def visualize_orbits(system, family_result, label, target_T):
    """可视化RO轨道族 - 使用e2m2e plotting模块的plot_resonant_orbit_family方法

    参数：
        system: CR3BP_System对象
        family_result: OrbitFamily对象
        label: str, RO标签如"3:2"或"3:1"
        target_T: float, 目标周期
    """
    # 创建轨道可视化器
    orbit_plotter = e2m2e.visualization.plotting.OrbitVisualizer(system)

    # 自定义天体颜色：地球蓝色，月球白色
    orbit_plotter.primary_body_color = "blue"
    orbit_plotter.secondary_body_color = "white"

    # 统一拉格朗日点样式：灰色小三角
    orbit_plotter.libration_point_colors = ["gray"] * 5
    orbit_plotter.libration_point_markers = ["^"] * 5
    orbit_plotter.libration_point_sizes = [60] * 5

    # 调用新的plot_resonant_orbit_family方法
    orbit_plotter.plot_resonant_orbit_family(
        family_result,
        label=label,
        target_period=target_T,
        show_plots=True,
    )


# ============================================================
# 主程序（已废弃，转发到新脚本）
# ============================================================
def main():
    # 检查脚本是否存在
    if not os.path.exists(GENERATE_SCRIPT):
        print(f"错误: 生成脚本不存在: {GENERATE_SCRIPT}")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="RO族生成（已废弃，请使用新脚本）")
    parser.add_argument("--run-continuation", action="store_true", help="执行延拓（已废弃）")
    parser.add_argument(
        "--family",
        choices=["32", "31", "both"],
        default="both",
        help="选择要处理的RO族",
    )
    parser.add_argument("--skip-deprecation-warning", action="store_true", help="跳过废弃警告")
    args = parser.parse_args()

    if not args.skip_deprecation_warning:
        print("=" * 60)
        print("【废弃警告】phase1_generate_ro.py 已废弃！")
        print("=" * 60)
        print("请使用新的脚本：")
        print(f"  生成: python {GENERATE_SCRIPT} --family {args.family}")
        print(f"  可视化: python {PLOT_SCRIPT} --family {args.family} --plots all")
        print("=" * 60)
        print()

    print("=" * 60)
    print("Phase 1: 共振轨道(RO)族生成")
    print(f"e2m2e version: {e2m2e.__version__}")
    print("=" * 60)

    # 创建系统
    system = e2m2e.core.system.CR3BP_System(mu=MU, primary="earth", secondary="moon")
    system.compute_libration_points()
    dynamics = e2m2e.core.dynamics.CR3BP_Dynamics(system)
    dynamics.integrator = "DOP853"

    # print(f"\n系统: μ = {system.mu}")
    # if system.L1 is not None:
    #     print(f"L1: x = {system.L1[0]:.6f}")
    #     print(f"L2: x = {system.L2[0]:.6f}")

    ensure_output_dir()

    # ============================================================
    # 3:2 RO
    # ============================================================
    if args.family in ["32", "both"]:
        print(f"\n{'#' * 60}")
        print(f"# 3:2 RO")
        print(f"# 目标周期 T = {T_RO_32:.6f} ({T_RO_32 * TU:.2f} days)")
        print(f"{'#' * 60}")

        seed = RO_SEEDS["3:2"]
        print(f"\n使用论文Table 2的种子值:")
        print(f"  x0 = {seed['x0']:.6f}")
        print(f"  period = {seed['period']:.10f} TU ({seed['period'] * TU:.4f} days)")

        if args.run_continuation:
            # 步骤1: 使用论文y幅值点作为初始猜测，通过微分修正找到正确的y_dot0
            print(f"\n[步骤1] 使用论文值创建种子轨道并修正...")
            x0 = seed["x0"]
            y0 = seed["y0"]
            period = seed["period"]

            # 初始猜测：y幅值点处vy=0
            # 这个值获取的方法是，我先将这个值设置为零，然后进行微分校正，得到的就是这个值，
            # 这个值满足了我设置的收敛条件，然后后续的话我就以这个校正成功之后的值作为初值，这样能加快后续调试的进度，这也是比较合理的。
            y_dot0_initial = 0.58566

            # 创建初始状态（从y幅值点出发，vy=0）
            initial_state = [x0, y0, 0.0, 0.0, y_dot0_initial, 0.0]

            # 积分一个周期
            t_eval = np.linspace(0, period, 500)
            res = solve_ivp(
                dynamics.equations_of_motion,
                (0, period),
                initial_state,
                method="DOP853",
                t_eval=t_eval,
                rtol=1e-10,
                atol=1e-10,
            )

            if not res.success:
                print(f"\n[错误] 初始积分失败！")
            else:
                orbit = Orbit(res.y.T, res.t, system=system)
                orbit.period = period

                # 微分修正 - 固定x0，从y幅值点出发，自由变量为[y_dot0, T_half]
                corrector = e2m2e.algorithms.DifferentialCorrection(dynamics)
                corrector.setup_2D_symmetric_x_fixed_x0(x0)
                corrector.tolerance = 1e-12
                corrector.max_iterations = 50

                corrected_orbit = corrector.iterate_correction(orbit, verbose=True)

                if corrected_orbit is None or not corrected_orbit.correction_success:
                    print(f"\n[错误] 种子轨道修正失败！")
                else:
                    print(f"\n[成功] 种子轨道修正成功!")
                    print(f"  修正后周期: {corrected_orbit.period:.6f} TU")
                    print(
                        f"  修正后状态: x={corrected_orbit.states[0, 0]:.6f}, y={corrected_orbit.states[0, 1]:.6f}"
                    )
                    print(f"  修正后y_dot0={corrected_orbit.states[0, 4]:.6f}")

                    # 验证周期误差
                    period_error = abs(corrected_orbit.period - period) / period
                    print(f"  周期误差: {period_error:.2%}")

                    # 步骤2: 使用修正后的轨道作为种子进行延拓
                    print(f"\n[步骤2] 开始延拓...")

                    # 创建新的微分修正器用于延拓（与DRO相同配置）
                    corrector_for_cont = e2m2e.algorithms.DifferentialCorrection(
                        dynamics
                    )
                    corrector_for_cont.setup_2D_symmetric_x_fixed_x0(x0)
                    corrector_for_cont.tolerance = 1e-12
                    corrector_for_cont.max_iterations = 50

                    # 使用论文给的x0作为中心，向两侧延拓
                    # 计划文件 TASK-004：x0范围 [-1.2, -0.8]，步长 0.005
                    x0_range = (
                        -1.2,  # param_min
                        -0.8,  # param_max
                    )
                    continuation = e2m2e.algorithms.Continuation(
                        corrector_for_cont, param="x0"
                    )

                    family_result = continuation.natural_continuation(
                        corrected_orbit, x0_range, 0.005, verbose=False
                    )

                    if family_result is not None and len(family_result) > 0:
                        print(f"\n3:2 RO族生成: {len(family_result)} 条轨道")
                        save_family(system, family_result, FAMILY_FILENAME_32)
                        visualize_orbits(
                            system, family_result, "3:2", T_RO_32
                        )  # //TODO 这里的绘图代码需要继承到e2m2e的plotting类中，尽量进行代码复用
                    else:
                        print("\n3:2 RO族延拓失败")
        else:
            # 尝试加载已有的轨道族数据
            family_path = os.path.join(OUTPUT_DIR, FAMILY_FILENAME_32)
            if os.path.exists(family_path):
                print(f"\n加载已有3:2 RO轨道族: {family_path}")
                family_result = e2m2e.OrbitFamily.load_from_file(family_path)
                if family_result is not None and len(family_result) > 0:
                    family_result.system = system
                    for orbit in family_result:
                        if orbit.system is None:
                            orbit.system = system
                    print(f"  成功加载 {len(family_result)} 条轨道")
                    visualize_orbits(system, family_result, "3:2", T_RO_32)
                else:
                    print("  加载失败")
            else:
                print("\n跳过延拓（使用 --run-continuation 执行延拓）")

    # ============================================================
    # 3:1 RO
    # ============================================================
    if args.family in ["31", "both"]:
        print(f"\n{'#' * 60}")
        print(f"# 3:1 RO")
        print(f"# 目标周期 T = {T_RO_31:.6f} ({T_RO_31 * TU:.2f} days)")
        print(f"{'#' * 60}")

        seed = RO_SEEDS["3:1"]
        print(f"\n使用论文Table 2的种子值:")
        print(f"  x0 = {seed['x0']:.6f}")
        print(f"  period = {seed['period']:.10f} TU ({seed['period'] * TU:.4f} days)")

        if args.run_continuation:
            # 步骤1: 使用论文y幅值点作为初始猜测，通过微分修正找到正确的y_dot0
            print(f"\n[步骤1] 使用论文值创建种子轨道并修正...")
            x0 = seed["x0"]
            y0 = seed["y0"]
            period = seed["period"]

            # 初始猜测：y幅值点处vy=0
            y_dot0_initial = 0.0

            # 创建初始状态（从y幅值点出发，vy=0）
            initial_state = [x0, y0, 0.0, 0.0, y_dot0_initial, 0.0]

            # 积分一个周期
            t_eval = np.linspace(0, period, 500)
            res = solve_ivp(
                dynamics.equations_of_motion,
                (0, period),
                initial_state,
                method="DOP853",
                t_eval=t_eval,
                rtol=1e-10,
                atol=1e-10,
            )

            if not res.success:
                print(f"\n[错误] 初始积分失败！")
            else:
                orbit = Orbit(res.y.T, res.t, system=system)
                orbit.period = period

                # 微分修正 - 固定x0，从y幅值点出发，自由变量为[y_dot0, T_half]
                corrector = e2m2e.algorithms.DifferentialCorrection(dynamics)
                corrector.setup_2D_symmetric_x_fixed_x0(x0)
                corrector.tolerance = 1e-12
                corrector.max_iterations = 50

                corrected_orbit = corrector.iterate_correction(orbit, verbose=False)

                if corrected_orbit is None or not corrected_orbit.correction_success:
                    print(f"\n[错误] 种子轨道修正失败！")
                else:
                    print(f"\n[成功] 种子轨道修正成功!")
                    print(f"  修正后周期: {corrected_orbit.period:.6f} TU")
                    print(
                        f"  修正后状态: x={corrected_orbit.states[0, 0]:.6f}, y={corrected_orbit.states[0, 1]:.6f}"
                    )
                    print(f"  修正后y_dot0={corrected_orbit.states[0, 4]:.6f}")

                    # 验证周期误差
                    period_error = abs(corrected_orbit.period - period) / period
                    print(f"  周期误差: {period_error:.2%}")

                    # 步骤2: 使用修正后的轨道作为种子进行延拓
                    print(f"\n[步骤2] 开始延拓...")

                    # 创建新的微分修正器用于延拓
                    corrector_for_cont = e2m2e.algorithms.DifferentialCorrection(
                        dynamics
                    )
                    corrector_for_cont.setup_2D_symmetric_x_fixed_x0(x0)
                    corrector_for_cont.tolerance = 1e-12
                    corrector_for_cont.max_iterations = 50

                    # 使用x0作为中心，向两侧延拓
                    # 计划文件 TASK-005：x0范围 [-1.0, -0.7]，步长 0.005
                    x0_range = (
                        -1.0,  # param_min
                        -0.7,  # param_max
                    )
                    continuation = e2m2e.algorithms.Continuation(
                        corrector_for_cont, param="x0", step=0.005
                    )

                    family_result = continuation.natural_continuation(
                        corrected_orbit, x0_range, 0.005, verbose=True
                    )

                    if family_result is not None and len(family_result) > 0:
                        print(f"\n3:1 RO族生成: {len(family_result)} 条轨道")
                        save_family(system, family_result, FAMILY_FILENAME_31)
                        visualize_orbits(system, family_result, "3:1", T_RO_31)
                    else:
                        print("\n3:1 RO族延拓失败")
        else:
            # 尝试加载已有的轨道族数据
            family_path = os.path.join(OUTPUT_DIR, FAMILY_FILENAME_31)
            if os.path.exists(family_path):
                print(f"\n加载已有3:1 RO轨道族: {family_path}")
                family_result = e2m2e.OrbitFamily.load_from_file(family_path)
                if family_result is not None and len(family_result) > 0:
                    family_result.system = system
                    for orbit in family_result:
                        if orbit.system is None:
                            orbit.system = system
                    print(f"  成功加载 {len(family_result)} 条轨道")
                    visualize_orbits(system, family_result, "3:1", T_RO_31)
                else:
                    print("  加载失败")
            else:
                print("\n跳过延拓（使用 --run-continuation 执行延拓）")

    print(f"\n{'=' * 60}")
    print("完成！")
    print(f"{'=' * 60}")


# ============================================================
# 废弃说明
# ============================================================
# 本文件已废弃，功能已拆分为：
#   - generate_ro_family.py: 生成RO轨道族
#   - plot_ro_family.py: 可视化RO轨道族
#
# 请使用新的脚本：
#   python scripts/generate_ro_family.py --family both
#   python scripts/plot_ro_family.py --family both --plots all
# ============================================================


if __name__ == "__main__":
    main()
