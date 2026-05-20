"""脚本注册表 — 所有可用脚本的元数据定义。"""

import math
from dataclasses import dataclass, field

from tod.commons.constants import DU, TU, VU

# 单位组定义：每组中的 key 为单位名，value 为到标准单位的换算因子。
# value_standard = value_displayed * factor
UNIT_GROUPS: dict[str, dict[str, float]] = {
    "distance": {"DU": 1.0, "km": 1.0 / DU},
    "velocity": {"VU": 1.0, "m/s": 1.0 / VU},
    "time": {"TU": 1.0, "days": 1.0 / TU},
    "angle": {"rad": 1.0, "deg": math.pi / 180.0},
}


@dataclass(frozen=True)
class EnvParam:
    """环境变量参数：GUI 通过下拉框选择文件，以环境变量传给子进程。"""

    env_var: str           # 环境变量名，如 "DRO_FILE"
    label: str             # UI 显示名，如 "DRO 轨道文件"
    file_category: str     # 文件类别过滤，如 "dro", "ro", "transfer"
    file_type: str = "json"  # 文件类型过滤
    name_pattern: str | None = None  # 文件名过滤模式，如 "*_family_*.json"


@dataclass(frozen=True)
class CliParam:
    """命令行参数：GUI 生成控件，值作为 extra_args 传给子进程。"""

    flag: str              # 命令行标志，如 "--orbit"
    label: str             # UI 显示名
    param_type: str        # "bool", "int", "str", "float"
    default: str = ""
    help: str = ""
    file_category: str | None = None  # 非 None 时 GUI 渲染为文件下拉框（editable combo）
    unit_group: str | None = None     # "distance", "time", "velocity", "angle" — GUI 显示单位选择器
    default_unit: str | None = None   # 默认选中的单位（如 "km"、"days"），None 则使用 unit_group 首项
    advanced: bool = False            # True 时 GUI 折叠到"高级选项"区域，默认收起
    choices: tuple[str, ...] | None = None  # 非 None 时 GUI 渲染为下拉选择框
    choice_values: dict[str, str] | None = None  # 显示标签 → CLI 值映射（如 {"北族": "0"}）
    path_mode: str = "absolute"       # "absolute" | "relative" — 文件下拉框的路径显示模式
    name_pattern: str | None = None  # 文件名过滤模式，如 "*_family_*.json"
    hidden_when: str | None = None   # 格式 "flag==condition"：当指定 flag 的控件有非空值时隐藏此参数
    required: bool | None = None     # None 保持旧逻辑；False 可声明可选文件参数


@dataclass(frozen=True)
class ScriptEntry:
    module: str           # 类别: "dro", "ro", "halo", "transfer", "ephemeris", "inspection"
    name: str             # 文件名（不含 .py）
    description: str      # 中文描述
    script_path: str      # 相对路径，如 "tod/generates/cr3bp/dro/generate_31_dro_orbit.py"
    output_dir: str | None = None                     # 关联输出目录，用于文件浏览器高亮
    accepts_file_arg: bool = False                    # 是否支持 --file 参数
    needs_spice: bool = False                         # 是否需要 SPICE_KERNEL_DIR
    env_params: dict[str, EnvParam] = field(default_factory=dict)
    cli_params: list[CliParam] = field(default_factory=list)
    group_label: str = ""                             # GUI 分组标签，如 "生成"、"绘图"；空表示不分组


def _ephemeris_conversion_cli_params(orbit_type: str, mode: str) -> list[CliParam]:
    file_category = "dro" if orbit_type == "dro" else "halo"
    input_help = "轨道族 JSON 文件路径" if mode == "family" else "单条轨道或轨道族 JSON 文件路径"
    input_pattern = "*_family_*.json" if mode == "family" else None
    params = [
        CliParam(
            "--input-file",
            "星历转换输入文件",
            "str",
            help=input_help,
            file_category=file_category,
            name_pattern=input_pattern,
        ),
        CliParam("--reference-epoch", "参考历元", "str", help="UTC 参考历元", required=True),
        CliParam(
            "--method",
            "星历转换方法",
            "str",
            "two_level",
            help="星历转换方法",
            choices=("standard", "two_level", "homotopy"),
        ),
    ]
    if mode == "single":
        params.append(CliParam("--orbit-index", "轨道索引", "int", help="从轨道族文件中选择单条轨道"))
    params.extend(
        [
            CliParam("--patch-points", "分段点数量", "int", "10", help="多重打靶分段点数量", advanced=True),
            CliParam("--position-tol", "位置容差", "float", "1e-3", help="位置连续性容差（km）", advanced=True),
            CliParam("--velocity-tol", "速度容差", "float", "1e-6", help="速度连续性容差（km/s）", advanced=True),
            CliParam("--spice-kernel-dir", "SPICE 内核目录", "str", help="SPICE 内核目录", advanced=True),
            CliParam("--bodies", "天体集合", "str", "EARTH,MOON,SUN", help="逗号分隔的天体集合", advanced=True),
            CliParam("--output-file", "输出文件", "str", help="输出 JSON 文件路径", advanced=True),
            CliParam("--per-orbit-workers", "单轨 worker 数", "int", "1", help="单条轨道修正并行 worker 数", advanced=True),
        ]
    )
    if mode == "family":
        params.extend(
            [
                CliParam("--family-workers", "轨道族 worker 数", "int", "1", help="轨道族级并行 worker 数", advanced=True),
                CliParam("--fail-fast", "首次失败即停止", "bool", help="轨道族转换遇到失败时立即停止", advanced=True),
                CliParam("--include-full-trajectory", "包含完整轨迹", "bool", help="轨道族输出包含完整轨迹", advanced=True),
            ]
        )
    return params


# 由扫描器在首次访问时填充
_SCRIPTS: dict[str, list] | None = None


def _get_scripts() -> dict[str, list]:
    """Lazily load and cache SCRIPTS from the scanner."""
    global _SCRIPTS
    if _SCRIPTS is None:
        from tod.gui.scripts._registry import get_scripts
        _SCRIPTS = get_scripts()
    return _SCRIPTS


def _scripts_getter() -> dict[str, list[ScriptEntry]]:
    return _get_scripts()


# Legacy category key aliases (old → new) for backward compatibility.
_LEGACY_ALIASES: dict[str, str] = {
    "Halo": "generates",
    "Transfer": "transfer",
    "Ephemeris": "ephemeris",
    "Inspection": "inspection",
}


# Proxy object that lazily resolves SCRIPTS on first attribute access.
class _SCRIPTSProxy:
    """Lazy proxy for SCRIPTS — resolves from scanner on first access."""

    def __getitem__(self, key: str) -> list:
        _key = _LEGACY_ALIASES.get(key, key)
        return _get_scripts()[_key]

    def get(self, key: str, default=None):
        _key = _LEGACY_ALIASES.get(key, key)
        return _get_scripts().get(_key, default)

    def keys(self):
        return _get_scripts().keys()

    def values(self):
        return _get_scripts().values()

    def items(self):
        return _get_scripts().items()

    def __iter__(self):
        return iter(_get_scripts())

    def __len__(self) -> int:
        return len(_get_scripts())

    def __repr__(self) -> str:
        return repr(_get_scripts())


# SCRIPTS 是懒加载的代理对象 — GUI 侧边栏等处的 `SCRIPTS.keys()` 等调用会触发扫描
SCRIPTS: dict = _SCRIPTSProxy()  # type: ignore[assignment]
