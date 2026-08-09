"""tests for FacadeBridge.control_orbit + OrbitDesignResultData.ephemeris (issue #348)。"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from src.engine.facade_bridge import ControlResultData, FacadeBridge

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeEphemeris:
    """Fake EphemerisTable -- 含 design_orbit 提取所需的全部字段。"""

    def __init__(self, n: int = 10) -> None:
        self.year = np.full(n, 2024)
        self.month = np.ones(n, dtype=int)
        self.day = np.ones(n, dtype=int)
        self.hour = np.zeros(n, dtype=int)
        self.minute = np.zeros(n, dtype=int)
        self.second = np.zeros(n, dtype=float)
        self.position_km = np.random.randn(n, 3)
        self.velocity_mps = np.random.randn(n, 3)
        self.synodic_position = np.random.randn(n, 3)

    def __len__(self) -> int:
        return self.year.shape[0]


class _FakeSKStatistic:
    def __init__(self) -> None:
        self.rows = np.array([[1.0, 2.0, 3.0]])


class _FakeManeuverTable:
    def __init__(self) -> None:
        self.mjd_tdb = np.array([60000.0, 60030.0])
        self.delta_v_mps = np.array([0.5, 0.3])


class _FakeControlledEphemeris:
    """Fake controlled_ephemeris -- 支持 len() 并暴露 control_orbit 提取所需全字段。

    control_orbit 现在除 synodic_position 外还要读 position_km（透传 GCRS km）
    和 year/month/day/hour/minute/second（重建 ET 秒）。
    """

    def __init__(
        self,
        synodic_position: np.ndarray,
        position_km: np.ndarray | None = None,
        times: list[tuple] | None = None,
    ) -> None:
        n = synodic_position.shape[0]
        self.synodic_position = synodic_position
        # 默认用 2024-01-01 起步、每行递增 1 整秒，方便测试断言 ET 重建正确。
        if position_km is None:
            position_km = np.random.randn(n, 3)
        self.position_km = position_km
        if times is None:
            times = [(2024, 1, 1, 0, 0, float(k)) for k in range(n)]
        year, month, day, hour, minute, second = zip(*times)
        self.year = np.array(year, dtype=int)
        self.month = np.array(month, dtype=int)
        self.day = np.array(day, dtype=int)
        self.hour = np.array(hour, dtype=int)
        self.minute = np.array(minute, dtype=int)
        self.second = np.array(second, dtype=float)

    def __len__(self) -> int:
        return self.synodic_position.shape[0]


class _FakeControlResult:
    """Fake ControlOrbitResult。"""

    def __init__(
        self,
        synodic_position: np.ndarray | None = None,
        position_km: np.ndarray | None = None,
        times: list[tuple] | None = None,
    ) -> None:
        self.num_failed = 0
        self.sk_statistic = _FakeSKStatistic()
        self.maneuvers = _FakeManeuverTable()
        if synodic_position is not None:
            self.controlled_ephemeris = _FakeControlledEphemeris(
                synodic_position=synodic_position,
                position_km=position_km,
                times=times,
            )
        else:
            self.controlled_ephemeris = None


# ---------------------------------------------------------------------------
# design_orbit ephemeris 提取
# ---------------------------------------------------------------------------


class TestDesignOrbitEphemerisExtraction:
    @pytest.mark.spice
    def test_design_orbit_result_carries_ephemeris_fields(self, monkeypatch):
        """design_orbit 应将 result.ephemeris 提取到 DTO.ephemeris dict。

        P0 起 ephemeris dict 还含 times_et（UTC 拆分用 str2et 重建的 ET 秒），
        故此测试需要闰秒内核 → spice marker。
        """
        n = 10
        orbit = SimpleNamespace(
            states=np.random.randn(n, 6),
            times=np.linspace(0, 1, n),
        )
        correction = SimpleNamespace(converged=True, iterations=1)
        fake_eph = _FakeEphemeris(n)
        result = SimpleNamespace(
            orbit_type="DRO",
            epoch_utc="2024-01-01T00:00:00",
            duration_day=1.0,
            initial_state=np.zeros(6),
            cr3bp_jacobi=3.0,
            cr3bp_orbit=orbit,
            correction=correction,
            ephemeris=fake_eph,
        )

        monkeypatch.setattr(
            "e2m2e.algorithm.design.design_orbit",
            lambda **kw: result,
            raising=False,
        )
        bridge = FacadeBridge()
        data = bridge.design_orbit(orbit_type="DRO")
        assert data.ephemeris is not None
        for key in (
            "year",
            "month",
            "day",
            "hour",
            "minute",
            "second",
            "position_km",
            "velocity_mps",
            "synodic_position",
            "times_et",
        ):
            assert key in data.ephemeris
            assert isinstance(data.ephemeris[key], np.ndarray)
        assert data.ephemeris["times_jd_tdb"] is None

    def test_design_orbit_ephemeris_none_when_absent(self, monkeypatch):
        """result 无 ephemeris 属性时，DTO.ephemeris 为 None。"""
        n = 10
        orbit = SimpleNamespace(
            states=np.random.randn(n, 6),
            times=np.linspace(0, 1, n),
        )
        correction = SimpleNamespace(converged=True, iterations=1)
        result = SimpleNamespace(
            orbit_type="DRO",
            epoch_utc="2024-01-01T00:00:00",
            duration_day=1.0,
            initial_state=np.zeros(6),
            cr3bp_jacobi=3.0,
            cr3bp_orbit=orbit,
            correction=correction,
        )

        monkeypatch.setattr(
            "e2m2e.algorithm.design.design_orbit",
            lambda **kw: result,
            raising=False,
        )
        bridge = FacadeBridge()
        data = bridge.design_orbit(orbit_type="DRO")
        assert data.ephemeris is None


# ---------------------------------------------------------------------------
# control_orbit
# ---------------------------------------------------------------------------


def _make_ephemeris_data(n: int = 10, with_none_tjd: bool = True) -> dict:
    """构造 control_orbit 所需的 ephemeris_data dict。

    times_jd_tdb 当前版本 EphemerisTable 无此字段，始终设 None（与生产提取一致）。
    with_none_tjd 参数保留用于验证 None 值被正确跳过。
    """
    data = {
        "year": np.full(n, 2024),
        "month": np.ones(n, dtype=int),
        "day": np.ones(n, dtype=int),
        "hour": np.zeros(n, dtype=int),
        "minute": np.zeros(n, dtype=int),
        "second": np.zeros(n, dtype=float),
        "position_km": np.random.randn(n, 3),
        "velocity_mps": np.random.randn(n, 3),
        "synodic_position": np.random.randn(n, 3),
        "times_jd_tdb": None if with_none_tjd else np.linspace(60000, 60365, n),
    }
    return data


class TestControlOrbit:
    @pytest.mark.spice
    def test_control_orbit_returns_control_result_dto(self, monkeypatch):
        """control_orbit 应返回 ControlResultData，controlled_states 形状 (n,6)。

        controlled_states[:, :3] 应为质心归一 synodic（= synodic_position − source_mu），
        position_km 等于 fake 的 GCRS km，times_et 等于 SPICE str2et 重建的真物理时间。
        """
        import spiceypy as spice

        from e2m2e.data.kernels.manager import SPICEManager

        # 确保闰秒内核已 furnsh（dev 环境 SPICE_KERNEL_DIR 已设；CI 跳过此测试）。
        SPICEManager()._ensure_leapseconds()

        n = 50
        source_mu = 0.012153645822478
        synodic = np.random.randn(n, 3)
        position_km = np.random.randn(n, 3)
        times_meta = [(2024, 1, 1, 0, 0, float(k)) for k in range(n)]
        fake_result = _FakeControlResult(
            synodic_position=synodic,
            position_km=position_km,
            times=times_meta,
        )

        monkeypatch.setattr(
            "e2m2e.algorithm.station_keeping.control_orbit",
            lambda eph, **kw: fake_result,
            raising=False,
        )
        bridge = FacadeBridge()
        data = bridge.control_orbit(
            ephemeris_data=_make_ephemeris_data(n),
            source_mu=source_mu,
            control_mode=1,
            num_monte_carlo=2,
        )
        assert isinstance(data, ControlResultData)
        assert data.num_failed == 0
        assert data.controlled_states is not None
        assert data.controlled_states.shape == (n, 6)
        # 质心归一：synodic − source_mu（地心归一 → 质心归一，月球在 1−μ）
        np.testing.assert_array_equal(
            data.controlled_states[:, :3], synodic - source_mu
        )
        # 速度列补零
        np.testing.assert_array_equal(data.controlled_states[:, 3:], np.zeros((n, 3)))
        assert data.controlled_times is not None
        assert len(data.controlled_times) == n
        assert data.mu == pytest.approx(source_mu)

        # position_km 直接透传
        assert data.position_km is not None
        np.testing.assert_array_equal(data.position_km, position_km)

        # times_et 由 UTC 拆分用 str2et 重建，应与逐点独立 str2et 一致
        assert data.times_et is not None
        expected_et = np.array(
            [
                spice.str2et(
                    f"{y:04d}-{mo:02d}-{d:02d}T{h:02d}:{mi:02d}:{s:06.3f}"
                )
                for (y, mo, d, h, mi, s) in times_meta
            ]
        )
        np.testing.assert_allclose(data.times_et, expected_et)
        # controlled_times 现在就是真物理时间（不再是 np.arange）
        np.testing.assert_array_equal(data.controlled_times, data.times_et)

    def test_control_orbit_none_states_when_no_ephemeris(self, monkeypatch):
        """所有样本失败（controlled_ephemeris=None）时，controlled_states/times 为 None。"""
        fake_result = _FakeControlResult(synodic_position=None)

        monkeypatch.setattr(
            "e2m2e.algorithm.station_keeping.control_orbit",
            lambda eph, **kw: fake_result,
            raising=False,
        )
        bridge = FacadeBridge()
        data = bridge.control_orbit(
            ephemeris_data=_make_ephemeris_data(10),
            source_mu=None,
            control_mode=1,
        )
        assert data.controlled_states is None
        assert data.controlled_times is None
        assert data.position_km is None
        assert data.times_et is None
        assert data.mu is None

    def test_control_orbit_translates_exceptions(self, monkeypatch):
        """算法层抛 ValueError 应翻译为 OrbitError(INVALID_PARAMS)。"""
        from src.engine.exceptions import OrbitError

        def _fail(eph, **kw):
            raise ValueError("bad params")

        monkeypatch.setattr(
            "e2m2e.algorithm.station_keeping.control_orbit",
            _fail,
            raising=False,
        )
        bridge = FacadeBridge()
        with pytest.raises(OrbitError) as exc_info:
            bridge.control_orbit(
                ephemeris_data=_make_ephemeris_data(10),
                source_mu=None,
            )
        assert exc_info.value.code == "INVALID_PARAMS"

    @pytest.mark.spice
    def test_ephemeris_table_reconstruction_skips_none_times(self, monkeypatch):
        """times_jd_tdb=None 时 EphemerisTable 重建不崩（走 dataclass 默认）。

        P0 起 control_orbit 会重建 times_et（spice.str2et），需闰秒内核 → spice marker。
        """
        fake_result = _FakeControlResult(synodic_position=np.random.randn(5, 3))

        captured: dict = {}

        def _capture(eph, **kw):
            captured["eph"] = eph
            return fake_result

        monkeypatch.setattr(
            "e2m2e.algorithm.station_keeping.control_orbit",
            _capture,
            raising=False,
        )
        bridge = FacadeBridge()
        bridge.control_orbit(
            ephemeris_data=_make_ephemeris_data(5, with_none_tjd=True),
            source_mu=None,
        )
        # EphemerisTable 成功构造（算法层被调用即证明）
        assert "eph" in captured
        assert captured["eph"].synodic_position is not None

    @pytest.mark.spice
    def test_control_orbit_kernel_dir_forwarded(self, monkeypatch):
        """kernel_dir 应注入到算法层调用。

        P0 起 control_orbit 会重建 times_et（spice.str2et），需闰秒内核 → spice marker。
        """
        captured: dict = {}
        fake_result = _FakeControlResult(synodic_position=np.random.randn(5, 3))

        def _capture(eph, **kw):
            captured.update(kw)
            return fake_result

        monkeypatch.setattr(
            "e2m2e.algorithm.station_keeping.control_orbit",
            _capture,
            raising=False,
        )
        bridge = FacadeBridge(kernel_dir="/tmp/kernels")
        bridge.control_orbit(
            ephemeris_data=_make_ephemeris_data(5),
            source_mu=None,
        )
        assert captured.get("kernel_dir") == "/tmp/kernels"
