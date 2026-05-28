"""轨道族生成器共享基类与配置。

从 ``dro/generate_dro_family.py`` 和 ``halo/generate_halo_family.py`` 中
提取的共享函数、配置数据类和基类。10 个存根族类型实现时可从此基类派生，
避免复制 ~300 行样板代码。

本模块当前仅提供共享工具——不修改任何现有消费者。迁移在各族独立的
切片中完成。
"""

from __future__ import annotations

import csv
import logging
import math
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import e2m2e
from e2m2e.core import CR3BP_Dynamics as _CR3BP_Dynamics
from e2m2e.core import CR3BP_System as _CR3BP_System
from e2m2e.core import Orbit, OrbitFamily
from tod.commons.constants import MU

logger = logging.getLogger(__name__)

# =============================================================================
# 共享常量
# =============================================================================

_LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
_DEFAULT_LOG_LEVEL = "WARNING"


def parse_log_level(level_str: str) -> int:
    """将日志级别字符串转为 logging 常量。"""
    return getattr(logging, level_str.upper(), logging.WARNING)


def setup_logging(level_str: str) -> None:
    """配置标准日志格式。"""
    logging.basicConfig(
        level=parse_log_level(level_str),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def find_project_root() -> Path:
    """从 ``tod/generates/cr3bp/_family_pipeline.py`` 向上走 5 级到项目根。"""
    return Path(__file__).resolve().parent.parent.parent.parent.parent


# =============================================================================
# 共享数学/工具函数（DRO 和 Halo 中逐字节相同）
# =============================================================================


def jacobi_constant(state: list[float]) -> float:
    """计算 CR3BP 伪无量纲状态的 Jacobi 常数。

    所有族生成器中此函数实现完全相同。集中在此处避免副本漂移。

    Args:
        state: 6 元素状态向量 [x, y, z, vx, vy, vz]（无量纲）。

    Returns:
        Jacobi 常数。
    """
    x, y, z = state[0], state[1], state[2]
    vx, vy, vz = state[3], state[4], state[5]
    r1 = math.sqrt((x - MU) ** 2 + y**2 + z**2)
    r2 = math.sqrt((x + 1 - MU) ** 2 + y**2 + z**2)
    Omega = (1 - MU) / r1 + MU / r2 + (x**2 + y**2) / 2
    v2 = vx**2 + vy**2 + vz**2
    return 2 * Omega - v2


def find_milestone_indices(n_orbits: int, n_milestones: int = 5) -> list[int]:
    """返回等间距里程碑轨道的索引列表。

    Args:
        n_orbits: 轨道族中的轨道总数。
        n_milestones: 要选取的里程碑数量。

    Returns:
        里程碑轨道在族中的索引列表。
    """
    return [
        round(i * (n_orbits - 1) / (n_milestones - 1)) for i in range(n_milestones)
    ]


# =============================================================================
# CR3BP 系统构建
# =============================================================================


def build_cr3bp_system(mu: float = MU) -> _CR3BP_System:
    """构建标准地月 CR3BP 系统对象。

    Args:
        mu: 质量比，默认地球-月球值。

    Returns:
        CR3BP_System 实例。
    """
    return _CR3BP_System(mu=mu, primary="earth", secondary="moon")


def build_cr3bp_dynamics(system: _CR3BP_System | None = None) -> _CR3BP_Dynamics:
    """构建标准 CR3BP 动力学对象。

    Args:
        system: CR3BP_System 实例；为 None 时使用默认地月系统。

    Returns:
        CR3BP_Dynamics 实例。
    """
    if system is None:
        system = build_cr3bp_system()
    return _CR3BP_Dynamics(system=system)


# =============================================================================
# 配置数据类
# =============================================================================


@dataclass
class FamilyGeneratorConfig:
    """轨道族生成的共享配置。

    Attributes:
        family_type: 族类型标识（如 ``"dro"``、``"halo"``）。
        output_subdir: ``output/`` 下的子目录名。
        summary_title: 摘要表标题模板（支持 ``{family_type}`` 等占位符）。
        summary_columns: 摘要表列名（不含固定列如周期误差）。
        csv_fieldnames: CSV 导出的字段名列表。
        csv_format_row: CSV 行格式化回调：``(orbit, index, is_milestone) -> dict``。
        summary_format_row: 摘要表行格式化回调：``(orbit) -> list[str]``。
        summary_extra_info: 摘要表额外的配置行（在统计块之后打印）。
    """

    family_type: str = ""
    output_subdir: str = ""
    summary_title: str = "  {family_type} 轨道族：配置、统计与代表性轨道"
    summary_columns: list[str] = field(default_factory=list)
    csv_fieldnames: list[str] = field(default_factory=list)
    csv_format_row: Callable[[Any, int, bool], dict[str, Any]] | None = None
    summary_format_row: Callable[[Any], list[str]] | None = None
    summary_extra_info: Callable[[], list[str]] | None = None
    n_milestones: int = 5


# =============================================================================
# 共享输出辅助
# =============================================================================


def print_summary_table(
    orbits: OrbitFamily,
    config: FamilyGeneratorConfig,
    *,
    mu: float = MU,
    extra_lines: list[str] | None = None,
) -> None:
    """打印论文风格的配置/统计/里程碑表格到控制台。

    泛化了 DRO 和 Halo 的 ``_print_summary_table``，通过
    ``FamilyGeneratorConfig`` 控制列和格式。

    Args:
        orbits: 轨道族。
        config: 族生成器配置。
        mu: 质量比（用于表头显示）。
        extra_lines: 额外的配置行（打印在统计块之后、里程碑表之前）。
    """
    if len(orbits) == 0:
        return

    # --- 统计摘要 ---
    periods = [o.period for o in orbits]
    errors = [o.periodicity_error for o in orbits if o.periodicity_error is not None]
    if not errors:
        errors = [0.0]
    seed_orbit = orbits[0]
    s_seed = seed_orbit.states[0]

    # --- 里程碑轨道 ---
    milestone_idx = find_milestone_indices(len(orbits), config.n_milestones)
    milestone_orbits = [orbits[i] for i in milestone_idx]

    # 打印标题
    title = config.summary_title.format(family_type=config.family_type.upper())
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)
    print()
    print("  配置与统计")
    print("  " + "-" * 68)
    print(f"  物理系统     Earth-Moon CR3BP  (mu = {mu})")
    print(f"  轨道类型     {config.family_type}")
    print(f"  轨道数量     {len(orbits)}")

    if extra_lines:
        for line in extra_lines:
            print(line)

    x0s = [o.states[0, 0] for o in orbits]
    print(f"  x0 范围     {min(x0s):.6f} ~ {max(x0s):.6f}")
    print(f"  周期范围     {min(periods):.4f} ~ {max(periods):.4f}")
    print(f"  终止条件     闭轨误差上界 (max = {max(errors):.2e})")

    if config.summary_extra_info is not None:
        for line in config.summary_extra_info():
            print(line)

    print()
    print("  代表性轨道（等间距采样）")
    print("  " + "-" * 68)

    # 表头
    header = "  " + " ".join(f"{col:^10}" for col in config.summary_columns) + f"  {'Periodicity Err':^14}"
    print(header)
    print("  " + "-" * 68)

    for o in milestone_orbits:
        if config.summary_format_row is None:
            continue
        row = config.summary_format_row(o)
        row_str = "  " + " ".join(f"{v:>10}" for v in row[:-1])
        row_str += f"  {float(o.periodicity_error or 0.0):14.2e}"
        print(row_str)

    print()
    print("=" * 72)
    print()


