"""
Tests for tod/commons/io.py module

Tests the constants and helper functions used across multiple scripts.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import os
import tempfile
import json

from tod.commons.common import (
    MU,
    TU,
    DU,
    VU,
    T_MOON,
    FAMILY_FILENAME,
    ensure_output_dir,
    get_latest_family_file,
    load_or_compute,
    save_family_to_file,
)


class TestConstants:
    """Test physical and astronomical constants"""

    def test_mu_is_positive(self):
        """MU should be positive (Earth-Moon mass ratio)"""
        assert MU > 0
        assert MU < 1  # Moon is much smaller than Earth

    def test_tu_is_positive(self):
        """TU (time unit in days) should be positive"""
        assert TU > 0

    def test_du_is_positive(self):
        """DU (distance unit in km) should be positive"""
        assert DU > 0

    def test_vu_is_positive(self):
        """VU (velocity unit in m/s) should be positive"""
        assert VU > 0

    def test_t_moon_equals_2pi(self):
        """Moon orbital period in nondimensional units should be 2π"""
        import math

        assert math.isclose(T_MOON, 2 * math.pi, rel_tol=1e-10)

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
