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
    """三段解析链（#415 收窄：配置文件层已删）：env → 仓库 kernels/ →
    用户数据目录，末尾附开发机历史布局回退。"""
    """The three-segment chain (narrowed by #415: config layer removed):
    env -> repo kernels/ -> user-data dir, plus the dev-layout fallback."""

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

    def test_repo_kernels_beats_user_data_dir(self, monkeypatch, tmp_path):
        # 仓库根 kernels/ 优先于用户数据目录（第二段）
        # Repo-root kernels/ wins over the user-data directory (second segment)
        monkeypatch.delenv("SPICE_KERNEL_DIR", raising=False)
        repo = tmp_path / "repo"
        (repo / "kernels").mkdir(parents=True)
        (tmp_path / "user-kernels").mkdir()
        monkeypatch.setattr(paths_module, "_REPO_ROOT", repo)
        assert detect_kernel_dir() == str(repo / "kernels")

    def test_default_when_env_unset(self, monkeypatch, tmp_path):
        # env 未设时回退到 <repo>/../e2m2e/kernels
        # Falls back to <repo>/../e2m2e/kernels when the env var is unset
        monkeypatch.delenv("SPICE_KERNEL_DIR", raising=False)
        default = tmp_path / "e2m2e" / "kernels"
        default.mkdir(parents=True)
        monkeypatch.setattr(paths_module, "_REPO_ROOT", tmp_path / "repo")
        assert detect_kernel_dir() == str(default)

    def test_user_data_dir_found(self, monkeypatch, tmp_path):
        # 用户数据目录（GUI 下载落点）可被探测到
        # The user-data directory (GUI download target) can be detected
        monkeypatch.delenv("SPICE_KERNEL_DIR", raising=False)
        user_dir = tmp_path / "user-kernels"
        user_dir.mkdir(parents=True)
        monkeypatch.setattr(paths_module, "_REPO_ROOT", tmp_path / "repo")
        assert detect_kernel_dir() == str(user_dir)

    def test_stale_kernels_dir_txt_ignored(self, monkeypatch, tmp_path):
        # 残留的旧 kernels_dir.txt（配置层已删）不参与解析：存在与否不影响结果
        # A leftover kernels_dir.txt (config layer removed) never joins the
        # resolution: its presence changes nothing
        monkeypatch.delenv("SPICE_KERNEL_DIR", raising=False)
        stale = tmp_path / "config" / "kernels_dir.txt"
        stale.parent.mkdir(parents=True)
        chosen = tmp_path / "my-kernels"
        chosen.mkdir()
        stale.write_text(str(chosen), encoding="utf-8")
        monkeypatch.setattr(paths_module, "_REPO_ROOT", tmp_path / "repo")
        default = tmp_path / "e2m2e" / "kernels"
        default.mkdir(parents=True)
        assert detect_kernel_dir() == str(default)
