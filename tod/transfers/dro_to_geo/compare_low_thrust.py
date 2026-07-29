"""DRO→GEO 小推力转移简单验证（方案 A）。

对比纯脉冲 vs 小推力的燃料消耗。
使用已有的分段打靶结果作为基准，应用小推力模型计算燃料消耗。

推进系统参数（来自文献）：
- 化学推进（脉冲）：Isp = 400 s，T = 10 N（关宇同 2026）
- 电推进（小推力）：Isp = 3000 s，T = 1 N（潘迅 2019，NSTAR）
- 航天器质量：1500 kg（Caillau 2012）
"""

import json
import numpy as np
from pathlib import Path

# 推进系统参数
CHEMICAL_ISP = 400.0  # s
ELECTRIC_ISP = 3000.0  # s
ELECTRIC_T_MAX = 1.0  # N
SPACECRAFT_MASS = 1500.0  # kg
G0 = 9.81  # m/s²


def compute_impulsive_propellant(delta_v_ms: float, mass_before: float) -> float:
    """计算脉冲推力燃料消耗（火箭方程）。

    Args:
        delta_v_ms: 速度增量（m/s）
        mass_before: 初始质量（kg）

    Returns:
        燃料质量（kg）
    """
    # Δv = Isp * g0 * ln(m_before / m_after)
    # m_after = m_before * exp(-Δv / (Isp * g0))
    # m_prop = m_before - m_after
    mass_after = mass_before * np.exp(-delta_v_ms / (CHEMICAL_ISP * G0))
    return mass_before - mass_after


def compute_electric_propellant(delta_v_ms: float, mass_before: float) -> float:
    """计算电推进燃料消耗（火箭方程）。

    Args:
        delta_v_ms: 速度增量（m/s）
        mass_before: 初始质量（kg）

    Returns:
        燃料质量（kg）
    """
    mass_after = mass_before * np.exp(-delta_v_ms / (ELECTRIC_ISP * G0))
    return mass_before - mass_after


def compute_electric_transfer_time(delta_v_ms: float, mass_avg: float) -> float:
    """计算电推进转移时间。

    注意：这是一个粗略估算。实际小推力转移时间取决于：
    1. 推力方向与速度方向的夹角
    2. 是否存在滑行段（coast phase）
    3. 轨迹优化程度

    参考文献：
    - Caillau et al. (2012): GEO→L1, 0.3 N, 8个月5天 (~250 天)
    - SMART-1: 0.07 N, 13个月 (~400 天)
    - 典型小推力转移时间：3-5倍于理想最小时间

    Args:
        delta_v_ms: 速度增量（m/s）
        mass_avg: 平均质量（kg）

    Returns:
        转移时间（天）
    """
    # 加速度：a = T / m
    acceleration = ELECTRIC_T_MAX / mass_avg  # m/s²
    # 理想最小时间：t = Δv / a
    ideal_time_s = delta_v_ms / acceleration
    # 实际时间估算：考虑推力方向损失和滑行段，乘以 3 倍因子（保守估计）
    realistic_time_s = ideal_time_s * 3.0
    return realistic_time_s / 86400.0  # 转换为天


