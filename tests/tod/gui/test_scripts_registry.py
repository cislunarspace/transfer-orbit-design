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
    """get_scripts() 返回的每个分类值是 _ScanEntry 列表。"""
    from tod.gui.scripts._registry import _ScanEntry, get_scripts

    SCRIPTS = get_scripts(toy_scripts_dir)

    required_fields = {"module", "name", "description", "script_path"}
    for category, entries in SCRIPTS.items():
        assert isinstance(entries, list), f"{category} value is not a list"
        for entry in entries:
            assert isinstance(entry, _ScanEntry), (
                f"Entry {entry.name!r} is not a _ScanEntry"
            )
            # Duck typing: 验证 entry 有 ScriptEntry 所需的属性
            for field_name in required_fields:
                assert hasattr(entry, field_name), (
                    f"Entry {entry.name!r} missing {field_name}"
                )


def test_get_scripts_scans_nested_subdirectories(toy_scripts_dir: Path) -> None:
    """扫描器能发现嵌套子目录下的 params 文件。"""
    from tod.gui.scripts._registry import get_scripts

    SCRIPTS = get_scripts(toy_scripts_dir)

    # toy_scripts_dir/generates/cr3bp/dro/generate_dro.py 存在
    entry_names = [e.name for entries in SCRIPTS.values() for e in entries]
    assert "generate_dro" in entry_names


def test_get_scripts_missing_script_entry_raises(invalid_scripts_dir: Path) -> None:
    """扫描到缺 SCRIPT_ENTRY 的 .py 文件时跳过该文件（不抛异常）。"""
    from tod.gui.scripts._registry import get_scripts

    # 新行为：没有 SCRIPT_ENTRY 的文件被静默跳过，不会抛异常
    SCRIPTS = get_scripts(invalid_scripts_dir)
    assert isinstance(SCRIPTS, dict)


def test_get_scripts_warns_on_load_failure(tmp_path: Path, caplog) -> None:
    """加载失败的脚本（SyntaxError/ImportError）应记录 WARNING 日志后跳过。"""
    from tod.gui.scripts._registry import get_scripts

    scripts_dir = tmp_path / "scripts"
    (scripts_dir / "plot").mkdir(parents=True)
    # 故意写一个有 ImportError 的脚本
    (scripts_dir / "plot" / "broken.py").write_text(
        "import nonexistent_xyz_module\n",
        encoding="utf-8",
    )

    import logging
    with caplog.at_level(logging.WARNING, logger="tod.gui.scripts._registry"):
        SCRIPTS = get_scripts(scripts_dir)

    # 扫描器不应崩溃
    assert isinstance(SCRIPTS, dict)
    # 应记录 WARNING 日志，包含文件路径
    assert any("broken.py" in record.getMessage() for record in caplog.records), (
        f"期望 WARNING 日志包含 broken.py，实际记录: {[r.getMessage() for r in caplog.records]}"
    )


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


def test_get_scripts_carries_catalog_seed_selector_without_loading_catalog(tmp_path: Path, monkeypatch) -> None:
    """scanner copies lightweight selector metadata without importing catalog loaders."""
    scripts_dir = tmp_path / "scripts"
    script_dir = scripts_dir / "generates" / "cr3bp" / "dro"
    script_dir.mkdir(parents=True)
    (script_dir / "generate_dro.py").write_text(
        "from dataclasses import dataclass, field\n"
        "@dataclass(frozen=True)\n"
        "class ScriptEntry:\n"
        '    module: str\n'
        '    name: str\n'
        '    description: str\n'
        '    script_path: str\n'
        '    output_dir: str | None = None\n'
        '    accepts_file_arg: bool = False\n'
        '    needs_spice: bool = False\n'
        '    cli_chip_params: list = field(default_factory=list)\n'
        '    multi_cli_params: list = field(default_factory=list)\n'
        '    catalog_seed_selectors: list = field(default_factory=list)\n'
        '    env_params: dict = field(default_factory=dict)\n'
        '    cli_params: list = field(default_factory=list)\n'
        '    group_label: str = ""\n'
        "SCRIPT_ENTRY = ScriptEntry(\n"
        '    module="dro", name="generate_dro", description="Test",\n'
        '    script_path="tod/generates/cr3bp/dro/generate_dro.py",\n'
        '    catalog_seed_selectors=[{"key": "dro_catalog_seed", "orbit_type": "dro"}],\n'
        ")\n",
        encoding="utf-8",
    )
    import builtins

    real_import = builtins.__import__

    def guard_import(name, *args, **kwargs):
        if name.startswith("tod.generates.cr3bp.importer"):
            raise AssertionError("scanner must not import catalog loader")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guard_import)

    from tod.gui.scripts._registry import get_scripts

    entry = get_scripts(scripts_dir)["generates"][0]
    assert entry.catalog_seed_selectors == [{"key": "dro_catalog_seed", "orbit_type": "dro"}]


