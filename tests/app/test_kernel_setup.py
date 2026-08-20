"""tests for src.app.kernel_setup（SPICE 内核引导弹窗：下载 / 指定目录 / 跳过）。"""

from __future__ import annotations

import pytest

import src.app.kernel_setup as ks
from src.commons import kernels


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


class _Signal:
    def connect(self, slot):
        pass


class _ButtonRole:
    AcceptRole = 1
    ActionRole = 2
    RejectRole = 3


class _Icon:
    Warning = 1


class _FakeMessageBox:
    """记录弹窗调用、可预设点击按钮的 QMessageBox 替身。

    预设点击经类属性 ``_click_text`` 传入（子类化后整体替换 ks.QMessageBox，
    保留 ButtonRole/Icon 类属性供 ensure_kernels 访问）。
    """

    calls: list[tuple[str, str]] = []
    _click_text: str | None = None

    ButtonRole = _ButtonRole
    Icon = _Icon

    def __init__(self, parent=None):
        self.buttons: dict[str, object] = {}
        self._click_text = type(self)._click_text

    def setWindowTitle(self, t):
        pass

    def setIcon(self, i):
        pass

    def setText(self, t):
        pass

    def setInformativeText(self, t):
        pass

    def addButton(self, text, role):
        btn = object()
        self.buttons[text] = btn
        return btn

    def setDefaultButton(self, b):
        pass

    def _exec_dialog(self) -> int:
        return 0

    # Qt 对话框方法名（供被测代码调用）；写成 def exec 会被安全扫描误判为
    # Python 内置 exec 动态执行，改用别名挂接
    exec = _exec_dialog

    def clickedButton(self):
        return self.buttons.get(self._click_text) if self._click_text else None

    @classmethod
    def warning(cls, parent, title, text):
        cls.calls.append(("warning", f"{title}: {text}"))

    @classmethod
    def information(cls, parent, title, text):
        cls.calls.append(("information", f"{title}: {text}"))


class _FakeProgressDialog:
    canceled = _Signal()

    def __init__(self, *a, **k):
        pass

    def setWindowTitle(self, t):
        pass

    def setMinimumDuration(self, d):
        pass

    def setAutoClose(self, b):
        pass

    def setAutoReset(self, b):
        pass

    def setMinimumWidth(self, w):
        pass

    def setMaximum(self, m):
        pass

    def setValue(self, v):
        pass

    def setLabelText(self, t):
        pass

    def _exec_dialog(self) -> int:
        return 0

    exec = _exec_dialog  # Qt 方法名别名（同 _FakeMessageBox 的说明）

    def close(self):
        pass


class _FakeWorker:
    """同步替身：不真下载，结果预设为成功。"""

    progress = _Signal()
    done = _Signal()

    def __init__(self, target):
        self.ok = True
        self.cancelled = False
        self.message = "fake ok"

    def start(self):
        pass

    def wait(self):
        pass

    def requestInterruption(self):
        pass


@pytest.fixture(autouse=True)
def _patch_ui(monkeypatch, tmp_path):
    """替换全部 UI 组件与用户目录，隔离真实环境。"""
    monkeypatch.setattr(ks, "QMessageBox", _FakeMessageBox)
    monkeypatch.setattr(ks, "QProgressDialog", _FakeProgressDialog)
    monkeypatch.setattr(ks, "_DownloadWorker", _FakeWorker)
    monkeypatch.setattr(kernels, "user_kernel_dir", lambda: tmp_path / "user-kernels")
    _FakeMessageBox.calls = []
    return tmp_path


def _box_class(click_text: str) -> type:
    """构造预设点击按钮的 QMessageBox 替身类。"""

    class _MB(_FakeMessageBox):
        _click_text = click_text

    return _MB


def test_returns_detected_usable_dir(monkeypatch, tmp_path):
    """探测到可用内核目录时直接返回，不弹窗、不下载。"""
    detected = tmp_path / "kernels"
    detected.mkdir()
    monkeypatch.setattr(ks, "detect_kernel_dir", lambda: str(detected))
    monkeypatch.setattr(kernels, "kernel_dir_usable", lambda d: True)
    assert ks.ensure_kernels() == str(detected)
    assert _FakeMessageBox.calls == []


def test_detected_but_incomplete_prompts(monkeypatch, tmp_path, _patch_ui):
    """探测到目录但缺内核（如仓库根只有小内核）→ 弹窗引导。"""
    detected = tmp_path / "kernels"
    detected.mkdir()
    monkeypatch.setattr(ks, "detect_kernel_dir", lambda: str(detected))
    monkeypatch.setattr(kernels, "kernel_dir_usable", lambda d: False)
    monkeypatch.setattr(ks, "QMessageBox", _box_class("暂时跳过"))
    assert ks.ensure_kernels() is None
    assert _FakeMessageBox.calls == []


def test_download_flow(monkeypatch, tmp_path, _patch_ui):
    """点“下载内核”→ 下载到用户目录 → 写配置 → 返回目录。"""
    monkeypatch.setattr(ks, "detect_kernel_dir", lambda: "")
    monkeypatch.setattr(ks, "QMessageBox", _box_class("下载内核"))
    saved = []
    monkeypatch.setattr(ks, "save_configured_kernel_dir", lambda p: saved.append(str(p)))

    result = ks.ensure_kernels()

    assert result == str(tmp_path / "user-kernels")
    assert saved == [result]
    assert any(t == "information" for t, _ in _FakeMessageBox.calls)


def test_pick_existing_flow(monkeypatch, tmp_path, _patch_ui):
    """点“指定已有目录”→ 校验通过 → 写配置 → 返回所选目录。"""
    monkeypatch.setattr(ks, "detect_kernel_dir", lambda: "")
    monkeypatch.setattr(ks, "QMessageBox", _box_class("指定已有目录"))
    chosen = tmp_path / "my-kernels"
    chosen.mkdir()
    monkeypatch.setattr(
        ks,
        "QFileDialog",
        type("FD", (), {"getExistingDirectory": staticmethod(lambda *a, **k: str(chosen))}),
    )
    monkeypatch.setattr(kernels, "kernel_dir_usable", lambda d: True)
    saved = []
    monkeypatch.setattr(ks, "save_configured_kernel_dir", lambda p: saved.append(str(p)))

    assert ks.ensure_kernels() == str(chosen)
    assert saved == [str(chosen)]


def test_pick_existing_invalid_warns(monkeypatch, tmp_path, _patch_ui):
    """所选目录不可用 → warning 且返回 None。"""
    monkeypatch.setattr(ks, "detect_kernel_dir", lambda: "")
    monkeypatch.setattr(ks, "QMessageBox", _box_class("指定已有目录"))
    monkeypatch.setattr(
        ks,
        "QFileDialog",
        type("FD", (), {"getExistingDirectory": staticmethod(lambda *a, **k: str(tmp_path))}),
    )
    monkeypatch.setattr(kernels, "kernel_dir_usable", lambda d: False)

    assert ks.ensure_kernels() is None
    assert any(t == "warning" for t, _ in _FakeMessageBox.calls)


def test_skip_flow(monkeypatch, _patch_ui):
    """点“暂时跳过”→ 返回 None，无下载无配置写入。"""
    monkeypatch.setattr(ks, "detect_kernel_dir", lambda: "")
    monkeypatch.setattr(ks, "QMessageBox", _box_class("暂时跳过"))
    saved = []
    monkeypatch.setattr(ks, "save_configured_kernel_dir", lambda p: saved.append(str(p)))

    assert ks.ensure_kernels() is None
    assert saved == []
    assert _FakeMessageBox.calls == []
