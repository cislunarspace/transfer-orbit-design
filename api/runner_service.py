"""脚本执行服务 — WebSocket 启动脚本并流式推送输出"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import uuid
from collections import deque
from datetime import datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException

from api.config import (
    REPO_ROOT,
    MAX_CONCURRENT,
    JOB_HISTORY_LIMIT,
    MAX_JOB_SECONDS,
    logger,
)

router = APIRouter()

# 运行中的任务
_active_jobs: dict[str, dict[str, Any]] = {}
# 已完成任务（最近 N 个）— deque 自动淘汰旧条目
_completed_jobs: deque[dict[str, Any]] = deque(maxlen=JOB_HISTORY_LIMIT)

# [FIX] 记录已使用的 job_id 防止重复
_used_job_ids: set[str] = set()


def _get_script_entry(module: str, name: str):
    """查找脚本条目"""
    from scripts.gui.script_registry import SCRIPTS
    entries = SCRIPTS.get(module, [])
    for e in entries:
        if e.name == name:
            return e
    return None


def _validate_cli_values(entry, cli_values: dict[str, str]) -> None:
    """[FIX] 验证 CLI 值只包含声明的 flag"""
    from scripts.gui.script_registry import CliParam
    allowed_flags = {p.flag for p in entry.cli_params}
    for flag in cli_values:
        if flag not in allowed_flags:
            raise ValueError(f"未声明的参数: {flag}")


def _validate_env_values(entry, env_values: dict[str, str]) -> None:
    """[FIX] 验证环境变量只包含声明的 env_param"""
    allowed_vars = {p.env_var for p in entry.env_params.values()}
    for key in env_values:
        if key not in allowed_vars:
            raise ValueError(f"未声明的环境变量: {key}")


def _build_cmd(entry, cli_values: dict[str, str]) -> list[str]:
    """构建命令行"""
    cmd = [sys.executable, str(REPO_ROOT / entry.script_path)]
    for flag, value in cli_values.items():
        # [FIX] 标准化 bool 值处理
        if not value or value.lower() in ("false", "0", "no"):
            continue
        if value.lower() in ("true", "1", "yes"):
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

    # [FIX] 验证 job_id 格式 (必须是 8-12 位十六进制)
    try:
        if not all(c in "0123456789abcdef" for c in job_id.lower()) or len(job_id) > 16:
            raise ValueError
    except (ValueError, TypeError):
        await websocket.send_json({"type": "error", "message": "无效的 job ID 格式"})
        await websocket.close()
        return

    # [FIX] 防止 job_id 重复使用
    if job_id in _used_job_ids:
        await websocket.send_json({"type": "error", "message": f"job ID 已使用: {job_id}"})
        await websocket.close()
        return

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

    # [FIX] 验证 env_values 和 cli_values 只包含声明的参数
    try:
        _validate_env_values(entry, env_values)
        _validate_cli_values(entry, cli_values)
    except ValueError as e:
        await websocket.send_json({"type": "error", "message": str(e)})
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

    _used_job_ids.add(job_id)

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
                try:
                    await websocket.send_json({
                        "type": "output",
                        "stream": stream_name,
                        "text": text,
                        "timestamp": datetime.now().isoformat(),
                    })
                except Exception:
                    # WebSocket 已断开，停止读取
                    break

        # [FIX] 使用 asyncio.wait_for 添加全局超时
        async def run_with_timeout():
            await asyncio.gather(
                read_stream(proc.stdout, "stdout"),
                read_stream(proc.stderr, "stderr"),
            )
            return await proc.wait()

        try:
            exit_code = await asyncio.wait_for(
                run_with_timeout(),
                timeout=MAX_JOB_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.warning("任务 %s 超时 (%ds)，强制终止", job_id, MAX_JOB_SECONDS)
            if proc.returncode is None:
                proc.kill()
                await proc.wait()
            await websocket.send_json({
                "type": "finished",
                "job_id": job_id,
                "exit_code": -1,
                "timestamp": datetime.now().isoformat(),
                "reason": "timeout",
            })
            return

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
            try:
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
    finally:
        _active_jobs.pop(job_id, None)
        # 保存到历史
        job_info["exit_code"] = proc.returncode
        job_info["finished_at"] = datetime.now().isoformat()
        _completed_jobs.append(job_info)  # deque 自动淘汰旧条目
        try:
            await websocket.close()
        except Exception:
            logger.debug("WebSocket 已关闭: %s", job_id, exc_info=True)


@router.post("/jobs/{job_id}/stop")
async def stop_job(job_id: str):
    """停止运行中的任务"""
    job = _active_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"任务未找到: {job_id}")
    proc = job.get("process")
    if proc and proc.returncode is None:
        try:
            proc.terminate()
            # [FIX] 使用 wait_for 替代无条件 sleep
            await asyncio.wait_for(proc.wait(), timeout=3.0)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
        except ProcessLookupError:
            pass  # 进程已退出
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
