"""ProcessSpec — 脚本进程启动的不可变描述。

把「启动什么」从「如何启动」中分离：``JobManager`` 不再自行拼
``[sys.executable, script_path, *args]``，而是接收一个 ``ProcessSpec``。
这为 e2m2e CLI 子进程执行模型（Phase 1 目标）留出执行缝。

设计约束：

- :class:`ProcessSpec` 为 frozen dataclass，不可变。
- ``program`` 与 ``argv`` 分离（QProcess 用 ``program`` + ``arguments``
  分开传），argv[0] 是脚本路径（legacy）或子命令名（e2m2e CLI）。
- ``working_dir`` 与 ``env`` 由 builder 填充；``JobManager`` 只消费。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class ProcessSpec:
    """脚本进程的不可变启动描述。

    Attributes:
        program: 可执行程序路径（``sys.executable`` 或 e2m2e CLI 路径）。
        argv: 传给 program 的参数（不含 program 本身）。legacy 模式下
            argv[0] 为脚本相对路径；e2m2e CLI 模式下 argv[0] 为子命令。
        working_dir: 子进程工作目录。
        env: 环境变量覆盖（额外插入到系统环境中）。
        is_legacy_script: 是否为 tod 脚本（legacy backend）。
    """

    program: str
    argv: tuple[str, ...]
    working_dir: str
    env: Mapping[str, str] = field(default_factory=dict)
    is_legacy_script: bool = True

    def to_list(self) -> list[str]:
        """返回合并后的完整 argv（program + argv），用于调试展示。"""
        return [self.program, *self.argv]
