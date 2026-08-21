"""tests for 项目树右键上下文菜单 + MainWindow 动作分发（issue #340）。"""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest


@pytest.fixture()
def qapp():
    try:
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app
    except ImportError:
        pytest.skip("QApplication 不可用")


def _make_window(qapp):
    """创建 MainWindow，mock 掉 discover_artifacts 避免扫描真实 output/。"""
    from src.app.main_window import MainWindow

    with patch("src.app.main_window.discover_artifacts", return_value=[]):
        return MainWindow()


def _add_artifact(window, *, artifact_type="orbit", label="A"):
    from src.model import Artifact

    artifact = Artifact(
        artifact_id=label,
        artifact_type=artifact_type,
        label=label,
        state_data=np.zeros((6, 6)),
        times=np.linspace(0, 1, 6),
        extra={"mu": 0.0123},
    )
    window._project.add(artifact)
    return artifact


# -- ProjectTreeView 菜单构建 -----------------------------------------------


def _make_view(project):
    from src.view.project_tree import ProjectTreeView

    view = ProjectTreeView()
    view.refresh(project)
    return view


def test_refresh_builds_id_to_type_map(qapp):
    from src.model import Artifact, Project

    proj = Project(name="t")
    proj.add(Artifact(artifact_id="o1", artifact_type="orbit", label="o1"))
    proj.add(Artifact(artifact_id="e1", artifact_type="ephemeris", label="e1"))
    view = _make_view(proj)

    assert view._id_to_type == {"o1": "orbit", "e1": "ephemeris"}


def test_orbit_menu_control_enabled_others_disabled(qapp):
    from PyQt6.QtWidgets import QMenu

    from src.model import Artifact

    view = _make_view(_project_with(Artifact(artifact_id="o1", artifact_type="orbit")))

    menu = QMenu()
    view._populate_type_actions(menu, "orbit", ["o1"])
    acts = menu.actions()

    assert [a.text() for a in acts] == ["轨道保持", "生成轨道族", "查看稳定性"]
    assert acts[0].isEnabled() is True  # control_orbit
    assert acts[1].isEnabled() is False  # generate_family 从工具选择器进，右键灰显
    assert acts[2].isEnabled() is True  # analyze_stability 已接入 e2m2e


def test_ephemeris_menu_has_control_entry(qapp):
    """星历产物右键也有轨道保持入口（链式站保，与 orbit 同一弹窗）。"""
    from PyQt6.QtWidgets import QMenu

    view = _make_view(_project_with())

    menu = QMenu()
    view._populate_type_actions(menu, "ephemeris", ["e1"])
    acts = menu.actions()

    assert [a.text() for a in acts] == ["轨道保持"]
    assert acts[0].isEnabled() is True


def test_family_menu_single_disabled_item(qapp):
    from PyQt6.QtWidgets import QMenu

    from src.model import Artifact

    view = _make_view(_project_with(Artifact(artifact_id="f1", artifact_type="family", label="f1")))

    menu = QMenu()
    view._populate_type_actions(menu, "family", ["f1"])
    acts = menu.actions()

    assert [a.text() for a in acts] == ["展开/折叠成员"]
    assert acts[0].isEnabled() is False


def test_transfer_menu_optimize_disabled(qapp):
    from PyQt6.QtWidgets import QMenu

    from src.model import Artifact

    view = _make_view(
        _project_with(Artifact(artifact_id="t1", artifact_type="transfer", label="t1"))
    )

    menu = QMenu()
    view._populate_type_actions(menu, "transfer", ["t1"])
    acts = menu.actions()

    assert [a.text() for a in acts] == ["优化"]
    assert acts[0].isEnabled() is False


def test_ephemeris_has_no_type_actions(qapp):
    """星历产物仅有轨道保持入口（站保链式），无生成族/稳定性等轨道动作。"""
    from PyQt6.QtWidgets import QMenu

    from src.model import Artifact

    view = _make_view(
        _project_with(Artifact(artifact_id="e1", artifact_type="ephemeris", label="e1"))
    )

    menu = QMenu()
    view._populate_type_actions(menu, "ephemeris", ["e1"])

    assert [a.text() for a in menu.actions()] == ["轨道保持"]


def _project_with(*artifacts):
    from src.model import Project

    proj = Project(name="t")
    for a in artifacts:
        proj.add(a)
    return proj


# -- MainWindow 动作分发 ----------------------------------------------------


def test_delete_removes_artifact_clears_selection_and_refreshes_tree(qapp):
    window = _make_window(qapp)
    a = _add_artifact(window, artifact_type="orbit", label="del1")
    window._refresh_project_tree()
    window._selected_artifact_ids = [a.artifact_id]

    window._on_context_action("delete", [a.artifact_id])

    assert window._project.get_by_id(a.artifact_id) is None
    assert a.artifact_id not in window._selected_artifact_ids
    assert a.artifact_id not in window._tree_view._id_to_type


def test_delete_multiple_artifacts(qapp):
    window = _make_window(qapp)
    a1 = _add_artifact(window, label="m1")
    a2 = _add_artifact(window, label="m2")
    window._refresh_project_tree()

    window._on_context_action("delete", [a1.artifact_id, a2.artifact_id])

    assert window._project.get_by_id(a1.artifact_id) is None
    assert window._project.get_by_id(a2.artifact_id) is None


def test_control_orbit_action_selects_orbit_and_opens_dialog(qapp):
    """右键轨道保持：选中该 Artifact 并弹 ControlOrbitDialog（patch exec 防阻塞）。"""
    window = _make_window(qapp)
    a = _add_artifact(window, artifact_type="orbit", label="co1")
    window._refresh_project_tree()

    with patch("src.view.control_orbit_dialog.ControlOrbitDialog.exec", return_value=0):
        window._on_context_action("control_orbit", [a.artifact_id])

    assert window._selected_artifact_ids == [a.artifact_id]


def test_control_orbit_action_opens_dialog_for_ephemeris(qapp):
    """星历产物（站保结果）也可作输入：链式站保。"""
    window = _make_window(qapp)
    a = _add_artifact(window, artifact_type="ephemeris", label="eph1")
    window._refresh_project_tree()

    with patch("src.view.control_orbit_dialog.ControlOrbitDialog.exec", return_value=0):
        window._on_context_action("control_orbit", [a.artifact_id])

    assert window._selected_artifact_ids == [a.artifact_id]


def test_control_orbit_action_ignores_non_controllable(qapp):
    window = _make_window(qapp)
    a = _add_artifact(window, artifact_type="family", label="fam1")
    window._refresh_project_tree()
    window._selected_artifact_ids = []

    window._on_context_action("control_orbit", [a.artifact_id])

    assert window._selected_artifact_ids == []


def test_unknown_action_does_not_crash(qapp):
    window = _make_window(qapp)
    window._on_context_action("nonexistent", ["x"])  # 静默忽略，不抛异常
