# pyright: reportArgumentType=false, reportOptionalMemberAccess=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false
"""TranslationLoader 和 translate_script_entry 的单元测试。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from src.app.i18n import TranslationLoader, translate_script_entry


@pytest.fixture
def i18n_dir(tmp_path):
    """创建临时 i18n 目录，含 .qm 和 .json 文件。"""
    d = tmp_path / "i18n"
    d.mkdir()
    return d


class TestTranslationLoader:
    def test_load_chinese_noop(self, i18n_dir):
        """中文模式不应加载任何翻译器。"""
        loader = TranslationLoader(i18n_dir, None)
        assert loader.load("zh") is True
        assert loader.language == "zh"
        assert loader.script_translations == {}
        assert loader._translator is None

    def test_load_missing_translation_falls_back(self, i18n_dir):
        """目标语言文件不存在时，静默回退。"""
        loader = TranslationLoader(i18n_dir, None)
        assert loader.load("en") is True
        assert loader.script_translations == {}

    def test_load_json_translations(self, i18n_dir):
        """加载 JSON 脚本翻译表。"""
        translations = {
            "generate_dro": {
                "description": "Generate DRO orbit family",
                "cli_params": {
                    "--ratio": {"label": "Ratio", "help": "Resonance ratio"},
                },
            }
        }
        (i18n_dir / "scripts.en.json").write_text(
            json.dumps(translations, ensure_ascii=False), encoding="utf-8"
        )

        loader = TranslationLoader(i18n_dir, None)
        loader.load("en")
        assert loader.script_translations == translations

    def test_load_switch_language(self, i18n_dir):
        """切换语言时更新翻译表。"""
        (i18n_dir / "scripts.en.json").write_text(
            json.dumps({"a": {"description": "English"}}), encoding="utf-8"
        )

        loader = TranslationLoader(i18n_dir, None)
        loader.load("en")
        assert loader.script_translations == {"a": {"description": "English"}}

        loader.load("zh")
        assert loader.script_translations == {}


@dataclass(frozen=True)
class _FakeCliParam:
    flag: str
    label: str = ""
    help: str = ""


@dataclass(frozen=True)
class _FakeEntry:
    name: str
    description: str = ""
    group_label: str = ""
    cli_params: list = field(default_factory=list)
    env_params: dict = field(default_factory=dict)


class TestTranslateScriptEntry:
    def test_no_translation_returns_same(self):
        """翻译表中无对应条目时返回原对象。"""
        entry = _FakeEntry(name="test", description="中文描述")
        result = translate_script_entry(entry, {})
        assert result is entry

    def test_description_translated(self):
        """description 字段被正确翻译。"""
        entry = _FakeEntry(name="test", description="中文")
        translations = {"test": {"description": "Chinese"}}
        result = translate_script_entry(entry, translations)
        assert result.description == "Chinese"

    def test_missing_field_keeps_original(self):
        """翻译表中缺少某字段时保持原值。"""
        entry = _FakeEntry(name="test", description="中文", group_label="生成")
        translations = {"test": {"description": "Test"}}
        result = translate_script_entry(entry, translations)
        assert result.description == "Test"
        assert result.group_label == "生成"

    def test_cli_params_translated(self):
        """cli_params 的 label 和 help 被翻译。"""
        entry = _FakeEntry(
            name="test",
            cli_params=[
                _FakeCliParam(flag="--ratio", label="比例", help="共振比"),
            ],
        )
        translations = {
            "test": {
                "cli_params": {
                    "--ratio": {"label": "Ratio", "help": "Resonance ratio"},
                }
            }
        }
        result = translate_script_entry(entry, translations)
        assert result.cli_params[0].label == "Ratio"
        assert result.cli_params[0].help == "Resonance ratio"

    def test_partial_cli_param_translation(self):
        """cli_params 只翻译 label 不翻译 help。"""
        entry = _FakeEntry(
            name="test",
            cli_params=[_FakeCliParam(flag="--x", label="标签", help="帮助")],
        )
        translations = {"test": {"cli_params": {"--x": {"label": "Label"}}}}
        result = translate_script_entry(entry, translations)
        assert result.cli_params[0].label == "Label"
        assert result.cli_params[0].help == "帮助"
