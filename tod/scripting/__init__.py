"""脚本注册表中性层：计算脚本与 GUI 共享的数据类型、扫描器与 SCRIPTS 代理。

本包从 tod.gui 解耦出来，消除「48 个计算脚本反向依赖 tod.gui.script_registry」
造成的 gui ↔ computes 循环。计算脚本应从 ``tod.scripting`` 导入 CliParam、
ScriptEntry 等声明类型；GUI 与扫描器内部从本包消费同一套类型。

公开 API：
- 数据类型：ScriptEntry、CliParam、MultiCliParam、CliChipParam、
  CatalogSeedSelectorParam、PerFileField、EnvParam、MultiFileConfig、UNIT_GROUPS
- 扫描器：get_scripts、iter_script_files、_make_module_name、_NoScriptEntryError
- 注册表单例：SCRIPTS（懒加载代理）、set_script_translations
"""

from tod.scripting.scanner import (
    _NoScriptEntryError,
    _make_module_name,
    get_scripts,
    iter_script_files,
)
from tod.scripting.types import (
    UNIT_GROUPS,
    CatalogSeedSelectorParam,
    CliChipParam,
    CliParam,
    EnvParam,
    MultiCliParam,
    MultiFileConfig,
    PerFileField,
    ScriptEntry,
)

__all__ = [
    "UNIT_GROUPS",
    "CatalogSeedSelectorParam",
    "CliChipParam",
    "CliParam",
    "EnvParam",
    "MultiCliParam",
    "MultiFileConfig",
    "PerFileField",
    "SCRIPTS",
    "ScriptEntry",
    "_NoScriptEntryError",
    "_make_module_name",
    "get_scripts",
    "iter_script_files",
    "set_script_translations",
]

# 由扫描器在首次访问时填充
_SCRIPTS: dict[str, list] | None = None

# 脚本翻译表 — 由 MainWindow 在启动时通过 set_script_translations() 设置。
# 在首次 SCRIPTS 访问前设置，语言切换（重启生效）无需缓存失效。
_TRANSLATIONS: dict | None = None

def set_script_translations(translations: dict) -> None:
    """设置脚本翻译表（应在首次访问 SCRIPTS 之前调用）。"""
    global _TRANSLATIONS
    _TRANSLATIONS = translations

def _get_scripts() -> dict[str, list]:
    """Lazily load and cache SCRIPTS from the scanner."""
    global _SCRIPTS
    if _SCRIPTS is None:
        from tod.scripting.scanner import get_scripts
        _SCRIPTS = get_scripts(translations=_TRANSLATIONS)
    return _SCRIPTS

def _scripts_getter() -> dict[str, list[ScriptEntry]]:
    return _get_scripts()

# Legacy category key aliases (old → new) for backward compatibility.
_LEGACY_ALIASES: dict[str, str] = {
    "Halo": "generates",
    "Transfer": "transfer",
    "Ephemeris": "ephemeris",
    "Inspection": "inspection",
}

# 代理对象：首次访问时延迟解析 SCRIPTS。
class _SCRIPTSProxy:
    """SCRIPTS 的延迟代理 — 首次访问时从扫描器解析。"""

    def __getitem__(self, key: str) -> list:
        _key = _LEGACY_ALIASES.get(key, key)
        return _get_scripts()[_key]

    def get(self, key: str, default=None):
        """执行 get 对应的处理逻辑。

        Args:
            key: 调用方传入的参数值。
            default: 调用方传入的参数值。

        Returns:
            函数执行结果。
        """
        _key = _LEGACY_ALIASES.get(key, key)
        return _get_scripts().get(_key, default)

    def keys(self):
        
        return _get_scripts().keys()

    def values(self):
        
        return _get_scripts().values()

    def items(self):
        
        return _get_scripts().items()

    def __iter__(self):
        return iter(_get_scripts())

    def __len__(self) -> int:
        return len(_get_scripts())

    def __repr__(self) -> str:
        return repr(_get_scripts())

# SCRIPTS 是懒加载的代理对象 — GUI 侧边栏等处的 `SCRIPTS.keys()` 等调用会触发扫描
SCRIPTS: dict = _SCRIPTSProxy()  # type: ignore[assignment]
