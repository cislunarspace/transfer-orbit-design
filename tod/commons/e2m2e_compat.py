"""e2m2e 旧路径兼容层（过渡 shim）。

e2m2e 在 v5.3.x 完成五层架构迁移（ADR 0011）并删除了旧包：
``e2m2e.core`` / ``e2m2e.algorithms`` / ``e2m2e.transfer`` /
``e2m2e.visualization`` / ``e2m2e.orbits``。本仓库（tod/）仍有 42 个文件
从旧路径导入，约 75 个测试 patch 点也以字符串/属性方式引用旧模块对象。

本模块在 ``sys.modules`` 中安装**虚拟旧路径模块**，把旧符号 re-export 到五层
新位置，使既有代码与测试无需逐文件改动即可继续工作。这是过渡桥，不是终态：
随 ``tod/generates|transfers|plot`` 脚本层按能力迁入 e2m2e api/CLI（Phase 2），
逐步删除对应别名，最终删除本 shim。

设计要点：

- :func:`install` 幂等：以 ``sys.modules`` 是否有对应键为守卫，重复调用安全。
- 安装时机：由 ``tod/commons/constants.py`` 模块顶部自引导调用（几乎每个计算
  脚本都经 ``tod.commons.constants`` 间接导入），并在 ``tod/__init__.py``
  兜底调用（覆盖 ``import tod`` 先行的场景）。
- ``e2m2e.algorithms`` / ``e2m2e.core`` / ``e2m2e.transfer`` 等是**真实模块对象**，
  测试对 ``mod.e2m2e.algorithms.DifferentialCorrection`` 的属性 patch 与字符串
  patch 继续作用于这些模块对象，语义与旧包一致。
- ``e2m2e.transfer`` 不整体 alias ``e2m2e.algorithm.transfer`` 包——其 ``__init__``
  曾因 r2s2 缺失而失败；改为按符号 re-export，避免拖入整包依赖。
"""

from __future__ import annotations

import sys
import types
from typing import Any


def _set_parent_attr(name: str) -> None:
    """把 ``sys.modules[name]`` 挂到其父包模块对象的同名属性上。

    Python 只在对**新加载**的子模块设置父包属性；对预置在 sys.modules 里的
    虚拟模块不会自动设置。生产代码常 ``import e2m2e`` 后以 ``e2m2e.core.X``
    属性访问，因此必须手动把 ``core`` 等挂到真实 ``e2m2e`` 包对象上。
    """
    mod = sys.modules.get(name)
    if mod is None:
        return
    parts = name.split(".")
    # 只设置最后一段属性（挂到直接父模块），避免中间段被后续子模块覆盖。
    parent_name = ".".join(parts[:-1])
    parent = sys.modules.get(parent_name)
    if parent is not None:
        try:
            setattr(parent, parts[-1], mod)
        except (AttributeError, TypeError):
            pass


def _install_alias(new_name: str, old_name: str) -> None:
    """把新路径模块 ``new_name`` 以旧名字 ``old_name`` 登记到 sys.modules。

    幂等：old_name 已在 sys.modules 时跳过。
    """
    if old_name in sys.modules:
        return
    try:
        __import__(new_name)
    except ModuleNotFoundError:
        # 该新路径在当前环境不可用（如可选依赖缺失），跳过不安装。
        return
    sys.modules[old_name] = sys.modules[new_name]
    _set_parent_attr(old_name)


def _re_export(old_name: str, **symbols: Any) -> None:
    """创建一个虚拟旧路径模块，把给定符号作为其属性。

    Args:
        old_name: 虚拟模块名（如 ``"e2m2e.core"``）。
        **symbols: 属性名 → 实际对象。值可为可调用（懒解析）或直接对象。
    """
    if old_name in sys.modules:
        return
    mod = types.ModuleType(old_name)
    mod.__doc__ = f"e2m2e 旧路径兼容虚拟模块（由 tod.commons.e2m2e_compat 安装）。"
    for name, value in symbols.items():
        setattr(mod, name, value)
    sys.modules[old_name] = mod
    _set_parent_attr(old_name)


def _re_export_module(old_name: str, new_name: str) -> None:
    """创建一个虚拟旧路径模块，整模块转发到新路径模块（含其属性）。

    对 ``import e2m2e.core.ephemeris_dynamics as ed`` 这类「以模块对象访问属性」
    的用法，需要旧模块对象能转发对新模块属性的访问。这里直接安装同对象的别名，
    使 ``ed._HAS_RUST_STM`` 等属性访问继续有效。
    """
    if old_name in sys.modules:
        return
    try:
        __import__(new_name)
    except ModuleNotFoundError:
        return
    sys.modules[old_name] = sys.modules[new_name]
    _set_parent_attr(old_name)


