"""PyQt6 图形界面组件。

"""

import platform
import subprocess
from pathlib import Path

from PyQt6.QtCore import QCoreApplication, Qt

FILE_PATH_ROLE = Qt.ItemDataRole.UserRole + 1

_T = QCoreApplication.translate

def get_selected_paths(tree) -> list[str]:
    """从 QTreeWidget 获取所有选中文件的绝对路径。"""
    paths: list[str] = []
    for item in tree.selectedItems():
        path = item.data(0, FILE_PATH_ROLE)
        if path:
            paths.append(path)
    return paths

def make_relative_paths(paths: list[str], repo_root: Path) -> list[str]:
    """将绝对路径列表转换为相对于 repo root 的路径列表（统一用正斜杠）。"""
    return [str(Path(p).relative_to(repo_root).as_posix()) for p in paths]

def reveal_in_file_manager(path: str, _platform: str | None = None) -> None:
    """在系统文件管理器中显示指定文件。

    Windows: explorer /select,<path>
    macOS:   open -R <path>
    Linux:   xdg-open <parent_dir>
    """
    sys = _platform or platform.system()
    if sys == "Windows":
        subprocess.run(["explorer", f"/select,{path}"], check=False)
    elif sys == "Darwin":
        subprocess.run(["open", "-R", path], check=False)
    else:
        subprocess.run(["xdg-open", Path(path).parent.as_posix()], check=False)

def format_delete_confirmation(paths: list[str]) -> tuple[str, str]:
    """生成删除确认对话框的标题和消息。

    单文件：直接显示文件名。
    多文件：列出前 5 个文件名，超出显示"及其他 N 个文件"。
    """
    title = _T("FileOperations", "确认删除")
    if len(paths) == 1:
        name = Path(paths[0]).name
        message = _T("FileOperations", "确定要删除文件 {} 吗？").format(name)
    else:
        names = [Path(p).name for p in paths[:5]]
        message = _T("FileOperations", "确定要删除以下文件吗？\n\n") + "\n".join(names)
        if len(paths) > 5:
            message += _T("FileOperations", "\n\n及其他 {} 个文件").format(len(paths) - 5)
    return title, message
