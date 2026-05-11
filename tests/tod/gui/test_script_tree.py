from pathlib import Path

from tod.gui.script_registry import ScriptEntry
from tod.gui.script_tree import EMPTY_FOLDER_COLOR, TreeNode, build_tree_from_scripts


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")


def test_tree_node_represents_folder_script_and_empty_folder() -> None:
    entry = ScriptEntry(
        "dro",
        "generate_dro",
        "",
        "tod/generates/cr3bp/dro/generate_dro.py",
    )

    script = TreeNode(
        name="generate_dro",
        path=entry.script_path,
        node_type="script",
        color="#4A90D9",
        script_entry=entry,
    )
    folder = TreeNode(
        name="dro",
        path="tod/generates/cr3bp/dro",
        node_type="folder",
        color="#4A90D9",
        children=[script],
    )
    empty = TreeNode(
        name="empty",
        path="tod/generates/cr3bp/empty",
        node_type="empty_folder",
        color=EMPTY_FOLDER_COLOR,
    )

    assert folder.children == [script]
    assert script.script_entry is entry
    assert empty.children == []


def test_build_tree_from_scripts_parses_registry_order_and_empty_dirs(tmp_path, monkeypatch) -> None:
    root = tmp_path
    _touch(root / "tod/generates/cr3bp/dro/generate_dro.py")
    _touch(root / "tod/transfers/dro_to_ro/grid_search.py")
    (root / "tod/generates/cr3bp/unused").mkdir(parents=True)

    from tod.gui import script_tree

    monkeypatch.setattr(script_tree, "PROJECT_ROOT", root)

    dro_entry = ScriptEntry(
        "dro",
        "generate_dro",
        "",
        "tod/generates/cr3bp/dro/generate_dro.py",
    )
    transfer_entry = ScriptEntry(
        "transfer",
        "grid_search",
        "",
        "tod/transfers/dro_to_ro/grid_search.py",
    )

    tree = build_tree_from_scripts(
        {
            "Transfer": [transfer_entry],
            "DRO": [dro_entry],
        }
    )

    assert [node.name for node in tree] == ["generates", "transfers"]

    generates = tree[0]
    assert generates.path == "tod/generates"
    assert generates.color == "#4A90D9"
    assert generates.children[0].name == "cr3bp"

    cr3bp = generates.children[0]
    assert [node.name for node in cr3bp.children] == ["dro", "unused"]
    assert cr3bp.children[0].children[0].name == "generate_dro"
    assert cr3bp.children[0].children[0].script_entry is dro_entry

    empty = cr3bp.children[1]
    assert empty.node_type == "empty_folder"
    assert empty.color == EMPTY_FOLDER_COLOR

    transfers = tree[1]
    assert transfers.color == "#E6A23C"
    assert transfers.children[0].name == "dro_to_ro"
    assert transfers.children[0].children[0].name == "grid_search"


def test_build_tree_from_scripts_empty(tmp_path, monkeypatch) -> None:
    """空注册表返回空列表"""
    from tod.gui import script_tree

    monkeypatch.setattr(script_tree, "PROJECT_ROOT", tmp_path)

    tree = build_tree_from_scripts({})

    assert tree == []


def test_build_tree_from_scripts_single(tmp_path, monkeypatch) -> None:
    """单个脚本正确构建单层树"""
    root = tmp_path
    _touch(root / "tod/generates/cr3bp/dro/generate_dro.py")

    from tod.gui import script_tree

    monkeypatch.setattr(script_tree, "PROJECT_ROOT", root)

    entry = ScriptEntry(
        "dro",
        "generate_dro",
        "生成 DRO 轨道",
        "tod/generates/cr3bp/dro/generate_dro.py",
    )

    tree = build_tree_from_scripts({"DRO": [entry]})

    assert len(tree) == 1
    assert tree[0].name == "generates"
    assert tree[0].node_type == "folder"
    assert len(tree[0].children) == 1
    assert tree[0].children[0].name == "cr3bp"
    assert len(tree[0].children[0].children) == 1
    assert tree[0].children[0].children[0].name == "dro"
    assert len(tree[0].children[0].children[0].children) == 1
    script_node = tree[0].children[0].children[0].children[0]
    assert script_node.name == "generate_dro"
    assert script_node.node_type == "script"
    assert script_node.script_entry is entry


def test_build_tree_from_scripts_nested(tmp_path, monkeypatch) -> None:
    """嵌套路径正确构建多层树"""
    root = tmp_path
    _touch(root / "tod/generates/cr3bp/dro/generate_dro.py")
    _touch(root / "tod/generates/cr3bp/halo/generate_halo.py")

    from tod.gui import script_tree

    monkeypatch.setattr(script_tree, "PROJECT_ROOT", root)

    dro_entry = ScriptEntry(
        "dro",
        "generate_dro",
        "生成 DRO 轨道",
        "tod/generates/cr3bp/dro/generate_dro.py",
    )
    halo_entry = ScriptEntry(
        "halo",
        "generate_halo",
        "生成 Halo 轨道",
        "tod/generates/cr3bp/halo/generate_halo.py",
    )

    tree = build_tree_from_scripts({"DRO": [dro_entry], "Halo": [halo_entry]})

    assert len(tree) == 1
    generates = tree[0]
    assert generates.name == "generates"
    cr3bp = generates.children[0]
    assert cr3bp.name == "cr3bp"
    assert len(cr3bp.children) == 2
    dro = cr3bp.children[0]
    halo = cr3bp.children[1]
    assert dro.name == "dro"
    assert halo.name == "halo"
    assert dro.children[0].script_entry is dro_entry
    assert halo.children[0].script_entry is halo_entry


