import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.animation import FuncAnimation
from enum import Enum
import matplotlib.gridspec as gridspec


class ProjectionPlane(Enum):
    """投影平面枚举"""

    XY = "xy"
    XZ = "xz"
    YZ = "yz"


class PlotStyle(Enum):
    """绘图样式枚举"""

    LINE = "line"
    SCATTER = "scatter"
    SURFACE = "surface"
    WIREFRAME = "wireframe"
    CONTOUR = "contour"


class Visualization:
    """轨道可视化

    属性：
    - system: CR3BP_System对象
    - figure: matplotlib图形对象
    - axes: 坐标轴对象

    方法：
    - __init__(system): 初始化可视化器
    - plot_3D_orbit(orbit, color, label): 绘制3D轨道
    - plot_2D_projection(orbit, plane, color): 绘制2D投影
    - plot_libration_points(): 绘制平动点
    - plot_primary_bodies(): 绘制主天体
    - plot_poincare_section(orbits, plane): 绘制庞加莱截面
    - animate_orbits(orbits, filename): 轨道动画
    - setup_subplots(layout): 设置子图布局
    - save_figure(filename): 保存图形
    - plot_multiple_orbits(orbits, labels, colors): 绘制多个轨道
    - create_comparison_plot(orbits, titles): 创建对比图
    """

    # 类属性
    DEFAULT_FIGURE_SIZE = (12, 8)
    DEFAULT_DPI = 100
    DEFAULT_COLORMAP = "viridis"
    AVAILABLE_STYLES = ["default", "dark_background", "seaborn", "ggplot"]

    def __init__(self, system):
        """初始化可视化器

        参数：
        - system: CR3BP_System对象
        """
        # 关联系统
        self.system = system
        self.mu = system.mu if hasattr(system, "mu") else None

        # 图形对象
        self.figure = None  # 当前图形
        self.axes = None  # 当前坐标轴
        self.axes_3d = None  # 3D坐标轴
        self.subplots = []  # 子图列表
        self.current_ax = None  # 当前活动坐标轴

        # 图形设置
        self.figsize = self.DEFAULT_FIGURE_SIZE
        self.dpi = self.DEFAULT_DPI
        self.style = "default"
        self.colormap = self.DEFAULT_COLORMAP
        self.background_color = "white"

        # 轨道绘制设置
        self.orbit_linewidth = 1.5
        self.orbit_alpha = 0.8
        self.orbit_markersize = 2
        self.orbit_linestyle = "-"

        # 平动点设置
        self.libration_point_coords = {
            "L1": None,
            "L2": None,
            "L3": None,
            "L4": None,
            "L5": None,
        }
        self.libration_point_colors = ["red", "blue", "green", "purple", "orange"]
        self.libration_point_markers = ["o", "s", "^", "D", "*"]
        self.libration_point_sizes = [100, 100, 100, 150, 150]
        self.libration_point_labels = ["L1", "L2", "L3", "L4", "L5"]

        # 天体绘制设置
        self.primary_body_color = "gold"
        self.primary_body_size = 200
        self.secondary_body_color = "silver"
        self.secondary_body_size = 100
        self.body_edge_color = "black"
        self.body_edge_width = 1

        # 坐标轴设置
        self.axis_labels = {
            "x": "X (dimensionless)",
            "y": "Y (dimensionless)",
            "z": "Z (dimensionless)",
            "vx": "Vx (dimensionless)",
            "vy": "Vy (dimensionless)",
            "vz": "Vz (dimensionless)",
        }
        self.axis_limits = {}  # 坐标轴范围
        self.axis_equal = True  # 是否等比例
        self.show_grid = True
        self.grid_alpha = 0.3
        self.grid_linestyle = "--"

        # 图例设置
        self.show_legend = True
        self.legend_location = "best"
        self.legend_fontsize = 10
        self.legend_frame = True

        # 标题和标签
        self.title = None
        self.title_fontsize = 14
        self.label_fontsize = 12
        self.tick_fontsize = 10

        # 动画设置
        self.animation_fps = 30
        self.animation_blit = True
        self.animation_interval = 50
        self.animation_repeat = True
        self.animation_save_kwargs = {}

        # 颜色相关
        self.color_cycle = plt.rcParams["axes.prop_cycle"].by_key()["color"]
        self.color_index = 0
        self.colorbar = None
        self.colorbar_label = ""

        # 文本标注
        self.annotations = []  # 文本标注列表
        self.text_objects = []  # 文本对象列表
        self.annotation_style = {
            "fontsize": 10,
            "bbox": {"boxstyle": "round", "facecolor": "wheat", "alpha": 0.5},
        }

        # 缓存
        self.plot_cache = {}  # 绘图对象缓存
        self.orbit_plots = []  # 轨道绘图对象列表
        self.point_plots = []  # 点绘图对象列表

        # 输出设置
        self.save_format = "png"  # 保存格式
        self.save_transparent = False  # 透明背景
        self.save_bbox_inches = "tight"
        self.save_pad_inches = 0.1

        # 交互设置
        self.interactive = True
        self.pickable = False
        self.pick_tolerance = 5  # 拾取容差

        # 统计信息
        self.plot_count = 0
        self.orbit_count = 0
        self.animation_count = 0

        # 初始化平动点坐标
        self._init_libration_points()

    def _init_libration_points(self):
        """初始化平动点坐标"""
        if self.mu is not None:
            # L1, L2, L3 需要数值解，这里使用近似值
            # 更精确的值可以通过数值方法求解
            self.libration_point_coords = {
                "L1": np.array([0.8369, 0, 0]),
                "L2": np.array([1.1557, 0, 0]),
                "L3": np.array([-1.0051, 0, 0]),
                "L4": np.array([0.5 - self.mu, np.sqrt(3) / 2, 0]),
                "L5": np.array([0.5 - self.mu, -np.sqrt(3) / 2, 0]),
            }

    def plot_3D_orbit(self, orbit, color=None, label=None, ax=None, show_start=True):
        """绘制3D轨道

        参数：
            orbit (Orbit): 轨道对象
            color (str): 轨道颜色
            label (str): 轨道标签
            ax: matplotlib 3D坐标轴
            show_start (bool): 是否标记起点

        返回：
            ax: 绘图的坐标轴
        """
        if ax is None:
            if self.axes_3d is None:
                self.figure = plt.figure(figsize=self.figsize, dpi=self.dpi)
                self.axes_3d = self.figure.add_subplot(111, projection="3d")
            ax = self.axes_3d
        else:
            self.axes_3d = ax

        # 提取轨道数据
        states = orbit.states
        if isinstance(states, list):
            states = np.array(states)

        if states.ndim == 1:  # 单个状态
            states = states.reshape(1, -1)

        x = states[:, 0]
        y = states[:, 1]
        z = states[:, 2]

        # 自动选择颜色
        if color is None:
            color = self.color_cycle[self.color_index % len(self.color_cycle)]
            self.color_index += 1

        # 绘制轨道
        line = ax.plot(
            x,
            y,
            z,
            color=color,
            label=label,
            linewidth=self.orbit_linewidth,
            alpha=self.orbit_alpha,
            linestyle=self.orbit_linestyle,
        )[0]

        self.orbit_plots.append(line)

        # 标记起点
        if show_start and len(x) > 0:
            ax.scatter(
                x[0],
                y[0],
                z[0],
                color=color,
                marker="o",
                s=50,
                edgecolors="black",
                linewidth=1,
                label=f"{label} start" if label else "start",
            )

        self.orbit_count += 1
        self.plot_count += 1

        return ax

    def plot_2D_projection(
        self,
        orbit,
        plane=ProjectionPlane.XY,
        color=None,
        label=None,
        ax=None,
        show_start=True,
    ):
        """绘制2D投影

        参数：
            orbit (Orbit): 轨道对象
            plane (ProjectionPlane): 投影平面
            color (str): 轨道颜色
            label (str): 轨道标签
            ax: matplotlib坐标轴
            show_start (bool): 是否标记起点

        返回：
            ax: 绘图的坐标轴
        """
        if ax is None:
            if self.axes is None:
                self.figure, self.axes = plt.subplots(
                    1, 1, figsize=self.figsize, dpi=self.dpi
                )
            ax = self.axes
        else:
            self.axes = ax

        # 提取轨道数据
        states = orbit.states
        if isinstance(states, list):
            states = np.array(states)

        if states.ndim == 1:
            states = states.reshape(1, -1)

        x = states[:, 0]
        y = states[:, 1]
        z = states[:, 2]

        # 自动选择颜色
        if color is None:
            color = self.color_cycle[self.color_index % len(self.color_cycle)]
            self.color_index += 1

        # 根据投影平面选择坐标
        if plane == ProjectionPlane.XY:
            proj_x, proj_y = x, y
            xlabel, ylabel = "X", "Y"
        elif plane == ProjectionPlane.XZ:
            proj_x, proj_y = x, z
            xlabel, ylabel = "X", "Z"
        elif plane == ProjectionPlane.YZ:
            proj_x, proj_y = y, z
            xlabel, ylabel = "Y", "Z"
        else:
            raise ValueError(f"未知投影平面: {plane}")

        # 绘制投影
        line = ax.plot(
            proj_x,
            proj_y,
            color=color,
            label=label,
            linewidth=self.orbit_linewidth,
            alpha=self.orbit_alpha,
            linestyle=self.orbit_linestyle,
        )[0]

        self.orbit_plots.append(line)

        # 标记起点
        if show_start and len(proj_x) > 0:
            ax.scatter(
                proj_x[0],
                proj_y[0],
                color=color,
                marker="o",
                s=50,
                edgecolors="black",
                linewidth=1,
                label=f"{label} start" if label else "start",
            )

        # 设置坐标轴标签
        ax.set_xlabel(
            self.axis_labels.get(xlabel.lower(), xlabel), fontsize=self.label_fontsize
        )
        ax.set_ylabel(
            self.axis_labels.get(ylabel.lower(), ylabel), fontsize=self.label_fontsize
        )

        if self.show_grid:
            ax.grid(True, alpha=self.grid_alpha, linestyle=self.grid_linestyle)

        if self.axis_equal and plane == ProjectionPlane.XY:
            ax.set_aspect("equal")

        self.orbit_count += 1
        self.plot_count += 1

        return ax

    def plot_libration_points(self, ax=None, show_labels=True):
        """绘制平动点

        参数：
            ax: matplotlib坐标轴
            show_labels (bool): 是否显示标签

        返回：
            ax: 绘图的坐标轴
        """
        if ax is None:
            if self.axes_3d is not None:
                ax = self.axes_3d
            elif self.axes is not None:
                ax = self.axes
            else:
                self.figure, self.axes = plt.subplots(
                    1, 1, figsize=self.figsize, dpi=self.dpi
                )
                ax = self.axes

        is_3d = hasattr(ax, "projection") and ax.name == "3d"

        for i, (label, coord) in enumerate(self.libration_point_coords.items()):
            if coord is None:
                continue

            color = self.libration_point_colors[i % len(self.libration_point_colors)]
            marker = self.libration_point_markers[i % len(self.libration_point_markers)]
            size = self.libration_point_sizes[i % len(self.libration_point_sizes)]

            if is_3d:
                scatter = ax.scatter(
                    coord[0],
                    coord[1],
                    coord[2],
                    c=color,
                    marker=marker,
                    s=size,
                    edgecolors="black",
                    linewidth=1,
                    label=label if show_labels else None,
                )
            else:
                scatter = ax.scatter(
                    coord[0],
                    coord[1],
                    c=color,
                    marker=marker,
                    s=size,
                    edgecolors="black",
                    linewidth=1,
                    label=label if show_labels else None,
                )

            self.point_plots.append(scatter)

        return ax

    def plot_primary_bodies(self, ax=None):
        """绘制主天体

        参数：
            ax: matplotlib坐标轴

        返回：
            ax: 绘图的坐标轴
        """
        if ax is None:
            if self.axes_3d is not None:
                ax = self.axes_3d
            elif self.axes is not None:
                ax = self.axes
            else:
                self.figure, self.axes = plt.subplots(
                    1, 1, figsize=self.figsize, dpi=self.dpi
                )
                ax = self.axes

        is_3d = hasattr(ax, "projection") and ax.name == "3d"

        # 主天体位置 (地球)
        primary_pos = np.array([-self.mu, 0, 0])

        # 次天体位置 (月球)
        secondary_pos = np.array([1 - self.mu, 0, 0])

        if is_3d:
            # 绘制地球
            ax.scatter(
                primary_pos[0],
                primary_pos[1],
                primary_pos[2],
                c=self.primary_body_color,
                marker="o",
                s=self.primary_body_size,
                edgecolors=self.body_edge_color,
                linewidth=self.body_edge_width,
                label="Earth",
            )

            # 绘制月球
            ax.scatter(
                secondary_pos[0],
                secondary_pos[1],
                secondary_pos[2],
                c=self.secondary_body_color,
                marker="o",
                s=self.secondary_body_size,
                edgecolors=self.body_edge_color,
                linewidth=self.body_edge_width,
                label="Moon",
            )
        else:
            # 绘制地球
            ax.scatter(
                primary_pos[0],
                primary_pos[1],
                c=self.primary_body_color,
                marker="o",
                s=self.primary_body_size,
                edgecolors=self.body_edge_color,
                linewidth=self.body_edge_width,
                label="Earth",
            )

            # 绘制月球
            ax.scatter(
                secondary_pos[0],
                secondary_pos[1],
                c=self.secondary_body_color,
                marker="o",
                s=self.secondary_body_size,
                edgecolors=self.body_edge_color,
                linewidth=self.body_edge_width,
                label="Moon",
            )

        return ax

    def plot_poincare_section(self, orbits, plane=ProjectionPlane.XY, value=0):
        """绘制庞加莱截面"""
        print("庞加莱截面功能待实现")
        return None

    def animate_orbits(self, orbits, filename):
        """轨道动画"""
        print("动画功能待实现")
        return None

    def setup_subplots(self, layout):
        """设置子图布局

        参数：
            layout (tuple): (rows, cols) 行数和列数

        返回：
            axes: 子图坐标轴数组
        """
        rows, cols = layout
        self.figure, self.subplots = plt.subplots(
            rows, cols, figsize=self.figsize, dpi=self.dpi
        )
        self.axes = self.subplots
        return self.subplots

    def save_figure(self, filename):
        """保存图形

        参数：
            filename (str): 文件名
        """
        if self.figure is None:
            print("没有可保存的图形")
            return

        self.figure.savefig(
            filename,
            format=self.save_format,
            transparent=self.save_transparent,
            bbox_inches=self.save_bbox_inches,
            pad_inches=self.save_pad_inches,
            dpi=self.dpi,
        )
        print(f"图形已保存到: {filename}")

    def plot_multiple_orbits(
        self,
        orbits,
        labels=None,
        colors=None,
        plane=ProjectionPlane.XY,
        ax=None,
        show_start=True,
    ):
        """绘制多个轨道

        参数：
            orbits (list): 轨道对象列表
            labels (list): 标签列表
            colors (list): 颜色列表
            plane (ProjectionPlane): 投影平面
            ax: matplotlib坐标轴
            show_start (bool): 是否标记起点

        返回：
            ax: 绘图的坐标轴
        """
        if ax is None:
            if self.axes is None:
                self.figure, self.axes = plt.subplots(
                    1, 1, figsize=self.figsize, dpi=self.dpi
                )
            ax = self.axes

        for i, orbit in enumerate(orbits):
            label = labels[i] if labels and i < len(labels) else f"Orbit {i + 1}"
            color = colors[i] if colors and i < len(colors) else None

            self.plot_2D_projection(
                orbit,
                plane=plane,
                color=color,
                label=label,
                ax=ax,
                show_start=show_start,
            )

        if self.show_legend:
            ax.legend(
                loc=self.legend_location,
                fontsize=self.legend_fontsize,
                frameon=self.legend_frame,
            )

        if self.title:
            ax.set_title(self.title, fontsize=self.title_fontsize)

        return ax

    def create_comparison_plot(self, orbits, titles=None, layout=(2, 2)):
        """创建对比图

        参数：
            orbits (list): 轨道对象列表
            titles (list): 子图标题列表
            layout (tuple): 子图布局 (rows, cols)

        返回：
            axes: 子图坐标轴数组
        """
        rows, cols = layout
        self.setup_subplots(layout)
        axes = (
            self.subplots
            if isinstance(self.subplots, np.ndarray)
            else np.array([self.subplots])
        )
        axes = axes.flatten()

        for i, orbit in enumerate(orbits):
            if i >= len(axes):
                break

            ax = axes[i]
            self.plot_2D_projection(orbit, ax=ax, show_start=True)
            self.plot_libration_points(ax=ax)
            self.plot_primary_bodies(ax=ax)

            if titles and i < len(titles):
                ax.set_title(titles[i], fontsize=self.title_fontsize)
            else:
                ax.set_title(f"Orbit {i + 1}", fontsize=self.title_fontsize)

        plt.tight_layout()
        return axes

    def show(self):
        """显示图形"""
        if self.figure:
            plt.show()
        else:
            print("没有可显示的图形")

    def close(self):
        """关闭图形"""
        if self.figure:
            plt.close(self.figure)
            self.figure = None
            self.axes = None
            self.axes_3d = None
            self.subplots = []
            self.orbit_plots = []
            self.point_plots = []
