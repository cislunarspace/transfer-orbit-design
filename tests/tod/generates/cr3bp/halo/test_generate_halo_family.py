"""Tests for HaloFamilyGenerator hook decomposition (PRD #163).

验证 Halo 族生成器通过基类 hook 方法实现族特有逻辑，
不再覆盖 run()。
"""

# pyright: reportOptionalMemberAccess=false

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from tod.generates.cr3bp._family_pipeline import FamilyGeneratorConfig
from tod.generates.cr3bp.halo.generate_halo_family import (
    LIBRATION_POINT_MAP,
    HaloFamilyGenerator,
)


# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------


def _make_halo_gen() -> HaloFamilyGenerator:
    """构造一个 HaloFamilyGenerator 实例（不含运行时状态）。"""
    config = FamilyGeneratorConfig(
        family_type="halo",
        output_subdir="halo",
    )
    return HaloFamilyGenerator(config)


def _make_halo_args(**overrides) -> MagicMock:
    """构造模拟 Halo CLI args。"""
    args = MagicMock()
    args.libration_point = overrides.get("libration_point", "L1")
    args.halo_class = overrides.get("halo_class", 0)
    args.amplitude_z = overrides.get("amplitude_z", 0.001)
    args.n_orbits = overrides.get("n_orbits", 20)
    args.step_size = overrides.get("step_size", 0.002)
    args.step_size_pal = overrides.get("step_size_pal", None)
    args.step_size_negative = overrides.get("step_size_negative", None)
    args.method = overrides.get("method", "pseudo_arclength")
    args.direction = overrides.get("direction", "both")
    args.seed_file = overrides.get("seed_file", None)
    args.z_min = overrides.get("z_min", None)
    args.z_max = overrides.get("z_max", None)
    args.verbose = overrides.get("verbose", False)
    args.output_dir = overrides.get("output_dir", None)
    args.log_level = overrides.get("log_level", "WARNING")
    args.n_milestones = overrides.get("n_milestones", 5)
    return args


# ---------------------------------------------------------------------------
# 1. _build_json_filename — 从 args 提取参数
# ---------------------------------------------------------------------------


class TestBuildJsonFilename:
    """验证 _build_json_filename 从 args 提取参数，不依赖 self._lp/self._hc。"""

    def test_l1_north_halo(self):
        gen = _make_halo_gen()
        args = _make_halo_args(libration_point="L1", halo_class=0, amplitude_z=0.001)
        result = gen._build_json_filename(args, ts=1234567890)
        assert result == "halo_L1_N_family_0.001_1234567890"

    def test_l2_south_halo(self):
        gen = _make_halo_gen()
        args = _make_halo_args(libration_point="L2", halo_class=1, amplitude_z=0.23)
        result = gen._build_json_filename(args, ts=9999)
        assert result == "halo_L2_S_family_0.23_9999"

    def test_l3_north_halo(self):
        gen = _make_halo_gen()
        args = _make_halo_args(libration_point="L3", halo_class=0, amplitude_z=0.05)
        result = gen._build_json_filename(args, ts=0)
        assert result == "halo_L3_N_family_0.05_0"

    def test_no_temporal_coupling(self):
        """不应依赖 self._lp / self._hc 实例变量。"""
        gen = _make_halo_gen()
        # 故意不设置 self._lp / self._hc
        assert not hasattr(gen, "_lp") or getattr(gen, "_lp", None) is None
        args = _make_halo_args(libration_point="L1", halo_class=0, amplitude_z=0.001)
        result = gen._build_json_filename(args, ts=100)
        assert "L1" in result
        assert "_N_" in result


# ---------------------------------------------------------------------------
# 2. _build_csv_filename_parts — 从 args 提取参数
# ---------------------------------------------------------------------------


class TestBuildCsvFilenameParts:
    """验证 _build_csv_filename_parts 从 args 提取参数，不依赖 self._lp/self._hc。"""

    def test_l1_north(self):
        gen = _make_halo_gen()
        args = _make_halo_args(libration_point="L1", halo_class=0)
        result = gen._build_csv_filename_parts(args, ts=1234)
        assert result == ["halo_L1_N_family", "1234"]

    def test_l2_south(self):
        gen = _make_halo_gen()
        args = _make_halo_args(libration_point="L2", halo_class=1)
        result = gen._build_csv_filename_parts(args, ts=9999)
        assert result == ["halo_L2_S_family", "9999"]

    def test_no_temporal_coupling(self):
        gen = _make_halo_gen()
        assert not hasattr(gen, "_lp") or getattr(gen, "_lp", None) is None
        args = _make_halo_args(libration_point="L3", halo_class=0)
        result = gen._build_csv_filename_parts(args, ts=0)
        assert "L3" in result[0]
        assert "N" in result[0]


