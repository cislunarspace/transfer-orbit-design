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
