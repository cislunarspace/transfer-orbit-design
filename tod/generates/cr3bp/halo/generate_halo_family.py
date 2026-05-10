"""
生成 Halo 轨道族

Halo 轨道族是一类围绕地月系统共线平动点（L1/L2/L3）的三维周期轨道族，
具有关于 XZ 平面对称的特征。本脚本通过延拓方法（自然参数延拓或伪弧长延拓）
从单条种子轨道出发，逐步生成覆盖不同振幅范围的完整轨道族。

支持两种种子轨道来源：
1. 从文件加载（--seed-file）：直接加载已有的精确 Halo 轨道 JSON 文件。
   适用于已生成精确种子后，仅需执行延拓的场景。
2. 自动生成：使用 Richardson 三阶解析近似提供初值猜测，结合微分修正
   迭代生成精确种子。适用于从零开始的完整流程。

种子轨道生成后，通过延拓方法生成完整的 Halo 轨道族：
- natural（自然参数延拓）：沿 z 方向固定步长推进，简单高效，但在
  切空间接近奇异时（如轨道族转向点附近）可能失效。
- pseudo_arclength（伪弧长延拓）：沿轨道族切向推进，步长自适应，
  能稳定通过转向点，但计算量稍大。

参考文献:
    Richardson, D. L. (1980). Analytic construction of periodic orbits
    about the collinear points. Celestial Mechanics.

注意:
    Richardson 三阶近似仅对小幅度的 Halo 轨道准确。当振幅较大时，
    解析近似可能偏离真解过远，导致微分修正无法收敛。此时可改用
    --seed-file 加载预先生成的高精度种子轨道。
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np

project_root = Path(__file__).resolve().parent.parent.parent.parent.parent

import time

from tod.commons.common import MU

import e2m2e
from e2m2e.core import Orbit

logger = logging.getLogger(__name__)

OUTPUT_DIR = project_root / "output" / "halo"

LIBRATION_POINT_MAP = {"L1": 1, "L2": 2, "L3": 3}


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


def parse_args(argv=None):
    """解析命令行参数。

    Args:
        argv: 可选参数列表。若提供，则解析该列表而非 sys.argv。
              主要用于单元测试中以编程方式调用。

    Returns:
        解析后的 argparse.Namespace 对象，包含所有脚本参数。
    """
    parser = argparse.ArgumentParser(description="生成 Halo 轨道族")
    parser.add_argument("--libration-point", type=str, default="L1", choices=["L1", "L2", "L3"], help="平动点：L1, L2, L3")
    parser.add_argument("--amplitude-z", type=float, default=0.001, help="Z 方向振幅（无量纲）")
    parser.add_argument("--halo-class", type=int, default=0, help="0=北 Halo, 1=南 Halo")
    parser.add_argument("--n-orbits", type=int, default=20, help="延拓轨道数量")
    parser.add_argument("--step-size", type=float, default=0.002, help="自然参数延拓 z 方向步长")
    parser.add_argument("--direction", type=str, default="positive", choices=["positive", "negative", "both"], help="延拓方向")
    parser.add_argument("--seed-file", type=str, default=None, help="种子轨道 JSON 文件路径（提供时跳过种子生成）")
    parser.add_argument("--method", type=str, default="natural", choices=["natural", "pseudo_arclength"], help="延拓方法")
    return parser.parse_args(argv)


def main():
    args = parse_args()

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
    halo_class = args.halo_class  # 0=北Halo (Class I), 1=南Halo (Class II)

    # =============================================================================
    # 3. 获取种子轨道
    # =============================================================================
    # 微分校正器：将 Richardson 近似（或用户提供）的初值迭代修正为精确的
    # 周期轨道，满足 Halo 轨道的对称性约束（y0=vy0=vx0=vz0=0）。
    corrector = e2m2e.algorithms.DifferentialCorrection(dynamic=dynamics)
    # 延拓器：基于校正后的种子轨道，通过步进方式生成轨道族。
    continuation = e2m2e.algorithms.Continuation(corrector=corrector)

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
    n_orbits = args.n_orbits
    step_size = args.step_size
    method = args.method

    if method == "natural":
        logger.info("开始 Halo 轨道族自然参数延拓（沿 z 方向）...")
        family_result = continuation.generate_halo_family(
            seed_orbit=seed_halo,
            n_orbits=n_orbits,
            direction=args.direction,
            step_size=step_size,
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
            direction="both",
            step_size=step_size,
            step_size_negative=step_size,
            verbose=True,
        )

    logger.info("轨道族生成完成: 共%d条轨道", len(family_result))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    # 文件名格式：halo_L{平动点}_{N/S}_family_{振幅}_{时间戳}.json
    family_name = f"halo_L{libration_point}_{'N' if halo_class == 0 else 'S'}_family_{amplitude_z}_{ts}"
    family_result.save_to_file(filename=str(OUTPUT_DIR / f"{family_name}.json"))

    logger.info("轨道族已保存至: %s", OUTPUT_DIR / f"{family_name}.json")
    logger.info("  轨道族名称: %s", family_name)
    if len(family_result) > 0:
        z_values = [getattr(o, "parameters", {}).get("amplitude_z", 0) for o in family_result]
        logger.info("  z_amplitude 范围: [%.4f, %.4f]", min(z_values), max(z_values))


if __name__ == "__main__":
    # IDE 调试模式：F5 直跑（无命令行参数）时注入下列参数；
    # 命令行调用时不影响。
    # 想调哪个值就改下方对应字面量即可。
    if len(sys.argv) == 1:
        sys.argv += [
            "--libration-point", "L1",                    # 平动点：L1, L2, L3
            "--amplitude-z", "0.001",                     # Z 方向振幅（无量纲）
            "--halo-class", "0",                          # 0=北 Halo, 1=南 Halo
            "--n-orbits", "20",                           # 延拓轨道数量
            "--step-size", "0.002",                       # 自然参数延拓 z 方向步长
            "--direction", "positive",                    # 延拓方向
            "--method", "natural",                        # 延拓方法
        ]
        logger.debug("使用代码内置调试参数")
    main()
