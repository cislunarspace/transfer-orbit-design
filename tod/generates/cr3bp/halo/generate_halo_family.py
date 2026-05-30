"""generate_halo_family 轨道生成脚本。

本模块在地月 CR3BP 中构造 Halo 种子轨道，调用 e2m2e 的微分修正、
自然延拓或伪弧长延拓算法生成 Halo 轨道族。

支持：L1/L2/L3 平动点，北/南/双分支，自然延拓/伪弧长延拓。

本脚本通过 ``FamilyGenerator`` 基类实现，但覆盖 ``run()`` 方法以支持
Halo 特有的分支组合、种子生成策略和 z_range 模式。共享的输出逻辑
（CSV 导出、摘要表打印）仍由基类模块提供。

运行示例:
    .. code-block:: bash

       uv run python -m tod.generates.cr3bp.halo.generate_halo_family --help
"""


from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

import e2m2e
from e2m2e.core import Orbit

from tod.generates.cr3bp._family_pipeline import (
    FamilyGenerator,
    FamilyGeneratorConfig,
    export_csv,
    inject_debug_args,
    jacobi_constant,
    print_summary_table,
    setup_logging,
)

logger = logging.getLogger(__name__)

LIBRATION_POINT_MAP = {"L1": 1, "L2": 2, "L3": 3}


# ------------------------------------------------------------------------------
# 种子轨道辅助
# ------------------------------------------------------------------------------


def _load_seed_orbit(seed_file: str, system) -> Orbit:
    """从 JSON 文件加载种子轨道。

    支持单轨道文件（states/times/period）和多轨道文件（orbits 列表）。
    多轨道文件时取索引 0 的轨道作为种子。
    """
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
    """为种子轨道标记 Halo 分类标签。

    将平动点编号、Halo 类别（北/南）和 z 方向振幅写入轨道的
    ``parameters`` 字典。优先保留已有值，避免覆盖用户显式设置。
    """
    params = getattr(seed_halo, "parameters", None)
    if not isinstance(params, dict):
        params = {}
        seed_halo.parameters = params
    seed_halo.family_type = "halo"
    params["libration_point"] = int(params.get("libration_point", libration_point))
    params["halo_class"] = int(params.get("halo_class", halo_class))
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


# ------------------------------------------------------------------------------
# 参数与验证
# ------------------------------------------------------------------------------


def _resolve_halo_branches(args) -> str:
    """由 ``--halo-class`` 推断分支：0=北族, 1=南族。"""
    return "north" if args.halo_class == 0 else "south"


# ------------------------------------------------------------------------------
# Halo 族生成器
# ------------------------------------------------------------------------------


