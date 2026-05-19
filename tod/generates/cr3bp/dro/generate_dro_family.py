"""
生成远距离逆行轨道族

本脚本实现：
1. 创建CR3BP系统和动力学模型
2. 设置DRO种子轨道的初始状态向量
3. 利用差分修正器修正种子轨道
4. 采用自然延拓方法生成完整轨道族

"""

import argparse
import csv
import logging
import math
import sys
import threading
import time
from pathlib import Path

import e2m2e
from e2m2e.core import Orbit
from tod.commons.common import MU

_LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
_DEFAULT_LOG_LEVEL = "WARNING"

project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
OUTPUT_DIR = project_root / "output" / "dro"


def _parse_log_level(level_str: str) -> int:
    return getattr(logging, level_str.upper(), logging.WARNING)


def parse_args():
    parser = argparse.ArgumentParser(description="生成 DRO 轨道族（差分修正 + 自然延拓）")
    parser.add_argument("--x0", type=float, default=0.79188556619742,
                        help="种子轨道初始 x 坐标（无量纲）")
    parser.add_argument("--vy0", type=float, default=0.53682,
                        help="种子轨道初始 vy 速度（无量纲）")
    parser.add_argument("--period", type=float, default=3.472526005624708,
                        help="初始周期猜测（无量纲）")
    parser.add_argument("--param-min", type=float, default=0.141886,
                        help="延拓参数范围下限（x0 最小值）")
    parser.add_argument("--param-max", type=float, default=0.9,
                        help="延拓参数范围上限（x0 最大值）")
    parser.add_argument("--step-size", type=float, default=0.005,
                        help="延拓步长")
    parser.add_argument("--log-level", type=str, default=_DEFAULT_LOG_LEVEL,
                        choices=_LOG_LEVELS,
                        help="日志级别")
    parser.add_argument("--verbose", action="store_true",
                        help="显示详细延拓过程（每步迭代、收敛进度等）")
    return parser.parse_args()


def _setup_logging(level_str: str) -> None:
    logging.basicConfig(
        level=_parse_log_level(level_str),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
logger = logging.getLogger(__name__)


class _ProgressTracker:
    """进度跟踪器：独立线程定期打印延拓进度。"""

    def __init__(self, total: int, interval: float = 2.0):
        self.total = total
        self.current = 0
        self._stop = False
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, args=(interval,), daemon=True)

    def start(self) -> None:
        self._thread.start()

    def update(self, count: int) -> None:
        with self._lock:
            self.current = count

    def stop(self) -> None:
        self._stop = True
        self._thread.join(timeout=5.0)

    def _run(self, interval: float) -> None:
        while not self._stop:
            time.sleep(interval)
            with self._lock:
                if self.current > 0 and not self._stop:
                    pct = self.current / self.total * 100 if self.total > 0 else 0
                    print(f"\r[2/3] 延拓进度: {self.current}/{self.total} ({pct:.0f}%)", end="", flush=True)
        print()  # 换行


def _jacobi_constant(state: list[float]) -> float:
    """计算 CR3BP 伪无量纲状态的 Jacobi 常数。"""
    x, y, z = state[0], state[1], state[2]
    vx, vy, vz = state[3], state[4], state[5]
    r1 = math.sqrt((x - MU) ** 2 + y ** 2 + z ** 2)
    r2 = math.sqrt((x + 1 - MU) ** 2 + y ** 2 + z ** 2)
    Omega = (1 - MU) / r1 + MU / r2 + (x ** 2 + y ** 2) / 2
    v2 = vx ** 2 + vy ** 2 + vz ** 2
    return 2 * Omega - v2


def _find_milestone_indices(n_orbits: int, n_milestones: int = 5) -> list[int]:
    """返回等间距里程碑轨道的索引列表。"""
    return [round(i * (n_orbits - 1) / (n_milestones - 1)) for i in range(n_milestones)]


def _print_summary_table(orbits: list, param_min: float, param_max: float,
                         step_size: float, n_milestones: int = 5) -> None:
    """打印论文风格的配置/统计/里程碑表格到控制台。"""
    # --- 统计摘要 ---
    periods = [o.period for o in orbits]
    x0s = [o.states[0, 0] for o in orbits]
    errors = [o.periodicity_error for o in orbits if o.periodicity_error is not None]
    if not errors:
        errors = [0.0]
    seed_orbit = next(o for o in orbits if o.metadata.get("continuation_step") == 0)
    s_seed = seed_orbit.states[0]

    # --- 里程碑轨道 ---
    milestone_idx = _find_milestone_indices(len(orbits), n_milestones)
    milestone_orbits = [orbits[i] for i in milestone_idx]

    # 计算里程碑 Jacobi 常数
    for i, o in zip(milestone_idx, milestone_orbits):
        o._c_jacobi = _jacobi_constant(o.states[0])

    # 打印配置与统计区块
    print()
    print("=" * 72)
    print("  Earth-Moon DRO 轨道族：配置、统计与代表性轨道")
    print("=" * 72)
    print()
    print("  配置与统计")
    print("  " + "-" * 68)
    print(f"  物理系统     Earth-Moon CR3BP  (mu = {MU})")
    print(f"  轨道类型     Distant Retrograde Orbit (DRO)")
    print(f"  轨道数量     {len(orbits)}")
    print(f"  种子 x0      {s_seed[0]:.8f}")
    print(f"  种子 vy0     {s_seed[4]:.5f}")
    print(f"  种子周期     {seed_orbit.period:.10f}")
    print(f"  延拓参数     x0 in [{param_min:.6f}, {param_max:.6f}]")
    print(f"  延拓步长     {step_size}")
    print(f"  周期范围     {min(periods):.4f} ~ {max(periods):.4f}")
    print(f"  终止条件     参数边界 / 闭轨误差上界 (max = {max(errors):.2e})")
    print()
    print("  代表性轨道（等间距采样）")
    print("  " + "-" * 68)
    header = (f"  {'x0':^10} {'Period':^8} {'x-amp':^8} {'y-amp':^8} "
              f"{'C_Jacobi':^10} {'Periodicity Err':^14}")
    print(header)
    print("  " + "-" * 68)
    for o in milestone_orbits:
        s = o.states[0]
        print(f"  {float(s[0]):10.6f} {float(o.period):8.4f} "
              f"{float(o.amplitudes['x']):8.5f} {float(o.amplitudes['y']):8.5f} "
              f"{float(o._c_jacobi):10.6f} {float(o.periodicity_error):14.2e}")
    print()
    print("=" * 72)
    print()


