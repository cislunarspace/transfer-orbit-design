"""Tests for tod.gui.files.file_operations."""

from pathlib import Path
from unittest.mock import MagicMock


from tod.gui.files.file_operations import (
    FILE_PATH_ROLE,
    format_delete_confirmation,
    get_selected_paths,
    make_relative_paths,
    reveal_in_file_manager,
)


class TestGetSelectedPaths:
    def test_single_selected_item_returns_its_path(self) -> None:
        """选中单个文件时返回该文件的绝对路径。"""
        tree = MagicMock()
        item = MagicMock()
        item.data.return_value = "/output/dro/family.json"
        tree.selectedItems.return_value = [item]

        paths = get_selected_paths(tree)

        assert paths == ["/output/dro/family.json"]
        item.data.assert_called_once_with(0, FILE_PATH_ROLE)

    def test_multiple_selected_items_returns_all_paths(self) -> None:
        """Ctrl/Shift 多选时返回所有选中文件的路径列表。"""
        tree = MagicMock()
        item1 = MagicMock()
        item1.data.return_value = "/output/dro/family.json"
        item2 = MagicMock()
        item2.data.return_value = "/output/ro/ro_31.json"
        tree.selectedItems.return_value = [item1, item2]

        paths = get_selected_paths(tree)

        assert paths == ["/output/dro/family.json", "/output/ro/ro_31.json"]


class TestMakeRelativePaths:
    def test_converts_absolute_to_relative(self) -> None:
        """将绝对路径转换为相对于 repo root 的路径。"""
        repo_root = Path("C:/project")
        paths = ["C:/project/output/dro/family.json"]

        result = make_relative_paths(paths, repo_root)

        assert result == ["output/dro/family.json"]

    def test_multiple_paths(self) -> None:
        """批量转换多个绝对路径。"""
        repo_root = Path("C:/project")
        paths = [
            "C:/project/output/dro/family.json",
            "C:/project/output/ro/ro_31.json",
        ]

        result = make_relative_paths(paths, repo_root)

        assert result == ["output/dro/family.json", "output/ro/ro_31.json"]


class TestFormatDeleteConfirmation:
    def test_single_file(self) -> None:
        """单文件删除确认包含文件名。"""
        paths = ["C:/project/output/dro/family.json"]

        title, message = format_delete_confirmation(paths)

        assert title == "确认删除"
        assert "family.json" in message
        assert "确定要删除" in message

    def test_multiple_files_within_limit(self) -> None:
        """少于等于 5 个文件时全部列出。"""
        paths = [f"C:/project/output/f{i}.json" for i in range(3)]

        title, message = format_delete_confirmation(paths)

        assert "f0.json" in message
        assert "f1.json" in message
        assert "f2.json" in message

    def test_multiple_files_over_limit(self) -> None:
        """超过 5 个文件时列出前 5 个并提示剩余数量。"""
        paths = [f"C:/project/output/f{i}.json" for i in range(7)]

        title, message = format_delete_confirmation(paths)

        assert "f0.json" in message
        assert "f4.json" in message
        assert "及其他 2 个文件" in message


class TestRevealInFileManager:
    def test_windows_uses_explorer_select(self, monkeypatch) -> None:
        """Windows 下调用 explorer /select,<path> 高亮文件。"""
        calls = []
        monkeypatch.setattr(
            "tod.gui.files.file_operations.subprocess.run",
            lambda cmd, **kw: calls.append(cmd),
        )

        reveal_in_file_manager("C:\\output\\dro\\family.json", _platform="Windows")

        assert calls == [["explorer", "/select,C:\\output\\dro\\family.json"]]

    def test_macos_uses_open_r(self, monkeypatch) -> None:
        """macOS 下调用 open -R <path>。"""
        calls = []
        monkeypatch.setattr(
            "tod.gui.files.file_operations.subprocess.run",
            lambda cmd, **kw: calls.append(cmd),
        )

        reveal_in_file_manager("/output/dro/family.json", _platform="Darwin")

        assert calls == [["open", "-R", "/output/dro/family.json"]]

    def test_linux_uses_xdg_open_parent(self, monkeypatch) -> None:
        """Linux 下调用 xdg-open 打开文件所在目录。"""
        calls = []
        monkeypatch.setattr(
            "tod.gui.files.file_operations.subprocess.run",
            lambda cmd, **kw: calls.append(cmd),
        )

        reveal_in_file_manager("/output/dro/family.json", _platform="Linux")

        assert calls == [["xdg-open", "/output/dro"]]
