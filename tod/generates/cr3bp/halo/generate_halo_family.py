"""generate_halo_family 轨道生成脚本。

本模块在地月 CR3BP 中构造 Halo 种子轨道，调用 e2m2e 的微分修正和
伪弧长延拓算法生成 Halo 轨道族。

支持：L1/L2/L3 平动点，北/南分支。

本脚本通过 ``FamilyGenerator`` 基类实现，族特有逻辑在子类 hook 中声明
（种子获取、修正配置、延拓执行），共享流程（系统初始化、保存、
CSV 导出、摘要表打印）由基类处理。

运行示例:
    .. code-block:: bash

       uv run python -m tod.generates.cr3bp.halo.generate_halo_family --help
"""


from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

import numpy as np

import e2m2e
from e2m2e.core import Orbit

from tod.generates.cr3bp._family_pipeline import (
    FamilyGenerator,
    FamilyGeneratorConfig,
    inject_debug_args,
    jacobi_constant,
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


# ------------------------------------------------------------------------------
# 参数与验证
# ------------------------------------------------------------------------------



# ------------------------------------------------------------------------------
# Halo 族生成器
# ------------------------------------------------------------------------------


class HaloFamilyGenerator(FamilyGenerator):
    """Halo 轨道族生成器。

    通过基类 hook 方法实现 Halo 特有的种子获取、修正配置和伪弧长延拓。
    不覆盖基类 ``run()``，共享保存和摘要输出逻辑。

    支持的延拓方法：伪弧长延拓（PAL）。
    种子获取策略：Richardson 三阶近似 → 预存实验初值 fallback。
    """

    # ------------------------------------------------------------------
    # hook: 种子获取
    # ------------------------------------------------------------------

    def _get_seed_orbit(self, args: Any):
        """获取 Halo 种子轨道。

        两条路径：
        - ``--seed-file`` 指定时从 JSON 加载。
        - 自动生成：先尝试 e2m2e Richardson 近似，失败后使用预存实验初值 fallback。

        Returns:
            带有 Halo 参数标签的种子轨道。

        Raises:
            RuntimeError: 种子生成和 fallback 均失败。
        """
        libration_point = LIBRATION_POINT_MAP[args.libration_point]
        halo_class = args.halo_class
        amplitude_z = args.amplitude_z

        # 路径 A：从文件加载种子
        if args.seed_file:
            logger.info("从文件加载种子轨道: %s", args.seed_file)
            seed_halo = _load_seed_orbit(args.seed_file, system=self.system)
            _tag_halo_seed_orbit(
                seed_halo,
                libration_point=libration_point,
                halo_class=halo_class,
                amplitude_z=abs(float(np.asarray(seed_halo.states)[0, 2])),
            )
            logger.info("种子轨道加载成功: 周期=%.6f TU", seed_halo.period)
            return seed_halo

        # 路径 B：自动生成
        logger.info(
            "正在生成种子轨道: L%d %s Halo",
            libration_point,
            "北" if halo_class == 0 else "南",
        )
        continuation = e2m2e.algorithms.Continuation(
            corrector=e2m2e.algorithms.DifferentialCorrection(dynamic=self.dynamics),
        )
        seed_halo = continuation.generate_halo_seed_orbit(
            libration_point=libration_point,
            amplitude_z=amplitude_z,
            halo_class=halo_class,
            verbose=False,
        )

        # Richardson 近似失败时尝试 fallback
        if seed_halo is None:
            seed_halo = self._fallback_seed_generation(
                libration_point, halo_class, amplitude_z,
            )
            if seed_halo is None:
                raise RuntimeError("种子轨道生成失败")

        _tag_halo_seed_orbit(
            seed_halo,
            libration_point=libration_point,
            halo_class=halo_class,
            amplitude_z=amplitude_z,
        )
        logger.info("种子轨道生成成功: 周期=%.6f TU", seed_halo.period)
        return seed_halo

    # ------------------------------------------------------------------
    # hook: 修正器配置
    # ------------------------------------------------------------------

    def _setup_corrector(self, args: Any) -> Any:
        """创建并配置 Halo 微分修正器。

        北族 z0 为正，南族 z0 为负。
        """
        corrector = e2m2e.algorithms.DifferentialCorrection(dynamic=self.dynamics)
        libration_point = LIBRATION_POINT_MAP[args.libration_point]
        amplitude_z = args.amplitude_z
        halo_class = args.halo_class
        z0 = amplitude_z if halo_class == 0 else -amplitude_z
        corrector.setup_halo_orbit_fixed_z0(z0=z0, libration_point=libration_point)
        return corrector

    # ------------------------------------------------------------------
    # hook: 修正 + 参数回填
    # ------------------------------------------------------------------

    def _correct_seed_orbit(self, corrector: Any, seed_orbit: Any, args: Any):
        """执行微分修正并回填 Halo 参数标签。

        调用基类 ``_correct_seed_orbit`` 获取修正后的轨道，
        然后回填 ``family_type``、``libration_point``、``halo_class``、
        ``amplitude_z``。修正和标记作为原子操作完成。
        """
        corrected = super()._correct_seed_orbit(corrector, seed_orbit, args)
        if corrected is not None:
            libration_point = LIBRATION_POINT_MAP[args.libration_point]
            halo_class = args.halo_class
            corrected.family_type = "halo"
            params = getattr(corrected, "parameters", None)
            if not isinstance(params, dict):
                params = {}
                corrected.parameters = params
            params["libration_point"] = libration_point
            params["halo_class"] = halo_class
            params["amplitude_z"] = abs(float(np.asarray(corrected.states)[0, 2]))
        return corrected

    # ------------------------------------------------------------------
    # hook: 延拓执行
    # ------------------------------------------------------------------

    def _run_continuation(self, corrector: Any, seed_orbit: Any, args: Any):
        """延拓路由：根据 args.method 分发到对应延拓方法。

        Raises:
            ValueError: 未实现的延拓方法。
        """
        method = args.method
        if method == "pseudo_arclength":
            return self._run_pal_continuation(corrector, seed_orbit, args)
        raise ValueError(f"未实现的延拓方法: {method}")

    def _run_pal_continuation(self, corrector: Any, seed_orbit: Any, args: Any):
        """伪弧长延拓（PAL）生成 Halo 轨道族。"""
        step_size = args.step_size_pal

        continuation = e2m2e.algorithms.Continuation(corrector=corrector)

        def _on_orbit(i, total, orbit, br):
            dir_label = "正向" if br == "positive" else "负向"
            z0_val = float(np.asarray(orbit.states)[0, 2])
            print(
                f"  {dir_label} #{i}/{total} 完成，"
                f"z0={z0_val:.4f}，T={float(orbit.period or 0.0):.2f} TU"
            )

        family_result = continuation.halo_pseudo_arclength_continuation(
            seed_orbit=seed_orbit,
            n_orbits=args.n_orbits,
            direction="both",
            step_size=step_size,
            verbose=False,
            progress_callback=_on_orbit,
        )
        return family_result

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _fallback_seed_generation(
        self, libration_point: int, halo_class: int, amplitude_z: float,
    ) -> Orbit | None:
        """Richardson 近似失效时的硬编码 fallback。

        使用预存的实验初值构造初始猜测，通过微分修正获得种子轨道。
        当前仅覆盖 L1 北族 + amplitude_z >= 0.01 的参数空间。
        """
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
            corrector = e2m2e.algorithms.DifferentialCorrection(dynamic=self.dynamics)
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

    # ------------------------------------------------------------------
    # CLI 参数
    # ------------------------------------------------------------------

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
            "--method",
            type=str,
            default="pseudo_arclength",
            choices=["pseudo_arclength"],
            help="延拓方法：pseudo_arclength（伪弧长延拓）",
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
            help="自然延拓步长（预留给自然延拓方法）",
        )
        parser.add_argument(
            "--step-size-pal",
            type=float,
            default=0.0045,
            help="伪弧长延拓步长 |Δs|",
        )
        parser.add_argument(
            "--seed-file",
            type=str,
            default=None,
            help="种子轨道 JSON 文件路径（提供时跳过种子生成）",
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

    # ------------------------------------------------------------------
    # 文件名构造
    # ------------------------------------------------------------------

    def _build_csv_filename_parts(self, args: Any, ts: int) -> list[str]:
        """Halo CSV 文件名前缀片段。

        从 args 提取参数，不依赖 self._lp / self._hc 实例变量。
        返回 [前缀, ts]，基类拼接为 halo_L{lp}_{N|S}_family_{ts}.csv。
        """
        libration_point = LIBRATION_POINT_MAP[args.libration_point]
        halo_class = args.halo_class
        lp_name = f"L{libration_point}"
        class_name = "N" if halo_class == 0 else "S"
        return [f"halo_{lp_name}_{class_name}_family", str(ts)]

    def _build_json_filename(self, args: Any, ts: int) -> str:
        """Halo JSON 文件名：halo_L{lp}_{N|S}_family_{amplitude_z}_{ts}。

        从 args 提取参数，不依赖 self._lp / self._hc 实例变量。
        """
        libration_point = LIBRATION_POINT_MAP[args.libration_point]
        halo_class = args.halo_class
        amplitude_z = args.amplitude_z
        class_name = "N" if halo_class == 0 else "S"
        return f"halo_L{libration_point}_{class_name}_family_{amplitude_z}_{ts}"

    # ------------------------------------------------------------------
    # 格式化回调（静态方法，由 config 引用）
    # ------------------------------------------------------------------

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


# ------------------------------------------------------------------------------
# 入口
# ------------------------------------------------------------------------------


def main() -> None:
    """Halo 轨道族生成入口。"""
    config = FamilyGeneratorConfig(
        family_type="halo",
        output_subdir="halo",
        summary_title="  Earth-Moon Halo 轨道族：配置、统计与代表性轨道",
        summary_columns=["z_amp", "x0", "z0", "Period", "C_Jacobi"],
        csv_format_row=HaloFamilyGenerator._csv_format_row,
        summary_format_row=HaloFamilyGenerator._summary_format_row,
        n_milestones=5,
    )
    gen = HaloFamilyGenerator(config)
    args = gen.parse_args()
    setup_logging(args.log_level)

    # 摘要额外信息需要 args，通过回调注入
    def _summary_extra_info():
        libration_point = LIBRATION_POINT_MAP[args.libration_point]
        halo_class = args.halo_class
        step_size = args.step_size_pal
        lp_name = f"L{libration_point}"
        class_name = "北" if halo_class == 0 else "南"
        method_label = {"pseudo_arclength": "伪弧长延拓"}.get(args.method, args.method)
        lines = [
            f"  平动点       {lp_name}",
            f"  Halo 类别   {class_name} Halo (Class {'I' if halo_class == 0 else 'II'})",
            f"  延拓方法     {method_label}",
            f"  延拓步长     {step_size}",
        ]
        return lines

    config.summary_extra_info = _summary_extra_info

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
        ],
    )
    main()