def test_ignore_tod_prefix(tmp_path, monkeypatch) -> None:
    """忽略 tod 前缀，树根从 section 文件夹开始"""
    root = tmp_path
    _touch(root / "tod/generates/cr3bp/dro/generate_dro.py")

    from tod.gui import script_tree

    monkeypatch.setattr(script_tree, "PROJECT_ROOT", root)

    entry = ScriptEntry(
        "dro",
        "generate_dro",
        "",
        "tod/generates/cr3bp/dro/generate_dro.py",
    )

    tree = build_tree_from_scripts({"DRO": [entry]})

    assert len(tree) == 1
    assert tree[0].name == "generates"
    assert tree[0].path == "tod/generates"
    assert all(root_node.name != "tod" for root_node in tree)


def test_ignore_non_tod_paths(tmp_path, monkeypatch) -> None:
    """不含 tod 前缀的路径不生成任何树节点"""
    empty_root = tmp_path / "empty"
    empty_root.mkdir()

    from tod.gui import script_tree

    monkeypatch.setattr(script_tree, "PROJECT_ROOT", empty_root)

    no_tod = ScriptEntry("dro", "bad", "", "other/generates/bad.py")
    tree = build_tree_from_scripts({"BAD": [no_tod]})

    assert tree == []


def test_folder_sorting_filesystem(tmp_path, monkeypatch) -> None:
    """顶层文件夹按文件系统目录顺序排列，不受 SCRIPTS 注册表顺序影响"""
    root = tmp_path
    for path in [
        "tod/generates/cr3bp/dro/generate.py",
        "tod/transfers/dro_to_ro/search.py",
        "tod/plot/dro/plot.py",
    ]:
        _touch(root / path)

    from tod.gui import script_tree

    monkeypatch.setattr(script_tree, "PROJECT_ROOT", root)

    dro = ScriptEntry("dro", "generate", "", "tod/generates/cr3bp/dro/generate.py")
    transfer = ScriptEntry("transfer", "search", "", "tod/transfers/dro_to_ro/search.py")
    plot = ScriptEntry("dro", "plot", "", "tod/plot/dro/plot.py")

    tree = build_tree_from_scripts(
        {"Transfer": [transfer], "Plot": [plot], "DRO": [dro]},
    )

    names = [node.name for node in tree]
    assert "generates" in names
    assert "transfers" in names
    assert "plot" in names


def test_children_sorting_scripts(tmp_path, monkeypatch) -> None:
    """子节点按 SCRIPTS 注册表顺序排列"""
    root = tmp_path
    _touch(root / "tod/generates/cr3bp/dro/second.py")
    _touch(root / "tod/generates/cr3bp/dro/first.py")
    _touch(root / "tod/generates/cr3bp/dro/third.py")

    from tod.gui import script_tree

    monkeypatch.setattr(script_tree, "PROJECT_ROOT", root)

    second = ScriptEntry("dro", "second", "", "tod/generates/cr3bp/dro/second.py")
    first = ScriptEntry("dro", "first", "", "tod/generates/cr3bp/dro/first.py")
    third = ScriptEntry("dro", "third", "", "tod/generates/cr3bp/dro/third.py")

    tree = build_tree_from_scripts(
        {"DRO": [second, first, third]},
    )

    dro = tree[0].children[0].children[0]
    script_names = [child.name for child in dro.children]
    assert script_names == ["second", "first", "third"]


def test_empty_folder_detection(tmp_path, monkeypatch) -> None:
    """空目录（无注册脚本）正确检测为 empty_folder"""
    root = tmp_path
    _touch(root / "tod/generates/cr3bp/dro/generate.py")
    (root / "tod/generates/cr3bp/unused").mkdir(parents=True)

    from tod.gui import script_tree

    monkeypatch.setattr(script_tree, "PROJECT_ROOT", root)

    entry = ScriptEntry("dro", "generate", "", "tod/generates/cr3bp/dro/generate.py")

    tree = build_tree_from_scripts({"DRO": [entry]})

    cr3bp = tree[0].children[0]
    names = [child.name for child in cr3bp.children]
    assert "unused" in names
    unused = next(child for child in cr3bp.children if child.name == "unused")
    assert unused.node_type == "empty_folder"
    assert unused.color == EMPTY_FOLDER_COLOR
    assert unused.children == []


def test_build_tree_from_scripts_limits_folders_to_three_levels_and_keeps_script_order(
    tmp_path,
    monkeypatch,
) -> None:
    root = tmp_path
    _touch(root / "tod/plot/transfer/dro_to_ro/deeper/ignored/plot_b.py")
    _touch(root / "tod/plot/transfer/dro_to_ro/deeper/ignored/plot_a.py")

    from tod.gui import script_tree

    monkeypatch.setattr(script_tree, "PROJECT_ROOT", root)

    second = ScriptEntry(
        "transfer",
        "plot_b",
        "",
        "tod/plot/transfer/dro_to_ro/deeper/ignored/plot_b.py",
    )
    first = ScriptEntry(
        "transfer",
        "plot_a",
        "",
        "tod/plot/transfer/dro_to_ro/deeper/ignored/plot_a.py",
    )

    tree = build_tree_from_scripts({"Transfer": [second, first]})

    assert [node.name for node in tree] == ["plot"]
    transfer = tree[0].children[0]
    dro_to_ro = transfer.children[0]

    assert transfer.name == "transfer"
    assert dro_to_ro.name == "dro_to_ro"
    assert [node.name for node in dro_to_ro.children] == ["plot_b", "plot_a"]
    assert all(node.node_type == "script" for node in dro_to_ro.children)
