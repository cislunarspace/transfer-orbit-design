"""facade → e2m2e 真路径 smoke 守卫。

mock 测试验证 FacadeBridge 的 DTO 装配，但不验证 e2m2e 真实调用链能否跑通。
e2m2e 升级（如 5.6.5 改 design_orbit 签名 / duration 单位）后，mock 可能仍绿
而真路径已炸。本文件用真 e2m2e + 真 SPICE 内核跑一条最轻量的 design_orbit
（DRO 短弧），守住"facade 能真跑通"这条底线。

需 SPICE 内核（de440s/de430），故 ``@pytest.mark.spice``，CI 默认跳过、本地手跑：
    pytest tests/engine/test_facade_bridge_e2m2e_smoke.py -m spice
"""

from __future__ import annotations

import pytest

from src.commons.paths import detect_kernel_dir


@pytest.mark.spice
def test_design_orbit_dro_real_pipeline_converges():
    """FacadeBridge.design_orbit(DRO) 真路径应跑通且修正收敛。

    DRO 走 two_level（Rust 多重打靶），收敛快、轻量。短弧（~1 个月）进一步
    压低耗时。这条测试是 e2m2e 再变签名时唯一能报出来的真路径守卫。
    """
    kernel_dir = detect_kernel_dir()
    if not kernel_dir:
        pytest.skip("无 SPICE 内核（detect_kernel_dir 返回空）")

    from src.engine.facade_bridge import FacadeBridge

    bridge = FacadeBridge(kernel_dir=kernel_dir)
    # duration 单位为年（GUI 标准单位），facade 内部换算成秒。1/12 年 ≈ 1 个月，
    # 足以验证完整链路（初猜 → 星历修正 → 长期预报）又不过慢。
    data = bridge.design_orbit(orbit_type="DRO", amplitude=60000.0, duration=1.0 / 12.0)

    assert data.orbit_type == "DRO"
    assert data.correction_converged is True
    assert data.ephemeris is not None
    assert len(data.ephemeris["position_km"]) > 1
