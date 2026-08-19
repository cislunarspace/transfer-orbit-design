"""tests for MainWindow catalog 集成（issue #375：清单 / 懒加载 / 完成回调）。"""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest

from src.engine.facade_bridge import OrbitDesignResultData


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


_RNG = np.random.default_rng(seed=42)


class _StubCatalog:
    """CatalogService 桩：清单 / 懒加载全在内存，不触真实库。

    all_artifacts 模拟全库（未过滤查询）；未设置时与过滤视图一致。
    """

    def __init__(self, artifacts=None, records=None, all_artifacts=None) -> None:
        self.artifacts = list(artifacts or [])
        self.all_artifacts = all_artifacts
        self.records = records or {}
        self.calls: list = []

    def query_artifacts(self, filters=None):
        self.calls.append(("query", filters))
        if filters is None and self.all_artifacts is not None:
            return list(self.all_artifacts)
        return list(self.artifacts)

    def load_arrays(self, artifact):
        self.calls.append(("load", artifact.record_id))
        stored = self.records.get(artifact.record_id)
        if stored is None:
            return False
        artifact.state_data = stored["states"]
        artifact.times = stored["times"]
        artifact.extra.update(stored.get("extra", {}))
        return True

    def tag(self, record_id, tags, note=None):
        self.calls.append(("tag", record_id, tags, note))

    def delete(self, record_id):
        self.calls.append(("delete", record_id))

    def promote_member(self, record_id, member_index):
        self.calls.append(("promote", record_id, member_index))
        return "rec-promoted"

    def export(self, filters, dest):
        self.calls.append(("export", filters, dest))
        return 2


def _make_window(qapp, catalog):
    from src.app.main_window import MainWindow

    with patch("src.app.main_window.discover_artifacts", return_value=[]):
        return MainWindow(catalog=catalog)


def _make_result_data(record_id: str | None = None) -> OrbitDesignResultData:
    n = 50
    return OrbitDesignResultData(
        orbit_type="DRO",
        epoch_utc="2024-01-01T00:00:00",
        duration_day=365.25,
        initial_state=np.zeros(6),
        cr3bp_jacobi=3.0058,
        states=_RNG.standard_normal((n, 6)),
        times=np.linspace(0, 365.25, n),
        correction_converged=True,
        correction_iterations=3,
        record_id=record_id,
    )


def _catalog_artifact(record_id: str, artifact_type: str = "orbit"):
    """构造 record_to_artifact 形态的清单 Artifact（无数组段）。"""
    from datetime import UTC, datetime

    from src.model.artifact import Artifact

    return Artifact(
        artifact_id=record_id,
        record_id=record_id,
        artifact_type=artifact_type,
        label=f"Halo (L2, C_J=3.0500)",
        orbit_type="Halo",
        source_tool="design_orbit" if artifact_type == "orbit" else "control_orbit",
        created_at=datetime.now(UTC),
        extra={
            "record_id": record_id,
            "source_record_id": None,
            "orbit_family": "halo",
            "libration_point": 2,
            "jacobi": [3.05, 3.05],
            "amplitude": None,
            "has_cr3bp": artifact_type == "orbit",
            "has_ephemeris": True,
            "member_count": 1,
            "tags": [],
            "note": "",
        },
    )


class TestInitReloadsFromCatalog:
    def test_init_queries_catalog(self, qapp):
        """启动恢复：清单经 catalog_query 重建（不再扫描 output/ 文件名分类）。"""
        catalog = _StubCatalog(artifacts=[_catalog_artifact("rec-1")])
        window = _make_window(qapp, catalog)
        assert ("query", {}) in catalog.calls
        assert [a.artifact_id for a in window._project.artifacts] == ["rec-1"]

    def test_query_failure_shows_status_not_crash(self, qapp):
        class _Broken:
            def query_artifacts(self, filters=None):
                raise RuntimeError("库目录不可读")

        from src.app.main_window import MainWindow

        with (
            patch("src.app.main_window.discover_artifacts", return_value=[]),
            patch("src.app.main_window.CatalogService") as svc_cls,
        ):
            svc_cls.return_value = _Broken()
            window = MainWindow()
        assert "读取轨道库失败" in window._status_bar.currentMessage()


class TestOnDesignFinished:
    def test_reloads_and_selects_new_record(self, qapp):
        """设计完成：产物已入库，重查清单并选中新记录（不经手写落盘）。"""
        catalog = _StubCatalog(artifacts=[_catalog_artifact("rec-new")])
        catalog.records["rec-new"] = {
            "states": np.zeros((50, 6)),
            "times": np.linspace(0, 1, 50),
        }
        window = _make_window(qapp, catalog)

        window._on_design_finished(_make_result_data(record_id="rec-new"))

        assert window._selected_artifact_ids == ["rec-new"]
        artifact = window._project.get_by_id("rec-new")
        assert artifact is not None
        assert artifact.state_data is not None  # 懒加载已填充
        assert "设计完成" in window._status_bar.currentMessage()

    def test_record_not_yet_in_catalog_logs_fallback(self, qapp):
        """record_id 不在清单（如入库异步可见前）时不选中，日志说明。"""
        catalog = _StubCatalog(artifacts=[])
        window = _make_window(qapp, catalog)

        window._on_design_finished(_make_result_data(record_id="rec-missing"))

        assert window._selected_artifact_ids == []
        assert window._project.get_by_id("rec-missing") is None


