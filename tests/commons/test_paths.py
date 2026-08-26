"""tests for src.commons.paths"""

from pathlib import Path

import pytest

import src.commons.paths as paths_module
from src.commons.paths import OUTPUT_DIR, detect_kernel_dir


@pytest.fixture(autouse=True)
def _isolate_user_paths(monkeypatch, tmp_path):
    """隔离真实用户配置/数据目录，探测链只走 tmp_path 内的路径。

        Isolate real user config/data
    directories; the probe chain only sees paths inside tmp_path."""
    monkeypatch.setattr(paths_module, "user_config_dir", lambda: tmp_path / "config")
    monkeypatch.setattr(paths_module, "user_kernel_dir", lambda: tmp_path / "user-kernels")


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
        # Returns SPICE_KERNEL_DIR first when it points at a valid directory
        target = tmp_path / "kernels"
        target.mkdir()
        monkeypatch.setenv("SPICE_KERNEL_DIR", str(target))
        assert detect_kernel_dir() == str(target)

    def test_invalid_env_falls_through_to_empty(self, monkeypatch, tmp_path):
        # SPICE_KERNEL_DIR 指向不存在的目录且默认路径也不存在时返回空串
        # Returns an empty string when SPICE_KERNEL_DIR does not exist and no default
        # path exists either
        monkeypatch.setenv("SPICE_KERNEL_DIR", "/no/such/dir")
        monkeypatch.setattr(paths_module, "_REPO_ROOT", tmp_path / "repo")
        assert detect_kernel_dir() == ""

    def test_default_when_env_unset(self, monkeypatch, tmp_path):
        # env 未设时回退到 <repo>/../e2m2e/kernels
        # Falls back to <repo>/../e2m2e/kernels when the env var is unset
        monkeypatch.delenv("SPICE_KERNEL_DIR", raising=False)
        default = tmp_path / "e2m2e" / "kernels"
        default.mkdir(parents=True)
        monkeypatch.setattr(paths_module, "_REPO_ROOT", tmp_path / "repo")
        assert detect_kernel_dir() == str(default)

    def test_configured_dir_beats_repo_kernels(self, monkeypatch, tmp_path):
        # 配置文件记录的用户目录优先于仓库根 kernels/
        # The user directory recorded in the config takes precedence over repo-root kernels/
        monkeypatch.delenv("SPICE_KERNEL_DIR", raising=False)
        configured = tmp_path / "config" / "kernels_dir.txt"
        configured.parent.mkdir(parents=True)
        chosen = tmp_path / "my-kernels"
        chosen.mkdir()
        configured.write_text(str(chosen), encoding="utf-8")
        monkeypatch.setattr(paths_module, "_REPO_ROOT", tmp_path / "repo")
        (tmp_path / "repo" / "kernels").mkdir(parents=True)
        assert detect_kernel_dir() == str(chosen)

    def test_user_data_dir_found(self, monkeypatch, tmp_path):
        # 用户数据目录（GUI 下载落点）可被探测到
        # The user-data directory (GUI download target) can be detected
        monkeypatch.delenv("SPICE_KERNEL_DIR", raising=False)
        user_dir = tmp_path / "user-kernels"
        user_dir.mkdir(parents=True)
        monkeypatch.setattr(paths_module, "_REPO_ROOT", tmp_path / "repo")
        assert detect_kernel_dir() == str(user_dir)

    def test_stale_configured_dir_ignored(self, monkeypatch, tmp_path):
        # 配置指向已删除目录时忽略，继续回退
        # A config pointing at a deleted directory is ignored; fallback continues
        monkeypatch.delenv("SPICE_KERNEL_DIR", raising=False)
        configured = tmp_path / "config" / "kernels_dir.txt"
        configured.parent.mkdir(parents=True)
        configured.write_text(str(tmp_path / "gone"), encoding="utf-8")
        default = tmp_path / "e2m2e" / "kernels"
        default.mkdir(parents=True)
        monkeypatch.setattr(paths_module, "_REPO_ROOT", tmp_path / "repo")
        assert detect_kernel_dir() == str(default)


class TestConfiguredKernelDir:
    def test_roundtrip(self, tmp_path):
        target = tmp_path / "chosen" / "kernels"
        target.mkdir(parents=True)
        paths_module.save_configured_kernel_dir(target)
        assert paths_module.load_configured_kernel_dir() == str(target.resolve())

    def test_missing_returns_empty(self):
        assert paths_module.load_configured_kernel_dir() == ""

    def test_stale_path_returns_empty(self, tmp_path):
        paths_module.save_configured_kernel_dir(tmp_path / "gone")
        assert paths_module.load_configured_kernel_dir() == ""
