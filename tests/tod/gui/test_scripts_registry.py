"""Tests for tod.gui.scripts._registry scanner."""

import pytest
from pathlib import Path


def test_get_scripts_returns_dict_with_expected_categories(toy_scripts_dir: Path) -> None:
    """get_scripts() 返回的 dict 包含预期的分类键。"""
    from tod.gui.scripts._registry import get_scripts

    SCRIPTS = get_scripts(toy_scripts_dir)

    assert isinstance(SCRIPTS, dict)
    assert set(SCRIPTS.keys()) == {"generates", "plot", "transfer"}


def test_get_scripts_returns_list_of_script_entries(toy_scripts_dir: Path) -> None:
    """get_scripts() 返回的每个分类值是 ScriptEntry 列表。"""
    from tod.gui.scripts._registry import get_scripts
    from tod.gui.scripts._registry import ScriptEntryScan

    SCRIPTS = get_scripts(toy_scripts_dir)

    for category, entries in SCRIPTS.items():
        assert isinstance(entries, list)
        for entry in entries:
            assert isinstance(entry, ScriptEntryScan)


def test_get_scripts_scans_nested_subdirectories(toy_scripts_dir: Path) -> None:
    """扫描器能发现嵌套子目录下的 params 文件。"""
    from tod.gui.scripts._registry import get_scripts

    SCRIPTS = get_scripts(toy_scripts_dir)

    # toy_scripts_dir/generates/cr3bp/dro/generate_dro.py 存在
    entry_names = [e.name for entries in SCRIPTS.values() for e in entries]
    assert "generate_dro" in entry_names


def test_get_scripts_missing_script_entry_raises(invalid_scripts_dir: Path) -> None:
    """扫描到缺 SCRIPT_ENTRY 的 .py 文件时抛出异常。"""
    from tod.gui.scripts._registry import get_scripts

    with pytest.raises(RuntimeError, match="缺少 SCRIPT_ENTRY"):
        get_scripts(invalid_scripts_dir)


def test_iter_script_files_yields_only_python_files(toy_scripts_dir: Path) -> None:
    """iter_script_files 只 yield .py 文件。"""
    from tod.gui.scripts._registry import iter_script_files

    py_files = list(iter_script_files(toy_scripts_dir))

    assert all(p.suffix == ".py" for p in py_files)


def test_iter_script_files_skips_init_and_private(toy_scripts_dir: Path) -> None:
    """iter_script_files 跳过 __init__.py 和以 _ 开头的私有文件。"""
    from tod.gui.scripts._registry import iter_script_files

    py_files = list(iter_script_files(toy_scripts_dir))
    names = [p.name for p in py_files]

    assert "__init__.py" not in names
    assert not any(p.name.startswith("_") for p in py_files if p.name.endswith(".py"))


