"""PyQt6 图形界面组件。

"""

from __future__ import annotations

import os
import subprocess
import time
import uuid
from dataclasses import dataclass

from PyQt6.QtCore import QProcessEnvironment, QObject, QProcess, QTimer, pyqtSignal

from tod.gui.i18n import qt_format
from tod.gui.jobs.job_status import JobFinishResult, JobStatus
from tod.gui.jobs.process_spec import ProcessSpec
from tod.gui.jobs.process_spec_builder import for_script
from tod.scripting import ScriptEntry

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

    job_created = pyqtSignal(str, str)          # (job_id, script_name) — Job 对象已进入系统
    job_started = pyqtSignal(str, str)          # (job_id, script_name) — QProcess 已真正启动
    job_state_changed = pyqtSignal(str, str, str)  # (job_id, old_status.value, new_status.value)
    job_output = pyqtSignal(str, str, str)      # (job_id, text, stream)  stream="stdout"|"stderr"
    job_finished = pyqtSignal(object)           # JobFinishResult — 进程结束（含 exit_code）
    job_error = pyqtSignal(object)              # JobFinishResult — 启动失败 / 进程错误
    jobs_pruned = pyqtSignal(list)              # pruned_job_ids — 历史 Job 被清理

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
        """启动一个新的脚本进程，返回 job_id。

        legacy 薄包装：构造 ``ProcessSpec`` 后委托给 :meth:`start_job_spec`。
        保留既有签名，调用方（``RunOrchestrator.dispatch`` 等）无需改动。
        """
        spec = for_script(
            script_entry,
            extra_args=extra_args,
            env=env_overrides,
            repo_root=self._repo_root,
        )
        return self.start_job_spec(spec, script_entry)

    def start_job_spec(self, spec: ProcessSpec, script_entry: ScriptEntry) -> str:
        """按给定的 ProcessSpec 启动脚本进程，返回 job_id。

        Args:
            spec: 进程启动描述（program / argv / working_dir / env）。
            script_entry: 脚本注册条目（用于 job 命名与信号）。

        Returns:
            新建 job 的 8 位 uuid 短 id；达到并发上限时返回空字符串。
        """
        running_count = sum(
            1 for j in self._jobs.values() if j.status == JobStatus.RUNNING
        )
        if running_count >= self.MAX_CONCURRENT:
            self.job_error.emit(JobFinishResult(
                job_id="",
                status=JobStatus.FAILURE,
                exit_code=None,
                error_message=self.tr("同时运行的任务数已达上限 ({})").format(self.MAX_CONCURRENT),
                script_name="",
            ))
            return ""

        job_id = uuid.uuid4().hex[:8]
        process = QProcess(self)
        process.setWorkingDirectory(spec.working_dir)

        proc_env = QProcessEnvironment.systemEnvironment()
        proc_env.insert("PYTHONUNBUFFERED", "1")
        proc_env.insert("PYTHONIOENCODING", "utf-8")
        for k, v in spec.env.items():
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

        process.start(spec.program, list(spec.argv))
        # 进程已启动（start() 同步发起），记录 started_at
        job.started_at = time.time()
        self.job_created.emit(job_id, script_entry.name)
        self.job_started.emit(job_id, script_entry.name)
        return job_id

    def stop_job(self, job_id: str) -> None:
        """停止指定 job（先 terminate，超时后 kill）。"""
        job = self._jobs.get(job_id)
        if job is None or job.status != JobStatus.RUNNING:
            return
        # 显式写 STOPPED，后续 _on_finished 看到 is_terminal 会跳过
        old = job.status
        job.status = JobStatus.STOPPED
        self.job_state_changed.emit(job_id, old.value, JobStatus.STOPPED.value)
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
        """获取 Job 对象，不存在时返回 None。"""
        return self._jobs.get(job_id)

    def get_job_status(self, job_id: str) -> JobStatus | None:
        """获取指定 job 的当前状态，被 prune 后返回 None。

        PR2 (BatchManager) 通过注入此方法查询 Job 状态。
        """
        job = self._jobs.get(job_id)
        return job.status if job is not None else None

    def running_jobs(self) -> list[Job]:
        """返回当前状态为运行中的 Job 列表。"""
        return [j for j in self._jobs.values() if j.status == JobStatus.RUNNING]

    def all_jobs(self) -> list[Job]:
        
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
        old_status = job.status
        # 若已被 stop_job / _on_error 显式写过终态（例如 STOPPED / FAILURE 启动失败），
        # 不再覆盖；只补 exit_code
        if not old_status.is_terminal:
            job.status = JobStatus.from_exit_code(exit_code)
        if job.status != old_status:
            self.job_state_changed.emit(job_id, old_status.value, job.status.value)
        self.job_finished.emit(JobFinishResult(
            job_id=job_id,
            status=job.status,
            exit_code=exit_code,
            error_message="",
            script_name=job.script_entry.name,
        ))
        self._prune_terminal()

    def _on_error(self, job_id: str, error) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            return
        name = job.script_entry.name
        if error == QProcess.ProcessError.FailedToStart:
            # 显式标 FAILURE；_on_finished 看到 is_terminal 会跳过重写
            old = job.status
            job.status = JobStatus.FAILURE
            if job.status != old:
                self.job_state_changed.emit(job_id, old.value, job.status.value)
            msg = self.tr("任务启动失败：{}\nPython 解释器未找到，请确认 Python 已正确安装").format(name)
            self.job_error.emit(JobFinishResult(
                job_id=job_id,
                status=job.status,
                exit_code=None,
                error_message=msg,
                script_name=name,
            ))
        elif error != QProcess.ProcessError.UnknownError:
            err_name = error.name if hasattr(error, "name") else str(error)
            msg = self.tr("进程错误（{}）：{}").format(name, err_name)
            self.job_error.emit(JobFinishResult(
                job_id=job_id,
                status=job.status,
                exit_code=None,
                error_message=msg,
                script_name=name,
            ))

    def _prune_terminal(self) -> None:
        """仅保留最近 _MAX_COMPLETED 个已终态的 job。"""
        terminal = [
            jid
            for jid, j in self._jobs.items()
            if j.status.is_terminal
        ]
        if len(terminal) > _MAX_COMPLETED:
            pruned = terminal[: len(terminal) - _MAX_COMPLETED]
            for jid in pruned:
                del self._jobs[jid]
            self.jobs_pruned.emit(pruned)
