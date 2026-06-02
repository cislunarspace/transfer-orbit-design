"""generate_dro_orbit 轨道生成脚本。

本模块在地月 CR3BP 中通过手动初值 + 固定周期微分修正生成单条 DRO 轨道。
输入为命令行给出的初始状态和周期猜测；输出为 output/dro/ 下的单条 DRO JSON 文件。

运行示例:
    .. code-block:: bash

       uv run python -m tod.generates.cr3bp.dro.generate_dro_orbit --help
"""


from __future__ import annotations

import argparse
import logging
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import e2m2e
import numpy as np
from e2m2e.core import Orbit
from scipy import integrate as sci_integrate
from tod.commons.constants import MU, TU
from tod.generates.cr3bp.importer import (
    Cr3bpCatalogLookupError,
    Cr3bpImportError,
    Cr3bpImportSchemaError,
    OrbitRecord,
    import_cr3bp_xlsx_catalog,
    load_cr3bp_catalog,
)

_LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
_DEFAULT_LOG_LEVEL = "WARNING"
DEFAULT_DRO_X0 = 1.1202
DEFAULT_DRO_VY0 = -0.4618
DEFAULT_DRO_PERIOD = 2.095
CATALOG_INTEGRATOR = "DOP853"
CATALOG_RTOL = 1e-12
CATALOG_ATOL = 1e-12

logger = logging.getLogger(__name__)

project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
OUTPUT_DIR = project_root / "output" / "dro"


@dataclass(frozen=True)
class CatalogSeed:
    """DRO catalog 中选出的单条 seed。"""

    source: str
    record: OrbitRecord
    target_jacobi: float | None = None
    tolerance: float | None = None

    @property
    def initial_state(self) -> list[float]:
        return self.record.state

    @property
    def period(self) -> float:
        return self.record.period


def _parse_log_level(level_str: str) -> int:
    return getattr(logging, level_str.upper(), logging.WARNING)


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0.0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return parsed