def _export_csv(orbits: list, param_min: float, param_max: float,
                step_size: float, n_milestones: int = 5) -> Path:
    """将全量轨道数据导出为 CSV，返回文件路径。"""
    milestone_idx = set(_find_milestone_indices(len(orbits), n_milestones))

    rows = []
    for i, o in enumerate(orbits):
        s = o.states[0]
        rows.append({
            "continuation_step": o.metadata.get("continuation_step", ""),
            "x0": float(s[0]),
            "y0": float(s[1]),
            "z0": float(s[2]),
            "vx0": float(s[3]),
            "vy0": float(s[4]),
            "vz0": float(s[5]),
            "period": float(o.period),
            "x_amp": float(o.amplitudes["x"]),
            "y_amp": float(o.amplitudes["y"]),
            "z_amp": float(o.amplitudes.get("z", 0.0)),
            "c_jacobi": float(_jacobi_constant(s)),
            "periodicity_error": float(o.periodicity_error),
            "is_milestone": i in milestone_idx,
        })

    ts = int(time.time())
    csv_path = OUTPUT_DIR / f"dro_31_family_{param_min}-{param_max}-{step_size}_{ts}.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    return csv_path


def main():
    args = parse_args()
    _setup_logging(args.log_level)

    # =============================================================================
    # 1. 系统与动力学模型初始化
    # =============================================================================
    system = e2m2e.core.system.CR3BP_System(mu=MU, primary="earth", secondary="moon")
    dynamic = e2m2e.core.dynamics.CR3BP_Dynamics(system=system)

    # =============================================================================
    # 2. 种子轨道初始状态定义
    # =============================================================================
    # DRO特征：平面内运动（y=z=0），关于x轴对称（vx=vz=0）
    # 初始状态向量格式：[x, y, z, vx, vy, vz]，均为无量纲量
    x0 = args.x0
    vy0 = args.vy0

    initial_state = [x0, 0.0, 0.0, 0.0, vy0, 0.0]
    times = [0]

    seed_state = Orbit(states=[initial_state], times=times)
    seed_state.period = args.period

    # =============================================================================
    # 3. 种子轨道差分修正
    # =============================================================================
    corrector = e2m2e.algorithms.DifferentialCorrection(dynamic=dynamic)
    corrector.setup_2D_symmetric_x_fixed_x0(x0=x0)
    print("[1/3] 开始种子轨道差分修正...")
    seed_DRO = corrector.iterate_correction(initial_guess=seed_state, verbose=args.verbose)
    if seed_DRO is None:
        print("[ERROR] 种子轨道修正失败")
        return
    print(f"[1/3] 完成，周期 = {seed_DRO.period:.4f} TU")

    # =============================================================================
    # 4. 自然延拓生成轨道族
    # =============================================================================
    continuation = e2m2e.algorithms.Continuation(corrector=corrector)
    param_min = args.param_min
    param_max = args.param_max
    step_size = args.step_size

    # 估算总步数（正向+反向）
    n_forward = int((param_max - param_min) / step_size) + 1
    n_backward = int((param_max - param_min) / step_size) + 1
    est_total = n_forward + n_backward
    print(f"[2/3] 开始自然延拓 (x0 ∈ [{param_min:.3f}, {param_max:.3f}], 步长 = {step_size}, 预计约 {est_total} 步)...")

    family_result = continuation.natural_continuation(
        seed_orbit=seed_DRO,
        param_range=(param_min, param_max),
        step_size=step_size,
        verbose=args.verbose,
    )

    orbits = family_result.orbits
    print(f"[2/3] 延拓完成，共 {len(orbits)} 条轨道")

    # =============================================================================
    # 5. 保存轨道数据（JSON）和导出 CSV
    # =============================================================================
    ts = int(time.time())
    json_path = OUTPUT_DIR / f"dro_31_family_{param_min}-{param_max}-{step_size}_{ts}.json"
    family_result.save_to_file(filename=str(json_path))

    csv_path = _export_csv(orbits, param_min, param_max, step_size)

    print(f"[3/3] 已保存：")
    print(f"  JSON: {json_path}")
    print(f"  CSV:  {csv_path}")

    # =============================================================================
    # 6. 打印论文风格摘要表格
    # =============================================================================
    _print_summary_table(orbits, param_min, param_max, step_size)


if __name__ == "__main__":
    # IDE 调试模式：F5 直跑（无命令行参数）时注入下列参数；
    # 命令行调用时不影响。
    if len(sys.argv) == 1:
        sys.argv += [
            "--x0", "0.79188556619742",
            "--vy0", "0.53682",
            "--period", "3.472526005624708",
            "--param-min", "0.141886",
            "--param-max", "0.9",
            "--step-size", "0.005",
        ]
        logger.debug("使用代码内置调试参数")
    main()
