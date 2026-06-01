"""RunOrchestrator — 集中管理「收集参数 → 展开组合 → 启动 Job」的运行流水线。

将 MainWindow 与 ScriptTabWidget 中散落的「chip 组合展开 + multi-file 注入 + 启动任务」逻辑
抽取为单一职责的协调器：

- :class:`RunSpec` —— 单个待运行任务的不可变描述（args + env）
- :class:`RunOrchestrator` —— 静态工具类，提供 :meth:`build_run_specs` 与 :meth:`dispatch`

设计原则：
- **不可变**：``RunSpec`` 为 frozen dataclass，避免调用方意外修改。
- **纯函数**：`build_run_specs` 不持有 Qt 状态，只接受已经收集好的数据。
- **不绑死 MainWindow**：``dispatch`` 接受任意 ``JobManager``-like 对象（duck-typed `start_job`）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from itertools import product
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from tod.gui.job_manager import JobManager
    from tod.gui.script_registry import ScriptEntry
    from tod.gui.script_tab_widget import ScriptTabWidget


class _SupportsStartJob(Protocol):
    """duck-typed 协议：仅需 ``start_job(entry, args, env)`` 方法。"""

    def start_job(
        self,
        script_entry: "ScriptEntry",
        extra_args: list[str] | None = None,
        env_overrides: dict[str, str] | None = None,
    ) -> str: ...


@dataclass(frozen=True)
class RunSpec:
    """单个待运行任务的不可变描述。

    Attributes:
        args: 完整的命令行参数（已展开芯片组合 + multi-file JSON 注入）。
        env: 完整的环境变量覆盖（已合并 plot 主题设置）。
    """

    args: tuple[str, ...]
    env: tuple[tuple[str, str], ...]

    def to_dispatch_kwargs(self) -> dict[str, object]:
        """转成 ``JobManager.start_job`` 的关键字参数（args list, env dict）。"""
        return {"args": list(self.args), "env": dict(self.env)}


class RunOrchestrator:
    """构造并派发 RunSpec。"""

    @staticmethod
    def build_run_specs(
        tab: "ScriptTabWidget",
        file_arg: list[str] | None,
        plot_env: dict[str, str],
    ) -> list[RunSpec]:
        """从 ScriptTabWidget 收集 widget 状态、注入 file_arg 与 plot_env，返回所有 RunSpec。

        Args:
            tab: 当前 ScriptTabWidget（提供 collect_* 系列方法）。
            file_arg: 若不为空，注入到基础 args 头部（如 ``["--file", "/abs/path"]``）。
            plot_env: 合并到每个 spec 的 env 中（plot 字体 / body icon 主题）。
        """
        chip_selections = tab.collect_chip_selections()
        multi_file_configs = tab.collect_multi_file_configs()
        env_overrides = tab.collect_env_overrides()
        extra_args = tab.collect_run_args()

        if file_arg:
            extra_args = list(file_arg) + extra_args

        # 合并 plot 主题环境变量
        env_overrides = {**env_overrides, **plot_env}

        # 展开芯片参数组合
        all_args_combinations = RunOrchestrator._expand_chip_combinations(
            tab.entry, extra_args, chip_selections
        )

        # 为每个组合注入 multi-file JSON 参数
        for args in all_args_combinations:
            for key, configs in multi_file_configs.items():
                if not configs:
                    continue
                flag = None
                for multi_param in tab.entry.multi_cli_params:
                    multi_key = multi_param.flag.lstrip("-").replace("-", "_")
                    if multi_key == key:
                        flag = multi_param.flag
                        break
                if flag:
                    args.extend([flag, json.dumps(configs)])

        env_items = tuple(sorted(env_overrides.items()))
        return [
            RunSpec(args=tuple(args), env=env_items)
            for args in all_args_combinations
        ]

    @staticmethod
    def dispatch(
        specs: list[RunSpec],
        entry: "ScriptEntry",
        job_manager: _SupportsStartJob,
    ) -> list[str]:
        """为每个 RunSpec 启动一个 Job，返回 job_id 列表。"""
        job_ids: list[str] = []
        for spec in specs:
            kwargs = spec.to_dispatch_kwargs()
            job_id = job_manager.start_job(
                entry, kwargs["args"], kwargs["env"]  # type: ignore[arg-type]
            )
            job_ids.append(job_id)
        return job_ids

    @staticmethod
    def _expand_chip_combinations(
        entry: "ScriptEntry",
        base_args: list[str],
        chip_selections: dict[str, list[str]],
    ) -> list[list[str]]:
        """展开芯片多选参数的所有笛卡尔积组合。"""
        if not chip_selections:
            return [base_args]

        chip_params_list: list[tuple[str, str, list[str]]] = []
        for key, values in chip_selections.items():
            flag = None
            for chip_param in entry.cli_chip_params:
                chip_key = chip_param.flag.lstrip("-").replace("-", "_")
                if chip_key == key:
                    flag = chip_param.flag
                    break
            if flag and values:
                chip_params_list.append((key, flag, values))

        if not chip_params_list:
            return [base_args]

        combinations: list[list[str]] = []
        for combo in product(*[vals for _, _, vals in chip_params_list]):
            args = base_args.copy()
            for (_, flag, _), value in zip(chip_params_list, combo):
                args.extend([flag, value])
            combinations.append(args)

        return combinations
