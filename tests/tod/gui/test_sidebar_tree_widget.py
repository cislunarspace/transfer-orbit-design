# pyright: reportArgumentType=false, reportOptionalMemberAccess=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false, reportCallIssue=false, reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false
from PyQt6.QtWidgets import QApplication

from tod.scripting import ScriptEntry
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


def _nested_nodes() -> list[TreeNode]:
    entry1 = _script_entry("generate_dro", "tod/generates/cr3bp/dro/generate_dro.py")
    entry2 = _script_entry("grid_search", "tod/transfers/lyapunov/grid_search.py")
    entry3 = _script_entry("plot_orbit", "tod/plot/halo/plot_orbit.py")
    return [
        TreeNode(
            name="generates",
            path="tod/generates",
            node_type="folder",
            color="#4A90D9",
            children=[
                TreeNode(
                    name="cr3bp",
                    path="tod/generates/cr3bp",
                    node_type="folder",
                    color="#4A90D9",
                    children=[
                        TreeNode(
                            name="dro",
                            path="tod/generates/cr3bp/dro",
                            node_type="folder",
                            color="#4A90D9",
                            children=[
                                TreeNode(
                                    name="generate_dro",
                                    path=entry1.script_path,
                                    node_type="script",
                                    color="#4A90D9",
                                    script_entry=entry1,
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        ),
        TreeNode(
            name="transfers",
            path="tod/transfers",
            node_type="folder",
            color="#E6A23C",
            children=[
                TreeNode(
                    name="lyapunov",
                    path="tod/transfers/lyapunov",
                    node_type="folder",
                    color="#E6A23C",
                    children=[
                        TreeNode(
                            name="grid_search",
                            path=entry2.script_path,
                            node_type="script",
                            color="#E6A23C",
                            script_entry=entry2,
                        ),
                    ],
                ),
            ],
        ),
        TreeNode(
            name="plot",
            path="tod/plot",
            node_type="folder",
            color="#67C23A",
            children=[
                TreeNode(
                    name="halo",
                    path="tod/plot/halo",
                    node_type="folder",
                    color="#67C23A",
                    children=[
                        TreeNode(
                            name="plot_orbit",
                            path=entry3.script_path,
                            node_type="script",
                            color="#67C23A",
                            script_entry=entry3,
                        ),
                    ],
                ),
            ],
        ),
    ]


class TestSidebarSearch:
    """Tests for sidebar search functionality (issue #62)."""

    def test_search_matches_node_name_case_insensitive(self) -> None:
        """Search should find nodes by name regardless of case."""
        _qapp()
        from tod.gui.sidebar_tree import SidebarTreeWidget

        nodes = _nested_nodes()
        tree = SidebarTreeWidget(nodes)

        results = tree.search("GENERATES")

        assert len(results) == 1
        assert results[0].text(0) == "generates"

    def test_search_matches_partial_node_name(self) -> None:
        """Search should find nodes with partial name match."""
        _qapp()
        from tod.gui.sidebar_tree import SidebarTreeWidget

        nodes = _nested_nodes()
        tree = SidebarTreeWidget(nodes)

        results = tree.search("gen")

        assert len(results) == 2
        texts = {r.text(0) for r in results}
        assert "generates" in texts
        assert "生成 DRO 轨道" in texts

    def test_search_matches_script_description(self) -> None:
        """Search should find script nodes by description."""
        _qapp()
        from tod.gui.sidebar_tree import SidebarTreeWidget

        nodes = _nested_nodes()
        tree = SidebarTreeWidget(nodes)

        results = tree.search("轨道")

        assert len(results) == 3
        for result in results:
            assert "轨道" in result.text(0)

    def test_search_auto_expands_matching_parent_nodes(self) -> None:
        """Searching should auto-expand parent nodes containing matches."""
        _qapp()
        from tod.gui.sidebar_tree import SidebarTreeWidget

        nodes = _nested_nodes()
        tree = SidebarTreeWidget(nodes)
        tree.collapse_all()

        tree.search("generate_dro")

        root = tree.topLevelItem(0)
        assert root.isExpanded() is True
        cr3bp = root.child(0)
        assert cr3bp.isExpanded() is True
        dro = cr3bp.child(0)
        assert dro.isExpanded() is True

    def test_search_keeps_matching_branches_expanded(self) -> None:
        """Searching should keep branches with matches expanded."""
        _qapp()
        from tod.gui.sidebar_tree import SidebarTreeWidget

        nodes = _nested_nodes()
        tree = SidebarTreeWidget(nodes)

        tree.search("plot")

        root = tree.topLevelItem(0)
        transfers = tree.topLevelItem(1)
        plot = tree.topLevelItem(2)

        assert root.isExpanded() is False
        assert transfers.isExpanded() is False
        assert plot.isExpanded() is True

    def test_clear_search_restores_original_expand_state(self) -> None:
        """Clearing search should restore the original expand state."""
        _qapp()
        from tod.gui.sidebar_tree import SidebarTreeWidget

        nodes = _nested_nodes()
        tree = SidebarTreeWidget(nodes)

        root = tree.topLevelItem(0)
        root.setExpanded(True)
        cr3bp = root.child(0)
        cr3bp.setExpanded(True)

        tree.search("halo")
        tree.clear_search()

        assert root.isExpanded() is True
        assert cr3bp.isExpanded() is True

    def test_search_with_no_matches_returns_empty(self) -> None:
        """Search with no matches should return empty list."""
        _qapp()
        from tod.gui.sidebar_tree import SidebarTreeWidget

        nodes = _nested_nodes()
        tree = SidebarTreeWidget(nodes)

        results = tree.search("nonexistent")

        assert results == []

    def test_search_highlights_matching_nodes(self) -> None:
        """Search should set highlight role on matching items."""
        _qapp()
        from tod.gui.sidebar_tree import SidebarTreeWidget

        nodes = _nested_nodes()
        tree = SidebarTreeWidget(nodes)

        results = tree.search("plot")

        assert len(results) == 2
        for result in results:
            assert result.data(0, tree._HIGHLIGHT_ROLE) is True

    def test_search_empty_input_restores_full_tree(self) -> None:
        """空输入（clear_search）恢复完整树的展开状态。"""
        _qapp()
        from tod.gui.sidebar_tree import SidebarTreeWidget

        nodes = _nested_nodes()
        tree = SidebarTreeWidget(nodes)

        root = tree.topLevelItem(0)
        root.setExpanded(True)

        tree.search("plot")
        assert root.isExpanded() is False

        tree.clear_search()

        assert root.isExpanded() is True
        assert tree.topLevelItemCount() == 3


class TestSidebarWidget:
    """Tests for the sidebar widget with search bar (issue #62)."""

    def test_sidebar_widget_shows_empty_state_when_no_matches(self) -> None:
        """Sidebar should show empty state message when search has no matches."""
        _qapp()
        from tod.gui.sidebar_widget import SidebarWidget

        widget = SidebarWidget()

        assert widget._empty_label.isHidden() is True

        widget._on_search_text_changed("nonexistent")

        assert widget._empty_label.isHidden() is False
        assert widget._empty_label.text() in {"无匹配结果", "No matching results"}

    def test_sidebar_widget_hides_empty_state_with_matches(self) -> None:
        """Sidebar should hide empty state when search has matches."""
        _qapp()
        from tod.gui.sidebar_widget import SidebarWidget

        widget = SidebarWidget()

        widget._on_search_text_changed("plot")

        assert widget._empty_label.isHidden() is True

    def test_sidebar_widget_hides_empty_state_when_cleared(self) -> None:
        """Sidebar should hide empty state when search is cleared."""
        _qapp()
        from tod.gui.sidebar_widget import SidebarWidget

        widget = SidebarWidget()

        widget._on_search_text_changed("nonexistent")
        assert widget._empty_label.isHidden() is False

        widget._on_search_text_changed("")

        assert widget._empty_label.isHidden() is True
