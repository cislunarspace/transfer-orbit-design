# 轨道设计 API 参考

> 本文档描述 FastAPI 后端（`api/`）的 HTTP 和 WebSocket 接口。
> 前端通过 `/orbit-api/` 代理路径访问，详见 cislunarspace 仓库中的代理配置。

## 概览

```
┌─────────────────────────┐      HTTP/WS       ┌──────────────────────────────┐
│  前端 (VuePress + Vue)   │ ──────────────────→ │  FastAPI (:8900)             │
│  /orbit-design/         │ ←────────────────── │  api/main.py                 │
└─────────────────────────┘                     │  registry_service.py         │
                                                │  runner_service.py            │
                                                │  file_service.py             │
                                                └──────────────────────────────┘
```

## 服务配置

| 配置项 | 值 | 来源 |
|--------|---|------|
| 监听地址 | `0.0.0.0:8900` | `api/config.py` |
| 工作目录 | `REPO_ROOT`（`api/main.py` 启动时确定） | |
| 最大并发任务 | `MAX_CONCURRENT = 8` | `api/config.py` |
| 单任务超时 | `MAX_JOB_SECONDS = 3600` | `api/config.py` |
| 任务历史 | `JOB_HISTORY_LIMIT = 20` | `api/config.py` |
| 输出行数限制 | `5000` 行/任务，超出截断 | `api/runner_service.py` |
| CORS 白名单 | `ALLOWED_ORIGINS` | `api/config.py` |

## HTTP 端点

### GET /api/scripts

返回完整脚本注册表（`SCRIPTS` dict）和单位组（`UNIT_GROUPS` dict）。

**实现**: `api/registry_service.py` → `get_scripts()`

**响应字段**: 见 [cislunarspace/web/orbit-design/api/orbit-design-api.md](../../cislunarspace/web/orbit-design/api/orbit-design-api.md)

### GET /api/files

查询 `output/` 目录中的文件。

**实现**: `api/file_service.py` → `discover_files()` + `GET /api/files` 端点

**文件类别**: `dro`, `ro`, `halo`, `transfer`, `geo`, `leo`

### GET /api/jobs

返回当前活跃任务和已完成任务列表。

**实现**: `api/runner_service.py` → `_active_jobs`, `_completed_jobs`

### POST /api/jobs/{job_id}/stop

停止指定任务。

**实现**: `api/runner_service.py` → `stop_job()`

使用 `asyncio.wait_for(job_process, 2)` 强制终止，超时后强制 kill。

---

## WebSocket 端点

### WS /api/ws/run/{job_id}

执行脚本并流式推送 stdout/stderr。

**实现**: `api/runner_service.py` → `run_script_websocket()`

### WebSocket 消息协议

#### 客户端 → 服务端（连接建立后立即发送）

```python
{
    "module": str,          # "dro", "transfer" 等
    "script_name": str,     # 脚本名（不含 .py）
    "env_values": dict,     # env_var → filename
    "cli_values": dict,     # flag → value（标准单位字符串）
}
```

#### 服务端 → 客户端

| type | 关键字段 |
|------|---------|
| `started` | `job_id`, `command`, `timestamp` |
| `output` | `stream` ("stdout"\|"stderr"), `text`, `timestamp` |
| `finished` | `job_id`, `exit_code`, `timestamp` |
| `error` | `message` |

详见完整协议文档：[cislunarspace/web/orbit-design/api/orbit-design-api.md](../../cislunarspace/web/orbit-design/api/orbit-design-api.md)

---

## 数据模型

所有 Pydantic 模型定义在 `api/models.py`：

| 模型 | 说明 |
|------|------|
| `UnitOption` | 单位选项（name, factor） |
| `UnitGroup` | 单位组（name, units[]） |
| `EnvParamSchema` | 环境变量参数 |
| `CliParamSchema` | 命令行参数 |
| `ScriptSchema` | 脚本条目 |
| `FileInfoSchema` | 文件信息 |
| `RunRequest` | WebSocket 请求体 |
| `StopResponse` | 停止操作响应 |
| `JobInfo` | 任务信息 |

---

## 安全说明

- **CORS 白名单**：仅允许列表中的源，防止跨站脚本调用
- **env 注入防护**：`env_values` 的 key 必须在脚本声明的 `env_params` 中存在
- **CLI 注入防护**：`cli_values` 的 key 必须在脚本声明的 `cli_params` 中存在
- **job_id 格式**：`job_{timestamp}_{6位随机串}`，防止枚举攻击
- **超时保护**：`asyncio.wait_for` 限制单任务最大执行时间
- **内存保护**：单任务输出超过 5000 行自动截断
