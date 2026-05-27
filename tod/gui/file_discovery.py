"""PyQt6 图形界面组件。

本模块为 Transfer Orbit Design 的脚本化工作流提供辅助类型、函数或入口。
"""


from dataclasses import dataclass
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path


@dataclass
class FileInfo:
    """表示 FileInfo 相关的数据结构或行为。
    
    该类由脚本或 GUI 工作流内部使用，字段含义与调用处的参数保持一致。
    """
    name: str
    path: str           # 相对于仓库根目录
    abs_path: str       # 绝对路径
    size: int           # 字节数
    modified: datetime  # 修改时间
    file_type: str      # "json", "png" 等
    category: str       # "dro", "ro", "transfer", "ephemeris", "halo"


def format_size(size: int) -> str:
    """将字节数格式化为人类可读的字符串。"""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    else:
        return f"{size / (1024 * 1024):.1f} MB"


def discover_files(repo_root: Path) -> list[FileInfo]:
    """扫描 output/ 子目录，返回所有文件的列表（按修改时间倒序）。"""
    results: list[FileInfo] = []
    output_dir = repo_root / "output"
    if not output_dir.is_dir():
        return results

    for subdir in sorted(output_dir.iterdir()):
        if not subdir.is_dir():
            continue
        category = subdir.name
        _scan_directory(subdir, category, repo_root, results)

    return results


def _scan_directory(
    directory: Path,
    category: str,
    repo_root: Path,
    results: list[FileInfo],
) -> None:
    """递归扫描一个目录，将文件追加到 results。"""
    for entry in directory.iterdir():
        if entry.is_symlink():
            continue
        try:
            if entry.is_dir():
                _scan_directory(entry, category, repo_root, results)
            elif entry.is_file():
                stat = entry.stat()
                results.append(FileInfo(
                    name=entry.name,
                    path=str(entry.relative_to(repo_root)),
                    abs_path=str(entry),
                    size=stat.st_size,
                    modified=datetime.fromtimestamp(stat.st_mtime),
                    file_type=entry.suffix.lstrip("."),
                    category=category,
                ))
        except OSError:
            continue  # 跳过无法访问的文件/目录


def filter_files(
    files: list[FileInfo],
    category: str | None = None,
    file_type: str | None = None,
    name_pattern: str | None = None,
) -> list[FileInfo]:
    """按类别和/或文件类型过滤。"""
    result = files
    if category:
        result = [f for f in result if f.category == category]
    if file_type:
        result = [f for f in result if f.file_type == file_type]
    if name_pattern:
        result = [f for f in result if fnmatch(f.name, name_pattern)]
    return result
