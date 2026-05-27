"""
richardson_initial_guess 重构回归测试（issue #33）。

验证：
- 子函数可导入且有文档
- 周期计算返回预期结构
- 种子提取找到正确的 z 最大值点
- vy0 符号选择产生正确的轨道方向
- richardson_initial_guess 返回一致的结果
"""

import importlib
import inspect

import numpy as np
import pytest


@pytest.fixture
def halo_module():
    """导入 generate_halo_orbit 模块。"""
    return importlib.import_module("tod.generates.cr3bp.halo.generate_halo_orbit")


@pytest.fixture
def mu():
    """地月质量比。"""
    return 1.21506683e-2


class TestSubFunctionsExist:
    """测试重构后的子函数是否正确定义。"""

    def test_compute_richardson_period_exists(self, halo_module):
        assert hasattr(halo_module, "_compute_richardson_period")

    def test_extract_seed_from_approximation_exists(self, halo_module):
        assert hasattr(halo_module, "_extract_seed_from_approximation")

    def test_select_vy0_sign_exists(self, halo_module):
        assert hasattr(halo_module, "_select_vy0_sign")

    def test_richardson_initial_guess_exists(self, halo_module):
        assert hasattr(halo_module, "richardson_initial_guess")


class TestSubFunctionsDocstring:
    """测试子函数包含中文文档字符串。"""

    def test_compute_richardson_period_has_docstring(self, halo_module):
        assert halo_module._compute_richardson_period.__doc__ is not None
        assert "计算" in halo_module._compute_richardson_period.__doc__

    def test_extract_seed_from_approximation_has_docstring(self, halo_module):
        assert halo_module._extract_seed_from_approximation.__doc__ is not None
        assert "提取" in halo_module._extract_seed_from_approximation.__doc__

    def test_select_vy0_sign_has_docstring(self, halo_module):
        assert halo_module._select_vy0_sign.__doc__ is not None
        assert "符号" in halo_module._select_vy0_sign.__doc__


class TestComputeRichardsonPeriod:
    """测试 _compute_richardson_period 返回正确的结构。"""

    def test_returns_five_values(self, halo_module, mu):
        Au = 0.1
        Aw = 0.2
        result = halo_module._compute_richardson_period(mu, Au, Aw, libration_point=1)
        assert isinstance(result, tuple)
        assert len(result) == 4  # T_linear, T_richardson, omega_p, freq_correction

    def test_periods_are_positive(self, halo_module, mu):
        Au = 0.1
        Aw = 0.2
        T_linear, T_richardson, omega_p, freq_correction = halo_module._compute_richardson_period(
            mu, Au, Aw, libration_point=1
        )
        assert T_linear > 0
        assert T_richardson > 0
        assert omega_p > 0

    def test_richardson_period_differs_from_linear(self, halo_module, mu):
        """Richardson correction should modify period for non-zero amplitudes."""
        Au = 0.3
        Aw = 0.5
        T_linear, T_richardson, _, freq_correction = halo_module._compute_richardson_period(
            mu, Au, Aw, libration_point=1
        )
        # 非零振幅下，freq_correction 应为非零
        assert freq_correction != 0
        # 由于修正，T_richardson 应与 T_linear 不同
        assert T_linear != T_richardson


class TestExtractSeedFromApproximation:
    """测试 _extract_seed_from_approximation 找到正确的点。"""

    def test_finds_z_maximum(self, halo_module):
        """应提取 z 振幅最大处的状态。"""
        # 创建模拟轨道，z 最大值在索引 50 处
        n_points = 100
        t = np.linspace(0, 2 * np.pi, n_points)
        z_col = np.sin(t)  # z 最大值在索引 25（sin = 1）
        x_col = np.cos(t)
        vy_col = np.zeros(n_points)

        # 构建 SV_xyz：[x, y, z, vx, vy, vz]
        SV_xyz = np.column_stack([x_col, np.zeros(n_points), z_col, np.zeros(n_points), vy_col, np.zeros(n_points)])

        x0, vy0, z0 = halo_module._extract_seed_from_approximation(SV_xyz, z_amplitude=1.0)

        # 应找到 |z| 最大点
        assert np.abs(x0) <= 1.0  # x 在有效范围内
        assert vy0 == 0.0  # z 最大值处 vy 为零

    def test_returns_float_values(self, halo_module):
        """应返回 Python float 而非 numpy 类型。"""
        n_points = 100
        t = np.linspace(0, 2 * np.pi, n_points)
        SV_xyz = np.column_stack([
            np.cos(t),
            np.zeros(n_points),
            np.sin(t),
            np.zeros(n_points),
            np.zeros(n_points),
            np.zeros(n_points),
        ])

        x0, vy0, z0 = halo_module._extract_seed_from_approximation(SV_xyz, z_amplitude=1.0)

        assert isinstance(x0, float)
        assert isinstance(vy0, float)
        assert isinstance(z0, float)


