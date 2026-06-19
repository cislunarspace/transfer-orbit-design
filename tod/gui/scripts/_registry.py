# pyright: reportArgumentType=false, reportOptionalMemberAccess=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false, reportInvalidTypeForm=false, reportCallIssue=false, reportPrivateImportUsage=false
"""_registry 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。description 按“目的、输入、输出”描述脚本，help 文本说明默认值与单位。
"""


from __future__ import annotations

import importlib.util
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class _NoScriptEntryError(RuntimeError):
    """文件加载成功但缺少 SCRIPT_ENTRY 导出。

    这是预期情况（实现目录中存在非注册文件），扫描器静默跳过。
    与加载失败（SyntaxError、ImportError 等真实 bug）区分。
    """

# 自包含的最小类型，避免在导入时触发 sciPy 等重型依赖。
# params 文件从 tod.gui.script_registry 导入真实的 ScriptEntry，
# 扫描器只读属性，不参与类型转换。


@dataclass(frozen=True)
class _ScanEntry:
    """扫描器视角下的 ScriptEntry，只包含分类所需的字段。"""

    module: str
    name: str
    description: str
    script_path: str
    output_dir: str | None = None
    accepts_file_arg: bool = False
    needs_spice: bool = False
    cli_chip_params: list = field(default_factory=list)
    multi_cli_params: list = field(default_factory=list)
    catalog_seed_selectors: list = field(default_factory=list)
    env_params: dict = field(default_factory=dict)
    cli_params: list = field(default_factory=list)
    group_label: str = ""


def iter_script_files(base: Path) -> Iterator[Path]:
    """Yield base 下所有含 SCRIPT_ENTRY 的 .py 文件（跳过私有目录和私有文件）。"""
    for path in base.rglob("*.py"):
        if any(p.name.startswith("_") for p in path.relative_to(base).parents):
            continue
        if path.name.startswith("_") or path.name == "__init__.py":
            continue
        yield path


def _load_script_entry(file_path: Path) -> _ScanEntry:
    """从单个 .py 文件加载 SCRIPT_ENTRY，不存在则抛异常。"""
    import sys as _sys

    module_name = f"_tod_scan_{file_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载文件: {file_path}")

    module = importlib.util.module_from_spec(spec)
    _sys.modules[module_name] = module  # @dataclass 需要模块在 sys.modules 中

    try:
        spec.loader.exec_module(module)
    except Exception as e:
        raise RuntimeError(f"加载 {file_path} 时出错: {e}") from e
    finally:
        _sys.modules.pop(module_name, None)  # 清理临时模块

    if not hasattr(module, "SCRIPT_ENTRY"):
        raise _NoScriptEntryError(
            f"文件 {file_path} 缺少 SCRIPT_ENTRY 导出。"
        )

    raw = module.SCRIPT_ENTRY
    return _ScanEntry(
        module=raw.module,
        name=raw.name,
        description=raw.description,
        script_path=raw.script_path,
        output_dir=raw.output_dir,
        accepts_file_arg=raw.accepts_file_arg,
        needs_spice=raw.needs_spice,
        cli_chip_params=raw.cli_chip_params,
        multi_cli_params=raw.multi_cli_params,
        catalog_seed_selectors=getattr(raw, "catalog_seed_selectors", []),
        env_params=raw.env_params,
        cli_params=raw.cli_params,
        group_label=raw.group_label,
    )


def _classify(entry: _ScanEntry) -> str:
    """根据 script_path 的目录结构推断分类键。

    例如: "tod/generates/ephemeris/dro/x.py" → "ephemeris"
          "tod/generates/cr3bp/dro/x.py" → "generates"
          "tod/plot/dro/plot_dro.py" → "plot"
          "tod/transfers/dro_to_geo/search.py" → "transfer"
    """
    parts = Path(entry.script_path).parts
    if "generates" in parts:
        # 细分：ephemeris 独立
        if "ephemeris" in parts:
            return "ephemeris"
        return "generates"
    if "plot" in parts:
        return "plot"
    if "transfers" in parts:
        return "transfer"
    if "inspection" in parts:
        return "inspection"
    return "misc"


def _default_scan_dirs() -> list[Path]:
    """返回默认扫描目录列表。

    扫描顺序决定优先级：同名 script_path 的条目以先扫到的为准。
    """
    gui_scripts = Path(__file__).parent
    repo_root = gui_scripts.parent.parent.parent  # tod/gui/scripts/ → repo root
    return [
        repo_root / "tod" / "generates",
        repo_root / "tod" / "plot",
        repo_root / "tod" / "transfers",
    ]


def get_scripts(
    scripts_dir: Path | None = None,
    translations: dict | None = None,
    scan_dirs: list[Path] | None = None,
) -> dict[str, list[_ScanEntry]]:
    """扫描实现目录，返回分类后的脚本注册表。

    Args:
        scripts_dir: 已废弃，保留向后兼容。优先使用 scan_dirs。
        translations: 脚本翻译表（按脚本名结构化），非空时应用于每个 ScriptEntry
        scan_dirs: 扫描目录列表，按优先级排列。同名 script_path 以先扫到的为准。
                   默认为实现目录（generates/plot/transfers）。

    Returns:
        dict[str, list[_ScanEntry]]: 按分类键分组的 _ScanEntry 列表
    """
    if scan_dirs is None:
        if scripts_dir is not None:
            scan_dirs = [scripts_dir]
        else:
            scan_dirs = _default_scan_dirs()

    seen_paths: set[str] = set()
    SCRIPTS: dict[str, list[_ScanEntry]] = {}

    for scan_dir in scan_dirs:
        if not scan_dir.is_dir():
            continue
        for file_path in iter_script_files(scan_dir):
            try:
                entry = _load_script_entry(file_path)
            except _NoScriptEntryError:
                continue  # 文件加载成功但无 SCRIPT_ENTRY（非注册文件），静默跳过
            except RuntimeError:
                logger.warning("扫描器跳过加载失败的脚本: %s", file_path, exc_info=True)
                continue
            if entry.script_path in seen_paths:
                continue  # 已由更高优先级目录注册
            seen_paths.add(entry.script_path)
            if translations:
                from tod.gui.i18n import translate_script_entry

                entry = translate_script_entry(entry, translations)
            category = _classify(entry)
            SCRIPTS.setdefault(category, []).append(entry)

    return SCRIPTS