def export_csv(
    orbits: OrbitFamily,
    config: FamilyGeneratorConfig,
    output_dir: Path,
    *,
    filename_prefix: str | None = None,
    extra_filename_parts: list[str] | None = None,
) -> Path:
    """将全量轨道数据导出为 CSV，返回文件路径。

    泛化了 DRO 和 Halo 的 ``_export_csv``，通过 ``FamilyGeneratorConfig``
    控制字段和行格式。

    Args:
        orbits: 轨道族。
        config: 族生成器配置。
        output_dir: 输出目录。
        filename_prefix: CSV 文件名前缀（默认使用 ``config.family_type``）。
        extra_filename_parts: 额外的文件名片段。

    Returns:
        导出文件路径。
    """
    if config.csv_format_row is None:
        raise ValueError("csv_format_row callback is required for CSV export")

    milestone_idx = set(find_milestone_indices(len(orbits), config.n_milestones))

    rows = []
    for i, o in enumerate(orbits):
        row = config.csv_format_row(o, i, i in milestone_idx)
        rows.append(row)

    ts = int(time.time())
    prefix = filename_prefix or config.family_type
    parts = [prefix, str(ts)]
    if extra_filename_parts:
        parts = [prefix] + extra_filename_parts + [str(ts)]
    csv_path = output_dir / f"{'_'.join(parts)}.csv"

    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    return csv_path


# =============================================================================
# 调试入口
# =============================================================================


def inject_debug_args(
    argv: list[str],
    defaults: list[str],
    description: str = "使用代码内置调试参数",
) -> None:
    """IDE 调试模式：F5 直跑时注入默认命令行参数。

    所有族生成器脚本的 ``if __name__ == "__main__"`` 块中此模式完全相同。

    Args:
        argv: ``sys.argv`` 列表（会被原地修改）。
        defaults: 偶数长度的键值对列表。
        description: 调试信息。
    """
    if len(argv) == 1:
        argv += defaults
        logger.debug(description)


# =============================================================================
# 族生成器基类
# =============================================================================


