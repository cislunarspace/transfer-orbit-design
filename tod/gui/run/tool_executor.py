"""ToolExecutor — GUI 启动计算工具的执行策略抽象。

把「用哪个后端启动工具」从「启动流程」中分离：

- :class:`ToolExecutor`：Protocol，提供 :meth:`build_spec`（ScriptEntry →
  ProcessSpec）与 :meth:`display_name`。
- :class:`LegacyScriptExecutor`：当前行为（``sys.executable <script_path>``），
  过渡期默认。
- :class:`E2m2eCliExecutor`：目标行为（``<e2m2e_cli> <subcommand>``）。

``MainWindow`` 持有 ``self._tool_executor``（默认 legacy），测试可注入。
``RunOrchestrator.dispatch`` 不直接依赖 executor——它只把 ``extra_args``
传给 ``JobManager.start_job``；backend 切换发生在 ``MainWindow`` 组装
executor 并交给 JobManager 时。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from tod.gui.jobs.process_spec import ProcessSpec
from tod.gui.jobs.process_spec_builder import (
    for_e2m2e_cli,
    for_script,
    resolve_subcommand,
)

if TYPE_CHECKING:
    from tod.scripting import ScriptEntry


@runtime_checkable
class ToolExecutor(Protocol):
    """计算工具启动策略。"""

    def build_spec(
        self,
        entry: "ScriptEntry",
        extra_args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> ProcessSpec:
        """构造启动该工具进程的 ProcessSpec。"""
        ...

    def display_name(self, entry: "ScriptEntry") -> str:
        """返回该工具在 GUI 中的显示名（如命令行预览）。"""
        ...


class LegacyScriptExecutor:
    """legacy 后端：以 sys.executable 运行 tod/ 下的脚本文件。"""

    name = "legacy"

    def __init__(self, repo_root: Path | str | None = None) -> None:
        self._repo_root = repo_root

    def build_spec(
        self,
        entry: "ScriptEntry",
        extra_args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> ProcessSpec:
        return for_script(entry, extra_args=extra_args, env=env, repo_root=self._repo_root)

    def display_name(self, entry: "ScriptEntry") -> str:
        return entry.script_path


class E2m2eCliExecutor:
    """e2m2e CLI 后端：以 e2m2e CLI 子进程运行（目标态）。

    e2m2e CLI 尚未在 e2m2e 仓库实现时，:meth:`build_spec` 抛 :class:`ValueError`，
    由调用方兜底到 legacy。
    """

    name = "e2m2e_cli"

    def __init__(
        self,
        repo_root: Path | str | None = None,
        cli_program: str | None = None,
    ) -> None:
        self._repo_root = repo_root
        self._cli_program = cli_program

    def build_spec(
        self,
        entry: "ScriptEntry",
        extra_args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> ProcessSpec:
        subcommand = resolve_subcommand(entry)
        return for_e2m2e_cli(
            subcommand,
            entry,
            args=extra_args,
            env=env,
            repo_root=self._repo_root,
            cli_program=self._cli_program,
        )

    def display_name(self, entry: "ScriptEntry") -> str:
        try:
            sub = resolve_subcommand(entry)
        except ValueError:
            return entry.script_path
        return f"e2m2e {sub}"
