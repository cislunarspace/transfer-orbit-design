"""tests for 紧凑化布局 -- 分栏默认宽度、旧存档迁移、按钮 padding、画布铺满。"""

from __future__ import annotations

from unittest.mock import patch

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


class _StubCatalog:
    """CatalogService 桩：清单查询返回空，不触真实库。"""

    def query_artifacts(self, filters=None):
        return []


def _make_ini_qsettings(tmp_path, name: str = "layout.ini"):
    from PyQt6.QtCore import QSettings

    return QSettings(str(tmp_path / name), QSettings.Format.IniFormat)


def _make_window(qapp, qsettings):
    """构造 MainWindow，把 QSettings 隔离到传入的 ini 实例。"""
    from src.app.main_window import MainWindow

    with (
        patch("PyQt6.QtCore.QSettings", lambda *_a, **_k: qsettings),
        patch("src.app.main_window.discover_artifacts", return_value=[]),
    ):
        return MainWindow(catalog=_StubCatalog())


class TestSplitterDefaults:
    """主分栏默认宽度：右栏容纳最长参数行，左栏收紧，总宽铺满默认窗口。"""

    def test_default_sizes_constants(self):
        from src.app.main_window import _MAIN_SPLITTER_SIZES

        left, center, right = _MAIN_SPLITTER_SIZES
        assert 340 <= right <= 400  # 贴合三列内容宽度：放得下最长行，也不空宽
        assert left <= 260  # 左栏不宽于旧默认
        assert left + center + right + 12 == 1400  # 含 2x6px 分隔条铺满默认窗口

    def test_spinbox_keeps_content_width_when_panel_wide(self, qapp, tmp_path):
        """栏拖宽时多余宽度归标签列，数字框不随栏宽拉长。"""
        qs = _make_ini_qsettings(tmp_path)
        window = _make_window(qapp, qs)
        window.show()
        window.resize(1600, 900)
        qapp.processEvents()

        spin = window._param_widgets.get("duration")
        assert spin is not None  # 默认工具面板应含 duration 字段
        from PyQt6.QtWidgets import QDoubleSpinBox

        assert isinstance(spin, QDoubleSpinBox)
        assert spin.width() <= 130  # 无 maxWidth 时会超过 200

    def test_param_panel_no_horizontal_scroll(self, qapp, tmp_path):
        """默认栏宽下参数面板不出现横向滚动（此前被宽容器顶到 680px）。"""
        qs = _make_ini_qsettings(tmp_path)
        window = _make_window(qapp, qs)
        window.show()
        qapp.processEvents()

        assert window._param_scroll.horizontalScrollBar().maximum() == 0

    def test_fresh_install_writes_defaults_version(self, qapp, tmp_path):
        qs = _make_ini_qsettings(tmp_path)
        window = _make_window(qapp, qs)

        from src.app.main_window import _SPLITTER_DEFAULTS_VERSION

        assert window._qsettings.value("ui/splitter/defaults_version", 0, type=int) == (
            _SPLITTER_DEFAULTS_VERSION
        )


class TestSplitterMigration:
    """默认值升版后，按旧默认拖出的存档被丢弃，新默认生效。"""

    def test_v1_saved_state_discarded(self, qapp, tmp_path):
        from PyQt6.QtCore import QByteArray

        from src.app.main_window import _SPLITTER_DEFAULTS_VERSION

        qs = _make_ini_qsettings(tmp_path)
        qs.setValue("ui/splitter/main", QByteArray(b"stale-bytes"))
        qs.setValue("ui/splitter/center", QByteArray(b"stale-bytes"))
        qs.setValue("ui/splitter/defaults_version", 1)
        qs.sync()

        _make_window(qapp, qs)

        assert qs.value("ui/splitter/main") is None
        assert qs.value("ui/splitter/center") is None
        assert qs.value("ui/splitter/defaults_version", 0, type=int) == _SPLITTER_DEFAULTS_VERSION

    def test_legacy_saved_state_without_version_discarded(self, qapp, tmp_path):
        """#378 时代的存档没有版本键，同样按旧档迁移丢弃。"""
        from PyQt6.QtCore import QByteArray

        qs = _make_ini_qsettings(tmp_path)
        qs.setValue("ui/splitter/main", QByteArray(b"legacy"))
        qs.sync()

        _make_window(qapp, qs)

        assert qs.value("ui/splitter/main") is None

    def test_current_version_kept(self, qapp, tmp_path):
        """已是当前版本的存档不丢（用户拖动位置仍被尊重）。"""
        from PyQt6.QtCore import QByteArray

        from src.app.main_window import _SPLITTER_DEFAULTS_VERSION

        qs = _make_ini_qsettings(tmp_path)
        qs.setValue("ui/splitter/main", QByteArray(b"fresh"))
        qs.setValue("ui/splitter/defaults_version", _SPLITTER_DEFAULTS_VERSION)
        qs.sync()

        _make_window(qapp, qs)

        saved = qs.value("ui/splitter/main")
        assert isinstance(saved, QByteArray) and saved.data() == b"fresh"


class TestCompactStylesheet:
    """全局 QSS：两主题统一紧凑按钮 padding。"""

    def test_both_themes_compact_button_padding(self, qapp):
        from src.view.ui_settings import build_app_stylesheet

        for theme in ("light", "dark"):
            assert "padding: 2px 8px" in build_app_stylesheet(theme)


class TestCanvasFillsPanel:
    """画布随中栏拉伸铺满（不再固定 800x600 居中留白）。"""

    def test_canvas_stretches_to_panel_width(self, qapp):
        from src.view.canvas import OrbitCanvasWithToolbar

        viz = OrbitCanvasWithToolbar()
        # 未 show 的 widget Qt 不执行布局，需 show 后断言拉伸生效
        viz.widget.show()
        viz.widget.resize(1000, 700)
        qapp.processEvents()

        assert viz.canvas.width() >= viz.widget.width() - 20

    def test_nav_toolbar_icon_compact(self, qapp):
        from src.view.canvas import OrbitCanvasWithToolbar

        viz = OrbitCanvasWithToolbar()
        assert viz.toolbar.iconSize().width() == 16
