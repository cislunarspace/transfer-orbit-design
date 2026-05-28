"""generate_halo_family 轨道生成脚本。

本模块在地月 CR3BP 中构造种子轨道，调用 e2m2e 的微分修正、自然延拓或伪弧长延拓算法生成目标轨道。输入为命令行给出的初始状态、周期猜测和延拓配置；输出为 output/ 下对应轨道类别的 JSON/CSV 文件。

运行示例:
    .. code-block:: bash

       uv run python -m tod.generates.cr3bp.halo.generate_halo_family --help
"""


import argparse
import csv
import json
import logging
import math
import sys
import time
from pathlib import Path

import e2m2e
import numpy as np
from e2m2e.core import Orbit, OrbitFamily
from tod.commons.constants import MU

logger = logging.getLogger(__name__)

project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
OUTPUT_DIR = project_root / "output" / "halo"

LIBRATION_POINT_MAP = {"L1": 1, "L2": 2, "L3": 3}


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


def _print_summary_table(orbits: OrbitFamily, libration_point: int, halo_class: int,
                         *, method: str = "natural", step_size: float = 0.0,
                         step_size_negative: float | None = None,
                         direction: str = "positive",
                         z_range: tuple[float, float] | None = None,
                         n_milestones: int = 5) -> None:
    """打印论文风格的配置/统计/里程碑表格到控制台。"""
    # --- 统计摘要 ---
    periods = [o.period for o in orbits]
    x0s = [o.states[0, 0] for o in orbits]
    errors = [o.periodicity_error for o in orbits if o.periodicity_error is not None]
    if not errors:
        errors = [0.0]
    # 种子轨道是轨道族的第一条轨道
    seed_orbit = orbits[0]
    s_seed = seed_orbit.states[0]

    # --- 里程碑轨道 ---
    milestone_idx = _find_milestone_indices(len(orbits), n_milestones)
    milestone_orbits = [orbits[i] for i in milestone_idx]

    # 计算里程碑 Jacobi 常数
    jacobi_map: dict[int, float] = {}
    for o in milestone_orbits:
        jacobi_map[id(o)] = _jacobi_constant(o.states[0])

    lp_name = f"L{libration_point}"
    class_name = "北" if halo_class == 0 else "南"

    # 打印配置与统计区块
    print()
    print("=" * 72)
    print(f"  Earth-Moon {lp_name} {class_name} Halo 轨道族：配置、统计与代表性轨道")
    print("=" * 72)
    print()
    print("  配置与统计")
    print("  " + "-" * 68)
    print(f"  物理系统     Earth-Moon CR3BP  (mu = {MU})")
    print(f"  平动点       {lp_name}")
    print(f"  Halo 类别   {class_name} Halo (Class {'I' if halo_class == 0 else 'II'})")
    print(f"  轨道数量     {len(orbits)}")
    print(f"  种子 x0      {float(s_seed[0]):.8f}")
    print(f"  种子 z0      {float(s_seed[2]):.6f}")
    print(f"  种子周期     {seed_orbit.period:.10f}")
    valid_periods = [p for p in periods if p is not None]
    print(f"  周期范围     {min(valid_periods):.4f} ~ {max(valid_periods):.4f}")

    # 延拓信息块
    if method == "natural":
        print(f"  延拓方法     自然参数延拓")
        if z_range is not None:
            print(f"  延拓参数     z0 in [{z_range[0]:.6f}, {z_range[1]:.6f}]")
        print(f"  延拓步长     {step_size}")
        print(f"  延拓方向     {direction}")
    else:
        pal_neg = step_size_negative if step_size_negative is not None else step_size
        print(f"  延拓方法     伪弧长延拓")
        print(f"  正向步长     {step_size}")
        print(f"  负向步长     {pal_neg}")
        print(f"  延拓方向     {direction}")

    print(f"  x0 范围     {min(x0s):.6f} ~ {max(x0s):.6f}")
    print(f"  终止条件     闭轨误差上界 (max = {max(errors):.2e})")
    print()
    print("  代表性轨道（等间距采样）")
    print("  " + "-" * 68)
    header = (f"  {'z_amp':^10} {'x0':^10} {'z0':^10} {'Period':^8} "
              f"{'C_Jacobi':^10} {'Periodicity Err':^14}")
    print(header)
    print("  " + "-" * 68)
    for o in milestone_orbits:
        s = o.states[0]
        params = getattr(o, "parameters", {})
        amp_z = params.get("amplitude_z", abs(float(s[2])))
        c_j = jacobi_map.get(id(o), 0.0)
        print(f"  {float(amp_z):10.6f} {float(s[0]):10.6f} {float(s[2]):10.6f} "
              f"{float(o.period or 0.0):8.4f} {float(c_j):10.6f} "
              f"{float(o.periodicity_error or 0.0):14.2e}")
    print()
    print("=" * 72)
    print()


