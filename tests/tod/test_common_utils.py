"""
tod/commons/io.py 模块的测试

测试多个脚本共用的常量和辅助函数。
"""

import math

import pytest
from pathlib import Path
from unittest.mock import MagicMock
import os
import tempfile

from tod.commons.constants import MU, TU, DU, VU, T_MOON, FAMILY_FILENAME
from tod.commons.constants import M_SUN, OMEGA_SUN, RHO
from tod.commons.common import ensure_output_dir, find_project_root, get_latest_family_file, safe_resolve_within, save_family_to_file


class TestConstants:
    """测试物理和天文常数"""

    def test_mu_is_positive(self):
        """MU 应为正（地月质量比）"""
        assert MU > 0
        assert MU < 1  # 月球远小于地球

    def test_tu_is_positive(self):
        """TU（时间单位，天）应为正"""
        assert TU > 0

    def test_du_is_positive(self):
        """DU（距离单位，km）应为正"""
        assert DU > 0

    def test_vu_is_positive(self):
        """VU (velocity unit in m/s) should be positive"""
        assert VU > 0

    def test_t_moon_equals_2pi(self):
        """Moon orbital period in nondimensional units should be 2π"""
        assert math.isclose(T_MOON, 2 * math.pi, rel_tol=1e-10)

    def test_m_sun_is_positive(self):
        """M_SUN (nondimensional sun mass) should be positive"""
        assert M_SUN > 0

    def test_omega_sun_is_positive(self):
        """OMEGA_SUN (nondimensional angular velocity) should be positive"""
        assert OMEGA_SUN > 0
        assert OMEGA_SUN < 1  # Should be less than 1 rotation per time unit

    def test_rho_is_positive(self):
        """RHO (nondimensional sun-Earth-moon distance) should be positive"""
        assert RHO > 0
        assert RHO > 1  # Sun is much farther than 1 DU

    def test_vu_consistency_with_du_tu(self):
        """VU should be consistent with DU and TU (VU = DU/TU in appropriate units)"""
        expected_vu = DU * 1000 / (TU * 86400)
        assert math.isclose(VU, expected_vu, rel_tol=0.01)

    def test_family_filename_default(self):
        """FAMILY_FILENAME should be a string"""
        assert isinstance(FAMILY_FILENAME, str)
        assert FAMILY_FILENAME == "family.json"


class TestEnsureOutputDir:
    """Test ensure_output_dir function"""

    def test_creates_directory(self, tmp_path):
        """Should create output directory if it doesn't exist"""
        test_dir = tmp_path / "output" / "subdir"
        ensure_output_dir(str(test_dir))
        assert test_dir.exists()

    def test_does_not_fail_if_exists(self, tmp_path):
        """Should not fail if directory already exists"""
        test_dir = tmp_path / "existing"
        test_dir.mkdir()
        ensure_output_dir(str(test_dir))  # Should not raise

    def test_returns_none(self):
        """Should return None (implicitly)"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = ensure_output_dir(tmpdir)
            assert result is None


class TestGetLatestFamilyFile:
    """Test get_latest_family_file function"""

    def test_returns_none_if_dir_not_exists(self):
        """Should return None if output_dir doesn't exist"""
        result = get_latest_family_file("/nonexistent/path")
        assert result is None

    def test_returns_none_if_no_files(self, tmp_path):
        """Should return None if directory is empty"""
        result = get_latest_family_file(str(tmp_path))
        assert result is None

    def test_returns_family_file_if_exists(self, tmp_path):
        """Should return path to family.json if it exists"""
        # Create family.json in tmp_path
        family_file = tmp_path / FAMILY_FILENAME
        family_file.write_text("{}")

        result = get_latest_family_file(str(tmp_path))
        assert result == str(family_file)

    def test_returns_latest_dir_family(self, tmp_path):
        """Should search in latest timestamped subdirectory"""
        import time
        import os

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        old_dir = output_dir / "20240101_100000"
        new_dir = output_dir / "20240102_110000"
        old_dir.mkdir()
        new_dir.mkdir()
        (old_dir / FAMILY_FILENAME).write_text('{"old": true}')
        (new_dir / FAMILY_FILENAME).write_text('{"new": true}')
        time.sleep(0.1)
        new_mtime = os.path.getmtime(str(new_dir)) + 1
        os.utime(str(new_dir), (new_mtime, new_mtime))
        result = get_latest_family_file(str(output_dir))
        assert result == str(new_dir / FAMILY_FILENAME)