class FamilyGenerator:
    """轨道族生成器基类。

    子类需要实现 ``_get_seed_orbit``、``_setup_corrector``、
    ``_run_continuation`` 等钩子方法，其余流程（系统初始化、保存、
    CSV 导出、摘要表打印）由基类处理。

    用法::

        class DroFamilyGenerator(FamilyGenerator):
            def _get_seed_orbit(self, args):
                ...
            def _setup_corrector(self, dynamics, args):
                ...
            def _run_continuation(self, continuation, seed_orbit, args):
                ...

        gen = DroFamilyGenerator(config)
        gen.run(args)
    """

    def __init__(self, config: FamilyGeneratorConfig) -> None:
        self.config = config
        self._system: _CR3BP_System | None = None
        self._dynamics: _CR3BP_Dynamics | None = None

    # ------------------------------------------------------------------
    # 共享流程（子类不应覆盖）
    # ------------------------------------------------------------------

    def init_system(self, mu: float = MU) -> None:
        """初始化 CR3BP 系统与动力学。"""
        self._system = build_cr3bp_system(mu=mu)
        self._dynamics = build_cr3bp_dynamics(self._system)

    @property
    def system(self) -> _CR3BP_System:
        if self._system is None:
            self.init_system()
        assert self._system is not None
        return self._system

    @property
    def dynamics(self) -> _CR3BP_Dynamics:
        if self._dynamics is None:
            self.init_system()
        assert self._dynamics is not None
        return self._dynamics

    def get_output_dir(self, project_root: Path | None = None) -> Path:
        """获取输出目录，必要时创建。

        Args:
            project_root: 项目根目录；为 None 时自动检测。

        Returns:
            输出目录路径。
        """
        if project_root is None:
            project_root = find_project_root()
        out = project_root / "output" / self.config.output_subdir
        out.mkdir(parents=True, exist_ok=True)
        return out

    # ------------------------------------------------------------------
    # 钩子方法（子类必须或可选覆盖）
    # ------------------------------------------------------------------

    def parse_args(self, argv: list[str] | None = None) -> Any:
        """解析命令行参数。

        子类必须覆盖此方法，返回 argparse.Namespace 或等效对象。
        """
        raise NotImplementedError("subclass must implement parse_args()")

    def _get_seed_orbit(self, args: Any) -> Orbit:
        """生成或加载种子轨道。

        子类必须覆盖此方法。
        """
        raise NotImplementedError("subclass must implement _get_seed_orbit()")

    def _setup_corrector(self, args: Any) -> Any:
        """创建并配置微分修正器。

        子类必须覆盖此方法。返回配置好的 DifferentialCorrection 实例。
        """
        raise NotImplementedError("subclass must implement _setup_corrector()")

    def _correct_seed_orbit(
        self, corrector: Any, seed_orbit: Orbit, args: Any
    ) -> Orbit | None:
        """对种子轨道执行微分修正。

        默认调用 ``corrector.iterate_correction``。子类可覆盖以自定义行为。

        Returns:
            修正后的轨道；若失败则返回 None。
        """
        return corrector.iterate_correction(initial_guess=seed_orbit)

    def _run_continuation(
        self, corrector: Any, seed_orbit: Orbit, args: Any
    ) -> OrbitFamily:
        """执行延拓生成轨道族。

        子类必须覆盖此方法。
        """
        raise NotImplementedError("subclass must implement _run_continuation()")

    def _format_csv_row(
        self, orbit: Any, index: int, is_milestone: bool
    ) -> dict[str, Any]:
        """格式化单条轨道的 CSV 行。

        默认使用 ``config.csv_format_row`` 回调。
        """
        if self.config.csv_format_row is None:
            raise ValueError("csv_format_row callback is required")
        return self.config.csv_format_row(orbit, index, is_milestone)

    # ------------------------------------------------------------------
    # 主流程
    # ------------------------------------------------------------------

    def run(self, args: Any, *, project_root: Path | None = None) -> OrbitFamily:
        """执行完整的族生成流水线。

        1. 初始化系统
        2. 生成/加载种子轨道
        3. 微分修正
        4. 延拓生成轨道族
        5. 保存 JSON + CSV
        6. 打印摘要表

        Args:
            args: 解析后的命令行参数。
            project_root: 项目根目录（可选）。

        Returns:
            生成的轨道族。
        """
        self.init_system()

        # 1. 种子轨道
        seed_orbit = self._get_seed_orbit(args)

        # 2. 微分修正
        corrector = self._setup_corrector(args)
        corrected = self._correct_seed_orbit(corrector, seed_orbit, args)
        if corrected is None:
            raise RuntimeError("种子轨道修正失败")

        # 3. 延拓
        family = self._run_continuation(corrector, corrected, args)
        logger.info("轨道族生成完成: 共 %d 条轨道", len(family))

        # 4. 保存
        output_dir = self.get_output_dir(project_root)
        ts = int(time.time())
        json_path = output_dir / f"{self.config.family_type}_family_{ts}.json"
        family.save_to_file(filename=str(json_path))

        csv_path = export_csv(family, self.config, output_dir)
        logger.info("已保存 JSON: %s", json_path)
        logger.info("已保存 CSV:  %s", csv_path)

        print(f"[3/3] 已保存：")
        print(f"  JSON: {json_path}")
        print(f"  CSV:  {csv_path}")

        # 5. 摘要表
        print_summary_table(family, self.config)
        return family