class HaloFamilyGenerator(FamilyGenerator):
    """Halo 轨道族生成器。

    覆盖 ``run()`` 以支持 Halo 特有的分支组合、种子生成策略和
    z_range 模式。共享输出逻辑仍使用基类模块级函数。
    """

    @classmethod
    def add_family_args(cls, parser) -> None:
        """声明 Halo 族特有的 CLI 参数。"""
        parser.add_argument(
            "--libration-point",
            type=str,
            default="L1",
            choices=["L1", "L2", "L3"],
            help="平动点：L1, L2, L3",
        )
        parser.add_argument(
            "--amplitude-z",
            type=float,
            default=0.001,
            help="Z 方向振幅（无量纲）",
        )
        parser.add_argument(
            "--halo-class",
            type=int,
            default=0,
            help="0=北 Halo, 1=南 Halo",
        )
        parser.add_argument(
            "--n-orbits",
            type=int,
            default=20,
            help="延拓轨道数量",
        )
        parser.add_argument(
            "--step-size",
            type=float,
            default=0.002,
            help="自然参数延拓 z 方向步长",
        )
        parser.add_argument(
            "--step-size-pal",
            type=float,
            default=None,
            help="伪弧长延拓步长（提供时覆盖 --step-size）",
        )
        parser.add_argument(
            "--step-size-negative",
            type=float,
            default=None,
            help="伪弧长延拓负向步长（默认等于正向步长）",
        )
        parser.add_argument(
            "--direction",
            type=str,
            default="both",
            choices=["positive", "negative", "both"],
            help="延拓方向（默认 both：从种子向振幅更小和更大双向铺开）",
        )
        parser.add_argument(
            "--seed-file",
            type=str,
            default=None,
            help="种子轨道 JSON 文件路径（提供时跳过种子生成）",
        )
        parser.add_argument(
            "--method",
            type=str,
            default="pseudo_arclength",
            choices=["natural", "pseudo_arclength"],
            help="延拓方法（默认 pseudo_arclength）",
        )
        parser.add_argument(
            "--z-min",
            type=float,
            default=None,
            help="延拓 z 振幅下限（正数，无量纲，与 --z-max 同时提供时启用 z_range 模式）",
        )
        parser.add_argument(
            "--z-max",
            type=float,
            default=None,
            help="延拓 z 振幅上限（正数，无量纲，与 --z-min 同时提供时启用 z_range 模式）",
        )

    def run(self, args, *, project_root=None):
        """执行 Halo 轨道族生成（覆盖基类以支持特有流程）。"""
        self.init_system()

        libration_point = LIBRATION_POINT_MAP[args.libration_point]
        branches = _resolve_halo_branches(args)
        halo_class = 0 if branches == "north" else 1
        method = args.method
        step_size = args.step_size_pal if args.step_size_pal is not None else args.step_size
        step_size_negative = (
            args.step_size_negative if args.step_size_negative is not None else step_size
        )
        direction = args.direction
        n_orbits = args.n_orbits

        corrector = e2m2e.algorithms.DifferentialCorrection(dynamic=self.dynamics)
        continuation = e2m2e.algorithms.Continuation(corrector=corrector)

        # 总览行
        method_label = "伪弧长延拓" if method == "pseudo_arclength" else "自然参数延拓"
        class_label = "北族" if halo_class == 0 else "南族"
        print(
            f"Halo 轨道族生成：L{libration_point} {class_label}，"
            f"{method_label}（步长 {step_size}），{n_orbits} 条轨道"
        )

        amplitude_z = args.amplitude_z

        # 种子轨道获取
        if args.seed_file:
            logger.info("从文件加载种子轨道: %s", args.seed_file)
            seed_halo = _load_seed_orbit(args.seed_file, system=self.system)
            amplitude_z = _tag_halo_seed_orbit(
                seed_halo,
                libration_point=libration_point,
                halo_class=halo_class,
                amplitude_z=abs(float(np.asarray(seed_halo.states)[0, 2])),
            )
            logger.info("种子轨道加载成功: 周期=%.6f TU", seed_halo.period)
        else:
            logger.info(
                "正在生成种子轨道: L%d %s Halo",
                libration_point,
                "北" if halo_class == 0 else "南",
            )
            seed_halo = continuation.generate_halo_seed_orbit(
                libration_point=libration_point,
                amplitude_z=amplitude_z,
                halo_class=halo_class,
                verbose=False,
            )
            if seed_halo is None:
                seed_halo = self._fallback_seed_generation(
                    continuation, corrector, libration_point, halo_class, amplitude_z
                )
                if seed_halo is None:
                    logger.error("种子轨道生成失败")
                    sys.exit(1)
            amplitude_z = _tag_halo_seed_orbit(
                seed_halo,
                libration_point=libration_point,
                halo_class=halo_class,
                amplitude_z=amplitude_z,
            )
            logger.info("种子轨道生成成功: 周期=%.6f TU", seed_halo.period)

        # 种子修正
        print("[1/3] 开始种子轨道差分修正...")
        corrector.setup_halo_orbit_fixed_z0(
            z0=amplitude_z if halo_class == 0 else -amplitude_z,
            libration_point=libration_point,
        )
        corrected = corrector.iterate_correction(initial_guess=seed_halo, verbose=False)
        if corrected is None:
            raise RuntimeError("种子轨道修正失败")
        print(f"[1/3] 完成，周期 = {corrected.period:.4f} TU")

        # iterate_correction 创建新 Orbit 时不保留 parameters/family_type，需手动回填
        corrected.family_type = "halo"
        corrected.parameters.update({
            "libration_point": libration_point,
            "halo_class": halo_class,
            "amplitude_z": abs(float(np.asarray(corrected.states)[0, 2])),
        })

        # z_range 模式
        z_range = self._resolve_z_range(args, halo_class, corrected)
        if z_range is not None and not (
            z_range[0] <= float(np.asarray(corrected.states)[0, 2]) <= z_range[1]
        ):
            corrected = self._regenerate_boundary_seed(
                continuation, libration_point, halo_class, z_range, args
            )

        # 延拓
        def _on_orbit(i, total, orbit, br):
            dir_label = "正向" if br == "positive" else "负向"
            z0 = float(np.asarray(orbit.states)[0, 2])
            print(
                f"[2/3] {dir_label} #{i}/{total} 完成，"
                f"z0={z0:.4f}，T={float(orbit.period or 0.0):.2f} TU"
            )

        t_start = time.time()
        if method == "natural":
            print("[2/3] 开始自然参数延拓...")
            family_result = continuation.generate_halo_family(
                seed_orbit=corrected,
                n_orbits=n_orbits,
                direction=direction,
                step_size=args.step_size,
                z_range=z_range,
                verbose=False,
                progress_callback=_on_orbit,
            )
            from e2m2e.core.orbit import OrbitFamily
            family = OrbitFamily([corrected])
            for o in family_result[1:]:
                family.add_orbit(o)
            family_result = family
        else:
            print("[2/3] 开始伪弧长延拓...")
            family_result = continuation.halo_pseudo_arclength_continuation(
                seed_orbit=corrected,
                n_orbits=n_orbits,
                direction=direction,
                step_size=step_size,
                step_size_negative=step_size_negative,
                verbose=False,
                progress_callback=_on_orbit,
            )
        print(
            f"[2/3] 完成，共 {len(family_result)} 条轨道，"
            f"耗时 {time.time() - t_start:.1f}s"
        )

        logger.info("轨道族生成完成: 共%d条轨道", len(family_result))

        self._lp = libration_point
        self._hc = halo_class
        self.config = self._build_config(args, libration_point, halo_class)
        self.config.n_milestones = getattr(args, "n_milestones", 5)

        output_dir = self.get_output_dir(project_root)
        output_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        family_name = (
            f"halo_L{libration_point}_{'N' if halo_class == 0 else 'S'}"
            f"_family_{amplitude_z}_{ts}"
        )
        json_path = output_dir / f"{family_name}.json"
        family_result.save_to_file(filename=str(json_path))

        csv_path = export_csv(
            family_result, self.config, output_dir,
            filename_prefix=self._build_csv_filename_parts(args, ts)[0],
        )

        logger.info("轨道族已保存至: %s", json_path)
        logger.info("  轨道族名称: %s", family_name)
        print(f"[3/3] 已保存：")
        print(f"  JSON: {json_path}")
        if csv_path is not None:
            print(f"  CSV:  {csv_path}")

        self._print_halo_summary(
            family_result, libration_point, halo_class, method, step_size,
            step_size_negative if method == "pseudo_arclength" else None,
            direction, z_range=z_range
        )
        return family_result

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _fallback_seed_generation(
        self, continuation, corrector, libration_point, halo_class, amplitude_z
    ) -> Orbit | None:
        """Richardson 近似失效时的硬编码 fallback。"""
        if libration_point == 1 and halo_class == 0 and amplitude_z >= 0.01:
            logger.warning("Richardson 近似失效，使用硬编码参考值生成种子...")
            x0_ref = 0.9305269194214338
            vy0_ref = 0.10431508546142665
            T_ref = 1.839732
            state0 = np.array([
                x0_ref, 0.0,
                amplitude_z if halo_class == 0 else -amplitude_z,
                0.0, vy0_ref, 0.0,
            ])
            corrector.setup_halo_orbit_fixed_z0(
                z0=amplitude_z if halo_class == 0 else -amplitude_z,
                libration_point=libration_point,
            )
            corrector.max_iterations = 150
            corrector.tolerance = 1e-6
            guess = e2m2e.core.Orbit(
                states=state0.reshape(1, -1),
                times=np.array([0.0]),
                system=self.system,
            )
            guess.period = T_ref
            seed = corrector.iterate_correction(guess, verbose=False)
            if seed is not None and seed.correction_success:
                logger.info("硬编码种子修正成功: 周期=%.6f TU", seed.period)
                return seed
            logger.error("硬编码种子修正也失败")
        return None

    def _resolve_z_range(self, args, halo_class, seed_halo):
        """解析 z_range 模式。"""
        if args.z_min is None or args.z_max is None:
            return None
        if args.z_min >= args.z_max:
            logger.error("z_min (%.4f) 必须小于 z_max (%.4f)", args.z_min, args.z_max)
            sys.exit(1)
        if halo_class == 0:
            return (args.z_min, args.z_max)
        return (-args.z_max, -args.z_min)

    def _regenerate_boundary_seed(self, continuation, libration_point, halo_class, z_range, args):
        """当种子 z0 不在 z_range 内时，重新生成边界种子。"""
        new_amp_z = args.z_min if halo_class == 0 else args.z_max
        logger.warning(
            "种子 z0 不在 z_range [%.4f, %.4f] 内，重新生成边界种子...",
            z_range[0], z_range[1],
        )
        seed = continuation.generate_halo_seed_orbit(
            libration_point=libration_point,
            amplitude_z=new_amp_z,
            halo_class=halo_class,
            verbose=False,
        )
        if seed is None:
            logger.error("边界种子轨道生成失败")
            sys.exit(1)
        _tag_halo_seed_orbit(
            seed,
            libration_point=libration_point,
            halo_class=halo_class,
            amplitude_z=new_amp_z,
        )
        logger.info("边界种子生成成功: 周期=%.6f TU, z0=%.6f", seed.period, np.asarray(seed.states)[0, 2])
        return seed

    def _build_csv_filename_parts(self, args: Any, ts: int) -> list[str]:
        """Halo CSV 文件名前缀片段（不含 ts）。

        从 run() 设置的实例变量中获取 libration_point / halo_class。
        基类 ``run()`` 会在最后追加 ts。
        """
        lp = getattr(self, "_lp", 1)
        hc = getattr(self, "_hc", 0)
        lp_name = f"L{lp}"
        class_name = "N" if hc == 0 else "S"
        return [f"halo_{lp_name}_{class_name}_family"]

    def _build_json_filename(self, args: Any, ts: int) -> str:
        """Halo JSON 文件名由 run() 自行管理，此处返回默认值。"""
        return f"halo_family_{ts}"

    def _build_config(
        self, args, libration_point: int, halo_class: int, branches: str | None = None
    ) -> FamilyGeneratorConfig:
        """构建 Halo 的 FamilyGeneratorConfig。"""
        lp_name = f"L{libration_point}"
        title = f"  Earth-Moon {lp_name} {'北' if halo_class == 0 else '南'} Halo 轨道族：配置、统计与代表性轨道"
        return FamilyGeneratorConfig(
            family_type="halo",
            output_subdir="halo",
            summary_title=title,
            summary_columns=["z_amp", "x0", "z0", "Period", "C_Jacobi"],
            csv_format_row=self._csv_format_row,
            summary_format_row=self._summary_format_row,
            n_milestones=getattr(args, "n_milestones", 5),
        )

    @staticmethod
    def _csv_format_row(orbit: Orbit, index: int, is_milestone: bool) -> dict[str, Any]:
        s = orbit.states[0]
        params = getattr(orbit, "parameters", {})
        return {
            "step": index,
            "branch": params.get("branch", "unknown"),
            "z_amp": float(params.get("amplitude_z", abs(float(s[2])))),
            "x0": float(s[0]),
            "y0": float(s[1]),
            "z0": float(s[2]),
            "vx0": float(s[3]),
            "vy0": float(s[4]),
            "vz0": float(s[5]),
            "period": float(orbit.period or 0.0),
            "c_jacobi": float(jacobi_constant(s)),
            "periodicity_error": float(orbit.periodicity_error or 0.0),
            "is_milestone": is_milestone,
        }

    @staticmethod
    def _summary_format_row(orbit: Orbit) -> list[str]:
        s = orbit.states[0]
        params = getattr(orbit, "parameters", {})
        amp_z = params.get("amplitude_z", abs(float(s[2])))
        return [
            f"{float(amp_z):10.6f}",
            f"{float(s[0]):10.6f}",
            f"{float(s[2]):10.6f}",
            f"{float(orbit.period or 0.0):8.4f}",
            f"{float(jacobi_constant(s)):10.6f}",
        ]

    def _print_halo_summary(
        self,
        orbits,
        libration_point: int,
        halo_class: int,
        method: str,
        step_size: float,
        step_size_negative: float | None,
        direction: str,
        z_range: tuple[float, float] | None,
    ) -> None:
        """打印 Halo 摘要表。"""
        lp_name = f"L{libration_point}"
        class_name = "北" if halo_class == 0 else "南"

        extra_lines = [
            f"  平动点       {lp_name}",
            f"  Halo 类别   {class_name} Halo (Class {'I' if halo_class == 0 else 'II'})",
        ]
        if method == "natural":
            extra_lines.append("  延拓方法     自然参数延拓")
            if z_range is not None:
                extra_lines.append(f"  延拓参数     z0 in [{z_range[0]:.6f}, {z_range[1]:.6f}]")
            extra_lines.append(f"  延拓步长     {step_size}")
            extra_lines.append(f"  延拓方向     {direction}")
        else:
            pal_neg = step_size_negative if step_size_negative is not None else step_size
            extra_lines.append("  延拓方法     伪弧长延拓")
            extra_lines.append(f"  正向步长     {step_size}")
            extra_lines.append(f"  负向步长     {pal_neg}")
            extra_lines.append(f"  延拓方向     {direction}")

        cfg = self._build_config(None, libration_point, halo_class)
        print_summary_table(orbits, cfg, extra_lines=extra_lines)


# ------------------------------------------------------------------------------
# 入口
# ------------------------------------------------------------------------------


def main() -> None:
    """Halo 轨道族生成入口。"""
    config = FamilyGeneratorConfig(family_type="halo", output_subdir="halo")
    gen = HaloFamilyGenerator(config)
    args = gen.parse_args()
    setup_logging(args.log_level)
    gen.run(args)


if __name__ == "__main__":
    inject_debug_args(
        sys.argv,
        [
            "--libration-point", "L1",
            "--amplitude-z", "0.001",
            "--halo-class", "1",
            "--n-orbits", "20",
            "--step-size-pal", "0.0045",
            "--direction", "both",
            "--method", "pseudo_arclength",
        ],
    )
    main()