# ---------------------------------------------------------------------------
# 3. _setup_corrector — z0 符号和平动点配置
# ---------------------------------------------------------------------------


class TestSetupCorrector:
    """验证 _setup_corrector 创建 corrector 并配置正确的 z0 符号。"""

    def test_north_halo_positive_z0(self):
        """北族（halo_class=0）应传入正 z0。"""
        gen = _make_halo_gen()
        args = _make_halo_args(libration_point="L1", halo_class=0, amplitude_z=0.23)

        with patch("tod.generates.cr3bp.halo.generate_halo_family.e2m2e.algorithms.DifferentialCorrection") as MockDC:
            mock_corrector = MagicMock()
            MockDC.return_value = mock_corrector

            result = gen._setup_corrector(args)

            MockDC.assert_called_once()
            mock_corrector.setup_halo_orbit_fixed_z0.assert_called_once_with(
                z0=0.23, libration_point=1,
            )
            assert result is mock_corrector

    def test_south_halo_negative_z0(self):
        """南族（halo_class=1）应传入负 z0。"""
        gen = _make_halo_gen()
        args = _make_halo_args(libration_point="L2", halo_class=1, amplitude_z=0.15)

        with patch("tod.generates.cr3bp.halo.generate_halo_family.e2m2e.algorithms.DifferentialCorrection") as MockDC:
            mock_corrector = MagicMock()
            MockDC.return_value = mock_corrector

            result = gen._setup_corrector(args)

            mock_corrector.setup_halo_orbit_fixed_z0.assert_called_once_with(
                z0=-0.15, libration_point=2,
            )


# ---------------------------------------------------------------------------
# 4. _correct_seed_orbit — 修正 + 参数回填
# ---------------------------------------------------------------------------


class TestCorrectSeedOrbit:
    """验证 _correct_seed_orbit 调用 correction 后回填 Halo 参数。"""

    def test_backfills_halo_metadata(self):
        """修正成功后应回填 family_type、libration_point、halo_class、amplitude_z。"""
        gen = _make_halo_gen()
        args = _make_halo_args(libration_point="L1", halo_class=0, amplitude_z=0.23)

        # 模拟 corrector 返回修正后的轨道
        mock_corrector = MagicMock()
        corrected = MagicMock()
        corrected.states = np.array([[0.93, 0.0, 0.23, 0.0, 0.1, 0.0]])
        corrected.period = 3.68
        corrected.parameters = {}
        mock_corrector.iterate_correction.return_value = corrected

        result = gen._correct_seed_orbit(mock_corrector, MagicMock(), args)

        assert result is corrected
        assert result.family_type == "halo"
        assert result.parameters["libration_point"] == 1
        assert result.parameters["halo_class"] == 0
        assert result.parameters["amplitude_z"] == pytest.approx(0.23)

    def test_returns_none_on_correction_failure(self):
        """修正失败时应返回 None，由基类 run() 处理报错。"""
        gen = _make_halo_gen()
        args = _make_halo_args()

        mock_corrector = MagicMock()
        mock_corrector.iterate_correction.return_value = None

        result = gen._correct_seed_orbit(mock_corrector, MagicMock(), args)
        assert result is None

    def test_south_halo_negative_z0_amplitude(self):
        """南族修正后 amplitude_z 应取绝对值（z0 为负）。"""
        gen = _make_halo_gen()
        args = _make_halo_args(libration_point="L1", halo_class=1, amplitude_z=0.15)

        mock_corrector = MagicMock()
        corrected = MagicMock()
        corrected.states = np.array([[0.93, 0.0, -0.15, 0.0, 0.1, 0.0]])
        corrected.period = 3.68
        corrected.parameters = {}
        mock_corrector.iterate_correction.return_value = corrected

        result = gen._correct_seed_orbit(mock_corrector, MagicMock(), args)

        assert result.parameters["halo_class"] == 1
        assert result.parameters["amplitude_z"] == pytest.approx(0.15)


# ---------------------------------------------------------------------------
# 5. _get_seed_orbit — 自动生成路径（Richardson → fallback）
# ---------------------------------------------------------------------------