def _export_csv(orbits: OrbitFamily, libration_point: int, halo_class: int,
                n_milestones: int = 5, branches: str | None = None) -> Path:
    """将全量轨道数据导出为 CSV，返回文件路径。"""
    milestone_idx = set(_find_milestone_indices(len(orbits), n_milestones))

    rows = []
    for i, o in enumerate(orbits):
        s = o.states[0]
        params = getattr(o, "parameters", {})
        rows.append({
            "step": i,
            "branch": params.get("branch", "north" if halo_class == 0 else "south"),
            "z_amp": float(params.get("amplitude_z", abs(float(s[2])))),
            "x0": float(s[0]),
            "y0": float(s[1]),
            "z0": float(s[2]),
            "vx0": float(s[3]),
            "vy0": float(s[4]),
            "vz0": float(s[5]),
            "period": float(o.period or 0.0),
            "c_jacobi": float(_jacobi_constant(s)),
            "periodicity_error": float(o.periodicity_error or 0.0),
            "is_milestone": i in milestone_idx,
        })

    ts = int(time.time())
    lp_name = f"L{libration_point}"
    class_name = "NS" if branches == "both" else ("N" if halo_class == 0 else "S")
    shared_suffix = "_shared" if branches == "both" else ""
    if not rows:
        logger.warning("轨道族为空，跳过 CSV 导出")
        return None

    csv_path = OUTPUT_DIR / f"halo_{lp_name}_{class_name}_family{shared_suffix}_{ts}.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    return csv_path


def _load_seed_orbit(seed_file: str, system) -> Orbit:
    """从 JSON 文件加载种子轨道。

    支持两种文件格式：
    - 单轨道文件：直接包含 states、times、period 等键。
    - 多轨道文件：包含 "orbits" 键，其值为 Orbit 对象列表。
      此时取列表中第一条轨道作为种子。

    多轨道文件格式常见于轨道族（OrbitFamily）保存结果，其中
    "orbits" 键存储了族内所有轨道数据。

    Args:
        seed_file: 种子轨道 JSON 文件路径（字符串或 PathLike）。
        system: CR3BP 系统对象，用于无量纲单位解析与状态向量转换。

    Returns:
        加载的 Orbit 对象，包含修正后的 states、times、period 等属性。
    """
    seed_path = Path(seed_file)
    with seed_path.open(encoding="utf-8") as f:
        data = json.load(f)

    # 检测多轨道格式：若存在 "orbits" 键，说明是 OrbitFamily 保存的文件，
    # 取索引 0 的轨道作为延拓种子。
    if "orbits" in data:
        return Orbit.load_from_file(seed_path, system=system, orbit_index=0)
    return Orbit.load_from_file(seed_path, system=system)


def _tag_halo_seed_orbit(
    seed_halo: Orbit,
    *,
    libration_point: int,
    halo_class: int,
    amplitude_z: float,
) -> float:
    """为种子轨道标记 Halo 轨道族的分类标签。

    将平动点编号、Halo 类别（北/南）和 z 方向振幅写入轨道的
    parameters 字典。若轨道已存在部分标签（例如从文件加载的种子
    已带有 parameters），优先保留已有值，避免覆盖用户显式设置的参数。

    amplitude_z 取绝对值是因为 Halo 轨道的北/南方向已由 halo_class
    显式编码，振幅本身应为非负标量。

    Args:
        seed_halo: 种子轨道对象。
        libration_point: 平动点编号（1=L1, 2=L2, 3=L3）。
        halo_class: Halo 类别（0=北 Halo/Class I, 1=南 Halo/Class II）。
        amplitude_z: Z 方向振幅猜测值（无量纲）。

    Returns:
        最终写入的 z 方向振幅（非负）。
    """
    params = getattr(seed_halo, "parameters", None)
    if not isinstance(params, dict):
        params = {}
        seed_halo.parameters = params

    seed_halo.family_type = "halo"
    # 优先保留已有参数：若种子从文件加载且已携带标签，不覆盖。
    params["libration_point"] = int(params.get("libration_point", libration_point))
    params["halo_class"] = int(params.get("halo_class", halo_class))
    # 振幅取绝对值：方向由 halo_class 编码，振幅本身为非负量。
    params["amplitude_z"] = abs(float(params.get("amplitude_z", amplitude_z)))
    return float(params["amplitude_z"])


