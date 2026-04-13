"""脚本执行服务 — WebSocket 启动脚本并流式推送输出"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException

from api.config import REPO_ROOT, MAX_CONCURRENT, JOB_HISTORY_LIMIT

router = APIRouter()

# 运行中的任务
_active_jobs: dict[str, dict[str, Any]] = {}
# 已完成任务（最近 N 个）
_completed_jobs: list[dict[str, Any]] = []


def _get_script_entry(module: str, name: str):
    """查找脚本条目"""
    from scripts.gui.script_registry import SCRIPTS
    entries = SCRIPTS.get(module, [])
    for e in entries:
        if e.name == name:
            return e
    return None


def _build_cmd(entry, cli_values: dict[str, str]) -> list[str]:
    """构建命令行"""
    cmd = [sys.executable, str(REPO_ROOT / entry.script_path)]
    for flag, value in cli_values.items():
        if value == "" or value == "False":
            continue
        if value == "True":
            cmd.append(flag)
        else:
            cmd.extend([flag, value])
    return cmd


def _build_env(entry, env_values: dict[str, str]) -> dict[str, str]:
    """构建环境变量"""
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    for env_var, file_path in env_values.items():
        env[env_var] = file_path
    if entry.needs_spice:
        spice_dir = REPO_ROOT / "../e2m2e/kernels"
        if spice_dir.exists():
            env["SPICE_KERNEL_DIR"] = str(spice_dir)
    return env


def stop_all_jobs():
    """停止所有运行中的任务"""
    for job_id, job in list(_active_jobs.items()):
        proc = job.get("process")
        if proc and proc.returncode is None:
            proc.terminate()


@router.websocket("/ws/run/{job_id}")
async def run_script(websocket: WebSocket, job_id: str):
    """WebSocket 端点: 接收运行请求，启动脚本，流式推送输出"""
    await websocket.accept()

    # 接收运行参数并验证
    from api.models import RunRequest
    raw = await websocket.receive_json()
    try:
        data = RunRequest(**raw)
    except Exception as e:
        await websocket.send_json({"type": "error", "message": f"参数格式错误: {e}"})
        await websocket.close()
        return
    module = data.module
    script_name = data.script_name
    env_values = data.env_values
    cli_values = data.cli_values

    entry = _get_script_entry(module, script_name)
    if not entry:
        await websocket.send_json({"type": "error", "message": f"脚本未找到: {module}/{script_name}"})
        await websocket.close()
        return

    if len(_active_jobs) >= MAX_CONCURRENT:
        await websocket.send_json({"type": "error", "message": f"已达最大并发数 {MAX_CONCURRENT}"})
        await websocket.close()
        return

    cmd = _build_cmd(entry, cli_values)
    env = _build_env(entry, env_values)

    # 发送启动消息
    await websocket.send_json({
        "type": "started",
        "job_id": job_id,
        "script_name": script_name,
        "command": " ".join(cmd),
        "timestamp": datetime.now().isoformat(),
    })

    # 启动子进程
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
        cwd=str(REPO_ROOT),
    )

    job_info = {
        "job_id": job_id,
        "script_name": script_name,
        "module": module,
        "process": proc,
        "started_at": datetime.now().isoformat(),
    }
    _active_jobs[job_id] = job_info

    try:
        async def read_stream(stream, stream_name: str):
            while True:
                line = await stream.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip("\n")
                await websocket.send_json({
                    "type": "output",
                    "stream": stream_name,
                    "text": text,
                    "timestamp": datetime.now().isoformat(),
                })

        # 并发读取 stdout 和 stderr
        await asyncio.gather(
            read_stream(proc.stdout, "stdout"),
            read_stream(proc.stderr, "stderr"),
        )

        exit_code = await proc.wait()
        await websocket.send_json({
            "type": "finished",
            "job_id": job_id,
            "exit_code": exit_code,
            "timestamp": datetime.now().isoformat(),
        })

    except WebSocketDisconnect:
        # 客户端断开，终止进程
        if proc.returncode is None:
            proc.terminate()
            await proc.wait()
    finally:
        _active_jobs.pop(job_id, None)
        # 保存到历史
        job_info["exit_code"] = proc.returncode
        job_info["finished_at"] = datetime.now().isoformat()
        _completed_jobs.append(job_info)
        # 保留最近 N 个
        while len(_completed_jobs) > JOB_HISTORY_LIMIT:
            _completed_jobs.pop(0)
        try:
            await websocket.close()
        except Exception:
            pass


@router.post("/jobs/{job_id}/stop")
async def stop_job(job_id: str):
    """停止运行中的任务"""
    job = _active_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"任务未找到: {job_id}")
    proc = job.get("process")
    if proc and proc.returncode is None:
        proc.terminate()
        # 3 秒后强制终止
        await asyncio.sleep(3)
        if proc.returncode is None:
            proc.kill()
    return {"status": "stopped", "job_id": job_id}


@router.get("/jobs")
async def list_jobs():
    """列出所有任务（运行中 + 最近完成）"""
    active = [
        {
            "job_id": j["job_id"],
            "script_name": j["script_name"],
            "module": j["module"],
            "started_at": j["started_at"],
            "status": "running",
        }
        for j in _active_jobs.values()
    ]
    completed = [
        {
            "job_id": j["job_id"],
            "script_name": j["script_name"],
            "module": j["module"],
            "started_at": j["started_at"],
            "finished_at": j.get("finished_at", ""),
            "exit_code": j.get("exit_code"),
            "status": "completed" if j.get("exit_code") == 0 else "error",
        }
        for j in _completed_jobs
    ]
    return {"active": active, "completed": completed}
