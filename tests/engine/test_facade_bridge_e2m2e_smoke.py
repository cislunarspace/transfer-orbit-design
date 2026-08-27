"""facade → e2m2e 真路径 smoke 守卫。

mock 测试验证 FacadeBridge 的 DTO 装配，但不验证 e2m2e 真实调用链能否跑通。
e2m2e 升级（如 5.6.5 改 design_orbit 签名 / duration 单位）后，mock 可能仍绿
而真路径已炸。本文件用真 e2m2e + 真 SPICE 内核跑一条最轻量的 design_orbit
（DRO 短弧），守住"facade 能真跑通"这条底线。

需 SPICE 内核（de440s/de430），故 ``@pytest.mark.spice``，CI 默认跳过、本地手跑：
    pytest tests/engine/test_facade_bridge_e2m2e_smoke.py -m spice

English: smoke guards over the real facade → e2m2e path. Mock tests
verify FacadeBridge's DTO assembly but not that the real e2m2e chain
runs; after an e2m2e upgrade (say 5.6.5 changing the design_orbit
signature or duration unit) mocks can stay green while the real path is
broken. This file runs the lightest real design_orbit (a short DRO arc)
with real e2m2e and real SPICE kernels, guarding the "facade really
works" baseline. Needs SPICE kernels (de440s/de430), hence
``@pytest.mark.spice``: skipped by default in CI, run locally via the
command above.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.commons.paths import detect_kernel_dir


@pytest.mark.spice
def test_design_orbit_dro_real_pipeline_converges():
    """FacadeBridge.design_orbit(DRO) 真路径应跑通且修正收敛。

    DRO 走 two_level（Rust 多重打靶），收敛快、轻量。短弧（~1 个月）进一步
    压低耗时。这条测试是 e2m2e 再变签名时唯一能报出来的真路径守卫。

    FacadeBridge.design_orbit(DRO) must run through the real path and
    converge. DRO goes two_level (Rust multi-shooting): fast convergence,
    lightweight; a short arc (~1 month) further cuts cost. This test is
    the only real-path guard that fires when e2m2e changes signatures
    again.
    """
    kernel_dir = detect_kernel_dir()
    if not kernel_dir:
        pytest.skip("无 SPICE 内核（detect_kernel_dir 返回空）")

    from src.engine.facade_bridge import FacadeBridge

    bridge = FacadeBridge(kernel_dir=kernel_dir)
    # duration 单位为年（GUI 标准单位），facade 内部换算成秒。1/12 年 ≈ 1 个月，
    # duration is in years (GUI standard unit) and converted to seconds inside the
    # facade. 1/12 year ~ 1 month:
    # 足以验证完整链路（初猜 → 星历修正 → 长期预报）又不过慢。
    # enough to exercise the full chain (initial guess -> ephemeris correction ->
    # long propagation) without being slow.
    data = bridge.design_orbit(orbit_type="DRO", amplitude=60000.0, duration=1.0 / 12.0)

    assert data.orbit_type == "DRO"
    assert data.correction_converged is True
    assert data.ephemeris is not None
    assert len(data.ephemeris["position_km"]) > 1


@pytest.mark.spice
@pytest.mark.slow
def test_design_orbit_dpo_default_real_pipeline_converges():
    """GUI 默认 DPO 真路径应收敛并产出标称星历（e2m2e 5.8.1 / #484）。

    e2m2e 5.8.0 及以前 DPO 被误归为稳定轨道走单圈修正+自由外推，默认参数必不收敛
    （位置残差 10^3 km 量级）；5.8.1 起 DPO 列入不稳定族，自动重定向 segmented。
    本守卫防止上游回退，也锁住 GUI 默认参数（amplitude=20000 / phase=0.5001）可用。

    The GUI's default DPO real path must converge and produce a nominal
    ephemeris (e2m2e 5.8.1 / #484). Up to e2m2e 5.8.0 DPO was misclassified
    as stable and took one-loop correction + free propagation; default
    parameters never converged (position residuals of order 10^3 km).
    Since 5.8.1 DPO belongs to the unstable family and auto-redirects to
    segmented. This guard prevents upstream regressions and keeps the GUI
    defaults (amplitude=20000 / phase=0.5001) usable.
    """
    kernel_dir = detect_kernel_dir()
    if not kernel_dir:
        pytest.skip("无 SPICE 内核（detect_kernel_dir 返回空）")

    from src.engine.facade_bridge import FacadeBridge

    bridge = FacadeBridge(kernel_dir=kernel_dir)
    data = bridge.design_orbit(
        orbit_type="DPO",
        amplitude=20000.0,
        phase=0.5001,
        duration=1.0 / 365.25,
    )

    assert data.orbit_type == "DPO"
    assert data.correction_converged is True
    assert data.ephemeris is not None


@pytest.mark.spice
@pytest.mark.slow
def test_design_orbit_lissajous_default_reference_stays_bounded():
    """默认 Lissajous 真路径的星历参考轨道应保持在地月尺度内。

        The default-Lissajous real path's
    reference orbit must stay within Earth-Moon scale."""
    kernel_dir = detect_kernel_dir()
    if not kernel_dir:
        pytest.skip("无 SPICE 内核（detect_kernel_dir 返回空）")

    from src.engine.facade_bridge import FacadeBridge

    bridge = FacadeBridge(kernel_dir=kernel_dir)
    data = bridge.design_orbit(
        orbit_type="Lissajous",
        collinear_point=2,
        amplitude_in=2500.0,
        amplitude_out=7500.0,
        phase_in=0.01,
        phase_out=0.55,
        duration=1.0 / 12.0,
    )

    assert data.correction_converged is True
    assert data.ephemeris is not None
    radii_km = np.linalg.norm(data.ephemeris["position_km"], axis=1)
    assert radii_km.max() < 500_000.0
    assert radii_km[-1] < 500_000.0


@pytest.mark.spice
@pytest.mark.slow
def test_design_orbit_nrho_default_converges_with_ephemeris():
    """GUI 默认量级 NRHO 真路径应收敛并产出对齐的标称星历（e2m2e 5.7.3 / #473）。

    依赖上游等时间采样 + 1 圈/段；本守卫防止再退回「旁路只交 CR3BP」或
    算法不收敛，并锁星历各槽等长（5.7.2 曾因采样未钉历元而错位）。

    The GUI-default NRHO real path must converge and produce an aligned
    nominal ephemeris (e2m2e 5.7.3 / #473). Depends on upstream equal-time
    sampling plus 1 loop per segment; this guard prevents regressing to
    the bypass (CR3BP only) or non-convergence, and locks the ephemeris
    slots to equal lengths (misaligned in 5.7.2 when sampling did not pin
    epochs).
    """
    kernel_dir = detect_kernel_dir()
    if not kernel_dir:
        pytest.skip("无 SPICE 内核（detect_kernel_dir 返回空）")

    from src.engine.facade_bridge import FacadeBridge

    bridge = FacadeBridge(kernel_dir=kernel_dir)
    data = bridge.design_orbit(
        orbit_type="NRHO",
        collinear_point=2,
        north_south=2,
        perilune_height=5000.0,
        phase=0.5,
        duration=1.0 / 12.0,
    )

    assert str(data.orbit_type).upper() == "NRHO"
    assert data.correction_converged is True
    assert data.ephemeris is not None
    eph = data.ephemeris
    # 星历各槽等长（位置/速度/时间一一对应），并覆盖整个设计弧
    # All ephemeris slots are equal length (positions/velocities/times one-to-one)
    # and cover the whole designed arc
    assert len(eph["position_km"]) == len(eph["velocity_mps"])
    assert len(eph["position_km"]) == len(eph["year"])
    assert len(eph["position_km"]) > 1
    # 真物理时间覆盖整个设计弧：1/12 年 ≈ 2.63e6 s，断言不短于 1.5e6 s
    # True physical time covers the whole arc: 1/12 year ~ 2.63e6 s; assert no shorter than 1.5e6 s
    assert eph["times_et"][-1] - eph["times_et"][0] > 1.5e6
    assert data.states is not None and len(data.states) > 1


@pytest.mark.spice
@pytest.mark.slow
def test_design_orbit_axial_default_real_pipeline_converges():
    """GUI 默认 Axial 真路径应收敛。

    e2m2e 5.8.0 默认 Axial 星历修正不收敛（自由时间打靶因 1:1 共振简并停滞），
    曾以 strict xfail 锁住缺口；上游修复已随 5.8.2 发布，移除 xfail 恢复承诺。

    The GUI-default Axial real path must converge. In e2m2e 5.8.0 the
    default Axial ephemeris correction failed to converge (free-time
    targeting stalled on a 1:1 resonance degeneracy); a strict xfail used
    to pin this gap until upstream fixed it in 5.8.2 — xfail removed,
    promise restored.
    """
    kernel_dir = detect_kernel_dir()
    if not kernel_dir:
        pytest.skip("无 SPICE 内核（detect_kernel_dir 返回空）")

    from src.engine.facade_bridge import FacadeBridge

    bridge = FacadeBridge(kernel_dir=kernel_dir)
    data = bridge.design_orbit(
        orbit_type="Axial",
        collinear_point=2,
        amplitude=5000.0,
        phase=0.0,
        duration=1.0 / 12.0,
    )

    assert str(data.orbit_type).upper() == "AXIAL"
    assert data.correction_converged is True
    assert data.ephemeris is not None
    assert len(data.ephemeris["position_km"]) > 1
