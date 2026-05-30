"""守护测试：GUI 下拉参数默认值必须与底层脚本 argparse 默认值一致。

根因背景：GUI 仅在「控件值 ≠ GUI 默认值」时才把参数发射到命令行
（``run_mixin._on_run``）。若 GUI 默认值与脚本 argparse 默认值不一致，
用户保持 GUI 默认时该参数被吞掉，脚本回退到自己的 argparse 默认——
导致「GUI 选了 A，脚本却跑了 B」的静默 bug（曾发生在 Halo 的 --method 上）。

本测试遍历所有族生成器 GUI 注册项，对每个下拉参数（choices 非空）
断言 GUI 默认值（经 choice_values 映射到 CLI 值后）等于 argparse 默认值。
"""

from __future__ import annotations

import importlib
import inspect

import pytest

from tod.generates.cr3bp._family_pipeline import FamilyGenerator
from tod.gui.script_registry import SCRIPTS, CliParam, ScriptEntry


def _family_entries() -> list[ScriptEntry]:
    """所有 generate_*_family GUI 注册项。"""
    return [
        e
        for e in SCRIPTS.get("generates", [])
        if e.name.startswith("generate_") and e.name.endswith("_family")
    ]


def _argparse_defaults(entry: ScriptEntry) -> dict[str, object]:
    """构建脚本的 argparse 解析器并返回 {flag: default} 映射。

    通过 script_path 推断模块路径，找到其中的 ``FamilyGenerator`` 子类，
    调用 ``build_parser`` 后解析空参数得到各默认值。
    """
    module_path = entry.script_path.replace("/", ".").removesuffix(".py")
    mod = importlib.import_module(module_path)
    classes = [
        c
        for _, c in inspect.getmembers(mod, inspect.isclass)
        if issubclass(c, FamilyGenerator)
        and c is not FamilyGenerator
        and c.__module__ == mod.__name__
    ]
    if not classes:
        pytest.skip(f"{entry.name}: 未找到 FamilyGenerator 子类")
    parser = classes[0].build_parser("consistency-check")
    ns = parser.parse_args([])
    out: dict[str, object] = {}
    for flag, value in vars(ns).items():
        out["--" + flag.replace("_", "-")] = value
    return out


def _gui_default_cli_value(param: CliParam) -> str:
    """把 GUI 默认值（可能是显示标签）映射为实际 CLI 值。"""
    if param.choice_values and param.default in param.choice_values:
        return param.choice_values[param.default]
    return param.default


@pytest.mark.parametrize("entry", _family_entries(), ids=lambda e: e.name)
def test_dropdown_defaults_match_argparse(entry: ScriptEntry) -> None:
    """每个族脚本：GUI 下拉默认值 == argparse 默认值。"""
    argparse_defaults = _argparse_defaults(entry)

    for param in entry.cli_params:
        if not param.choices:
            continue
        if param.flag not in argparse_defaults:
            # GUI 声明了该下拉参数但脚本没有——也是一种漂移，应当暴露。
            pytest.fail(
                f"{entry.name}: GUI 下拉参数 {param.flag} 在脚本 argparse 中不存在"
            )
        gui_value = _gui_default_cli_value(param)
        argparse_value = str(argparse_defaults[param.flag])
        assert gui_value == argparse_value, (
            f"{entry.name}: {param.flag} 默认值漂移——"
            f"GUI={gui_value!r} 但 argparse={argparse_value!r}。"
            f"GUI 会在用户保持默认时吞掉该参数，导致脚本静默使用 argparse 默认值。"
        )
