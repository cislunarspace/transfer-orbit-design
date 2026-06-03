"""PyQt6 图形界面组件。

本模块为 Transfer Orbit Design 的脚本化工作流提供辅助类型、函数或入口。
"""


from __future__ import annotations

import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass

from PyQt6.QtCore import QProcessEnvironment, QObject, QProcess, QTimer, pyqtSignal

from tod.gui.job_status import JobStatus
from tod.gui.script_registry import ScriptEntry

_KILL_TIMEOUT_MS = 3000
_MAX_COMPLETED = 20


@dataclass
class Job:
    """单个脚本任务的运行时状态。"""

    job_id: str
    script_entry: ScriptEntry
    process: QProcess
    created_at: float
    started_at: float | None = None
    status: JobStatus = JobStatus.RUNNING
    exit_code: int | None = None


class JobManager(QObject):
    """管理多个并发脚本进程，每个进程通过 job_id 唯一标识。"""

    MAX_CONCURRENT = 8

    job_started = pyqtSignal(str, str)     # (job_id, script_name)
    job_output = pyqtSignal(str, str, str) # (job_id, text, stream)  stream="stdout"|"stderr"
    job_finished = pyqtSignal(str, str, int)  # (job_id, script_name, exit_code)
    job_error = pyqtSignal(str, str)       # (job_id, error_message)

    def __init__(self, repo_root: str, parent=None):
        super().__init__(parent)
        self._repo_root = repo_root
        self._jobs: dict[str, Job] = {}

    # -- 公开 API --

    def start_job(
        self,
        script_entry: ScriptEntry,
        extra_args: list[str] | None = None,
        env_overrides: dict[str, str] | None = None,
    ) -> str:
        """启动一个新的脚本进程，返回 job_id。"""
        running_count = sum(
            1 for j in self._jobs.values() if j.status == JobStatus.RUNNING
        )
        if running_count >= self.MAX_CONCURRENT:
            self.job_error.emit(
                "", self.tr("同时运行的任务数已达上限 ({})").format(self.MAX_CONCURRENT)
            )
            return ""

        job_id = uuid.uuid4().hex[:8]
        process = QProcess(self)
        process.setWorkingDirectory(self._repo_root)

        proc_env = QProcessEnvironment.systemEnvironment()
        proc_env.insert("PYTHONUNBUFFERED", "1")
        proc_env.insert("PYTHONIOENCODING", "utf-8")
        if env_overrides:
            for k, v in env_overrides.items():
                proc_env.insert(k, v)
        process.setProcessEnvironment(proc_env)

        # 用 lambda 捕获 job_id，实现 per-job 信号路由
        process.readyReadStandardOutput.connect(
            lambda jid=job_id: self._on_stdout(jid)
        )
        process.readyReadStandardError.connect(
            lambda jid=job_id: self._on_stderr(jid)
        )
        process.finished.connect(
            lambda ec, es, jid=job_id: self._on_finished(jid, ec, es)
        )
        process.errorOccurred.connect(
            lambda err, jid=job_id: self._on_error(jid, err)
        )

        job = Job(
            job_id=job_id,
            script_entry=script_entry,
            process=process,
            created_at=time.time(),
        )
        self._jobs[job_id] = job

        args = [script_entry.script_path]
        if extra_args:
            args.extend(extra_args)
        process.start(sys.executable, args)
        # 进程已启动（start() 同步发起），记录 started_at
        job.started_at = time.time()
        self.job_started.emit(job_id, script_entry.name)
        return job_id

    def stop_job(self, job_id: str) -> None:
        """停止指定 job（先 terminate，超时后 kill）。"""
        job = self._jobs.get(job_id)
        if job is None or job.status != JobStatus.RUNNING:
            return
        # 显式写 STOPPED，后续 _on_finished 看到 is_terminal 会跳过
        job.status = JobStatus.STOPPED
        if job.process.state() != QProcess.ProcessState.NotRunning:
            # Windows：使用 taskkill /F /T 杀死整个进程树，避免子进程残留
            if os.name == "nt":
                try:
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(job.process.processId())],
                        capture_output=True,
                        timeout=5,
                    )
                except (OSError, subprocess.TimeoutExpired):
                    pass
                return
            job.process.terminate()
            QTimer.singleShot(
                _KILL_TIMEOUT_MS,
                lambda jid=job_id: self._force_kill_if_needed(jid),
            )

    def stop_all(self) -> None:
        """停止所有运行中的 job 并等待其退出（用于应用关闭）。"""
        running_ids = [
            jid for jid, j in self._jobs.items() if j.status == JobStatus.RUNNING
        ]
        for job_id in running_ids:
            self.stop_job(job_id)
        # 等待进程真正退出（最多 5s）
        for job_id in running_ids:
            job = self._jobs.get(job_id)
            if job is None:
                continue
            try:
                job.process.waitForFinished(5000)
            except RuntimeError:
                pass

    def get_job(self, job_id: str) -> Job | None:
        """执行 get_job 对应的处理逻辑。

        Args:
            job_id: 调用方传入的参数值。

        Returns:
            函数执行结果。
        """
        return self._jobs.get(job_id)

    def running_jobs(self) -> list[Job]:
        """执行 running_jobs 对应的处理逻辑。

        Returns:
            函数执行结果。
        """
        return [j for j in self._jobs.values() if j.status == JobStatus.RUNNING]

    def all_jobs(self) -> list[Job]:
        """执行 all_jobs 对应的处理逻辑。

        Returns:
            函数执行结果。
        """
        return list(self._jobs.values())

    # -- 私有处理器 --

    def _force_kill_if_needed(self, job_id: str) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            return
        try:
            if job.process.state() != QProcess.ProcessState.NotRunning:
                job.process.kill()
        except RuntimeError:
            pass

    def _on_stdout(self, job_id: str) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            return
        data = job.process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        self.job_output.emit(job_id, data, "stdout")

    def _on_stderr(self, job_id: str) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            return
        data = job.process.readAllStandardError().data().decode("utf-8", errors="replace")
        self.job_output.emit(job_id, data, "stderr")

    def _on_finished(self, job_id: str, exit_code: int, _exit_status) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            return
        job.exit_code = exit_code
        # 若已被 stop_job / _on_error 显式写过终态（例如 STOPPED / FAILURE 启动失败），
        # 不再覆盖；只补 exit_code
        if not job.status.is_terminal:
            job.status = JobStatus.from_exit_code(exit_code)
        self.job_finished.emit(job_id, job.script_entry.name, exit_code)
        self._prune_terminal()

    def _on_error(self, job_id: str, error) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            return
        name = job.script_entry.name
        if error == QProcess.ProcessError.FailedToStart:
            # 显式标 FAILURE；_on_finished 看到 is_terminal 会跳过重写
            job.status = JobStatus.FAILURE
            self.job_error.emit(
                job_id,
                self.tr("脚本启动失败: {}\nPython 解释器未找到，请确认 Python 已正确安装").format(name),
            )
        elif error != QProcess.ProcessError.UnknownError:
            err_name = error.name if hasattr(error, "name") else str(error)
            self.job_error.emit(job_id, self.tr("进程错误 ({}): {}").format(name, err_name))

    def _prune_terminal(self) -> None:
        """仅保留最近 _MAX_COMPLETED 个已终态的 job。"""
        terminal = [
            jid
            for jid, j in self._jobs.items()
            if j.status.is_terminal
        ]
        if len(terminal) > _MAX_COMPLETED:
            for jid in terminal[: len(terminal) - _MAX_COMPLETED]:
                del self._jobs[jid]
