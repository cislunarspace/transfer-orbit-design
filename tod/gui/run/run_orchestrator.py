"""RunOrchestrator — 集中管理「收集参数 → 展开组合 → 启动 Job」的运行流水线。

将 MainWindow 与 ScriptTabWidget 中散落的「chip 组合展开 + multi-file 注入 + 启动任务」逻辑
抽取为单一职责的协调器：

- :class:`RunSpec` —— 单个待运行任务的不可变描述（args + env）
- :class:`RunPlan` —— 一次"运行前确认"的完整数据载体（specs + 摘要元数据）
- :class:`RunOrchestrator` —— 静态工具类，提供 :meth:`build_run_specs`、:meth:`build_run_plan`、:meth:`dispatch`

设计原则：
- **不可变**：``RunSpec``、``RunPlan``、``OverwriteTarget``、``ChipGroup`` 均为 frozen dataclass，避免调用方意外修改。
- **纯函数**：`build_run_specs` / `build_run_plan` 不持有 Qt 状态，只接受已经收集好的数据。
- **不绑死 MainWindow**：``dispatch`` 接受 ``JobManager`` 实例并调用其 ``start_job``。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from itertools import product
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tod.gui.jobs.job_manager import JobManager
    from tod.scripting import ScriptEntry
    from tod.gui.script_tab_widget import ScriptTabWidget

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

@dataclass(frozen=True)
class DispatchResult:
    """一次 RunOrchestrator.dispatch 的汇总结果。

    由 ``RunOrchestrator.dispatch`` 返回；BatchManager 用它创建 batch。

    Attributes:
        created_job_ids: 本次成功创建的 job_id 列表。
        rejected: 未能创建的 (job_id_or_empty, reason) 列表（如 MAX_CONCURRENT 触顶）。
        total_tasks: 待 dispatch 的 spec 总数。
        entry: 关联的 ScriptEntry。
        batch_id: 若为多任务，BatchManager 会填充此字段（PR2）。PR1 为 None。
    """

    created_job_ids: tuple[str, ...]
    rejected: tuple[tuple[str, str], ...]
    total_tasks: int
    entry: "ScriptEntry"
    batch_id: str | None = None

    @property
    def is_batch(self) -> bool:
        """是否为多任务 batch（>= 2 个 job_id）。"""
        return len(self.created_job_ids) >= 2

@dataclass(frozen=True)
class OverwriteTarget:
    """被 spec 指向的、已存在并将被覆盖的输出文件。

    Attributes:
        path: 覆盖目标的绝对或相对路径（与用户在 --output-file 输入一致，不 resolve）。
        shared_count: 多少个 RunSpec 共享该文件。
    """

    path: str
    shared_count: int

@dataclass(frozen=True)
class ChipGroup:
    """按第一个 chip key-value 分组后的 spec 集合。

    Attributes:
        group_key: 分组键对应的 flag（如 "--libration-point"）。
        group_value: 当前组对应的 chip 值（如 "1" / "L1"）。
        specs: 属于该分组的 RunSpec 列表（按 spec 顺序保持稳定）。
    """

    group_key: str
    group_value: str
    specs: tuple[RunSpec, ...]

@dataclass(frozen=True)
class RunPlan:
    """一次"运行前确认"的完整数据载体。

    Attributes:
        specs: 待 dispatch 的 RunSpec 列表。
        file_input: 当前选择文件的绝对路径（来自 `accepts_file_arg` 注入），无则 None。
        overwrites: 已被检测出将被覆盖的输出文件列表（按 spec 共享数聚合）。
        chip_groups: 按第一个被选中的 chip 分组后的 spec 集合；无 chip 或第一个 chip 未选时为 ()。
        has_output_file_param: 工具是否声明了 `kind="file_output"` 的 CliParam。
        total_tasks: spec 数量（= len(specs)）。
        entry: 关联的 ScriptEntry（供 dialog 显示工具名 + dispatch 时传入）。
    """

    specs: tuple[RunSpec, ...]
    file_input: str | None
    overwrites: tuple[OverwriteTarget, ...]
    chip_groups: tuple[ChipGroup, ...]
    has_output_file_param: bool
    total_tasks: int
    entry: "ScriptEntry"

class RunOrchestrator:
    """构造并派发 RunSpec / RunPlan。"""

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
    def build_run_plan(
        tab: "ScriptTabWidget",
        file_arg: list[str] | None,
        plot_env: dict[str, str],
        repo_root: Path,
    ) -> RunPlan:
        """构造 RunPlan：在 build_run_specs 之上叠加覆盖检测 + chip 分组。

        Args:
            tab: 当前 ScriptTabWidget。
            file_arg: 若不为空，注入到基础 args 头部。
            plot_env: 合并到每个 spec 的 env 中。
            repo_root: 项目根目录，用于解析 `--output-file` 相对路径。
        """
        specs = RunOrchestrator.build_run_specs(tab, file_arg, plot_env)
        spec_tuple = tuple(specs)
        entry = tab.entry

        file_input = file_arg[1] if file_arg and len(file_arg) >= 2 else None

        overwrites, has_output_file_param = RunOrchestrator._detect_overwrites(
            entry, specs, repo_root
        )

        chip_groups = RunOrchestrator._group_by_first_chip(entry, specs)

        return RunPlan(
            specs=spec_tuple,
            file_input=file_input,
            overwrites=overwrites,
            chip_groups=chip_groups,
            has_output_file_param=has_output_file_param,
            total_tasks=len(spec_tuple),
            entry=entry,
        )

    @staticmethod
    def dispatch(
        specs: list[RunSpec],
        entry: "ScriptEntry",
        job_manager: "JobManager",
    ) -> DispatchResult:
        """为每个 RunSpec 启动一个 Job，返回 DispatchResult。"""
        created: list[str] = []
        rejected: list[tuple[str, str]] = []
        for spec in specs:
            kwargs = spec.to_dispatch_kwargs()
            job_id = job_manager.start_job(
                entry, kwargs["args"], kwargs["env"]  # type: ignore[arg-type]
            )
            if job_id:
                created.append(job_id)
            else:
                rejected.append(("", "start_job returned empty"))
        return DispatchResult(
            created_job_ids=tuple(created),
            rejected=tuple(rejected),
            total_tasks=len(specs),
            entry=entry,
        )

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

    @staticmethod
    def _detect_overwrites(
        entry: "ScriptEntry",
        specs: list[RunSpec],
        repo_root: Path,
    ) -> tuple[tuple[OverwriteTarget, ...], bool]:
        """扫描所有 spec 的 --output-file 参数，统计已存在并将被覆盖的目标。

        Returns:
            (overwrites, has_output_file_param)：
            - overwrites: 去重后按 (path, shared_count) 聚合的覆盖目标
            - has_output_file_param: entry 是否声明了 kind="file_output" 的 CliParam
        """
        output_params = [p for p in entry.cli_params if p.kind == "file_output"]
        if not output_params:
            return ((), False)

        # 取第一个 kind="file_output" 的 flag（理论上一个工具只有一个 --output-file）
        output_flag = output_params[0].flag

        # 收集所有 spec 中该 flag 后面的非空值
        from collections import Counter

        path_counter: Counter[str] = Counter()
        for spec in specs:
            args = list(spec.args)
            for i, token in enumerate(args):
                if token == output_flag and i + 1 < len(args):
                    value = args[i + 1].strip()
                    if value:
                        path_counter[value] += 1

        # 过滤出"已存在的文件"（相对路径相对 repo_root 解析）
        overwrites: list[OverwriteTarget] = []
        for path, count in path_counter.items():
            candidate = (repo_root / path).expanduser()
            if candidate.is_file():
                overwrites.append(
                    OverwriteTarget(path=path, shared_count=count)
                )

        # 路径顺序按首次出现顺序稳定
        return (tuple(overwrites), True)

    @staticmethod
    def _group_by_first_chip(
        entry: "ScriptEntry",
        specs: list[RunSpec],
    ) -> tuple[ChipGroup, ...]:
        """按 entry.cli_chip_params[0] 的值分组；当第一个 chip 用户未选时返回 ()。"""
        if not entry.cli_chip_params or not specs:
            return ()

        first_chip = entry.cli_chip_params[0]
        first_chip_flag = first_chip.flag

        # 遍历每个 spec，找出 first_chip_flag 后面的值
        groups_dict: dict[str, list[RunSpec]] = {}
        for spec in specs:
            args = list(spec.args)
            for i, token in enumerate(args):
                if token == first_chip_flag and i + 1 < len(args):
                    value = args[i + 1]
                    groups_dict.setdefault(value, []).append(spec)
                    break

        if not groups_dict:
            return ()

        return tuple(
            ChipGroup(
                group_key=first_chip_flag,
                group_value=value,
                specs=tuple(group_specs),
            )
            for value, group_specs in groups_dict.items()
        )
