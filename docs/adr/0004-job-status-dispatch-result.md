# ADR-0004: JobStatus 枚举与 DispatchResult 信号载体

## 状态

已接受

## 上下文

`CONTEXT.md` 定义了 **任务状态** 的五个规范取值：等待中、运行中、成功、失败和已停止。PR1（ADR-0003）引入 `RunConfirmationDialog` 后，GUI 任务生命周期的下一阶段需要统一：

1. `Job.status` 原为 `str`（`"running"` / `"finished"` / `"error"` / `"stopped"`），与 `CONTEXT.md` 的五状态不对应。
2. `job_finished` 信号原签名为 `(job_id: str, name: str, exit_code: int)`，消费端（`JobPanelMixin._on_job_finished`）需回调 `JobManager.get_job(job_id)` 查询实际状态再做 UI 更新。这引入 TOCTOU：`stop_job` 已将 `job.status` 标为 `STOPPED`，但 `_on_job_finished` 可能在回调时读到被覆盖的值。
3. `job_error` 信号原签名为 `(job_id: str, error_message: str)`，与 `job_finished` 携带不同信息结构，消费端需要分别处理两个信号才能获得完整的状态/错误/脚本名上下文。

## 决策

### 1. 引入 `JobStatus(StrEnum)` 五值枚举

```python
class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    STOPPED = "stopped"
```

- 继承 `StrEnum`，可直接用于 `str` 比较和 JSON 序列化。
- 提供 `is_active` / `is_terminal` 两个 property，通过 `frozenset` 集合判定，不做 `__contains__` 线性扫描。
- 提供 `from_exit_code(code, *, stopped=False)` 纯函数：`stopped=True` 优先级最高，`code==0` 返回 `SUCCESS`，其他返回 `FAILURE`。

### 2. 引入 `DispatchResult(frozen=True dataclass)` 统一信号载体

```python
@dataclass(frozen=True)
class DispatchResult:
    job_id: str
    status: JobStatus
    exit_code: int | None
    error_message: str
    script_name: str
```

- `job_finished` 和 `job_error` 信号签名统一为 `(DispatchResult)`。
- `JobManager._on_finished` / `_on_error` / `start_job` 上限错误均构造 `DispatchResult`。
- 消费端（`JobPanelMixin`）直接读 `result.status`，不再回调 `JobManager.get_job`。
- `frozen=True` 确保信号参数不会被下游意外修改。

### 3. `stop_job` 路径的状态归属

`stop_job` 显式将 `job.status = JobStatus.STOPPED`，`_on_finished` 看到 `is_terminal` 时跳过 `from_exit_code` 覆盖。`DispatchResult.status` 由 `JobManager` 在构造时一次性确定，消费端无需推断。

### 4. 中文显示映射集中硬编码

```python
JOB_STATUS_DISPLAY: dict[JobStatus, str] = {
    JobStatus.PENDING: "等待中",
    JobStatus.RUNNING: "运行中",
    JobStatus.SUCCESS: "已完成",
    JobStatus.FAILURE: "失败",
    JobStatus.STOPPED: "已停止",
}
```

不接 i18n（`CONTEXT.md` 任务状态术语已定），避免翻译缺失导致状态显示空白。

## 后果

### 正面

- 任务状态与 `CONTEXT.md` 五值完全对应，类型安全（`StrEnum`），替代松散的 `str` 比较
- `DispatchResult` 消除 TOCTOU：`_on_job_finished` 无需回调查询，信号携带完整终态
- `job_finished` / `job_error` 信号签名统一为 `(object)`，`main_window.py` 无需改动（Qt `object` 信号兼容任意 slot 签名）
- `frozen dataclass` + `StrEnum` 对序列化、调试和类型推断友好
- 停止任务的状态由生产端（`JobManager`）确定，而非消费端推断

### 负面

- 信号签名变更（`(str, str, int)` → `(object)`）：所有 `connect` 代码需要同步更新；`main_window.py` 因 Qt `object` 类型兼容性无需改动，但第三方插件（如有）需注意
- `Job.status` 从 `str` 迁移到 `JobStatus` 枚举：任何对 `job.status == "running"` 的字符串比较都会变为类型错误，需要全量 grep 修复

### 后续

- `PENDING` 状态已就位但尚未引入真实队列调度；留给后续 issue
- `DispatchResult` 可承载更多诊断字段（如 `wall_time`、`peak_memory`），按需扩展