class TestGetSeedOrbitAutoGeneration:
    """验证 _get_seed_orbit 自动生成路径：Richardson 先试 → hardcoded fallback。"""

    def test_richardson_success(self):
        """Richardson 近似成功时直接返回种子。"""
        gen = _make_halo_gen()
        gen.init_system()
        args = _make_halo_args(seed_file=None, libration_point="L1", halo_class=0, amplitude_z=0.001)

        mock_seed = MagicMock()
        mock_seed.states = np.array([[0.93, 0.0, 0.001, 0.0, 0.1, 0.0]])
        mock_seed.period = 3.68

        with patch("tod.generates.cr3bp.halo.generate_halo_family.e2m2e.algorithms.Continuation") as MockCont:
            mock_continuation = MagicMock()
            mock_continuation.generate_halo_seed_orbit.return_value = mock_seed
            MockCont.return_value = mock_continuation

            result = gen._get_seed_orbit(args)

        assert result is mock_seed
        assert result.family_type == "halo"
        assert result.parameters["libration_point"] == 1
        assert result.parameters["halo_class"] == 0

    def test_richardson_failure_triggers_fallback(self):
        """Richardson 失败时应尝试 fallback 种子。"""
        gen = _make_halo_gen()
        gen.init_system()
        args = _make_halo_args(
            seed_file=None,
            libration_point="L1",
            halo_class=0,
            amplitude_z=0.23,
        )

        mock_fallback = MagicMock()
        mock_fallback.states = np.array([[0.93, 0.0, 0.23, 0.0, 0.1, 0.0]])
        mock_fallback.period = 3.68
        mock_fallback.correction_success = True

        with patch("tod.generates.cr3bp.halo.generate_halo_family.e2m2e.algorithms.Continuation") as MockCont, \
             patch("tod.generates.cr3bp.halo.generate_halo_family.e2m2e.algorithms.DifferentialCorrection") as MockDC:
            mock_continuation = MagicMock()
            mock_continuation.generate_halo_seed_orbit.return_value = None  # Richardson 失败
            MockCont.return_value = mock_continuation

            mock_corrector = MagicMock()
            mock_corrector.iterate_correction.return_value = mock_fallback
            MockDC.return_value = mock_corrector

            result = gen._get_seed_orbit(args)

        assert result is mock_fallback

    def test_all_generation_failure_raises(self):
        """Richardson 和 fallback 都失败时应抛出 RuntimeError。"""
        gen = _make_halo_gen()
        gen.init_system()
        args = _make_halo_args(
            seed_file=None,
            libration_point="L1",
            halo_class=1,
            amplitude_z=0.001,
        )

        with patch("tod.generates.cr3bp.halo.generate_halo_family.e2m2e.algorithms.Continuation") as MockCont:
            mock_continuation = MagicMock()
            mock_continuation.generate_halo_seed_orbit.return_value = None
            MockCont.return_value = mock_continuation

            with pytest.raises(RuntimeError, match="种子轨道生成失败"):
                gen._get_seed_orbit(args)


# ---------------------------------------------------------------------------
# 6. _get_seed_orbit — seed-file 路径
# ---------------------------------------------------------------------------


class TestGetSeedOrbitSeedFile:
    """验证 _get_seed_orbit 从 JSON 文件加载种子。"""

    def test_loads_from_seed_file(self, tmp_path):
        """--seed-file 指定时从 JSON 加载种子并打标签。"""
        gen = _make_halo_gen()
        gen.init_system()

        # 创建模拟种子文件
        seed_file = tmp_path / "seed.json"
        seed_file.write_text('{"states": [[0.93, 0.0, 0.23, 0.0, 0.1, 0.0]], "times": [0.0]}')

        args = _make_halo_args(seed_file=str(seed_file), libration_point="L1", halo_class=0)

        with patch("tod.generates.cr3bp.halo.generate_halo_family._load_seed_orbit") as mock_load:
            mock_orbit = MagicMock()
            mock_orbit.states = np.array([[0.93, 0.0, 0.23, 0.0, 0.1, 0.0]])
            mock_orbit.period = 3.68
            mock_orbit.parameters = {}
            mock_load.return_value = mock_orbit

            result = gen._get_seed_orbit(args)

        assert result is mock_orbit
        assert result.family_type == "halo"
        assert result.parameters["libration_point"] == 1
        assert result.parameters["halo_class"] == 0


# ---------------------------------------------------------------------------
# 7. _run_continuation — z_range 验证
# ---------------------------------------------------------------------------


