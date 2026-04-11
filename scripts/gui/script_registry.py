"""脚本注册表 — 所有可用脚本的元数据定义。"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScriptEntry:
    module: str           # 类别: "dro", "ro", "halo", "transfer", "ephemeris", "inspection"
    name: str             # 文件名（不含 .py）
    description: str      # 中文描述
    script_path: str      # 相对路径 "scripts/dro/generate_31_dro_orbit.py"
    output_dir: str | None = None        # 关联输出目录，用于文件浏览器高亮
    accepts_file_arg: bool = False       # 是否支持 --file 参数
    needs_spice: bool = False            # 是否需要 SPICE_KERNEL_DIR


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
        ),
        ScriptEntry(
            "transfer", "grid_search_dro_to_geo",
            "DRO→GEO 转移轨道网格搜索",
            "scripts/transfer/grid_search_dro_to_geo.py",
            output_dir="output/transfer",
        ),
        ScriptEntry(
            "transfer", "grid_search_geo_to_dro",
            "GEO→DRO 转移轨道网格搜索",
            "scripts/transfer/grid_search_geo_to_dro.py",
            output_dir="output/transfer",
        ),
        ScriptEntry(
            "transfer", "grid_search_leo_to_dro",
            "LEO→DRO 转移轨道网格搜索",
            "scripts/transfer/grid_search_leo_to_dro.py",
            output_dir="output/transfer",
        ),
        ScriptEntry(
            "transfer", "optimize_dro_to_ro",
            "DRO→RO 转移 NLP 优化（SLSQP 最小化 Δv）",
            "scripts/transfer/optimize_dro_to_ro.py",
            output_dir="output/transfer",
        ),
        ScriptEntry(
            "transfer", "optimize_dro_to_geo",
            "DRO→GEO 转移 NLP 优化",
            "scripts/transfer/optimize_dro_to_geo.py",
            output_dir="output/transfer",
        ),
        ScriptEntry(
            "transfer", "optimize_geo_to_dro",
            "GEO→DRO 转移 NLP 优化",
            "scripts/transfer/optimize_geo_to_dro.py",
            output_dir="output/transfer",
        ),
        ScriptEntry(
            "transfer", "optimize_leo_to_dro",
            "LEO→DRO 转移 NLP 优化",
            "scripts/transfer/optimize_leo_to_dro.py",
            output_dir="output/transfer",
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
        ),
        ScriptEntry(
            "transfer", "plot_search_results_geo",
            "绘制 DRO-GEO 网格搜索结果",
            "scripts/transfer/plot_search_results_geo.py",
            output_dir="output/transfer",
            accepts_file_arg=True,
        ),
        ScriptEntry(
            "transfer", "plot_search_results_geo_to_dro",
            "绘制 GEO-DRO 网格搜索结果",
            "scripts/transfer/plot_search_results_geo_to_dro.py",
            output_dir="output/transfer",
            accepts_file_arg=True,
        ),
        ScriptEntry(
            "transfer", "plot_optimize_result",
            "绘制 DRO-RO NLP 优化结果",
            "scripts/transfer/plot_optimize_result.py",
            output_dir="output/transfer",
            accepts_file_arg=True,
        ),
        ScriptEntry(
            "transfer", "plot_optimize_result_geo_to_dro",
            "绘制 GEO-DRO NLP 优化结果",
            "scripts/transfer/plot_optimize_result_geo_to_dro.py",
            output_dir="output/transfer",
            accepts_file_arg=True,
        ),
    ],
    "Ephemeris": [
        ScriptEntry(
            "ephemeris", "correct_dro_to_ephemeris",
            "CR3BP DRO 星历修正（多重打靶法）",
            "scripts/ephemeris/correct_dro_to_ephemeris.py",
            output_dir="output/ephemeris",
            needs_spice=True,
        ),
        ScriptEntry(
            "ephemeris", "homotopy_dro_to_ephemeris",
            "CR3BP DRO 星历修正（同伦法 λ 延续）",
            "scripts/ephemeris/homotopy_dro_to_ephemeris.py",
            output_dir="output/ephemeris",
            needs_spice=True,
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
