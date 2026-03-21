"""
Tests for data loading and file generation functionality

These tests:
- Test loading existing orbit family JSON files
- Test file naming conventions
- Test data structure validation
"""

import pytest
import sys
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


# Sample orbit family data structure for testing
SAMPLE_ORBIT_DATA = {
    "family_type": "distant_retrograde_orbit",
    "system": {
        "mu": 0.0121506683,
        "primary": "earth",
        "secondary": "moon"
    },
    "orbits": [
        {
            "states": [[-0.8, 0.0, 0.0, 0.0, 0.4, 0.0]],
            "times": [0.0],
            "period": 6.28,
            "jacobi_constant": 3.0,
            "stability_index": 0.95
        }
    ],
    "metadata": {
        "created": "2025-01-01T00:00:00",
        "version": "1.0"
    }
}


class TestOrbitFamilyDataStructure:
    """Test orbit family JSON data structure"""

    def test_family_type_recognized(self):
        """Test that family_type field is valid"""
        family_type = SAMPLE_ORBIT_DATA["family_type"]
        valid_types = ["distant_retrograde_orbit", "halo", "lyapunov", "vertical", "butterfly"]
        assert family_type in valid_types

    def test_system_params_exist(self):
        """Test that system parameters are present"""
        system = SAMPLE_ORBIT_DATA["system"]
        assert "mu" in system
        assert "primary" in system
        assert "secondary" in system
        assert system["mu"] > 0

    def test_orbits_list_not_empty(self):
        """Test that orbits list is not empty"""
        assert len(SAMPLE_ORBIT_DATA["orbits"]) > 0

    def test_single_orbit_structure(self):
        """Test structure of a single orbit"""
        orbit = SAMPLE_ORBIT_DATA["orbits"][0]
        
        # States should be a list of lists with 6 elements
        assert "states" in orbit
        assert len(orbit["states"]) > 0
        assert len(orbit["states"][0]) == 6
        
        # Times should match states length
        assert "times" in orbit
        assert len(orbit["times"]) == len(orbit["states"])
        
        # Period should be positive
        assert "period" in orbit
        assert orbit["period"] > 0


class TestOrbitFamilyFileNaming:
    """Test orbit family file naming conventions"""

    def test_ro_31_filename_pattern(self):
        """Test 3:1 RO family filename pattern"""
        filename = "ro_31_family_0.8905--0.8304999999999999-0.001_3856910376.json"
        
        # Should contain family type identifier
        assert "ro_31_family" in filename
        
        # Should contain parameter range
        assert "0.8905" in filename
        
        # Should end with .json
        assert filename.endswith(".json")

    def test_ro_32_filename_pattern(self):
        """Test 3:2 RO family filename pattern"""
        filename = "ro_32_family_-1.2--0.8-0.005_3856904629.json"
        
        assert "ro_32_family" in filename
        assert ".json" in filename

    def test_dro_filename_pattern(self):
        """Test DRO family filename pattern"""
        filename = "dro_family_0.6-0.8-0.005_3856837265.json"
        
        assert "dro_family" in filename
        assert ".json" in filename

    def test_filename_contains_timestamp(self):
        """Test that filename contains timestamp-like suffix"""
        filename = "ro_31_family_0.8905--0.8304999999999999-0.001_3856910376.json"
        
        # Extract the numeric suffix (timestamp)
        parts = filename.replace(".json", "").split("_")
        last_part = parts[-1]
        
        # Should be a reasonably large number (timestamp)
        assert len(last_part) >= 7  # At least 7 digits for timestamp
        assert last_part.isdigit() or last_part.replace(".", "").isdigit()


class TestJSONLoading:
    """Test JSON file loading and parsing"""

    def test_json_serialization(self):
        """Test that sample data can be serialized to JSON"""
        json_str = json.dumps(SAMPLE_ORBIT_DATA)
        assert len(json_str) > 0
        
    def test_json_deserialization(self):
        """Test that JSON can be deserialized back to dict"""
        json_str = json.dumps(SAMPLE_ORBIT_DATA)
        parsed = json.loads(json_str)
        
        assert parsed["family_type"] == SAMPLE_ORBIT_DATA["family_type"]
        assert parsed["system"]["mu"] == SAMPLE_ORBIT_DATA["system"]["mu"]
        assert len(parsed["orbits"]) == len(SAMPLE_ORBIT_DATA["orbits"])

    def test_invalid_json_raises_error(self):
        """Test that invalid JSON raises JSONDecodeError"""
        invalid_json = "{ invalid json }"
        
        with pytest.raises(json.JSONDecodeError):
            json.loads(invalid_json)


class TestRealOrbitFamilyFiles:
    """Test loading real orbit family JSON files from output directory"""

    @pytest.fixture
    def output_dir(self):
        """Get the output directory path"""
        return project_root / "output" / "ro"

    def test_output_directory_exists(self, output_dir):
        """Test that output/ro directory exists"""
        assert output_dir.exists(), f"Output directory {output_dir} should exist"

    def test_there_are_json_files(self, output_dir):
        """Test that there are JSON orbit family files"""
        json_files = list(output_dir.glob("*.json"))
        assert len(json_files) > 0, "Should have at least one orbit family JSON file"

    @pytest.mark.parametrize("json_file", [
        "ro_31_family_-0.9305--0.8304999999999999-0.001_3856908879.json",
        "ro_31_family_0.8905--0.8304999999999999-0.001_3856910376.json",
    ])
    def test_ro_family_file_loads(self, output_dir, json_file):
        """Test that RO family JSON files can be loaded"""
        json_path = output_dir / json_file
        
        if not json_path.exists():
            pytest.skip(f"File {json_file} not found")
        
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        assert isinstance(data, dict)
        assert "orbits" in data or "family_type" in data
