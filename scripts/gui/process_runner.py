"""进程运行器 — 封装 QProcess，管理脚本子进程。"""

from __future__ import annotations

from PyQt6.QtCore import QObject, QProcess, QTimer, pyqtSignal

from scripts.gui.script_registry import ScriptEntry

_KILL_TIMEOUT_MS = 3000


class ScriptRunner(QObject):
    """管理单个脚本子进程的生命周期和输出。"""

    output_received = pyqtSignal(str)          # 输出文本
    script_started = pyqtSignal(str)           # 脚本名称
    script_finished = pyqtSignal(str, int)     # 脚本名称, 退出码
    script_error = pyqtSignal(str)             # 错误消息

    def __init__(self, repo_root: str, parent=None):
        super().__init__(parent)
        self._repo_root = repo_root
        self._current_script: ScriptEntry | None = None
        self._failed_to_start = False
        self._process = QProcess(self)
        self._process.setWorkingDirectory(repo_root)
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)

    def run(
        self,
        script_entry: ScriptEntry,
        extra_args: list[str] | None = None,
        env_overrides: dict[str, str] | None = None,
    ) -> None:
        """启动脚本子进程。"""
        if self.is_running():
            self.script_error.emit("已有脚本在运行，请先停止")
            return

        self._failed_to_start = False
        self._current_script = script_entry
        args = [script_entry.script_path]
        if extra_args:
            args.extend(extra_args)

        # 构建环境变量：继承系统环境 + 强制无缓冲输出
        env_dict: dict[str, str] = {}
        for entry in QProcess.systemEnvironment():
            if "=" in entry:
                k, v = entry.split("=", 1)
                env_dict[k] = v
        env_dict["PYTHONUNBUFFERED"] = "1"
        if env_overrides:
            env_dict.update(env_overrides)
        self._process.setEnvironment(  # type: ignore[attr-defined]
            [f"{k}={v}" for k, v in env_dict.items()]
        )

        self._process.start("python", args)
        self.script_started.emit(script_entry.name)

    def stop(self) -> None:
        """终止运行中的进程（先尝试优雅停止，超时后强制杀死）。"""
        if self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.terminate()
            QTimer.singleShot(_KILL_TIMEOUT_MS, self._force_kill_if_needed)

    def _force_kill_if_needed(self) -> None:
        try:
            if self._process.state() != QProcess.ProcessState.NotRunning:
                self._process.kill()
        except RuntimeError:
            pass  # C++ 对象在关闭过程中已被销毁

    def is_running(self) -> bool:
        return self._process.state() != QProcess.ProcessState.NotRunning

    def _on_stdout(self) -> None:
        data = self._process.readAllStandardOutput().data().decode(
            errors="replace"
        )
        self.output_received.emit(data)

    def _on_stderr(self) -> None:
        data = self._process.readAllStandardError().data().decode(
            errors="replace"
        )
        self.output_received.emit(data)

    def _on_finished(self, exit_code: int, _exit_status) -> None:
        if self._failed_to_start:
            self._failed_to_start = False
            return
        name = self._current_script.name if self._current_script else "unknown"
        self.script_finished.emit(name, exit_code)

    def _on_error(self, error) -> None:
        name = self._current_script.name if self._current_script else "unknown"
        if error == QProcess.ProcessError.FailedToStart:
            self._failed_to_start = True
            self.script_error.emit(
                f"脚本启动失败: {name}\n"
                "命令 'python' 未找到，请确认 Python 已安装并加入 PATH"
            )
        elif error != QProcess.ProcessError.UnknownError:
            err_name = error.name if hasattr(error, "name") else str(error)
            self.script_error.emit(f"进程错误 ({name}): {err_name}")
