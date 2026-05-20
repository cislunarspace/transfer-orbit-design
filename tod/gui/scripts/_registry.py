"""Script registry scanner — 自动扫描并收集所有 script params 定义。

启动时调用一次，由 GUI 层的 script_registry.py 封装后使用。
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    from tod.gui.script_registry import CliParam, EnvParam

# 自包含的最小类型，避免拉入 sciPy 等重型依赖。
# 实际类型由 params 定义文件从 tod.gui.script_registry 导入，
# 扫描器只读属性。


@dataclass(frozen=True)
class ScriptEntryScan:
    """扫描器视角下的 ScriptEntry，只包含分类所需的字段。"""

    module: str
    name: str
    description: str
    script_path: str
    output_dir: str | None = None
    accepts_file_arg: bool = False
    needs_spice: bool = False
    env_params: dict = field(default_factory=dict)
    cli_params: list = field(default_factory=list)
    group_label: str = ""


def iter_script_files(base: Path) -> Iterator[Path]:
    """Yield base 下所有含 SCRIPT_ENTRY 的 .py 文件（跳过私有目录和私有文件）。"""
    for path in base.rglob("*.py"):
        # 跳过私有文件和私有目录下的所有内容
        if any(p.name.startswith("_") for p in path.relative_to(base).parents):
            continue
        if path.name.startswith("_") or path.name == "__init__.py":
            continue
        yield path


def _load_script_entry(file_path: Path) -> ScriptEntryScan:
    """从单个 .py 文件加载 SCRIPT_ENTRY，不存在则抛异常。"""
    spec = importlib.util.spec_from_file_location("_script_module", file_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载文件: {file_path}")

    module = importlib.util.module_from_spec(spec)

    try:
        spec.loader.exec_module(module)
    except Exception as e:
        raise RuntimeError(f"加载 {file_path} 时出错: {e}") from e

    if not hasattr(module, "SCRIPT_ENTRY"):
        raise RuntimeError(
            f"文件 {file_path} 缺少 SCRIPT_ENTRY 导出。\n"
            "每个 params 定义文件必须导出 SCRIPT_ENTRY = ScriptEntry(...)。"
        )

    raw = module.SCRIPT_ENTRY
    return ScriptEntryScan(
        module=raw.module,
        name=raw.name,
        description=raw.description,
        script_path=raw.script_path,
        output_dir=raw.output_dir,
        accepts_file_arg=raw.accepts_file_arg,
        needs_spice=raw.needs_spice,
        env_params=raw.env_params,
        cli_params=raw.cli_params,
        group_label=raw.group_label,
    )


def _classify(entry: ScriptEntryScan) -> str:
    """根据 script_path 的目录结构推断分类键。

    例如: "tod/generates/cr3bp/dro/generate_dro.py" → "generates"
          "tod/plot/dro/plot_dro.py" → "plot"
          "tod/transfers/dro_to_geo/search.py" → "transfer"
    """
    parts = set(Path(entry.script_path).parts)
    if "generates" in parts:
        return "generates"
    if "plot" in parts:
        return "plot"
    if "transfers" in parts:
        return "transfer"
    if "inspection" in parts:
        return "inspection"
    return "misc"


def get_scripts(scripts_dir: Path | None = None) -> dict[str, list[ScriptEntryScan]]:
    """扫描 scripts_dir，返回分类后的脚本注册表。

    Args:
        scripts_dir: scripts/ 目录路径，默认为 tod/gui/scripts/

    Returns:
        dict[str, list[ScriptEntryScan]]: 按分类键分组的 ScriptEntryScan 列表
    """
    if scripts_dir is None:
        scripts_dir = Path(__file__).parent

    SCRIPTS: dict[str, list[ScriptEntryScan]] = {}

    for file_path in iter_script_files(scripts_dir):
        entry = _load_script_entry(file_path)
        category = _classify(entry)
        SCRIPTS.setdefault(category, []).append(entry)

    return SCRIPTS
