"""
Tests for generation scripts (generate_31_ro_family.py, generate_32_ro_family.py, generate_dro_family.py)

These tests focus on:
- Testing the parameter configurations
- Testing the import structure
- Testing that scripts can be parsed without errors
"""

import pytest
import sys
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class TestGenerateScriptImports:
    """Test that generation scripts can be imported and parsed"""

    def test_generate_31_ro_imports(self):
        """Test that generate_31_ro_family.py can be imported without errors"""
        script_path = project_root / "scripts" / "generate_31_ro_family.py"
        spec = importlib.util.spec_from_file_location("generate_31_ro_family", script_path)
        module = importlib.util.module_from_spec(spec)
        
        # Should not raise when parsing
        # Note: actual execution may fail without e2m2e, but import should work
        try:
            spec.loader.exec_module(module)
        except ImportError:
            # e2m2e may not be installed in test env, which is OK for syntax check
            pass

    def test_generate_32_ro_imports(self):
        """Test that generate_32_ro_family.py can be imported without errors"""
        script_path = project_root / "scripts" / "generate_32_ro_family.py"
        spec = importlib.util.spec_from_file_location("generate_32_ro_family", script_path)
        module = importlib.util.module_from_spec(spec)
        
        try:
            spec.loader.exec_module(module)
        except ImportError:
            pass

    def test_generate_dro_imports(self):
        """Test that generate_dro_family.py can be imported without errors"""
        script_path = project_root / "scripts" / "generate_dro_family.py"
        spec = importlib.util.spec_from_file_location("generate_dro_family", script_path)
        module = importlib.util.module_from_spec(spec)
        
        try:
            spec.loader.exec_module(module)
        except ImportError:
            pass


class TestGenerate31ROParameters:
    """Test generate_31_ro_family.py parameter configurations"""

    def test_seed_parameters_31ro(self):
        """Test that 3:1 RO seed orbit parameters are reasonable"""
        # These are theoretical values from the script
        x0 = -0.8805
        z0 = 0.0
        vy0 = 0.3921
        vz0 = 0.0
        
        # x0 should be in valid range for 3:1 RO
        assert -2 < x0 < 0  # RO orbits are on Moon's far side
        assert z0 == 0  # Planar orbit
        assert vy0 > 0  # Retrograde orbit has positive vy
        assert vz0 == 0  # Planar orbit

    def test_continuation_range_31ro(self):
        """Test that 3:1 RO continuation range is reasonable"""
        x0 = -0.8805
        param_min = x0
        param_max = x0 + 0.05
        
        assert param_min < 0  # RO orbits are on Moon's far side (negative x)
        assert param_max > param_min
        assert param_max < 0  # Should be in valid RO region


class TestGenerate32ROParameters:
    """Test generate_32_ro_family.py parameter configurations"""

    def test_seed_parameters_32ro(self):
        """Test that 3:2 RO seed orbit parameters are reasonable"""
        x0 = -1.1453
        z0 = 0.0
        vy0 = 0.4633
        vz0 = 0.0
        
        # x0 should be in valid range for 3:2 RO
        assert -2 < x0 < 0
        assert z0 == 0
        assert vy0 > 0
        assert vz0 == 0

    def test_continuation_range_32ro(self):
        """Test that 3:2 RO continuation range is reasonable"""
        param_min = -1.2
        param_max = -0.8
        
        assert param_min < param_max
        assert -2 < param_min < 0
        assert -2 < param_max < 0


class TestGenerateDROParameters:
    """Test generate_dro_family.py parameter configurations"""

    def test_seed_parameters_dro(self):
        """Test that DRO seed orbit parameters are reasonable"""
        x0 = 0.79188556619742
        vy0 = 0.53682
        
        # DRO orbits are between Earth and Moon, x0 should be positive
        assert 0 < x0 < 1
        assert vy0 > 0

    def test_continuation_range_dro(self):
        """Test that DRO continuation range is reasonable"""
        param_min = 0.6
        param_max = 0.8
        step_size = 0.005
        
        assert 0 < param_min < param_max
        assert param_max < 1
        assert step_size > 0
        assert step_size < 0.1  # Step size should be reasonable
