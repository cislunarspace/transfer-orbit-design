"""
提取3:2共振轨道(RO) - 32周期比

从轨道族JSON文件中提取T/T_moon ≈ 1.5的共振轨道。

用法:
    python extract_32_ro_orbit.py
"""

import sys
import glob
import json
from pathlib import Path
from fontTools.misc.timeTools import timestampNow

# 将项目根目录添加到 sys.path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import e2m2e
from scripts.utils.common import T_MOON

OUTPUT_DIR = project_root / "output"

# =============================================================================
# 主流程
# =============================================================================
ORBIT_TYPE = "ro"
TARGET_RATIO = 1.5  # 3:2 共振
TOLERANCE = 0.05
# =============================================================================
# 输入文件指定
# =============================================================================
# 可指定具体文件名或带 * 的 glob 模式：
#   - 具体文件: "ro_32_family_-0.9305--0.8304999999999999-0.001_3856908879.json"
#   - glob模式: "ro_32_family_*.json"
INPUT_FILE = "ro_32_family_*.json"
# =============================================================================

INPUT_PATTERN = str(OUTPUT_DIR / "ro" / INPUT_FILE)

output_base = OUTPUT_DIR / ORBIT_TYPE / "32"

print(f"轨道类型: {ORBIT_TYPE}")
print(f"目标周期比: 32 (T/T_moon ≈ {TARGET_RATIO})")
print(f"容差: {TOLERANCE}")
print(f"输入文件: {INPUT_FILE}")

input_files = glob.glob(INPUT_PATTERN)
if not input_files:
    raise FileNotFoundError(f"未找到匹配的文件: {INPUT_PATTERN}")

print(f"\n找到 {len(input_files)} 个轨道族文件:")
for f in input_files:
    print(f"  - {f}")

all_matching_orbits = []

for input_file in input_files:
    print(f"\n处理文件: {input_file}")

    family_data = e2m2e.core.orbit.OrbitFamily.load_from_file(input_file)
    print(f"  轨道族包含 {len(family_data.orbits)} 条轨道")

    matching = []
    for i, orbit in enumerate(family_data.orbits):
        if orbit.period is None:
            continue
        period_ratio = orbit.period / T_MOON
        if abs(period_ratio - TARGET_RATIO) <= TOLERANCE:
            matching.append(
                {
                    "index": i,
                    "orbit": orbit,
                    "period_ratio": period_ratio,
                    "period": orbit.period,
                }
            )

    if matching:
        print(f"  找到 {len(matching)} 条匹配轨道:")
        for m in matching:
            print(
                f"    索引 {m['index']}: 周期比 = {m['period_ratio']:.6f}, 周期 = {m['period']:.6f} TU"
            )
            all_matching_orbits.append(
                {
                    "source_file": input_file,
                    "orbit_index": m["index"],
                    "period_ratio": m["period_ratio"],
                    "period": m["period"],
                    "orbit": m["orbit"],
                }
            )
    else:
        print(f"  未找到匹配轨道")

# =============================================================================
# 保存或显示结果
# =============================================================================
if not all_matching_orbits:
    print("\n错误: 未找到任何匹配的轨道")
    sys.exit(1)

print(f"\n总计找到 {len(all_matching_orbits)} 条匹配轨道")

DRY_RUN = False  # 设为 True 则仅显示结果，不保存文件

if DRY_RUN:
    print("\n[Dry Run] 不保存文件")
else:
    output_base.mkdir(parents=True, exist_ok=True)
    timestamp = timestampNow()

    for i, match in enumerate(all_matching_orbits):
        orbit = match["orbit"]
        period_ratio_str = f"{match['period_ratio']:.4f}".replace(".", "p")
        output_filename = f"{ORBIT_TYPE}_32_{period_ratio_str}_idx{match['orbit_index']}_{timestamp}.json"
        output_path = output_base / output_filename

        orbit_dict = {
            "states": orbit.states.tolist(),
            "times": orbit.times.tolist(),
            "metadata": getattr(orbit, "metadata", {}),
            "properties": {
                "period": orbit.period,
                "amplitudes": orbit.amplitudes,
                "extrema": orbit.extrema,
                "mean_state": orbit.mean_state.tolist()
                if orbit.mean_state is not None
                else None,
                "family_type": orbit.family_type,
                "is_periodic": orbit.is_periodic,
                "periodicity_error": getattr(orbit, "periodicity_error", None),
            },
        }

        with open(output_path, "w") as f:
            json.dump(orbit_dict, f, indent=2)

        print(f"  保存: {output_path}")

    print(f"\n结果已保存到: {output_base}")
