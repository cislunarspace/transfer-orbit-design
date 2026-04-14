"""脚本注册表 — 所有可用脚本的元数据定义。"""

import math
from dataclasses import dataclass, field

from scripts.utils.constants import DU, TU, VU

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


@dataclass(frozen=True)
class ScriptEntry:
    module: str           # 类别: "dro", "ro", "halo", "transfer", "ephemeris", "inspection"
    name: str             # 文件名（不含 .py）
    description: str      # 中文描述
    script_path: str      # 相对路径，如 "scripts/dro/generate/generate_31_dro_orbit.py"
    output_dir: str | None = None                     # 关联输出目录，用于文件浏览器高亮
    accepts_file_arg: bool = False                    # 是否支持 --file 参数
    needs_spice: bool = False                         # 是否需要 SPICE_KERNEL_DIR
    env_params: dict[str, EnvParam] = field(default_factory=dict)
    cli_params: list[CliParam] = field(default_factory=list)
    group_label: str = ""                             # GUI 分组标签，如 "生成"、"绘图"；空表示不分组


# 按类别分组的脚本注册表，顺序决定 UI 中的显示顺序
SCRIPTS: dict[str, list[ScriptEntry]] = {
    "DRO": [
        ScriptEntry(
            "dro", "generate_31_dro_orbit",
            "生成 3:1 DRO 轨道（固定周期微分校正）",
            "scripts/dro/generate/generate_31_dro_orbit.py",
            output_dir="output/dro",
            group_label="生成",
            cli_params=[
                CliParam("--x0", "初始 x 坐标", "float", "1.1202", "初始 x 坐标（无量纲）", unit_group="distance", default_unit="km"),
                CliParam("--vy0", "初始 vy 速度", "float", "-0.4618", "初始 y 方向速度（无量纲）", unit_group="velocity"),
                CliParam("--period", "目标周期", "float", "2.095", "目标周期（无量纲）", unit_group="time", default_unit="days"),
            ],
        ),
        ScriptEntry(
            "dro", "generate_dro_family",
            "生成 DRO 轨道族（差分修正 + 自然延拓）",
            "scripts/dro/generate/generate_dro_family.py",
            output_dir="output/dro",
            group_label="生成",
            cli_params=[
                CliParam("--x0", "初始 x 坐标", "float", "0.79188556619742", "种子轨道初始 x 坐标（无量纲）", unit_group="distance", default_unit="km"),
                CliParam("--vy0", "初始 vy 速度", "float", "0.53682", "种子轨道初始 vy 速度（无量纲）", unit_group="velocity"),
                CliParam("--period", "初始周期", "float", "3.472526005624708", "初始周期猜测（无量纲）", unit_group="time", default_unit="days"),
                CliParam("--param-min", "延拓下限", "float", "0.141886", "延拓参数范围下限（x0 最小值）", unit_group="distance", default_unit="km"),
                CliParam("--param-max", "延拓上限", "float", "0.9", "延拓参数范围上限（x0 最大值）", unit_group="distance", default_unit="km"),
                CliParam("--step-size", "延拓步长", "float", "0.005", "延拓步长"),
            ],
        ),
        ScriptEntry(
            "dro", "plot_dro_family",
            "绘制 DRO 轨道族",
            "scripts/dro/plot/plot_dro_family.py",
            output_dir="output/dro",
            group_label="绘图",
            cli_params=[
                CliParam("--json-file", "轨道族文件", "str", help="轨道族 JSON 文件路径", file_category="dro"),
            ],
        ),
    ],
    "RO": [
        ScriptEntry(
            "ro", "generate_31_ro_orbit",
            "生成 3:1 RO 轨道（固定周期微分校正）",
            "scripts/ro/generate/generate_31_ro_orbit.py",
            output_dir="output/ro",
            group_label="生成",
            cli_params=[
                CliParam("--x0", "初始 x 坐标", "float", "-0.8805", "初始 x 坐标（无量纲）", unit_group="distance", default_unit="km"),
                CliParam("--vy0", "初始 vy 速度", "float", "0.3921", "初始 y 方向速度（无量纲）", unit_group="velocity"),
                CliParam("--period", "目标周期", "float", str(round(27.32 / 0.3482, 6)), "目标周期（无量纲）", unit_group="time", default_unit="days"),
            ],
        ),
        ScriptEntry(
            "ro", "generate_31_ro_family",
            "生成 3:1 共振轨道族（差分修正 + 自然延拓）",
            "scripts/ro/generate/generate_31_ro_family.py",
            output_dir="output/ro",
            group_label="生成",
            cli_params=[
                CliParam("--x0", "初始 x 坐标", "float", "-0.8805", "初始 x 坐标（无量纲）", unit_group="distance", default_unit="km"),
                CliParam("--vy0", "初始 vy 速度", "float", "0.3921", "初始 y 方向速度（无量纲）", unit_group="velocity"),
                CliParam("--period", "轨道周期", "float", str(round(27.32 / 0.3482, 6)), "轨道周期（无量纲）", unit_group="time", default_unit="days"),
                CliParam("--param-min", "延拓下限", "float", "-0.8905", "延拓参数范围下限", unit_group="distance", default_unit="km"),
                CliParam("--param-max", "延拓上限", "float", "-0.8305", "延拓参数范围上限", unit_group="distance", default_unit="km"),
                CliParam("--step-size", "延拓步长", "float", "0.001", "延拓步长"),
            ],
        ),
        ScriptEntry(
            "ro", "generate_32_ro_family",
            "生成 3:2 共振轨道族（差分修正 + 自然延拓）",
            "scripts/ro/generate/generate_32_ro_family.py",
            output_dir="output/ro",
            group_label="生成",
            cli_params=[
                CliParam("--x0", "初始 x 坐标", "float", "-1.1453", "初始 x 坐标（无量纲）", unit_group="distance", default_unit="km"),
                CliParam("--vy0", "初始 vy 速度", "float", "0.4633", "初始 y 方向速度（无量纲）", unit_group="velocity"),
                CliParam("--period", "轨道周期", "float", str(round(54.64 / 0.3482, 6)), "轨道周期（无量纲）", unit_group="time", default_unit="days"),
                CliParam("--param-min", "延拓下限", "float", "-1.2", "延拓参数范围下限", unit_group="distance", default_unit="km"),
                CliParam("--param-max", "延拓上限", "float", "-0.8", "延拓参数范围上限", unit_group="distance", default_unit="km"),
                CliParam("--step-size", "延拓步长", "float", "0.005", "延拓步长"),
            ],
        ),
        ScriptEntry(
            "ro", "generate_aro_family",
            "生成 ARO 轴向共振轨道族（从 3:2 RO 分岔）",
            "scripts/ro/generate/generate_aro_family.py",
            output_dir="output/ro",
            group_label="生成",
            cli_params=[
                CliParam("--ro-file", "RO 文件", "str", help="3:2 RO 轨道 JSON 文件路径", file_category="ro"),
                CliParam("--target-x0", "目标 x0", "float", "-1.0878", "目标 x0 分岔点", unit_group="distance", default_unit="km"),
                CliParam("--z0", "固定 z0", "float", "0.1999", "固定 z0 坐标（无量纲）", unit_group="distance", default_unit="km"),
                CliParam("--vy0", "初始 vy 速度", "float", "0.4", "初始 y 方向速度猜测（无量纲）", unit_group="velocity"),
                CliParam("--period", "初始周期", "float", str(round(60.0 / 0.3482, 6)), "初始周期猜测（无量纲）", unit_group="time", default_unit="days"),
                CliParam("--x-min", "x 下限", "float", "-1.2", "延拓 x0 范围下限", unit_group="distance", default_unit="km"),
                CliParam("--x-max", "x 上限", "float", "-0.9", "延拓 x0 范围上限", unit_group="distance", default_unit="km"),
                CliParam("--step-size", "延拓步长", "float", "0.005", "延拓步长"),
            ],
        ),
        ScriptEntry(
            "ro", "generate_rro_family",
            "生成 RRO 反射共振轨道族（从 3:2 RO 分岔）",
            "scripts/ro/generate/generate_rro_family.py",
            output_dir="output/ro",
            group_label="生成",
            cli_params=[
                CliParam("--ro-file", "RO 文件", "str", help="3:2 RO 轨道 JSON 文件路径", file_category="ro"),
                CliParam("--target-x0", "目标 x0", "float", "-1.1318", "目标 x0 分岔点", unit_group="distance", default_unit="km"),
                CliParam("--z-max", "最大 z 幅值", "float", "0.5", "最大 z 幅值", unit_group="distance", default_unit="km"),
                CliParam("--step-size", "延拓步长", "float", "0.01", "延拓步长"),
            ],
        ),
        ScriptEntry(
            "ro", "plot_31_ro_family",
            "绘制 3:1 共振轨道族",
            "scripts/ro/plot/plot_31_ro_family.py",
            output_dir="output/ro",
            group_label="绘图",
            cli_params=[
                CliParam("--json-file", "轨道族文件", "str", help="轨道族 JSON 文件路径", file_category="ro"),
                CliParam("--start", "起始索引", "int", "-1", "起始轨道索引，-1 表示从第一条"),
                CliParam("--end", "结束索引", "int", "-1", "结束轨道索引（含），-1 表示到最后一条"),
            ],
        ),
        ScriptEntry(
            "ro", "plot_32_ro_family",
            "绘制 3:2 共振轨道族",
            "scripts/ro/plot/plot_32_ro_family.py",
            output_dir="output/ro",
            group_label="绘图",
            cli_params=[
                CliParam("--json-file", "轨道族文件", "str", help="轨道族 JSON 文件路径", file_category="ro"),
                CliParam("--start", "起始索引", "int", "-1", "起始轨道索引，-1 表示从第一条"),
                CliParam("--end", "结束索引", "int", "42", "结束轨道索引（含），-1 表示到最后一条"),
            ],
        ),
        ScriptEntry(
            "ro", "plot_aro_family",
            "绘制 ARO 轨道族",
            "scripts/ro/plot/plot_aro_family.py",
            output_dir="output/ro",
            group_label="绘图",
            cli_params=[
                CliParam("--json-file", "轨道族文件", "str", help="轨道族 JSON 文件路径", file_category="ro"),
                CliParam("--start", "起始索引", "int", "-1", "起始轨道索引，-1 表示从第一条"),
                CliParam("--end", "结束索引", "int", "-1", "结束轨道索引（含），-1 表示到最后一条"),
            ],
        ),
        ScriptEntry(
            "ro", "plot_rro_family",
            "绘制 RRO 轨道族",
            "scripts/ro/plot/plot_rro_family.py",
            output_dir="output/ro",
            group_label="绘图",
            cli_params=[
                CliParam("--json-file", "轨道族文件", "str", help="轨道族 JSON 文件路径", file_category="ro"),
                CliParam("--start", "起始索引", "int", "-1", "起始轨道索引，-1 表示从第一条"),
                CliParam("--end", "结束索引", "int", "-1", "结束轨道索引（含），-1 表示到最后一条"),
            ],
        ),
    ],
    "Halo": [
        ScriptEntry(
            "halo", "generate_halo_orbit",
            "生成 Halo 轨道（Richardson 三阶近似 + 微分修正）",
            "scripts/halo/generate/generate_halo_orbit.py",
            output_dir="output/halo",
            group_label="生成",
            cli_params=[
                CliParam("--libration-point", "平动点", "int", "1", "平动点：1=L1, 2=L2"),
                CliParam("--amplitude-z", "Z 振幅", "float", "0.23", "Z 方向振幅（无量纲）", unit_group="distance", default_unit="km"),
                CliParam("--halo-class", "Halo 类型", "int", "0", "0=北 Halo, 1=南 Halo"),
                CliParam("--period", "目标周期", "float", "1.839732", "目标周期（无量纲）", unit_group="time", default_unit="days"),
                CliParam("--x0", "初始 x 坐标", "float", "0.9305269194214338", "初始 x 坐标（无量纲）", unit_group="distance", default_unit="km"),
                CliParam("--vy0", "初始 vy 速度", "float", "0.10431508546142665", "初始 y 方向速度（无量纲）", unit_group="velocity"),
                CliParam("--max-iterations", "最大迭代次数", "int", "150", "最大迭代次数"),
                CliParam("--tolerance", "修正容差", "float", "1e-6", "修正容差"),
            ],
        ),
        ScriptEntry(
            "halo", "generate_halo_family",
            "生成 Halo 轨道族（伪弧长延拓）",
            "scripts/halo/generate/generate_halo_family.py",
            output_dir="output/halo",
            group_label="生成",
            cli_params=[
                CliParam("--libration-point", "平动点", "int", "1", "平动点：1=L1, 2=L2"),
                CliParam("--amplitude-z", "Z 振幅", "float", "0.23", "Z 方向振幅（无量纲）", unit_group="distance", default_unit="km"),
                CliParam("--halo-class", "Halo 类型", "int", "0", "0=北 Halo, 1=南 Halo"),
                CliParam("--n-orbits", "轨道数量", "int", "20", "延拓轨道数量"),
                CliParam("--step-size", "正向步长", "float", "0.0045", "正向延拓步长"),
                CliParam("--step-size-negative", "负向步长", "float", "0.009", "负向延拓步长"),
            ],
        ),
        ScriptEntry(
            "halo", "plot_halo_family",
            "绘制 Halo 轨道族",
            "scripts/halo/plot/plot_halo_family.py",
            output_dir="output/halo",
            group_label="绘图",
            env_params={
                "json_file": EnvParam("HALO_FAMILY_FILE", "Halo 轨道族文件", "halo"),
            },
            cli_params=[
                CliParam("--latest", "使用最新文件", "bool", help="使用 output/halo 下最新的 halo_*_family_*.json"),
                CliParam("--output-dir", "PNG 输出目录", "str", help="默认与 JSON 同目录"),
                CliParam("--start", "起始索引", "int", "-1", "起始轨道索引，-1 表示从第一条"),
                CliParam("--end", "结束索引", "int", "-1", "结束轨道索引（含），-1 表示到最后一条"),
                CliParam("--no-show", "只保存不显示", "bool", help="只保存图片，不调用 plt.show()"),
            ],
        ),
        ScriptEntry(
            "halo", "plot_halo_orbit",
            "绘制 Halo 轨道族（含 Jacobi/稳定性分析）",
            "scripts/halo/plot/plot_halo_orbit.py",
            output_dir="output/halo",
            group_label="绘图",
            cli_params=[
                CliParam("--json-file", "轨道族文件", "str", help="轨道族 JSON 文件路径", file_category="halo"),
                CliParam("--start", "起始索引", "int", "-1", "起始轨道索引，-1 表示从第一条"),
                CliParam("--end", "结束索引", "int", "-1", "结束轨道索引（含），-1 表示到最后一条"),
            ],
        ),
    ],
    "Transfer": [
        # ── DRO→RO ──────────────────────────────────────────────
        ScriptEntry(
            "transfer", "grid_search_dro_to_ro",
            "DRO→RO 转移轨道网格搜索",
            "scripts/transfer/dro_to_ro/grid_search_dro_to_ro.py",
            output_dir="output/transfer",
            group_label="DRO→RO",
            cli_params=[
                CliParam("--dro-file", "DRO 文件", "str", help="DRO 轨道 JSON 文件路径", file_category="dro"),
                CliParam("--ro-file", "RO 文件", "str", help="RO 轨道 JSON 文件路径", file_category="ro"),
                CliParam("--n-departure", "出发点数", "int", "200", "出发时间网格数"),
                CliParam("--n-alpha", "alpha 密度", "int", "100", "alpha 网格密度"),
                CliParam("--alpha-min", "alpha 下界", "float", "0.5", "alpha 搜索下界"),
                CliParam("--alpha-max", "alpha 上界", "float", "2.5", "alpha 搜索上界"),
                CliParam("--max-transfer-time", "最大转移时间", "float", str(round(100.0 / 0.3482, 6)), "最大转移时间（无量纲）", unit_group="time", default_unit="days"),
                CliParam("--intersection-threshold", "相交阈值", "float", "0.001", "相交判定距离阈值", unit_group="distance", default_unit="km"),
                CliParam("--min-distance", "最小距离阈值", "float", str(round(100.0 / 384400, 6)), "候选解最小距离阈值", unit_group="distance", default_unit="km"),
                CliParam("--earth-radius", "地球半径", "float", str(round(200.0 / 384400, 6)), "地球碰撞检测半径", unit_group="distance", default_unit="km"),
                CliParam("--moon-radius", "月球半径", "float", str(round(100.0 / 384400, 6)), "月球碰撞检测半径", unit_group="distance", default_unit="km"),
            ],
        ),
        ScriptEntry(
            "transfer", "optimize_dro_to_ro",
            "DRO→RO 转移 NLP 优化（SLSQP 最小化 Δv）",
            "scripts/transfer/dro_to_ro/optimize_dro_to_ro.py",
            output_dir="output/transfer",
            group_label="DRO→RO",
            cli_params=[
                CliParam("--search-file", "搜索结果文件", "str", help="网格搜索结果 JSON 文件路径", file_category="transfer"),
                CliParam("--dro-file", "DRO 文件", "str", help="DRO 轨道 JSON 文件路径", file_category="dro"),
                CliParam("--ro-file", "RO 文件", "str", help="RO 轨道 JSON 文件路径", file_category="ro"),
                CliParam("--alpha-min", "alpha 下界", "float", "0.5", "alpha 搜索下界"),
                CliParam("--alpha-max", "alpha 上界", "float", "2.5", "alpha 搜索上界"),
                CliParam("--nlp-maxiter", "NLP 最大迭代", "int", "100", "NLP 最大迭代次数"),
                CliParam("--nlp-ftol", "NLP 函数容差", "float", "1e-8", "NLP 函数容差"),
                CliParam("--top-k", "前 K 个可行解", "int", help="取前 K 个可行解优化"),
                CliParam("--max-cases", "最大案例数", "int", help="最大优化案例数"),
                CliParam("--n-workers", "并行 worker 数", "int", help="并行 worker 数"),
                CliParam("--velocity-angle-tol", "速度方向容差", "float", "0.05", "速度方向容差（弧度）", unit_group="angle"),
            ],
        ),
        ScriptEntry(
            "transfer", "plot_search_results_dro_to_ro",
            "绘制 DRO→RO 网格搜索结果",
            "scripts/transfer/dro_to_ro/plot_search_results_dro_to_ro.py",
            output_dir="output/transfer",
            group_label="DRO→RO",
            cli_params=[
                CliParam("--file", "搜索结果文件", "str", help="搜索结果 JSON 文件路径", file_category="transfer"),
                CliParam("--orbit", "转移轨道图（3D）", "bool", help="重新积分并绘制转移轨道 3D 示意图"),
                CliParam("--time-dv", "转移时间-Δv 散点图", "bool", help="绘制转移时间 vs Δv 散点图"),
                CliParam("--idx", "选中轨道（--orbit 模式）", "str", "0", "整数索引 / best / best:N / random / all"),
                CliParam("--save", "保存图片路径", "str", help="不填则弹窗显示"),
                CliParam("--max-points", "最大散点数", "int", "50000", "散点子采样上限，避免过多点导致卡顿", advanced=True),
                CliParam("--seed", "随机种子", "int", "0", "子采样随机种子", advanced=True),
                CliParam("--dpi", "图片 DPI", "int", "150", "保存图片的分辨率", advanced=True),
                CliParam("--n-workers", "并行 worker 数", "int", help="并行积分进程数，仅 --orbit 模式", advanced=True),
            ],
        ),
        ScriptEntry(
            "transfer", "plot_optimize_result_dro_to_ro",
            "绘制 DRO→RO NLP 优化结果",
            "scripts/transfer/dro_to_ro/plot_optimize_result_dro_to_ro.py",
            output_dir="output/transfer",
            group_label="DRO→RO",
            cli_params=[
                CliParam("--file", "优化结果文件", "str", help="优化结果 JSON 文件路径", file_category="transfer"),
                CliParam("--orbit", "转移轨道图（3D）", "bool", help="重新积分并绘制转移轨道 3D 示意图"),
                CliParam("--time-dv", "转移时间-Δv 散点图", "bool", help="转移时间 vs Δv 散点图"),
                CliParam("--idx", "选中轨道（--orbit 模式）", "str", "best", "整数索引 / best / best:N / random / all"),
                CliParam("--save", "保存图片路径", "str", help="不填则弹窗显示"),
                CliParam("--max-points", "最大绘制轨道数", "int", "500", "--idx all 时最多绘制条数", advanced=True),
                CliParam("--seed", "随机种子", "int", "0", "子采样随机种子", advanced=True),
                CliParam("--dpi", "图片 DPI", "int", "150", "保存图片的分辨率", advanced=True),
            ],
        ),
        # ── DRO→GEO ────────────────────────────────────────────
        ScriptEntry(
            "transfer", "grid_search_dro_to_geo",
            "DRO→GEO 转移轨道网格搜索",
            "scripts/transfer/dro_to_geo/grid_search_dro_to_geo.py",
            output_dir="output/transfer",
            group_label="DRO→GEO",
            cli_params=[
                CliParam("--dro-file", "DRO 文件", "str", help="DRO 轨道 JSON 文件路径", file_category="dro"),
                CliParam("--n-departure", "出发点数", "int", "200", "出发时间网格数"),
                CliParam("--n-alpha", "alpha 密度", "int", "100", "alpha 网格密度"),
                CliParam("--alpha-min", "alpha 下界", "float", "0.5", "alpha 搜索下界"),
                CliParam("--alpha-max", "alpha 上界", "float", "2.5", "alpha 搜索上界"),
                CliParam("--max-transfer-time", "最大转移时间", "float", str(round(100.0 / 0.3482, 6)), "最大转移时间（无量纲）", unit_group="time", default_unit="days"),
                CliParam("--geo-threshold", "GEO 相交阈值", "float", str(round(100.0 / 384400, 6)), "GEO 相交距离阈值", unit_group="distance", default_unit="km"),
                CliParam("--earth-radius", "地球半径", "float", str(round(200.0 / 384400, 6)), "地球碰撞检测半径", unit_group="distance", default_unit="km"),
                CliParam("--moon-radius", "月球半径", "float", str(round(100.0 / 384400, 6)), "月球碰撞检测半径", unit_group="distance", default_unit="km"),
            ],
        ),
        ScriptEntry(
            "transfer", "optimize_dro_to_geo",
            "DRO→GEO 转移 NLP 优化",
            "scripts/transfer/dro_to_geo/optimize_dro_to_geo.py",
            output_dir="output/transfer",
            group_label="DRO→GEO",
            cli_params=[
                CliParam("--search-file", "搜索结果文件", "str", help="网格搜索结果 JSON 文件路径", file_category="transfer"),
                CliParam("--dro-file", "DRO 文件", "str", help="DRO 轨道 JSON 文件路径", file_category="dro"),
                CliParam("--alpha-min", "alpha 下界", "float", "0.5", "alpha 搜索下界"),
                CliParam("--alpha-max", "alpha 上界", "float", "2.5", "alpha 搜索上界"),
                CliParam("--t-min", "转移时间下界", "float", "0.5", "转移时间下界（无量纲）", unit_group="time", default_unit="days"),
                CliParam("--t-max", "转移时间上界", "float", "30.0", "转移时间上界（无量纲）", unit_group="time", default_unit="days"),
                CliParam("--nlp-maxiter", "NLP 最大迭代", "int", "100", "NLP 最大迭代次数"),
                CliParam("--nlp-ftol", "NLP 函数容差", "float", "1e-8", "NLP 函数容差"),
                CliParam("--top-k", "前 K 个可行解", "int", help="取前 K 个可行解优化"),
                CliParam("--max-cases", "最大案例数", "int", help="最大优化案例数"),
                CliParam("--n-workers", "并行 worker 数", "int", help="并行 worker 数"),
            ],
        ),
        ScriptEntry(
            "transfer", "plot_search_results_dro_to_geo",
            "绘制 DRO→GEO 网格搜索结果",
            "scripts/transfer/dro_to_geo/plot_search_results_dro_to_geo.py",
            output_dir="output/transfer",
            group_label="DRO→GEO",
            cli_params=[
                CliParam("--file", "搜索结果文件", "str", help="搜索结果 JSON 文件路径", file_category="transfer"),
                CliParam("--orbit", "转移轨道图（3D）", "bool", help="重新积分并绘制转移轨道 3D 示意图"),
                CliParam("--time-dv", "转移时间-Δv 散点图", "bool", help="绘制转移时间 vs Δv 散点图"),
                CliParam("--interactive", "逐条浏览模式", "bool", help="按转移时间排序逐条浏览"),
                CliParam("--idx", "选中轨道（--orbit 模式）", "str", "0", "整数索引 / best / best:N / random / all"),
                CliParam("--save", "保存图片路径", "str", help="不填则弹窗显示"),
                CliParam("--max-points", "最大散点数", "int", "50000", "散点子采样上限，避免过多点导致卡顿", advanced=True),
                CliParam("--seed", "随机种子", "int", "0", "子采样随机种子", advanced=True),
                CliParam("--dpi", "图片 DPI", "int", "150", "保存图片的分辨率", advanced=True),
                CliParam("--n-workers", "并行 worker 数", "int", help="并行积分进程数，仅 --orbit 模式", advanced=True),
            ],
        ),
        # ── GEO→DRO ────────────────────────────────────────────
        ScriptEntry(
            "transfer", "grid_search_geo_to_dro",
            "GEO→DRO 转移轨道网格搜索",
            "scripts/transfer/geo_to_dro/grid_search_geo_to_dro.py",
            output_dir="output/transfer",
            group_label="GEO→DRO",
            cli_params=[
                CliParam("--dro-file", "DRO 文件", "str", help="DRO 轨道 JSON 文件路径", file_category="dro"),
                CliParam("--n-departure", "GEO 出发点数", "int", "10", "GEO 出发点数量"),
                CliParam("--n-alpha", "alpha 密度", "int", "200", "alpha 网格密度"),
                CliParam("--alpha-min", "alpha 下界", "float", "1.0", "alpha 搜索下界"),
                CliParam("--alpha-max", "alpha 上界", "float", "1.5", "alpha 搜索上界"),
                CliParam("--max-transfer-time", "最大转移时间", "float", str(round(10.0 / 0.3482, 6)), "最大转移时间（无量纲）", unit_group="time", default_unit="days"),
                CliParam("--intersection-threshold", "相交阈值", "float", str(round(100.0 / 384400, 6)), "相交判定距离阈值", unit_group="distance", default_unit="km"),
                CliParam("--min-distance", "最小距离阈值", "float", str(round(100.0 / 384400, 6)), "候选解最小距离阈值", unit_group="distance", default_unit="km"),
                CliParam("--earth-radius", "地球半径", "float", str(round(200.0 / 384400, 6)), "地球碰撞检测半径", unit_group="distance", default_unit="km"),
                CliParam("--moon-radius", "月球半径", "float", str(round(100.0 / 384400, 6)), "月球碰撞检测半径", unit_group="distance", default_unit="km"),
                CliParam("--geo-n-points", "GEO 采样点数", "int", "1000", "GEO 轨道采样点数"),
            ],
        ),
        ScriptEntry(
            "transfer", "optimize_geo_to_dro",
            "GEO→DRO 转移 NLP 优化",
            "scripts/transfer/geo_to_dro/optimize_geo_to_dro.py",
            output_dir="output/transfer",
            group_label="GEO→DRO",
            cli_params=[
                CliParam("--search-file", "搜索结果文件", "str", help="网格搜索结果 JSON 文件路径", file_category="transfer"),
                CliParam("--dro-file", "DRO 文件", "str", help="DRO 轨道 JSON 文件路径", file_category="dro"),
                CliParam("--alpha-min", "alpha 下界", "float", "1.0", "alpha 搜索下界"),
                CliParam("--alpha-max", "alpha 上界", "float", "1.5", "alpha 搜索上界"),
                CliParam("--t-min", "转移时间下界", "float", "5.0", "转移时间下界（无量纲）", unit_group="time", default_unit="days"),
                CliParam("--t-max", "转移时间上界", "float", "60.0", "转移时间上界（无量纲）", unit_group="time", default_unit="days"),
                CliParam("--t-ins-min", "插入时间下界", "float", "0.0", "DRO 插入时间下界", unit_group="time", default_unit="days"),
                CliParam("--t-ins-max", "插入时间上界", "float", "10.0", "DRO 插入时间上界", unit_group="time", default_unit="days"),
                CliParam("--velocity-angle-tol", "速度平行性容差", "float", help="速度平行性容差（度）", unit_group="angle"),
                CliParam("--nlp-maxiter", "NLP 最大迭代", "int", "100", "NLP 最大迭代次数"),
                CliParam("--nlp-ftol", "NLP 函数容差", "float", "1e-8", "NLP 函数容差"),
                CliParam("--top-k", "前 K 个可行解", "int", help="取前 K 个可行解优化"),
                CliParam("--max-cases", "最大案例数", "int", help="最大优化案例数"),
                CliParam("--n-workers", "并行 worker 数", "int", help="并行 worker 数"),
            ],
        ),
        ScriptEntry(
            "transfer", "plot_search_results_geo_to_dro",
            "绘制 GEO→DRO 网格搜索结果",
            "scripts/transfer/geo_to_dro/plot_search_results_geo_to_dro.py",
            output_dir="output/transfer",
            group_label="GEO→DRO",
            cli_params=[
                CliParam("--file", "搜索结果文件", "str", help="搜索结果 JSON 文件路径", file_category="transfer"),
                CliParam("--orbit", "转移轨道图（3D）", "bool", help="重新积分并绘制转移轨道 3D 示意图"),
                CliParam("--time-dv", "转移时间-Δv 散点图", "bool", help="绘制转移时间 vs Δv 散点图"),
                CliParam("--interactive", "逐条浏览模式", "bool", help="按转移时间排序逐条浏览"),
                CliParam("--idx", "选中轨道（--orbit 模式）", "str", "best:10", "all / best / best:N / random / 序号"),
                CliParam("--save", "保存图片路径", "str", help="不填则弹窗显示"),
                CliParam("--max-points", "最大散点数", "int", "50000", "散点子采样上限，避免过多点导致卡顿", advanced=True),
                CliParam("--seed", "随机种子", "int", "0", "子采样随机种子", advanced=True),
                CliParam("--dpi", "图片 DPI", "int", "150", "保存图片的分辨率", advanced=True),
            ],
        ),
        ScriptEntry(
            "transfer", "plot_optimize_result_geo_to_dro",
            "绘制 GEO→DRO NLP 优化结果",
            "scripts/transfer/geo_to_dro/plot_optimize_result_geo_to_dro.py",
            output_dir="output/transfer",
            group_label="GEO→DRO",
            cli_params=[
                CliParam("--file", "优化结果文件", "str", help="优化结果 JSON 文件路径", file_category="transfer"),
                CliParam("--orbit", "转移轨道图（3D）", "bool", help="重新积分并绘制转移轨道 3D 示意图"),
                CliParam("--time-dv", "转移时间-Δv 散点图", "bool", help="转移时间 vs Δv 散点图"),
                CliParam("--interactive", "逐条浏览模式", "bool", help="按转移时间排序逐条浏览"),
                CliParam("--idx", "选中轨道（--orbit 模式）", "str", "best:5", "all / best / best:N / random / 序号"),
                CliParam("--max-pos-err", "最大位置误差 (km)", "float", "100.0", "过滤：位置误差超过此值的结果不显示"),
                CliParam("--save", "保存图片路径", "str", help="不填则弹窗显示"),
                CliParam("--max-points", "最大绘制轨道数", "int", "200", "--idx all 时最多绘制条数", advanced=True),
                CliParam("--seed", "随机种子", "int", "42", "子采样随机种子", advanced=True),
                CliParam("--dpi", "图片 DPI", "int", "150", "保存图片的分辨率", advanced=True),
            ],
        ),
        ScriptEntry(
            "transfer", "validate_geo_to_dro",
            "验证 GEO→DRO 转移轨道搜索可行性",
            "scripts/transfer/geo_to_dro/validate_geo_to_dro.py",
            output_dir="output/transfer",
            group_label="GEO→DRO",
        ),
        # ── LEO→DRO ────────────────────────────────────────────
        ScriptEntry(
            "transfer", "grid_search_leo_to_dro",
            "LEO→DRO 转移轨道网格搜索",
            "scripts/transfer/leo_to_dro/grid_search_leo_to_dro.py",
            output_dir="output/transfer",
            group_label="LEO→DRO",
            cli_params=[
                CliParam("--dro-file", "DRO 文件", "str", help="DRO 轨道 JSON 文件路径", file_category="dro"),
                CliParam("--n-departure", "出发点数", "int", "200", "出发时间网格数"),
                CliParam("--n-alpha", "alpha 密度", "int", "100", "alpha 网格密度"),
                CliParam("--alpha-min", "alpha 下界", "float", "1.2", "alpha 搜索下界"),
                CliParam("--alpha-max", "alpha 上界", "float", "2.0", "alpha 搜索上界"),
                CliParam("--max-transfer-time", "最大转移时间", "float", "80.0", "最大转移时间（无量纲）", unit_group="time", default_unit="days"),
                CliParam("--intersection-threshold", "相交阈值", "float", "0.001", "相交判定距离阈值", unit_group="distance", default_unit="km"),
                CliParam("--min-distance", "最小距离阈值", "float", str(round(500.0 / 384400, 6)), "候选解最小距离阈值", unit_group="distance", default_unit="km"),
                CliParam("--earth-radius", "地球半径", "float", str(round(200.0 / 384400, 6)), "地球碰撞检测半径", unit_group="distance", default_unit="km"),
                CliParam("--moon-radius", "月球半径", "float", str(round(100.0 / 384400, 6)), "月球碰撞检测半径", unit_group="distance", default_unit="km"),
                CliParam("--leo-n-points", "LEO 采样点数", "int", "500", "LEO 轨道采样点数"),
            ],
        ),
        ScriptEntry(
            "transfer", "optimize_leo_to_dro",
            "LEO→DRO 转移 NLP 优化",
            "scripts/transfer/leo_to_dro/optimize_leo_to_dro.py",
            output_dir="output/transfer",
            group_label="LEO→DRO",
            cli_params=[
                CliParam("--search-file", "搜索结果文件", "str", help="网格搜索结果 JSON 文件路径", file_category="transfer"),
                CliParam("--dro-file", "DRO 文件", "str", help="DRO 轨道 JSON 文件路径", file_category="dro"),
                CliParam("--alpha-min", "alpha 下界", "float", "1.2", "alpha 搜索下界"),
                CliParam("--alpha-max", "alpha 上界", "float", "2.0", "alpha 搜索上界"),
                CliParam("--t-min", "转移时间下界", "float", "5.0", "转移时间下界（无量纲）", unit_group="time", default_unit="days"),
                CliParam("--t-max", "转移时间上界", "float", "80.0", "转移时间上界（无量纲）", unit_group="time", default_unit="days"),
                CliParam("--t-ins-min", "插入时间下界", "float", "0.0", "DRO 插入时间下界", unit_group="time", default_unit="days"),
                CliParam("--t-ins-max", "插入时间上界", "float", "10.0", "DRO 插入时间上界", unit_group="time", default_unit="days"),
                CliParam("--velocity-angle-tol", "速度平行性容差", "float", help="速度平行性容差（度）", unit_group="angle"),
                CliParam("--nlp-maxiter", "NLP 最大迭代", "int", "100", "NLP 最大迭代次数"),
                CliParam("--nlp-ftol", "NLP 函数容差", "float", "1e-8", "NLP 函数容差"),
                CliParam("--top-k", "前 K 个可行解", "int", help="取前 K 个可行解优化"),
                CliParam("--max-cases", "最大案例数", "int", help="最大优化案例数"),
                CliParam("--n-workers", "并行 worker 数", "int", help="并行 worker 数"),
            ],
        ),
    ],
    "Ephemeris": [
        ScriptEntry(
            "ephemeris", "correct_dro_to_ephemeris",
            "CR3BP DRO 星历修正（多重打靶法）",
            "scripts/ephemeris/correct/correct_dro_to_ephemeris.py",
            output_dir="output/ephemeris",
            needs_spice=True,
            group_label="星历修正",
            env_params={
                "dro_file": EnvParam("DRO_FILE", "DRO 轨道文件", "dro"),
            },
        ),
        ScriptEntry(
            "ephemeris", "homotopy_dro_to_ephemeris",
            "CR3BP DRO 星历修正（同伦法 λ 延续）",
            "scripts/ephemeris/correct/homotopy_dro_to_ephemeris.py",
            output_dir="output/ephemeris",
            needs_spice=True,
            group_label="星历修正",
            env_params={
                "dro_file": EnvParam("DRO_FILE", "DRO 轨道文件", "dro"),
            },
        ),
        ScriptEntry(
            "ephemeris", "compare_ephemeris_methods",
            "对比直接法与同伦法星历修正效率",
            "scripts/ephemeris/compare/compare_ephemeris_methods.py",
            output_dir="output/ephemeris",
            needs_spice=True,
            group_label="对比分析",
        ),
        ScriptEntry(
            "ephemeris", "plot_ephemeris_correction",
            "绘制 DRO 星历修正前后对比图",
            "scripts/ephemeris/plot/plot_ephemeris_correction.py",
            output_dir="output/ephemeris",
            needs_spice=True,
            group_label="绘图",
            cli_params=[
                CliParam("--dro-file", "DRO 文件", "str", help="DRO 轨道 JSON 文件路径", file_category="dro"),
                CliParam("--ephemeris-file", "星历修正文件", "str", help="星历修正 JSON 文件路径", file_category="ephemeris"),
            ],
        ),
    ],
    "Inspection": [
        ScriptEntry(
            "inspection", "plot_interactive_orbit_inspector",
            "交互式轨道检查器（逐步遍历轨道族）",
            "scripts/inspection/plot_interactive_orbit_inspector.py",
            group_label="交互式检查",
            cli_params=[
                CliParam("--json-file", "轨道族文件", "str", help="轨道族 JSON 文件路径"),
                CliParam("--plane", "投影平面", "str", "xy", "投影平面: xy, xz, yz"),
                CliParam("--show-3d", "显示 3D 视图", "bool", help="同时显示 3D 视图"),
                CliParam("--fig-size", "图形大小", "str", "10 8", "图形大小 (宽 高)"),
            ],
        ),
        ScriptEntry(
            "inspection", "plot_single_orbit",
            "绘制单条轨道（2D + 3D 视图）",
            "scripts/inspection/plot_single_orbit.py",
            group_label="单轨道绘图",
            cli_params=[
                CliParam("--json-file", "轨道文件", "str", help="轨道 JSON 文件路径"),
            ],
        ),
    ],
}
