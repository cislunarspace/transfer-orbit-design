from PyQt6.QtWidgets import QApplication

from tod.gui.script_registry import ScriptEntry
from tod.gui.script_tree import TreeNode


def _qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        return QApplication([])
    return app


def _script_entry(name: str, path: str) -> ScriptEntry:
    return ScriptEntry("dro", name, "", path)


def _nodes() -> tuple[list[TreeNode], ScriptEntry]:
    entry = _script_entry(
        "generate_dro",
        "tod/generates/cr3bp/dro/generate_dro.py",
    )
    return [
        TreeNode(
            name="generates",
            path="tod/generates",
            node_type="folder",
            color="#4A90D9",
            children=[
                TreeNode(
                    name="generate_dro",
                    path=entry.script_path,
                    node_type="script",
                    color="#4A90D9",
                    script_entry=entry,
                ),
            ],
        ),
    ], entry


def test_sidebar_tree_widget_renders_tree_nodes() -> None:
    _qapp()
    from tod.gui.sidebar_tree import SidebarTreeWidget

    nodes, _entry = _nodes()

    tree = SidebarTreeWidget(nodes)

    assert tree.topLevelItemCount() == 1
    folder = tree.topLevelItem(0)
    assert folder.text(0) == "generates"
    assert folder.childCount() == 1
    assert folder.child(0).text(0) == "generate_dro"


def test_sidebar_tree_widget_defaults_folders_collapsed() -> None:
    _qapp()
    from tod.gui.sidebar_tree import SidebarTreeWidget

    nodes, _entry = _nodes()

    tree = SidebarTreeWidget(nodes)

    assert tree.topLevelItem(0).isExpanded() is False


def test_sidebar_tree_widget_folder_click_toggles_without_script_callback() -> None:
    _qapp()
    from tod.gui.sidebar_tree import SidebarTreeWidget

    nodes, _entry = _nodes()
    selected: list[ScriptEntry] = []
    tree = SidebarTreeWidget(nodes)
    tree.set_script_selected_callback(selected.append)
    folder = tree.topLevelItem(0)

    tree.itemClicked.emit(folder, 0)

    assert folder.isExpanded() is True
    assert selected == []

    tree.itemClicked.emit(folder, 0)

    assert folder.isExpanded() is False
    assert selected == []


def test_sidebar_tree_widget_script_click_calls_callback() -> None:
    _qapp()
    from tod.gui.sidebar_tree import SidebarTreeWidget

    nodes, entry = _nodes()
    selected: list[ScriptEntry] = []
    tree = SidebarTreeWidget(nodes)
    tree.set_script_selected_callback(selected.append)
    script = tree.topLevelItem(0).child(0)

    tree.itemClicked.emit(script, 0)

    assert selected == [entry]


def test_sidebar_tree_widget_expands_and_collapses_all_nodes() -> None:
    _qapp()
    from tod.gui.sidebar_tree import SidebarTreeWidget

    nodes, _entry = _nodes()
    tree = SidebarTreeWidget(nodes)
    folder = tree.topLevelItem(0)

    tree.expand_all()

    assert folder.isExpanded() is True

    tree.collapse_all()

    assert folder.isExpanded() is False
