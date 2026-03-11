"""
阶段一：任务轨道生成 — DRO族

生成完整的Distant Retrograde Orbit (DRO)族，计算Jacobi常数与稳定性指标。

参考论文：
  Cui et al. (2025) "Two-Impulse Transfers from Lunar Distant Retrograde Orbits
  to Resonant Orbits", JGCD, Vol.48, No.6

DRO是月球远距离逆行轨道（Broucke Family F），具有以下对称性：
  - 关于x轴对称
  - 初始状态 [x0, 0, 0, 0, vy0, 0]，其中vy0 < 0（逆行）
  - 半周期条件：y(T/2) = 0, vx(T/2) = 0

论文参数：
  μ = 1.21506683 × 10⁻² (地月系统质量比)
  DU = 3.84405 × 10⁵ km, TU = 4.34811305 天

用法：
  python phase1_generate_dro.py           # 默认：重新计算
  python phase1_generate_dro.py --load    # 加载已有数据
  python phase1_generate_dro.py --load dro_family_20260311  # 加载指定数据
"""

import argparse
import datetime
import os

import matplotlib
import e2m2e
from e2m2e.core import Orbit, OrbitFamily
import numpy as np

# matplotlib.use("Agg")  # 非交互式后端，用于服务器环境或批量处理时避免图形界面

# ============================================================
# 系统参数（论文Table 1）
# ============================================================
# 地月系统质量比，μ = m2/(m1+m2)，其中m1为地球质量，m2为月球质量
MU = 1.21506683e-2  # Mass ratio of the Earth–moon system

# 太阳的无量纲质量，用于后续考虑太阳引力摄动
M_SUN = 3.28900541e5  # Nondimensional mass of the sun

# 太阳的无量纲角速度，描述太阳在旋转坐标系中的运动
OMEGA_SUN = 9.25195985e-1  # Nondimensional angular velocity of the sun

# 太阳到地月系统的无量纲距离
RHO = 3.88811143e2  # Nondimensional sun–(Earth–moon) distance

# 距离单位：1 DU = 384405 km，地月平均距离
DU = 3.84405000e5  # Distance unit km

# 时间单位：1 TU = 4.34811305 天，地月系统的特征时间尺度
TU = 4.34811305  # Time unit days

# 速度单位：1 VU = 1023.23281 m/s，基于DU和TU计算得出
VU = 1023.23281  # Velocity unit m/s

# 输出目录配置
OUTPUT_DIR = "output/phase1_dro"
FAMILY_FILENAME = "dro_family.json"  # 轨道族统一文件名