def install() -> None:
    """安装全部 e2m2e 旧路径别名（幂等）。"""
    # ---- e2m2e.core 与子模块 ----
    from e2m2e.algorithm.dynamics import (  # noqa: F401
        CR3BP_Dynamics,
        CR3BP_System,
        Dynamics,
        EphemerisDynamics,
        EphemerisSystem,
        LibrationPoint,
    )
    from e2m2e.algorithm.coordinate.synodic_j2000 import (  # noqa: F401
        SynodicJ2000System,
    )
    from e2m2e.data.types.orbit import Orbit, OrbitFamily  # noqa: F401
    from e2m2e.data.kernels.manager import SPICEManager  # noqa: F401

    _re_export(
        "e2m2e.core",
        CR3BP_System=CR3BP_System,
        CR3BP_Dynamics=CR3BP_Dynamics,
        Dynamics=Dynamics,
        EphemerisSystem=EphemerisSystem,
        EphemerisDynamics=EphemerisDynamics,
        LibrationPoint=LibrationPoint,
        SynodicJ2000System=SynodicJ2000System,
        Orbit=Orbit,
        OrbitFamily=OrbitFamily,
        SPICEManager=SPICEManager,
    )
    _re_export_module("e2m2e.core.orbit", "e2m2e.data.types.orbit")
    _re_export_module(
        "e2m2e.core.ephemeris_system", "e2m2e.algorithm.dynamics.ephemeris_system"
    )
    _re_export_module(
        "e2m2e.core.ephemeris_dynamics", "e2m2e.algorithm.dynamics.ephemeris_dynamics"
    )
    _re_export_module("e2m2e.core.spice", "e2m2e.data.kernels.manager")

    # ---- e2m2e.algorithms 与子模块 ----
    from e2m2e.algorithm.solver import (  # noqa: F401
        Continuation,
        DifferentialCorrection,
        MultipleShooting,
        convert_to_j2000,
        sample_patch_points,
    )
    from e2m2e.algorithm.stability import StabilityAnalysis  # noqa: F401
    from e2m2e.algorithm.family import (  # noqa: F401
        compute_halo_coefficients,
        halo_third_order_approximation,
    )

    _re_export(
        "e2m2e.algorithms",
        DifferentialCorrection=DifferentialCorrection,
        Continuation=Continuation,
        MultipleShooting=MultipleShooting,
        convert_to_j2000=convert_to_j2000,
        sample_patch_points=sample_patch_points,
        StabilityAnalysis=StabilityAnalysis,
        compute_halo_coefficients=compute_halo_coefficients,
        halo_third_order_approximation=halo_third_order_approximation,
    )
    _re_export_module(
        "e2m2e.algorithms.ephemeris_correction",
        "e2m2e.algorithm.ephemeris_correction",
    )
    _re_export_module("e2m2e.algorithms.stability", "e2m2e.algorithm.stability")

    # ---- e2m2e.transfer ----
    # 不 alias 整包（包 __init__ 曾依赖 coordinate → r2s2），按符号 re-export。
    from e2m2e.algorithm.transfer import (  # noqa: F401
        DROTRONLPOptimizer,
        NLPOptimizationVariables,
        TransferOptimizationResult,
        optimize_with_copt,
    )
    from e2m2e.algorithm.transfer.transfer_search import (  # noqa: F401
        TransferSearch,
        load_orbit_from_json,
    )

    _re_export(
        "e2m2e.transfer",
        TransferSearch=TransferSearch,
        load_orbit_from_json=load_orbit_from_json,
        DROTRONLPOptimizer=DROTRONLPOptimizer,
        NLPOptimizationVariables=NLPOptimizationVariables,
        TransferOptimizationResult=TransferOptimizationResult,
        optimize_with_copt=optimize_with_copt,
    )

    # ---- e2m2e.visualization ----
    try:
        from e2m2e.tools.viz import (  # noqa: F401
            FamilyPlotter,
            OrbitVisualizer,
            PlotConfig,
        )
    except ModuleNotFoundError:
        # matplotlib / [viz] extra 缺失时降级：不安装别名，相关脚本在真正用时失败。
        FamilyPlotter = PlotConfig = OrbitVisualizer = None  # type: ignore[assignment]

    if FamilyPlotter is not None:
        _re_export(
            "e2m2e.visualization",
            FamilyPlotter=FamilyPlotter,
            PlotConfig=PlotConfig,
            OrbitVisualizer=OrbitVisualizer,
        )
        _re_export_module("e2m2e.visualization.base", "e2m2e.tools.viz.base")