def _num_points(value: str) -> int:
    parsed = int(value)
    if not 2 <= parsed <= 100000:
        raise argparse.ArgumentTypeError("must be between 2 and 100000")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    """构造单条 DRO 生成器 CLI parser。"""
    parser = argparse.ArgumentParser(
        description="生成 DRO 轨道（手动初值 + 固定周期微分校正）",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--x0", type=float, default=None, help="初始 x 坐标（无量纲）")
    parser.add_argument("--vy0", type=float, default=None, help="初始 y 方向速度（无量纲）")
    parser.add_argument("--period", type=float, default=None, help="目标周期（无量纲）")
    catalog_group = parser.add_mutually_exclusive_group()
    catalog_group.add_argument("--jacobi", type=float, default=None, help="按目标 Jacobi 值从 normalized DRO catalog 选择 seed")
    catalog_group.add_argument("--seed-id", type=str, default=None, help="按 seed/orbit id 从 normalized DRO catalog 选择 seed")
    parser.add_argument("--jacobi-tolerance", type=float, default=None, help="Jacobi 最近邻匹配容差；未提供时不启用硬容差")
    parser.add_argument("--period-multiplier", type=_positive_float, default=1.0, help="catalog 周期外推倍数")
    parser.add_argument("--num-points", type=_num_points, default=1000, help="catalog 外推轨迹采样点数")
    parser.add_argument("--catalog-dir", type=Path, default=Path("data/cr3bp_data/normalized"), help="normalized CR3BP catalog 目录")
    parser.add_argument("--raw-data-dir", type=Path, default=Path("data/cr3bp_data/raw"), help="raw CR3BP XLSX 数据目录")
    parser.add_argument("--no-auto-build-catalog", action="store_true", help="normalized catalog 缺失时不自动从 raw 数据生成")
    parser.add_argument(
        "--log-level",
        type=str,
        default=_DEFAULT_LOG_LEVEL,
        choices=_LOG_LEVELS,
        help="日志级别",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="显示详细迭代过程（残差、收敛进度等）",
    )
    return parser


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """解析命令行参数。"""
    return build_parser().parse_args(argv)


def _setup_logging(level_str: str) -> None:
    logging.basicConfig(
        level=_parse_log_level(level_str),
        format="%(levelname)s: %(message)s",
    )


def _validate_args(args: argparse.Namespace) -> None:
    """校验手动模式与 catalog 模式的互斥输入。"""
    catalog_flags = [flag for flag, value in (("--seed-id", args.seed_id), ("--jacobi", args.jacobi)) if value is not None]
    manual_flags = [flag for flag, value in (("--x0", args.x0), ("--vy0", args.vy0), ("--period", args.period)) if value is not None]
    if catalog_flags and manual_flags:
        raise SystemExit(
            "catalog 模式不能与显式 manual 参数混用: "
            f"{', '.join(catalog_flags)} 与 {', '.join(manual_flags)} 冲突。"
        )


def _manual_seed_metadata(initial_state: list[float], period: float) -> dict[str, object]:
    """返回 manual seed 路径写入单轨 JSON 的 provenance metadata。"""
    return {
        "seed_source": "manual",
        "initial_state": initial_state,
        "period": period,
        "is_corrected": True,
        "generation_method": "fixed_period_differential_correction",
    }


def _catalog_seed_metadata(seed: CatalogSeed, *, period_multiplier: float, num_points: int) -> dict[str, object]:
    """返回 catalog seed 路径写入单轨 JSON 的 provenance metadata。"""
    propagation_duration = seed.period * period_multiplier
    metadata: dict[str, object] = {
        "seed_source": seed.source,
        "selection_mode": "jacobi" if seed.target_jacobi is not None else "seed_id",
        "seed_id": seed.record.orbit_id,
        "matched_seed_id": seed.record.orbit_id,
        "initial_state": seed.initial_state,
        "period": seed.period,
        "period_multiplier": period_multiplier,
        "propagation_duration": propagation_duration,
        "num_points": num_points,
        "integrator": CATALOG_INTEGRATOR,
        "rtol": CATALOG_RTOL,
        "atol": CATALOG_ATOL,
        "is_corrected": False,
        "generation_method": "catalog_seed_propagation",
        "source_file": seed.record.source_file,
        "source_row": seed.record.source_row,
    }
    if seed.target_jacobi is not None:
        metadata.update(
            {
                "target": seed.target_jacobi,
                "actual": seed.record.jacobi,
                "error": abs(seed.record.jacobi - seed.target_jacobi),
                "target_jacobi": seed.target_jacobi,
                "matched_jacobi": seed.record.jacobi,
                "jacobi_delta": abs(seed.record.jacobi - seed.target_jacobi),
                "tolerance": seed.tolerance,
            }
        )
    return metadata


def _ensure_catalog_available(args: argparse.Namespace) -> None:
    index_file = args.catalog_dir / "index.csv"
    dro_file = args.catalog_dir / "families" / "dro.csv"
    if index_file.exists() and dro_file.exists():
        return
    if args.no_auto_build_catalog:
        raise SystemExit(
            "normalized CR3BP catalog 缺失；请先运行 importer，或移除 --no-auto-build-catalog 允许自动生成。"
        )
    import_cr3bp_xlsx_catalog(args.raw_data_dir, args.catalog_dir, overwrite=False)


def _select_catalog_seed(args: argparse.Namespace) -> CatalogSeed:
    try:
        _ensure_catalog_available(args)
        catalog = load_cr3bp_catalog(args.catalog_dir)
        if args.seed_id is not None:
            for record in catalog.records(orbit_type="dro"):
                if record.orbit_id == args.seed_id:
                    return CatalogSeed(source="catalog_seed_id", record=record)
            raise SystemExit(f"未找到 DRO catalog seed_id={args.seed_id!r}；catalog_dir={args.catalog_dir}")

        record = catalog.nearest_jacobi("dro", args.jacobi, tolerance=args.jacobi_tolerance)
        return CatalogSeed(
            source="catalog_jacobi",
            record=record,
            target_jacobi=args.jacobi,
            tolerance=args.jacobi_tolerance,
        )
    except Cr3bpCatalogLookupError as exc:
        raise SystemExit(
            f"DRO catalog 查找失败：catalog_dir={args.catalog_dir}, "
            f"seed_id={args.seed_id!r}, jacobi={args.jacobi!r}, tolerance={args.jacobi_tolerance!r}: {exc}"
        ) from exc
    except Cr3bpImportSchemaError as exc:
        raise SystemExit(f"DRO catalog CSV 无效：catalog_dir={args.catalog_dir}: {exc}") from exc
    except Cr3bpImportError as exc:
        raise SystemExit(f"DRO catalog 加载失败：catalog_dir={args.catalog_dir}: {exc}") from exc


def _propagate_catalog_seed(
    initial_state: list[float],
    period: float,
    dynamics,
    *,
    period_multiplier: float = 1.0,
    num_points: int = 1000,
) -> Orbit:
    duration = period * period_multiplier
    times = np.linspace(0.0, duration, num_points)
    result = sci_integrate.solve_ivp(
        dynamics.equations_of_motion,
        (0.0, duration),
        initial_state,
        method=CATALOG_INTEGRATOR,
        rtol=CATALOG_RTOL,
        atol=CATALOG_ATOL,
        t_eval=times,
    )
    if not result.success:
        raise RuntimeError(f"catalog seed propagation failed: {result.message}")
    orbit = Orbit(states=result.y.T.tolist(), times=result.t.tolist())
    orbit.period = duration
    return orbit


def _safe_filename_part(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "seed"


def _save_orbit(orbit: Orbit, metadata: dict[str, object], *, seed_id: str | None = None) -> Path:
    orbit.metadata.update(metadata)
    ts = int(time.time())
    if seed_id is None:
        filename = f"dro_{ts}.json"
    else:
        filename = f"dro_catalog_{_safe_filename_part(seed_id)}_{ts}.json"
    output_file = OUTPUT_DIR / filename
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    orbit.save_to_file(filename=str(output_file))
    return output_file


def main(argv: Sequence[str] | None = None) -> None:
    """执行脚本主流程。"""
    args = parse_args(argv)
    _validate_args(args)
    _setup_logging(args.log_level)

    system = e2m2e.core.system.CR3BP_System(mu=MU, primary="earth", secondary="moon")
    dynamics = e2m2e.core.dynamics.CR3BP_Dynamics(system=system)

    x0 = args.x0 if args.x0 is not None else DEFAULT_DRO_X0
    vy0 = args.vy0 if args.vy0 is not None else DEFAULT_DRO_VY0
    target_period = args.period if args.period is not None else DEFAULT_DRO_PERIOD
    t_half = target_period / 2

    if args.seed_id is not None or args.jacobi is not None:
        seed = _select_catalog_seed(args)
        print(f"[1/2] 使用 catalog seed: {seed.record.orbit_id}")
        orbit_result = _propagate_catalog_seed(
            seed.initial_state,
            seed.period,
            dynamics,
            period_multiplier=args.period_multiplier,
            num_points=args.num_points,
        )
        output_file = _save_orbit(
            orbit_result,
            _catalog_seed_metadata(seed, period_multiplier=args.period_multiplier, num_points=args.num_points),
            seed_id=seed.record.orbit_id,
        )
        print(f"[2/2] 已保存至: {output_file}")
        return

    print("[1/2] 开始微分修正...")
    if args.verbose:
        print("  目标轨道: DRO")
        print(f"  初始状态: x0={x0}, vy0={vy0}")
        print(f"  目标周期: {target_period:.4f} TU ({target_period * TU:.2f} days)")

    corrector = e2m2e.algorithms.DifferentialCorrection(dynamic=dynamics)
    corrector.setup_2D_symmetric_x_fixed_t(t_half=t_half)

    initial_state = [x0, 0.0, 0.0, 0.0, vy0, 0.0]
    orbit_init = Orbit(states=[initial_state], times=[0])

    def on_iteration(iteration, error, converged):
        """输出 verbose 模式下的微分修正迭代进度。"""
        if args.verbose:
            tag = " [收敛]" if converged else ""
            print(f"  迭代 {iteration}: 残差 {error:.2e}{tag}")

    orbit_result = corrector.iterate_correction(
        initial_guess=orbit_init,
        verbose=False,
        callback=on_iteration,
    )

    if orbit_result is not None:
        print(f"[1/2] 完成，修正后周期 = {orbit_result.period:.6f} TU ({orbit_result.period * TU:.4f} days)")

        output_file = _save_orbit(orbit_result, _manual_seed_metadata(initial_state, target_period))
        print(f"[2/2] 已保存至: {output_file}")
    else:
        print(f"[ERROR] 修正失败: {corrector.termination_reason}")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv += [
            "--x0", "1.1202",
            "--vy0", "-0.4618",
            "--period", "2.095",
        ]
        logger.debug("使用代码内置调试参数")
    main()
