"""analyze_cr3bp_dataset 脚本（仿真 10）。

统计 ``data/cr3bp_data/raw/`` 下全部 CR3BP 轨道 XLSX 数据集：
每个轨道族的轨道数量、Jacobi 常数范围、周期范围、稳定性指数分布，
绘制 2×2 覆盖情况图并输出 JSON 统计，为后续数据基础设施提供清单。

复用项目内置零依赖 XLSX 读取器 ``tod.generates.cr3bp._xlsx_reader``
与文件名解析器 ``_raw_naming``，不引入 pandas。

运行示例:
    .. code-block:: bash

       uv run python -m tod.transfers.dro_to_geo.analyze_cr3bp_dataset \
           --data-dir data/cr3bp_data/raw
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from tod.generates.cr3bp._raw_naming import parse_raw_xlsx_name
from tod.generates.cr3bp._xlsx_reader import read_xlsx_sheets
from tod.generates.cr3bp.importer import SHEET1_COLUMNS

project_root = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_DATA_DIR = project_root / "data" / "cr3bp_data" / "raw"
DEFAULT_OUTPUT_JSON = project_root / "output" / "cr3bp_dataset_statistics.json"
DEFAULT_PLOT = project_root / "figures" / "cr3bp_dataset_coverage.png"


def parse_args():
    parser = argparse.ArgumentParser(
        description="CR3BP 轨道数据集统计（仿真 10）",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--data-dir", type=str, default=str(DEFAULT_DATA_DIR),
        help="CR3BP 原始 XLSX 数据目录",
    )
    parser.add_argument(
        "--output-file", type=str, default=str(DEFAULT_OUTPUT_JSON),
        help="输出 JSON 路径",
    )
    parser.add_argument(
        "--plot-save", type=str, default=str(DEFAULT_PLOT),
        help="输出图片路径",
    )
    return parser.parse_args()


def _sheet1_records(path: Path) -> list[dict[str, float]]:
    """读取 Sheet1 数据行，返回 SHEET1_COLUMNS 键的数值记录列表。"""
    sheets = read_xlsx_sheets(path)
    if "Sheet1" not in sheets:
        raise ValueError(f"{path.name} 缺少 Sheet1")
    rows = sheets["Sheet1"]
    if not rows:
        return []
    header = [cell.strip() for cell in rows[0]]
    col_index = {name: header.index(name) for name in SHEET1_COLUMNS if name in header}
    missing = [name for name in ("jacobi", "period", "stability") if name not in col_index]
    if missing:
        raise ValueError(f"{path.name} Sheet1 缺少列: {missing}")

    records = []
    for row in rows[1:]:
        if not any(cell.strip() for cell in row):
            continue
        record = {}
        for name, idx in col_index.items():
            cell = row[idx] if idx < len(row) else ""
            try:
                record[name] = float(cell)
            except ValueError:
                record[name] = float("nan")
        records.append(record)
    return records


def main():
    args = parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.is_dir():
        raise FileNotFoundError(f"未找到数据目录: {data_dir}")

    xlsx_files = sorted(p for p in data_dir.glob("*.xlsx") if p.is_file())
    print(f"数据目录: {data_dir}")
    print(f"XLSX 文件数: {len(xlsx_files)}")

    statistics = []
    all_stability = []
    for xlsx_file in xlsx_files:
        name = parse_raw_xlsx_name(xlsx_file)
        records = _sheet1_records(xlsx_file)
        if not records:
            print(f"  警告: {xlsx_file.name} 无数据行，跳过")
            continue

        jacobi = np.array([r["jacobi"] for r in records], dtype=float)
        period = np.array([r["period"] for r in records], dtype=float)
        stability = np.array([r["stability"] for r in records], dtype=float)
        all_stability.extend(stability[np.isfinite(stability)].tolist())

        statistics.append({
            "orbit_family": name.dataset_id,
            "orbit_type": name.orbit_type,
            "libration_point": name.libration_point,
            "branch": name.branch,
            "resonance": name.resonance,
            "n_orbits": len(records),
            "jacobi_min": float(np.nanmin(jacobi)),
            "jacobi_max": float(np.nanmax(jacobi)),
            "period_min": float(np.nanmin(period)),
            "period_max": float(np.nanmax(period)),
            "stability_min": float(np.nanmin(stability)),
            "stability_max": float(np.nanmax(stability)),
            "stability_mean": float(np.nanmean(stability)),
        })
        print(
            f"  {name.dataset_id:<32s} n={len(records):5d}  "
            f"C∈[{np.nanmin(jacobi):.3f}, {np.nanmax(jacobi):.3f}]  "
            f"T∈[{np.nanmin(period):.3f}, {np.nanmax(period):.3f}] TU"
        )

    payload = {
        "metadata": {
            "data_dir": str(data_dir),
            "n_files": len(xlsx_files),
            "n_families": len(statistics),
            "total_orbits": sum(s["n_orbits"] for s in statistics),
        },
        "families": statistics,
    }
    out_path = Path(args.output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"\n结果已保存: {out_path}")

    # 绘图
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from tod.plot.config import apply_standard_plot_config
    apply_standard_plot_config()

    # 标签去掉公共前缀，紧凑显示
    labels = [s["orbit_family"].replace("earth-moon_", "") for s in statistics]

    fig, axes = plt.subplots(2, 2, figsize=(14, 12))

    ax = axes[0, 0]
    ax.barh(labels, [s["n_orbits"] for s in statistics])
    ax.invert_yaxis()
    ax.set_xlabel("轨道数量")
    ax.set_title("CR3BP 轨道族数量分布")
    ax.tick_params(axis="y", labelsize=6)
    ax.grid(True, alpha=0.3, axis="x")

    ax = axes[0, 1]
    for i, s in enumerate(statistics):
        ax.plot([i, i], [s["jacobi_min"], s["jacobi_max"]], "b-", lw=1.5)
        ax.plot(i, s["jacobi_min"], "b_", ms=6)
        ax.plot(i, s["jacobi_max"], "b_", ms=6)
    ax.set_xticks(range(len(labels)), labels, rotation=90, fontsize=6)
    ax.set_ylabel("Jacobi 常数")
    ax.set_title("Jacobi 常数范围")
    ax.grid(True, alpha=0.3, axis="y")

    ax = axes[1, 0]
    for i, s in enumerate(statistics):
        ax.plot([i, i], [s["period_min"], s["period_max"]], "g-", lw=1.5)
        ax.plot(i, s["period_min"], "g_", ms=6)
        ax.plot(i, s["period_max"], "g_", ms=6)
    ax.set_xticks(range(len(labels)), labels, rotation=90, fontsize=6)
    ax.set_ylabel("周期 (TU)")
    ax.set_title("周期范围")
    ax.grid(True, alpha=0.3, axis="y")

    ax = axes[1, 1]
    stability_arr = np.array(all_stability, dtype=float)
    stability_arr = stability_arr[np.isfinite(stability_arr)]
    if stability_arr.size and stability_arr.min() > 0:
        bins = np.logspace(
            np.log10(stability_arr.min()), np.log10(stability_arr.max()), 40
        )
        ax.hist(stability_arr, bins=bins, color="tab:purple", alpha=0.8)
        ax.set_xscale("log")
    else:
        ax.hist(stability_arr, bins=40, color="tab:purple", alpha=0.8)
    ax.set_xlabel("稳定性指数")
    ax.set_ylabel("轨道数量")
    ax.set_title("稳定性指数分布（全部轨道族）")
    ax.grid(True, alpha=0.3)

    fig.tight_layout()

    plot_path = Path(args.plot_save)
    plot_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(plot_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"图片已保存: {plot_path}")

    print("\n=== 汇总 ===")
    print(f"  轨道族数量: {len(statistics)}")
    print(f"  轨道总数: {payload['metadata']['total_orbits']}")
    print("\n完成。")


if __name__ == "__main__":
    main()

# ------------------------------------------------------------------
# GUI 注册
# ------------------------------------------------------------------

from tod.scripting import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='transfer',
    name='analyze_cr3bp_dataset',
    description='CR3BP 数据集统计',
    script_path='tod/transfers/dro_to_geo/analyze_cr3bp_dataset.py',
    output_dir='output',
    group_label='DRO→GEO',
    cli_params=[
        CliParam('--data-dir', '数据目录', 'str', 'data/cr3bp_data/raw', help='CR3BP 原始 XLSX 数据目录。'),
    ],
)
