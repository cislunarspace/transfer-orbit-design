"""
生成 Halo 轨道族

支持两种种子轨道来源：
1. 从文件加载（--seed-file）：直接加载已有的精确 Halo 轨道 JSON 文件
2. 自动生成：使用 Richardson 三阶近似 + 微分修正生成精确种子

种子轨道通过伪弧长延拓方法生成完整的 Halo 轨道族。

参考文献:
    Richardson, D. L. (1980). Analytic construction of periodic orbits
    about the collinear points. Celestial Mechanics.

注意:
    Halo轨道族延拓是一个非线性问题。Richardson三阶近似仅对小幅度的
    Halo轨道准确。伪弧长步长与 CR3BP_MATLAB_Library 中
    examples/FAMILY_L1Halo_North.m 一致：正向 DeltaS=0.0045，负向 |DeltaS|=0.009
    （由 step_size / step_size_negative 控制）。
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

project_root = Path(__file__).resolve().parent.parent.parent.parent.parent

import time

from tod.commons.common import MU

import e2m2e
from e2m2e.core import Orbit

OUTPUT_DIR = project_root / "output" / "halo"

LIBRATION_POINT_MAP = {"L1": 1, "L2": 2, "L3": 3}


def _load_seed_orbit(seed_file: str, system) -> Orbit:
    seed_path = Path(seed_file)
    with seed_path.open(encoding="utf-8") as f:
        data = json.load(f)

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
    params = getattr(seed_halo, "parameters", None)
    if not isinstance(params, dict):
        params = {}
        seed_halo.parameters = params

    seed_halo.family_type = "halo"
    params["libration_point"] = int(params.get("libration_point", libration_point))
    params["halo_class"] = int(params.get("halo_class", halo_class))
    params["amplitude_z"] = abs(float(params.get("amplitude_z", amplitude_z)))
    return float(params["amplitude_z"])


def parse_args(argv=None):
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
    corrector = e2m2e.algorithms.DifferentialCorrection(dynamic=dynamics)
    continuation = e2m2e.algorithms.Continuation(corrector=corrector)

    if args.seed_file:
        print(f"从文件加载种子轨道: {args.seed_file}")
        seed_halo = _load_seed_orbit(args.seed_file, system=system)
        amplitude_z = _tag_halo_seed_orbit(
            seed_halo,
            libration_point=libration_point,
            halo_class=halo_class,
            amplitude_z=abs(float(np.asarray(seed_halo.states)[0, 2])),
        )
        print(f"[ok] 种子轨道加载成功: 周期={seed_halo.period:.6f} TU")
        print(f"  x0={np.asarray(seed_halo.states)[0, 0]:.6f}, z0={np.asarray(seed_halo.states)[0, 2]:.6f}")
    else:
        print(f"正在生成种子轨道: L{libration_point} {'北' if halo_class == 0 else '南'} Halo")
        print(f"  Z振幅: {amplitude_z}")

        seed_halo = continuation.generate_halo_seed_orbit(
            libration_point=libration_point,
            amplitude_z=amplitude_z,
            halo_class=halo_class,
            verbose=False,
        )

        if seed_halo is None:
            # Richardson 对大振幅失效，尝试硬编码的 L1 北 Halo 参考值
            if libration_point == 1 and halo_class == 0 and amplitude_z >= 0.01:
                print("  Richardson 近似失效，使用硬编码参考值生成种子...")
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
                    print(f"  [ok] 硬编码种子修正成功: 周期={seed_halo.period:.6f} TU")
                else:
                    print("[error] 硬编码种子修正也失败")
                    sys.exit(1)
            else:
                print("[error] 种子轨道生成失败")
                sys.exit(1)

        amplitude_z = _tag_halo_seed_orbit(
            seed_halo,
            libration_point=libration_point,
            halo_class=halo_class,
            amplitude_z=amplitude_z,
        )
        print(f"[ok] 种子轨道生成成功: 周期={seed_halo.period:.6f} TU")
        print(f"  x0={np.asarray(seed_halo.states)[0, 0]:.6f}, z0={np.asarray(seed_halo.states)[0, 2]:.6f}")

    # =============================================================================
    # 4. 生成轨道族
    # =============================================================================
    n_orbits = args.n_orbits
    step_size = args.step_size
    method = args.method

    if method == "natural":
        print(f"\n开始 Halo 轨道族自然参数延拓（沿 z 方向）...")
        family_result = continuation.generate_halo_family(
            seed_orbit=seed_halo,
            n_orbits=n_orbits,
            direction=args.direction,
            step_size=step_size,
            verbose=True,
        )
        # generate_halo_family 返回 list[Orbit]，需要包装为 OrbitFamily
        from e2m2e.core.orbit import OrbitFamily
        family = OrbitFamily([seed_halo])
        for o in family_result[1:]:
            family.add_orbit(o)
        family_result = family
    else:
        print(f"\n开始 Halo 轨道族伪弧长延拓（continuation_PAL_CR3BP 流程）...")
        family_result = continuation.halo_pseudo_arclength_continuation(
            seed_orbit=seed_halo,
            n_orbits=n_orbits,
            direction="both",
            step_size=step_size,
            step_size_negative=step_size,
            verbose=True,
        )

    print(f"\n[ok] 轨道族生成完成: 共{len(family_result)}条轨道")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    family_name = f"halo_L{libration_point}_{'N' if halo_class == 0 else 'S'}_family_{amplitude_z}_{ts}"
    family_result.save_to_file(filename=str(OUTPUT_DIR / f"{family_name}.json"))

    print(f"\n[ok] 轨道族已保存至: {OUTPUT_DIR / f'{family_name}.json'}")
    print(f"  轨道族名称: {family_name}")
    if len(family_result) > 0:
        z_values = [getattr(o, "parameters", {}).get("amplitude_z", 0) for o in family_result]
        print(f"  z_amplitude 范围: [{min(z_values):.4f}, {max(z_values):.4f}]")


if __name__ == "__main__":
    main()