class TestLazyLoadOnSelect:
    def test_click_triggers_catalog_load_and_render(self, qapp):
        catalog = _StubCatalog(artifacts=[_catalog_artifact("rec-1")])
        catalog.records["rec-1"] = {"states": np.zeros((50, 6)), "times": np.arange(50)}
        window = _make_window(qapp, catalog)
        artifact = window._project.get_by_id("rec-1")
        assert artifact.state_data is None

        with patch.object(window._viz.canvas, "render") as mock_render:
            window._on_artifact_clicked("rec-1")
            mock_render.assert_called_once()

        assert artifact.state_data is not None
        assert artifact.state_data.shape == (50, 6)
        assert artifact.times.shape == (50,)

    def test_load_failure_logs_and_continues(self, qapp):
        catalog = _StubCatalog(artifacts=[_catalog_artifact("rec-gone")])
        window = _make_window(qapp, catalog)

        window._on_artifact_clicked("rec-gone")

        assert "记录数据加载失败" in window._log.toPlainText()


class TestTagPromoteExport:
    def test_tag_requested_saves_and_reselects(self, qapp):
        catalog = _StubCatalog(artifacts=[_catalog_artifact("rec-1")])
        catalog.records["rec-1"] = {"states": np.zeros((5, 6)), "times": np.arange(5)}
        window = _make_window(qapp, catalog)

        window._on_tag_requested("rec-1", ["课程A"], "课堂示例")

        assert ("tag", "rec-1", ["课程A"], "课堂示例") in catalog.calls
        assert window._selected_artifact_ids == ["rec-1"]
        assert "标注已保存" in window._status_bar.currentMessage()

    def test_promote_requested_reloads_and_selects(self, qapp):
        catalog = _StubCatalog(artifacts=[_catalog_artifact("rec-1")])
        window = _make_window(qapp, catalog)

        window._on_promote_requested("rec-1", 3)

        assert ("promote", "rec-1", 3) in catalog.calls
        assert "提升" in window._status_bar.currentMessage()

    def test_export_requested_exports_current_filters(self, qapp, monkeypatch):
        catalog = _StubCatalog(artifacts=[_catalog_artifact("rec-1")])
        window = _make_window(qapp, catalog)
        window._catalog_filters = {"orbit_family": "halo"}

        class _Dlg:
            @staticmethod
            def getSaveFileName(*_args, **_kwargs):
                return "/tmp/cases.zip", "案例包 zip (*.zip)"

        with patch("src.app.main_window.QFileDialog", _Dlg):
            window._on_export_requested()

        assert ("export", {"orbit_family": "halo"}, "/tmp/cases.zip") in catalog.calls
        assert "已导出 2 条记录" in window._status_bar.currentMessage()


class TestDeleteArtifacts:
    def test_delete_record_backed_asks_and_deletes(self, qapp):
        """库记录删除前弹确认；确认后走 catalog_delete 并重查清单。"""
        from PyQt6.QtWidgets import QMessageBox

        catalog = _StubCatalog(artifacts=[_catalog_artifact("rec-1")])
        window = _make_window(qapp, catalog)

        with patch("PyQt6.QtWidgets.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
            window._delete_artifacts(["rec-1"])

        assert ("delete", "rec-1") in catalog.calls

    def test_delete_record_backed_cancelled(self, qapp):
        """确认框选"否"时不删除。"""
        from PyQt6.QtWidgets import QMessageBox

        catalog = _StubCatalog(artifacts=[_catalog_artifact("rec-1")])
        window = _make_window(qapp, catalog)

        with patch("PyQt6.QtWidgets.QMessageBox.question", return_value=QMessageBox.StandardButton.No):
            window._delete_artifacts(["rec-1"])

        assert ("delete", "rec-1") not in catalog.calls

    def test_delete_legacy_artifact_no_prompt(self, qapp):
        """遗留分区（非库记录）删除不弹确认，仅移出内存。"""
        from src.model.artifact import Artifact

        catalog = _StubCatalog()
        window = _make_window(qapp, catalog)
        legacy = Artifact(artifact_type="transfer", label="corrected_transfer_001")
        window._project.add(legacy)
        window._legacy_artifacts.append(legacy)

        with patch("PyQt6.QtWidgets.QMessageBox.question") as mock_question:
            window._delete_artifacts([legacy.artifact_id])

        mock_question.assert_not_called()
        assert window._project.get_by_id(legacy.artifact_id) is None
        assert ("delete", legacy.artifact_id) not in catalog.calls


class TestLineageUnderFilter:
    """issue #375 US6：断链按全库判定，过滤把上游筛出清单不算断链。"""

    def test_filtered_out_upstream_not_marked_broken(self, qapp):
        upstream = _catalog_artifact("rec-src")
        downstream = _catalog_artifact("rec-ctl", artifact_type="ephemeris")
        downstream.extra["source_record_id"] = "rec-src"
        downstream.extra["has_cr3bp"] = False

        # 当前过滤视图只剩下游；全库（未过滤）两条都在
        catalog = _StubCatalog(artifacts=[downstream], all_artifacts=[upstream, downstream])
        window = _make_window(qapp, catalog)
        window._catalog_filters = {"has_ephemeris": True}
        window._reload_from_catalog()

        assert window._project.known_record_ids == {"rec-src", "rec-ctl"}
        assert window._project.has_broken_lineage(downstream) is False

    def test_deleted_upstream_marked_broken(self, qapp):
        downstream = _catalog_artifact("rec-ctl", artifact_type="ephemeris")
        downstream.extra["source_record_id"] = "rec-gone"

        catalog = _StubCatalog(artifacts=[downstream])
        window = _make_window(qapp, catalog)
        window._reload_from_catalog()

        assert window._project.has_broken_lineage(downstream) is True
