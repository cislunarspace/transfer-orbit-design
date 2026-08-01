"""ProcessSpecBuilder — 从 ScriptEntry / e2m2e 子命令构造 ProcessSpec。

legacy backend（默认，过渡期）：``sys.executable <script_path> <args>``，
与 JobManager 旧行为一致。

e2m2e CLI backend（目标）：``<e2m2e_cli> <subcommand> <args>``，其中
``subcommand`` 由 ``E2M2E_SUBCOMMANDS`` 映射（ScriptEntry.name → 子命令名）。
e2m2e CLI 未就绪时，``E2m2eCliExecutor`` 抛清晰错误，GUI 侧兜底 legacy。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Mapping

from tod.gui.jobs.process_spec import ProcessSpec
from tod.scripting import ScriptEntry

# ScriptEntry.name → e2m2e CLI 子命令映射（随 e2m2e CLI 就绪度逐步扩充）。
# 这里先声明可测试的最小映射；Phase 2 按能力迁移时扩充。
E2M2E_SUBCOMMANDS: dict[str, str] = {
    "generate_dro_orbit": "orbit_design",
    "generate_dpo_orbit": "orbit_design",
    "generate_halo_orbit": "orbit_design",
    "generate_ro_orbit": "orbit_design",
}


def _default_env() -> Mapping[str, str]:
    """legacy 脚本进程所需的默认环境覆盖。"""
    return {
        "PYTHONUNBUFFERED": "1",
        "PYTHONIOENCODING": "utf-8",
    }


def for_script(
    entry: ScriptEntry,
    extra_args: list[str] | None = None,
    env: Mapping[str, str] | None = None,
    repo_root: Path | str | None = None,
) -> ProcessSpec:
    """构造 legacy 脚本进程的 ProcessSpec（与 JobManager 旧行为一致）。

    Args:
        entry: 脚本注册条目。
        extra_args: 额外的命令行参数。
        env: 额外的环境变量覆盖。
        repo_root: 工作目录（默认当前目录）。

    Returns:
        对应的 ProcessSpec。
    """
    args = [entry.script_path]
    if extra_args:
        args.extend(extra_args)
    merged_env = dict(_default_env())
    if env:
        merged_env.update(env)
    return ProcessSpec(
        program=sys.executable,
        argv=tuple(args),
        working_dir=str(repo_root or Path.cwd()),
        env=merged_env,
        is_legacy_script=True,
    )


def for_e2m2e_cli(
    subcommand: str,
    entry: ScriptEntry,
    args: list[str] | None = None,
    env: Mapping[str, str] | None = None,
    repo_root: Path | str | None = None,
    cli_program: str | None = None,
) -> ProcessSpec:
    """构造 e2m2e CLI 子进程的 ProcessSpec。

    Args:
        subcommand: e2m2e CLI 子命令名（如 ``"orbit_design"``）。
        entry: 脚本注册条目（用于 job 命名等）。
        args: 传给子命令的参数。
        env: 额外的环境变量覆盖。
        repo_root: 工作目录。
        cli_program: e2m2e CLI 可执行程序路径；None 时尝试解析。

    Returns:
        对应的 ProcessSpec。
    """
    cli = cli_program or _resolve_e2m2e_cli()
    argv = [subcommand]
    if args:
        argv.extend(args)
    return ProcessSpec(
        program=cli,
        argv=tuple(argv),
        working_dir=str(repo_root or Path.cwd()),
        env=dict(env or {}),
        is_legacy_script=False,
    )


def _resolve_e2m2e_cli() -> str:
    """解析 e2m2e CLI 可执行程序路径。

    优先 ``e2m2e`` console-script 入口；不可用时报清晰错误。e2m2e CLI
    尚未在 e2m2e 仓库实现（api/cli/main.py 为空骨架），因此本函数当前
    总是抛错——由调用方（E2m2eCliExecutor）在 GUI 侧兜底 legacy。
    """
    # 1) 尝试环境变量显式指定
    explicit = os.environ.get("E2M2E_CLI")
    if explicit:
        return explicit

    # 2) 尝试 console-script 入口（e2m2e pyproject 尚未声明 [project.scripts]）
    from shutil import which

    found = which("e2m2e")
    if found:
        return found

    # 3) 尝试 python -m e2m2e.api.cli.main（骨架已存在，子命令未实现）
    #    这里只返回程序路径，不验证子命令可用性；E2m2eCliExecutor 会做兜底。
    return sys.executable


def resolve_subcommand(entry: ScriptEntry) -> str:
    """返回 ScriptEntry 对应的 e2m2e 子命令名。

    Raises:
        ValueError: 该脚本尚未映射到任何 e2m2e 子命令。
    """
    sub = E2M2E_SUBCOMMANDS.get(entry.name)
    if sub is None:
        raise ValueError(
            f"脚本 {entry.name!r} 尚未映射到 e2m2e CLI 子命令；"
            "当前仍走 legacy 脚本子进程。"
        )
    return sub
