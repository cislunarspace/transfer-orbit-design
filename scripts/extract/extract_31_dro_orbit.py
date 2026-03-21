"""
提取3:1远距逆行轨道(DRO) - 31周期比

从轨道族JSON文件中提取T/T_moon ≈ 3.0的远距逆行轨道。

用法:
    python extract_31_dro_orbit.py
"""

import sys
import glob
import json
from pathlib import Path
from fontTools.misc.timeTools import timestampNow


# 修正：将项目根目录设置为 transfer-orbit-design 根目录
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import e2m2e
from scripts.utils.common import T_MOON

# =============================================================================
# 主流程
# =============================================================================
TARGET_RATIO = 3.0  # 3:1 共振
TOLERANCE = 0.05
# =============================================================================
# 输入文件指定
# =============================================================================
# 可指定具体文件名或带 * 的 glob 模式：
#   - 具体文件: "dro_family_0.6-0.8-0.005_3856914009.json"
#   - glob模式: "dro_family_*.json"
INPUT_FILE = "dro_family_0.6-0.8-0.005_3856915870"
# =============================================================================
INPUT_PATTERN = project_root / "output" / "dro" / f"{INPUT_FILE}.json"

output_base = project_root / "dro" / "31"

print(f"轨道类型: dro")
print(f"目标周期比: 31 (T/T_moon ≈ {TARGET_RATIO})")
print(f"容差: {TOLERANCE}")
print(f"输入文件: {INPUT_FILE}")
all_matching_orbits = []
family_data = e2m2e.core.orbit.OrbitFamily.load_from_file(INPUT_PATTERN)
print(f"  轨道族包含 {len(family_data.orbits)} 条轨道")

matching = []
for i, orbit in enumerate(family_data.orbits):
    if orbit.period is None:
        continue
    period_ratio = T_MOON / orbit.period
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
                "source_file": INPUT_FILE,
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
