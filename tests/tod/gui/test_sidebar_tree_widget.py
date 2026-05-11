from PyQt6.QtWidgets import QApplication

from tod.gui.script_registry import ScriptEntry
from tod.gui.script_tree import EMPTY_FOLDER_COLOR, TreeNode

_APP: QApplication | None = None


def _qapp() -> QApplication:
    global _APP
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _APP = app
    return _APP


def _script_entry(name: str, path: str) -> ScriptEntry:
    return ScriptEntry("dro", name, "生成 DRO 轨道", path)


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
    assert folder.child(0).text(0) == "生成 DRO 轨道"


def test_sidebar_tree_widget_adds_color_rail_icons_to_folder_script_and_empty_nodes() -> None:
    _qapp()
    from tod.gui.sidebar_tree import SidebarTreeWidget

    entry = _script_entry(
        "grid_search",
        "tod/transfers/dro_to_ro/grid_search.py",
    )
    nodes = [
        TreeNode(
            name="transfers",
            path="tod/transfers",
            node_type="folder",
            color="#E6A23C",
            children=[
                TreeNode(
                    name="grid_search",
                    path=entry.script_path,
                    node_type="script",
                    color="#E6A23C",
                    script_entry=entry,
                ),
                TreeNode(
                    name="unused",
                    path="tod/transfers/unused",
                    node_type="empty_folder",
                    color=EMPTY_FOLDER_COLOR,
                ),
            ],
        )
    ]

    tree = SidebarTreeWidget(nodes)

    folder = tree.topLevelItem(0)
    script = folder.child(0)
    empty = folder.child(1)

    assert _icon_rail_color(folder) == "#e6a23c"
    assert _icon_rail_color(script) == "#e6a23c"
    assert _icon_rail_color(empty) == "#f56c6c"
    assert not folder.icon(0).isNull()
    assert not script.icon(0).isNull()
    assert not empty.icon(0).isNull()


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


def _icon_rail_color(item) -> str:
    image = item.icon(0).pixmap(24, 18).toImage()
    return image.pixelColor(1, image.height() // 2).name()
