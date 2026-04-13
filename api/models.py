"""API 数据模型 — 对应 script_registry.py 中的 dataclass"""
from __future__ import annotations

from pydantic import BaseModel


class UnitOption(BaseModel):
    """单位选项"""
    name: str       # "DU", "km"
    factor: float   # 转换因子 (乘以这个值得到标准单位)


class UnitGroup(BaseModel):
    """单位组"""
    name: str                   # "distance", "velocity", "time", "angle"
    units: list[UnitOption]


class EnvParamSchema(BaseModel):
    """环境变量参数"""
    env_var: str
    label: str
    file_category: str
    file_type: str = "json"


class CliParamSchema(BaseModel):
    """命令行参数"""
    flag: str
    label: str
    param_type: str         # "bool" | "int" | "float" | "str"
    default: str = ""
    help: str = ""
    file_category: str | None = None
    unit_group: str | None = None
    advanced: bool = False


class ScriptSchema(BaseModel):
    """脚本条目"""
    module: str
    name: str
    description: str
    script_path: str
    output_dir: str | None = None
    accepts_file_arg: bool = False
    needs_spice: bool = False
    env_params: dict[str, EnvParamSchema] = {}
    cli_params: list[CliParamSchema] = []


class FileInfoSchema(BaseModel):
    """文件信息"""
    name: str
    path: str
    size: int
    modified: str        # ISO 格式时间戳
    file_type: str
    category: str


class RunRequest(BaseModel):
    """脚本执行请求 (用于 WebSocket JSON 验证)"""
    script_name: str                          # ScriptEntry.name
    module: str                               # ScriptEntry.module
    env_values: dict[str, str] = {}           # env_var → file path
    cli_values: dict[str, str] = {}           # flag → value string


class StopResponse(BaseModel):
    status: str
    job_id: str


class JobInfo(BaseModel):
    job_id: str
    script_name: str
    module: str
    started_at: str
    status: str
    finished_at: str = ""
    exit_code: int | None = None