class TestSaveFamilyToFile:
    """Test save_family_to_file function"""

    def test_creates_timestamped_dir(self, tmp_path):
        """Should create a timestamped subdirectory"""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Create a mock that writes file at the exact path passed
        mock_family = MagicMock()

        def mock_save(filepath):
            # filepath is like tmp/output/timestamp/family.json
            p = Path(filepath)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("{}")

        mock_family.save_to_file = mock_save

        result_dir = save_family_to_file(mock_family, str(output_dir))

        # Check that timestamped directory was created
        assert Path(result_dir).exists()
        # Check that family.json exists inside it
        assert (Path(result_dir) / FAMILY_FILENAME).exists()

    def test_copies_to_latest(self, tmp_path):
        """Should copy saved file to latest path"""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Create a mock that writes file at the exact path passed
        mock_family = MagicMock()

        def mock_save(filepath):
            p = Path(filepath)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("{}")

        mock_family.save_to_file = mock_save

        save_family_to_file(mock_family, str(output_dir))

        latest_path = output_dir / FAMILY_FILENAME
        assert latest_path.exists()


class TestFindProjectRoot:
    """Test find_project_root function"""

    def test_from_project_root_directory(self):
        """Should find project root when starting from a file at the root level"""
        project_root = Path(__file__).resolve().parents[2]
        # find_project_root calls .parent on start, so pass a file at root level
        result = find_project_root(project_root / "pyproject.toml")
        assert result == project_root
        assert (result / "pyproject.toml").exists()

    def test_from_deep_nested_path(self):
        """Should find project root from a deeply nested path"""
        project_root = Path(__file__).resolve().parents[2]
        deep_path = project_root / "tod" / "plot" / "transfer" / "dro_to_ro"
        result = find_project_root(deep_path)
        assert result == project_root

    def test_from_source_file(self):
        """Should find project root from the common.py source file"""
        project_root = Path(__file__).resolve().parents[2]
        source_file = project_root / "tod" / "commons" / "common.py"
        result = find_project_root(source_file)
        assert result == project_root

    def test_raises_when_no_root_found(self, tmp_path):
        """Should raise FileNotFoundError when no root marker exists"""
        nested = tmp_path / "a" / "b" / "c"
        nested.mkdir(parents=True)
        with pytest.raises(FileNotFoundError):
            find_project_root(nested)


class TestSafeResolveWithin:
    """Test safe_resolve_within function"""

    def test_path_within_allowed_root(self, tmp_path):
        """Should return resolved path when it is within allowed root"""
        allowed = tmp_path / "project"
        allowed.mkdir()
        target = allowed / "src" / "main.py"
        target.parent.mkdir(parents=True)
        target.touch()

        result = safe_resolve_within(str(target), allowed)
        assert result is not None
        assert result == target.resolve()

    def test_path_outside_allowed_root(self, tmp_path):
        """Should return None when path is outside allowed root"""
        allowed = tmp_path / "project"
        allowed.mkdir()
        outside = tmp_path / "other" / "secret.txt"
        outside.parent.mkdir(parents=True)
        outside.touch()

        result = safe_resolve_within(str(outside), allowed)
        assert result is None

    def test_traversal_attack_blocked(self, tmp_path):
        """Should block path traversal attempts using ../"""
        allowed = tmp_path / "sandbox"
        allowed.mkdir()

        result = safe_resolve_within("../../../etc/passwd", allowed)
        assert result is None

    def test_relative_path_within_root(self, tmp_path):
        """Should resolve a relative path that stays within root"""
        allowed = tmp_path / "project"
        sub = allowed / "data"
        sub.mkdir(parents=True)

        original_cwd = Path.cwd()
        try:
            os.chdir(str(allowed))
            result = safe_resolve_within("data", allowed)
            assert result is not None
            assert result == sub.resolve()
        finally:
            os.chdir(str(original_cwd))
