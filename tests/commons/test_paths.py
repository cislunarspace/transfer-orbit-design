"""tests for src.commons.paths"""

from pathlib import Path

import src.commons.paths as paths_module
from src.commons.paths import OUTPUT_DIR, detect_kernel_dir


class TestOutputDir:
    def test_points_to_repo_root_output(self):
        assert OUTPUT_DIR.name == "output"
        # OUTPUT_DIR should be the repo root's output/, anchored to paths.py location
        assert OUTPUT_DIR.parent == Path(__file__).resolve().parent.parent.parent

    def test_is_absolute(self):
        assert OUTPUT_DIR.is_absolute()


class TestDetectKernelDir:
    def test_env_priority(self, monkeypatch, tmp_path):
        # SPICE_KERNEL_DIR 指向有效目录时优先返回它
        target = tmp_path / "kernels"
        target.mkdir()
        monkeypatch.setenv("SPICE_KERNEL_DIR", str(target))
        assert detect_kernel_dir() == str(target)

    def test_invalid_env_falls_through_to_empty(self, monkeypatch, tmp_path):
        # SPICE_KERNEL_DIR 指向不存在的目录且默认路径也不存在时返回空串
        monkeypatch.setenv("SPICE_KERNEL_DIR", "/no/such/dir")
        monkeypatch.setattr(paths_module, "_REPO_ROOT", tmp_path / "repo")
        assert detect_kernel_dir() == ""

    def test_default_when_env_unset(self, monkeypatch, tmp_path):
        # env 未设时回退到 <repo>/../e2m2e/kernels
        monkeypatch.delenv("SPICE_KERNEL_DIR", raising=False)
        default = tmp_path / "e2m2e" / "kernels"
        default.mkdir(parents=True)
        monkeypatch.setattr(paths_module, "_REPO_ROOT", tmp_path / "repo")
        assert detect_kernel_dir() == str(default)