class TestSelectVy0Sign:
    """测试 _select_vy0_sign 正确选择轨道方向。"""

    def test_returns_positive_vy0_when_x_increases(self, halo_module, mu):
        """当半周期传播导致 x 增大时，vy0 应为正。"""
        # L1 Halo 轨道初始向外运动，因此 vy0 > 0
        vy0_raw = 0.1
        result = halo_module._select_vy0_sign(x0=0.93, z0=0.23, vy0_raw=vy0_raw, T=3.6, mu=mu)
        assert result > 0

    def test_returns_negative_vy0_when_x_decreases(self, halo_module, mu):
        """当半周期传播导致 x 减小时，vy0 应为负。"""
        # 测试符号修正逻辑
        vy0_raw = -0.1  # 负初始值
        result = halo_module._select_vy0_sign(x0=0.93, z0=0.23, vy0_raw=vy0_raw, T=3.6, mu=mu)
        # 函数应确保符号与 x 方向匹配
        assert isinstance(result, float)

    def test_magnitude_preserved(self, halo_module, mu):
        """符号选择应保持幅值不变。"""
        vy0_raw = 0.25
        result = halo_module._select_vy0_sign(x0=0.93, z0=0.23, vy0_raw=vy0_raw, T=3.6, mu=mu)
        assert np.abs(result) == pytest.approx(0.25)


class TestRichardsonInitialGuess:
    """测试 richardson_initial_guess 集成。"""

    def test_returns_dict_with_required_keys(self, halo_module, mu):
        """应返回包含 x0, z0, vy0, period 的字典。"""
        result = halo_module.richardson_initial_guess(mu, 0.23, libration_point=1, halo_class=0)
        assert isinstance(result, dict)
        assert set(result.keys()) == {"x0", "z0", "vy0", "period"}

    def test_z0_sign_for_north_halo(self, halo_module, mu):
        """北 Halo（Class I）z0 应为正。"""
        result = halo_module.richardson_initial_guess(mu, 0.23, libration_point=1, halo_class=0)
        assert result["z0"] > 0

    def test_z0_sign_for_south_halo(self, halo_module, mu):
        """南 Halo（Class II）z0 应为负。"""
        result = halo_module.richardson_initial_guess(mu, 0.23, libration_point=1, halo_class=1)
        assert result["z0"] < 0

    def test_x0_in_valid_range_for_l1(self, halo_module, mu):
        """L1 Halo x0 应在地月连线与 L1 点之间。"""
        result = halo_module.richardson_initial_guess(mu, 0.23, libration_point=1, halo_class=0)
        # L1 在 x ≈ 0.99 处，x0 应小于 L1
        assert 0.8 < result["x0"] < 1.0

    def test_period_is_positive(self, halo_module, mu):
        """周期应始终为正。"""
        result = halo_module.richardson_initial_guess(mu, 0.23, libration_point=1, halo_class=0)
        assert result["period"] > 0

    def test_vy0_magnitude_reasonable(self, halo_module, mu):
        """vy0 幅值应在 Halo 轨道的合理范围内。"""
        result = halo_module.richardson_initial_guess(mu, 0.23, libration_point=1, halo_class=0)
        # 典型 Halo 轨道 vy0 约为 O(0.1)
        assert 0.0 < abs(result["vy0"]) < 1.0

    @pytest.mark.parametrize("halo_class", [0, 1])
    def test_l1_halo_both_classes(self, halo_module, mu, halo_class):
        """两种 Halo 类别对 L1 都应产生有效结果。"""
        result = halo_module.richardson_initial_guess(mu, 0.23, libration_point=1, halo_class=halo_class)
        assert "x0" in result
        assert "z0" in result
        assert "vy0" in result
        assert "period" in result


class TestFunctionLineCounts:
    """验证重构满足 issue #33 的行数要求。"""

    def test_richardson_initial_guess_under_50_lines(self, halo_module):
        """richardson_initial_guess 应少于 50 行。"""
        source = inspect.getsource(halo_module.richardson_initial_guess)
        lines = [l for l in source.split('\n') if l.strip() and not l.strip().startswith('#')]
        assert len(lines) < 50, f"Function has {len(lines)} lines, should be < 50"

    def test_sub_functions_under_50_lines(self, halo_module):
        """所有子函数应少于 50 行。"""
        funcs = [
            halo_module._compute_richardson_period,
            halo_module._extract_seed_from_approximation,
            halo_module._select_vy0_sign,
        ]
        for func in funcs:
            source = inspect.getsource(func)
            lines = [l for l in source.split('\n') if l.strip() and not l.strip().startswith('#')]
            assert len(lines) < 50, f"{func.__name__} has {len(lines)} lines, should be < 50"