def _set_halo_branch(orbit: Orbit, branch: str) -> Orbit:
    params = getattr(orbit, "parameters", None)
    if not isinstance(params, dict):
        params = {}
        orbit.parameters = params
    params["branch"] = branch
    params["halo_class"] = 0 if branch == "north" else 1
    return orbit


def _locate_halo_crossing_orbit(*, system, libration_point: int) -> Orbit:
    raise NotImplementedError("shared Halo crossing orbit locator is not implemented yet")


def _branch_switch_halo_from_crossing(*, crossing_orbit: Orbit, branch: str) -> Orbit:
    raise NotImplementedError("Halo branch switching is not implemented yet")


def _crossing_orbit_metadata(crossing_orbit: Orbit) -> dict[str, float | str]:
    state = np.asarray(crossing_orbit.states)[0]
    return {
        "family": "Lyapunov",
        "role": "vertical_critical_crossing_orbit",
        "x0": float(state[0]),
        "z0": float(state[2]),
        "period": float(crossing_orbit.period or 0.0),
    }


def _generate_combined_halo_family(
    *,
    continuation,
    system,
    libration_point: int,
    n_orbits: int,
    step_size: float,
    step_size_negative: float,
) -> OrbitFamily:
    crossing_orbit = _locate_halo_crossing_orbit(system=system, libration_point=libration_point)
    combined_family = OrbitFamily([])
    for branch in ("north", "south"):
        seed_orbit = _branch_switch_halo_from_crossing(crossing_orbit=crossing_orbit, branch=branch)
        branch_family = continuation.halo_pseudo_arclength_continuation(
            seed_orbit=seed_orbit,
            n_orbits=n_orbits,
            direction="positive",
            step_size=step_size,
            step_size_negative=step_size_negative,
            verbose=True,
        )
        for orbit in branch_family:
            combined_family.add_orbit(_set_halo_branch(orbit, branch))
    combined_family.metadata["generation_mode"] = "shared_crossing_orbit"
    combined_family.metadata["halo_branches"] = ["north", "south"]
    combined_family.metadata["libration_point"] = libration_point
    combined_family.metadata["crossing_orbit"] = _crossing_orbit_metadata(crossing_orbit)
    combined_family.metadata["continuation_method"] = "pseudo_arclength"
    return combined_family


def _resolve_halo_branches(args: argparse.Namespace) -> str:
    if args.branches is not None:
        return args.branches
    return "north" if args.halo_class == 0 else "south"


def _validate_halo_branch_request(args: argparse.Namespace) -> None:
    branches = _resolve_halo_branches(args)
    if branches == "both" and args.method != "pseudo_arclength":
        raise ValueError("combined north/south Halo generation requires pseudo_arclength")