@pytest.fixture
def toy_scripts_dir(tmp_path: Path, monkeypatch) -> Path:
    """在临时目录创建玩具 scripts 结构用于测试扫描器。"""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()

    # 生成目录结构
    (scripts_dir / "generates").mkdir()
    (scripts_dir / "generates" / "cr3bp").mkdir()
    (scripts_dir / "generates" / "cr3bp" / "dro").mkdir()
    (scripts_dir / "plot").mkdir()
    (scripts_dir / "transfer").mkdir()

    # 有效文件：generates/cr3bp/dro/generate_dro.py
    # 不导入 tod.gui.script_registry，避免触发 scipy 依赖
    (scripts_dir / "generates" / "cr3bp" / "dro" / "generate_dro.py").write_text(
        "from dataclasses import dataclass\n"
        "@dataclass(frozen=True)\n"
        "class _Entry:\n"
        '    module: str; name: str; description: str; script_path: str\n'
        '    output_dir: str | None = None; accepts_file_arg: bool = False\n'
        '    needs_spice: bool = False; env_params = None; cli_params = []\n'
        '    group_label: str = ""\n'
        "SCRIPT_ENTRY = _Entry(\n"
        '    module="dro", name="generate_dro", description="Test",\n'
        '    script_path="tod/generates/cr3bp/dro/generate_dro.py", group_label="生成",\n'
        ")\n", encoding="utf-8"
    )

    # 有效文件：plot/plot_dro.py
    (scripts_dir / "plot" / "plot_dro.py").write_text(
        "from dataclasses import dataclass\n"
        "@dataclass(frozen=True)\n"
        "class _Entry:\n"
        '    module: str; name: str; description: str; script_path: str\n'
        '    output_dir: str | None = None; accepts_file_arg: bool = False\n'
        '    needs_spice: bool = False; env_params = None; cli_params = []\n'
        '    group_label: str = ""\n'
        "SCRIPT_ENTRY = _Entry(\n"
        '    module="dro", name="plot_dro", description="Test",\n'
        '    script_path="tod/plot/dro/plot_dro.py", group_label="绘图",\n'
        ")\n", encoding="utf-8"
    )

    # 有效文件：transfer/dro_to_geo/search.py
    (scripts_dir / "transfer").mkdir(exist_ok=True)
    (scripts_dir / "transfer" / "dro_to_geo").mkdir()
    (scripts_dir / "transfer" / "dro_to_geo" / "search.py").write_text(
        "from dataclasses import dataclass\n"
        "@dataclass(frozen=True)\n"
        "class _Entry:\n"
        '    module: str; name: str; description: str; script_path: str\n'
        '    output_dir: str | None = None; accepts_file_arg: bool = False\n'
        '    needs_spice: bool = False; env_params = None; cli_params = []\n'
        '    group_label: str = ""\n'
        "SCRIPT_ENTRY = _Entry(\n"
        '    module="transfer", name="search", description="Test",\n'
        '    script_path="tod/transfers/dro_to_geo/search.py", group_label="DRO→GEO",\n'
        ")\n", encoding="utf-8"
    )

    # 无效文件隔离在单独子目录，避免污染其他测试
    # 用 _test_invalid/ 前缀（以 _ 开头），扫描器会跳过
    (scripts_dir / "_test_invalid").mkdir()
    (scripts_dir / "_test_invalid" / "no_entry.py").write_text("x = 1\n", encoding="utf-8")

    # __init__.py 应该被跳过
    (scripts_dir / "__init__.py").write_text("", encoding="utf-8")
    (scripts_dir / "generates" / "__init__.py").write_text("", encoding="utf-8")

    # 私有文件应该被跳过
    (scripts_dir / "generates" / "_private.py").write_text(
        "from dataclasses import dataclass\n"
        "@dataclass(frozen=True)\n"
        "class _Entry:\n"
        '    module: str; name: str; description: str; script_path: str\n'
        '    output_dir: str | None = None; accepts_file_arg: bool = False\n'
        '    needs_spice: bool = False; env_params = None; cli_params = []\n'
        '    group_label: str = ""\n'
        "SCRIPT_ENTRY = _Entry(\n"
        '    module="dro", name="private", description="Test",\n'
        '    script_path="dummy.py", group_label="生成",\n'
        ")\n", encoding="utf-8"
    )

    # 将 tmp_path 加入 Python 路径，使 import 生效
    import sys
    monkeypatch.setattr(sys, "path", [str(tmp_path)] + sys.path[:3])

    return scripts_dir


@pytest.fixture
def invalid_scripts_dir(tmp_path: Path, monkeypatch) -> Path:
    """包含无效 params 文件的目录，用于测试强制规范行为。"""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "plot").mkdir()
    # 无效文件：缺 SCRIPT_ENTRY
    (scripts_dir / "plot" / "no_entry.py").write_text("x = 1\n", encoding="utf-8")

    import sys
    monkeypatch.setattr(sys, "path", [str(tmp_path)] + sys.path[:3])

    return scripts_dir
