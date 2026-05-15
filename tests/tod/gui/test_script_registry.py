"""Tests for tod.gui.script_registry."""

from pathlib import Path

import tod
from tod.gui.script_registry import SCRIPTS, UNIT_GROUPS

# Project root: parent of the `tod/` package directory.
PROJECT_ROOT = Path(tod.__file__).resolve().parent.parent


def test_all_registered_script_paths_exist() -> None:
    """Every script_path registered in SCRIPTS must point to a real file."""
    missing: list[str] = []
    for category, entries in SCRIPTS.items():
        for entry in entries:
            full_path = PROJECT_ROOT / entry.script_path
            if not full_path.is_file():
                missing.append(f"[{category}] {entry.name}: {entry.script_path}")

    assert not missing, (
        f"The following registered script paths do not exist on disk:\n"
        + "\n".join(missing)
    )


def test_all_cli_param_unit_groups_are_registered() -> None:
    """每个 CliParam 的 unit_group 都必须存在于 UNIT_GROUPS 中。

    防止注册表里写了 unit_group 但 UNIT_GROUPS 中找不到对应 key，
    导致 GUI 静默跳过单位选择器（参见 dro_to_geo 半径单位 bug）。
    """
    unknown: list[str] = []
    for category, entries in SCRIPTS.items():
        for entry in entries:
            for param in entry.cli_params:
                if param.unit_group is None:
                    continue
                if param.unit_group not in UNIT_GROUPS:
                    unknown.append(
                        f"[{category}] {entry.name} {param.flag}: "
                        f"unit_group={param.unit_group!r} 未在 UNIT_GROUPS 中注册"
                    )

    assert not unknown, "未知的 unit_group:\n" + "\n".join(unknown)


def test_all_cli_param_default_units_are_in_group() -> None:
    """每个 CliParam 的 default_unit 都必须存在于其 unit_group 的单位列表中。"""
    invalid: list[str] = []
    for category, entries in SCRIPTS.items():
        for entry in entries:
            for param in entry.cli_params:
                if param.default_unit is None:
                    continue
                if param.unit_group is None:
                    invalid.append(
                        f"[{category}] {entry.name} {param.flag}: "
                        f"声明了 default_unit={param.default_unit!r} 但 unit_group 为 None"
                    )
                    continue
                group = UNIT_GROUPS.get(param.unit_group)
                if group is None:
                    continue
                if param.default_unit not in group:
                    invalid.append(
                        f"[{category}] {entry.name} {param.flag}: "
                        f"default_unit={param.default_unit!r} 不在 "
                        f"unit_group={param.unit_group!r} 的单位列表 {list(group.keys())} 中"
                    )

    assert not invalid, "无效的 default_unit:\n" + "\n".join(invalid)
