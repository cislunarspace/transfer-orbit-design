"""GUI 首次启动的 SPICE 内核引导。

e2m2e 的 SPICE 内核不随 pip 包分发，需用户自行准备。本模块在应用启动时
探测可用内核目录（``src.commons.paths.detect_kernel_dir`` + 完整性判断），
缺失则弹窗引导：

- **下载内核**：后台线程从 e2m2e ``kernels-v1`` release 下载到用户数据
  目录（``src.commons.kernels.user_kernel_dir``），进度条显示，可取消
  （已下载文件保留，重试幂等续传）；
- **指定已有目录**：文件选择对话框选目录，校验含必需内核后写入配置
  （``src.commons.paths.save_configured_kernel_dir``），下次启动自动探测；
- **暂时跳过**：本次不准备，轨道设计/星历/时间转换用时再报错。

调用方：``src.app.main``（必须在 import e2m2e 之前把返回目录写入
``SPICE_KERNEL_DIR``）。
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QProgressDialog, QWidget

from src.commons import kernels
from src.commons.paths import detect_kernel_dir, save_configured_kernel_dir


class _Cancelled(Exception):
    """用户取消下载。"""


class _DownloadWorker(QThread):
    """后台下载线程：进度经信号上报，支持取消（当前文件下载完即停）。"""

    progress = pyqtSignal(int, int, str)  # done, total, name
    done = pyqtSignal(bool, str)  # ok, message

    def __init__(self, kernel_dir: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._kernel_dir = kernel_dir
        self.ok = False
        self.cancelled = False
        self.message = ""

    def run(self) -> None:
        def on_progress(done: int, total: int, name: str) -> None:
            self.progress.emit(done, total, name)
            if self.isInterruptionRequested():
                raise _Cancelled()

        try:
            fetched, skipped = kernels.download_kernels(self._kernel_dir, on_progress)
            self.ok = kernels.kernel_dir_usable(self._kernel_dir)
            if self.ok:
                self.message = f"下载完成：新增 {fetched} 个，已有 {skipped} 个"
            else:
                self.message = "下载完成，但目录仍缺必需内核（行星历 .bsp 或闰秒 .tls）"
        except _Cancelled:
            self.cancelled = True
            self.message = "已取消"
        except Exception as exc:  # 网络/磁盘错误
            self.ok = False
            self.message = str(exc)
        self.done.emit(self.ok, self.message)


def _download_and_wait(parent: QWidget | None) -> str | None:
    """下载到用户数据目录，模态进度对话框等待完成；成功返回目录。"""
    target = kernels.user_kernel_dir()
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        QMessageBox.warning(parent, "无法创建内核目录", f"{target}\n{exc}")
        return None

    dlg = QProgressDialog("正在下载 SPICE 内核（kernels-v1）…", "取消", 0, 0, parent)
    dlg.setWindowTitle("下载 SPICE 内核")
    dlg.setMinimumDuration(0)
    dlg.setAutoClose(False)
    dlg.setAutoReset(False)
    dlg.setMinimumWidth(440)

    def _on_progress(done: int, total: int, name: str) -> None:
        dlg.setMaximum(total)
        dlg.setValue(done)
        dlg.setLabelText(f"正在下载 {name}（{done}/{total}）")

    worker = _DownloadWorker(target)
    worker.progress.connect(_on_progress)
    worker.done.connect(dlg.close)
    dlg.canceled.connect(worker.requestInterruption)
    worker.start()
    dlg.exec()  # 模态事件循环；worker 结束后经 done 信号关闭
    worker.wait()  # 取消路径：等当前文件下载完退出

    if worker.ok:
        save_configured_kernel_dir(target)
        QMessageBox.information(parent, "下载完成", f"SPICE 内核已就绪：{target}")
        return str(target)
    if worker.cancelled:
        return None  # 用户取消：静默继续，功能用时再提示
    QMessageBox.warning(
        parent,
        "下载失败",
        f"{worker.message}\n可稍后重试（重复运行会跳过已下载的文件），或指定已有内核目录。",
    )
    return None


def _pick_existing(parent: QWidget | None) -> str | None:
    """让用户指定已有内核目录；校验通过后写入配置并返回。"""
    chosen = QFileDialog.getExistingDirectory(
        parent, "选择 SPICE 内核目录", str(Path.home())
    )
    if not chosen:
        return None
    if not kernels.kernel_dir_usable(chosen):
        QMessageBox.warning(
            parent,
            "目录不可用",
            f"所选目录缺少必需内核（行星历 .bsp 与闰秒 .tls）：\n{chosen}",
        )
        return None
    save_configured_kernel_dir(chosen)
    return chosen


def ensure_kernels(parent: QWidget | None = None) -> str | None:
    """确保可用内核目录就绪；返回可用目录，用户跳过时返回 None。

    探测到可用内核目录（环境变量/配置/仓库/用户数据目录任一）直接返回，
    否则弹窗引导下载或指定已有目录。
    """
    detected = detect_kernel_dir()
    if detected and kernels.kernel_dir_usable(detected):
        return detected

    box = QMessageBox(parent)
    box.setWindowTitle("SPICE 内核缺失")
    box.setIcon(QMessageBox.Icon.Warning)
    box.setText("轨道设计需要 NASA SPICE 内核（行星历 + 闰秒，约 200 MB）。")
    box.setInformativeText(
        "未找到可用内核，轨道设计、星历与时间转换将不可用。"
        "可以现在从 e2m2e kernels-v1 release 下载，或指定已有内核文件的目录。"
    )
    btn_download = box.addButton("下载内核", QMessageBox.ButtonRole.AcceptRole)
    btn_browse = box.addButton("指定已有目录", QMessageBox.ButtonRole.ActionRole)
    box.addButton("暂时跳过", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(btn_download)
    box.exec()

    clicked = box.clickedButton()
    if clicked is btn_download:
        return _download_and_wait(parent)
    if clicked is btn_browse:
        return _pick_existing(parent)
    return None
