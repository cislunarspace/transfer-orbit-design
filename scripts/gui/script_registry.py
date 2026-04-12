"""脚本注册表 — 所有可用脚本的元数据定义。"""

from dataclasses import dataclass, field


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


@dataclass(frozen=True)
class ScriptEntry:
    module: str           # 类别: "dro", "ro", "halo", "transfer", "ephemeris", "inspection"
    name: str             # 文件名（不含 .py）
    description: str      # 中文描述
    script_path: str      # 相对路径 "scripts/dro/generate_31_dro_orbit.py"
    output_dir: str | None = None                     # 关联输出目录，用于文件浏览器高亮
    accepts_file_arg: bool = False                    # 是否支持 --file 参数
    needs_spice: bool = False                         # 是否需要 SPICE_KERNEL_DIR
    env_params: dict[str, EnvParam] = field(default_factory=dict)
    cli_params: list[CliParam] = field(default_factory=list)


# 按类别分组的脚本注册表，顺序决定 UI 中的显示顺序
SCRIPTS: dict[str, list[ScriptEntry]] = {
    "DRO": [
        ScriptEntry(
            "dro", "generate_31_dro_orbit",
            "生成 3:1 DRO 轨道（固定周期微分校正）",
            "scripts/dro/generate_31_dro_orbit.py",
            output_dir="output/dro",
        ),
        ScriptEntry(
            "dro", "generate_dro_family",
            "生成 DRO 轨道族（差分修正 + 自然延拓）",
            "scripts/dro/generate_dro_family.py",
            output_dir="output/dro",
            cli_params=[
                CliParam("--x0", "初始 x 坐标", "float", "0.79188556619742", "种子轨道初始 x 坐标（无量纲）"),
                CliParam("--vy0", "初始 vy 速度", "float", "0.53682", "种子轨道初始 vy 速度（无量纲）"),
                CliParam("--period", "初始周期", "float", "3.472526005624708", "初始周期猜测（无量纲）"),
                CliParam("--param-min", "延拓下限", "float", "0.141886", "延拓参数范围下限（x0 最小值）"),
                CliParam("--param-max", "延拓上限", "float", "0.9", "延拓参数范围上限（x0 最大值）"),
                CliParam("--step-size", "延拓步长", "float", "0.005", "延拓步长"),
            ],
        ),
        ScriptEntry(
            "dro", "plot_dro_family",
            "绘制 DRO 轨道族",
            "scripts/dro/plot_dro_family.py",
            output_dir="output/dro",
        ),
    ],
    "RO": [
        ScriptEntry(
            "ro", "generate_31_ro_orbit",
            "生成 3:1 RO 轨道（固定周期微分校正）",
            "scripts/ro/generate_31_ro_orbit.py",
            output_dir="output/ro",
        ),
        ScriptEntry(
            "ro", "generate_31_ro_family",
            "生成 3:1 共振轨道族（差分修正 + 自然延拓）",
            "scripts/ro/generate_31_ro_family.py",
            output_dir="output/ro",
        ),
        ScriptEntry(
            "ro", "generate_32_ro_family",
            "生成 3:2 共振轨道族（差分修正 + 自然延拓）",
            "scripts/ro/generate_32_ro_family.py",
            output_dir="output/ro",
        ),
        ScriptEntry(
            "ro", "generate_aro_family",
            "生成 ARO 轴向共振轨道族（从 3:2 RO 分岔）",
            "scripts/ro/generate_aro_family.py",
            output_dir="output/ro",
        ),
        ScriptEntry(
            "ro", "generate_rro_family",
            "生成 RRO 反射共振轨道族（从 3:2 RO 分岔）",
            "scripts/ro/generate_rro_family.py",
            output_dir="output/ro",
        ),
        ScriptEntry(
            "ro", "plot_31_ro_family",
            "绘制 3:1 共振轨道族",
            "scripts/ro/plot_31_ro_family.py",
            output_dir="output/ro",
        ),
        ScriptEntry(
            "ro", "plot_32_ro_family",
            "绘制 3:2 共振轨道族",
            "scripts/ro/plot_32_ro_family.py",
            output_dir="output/ro",
        ),
        ScriptEntry(
            "ro", "plot_aro_family",
            "绘制 ARO 轨道族",
            "scripts/ro/plot_aro_family.py",
            output_dir="output/ro",
        ),
        ScriptEntry(
            "ro", "plot_rro_family",
            "绘制 RRO 轨道族",
            "scripts/ro/plot_rro_family.py",
            output_dir="output/ro",
        ),
    ],
    "Halo": [
        ScriptEntry(
            "halo", "generate_halo_orbit",
            "生成 Halo 轨道（Richardson 三阶近似 + 微分修正）",
            "scripts/halo/generate_halo_orbit.py",
            output_dir="output/halo",
        ),
        ScriptEntry(
            "halo", "generate_halo_family",
            "生成 Halo 轨道族（伪弧长延拓）",
            "scripts/halo/generate_halo_family.py",
            output_dir="output/halo",
        ),
        ScriptEntry(
            "halo", "plot_halo_family",
            "绘制 Halo 轨道族",
            "scripts/halo/plot_halo_family.py",
            output_dir="output/halo",
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
            "绘制单条 Halo 轨道",
            "scripts/halo/plot_halo_orbit.py",
            output_dir="output/halo",
        ),
    ],
    "Transfer": [
        ScriptEntry(
            "transfer", "grid_search_dro_to_ro",
            "DRO→RO 转移轨道网格搜索",
            "scripts/transfer/grid_search_dro_to_ro.py",
            output_dir="output/transfer",
            env_params={
                "dro_file": EnvParam("DRO_FILE", "DRO 轨道文件", "dro"),
                "ro_file": EnvParam("RO_FILE", "RO 轨道文件", "ro"),
            },
        ),
        ScriptEntry(
            "transfer", "grid_search_dro_to_geo",
            "DRO→GEO 转移轨道网格搜索",
            "scripts/transfer/grid_search_dro_to_geo.py",
            output_dir="output/transfer",
            env_params={
                "dro_file": EnvParam("DRO_FILE", "DRO 轨道文件", "dro"),
            },
        ),
        ScriptEntry(
            "transfer", "grid_search_geo_to_dro",
            "GEO→DRO 转移轨道网格搜索",
            "scripts/transfer/grid_search_geo_to_dro.py",
            output_dir="output/transfer",
            env_params={
                "dro_file": EnvParam("DRO_FILE", "DRO 轨道文件", "dro"),
            },
        ),
        ScriptEntry(
            "transfer", "grid_search_leo_to_dro",
            "LEO→DRO 转移轨道网格搜索",
            "scripts/transfer/grid_search_leo_to_dro.py",
            output_dir="output/transfer",
            env_params={
                "dro_file": EnvParam("DRO_FILE", "DRO 轨道文件", "dro"),
            },
        ),
        ScriptEntry(
            "transfer", "optimize_dro_to_ro",
            "DRO→RO 转移 NLP 优化（SLSQP 最小化 Δv）",
            "scripts/transfer/optimize_dro_to_ro.py",
            output_dir="output/transfer",
            env_params={
                "search_results": EnvParam("SEARCH_RESULTS_FILE", "搜索结果文件", "transfer"),
                "dro_file": EnvParam("DRO_FILE", "DRO 轨道文件", "dro"),
                "ro_file": EnvParam("RO_FILE", "RO 轨道文件", "ro"),
            },
        ),
        ScriptEntry(
            "transfer", "optimize_dro_to_geo",
            "DRO→GEO 转移 NLP 优化",
            "scripts/transfer/optimize_dro_to_geo.py",
            output_dir="output/transfer",
            env_params={
                "search_results": EnvParam("SEARCH_RESULTS_FILE", "搜索结果文件", "transfer"),
                "dro_file": EnvParam("DRO_FILE", "DRO 轨道文件", "dro"),
            },
        ),
        ScriptEntry(
            "transfer", "optimize_geo_to_dro",
            "GEO→DRO 转移 NLP 优化",
            "scripts/transfer/optimize_geo_to_dro.py",
            output_dir="output/transfer",
            env_params={
                "search_results": EnvParam("SEARCH_RESULTS_FILE", "搜索结果文件", "transfer"),
                "dro_file": EnvParam("DRO_FILE", "DRO 轨道文件", "dro"),
            },
        ),
        ScriptEntry(
            "transfer", "optimize_leo_to_dro",
            "LEO→DRO 转移 NLP 优化",
            "scripts/transfer/optimize_leo_to_dro.py",
            output_dir="output/transfer",
            env_params={
                "search_results": EnvParam("SEARCH_RESULTS_FILE", "搜索结果文件", "transfer"),
                "dro_file": EnvParam("DRO_FILE", "DRO 轨道文件", "dro"),
            },
        ),
        ScriptEntry(
            "transfer", "validate_geo_to_dro",
            "验证 GEO→DRO 转移轨道搜索可行性",
            "scripts/transfer/validate_geo_to_dro.py",
            output_dir="output/transfer",
        ),
        ScriptEntry(
            "transfer", "plot_search_results",
            "绘制 DRO-RO 网格搜索结果",
            "scripts/transfer/plot_search_results.py",
            output_dir="output/transfer",
            accepts_file_arg=True,
            cli_params=[
                CliParam("--orbit", "绘制转移轨道图", "bool", help="绘制转移轨道示意图（替代散点图）"),
                CliParam("--time-dv", "时间 vs Δv 图", "bool", help="绘制转移时间 vs Δv 散点图"),
                CliParam("--idx", "轨道选择", "str", "0", "整数索引 / best / best:N / random / all"),
                CliParam("--max-points", "最大点数", "int", "50000", "散点最多绘制的可行点数"),
                CliParam("--dpi", "DPI", "int", "150"),
                CliParam("--seed", "随机种子", "int", "0", "子采样随机种子"),
                CliParam("--save", "保存路径", "str", help="保存 PNG 路径；不传则弹窗显示"),
                CliParam("--n-workers", "并行 worker 数", "int", help="并行积分的 worker 进程数（仅 --orbit）"),
            ],
        ),
        ScriptEntry(
            "transfer", "plot_search_results_geo",
            "绘制 DRO-GEO 网格搜索结果",
            "scripts/transfer/plot_search_results_geo.py",
            output_dir="output/transfer",
            accepts_file_arg=True,
            cli_params=[
                CliParam("--orbit", "绘制转移轨道图", "bool", help="绘制转移轨道示意图（替代散点图）"),
                CliParam("--time-dv", "时间 vs Δv 图", "bool", help="绘制转移时间 vs Δv 散点图"),
                CliParam("--interactive", "交互式浏览", "bool", help="交互式逐条浏览转移轨道"),
                CliParam("--idx", "轨道选择", "str", "0", "整数索引 / best / best:N / random / all"),
                CliParam("--max-points", "最大点数", "int", "50000", "散点最多绘制的可行点数"),
                CliParam("--dpi", "DPI", "int", "150"),
                CliParam("--seed", "随机种子", "int", "0", "子采样随机种子"),
                CliParam("--save", "保存路径", "str", help="保存 PNG 路径；不传则弹窗显示"),
                CliParam("--n-workers", "并行 worker 数", "int", help="并行积分的 worker 进程数（仅 --orbit）"),
            ],
        ),
        ScriptEntry(
            "transfer", "plot_search_results_geo_to_dro",
            "绘制 GEO-DRO 网格搜索结果",
            "scripts/transfer/plot_search_results_geo_to_dro.py",
            output_dir="output/transfer",
            accepts_file_arg=True,
            cli_params=[
                CliParam("--time-dv", "时间 vs Δv 图", "bool", help="绘制转移时间 vs Δv 散点图"),
                CliParam("--orbit", "绘制 3D 轨道图", "bool", help="绘制 3D 转移轨道图"),
                CliParam("--interactive", "交互式浏览", "bool", help="交互式浏览模式"),
                CliParam("--idx", "轨道选择", "str", "best:10", "all / best / best:N / random / 序号"),
            ],
        ),
        ScriptEntry(
            "transfer", "plot_optimize_result",
            "绘制 DRO-RO NLP 优化结果",
            "scripts/transfer/plot_optimize_result.py",
            output_dir="output/transfer",
            accepts_file_arg=True,
            cli_params=[
                CliParam("--orbit", "绘制 3D 轨道图", "bool", help="绘制转移轨道 3D 示意图"),
                CliParam("--time-dv", "时间 vs Δv 图", "bool", help="转移时间 vs Δv 散点图"),
                CliParam("--idx", "轨道选择", "str", "best", "整数索引 / best / best:N / random / all"),
                CliParam("--max-points", "最大点数", "int", "500", "--orbit --idx all 时最多绘制条数"),
                CliParam("--dpi", "DPI", "int", "150"),
                CliParam("--seed", "随机种子", "int", "0"),
                CliParam("--save", "保存路径", "str", help="保存图片路径"),
            ],
        ),
        ScriptEntry(
            "transfer", "plot_optimize_result_geo_to_dro",
            "绘制 GEO-DRO NLP 优化结果",
            "scripts/transfer/plot_optimize_result_geo_to_dro.py",
            output_dir="output/transfer",
            accepts_file_arg=True,
            cli_params=[
                CliParam("--orbit", "绘制 3D 轨道图", "bool", help="3D transfer orbit plot"),
                CliParam("--time-dv", "时间 vs Δv 图", "bool", help="transfer time vs dv scatter"),
                CliParam("--interactive", "交互式浏览", "bool", help="interactive browsing mode"),
                CliParam("--idx", "轨道选择", "str", "best:5", "all / best / best:N / random / 序号"),
                CliParam("--max-points", "最大点数", "int", "200", "max orbits for --idx all"),
                CliParam("--max-pos-err", "最大位置误差 (km)", "float", "100.0", "max position error to include"),
                CliParam("--dpi", "DPI", "int", "150"),
                CliParam("--seed", "随机种子", "int", "42"),
                CliParam("--save", "保存路径", "str", help="save figure to path"),
            ],
        ),
    ],
    "Ephemeris": [
        ScriptEntry(
            "ephemeris", "correct_dro_to_ephemeris",
            "CR3BP DRO 星历修正（多重打靶法）",
            "scripts/ephemeris/correct_dro_to_ephemeris.py",
            output_dir="output/ephemeris",
            needs_spice=True,
            env_params={
                "dro_file": EnvParam("DRO_FILE", "DRO 轨道文件", "dro"),
            },
        ),
        ScriptEntry(
            "ephemeris", "homotopy_dro_to_ephemeris",
            "CR3BP DRO 星历修正（同伦法 λ 延续）",
            "scripts/ephemeris/homotopy_dro_to_ephemeris.py",
            output_dir="output/ephemeris",
            needs_spice=True,
            env_params={
                "dro_file": EnvParam("DRO_FILE", "DRO 轨道文件", "dro"),
            },
        ),
        ScriptEntry(
            "ephemeris", "compare_ephemeris_methods",
            "对比直接法与同伦法星历修正效率",
            "scripts/ephemeris/compare_ephemeris_methods.py",
            output_dir="output/ephemeris",
            needs_spice=True,
        ),
        ScriptEntry(
            "ephemeris", "plot_ephemeris_correction",
            "绘制 DRO 星历修正前后对比图",
            "scripts/ephemeris/plot_ephemeris_correction.py",
            output_dir="output/ephemeris",
            needs_spice=True,
        ),
    ],
    "Inspection": [
        ScriptEntry(
            "inspection", "plot_interactive_orbit_inspector",
            "交互式轨道检查器（逐步遍历轨道族）",
            "scripts/inspection/plot_interactive_orbit_inspector.py",
        ),
        ScriptEntry(
            "inspection", "plot_single_orbit",
            "绘制单条轨道（2D + 3D 视图）",
            "scripts/inspection/plot_single_orbit.py",
        ),
    ],
}
