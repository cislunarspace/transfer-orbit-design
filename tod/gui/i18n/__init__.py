"""i18n 模块：加载 GUI 翻译文件和脚本翻译表。

TranslationLoader   — 加载 .qm 和 JSON 翻译文件，回退到中文
translate_script_entry — 对 ScriptEntry 应用翻译表，返回新副本
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import QCoreApplication, QTranslator

if TYPE_CHECKING:
    from tod.scripting import ScriptEntry

def qt_format(s: str, *args: object) -> str:
    """Replace Qt ``%1``, ``%2``, … placeholders with positional arguments.

    PyQt6 ``tr()`` returns a plain Python ``str`` which lacks C++ Qt's
    ``QString.arg()`` method.  This helper bridges that gap so that
    translatable strings can use the standard Qt placeholder syntax.
    """
    for i, arg in enumerate(args, start=1):
        s = s.replace(f"%{i}", str(arg))
    return s

class TranslationLoader:
    """加载并管理 GUI 翻译文件和脚本翻译表。"""

    def __init__(self, i18n_dir: str | Path, app: QCoreApplication):
        self._i18n_dir = Path(i18n_dir)
        self._app = app
        self._translator: QTranslator | None = None
        self._script_translations: dict = {}
        self._language: str = "zh"

    @property
    def language(self) -> str:
        return self._language

    @property
    def script_translations(self) -> dict:
        return self._script_translations

    def load(self, language: str) -> bool:
        self._language = language
        if language == "zh":
            return self._load_chinese()
        return self._load_translated(language)

    def _load_chinese(self) -> bool:
        if self._translator is not None:
            self._app.removeTranslator(self._translator)
            self._translator = None
        self._script_translations = {}
        return True

    def _load_translated(self, language: str) -> bool:
        qm_path = self._i18n_dir / f"gui.{language}.qm"
        translator = QTranslator()
        if qm_path.exists() and translator.load(str(qm_path)):
            self._app.installTranslator(translator)
            if self._translator is not None:
                self._app.removeTranslator(self._translator)
            self._translator = translator

        json_path = self._i18n_dir / f"scripts.{language}.json"
        if json_path.exists():
            self._script_translations = json.loads(json_path.read_text(encoding="utf-8"))
        else:
            self._script_translations = {}
        return True

def translate_script_entry(entry: ScriptEntry, translations: dict) -> ScriptEntry:
    """对 ScriptEntry 应用翻译表，返回新副本（不可变更新）。

    翻译缺失时保持原中文文本。
    """
    t = translations.get(entry.name, {})
    if not t:
        return entry

    desc = t.get("description", entry.description)
    group_label = t.get("group_label", entry.group_label)

    cli_t = t.get("cli_params", {})
    new_cli = [
        _translate_cli_param(p, cli_t) for p in entry.cli_params
    ]

    env_t = t.get("env_params", {})
    new_env = {
        k: _translate_env_param(v, env_t) for k, v in entry.env_params.items()
    }

    return replace(
        entry,
        description=desc,
        group_label=group_label,
        cli_params=new_cli,
        env_params=new_env,
    )

def _translate_cli_param(param, cli_t: dict):
    """对单个 CliParam 应用翻译。"""
    p = cli_t.get(param.flag, {})
    if not p:
        return param
    updates = {}
    if "label" in p:
        updates["label"] = p["label"]
    if "help" in p:
        updates["help"] = p["help"]
    return replace(param, **updates) if updates else param

def _translate_env_param(param, env_t: dict):
    """对单个 EnvParam 应用翻译。"""
    p = env_t.get(param.env_var, {})
    if not p:
        return param
    updates = {}
    if "label" in p:
        updates["label"] = p["label"]
    return replace(param, **updates) if updates else param
