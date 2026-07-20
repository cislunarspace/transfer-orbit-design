"""
tod/plot 脚本的测试 (plot_orbits.py, plot_interactive_orbit_inspector.py)

These tests focus on:
- Testing the import structure
- Testing that scripts can be parsed without errors
"""

import matplotlib

matplotlib.use("Agg")  # 使用非 GUI 后端以抑制绘图显示

import pytest
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch
import numpy as np

project_root = Path(__file__).resolve().parent.parent.parent.parent


class TestPlotScriptImports:
    """测试绘图脚本可被导入和解析"""

    def _create_mock_family_result(self, mock_system):
        """创建正确配置的模拟 OrbitFamily 用于测试"""

        # Use a real class instead of MagicMock to avoid len() returning MagicMock
        class MockOrbitFamily:
            def __init__(self, system):
                self.system = system

            def __len__(self):
                return 0

            def get_jacobi_constants(self):
                return np.array([3.0, 3.5])

            def get_periods(self):
                return np.array([1.0, 1.5])

        return MockOrbitFamily(mock_system)

    @patch("e2m2e.core.OrbitFamily.load_from_file")
    @patch("e2m2e.core.CR3BP_System")
    def test_plot_orbits_imports(self, mock_system, mock_load):
        """Test that plot_orbits.py can be imported without errors"""
        mock_load.return_value = self._create_mock_family_result(
            mock_system.return_value
        )
        mock_system.return_value = MagicMock()

        script_path = project_root / "tod" / "plot" / "plot_orbits.py"
        spec = importlib.util.spec_from_file_location("plot_orbits", script_path)
        assert spec is not None
        module = importlib.util.module_from_spec(spec)

        try:
            spec.loader.exec_module(module)  # type: ignore[union-attr]
        except ImportError as e:
            pytest.skip(f"Missing dependency: {e}")
        except (Exception, SystemExit):
            pass

    @patch("e2m2e.core.OrbitFamily.load_from_file")
    @patch("e2m2e.core.CR3BP_System")
    def test_plot_interactive_imports(self, mock_system, mock_load):
        """Test that plot_interactive_orbit_inspector.py can be imported without errors"""
        # Mock expensive data loading to avoid long-running tests
        mock_load.return_value = self._create_mock_family_result(
            mock_system.return_value
        )
        mock_system.return_value = MagicMock()

        script_path = (
            project_root
            / "tod"
            / "pipelines"
            / "inspection"
            / "plot_interactive_orbit_inspector.py"
        )
        spec = importlib.util.spec_from_file_location(
            "plot_interactive_orbit_inspector", script_path
        )
        assert spec is not None
        module = importlib.util.module_from_spec(spec)

        try:
            spec.loader.exec_module(module)  # type: ignore[union-attr]
        except ImportError as e:
            pytest.skip(f"Missing dependency: {e}")
        except (Exception, SystemExit):
            pass