def parse_args(argv=None):
    """解析命令行参数。

    Args:
        argv: 可选参数列表。若提供，则解析该列表而非 sys.argv。
              主要用于单元测试中以编程方式调用。

    Returns:
        解析后的 argparse.Namespace 对象，包含所有脚本参数。
    """
    parser = argparse.ArgumentParser(description="生成 Halo 轨道族", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--libration-point", type=str, default="L1", choices=["L1", "L2", "L3"], help="平动点：L1, L2, L3")
    parser.add_argument("--amplitude-z", type=float, default=0.001, help="Z 方向振幅（无量纲）")
    parser.add_argument("--halo-class", type=int, default=0, help="0=北 Halo, 1=南 Halo")
    parser.add_argument("--branches", type=str, default=None, choices=["north", "south", "both"], help="Halo 分支选择：north=北族, south=南族, both=共享交叉轨道生成北族和南族")
    parser.add_argument("--n-orbits", type=int, default=20, help="延拓轨道数量")
    parser.add_argument("--step-size", type=float, default=0.002, help="自然参数延拓 z 方向步长")
    parser.add_argument("--step-size-pal", type=float, default=None, help="伪弧长延拓步长（提供时覆盖 --step-size）")
    parser.add_argument("--step-size-negative", type=float, default=None, help="伪弧长延拓负向步长（默认等于正向步长）")
    parser.add_argument("--direction", type=str, default="positive", choices=["positive", "negative", "both"], help="延拓方向")
    parser.add_argument("--seed-file", type=str, default=None, help="种子轨道 JSON 文件路径（提供时跳过种子生成）")
    parser.add_argument("--method", type=str, default="natural", choices=["natural", "pseudo_arclength"], help="延拓方法")
    parser.add_argument("--z-min", type=float, default=None, help="延拓 z 振幅下限（正数，无量纲，与 --z-max 同时提供时启用 z_range 模式）")
    parser.add_argument("--z-max", type=float, default=None, help="延拓 z 振幅上限（正数，无量纲，与 --z-min 同时提供时启用 z_range 模式）")
    return parser.parse_args(argv)


def main():
    """执行脚本主流程。
    
    Returns:
        None。
    """
    args = parse_args()
    try:
        _validate_halo_branch_request(args)
    except ValueError as exc:
        logger.error(str(exc))
        sys.exit(2)

    # =============================================================================
    # 1. 系统与动力学模型初始化
    # =============================================================================
    system = e2m2e.core.system.CR3BP_System(mu=MU, primary="earth", secondary="moon")
    dynamics = e2m2e.core.dynamics.CR3BP_Dynamics(system=system)

    # =============================================================================
    # 2. Halo轨道参数
    # =============================================================================
    libration_point = LIBRATION_POINT_MAP[args.libration_point]  # 1=L1, 2=L2, 3=L3
    amplitude_z = args.amplitude_z  # Z方向振幅
    branches = _resolve_halo_branches(args)
    halo_class = 0 if branches == "north" else 1  # 0=北Halo (Class I), 1=南Halo (Class II)

    # =============================================================================
    # 3. 获取种子轨道
    # =============================================================================
    # 微分校正器：将 Richardson 近似（或用户提供）的初值迭代修正为精确的
    # 周期轨道，满足 Halo 轨道的对称性约束（y0=vy0=vx0=vz0=0）。
    corrector = e2m2e.algorithms.DifferentialCorrection(dynamic=dynamics)
    # 延拓器：基于校正后的种子轨道，通过步进方式生成轨道族。
    continuation = e2m2e.algorithms.Continuation(corrector=corrector)

    n_orbits = args.n_orbits
    method = args.method
    step_size = args.step_size_pal if args.step_size_pal is not None else args.step_size
    step_size_negative = args.step_size_negative if args.step_size_negative is not None else step_size
    direction = args.direction

    if branches == "both":
        logger.info("开始 Halo 北族+南族共享交叉轨道生成...")
        family_result = _generate_combined_halo_family(
            continuation=continuation,
            system=system,
            libration_point=libration_point,
            n_orbits=n_orbits,
            step_size=step_size,
            step_size_negative=step_size_negative,
        )
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        family_name = f"halo_L{libration_point}_NS_family_shared_{ts}"
        json_path = OUTPUT_DIR / f"{family_name}.json"
        family_result.save_to_file(filename=str(json_path))
        csv_path = _export_csv(family_result, libration_point, halo_class, branches="both")
        logger.info("轨道族已保存至: %s", json_path)
        logger.info("  轨道族名称: %s", family_name)
        print(f"[3/3] 已保存：")
        print(f"  JSON: {json_path}")
        print(f"  CSV:  {csv_path}")
        _print_summary_table(
            family_result, libration_point, halo_class,
            method=method, step_size=step_size,
            step_size_negative=step_size_negative,
            direction=direction,
        )
        return

    if args.seed_file:
        logger.info("从文件加载种子轨道: %s", args.seed_file)
        seed_halo = _load_seed_orbit(args.seed_file, system=system)
        # 加载外部种子时，以文件中的 z0 实际值为准重新标记振幅，
        # 避免命令行 --amplitude-z 与文件内容不一致。
        amplitude_z = _tag_halo_seed_orbit(
            seed_halo,
            libration_point=libration_point,
            halo_class=halo_class,
            amplitude_z=abs(float(np.asarray(seed_halo.states)[0, 2])),
        )
        logger.info("种子轨道加载成功: 周期=%.6f TU", seed_halo.period)
        logger.info("  x0=%.6f, z0=%.6f", np.asarray(seed_halo.states)[0, 0], np.asarray(seed_halo.states)[0, 2])
    else:
        logger.info("正在生成种子轨道: L%d %s Halo", libration_point, "北" if halo_class == 0 else "南")
        logger.info("  Z振幅: %s", amplitude_z)

        seed_halo = continuation.generate_halo_seed_orbit(
            libration_point=libration_point,
            amplitude_z=amplitude_z,
            halo_class=halo_class,
            verbose=False,
        )

        if seed_halo is None:
            # Richardson 三阶近似对大振幅 Halo 轨道（尤其是 L1 北向）的预测误差
            # 可能超过微分校正的收敛域，导致 corrector 无法找到周期轨道。
            # 针对这一已知问题，我们提供一组来自文献的硬编码高精度参考值
            # 作为 Richardson 失效时的 fallback。
            if libration_point == 1 and halo_class == 0 and amplitude_z >= 0.01:
                logger.warning("Richardson 近似失效，使用硬编码参考值生成种子...")
                x0_ref = 0.9305269194214338
                vy0_ref = 0.10431508546142665
                T_ref = 1.839732
                state0 = np.array([x0_ref, 0.0, amplitude_z if halo_class == 0 else -amplitude_z, 0.0, vy0_ref, 0.0])
                corrector.setup_halo_orbit_fixed_z0(
                    z0=amplitude_z if halo_class == 0 else -amplitude_z,
                    libration_point=libration_point,
                )
                corrector.max_iterations = 150
                corrector.tolerance = 1e-6
                guess = e2m2e.core.Orbit(states=state0.reshape(1, -1), times=np.array([0.0]), system=system)
                guess.period = T_ref
                seed_halo = corrector.iterate_correction(guess, verbose=False)
                if seed_halo is not None and seed_halo.correction_success:
                    logger.info("硬编码种子修正成功: 周期=%.6f TU", seed_halo.period)
                else:
                    logger.error("硬编码种子修正也失败")
                    sys.exit(1)
            else:
                logger.error("种子轨道生成失败")
                sys.exit(1)

        amplitude_z = _tag_halo_seed_orbit(
            seed_halo,
            libration_point=libration_point,
            halo_class=halo_class,
            amplitude_z=amplitude_z,
        )
        logger.info("种子轨道生成成功: 周期=%.6f TU", seed_halo.period)
        logger.info("  x0=%.6f, z0=%.6f", np.asarray(seed_halo.states)[0, 0], np.asarray(seed_halo.states)[0, 2])

    # =============================================================================
    # 4. 生成轨道族
    # =============================================================================
    # 只有当 --z-min 和 --z-max 同时显式提供时才启用 z_range 模式
    z_range = None
    if args.z_min is not None and args.z_max is not None:
        if args.z_min >= args.z_max:
            logger.error("z_min (%.4f) 必须小于 z_max (%.4f)", args.z_min, args.z_max)
            sys.exit(1)
        # 构造 z_range：振幅（正数）→ 根据 halo_class 转为带符号的 z 值
        if args.halo_class == 0:
            z_range = (args.z_min, args.z_max)
        else:
            z_range = (-args.z_max, -args.z_min)

        # 验证种子 z 是否在请求的范围内；若不在，调整到边界
        seed_z = float(np.asarray(seed_halo.states)[0, 2])
        if not (z_range[0] <= seed_z <= z_range[1]):
            logger.warning(
                "种子 z0 (%.4f) 不在请求的 z_range [%.4f, %.4f] 内，重新生成边界种子...",
                seed_z, z_range[0], z_range[1],
            )
            # 北 Halo 用 z_min，南 Halo 用 z_max（负值）作为新的种子振幅
            new_amp_z = args.z_min if args.halo_class == 0 else args.z_max
            seed_halo = continuation.generate_halo_seed_orbit(
                libration_point=libration_point,
                amplitude_z=new_amp_z,
                halo_class=halo_class,
                verbose=False,
            )
            if seed_halo is None:
                logger.error("边界种子轨道生成失败")
                sys.exit(1)
            amplitude_z = _tag_halo_seed_orbit(
                seed_halo,
                libration_point=libration_point,
                halo_class=halo_class,
                amplitude_z=new_amp_z,
            )
            logger.info("边界种子生成成功: 周期=%.6f TU, z0=%.6f", seed_halo.period, np.asarray(seed_halo.states)[0, 2])

        logger.info("使用参数区间模式: z_range=[%.4f, %.4f], 最大轨道数=%d", z_range[0], z_range[1], n_orbits)
    else:
        logger.info("使用轨道数量模式: n_orbits=%d, direction=%s", n_orbits, args.direction)

    if method == "natural":
        logger.info("开始 Halo 轨道族自然参数延拓（沿 z 方向）...")
        family_result = continuation.generate_halo_family(
            seed_orbit=seed_halo,
            n_orbits=n_orbits,
            direction=direction,
            step_size=args.step_size,
            z_range=z_range,
            verbose=True,
        )
        from e2m2e.core.orbit import OrbitFamily
        family = OrbitFamily([seed_halo])
        for o in family_result[1:]:
            family.add_orbit(o)
        family_result = family
    else:
        logger.info("开始 Halo 轨道族伪弧长延拓（continuation_PAL_CR3BP 流程）...")
        family_result = continuation.halo_pseudo_arclength_continuation(
            seed_orbit=seed_halo,
            n_orbits=n_orbits,
            direction=direction,
            step_size=step_size,
            step_size_negative=step_size_negative,
            verbose=True,
        )

    logger.info("轨道族生成完成: 共%d条轨道", len(family_result))

    # =============================================================================
    # 5. 保存轨道数据（JSON）
    # =============================================================================
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    # 文件名格式：halo_L{平动点}_{N/S}_family_{振幅}_{时间戳}.json
    family_name = f"halo_L{libration_point}_{'N' if halo_class == 0 else 'S'}_family_{amplitude_z}_{ts}"
    json_path = OUTPUT_DIR / f"{family_name}.json"
    family_result.save_to_file(filename=str(json_path))

    # =============================================================================
    # 6. 导出全量数据为 CSV
    # =============================================================================
    csv_path = _export_csv(family_result, libration_point, halo_class)

    logger.info("轨道族已保存至: %s", OUTPUT_DIR / f"{family_name}.json")
    logger.info("  轨道族名称: %s", family_name)
    if len(family_result) > 0:
        z_values = [getattr(o, "parameters", {}).get("amplitude_z", 0) for o in family_result]
        logger.info("  z_amplitude 范围: [%.4f, %.4f]", min(z_values), max(z_values))

    print(f"[3/3] 已保存：")
    print(f"  JSON: {json_path}")
    print(f"  CSV:  {csv_path}")

    # =============================================================================
    # 7. 打印论文风格摘要表格
    # =============================================================================
    _print_summary_table(
        family_result, libration_point, halo_class,
        method=method, step_size=step_size,
        step_size_negative=step_size_negative if method == "pseudo_arclength" else None,
        direction=direction, z_range=z_range,
    )


if __name__ == "__main__":
    # IDE 调试模式：F5 直跑（无命令行参数）时注入下列参数；
    # 命令行调用时不影响。
    # 想调哪个值就改下方对应字面量即可。
    if len(sys.argv) == 1:
        sys.argv += [
            "--libration-point", "L1",                    # 平动点：L1, L2, L3
            "--amplitude-z", "0.001",                     # Z 方向振幅（无量纲）
            "--halo-class", "1",                          # 0=北 Halo, 1=南 Halo
            "--n-orbits", "20",                           # 延拓轨道数量
            "--step-size", "0.002",                       # 自然参数延拓 z 方向步长
            "--direction", "positive",                    # 延拓方向
            "--method", "natural",                        # 延拓方法
        ]
        logger.debug("使用代码内置调试参数")
    main()
