# pyright: reportArgumentType=false, reportOptionalMemberAccess=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false, reportInvalidTypeForm=false, reportCallIssue=false, reportPrivateImportUsage=false
"""_registry 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。description 按“目的、输入、输出”描述脚本，help 文本说明默认值与单位。
"""


from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    pass

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


def get_scripts(scripts_dir: Path | None = None, translations: dict | None = None) -> dict[str, list[_ScanEntry]]:
    """扫描 scripts_dir，返回分类后的脚本注册表。

    Args:
        scripts_dir: scripts/ 目录路径，默认为 tod/gui/scripts/
        translations: 脚本翻译表（按脚本名结构化），非空时应用于每个 ScriptEntry

    Returns:
        dict[str, list[_ScanEntry]]: 按分类键分组的 _ScanEntry 列表
    """
    if scripts_dir is None:
        scripts_dir = Path(__file__).parent

    SCRIPTS: dict[str, list[_ScanEntry]] = {}

    for file_path in iter_script_files(scripts_dir):
        entry = _load_script_entry(file_path)
        if translations:
            from tod.gui.i18n import translate_script_entry

            entry = translate_script_entry(entry, translations)
        category = _classify(entry)
        SCRIPTS.setdefault(category, []).append(entry)

    return SCRIPTS