def main():
    # 读取纯脉冲结果
    opt_file = Path("output/transfer/corrected_transfer_1785255430.json")
    with open(opt_file) as fp:
        data = json.load(fp)

    cr3bp = data.get("cr3bp", {})
    delta_v_ms = cr3bp.get("objective_value_m_s", 0)  # m/s
    transfer_days = cr3bp.get("transfer_time_days", 0)

    print("=" * 60)
    print("DRO→GEO 转移：纯脉冲 vs 小推力对比")
    print("=" * 60)

    # 纯脉冲结果
    print("\n【纯脉冲（化学推进）】")
    print(f"  Δv: {delta_v_ms:.0f} m/s")
    print(f"  转移时间: {transfer_days:.1f} 天")

    prop_impulsive = compute_impulsive_propellant(delta_v_ms, SPACECRAFT_MASS)
    print(f"  燃料消耗: {prop_impulsive:.1f} kg")
    print(f"  燃料占比: {prop_impulsive / SPACECRAFT_MASS * 100:.1f}%")

    # 小推力结果（假设相同的 Δv）
    print("\n【小推力（电推进）】")
    print(f"  Δv: {delta_v_ms:.0f} m/s（假设相同）")

    prop_electric = compute_electric_propellant(delta_v_ms, SPACECRAFT_MASS)
    time_electric = compute_electric_transfer_time(delta_v_ms, SPACECRAFT_MASS - prop_electric / 2)

    print(f"  燃料消耗: {prop_electric:.1f} kg")
    print(f"  燃料占比: {prop_electric / SPACECRAFT_MASS * 100:.1f}%")
    print(f"  估算转移时间: {time_electric:.1f} 天（假设连续推力）")

    # 对比
    print("\n【对比】")
    fuel_saving = prop_impulsive - prop_electric
    fuel_saving_pct = fuel_saving / prop_impulsive * 100
    time_increase = time_electric - transfer_days
    time_increase_pct = time_increase / transfer_days * 100

    print(f"  燃料节省: {fuel_saving:.1f} kg ({fuel_saving_pct:.1f}%)")
    print(f"  时间增加: {time_increase:.1f} 天 ({time_increase_pct:.1f}%)")

    # 混合推进策略
    print("\n【混合推进策略】")
    print("  策略：化学推进用于大轨道改变，电推进用于精细调整")
    print("  - DRO 逃逸：化学推进（~500 m/s）")
    print("  - 中间转移：电推进（~500 m/s）")
    print("  - GEO 插入：化学推进（~500 m/s）")

    # 估算混合推进燃料消耗
    dv_chemical = 500.0  # m/s（化学推进部分）
    dv_electric = delta_v_ms - 2 * dv_chemical  # m/s（电推进部分）

    if dv_electric > 0:
        prop_hybrid_chem = 2 * compute_impulsive_propellant(dv_chemical, SPACECRAFT_MASS)
        prop_hybrid_elec = compute_electric_propellant(dv_electric, SPACECRAFT_MASS - prop_hybrid_chem)
        prop_hybrid = prop_hybrid_chem + prop_hybrid_elec

        print(f"\n  化学推进燃料: {prop_hybrid_chem:.1f} kg")
        print(f"  电推进燃料: {prop_hybrid_elec:.1f} kg")
        print(f"  总燃料: {prop_hybrid:.1f} kg")
        print(f"  vs 纯脉冲节省: {(prop_impulsive - prop_hybrid) / prop_impulsive * 100:.1f}%")
        print(f"  vs 纯电推增加: {(prop_hybrid - prop_electric) / prop_electric * 100:.1f}%")

    print("\n" + "=" * 60)

    # 保存结果
    result = {
        "impulsive": {
            "delta_v_ms": delta_v_ms,
            "transfer_days": transfer_days,
            "propellant_kg": prop_impulsive,
            "propellant_pct": prop_impulsive / SPACECRAFT_MASS * 100,
        },
        "electric": {
            "delta_v_ms": delta_v_ms,
            "transfer_days_estimated": time_electric,
            "propellant_kg": prop_electric,
            "propellant_pct": prop_electric / SPACECRAFT_MASS * 100,
        },
        "comparison": {
            "fuel_saving_kg": fuel_saving,
            "fuel_saving_pct": fuel_saving_pct,
            "time_increase_days": time_increase,
            "time_increase_pct": time_increase_pct,
        },
        "propulsion_params": {
            "chemical_isp_s": CHEMICAL_ISP,
            "electric_isp_s": ELECTRIC_ISP,
            "electric_t_max_n": ELECTRIC_T_MAX,
            "spacecraft_mass_kg": SPACECRAFT_MASS,
        },
    }

    output_file = Path("output/transfer/low_thrust_comparison.json")
    with open(output_file, "w") as fp:
        json.dump(result, fp, indent=2, ensure_ascii=False)

    print(f"\n结果已保存: {output_file}")


if __name__ == "__main__":
    main()
