"""多进程 Job 管理器 — 支持同时运行多个脚本，每个 job 拥有独立 QProcess。"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field

from PyQt6.QtCore import QProcessEnvironment, QObject, QProcess, QTimer, pyqtSignal

from scripts.gui.script_registry import ScriptEntry

_KILL_TIMEOUT_MS = 3000
_MAX_COMPLETED = 20


@dataclass
class Job:
    """单个脚本任务的运行时状态。"""

    job_id: str
    script_entry: ScriptEntry
    process: QProcess
    started_at: float
    status: str = "running"  # "running" | "completed" | "error" | "killed"
    exit_code: int | None = None
    _failed_to_start: bool = field(default=False, repr=False)
    _intentional_stop: bool = field(default=False, repr=False)


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

    # -- public API --

    def start_job(
        self,
        script_entry: ScriptEntry,
        extra_args: list[str] | None = None,
        env_overrides: dict[str, str] | None = None,
    ) -> str:
        """启动一个新的脚本进程，返回 job_id。"""
        running_count = sum(
            1 for j in self._jobs.values() if j.status == "running"
        )
        if running_count >= self.MAX_CONCURRENT:
            self.job_error.emit(
                "", f"同时运行的任务数已达上限 ({self.MAX_CONCURRENT})"
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
            started_at=time.time(),
        )
        self._jobs[job_id] = job

        args = [script_entry.script_path]
        if extra_args:
            args.extend(extra_args)
        process.start(sys.executable, args)
        self.job_started.emit(job_id, script_entry.name)
        return job_id

    def stop_job(self, job_id: str) -> None:
        """停止指定 job（先 terminate，超时后 kill）。"""
        job = self._jobs.get(job_id)
        if job is None or job.status != "running":
            return
        job._intentional_stop = True
        if job.process.state() != QProcess.ProcessState.NotRunning:
            # Windows: 使用 taskkill /F /T 杀死整个进程树，避免子进程残留
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
        running_ids = [jid for jid, j in self._jobs.items() if j.status == "running"]
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
        return self._jobs.get(job_id)

    def running_jobs(self) -> list[Job]:
        return [j for j in self._jobs.values() if j.status == "running"]

    def all_jobs(self) -> list[Job]:
        return list(self._jobs.values())

    # -- private handlers --

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
        if job._failed_to_start:
            job._failed_to_start = False
            return
        job.exit_code = exit_code
        if job._intentional_stop:
            job.status = "killed"
        elif exit_code == 0:
            job.status = "completed"
        else:
            job.status = "error"
        self.job_finished.emit(job_id, job.script_entry.name, exit_code)
        self._prune_completed()

    def _on_error(self, job_id: str, error) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            return
        name = job.script_entry.name
        if error == QProcess.ProcessError.FailedToStart:
            job._failed_to_start = True
            job.status = "error"
            self.job_error.emit(
                job_id,
                f"脚本启动失败: {name}\n"
                "Python 解释器未找到，请确认 Python 已正确安装",
            )
        elif error != QProcess.ProcessError.UnknownError:
            err_name = error.name if hasattr(error, "name") else str(error)
            self.job_error.emit(job_id, f"进程错误 ({name}): {err_name}")

    def _prune_completed(self) -> None:
        """仅保留最近 _MAX_COMPLETED 个已完成的 job。"""
        completed = [
            jid
            for jid, j in self._jobs.items()
            if j.status != "running"
        ]
        if len(completed) > _MAX_COMPLETED:
            for jid in completed[: len(completed) - _MAX_COMPLETED]:
                del self._jobs[jid]
