"""tests for src.view.catalog_filter_bar -- 多维过滤栏（issue #375，ADR 0009 范式）。"""

from __future__ import annotations

import pytest


@pytest.fixture()
def qapp():
    try:
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app
    except Exception:
        pytest.skip("QApplication 不可用（无 GUI 环境）")


class TestValueDomains:
    """取值域经 e2m2e Pydantic 模型公开接口生成（Field description）。"""

    def test_family_options_from_model_description(self):
        from src.view.catalog_filter_bar import _family_options

        families = _family_options()
        assert "halo" in families
        assert "nrho" in families
        assert "lissajous" in families
        assert all(f == f.lower() for f in families)

    def test_libration_points_from_model_description(self):
        from src.view.catalog_filter_bar import _libration_point_options

        assert _libration_point_options() == [1, 2, 3, 4, 5]


class TestFilters:
    def test_default_no_filters(self, qapp):
        from src.view.catalog_filter_bar import CatalogFilterBar

        bar = CatalogFilterBar()
        assert bar.filters() == {}

    def test_family_and_point_filters(self, qapp):
        from src.view.catalog_filter_bar import CatalogFilterBar

        bar = CatalogFilterBar()
        bar._family_combo.setCurrentText("nrho")
        bar._point_combo.setCurrentText("L2")
        assert bar.filters() == {"orbit_family": "nrho", "libration_point": 2}

    def test_jacobi_range_only_when_checked(self, qapp):
        from src.view.catalog_filter_bar import CatalogFilterBar

        bar = CatalogFilterBar()
        bar._jacobi_min.setValue(3.0)
        assert bar.filters() == {}  # 未勾选不生效
        bar._jacobi_check.setChecked(True)
        bar._jacobi_min.setValue(3.0)
        bar._jacobi_max.setValue(3.1)
        assert bar.filters() == {"jacobi_min": 3.0, "jacobi_max": 3.1}

    def test_amplitude_range(self, qapp):
        from src.view.catalog_filter_bar import CatalogFilterBar

        bar = CatalogFilterBar()
        bar._amplitude_check.setChecked(True)
        bar._amplitude_min.setValue(1000.0)
        bar._amplitude_max.setValue(20000.0)
        assert bar.filters() == {
            "amplitude_min_km": 1000.0,
            "amplitude_max_km": 20000.0,
        }

    def test_segment_presence_tri_state(self, qapp):
        from src.view.catalog_filter_bar import CatalogFilterBar

        bar = CatalogFilterBar()
        bar._cr3bp_combo.setCurrentText("含")
        bar._ephemeris_combo.setCurrentText("含")
        assert bar.filters() == {"has_cr3bp": True, "has_ephemeris": True}
        bar._cr3bp_combo.setCurrentText("不限")
        assert bar.filters() == {"has_ephemeris": True}

    def test_reset_clears_all(self, qapp):
        from src.view.catalog_filter_bar import CatalogFilterBar

        bar = CatalogFilterBar()
        bar._family_combo.setCurrentText("halo")
        bar._jacobi_check.setChecked(True)
        bar._cr3bp_combo.setCurrentText("含")
        bar.reset()
        assert bar.filters() == {}

    def test_filters_changed_signal(self, qapp):
        from src.view.catalog_filter_bar import CatalogFilterBar

        bar = CatalogFilterBar()
        received: list[dict] = []
        bar.filters_changed.connect(received.append)
        bar._family_combo.setCurrentText("halo")
        assert received == [{"orbit_family": "halo"}]

    def test_export_requested_signal(self, qapp):
        from PyQt6.QtWidgets import QPushButton

        from src.view.catalog_filter_bar import CatalogFilterBar

        bar = CatalogFilterBar()
        received: list[bool] = []
        bar.export_requested.connect(lambda: received.append(True))
        export_btn = next(b for b in bar.findChildren(QPushButton) if b.text() == "导出案例包")
        export_btn.click()
        assert received == [True]
