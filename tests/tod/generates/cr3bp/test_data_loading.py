"""
数据加载与文件生成功能测试

这些测试：
- 测试加载现有轨道族 JSON 文件
"""

import pytest
import json
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent.parent.parent


class TestRealOrbitFamilyFiles:
    """Test loading real orbit family JSON files from output directory"""

    @pytest.fixture
    def output_dir(self):
        """Get the output directory path"""
        return project_root / "output" / "ro"

    def test_output_directory_exists(self, output_dir):
        """Test that output/ro directory exists"""
        if not output_dir.exists():
            pytest.skip(f"Output directory {output_dir} not found — run generators first")
        assert output_dir.exists()

    def test_there_are_json_files(self, output_dir):
        """Test that there are JSON orbit family files"""
        if not output_dir.exists():
            pytest.skip(f"Output directory {output_dir} not found — run generators first")
        json_files = list(output_dir.glob("*.json"))
        if not json_files:
            pytest.skip(f"No JSON files in {output_dir} — run generators first")
        assert len(json_files) > 0, "Should have at least one orbit family JSON file"

    @pytest.mark.parametrize(
        "json_file",
        [
            "ro_31_family_-0.9305--0.8304999999999999-0.001_3856908879.json",
            "ro_31_family_0.8905--0.8304999999999999-0.001_3856910376.json",
        ],
    )
    def test_ro_family_file_loads(self, output_dir, json_file):
        """Test that RO family JSON files can be loaded"""
        json_path = output_dir / json_file

        if not json_path.exists():
            pytest.skip(f"File {json_file} not found")

        with open(json_path, "r") as f:
            data = json.load(f)

        assert isinstance(data, dict)
        assert "orbits" in data or "family_type" in data