class TestRunContinuationZRange:
    """验证 _run_continuation 中 z_range 验证行为。"""

    def test_z_range_passes_when_seed_in_range(self):
        """种子 z0 在 z_range 范围内时应正常执行。"""
        gen = _make_halo_gen()
        args = _make_halo_args(halo_class=0, z_min=0.1, z_max=0.5)

        mock_seed = MagicMock()
        mock_seed.states = np.array([[0.93, 0.0, 0.23, 0.0, 0.1, 0.0]])

        with patch("tod.generates.cr3bp.halo.generate_halo_family.e2m2e.algorithms.Continuation") as MockCont:
            mock_family = MagicMock()
            mock_cont_instance = MagicMock()
            mock_cont_instance.halo_pseudo_arclength_continuation.return_value = mock_family
            MockCont.return_value = mock_cont_instance

            result = gen._run_continuation(MagicMock(), mock_seed, args)

        assert result is mock_family

    def test_z_range_raises_when_seed_out_of_range(self):
        """种子 z0 不在 z_range 范围内时应抛出 ValueError。"""
        gen = _make_halo_gen()
        args = _make_halo_args(halo_class=0, z_min=0.5, z_max=1.0)

        mock_seed = MagicMock()
        mock_seed.states = np.array([[0.93, 0.0, 0.1, 0.0, 0.1, 0.0]])  # z0=0.1 < z_min

        with pytest.raises(ValueError, match="z_range"):
            gen._run_continuation(MagicMock(), mock_seed, args)

    def test_z_range_south_halo_negative_z0(self):
        """南族 z_range 应取负值范围。"""
        gen = _make_halo_gen()
        args = _make_halo_args(halo_class=1, z_min=0.1, z_max=0.5)

        mock_seed = MagicMock()
        mock_seed.states = np.array([[0.93, 0.0, -0.23, 0.0, 0.1, 0.0]])  # z0=-0.23 ∈ [-0.5, -0.1]

        with patch("tod.generates.cr3bp.halo.generate_halo_family.e2m2e.algorithms.Continuation") as MockCont:
            mock_family = MagicMock()
            mock_cont_instance = MagicMock()
            mock_cont_instance.halo_pseudo_arclength_continuation.return_value = mock_family
            MockCont.return_value = mock_cont_instance

            result = gen._run_continuation(MagicMock(), mock_seed, args)
        assert result is mock_family

    def test_no_z_range_skips_validation(self):
        """不提供 z_min/z_max 时跳过验证。"""
        gen = _make_halo_gen()
        args = _make_halo_args(z_min=None, z_max=None)

        mock_seed = MagicMock()
        mock_seed.states = np.array([[0.93, 0.0, 0.23, 0.0, 0.1, 0.0]])

        with patch("tod.generates.cr3bp.halo.generate_halo_family.e2m2e.algorithms.Continuation") as MockCont:
            mock_family = MagicMock()
            mock_cont_instance = MagicMock()
            mock_cont_instance.halo_pseudo_arclength_continuation.return_value = mock_family
            MockCont.return_value = mock_cont_instance

            result = gen._run_continuation(MagicMock(), mock_seed, args)
        assert result is mock_family

    # ---------------------------------------------------------------------------
    # 8. _run_continuation — 延拓方法路由
    # ---------------------------------------------------------------------------

    def test_run_continuation_raises_on_unknown_method(self):
        """未知延拓方法应抛出 ValueError。"""
        gen = _make_halo_gen()
        args = _make_halo_args(method="unknown_method")

        mock_seed = MagicMock()
        mock_seed.states = np.array([[0.93, 0.0, 0.23, 0.0, 0.1, 0.0]])

        with pytest.raises(ValueError, match="未实现的延拓方法"):
            gen._run_continuation(MagicMock(), mock_seed, args)

    def test_run_continuation_pal_calls_pal_api(self):
        """method=pseudo_arclength 时应调用 halo_pseudo_arclength_continuation。"""
        gen = _make_halo_gen()
        args = _make_halo_args(method="pseudo_arclength")

        mock_seed = MagicMock()
        mock_seed.states = np.array([[0.93, 0.0, 0.23, 0.0, 0.1, 0.0]])

        with patch("tod.generates.cr3bp.halo.generate_halo_family.e2m2e.algorithms.Continuation") as MockCont:
            mock_family = MagicMock()
            mock_cont_instance = MagicMock()
            mock_cont_instance.halo_pseudo_arclength_continuation.return_value = mock_family
            MockCont.return_value = mock_cont_instance

            result = gen._run_continuation(MagicMock(), mock_seed, args)

        assert result is mock_family
        mock_cont_instance.halo_pseudo_arclength_continuation.assert_called_once()
