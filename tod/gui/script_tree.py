"""PyQt6 图形界面组件。

本模块为 Transfer Orbit Design 的脚本化工作流提供辅助类型、函数或入口。
"""


from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from tod.gui.script_registry import ScriptEntry

PROJECT_ROOT = Path(__file__).resolve().parents[2]

GENERATES_COLOR = "#4A90D9"
TRANSFERS_COLOR = "#E6A23C"
PLOT_COLOR = "#67C23A"
EMPTY_FOLDER_COLOR = "#F56C6C"

_SECTION_COLORS = {
    "generates": GENERATES_COLOR,
    "transfers": TRANSFERS_COLOR,
    "plot": PLOT_COLOR,
}

NodeType = Literal["folder", "script", "empty_folder"]


@dataclass
class TreeNode:
    """表示 TreeNode 相关的数据结构或行为。
    
    该类由脚本或 GUI 工作流内部使用，字段含义与调用处的参数保持一致。
    """
    name: str
    path: str
    node_type: NodeType
    color: str
    children: list[TreeNode] = field(default_factory=list)
    script_entry: ScriptEntry | None = None


def build_tree_from_scripts(scripts: dict[str, list[ScriptEntry]]) -> list[TreeNode]:
    """Build sidebar tree nodes from the script registry and on-disk folders."""

    indexed_dirs = _collect_script_dirs(scripts)
    roots_by_path: dict[str, TreeNode] = {}

    for entry in _iter_script_entries(scripts):
        parts = _script_folder_parts(entry.script_path)
        if not parts:
            continue

        color = _color_for_parts(parts)
        parent = _ensure_folder_path(parts, roots_by_path, color)
        parent.children.append(
            TreeNode(
                name=entry.name,
                path=entry.script_path,
                node_type="script",
                color=color,
                script_entry=entry,
            )
        )

    for parts in _iter_filesystem_dirs(indexed_dirs):
        color = _color_for_parts(parts)
        path = _join_tod_path(parts)
        existing = _find_node(roots_by_path, path)
        if existing is not None:
            continue

        empty = TreeNode(parts[-1], path, "empty_folder", EMPTY_FOLDER_COLOR)
        if len(parts) == 1:
            roots_by_path[path] = empty
        else:
            parent = _ensure_folder_path(parts[:-1], roots_by_path, color)
            parent.children.append(empty)

    return [roots_by_path[path] for path in _ordered_root_paths(roots_by_path)]


def _iter_script_entries(scripts: dict[str, list[ScriptEntry]]) -> list[ScriptEntry]:
    return [entry for entries in scripts.values() for entry in entries]


def _script_folder_parts(script_path: str) -> list[str]:
    parts = Path(script_path).parts
    if len(parts) < 2 or parts[0] != "tod":
        return []
    return list(parts[1:-1])[:3]


def _join_tod_path(parts: list[str] | tuple[str, ...]) -> str:
    return "/".join(("tod", *parts))


def _color_for_parts(parts: list[str] | tuple[str, ...]) -> str:
    return _SECTION_COLORS.get(parts[0], EMPTY_FOLDER_COLOR)


def _ensure_folder_path(
    parts: list[str] | tuple[str, ...],
    roots_by_path: dict[str, TreeNode],
    color: str,
) -> TreeNode:
    if not parts:
        raise ValueError("script paths must include a folder below tod/")

    root_path = _join_tod_path(parts[:1])
    node = roots_by_path.get(root_path)
    if node is None:
        node = TreeNode(parts[0], root_path, "folder", color)
        roots_by_path[root_path] = node

    current = node
    for depth in range(2, len(parts) + 1):
        path = _join_tod_path(parts[:depth])
        child = next(
            (
                child
                for child in current.children
                if child.path == path and child.node_type != "script"
            ),
            None,
        )
        if child is None:
            child = TreeNode(parts[depth - 1], path, "folder", color)
            current.children.append(child)
        current = child

    return current


def _find_node(roots_by_path: dict[str, TreeNode], path: str) -> TreeNode | None:
    for root in roots_by_path.values():
        found = _find_node_in(root, path)
        if found is not None:
            return found
    return None


def _find_node_in(node: TreeNode, path: str) -> TreeNode | None:
    if node.path == path:
        return node
    for child in node.children:
        found = _find_node_in(child, path)
        if found is not None:
            return found
    return None


def _collect_script_dirs(scripts: dict[str, list[ScriptEntry]]) -> set[str]:
    return {
        _join_tod_path(parts)
        for entry in _iter_script_entries(scripts)
        if (parts := _script_folder_parts(entry.script_path))
    }


def _iter_filesystem_dirs(indexed_dirs: set[str]) -> list[list[str]]:
    tod_root = PROJECT_ROOT / "tod"
    if not tod_root.is_dir():
        return []

    dirs: list[list[str]] = []
    for root in _iter_ordered_function_roots(tod_root):
        _collect_filesystem_dirs(root, [root.name], indexed_dirs, dirs)
    return dirs


def _iter_ordered_function_roots(tod_root: Path) -> list[Path]:
    return [
        tod_root / name
        for name in _SECTION_COLORS
        if (tod_root / name).is_dir()
    ]


def _collect_filesystem_dirs(
    directory: Path,
    parts: list[str],
    indexed_dirs: set[str],
    dirs: list[list[str]],
) -> bool:
    path = _join_tod_path(parts)
    child_has_registered_script = False

    if len(parts) < 3:
        for child in directory.iterdir():
            if not child.is_dir() or child.name.startswith("__"):
                continue
            child_has_registered_script = (
                _collect_filesystem_dirs(
                    child,
                    [*parts, child.name],
                    indexed_dirs,
                    dirs,
                )
                or child_has_registered_script
            )

    has_registered_script = path in indexed_dirs or child_has_registered_script
    if not has_registered_script and _dir_has_meaningful_scripts(directory):
        dirs.append(parts)
    return has_registered_script


def _dir_has_meaningful_scripts(directory: Path) -> bool:
    """目录下是否包含至少一个实际 Python 脚本（排除 __init__.py 和私有文件）。"""
    for entry in directory.iterdir():
        if entry.is_file() and entry.suffix == ".py" and not entry.name.startswith("_"):
            return True
    return False


def _ordered_root_paths(roots_by_path: dict[str, TreeNode]) -> list[str]:
    tod_root = PROJECT_ROOT / "tod"
    if not tod_root.is_dir():
        return list(roots_by_path)

    ordered = [
        _join_tod_path([name])
        for name in _SECTION_COLORS
        if _join_tod_path([name]) in roots_by_path
    ]
    remaining = [path for path in roots_by_path if path not in ordered]
    return [*ordered, *remaining]