@pytest.fixture
def toy_scripts_dir(tmp_path: Path, monkeypatch) -> Path:
    """在临时目录创建玩具 scripts 结构用于测试扫描器。

    使用 local mock ScriptEntry 而非真实导入，
    因为 tod.gui.script_registry → tod.commons.constants → e2m2e → scipy
    的依赖链在测试环境中可能不可用。
    """
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()

    # 生成目录结构
    (scripts_dir / "generates").mkdir()
    (scripts_dir / "generates" / "cr3bp").mkdir()
    (scripts_dir / "generates" / "cr3bp" / "dro").mkdir()
    (scripts_dir / "plot").mkdir()
    (scripts_dir / "transfer").mkdir()

    # 有效文件：generates/cr3bp/dro/generate_dro.py
    (scripts_dir / "generates" / "cr3bp" / "dro" / "generate_dro.py").write_text(
        "from dataclasses import dataclass, field\n"
        "@dataclass(frozen=True)\n"
        "class ScriptEntry:\n"
        '    module: str\n'
        '    name: str\n'
        '    description: str\n'
        '    script_path: str\n'
        '    output_dir: str | None = None\n'
        '    accepts_file_arg: bool = False\n'
        '    needs_spice: bool = False\n'
        '    cli_chip_params: list = field(default_factory=list)\n'
        '    multi_cli_params: list = field(default_factory=list)\n'
        '    env_params: dict = field(default_factory=dict)\n'
        '    cli_params: list = field(default_factory=list)\n'
        '    group_label: str = ""\n'
        "SCRIPT_ENTRY = ScriptEntry(\n"
        '    module="dro", name="generate_dro", description="Test",\n'
        '    script_path="tod/generates/cr3bp/dro/generate_dro.py", group_label="生成",\n'
        ")\n",
        encoding="utf-8",
    )

    # 有效文件：plot/plot_dro.py
    (scripts_dir / "plot" / "plot_dro.py").write_text(
        "from dataclasses import dataclass, field\n"
        "@dataclass(frozen=True)\n"
        "class ScriptEntry:\n"
        '    module: str\n'
        '    name: str\n'
        '    description: str\n'
        '    script_path: str\n'
        '    output_dir: str | None = None\n'
        '    accepts_file_arg: bool = False\n'
        '    needs_spice: bool = False\n'
        '    cli_chip_params: list = field(default_factory=list)\n'
        '    multi_cli_params: list = field(default_factory=list)\n'
        '    env_params: dict = field(default_factory=dict)\n'
        '    cli_params: list = field(default_factory=list)\n'
        '    group_label: str = ""\n'
        "SCRIPT_ENTRY = ScriptEntry(\n"
        '    module="dro", name="plot_dro", description="Test",\n'
        '    script_path="tod/plot/dro/plot_dro.py", group_label="绘图",\n'
        ")\n",
        encoding="utf-8",
    )

    # 有效文件：transfer/dro_to_geo/search.py
    (scripts_dir / "transfer").mkdir(exist_ok=True)
    (scripts_dir / "transfer" / "dro_to_geo").mkdir()
    (scripts_dir / "transfer" / "dro_to_geo" / "search.py").write_text(
        "from dataclasses import dataclass, field\n"
        "@dataclass(frozen=True)\n"
        "class ScriptEntry:\n"
        '    module: str\n'
        '    name: str\n'
        '    description: str\n'
        '    script_path: str\n'
        '    output_dir: str | None = None\n'
        '    accepts_file_arg: bool = False\n'
        '    needs_spice: bool = False\n'
        '    cli_chip_params: list = field(default_factory=list)\n'
        '    multi_cli_params: list = field(default_factory=list)\n'
        '    env_params: dict = field(default_factory=dict)\n'
        '    cli_params: list = field(default_factory=list)\n'
        '    group_label: str = ""\n'
        "SCRIPT_ENTRY = ScriptEntry(\n"
        '    module="transfer", name="search", description="Test",\n'
        '    script_path="tod/transfers/dro_to_geo/search.py", group_label="DRO→GEO",\n'
        ")\n",
        encoding="utf-8",
    )

    # 无效文件隔离在单独子目录，避免污染其他测试
    (scripts_dir / "_test_invalid").mkdir()
    (scripts_dir / "_test_invalid" / "no_entry.py").write_text("x = 1\n", encoding="utf-8")

    # __init__.py 应该被跳过
    (scripts_dir / "__init__.py").write_text("", encoding="utf-8")
    (scripts_dir / "generates" / "__init__.py").write_text("", encoding="utf-8")

    # 私有文件应该被跳过
    (scripts_dir / "generates" / "_private.py").write_text(
        "from dataclasses import dataclass, field\n"
        "@dataclass(frozen=True)\n"
        "class ScriptEntry:\n"
        '    module: str; name: str; description: str; script_path: str\n'
        '    output_dir: str | None = None; accepts_file_arg: bool = False\n'
        '    needs_spice: bool = False; env_params = None; cli_params = []\n'
        '    group_label: str = ""\n'
        "SCRIPT_ENTRY = ScriptEntry(\n"
        '    module="dro", name="private", description="Test",\n'
        '    script_path="dummy.py", group_label="生成",\n'
        ")\n",
        encoding="utf-8",
    )

    # 将 tmp_path 加入 Python 路径
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