# ============================================================
# 辅助函数
# ============================================================
def ensure_output_dir():
    """确保输出目录存在"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def get_latest_family_file():
    """获取最新的轨道族数据文件"""
    if not os.path.exists(OUTPUT_DIR):
        return None

    family_path = os.path.join(OUTPUT_DIR, FAMILY_FILENAME)
    if os.path.exists(family_path):
        return family_path

    # 兼容旧格式：查找带时间戳的文件夹
    dirs = [
        d for d in os.listdir(OUTPUT_DIR) if os.path.isdir(os.path.join(OUTPUT_DIR, d))
    ]
    if not dirs:
        return None

    # 按修改时间排序，返回最新的
    dirs.sort(key=lambda x: os.path.getmtime(os.path.join(OUTPUT_DIR, x)), reverse=True)
    latest_dir = dirs[0]
    return os.path.join(OUTPUT_DIR, latest_dir, FAMILY_FILENAME)


def load_or_compute(args):
    """加载或计算轨道族

    参数：
        args: 命令行参数

    返回：
        system: CR3BP_System对象
        family_result: OrbitFamily对象或None
    """
    system = e2m2e.core.system.CR3BP_System(mu=MU, primary="earth", secondary="moon")

    # 加载模式
    if args.load:
        if args.load == True:
            # 未指定具体文件，查找最新的
            family_path = get_latest_family_file()
        else:
            # 指定了文件名（可能是完整路径或相对路径）
            if os.path.isabs(args.load):
                family_path = args.load
            else:
                # 可能是 output/phase1_dro/xxx 或直接文件名
                if os.path.exists(args.load):
                    family_path = args.load
                else:
                    family_path = os.path.join(OUTPUT_DIR, args.load, FAMILY_FILENAME)

        if family_path and os.path.exists(family_path):
            print(f"加载轨道族数据: {family_path}")
            family_result = OrbitFamily.load_from_file(family_path, system)
            print(f"已加载 {len(family_result)} 条轨道")
            return system, family_result
        else:
            print(f"未找到数据文件: {family_path}")
            print("将重新计算...")

    return system, None


def compute_dro_family(system):
    """计算DRO轨道族

    参数：
        system: CR3BP_System对象

    返回：
        seed_DRO: 修正后的种子轨道
        family_result: OrbitFamily对象
    """
    # 创建动力学模型，用于计算状态转移矩阵和微分方程
    dynamic = e2m2e.core.dynamics.CR3BP_Dynamics(system)

    # 创建微分修正器，用于将近似轨道修正为精确周期轨道
    corrector = e2m2e.algorithms.DifferentialCorrection(dynamic)

    # 设置2D对称轨道修正模式：固定x0，修正其他参数
    # 这种模式适用于关于x轴对称的轨道，如DRO
    x0 = 0.79188556619742  # 初始x坐标（无量纲）
    corrector.setup_2D_symmetric_x_fixed_x0(x0)

    # 2. 生成DRO族
    # 设置初值：基于论文或前期计算结果
    vy0 = 0.53682  # 初始y方向速度（无量纲）

    # 初始状态向量：[x, y, z, vx, vy, vz]
    # 对于2D对称DRO：y=0, z=0, vx=0, vz=0
    initial_state = [x0, 0.0, 0.0, 0.0, vy0, 0.0]
    times = [
        0
    ]  # Orbit对象初始化所需的时间与对应索引的state一一对应。在实际数据处理中，times的元素为时间历元格式，此处用0表示第一个历元。
    seed_state = Orbit([initial_state], times)
    seed_state.period = (
        3.472526005624708  # 初始半周期猜测（无量纲时间），基于论文或前期计算结果
    )

    # 修正种子轨道后，将修正后的状态和半周期传递给延拓器
    seed_DRO = corrector.iterate_correction(seed_state)
    if seed_DRO is None:
        raise RuntimeError("种子DRO修正失败")

    continuation = e2m2e.algorithms.Continuation(corrector, param="x0", step=0.02)

    # 使用param_range参数进行参数区间延拓
    family_result = continuation.natural_continuation(
        seed_DRO,
        (0.7, 0.79188556619742),  # x0参数范围 //TODO 目前这里无法区分正向延拓和反向延拓，步长只能在原有基础上增加，不能减小
        0.001,  # 延拓步长
        False,
    )

    return seed_DRO, family_result


def save_family(system, family_result, seed_orbit=None):
    """保存轨道族到文件

    参数：
        system: CR3BP_System对象
        family_result: OrbitFamily对象
        seed_orbit: 种子轨道（可选）
    """
    ensure_output_dir()

    # 生成时间戳作为子目录名
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    family_dir = os.path.join(OUTPUT_DIR, timestamp)
    os.makedirs(family_dir, exist_ok=True)

    # 保存轨道族（统一文件）
    family_path = os.path.join(family_dir, FAMILY_FILENAME)
    family_result.save_to_file(family_path)
    print(f"轨道族已保存: {family_path}")

    # 同时保存到 latest 链接（创建符号链接的替代方案：复制）
    latest_path = os.path.join(OUTPUT_DIR, FAMILY_FILENAME)
    import shutil

    shutil.copy(family_path, latest_path)
    print(f"最新轨道族: {latest_path}")

    return family_dir


# 目标DRO
# 论文中作者是通过初值猜测和延拓法得到了DRO轨道组，然后在轨道族中找到了周期接近2:1和3:1的DRO。
# 我们也将采用同样的策略。
#
# DRO轨道特点：
# 1. 逆行轨道（retrograde），相对于月球运动方向相反
# 2. 距离较远（distant），通常位于月球轨道之外
# 3. 具有周期性，在旋转坐标系中闭合
# 4. 关于x轴对称，满足对称性条件
#
# 算法原理：
# 1. 微分修正法（Differential Correction）：通过迭代修正初始状态，使轨道满足周期条件
# 2. 对称性条件：对于2D对称DRO，满足 y(0)=0, vx(0)=0, y(T/2)=0, vx(T/2)=0
# 3. 自然延拓法（Natural Continuation）：从一个已知解出发，通过参数连续变化得到轨道族
#
# 关键参数：
# - Jacobi常数（Cj）：运动积分，表征轨道能量
# - 稳定性指标：通过单值矩阵特征值判断轨道稳定性
# - 共振比：轨道周期与月球轨道周期的比值


# ============================================================
# 主程序
# ============================================================
def main(args=None):
    """
    主函数：生成DRO轨道族

    步骤：
    1. 创建CR3BP系统
    2. 设置微分修正器
    3. 提供初始猜测
    4. 进行微分修正得到精确的DRO轨道
    5. 可视化结果
    """
    # 解析命令行参数
    if args is None:
        parser = create_parser()
        args = parser.parse_args()

    # 确保输出目录存在
    ensure_output_dir()

    # 加载或计算轨道族
    system, family_result = load_or_compute(args)

    # 如果没有加载到数据，则计算
    if family_result is None:
        print("开始计算DRO轨道族...")
        seed_DRO, family_result = compute_dro_family(system)
        print(f"计算完成，共生成 {len(family_result)} 条轨道")

        # 保存结果
        seed_orbit = family_result[0] if len(family_result) > 0 else None
        save_family(system, family_result, seed_orbit)
    else:
        # 使用加载的数据
        seed_orbit = family_result[0] if len(family_result) > 0 else None

    # 打印轨道信息
    print(f"\nDRO轨道族信息：")
    print(f"  轨道数量: {len(family_result)}")
    if seed_orbit is not None:
        print(
            f"  种子轨道周期: {seed_orbit.period:.6f} TU ({seed_orbit.period * TU:.4f} 天)"
        )
    if len(family_result) > 0:
        print(
            f"  最后一轨周期: {family_result.periods[-1]:.6f} TU ({family_result.periods[-1] * TU:.4f} 天)"
        )

    # 3. 可视化结果
    visualize_orbits(system, family_result)

    print("\n处理完成!")


def visualize_orbits(system, family_result):
    """可视化轨道族

    参数：
        system: CR3BP_System对象
        family_result: OrbitFamily对象
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

    # 获取颜色映射
    n_orbits = len(family_result) if family_result is not None else 0

    # family_result 现在是 OrbitFamily 对象
    # 延拓后的 Orbit 对象已经包含完整积分的轨道数据，可以直接用于可视化
    # 绘制种子DRO（使用延拓结果的第一条轨道）
    if family_result is not None and n_orbits > 0:
        seed_orbit = family_result[0]
        orbit_plotter.plot_2d_projection(
            seed_orbit, plane="xy", color="red", label="Seed DRO"
        )

    # 绘制延拓轨道族（所有轨道）
    if family_result is not None and n_orbits > 1:
        import matplotlib.pyplot as plt
        cmap = plt.cm.get_cmap("viridis")

        # 从第2条轨道开始绘制（第1条是种子轨道）
        for idx in range(1, n_orbits):
            orbit = family_result[idx]
            # 使用颜色映射，每条轨道使用不同的颜色
            color = cmap(idx / max(n_orbits - 1, 1))
            orbit_plotter.plot_2d_projection(
                orbit,
                plane="xy",
                color=color,
                show_start=False,  # 关闭起点标记，避免图例过于拥挤
            )

    # 添加主次天体（地球和月球）到图中
    orbit_plotter.plot_primary_bodies(ax=orbit_plotter.axes)

    # 添加拉格朗日点（平动点）到图中
    orbit_plotter.plot_libration_points(ax=orbit_plotter.axes)

    # 坐标轴标签和图例
    ax = orbit_plotter.axes
    ax.set_xlabel("X (nondimensional)", fontsize=12)
    ax.set_ylabel("Y (nondimensional)", fontsize=12)
    ax.set_title(f"DRO Family in Earth-Moon CR3BP (XY Plane) - {n_orbits} orbits", fontsize=14)
    ax.legend(loc="upper right", fontsize=8)

    # 显示图形
    orbit_plotter.show()


def create_parser():
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description="阶段一：DRO轨道族生成",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python phase1_generate_dro.py           # 重新计算DRO轨道族
  python phase1_generate_dro.py --load     # 加载最新的轨道数据
  python phase1_generate_dro.py --load 20260311_120000  # 加载指定日期的数据
        """,
    )
    parser.add_argument(
        "--load",
        nargs="?",
        const=True,
        default=False,
        help="加载已有数据，不重新计算。可指定具体日期时间戳",
    )
    parser.add_argument(
        "--output-dir", default=OUTPUT_DIR, help=f"输出目录 (默认: {OUTPUT_DIR})"
    )
    return parser


if __name__ == "__main__":
    """
    程序入口点
    当直接运行此脚本时执行main()函数
    """
    parser = create_parser()
    args = parser.parse_args()
    main(args)
