/**
 * 参数覆写层 (paramOverlay)
 * 来源：docs-old-pyqt-gui-inventory.md B节规范
 */

import type { SchemaProperty, ToolSchema } from "../schema";

export interface UnitOption {
  label: string;
  toStandard: number; // 换算到标准单位的乘数：standardValue = displayValue * toStandard
  decimals: number;
  step: number;
}

/** 17 个可切换单位字段定义（首项为标准单位，toStandard 恒为 1.0） */
export const UNIT_DEFINITIONS: Record<string, UnitOption[]> = {
  // 长度类（标准单位：km）
  amplitude: [
    { label: "km", toStandard: 1.0, decimals: 1, step: 100 },
    { label: "m", toStandard: 1e-3, decimals: 0, step: 1000 },
    { label: "DU", toStandard: 384400, decimals: 6, step: 0.001 },
  ],
  perilune_height: [
    { label: "km", toStandard: 1.0, decimals: 1, step: 50 },
    { label: "m", toStandard: 1e-3, decimals: 0, step: 1000 },
    { label: "DU", toStandard: 384400, decimals: 6, step: 0.001 },
  ],
  amplitude_in: [
    { label: "km", toStandard: 1.0, decimals: 1, step: 100 },
    { label: "m", toStandard: 1e-3, decimals: 0, step: 1000 },
    { label: "DU", toStandard: 384400, decimals: 6, step: 0.001 },
  ],
  amplitude_out: [
    { label: "km", toStandard: 1.0, decimals: 1, step: 100 },
    { label: "m", toStandard: 1e-3, decimals: 0, step: 1000 },
    { label: "DU", toStandard: 384400, decimals: 6, step: 0.001 },
  ],
  semi_major_axis: [
    { label: "km", toStandard: 1.0, decimals: 1, step: 100 },
    { label: "m", toStandard: 1e-3, decimals: 0, step: 1000 },
    { label: "DU", toStandard: 384400, decimals: 6, step: 0.001 },
  ],
  max_amplitude_km: [
    { label: "km", toStandard: 1.0, decimals: 1, step: 500 },
    { label: "m", toStandard: 1e-3, decimals: 0, step: 1000 },
    { label: "DU", toStandard: 384400, decimals: 6, step: 0.001 },
  ],
  min_amplitude_km: [
    { label: "km", toStandard: 1.0, decimals: 1, step: 500 },
    { label: "m", toStandard: 1e-3, decimals: 0, step: 1000 },
    { label: "DU", toStandard: 384400, decimals: 6, step: 0.001 },
  ],
  perilune_height_max_km: [
    { label: "km", toStandard: 1.0, decimals: 1, step: 500 },
    { label: "m", toStandard: 1e-3, decimals: 0, step: 1000 },
    { label: "DU", toStandard: 384400, decimals: 6, step: 0.001 },
  ],
  amplitude_in_km: [
    { label: "km", toStandard: 1.0, decimals: 1, step: 100 },
    { label: "m", toStandard: 1e-3, decimals: 0, step: 1000 },
    { label: "DU", toStandard: 384400, decimals: 6, step: 0.001 },
  ],
  amplitude_out_km: [
    { label: "km", toStandard: 1.0, decimals: 1, step: 100 },
    { label: "m", toStandard: 1e-3, decimals: 0, step: 1000 },
    { label: "DU", toStandard: 384400, decimals: 6, step: 0.001 },
  ],
  match_tolerance_km: [
    { label: "km", toStandard: 1.0, decimals: 4, step: 0.01 },
    { label: "m", toStandard: 1e-3, decimals: 1, step: 10 },
    { label: "DU", toStandard: 384400, decimals: 8, step: 0.00001 },
  ],
  // 相位与角度类
  phase: [
    { label: "周期份额", toStandard: 1.0, decimals: 4, step: 0.05 },
    { label: "度", toStandard: 1 / 360, decimals: 1, step: 5 },
    { label: "弧度", toStandard: 1 / (2 * Math.PI), decimals: 3, step: 0.05 },
  ],
  phase_in: [
    { label: "周期份额", toStandard: 1.0, decimals: 4, step: 0.05 },
    { label: "度", toStandard: 1 / 360, decimals: 1, step: 5 },
    { label: "弧度", toStandard: 1 / (2 * Math.PI), decimals: 3, step: 0.05 },
  ],
  phase_out: [
    { label: "周期份额", toStandard: 1.0, decimals: 4, step: 0.05 },
    { label: "度", toStandard: 1 / 360, decimals: 1, step: 5 },
    { label: "弧度", toStandard: 1 / (2 * Math.PI), decimals: 3, step: 0.05 },
  ],
  inclination: [
    { label: "度", toStandard: 1.0, decimals: 2, step: 1 },
    { label: "rad", toStandard: 180 / Math.PI, decimals: 4, step: 0.01 },
  ],
  arg_of_pericenter: [
    { label: "度", toStandard: 1.0, decimals: 2, step: 1 },
    { label: "rad", toStandard: 180 / Math.PI, decimals: 4, step: 0.01 },
  ],
  // 时间类（标准单位：年 或 秒）
  duration: [
    { label: "年", toStandard: 1.0, decimals: 4, step: 0.05 },
    { label: "月", toStandard: 1 / 12, decimals: 2, step: 0.5 },
    { label: "日", toStandard: 1 / 365.25, decimals: 1, step: 1 },
    { label: "时", toStandard: 1 / (365.25 * 24), decimals: 1, step: 24 },
    { label: "秒", toStandard: 1 / (365.25 * 86400), decimals: 0, step: 86400 },
    { label: "TU", toStandard: 375676.97 / (365.25 * 86400), decimals: 4, step: 0.1 },
  ],
  output_step: [
    { label: "秒", toStandard: 1.0, decimals: 0, step: 60 },
    { label: "时", toStandard: 3600, decimals: 2, step: 0.5 },
    { label: "日", toStandard: 86400, decimals: 4, step: 0.1 },
    { label: "TU", toStandard: 375676.97, decimals: 4, step: 0.01 },
  ],
  control_interval: [
    { label: "天", toStandard: 1.0, decimals: 3, step: 0.1 },
    { label: "秒", toStandard: 1 / 86400, decimals: 0, step: 3600 },
    { label: "TU", toStandard: 375676.97 / 86400, decimals: 4, step: 0.05 },
  ],
  feedback_arc: [
    { label: "天", toStandard: 1.0, decimals: 3, step: 0.1 },
    { label: "秒", toStandard: 1 / 86400, decimals: 0, step: 3600 },
    { label: "TU", toStandard: 375676.97 / 86400, decimals: 4, step: 0.05 },
  ],
  momentum_interval: [
    { label: "天", toStandard: 1.0, decimals: 3, step: 0.5 },
    { label: "秒", toStandard: 1 / 86400, decimals: 0, step: 3600 },
    { label: "TU", toStandard: 375676.97 / 86400, decimals: 4, step: 0.05 },
  ],
};

export function convertValue(
  field: string,
  val: number,
  fromUnit: string,
  toUnit: string
): number {
  const units = UNIT_DEFINITIONS[field];
  if (!units) return val;
  const from = units.find((u) => u.label === fromUnit);
  const to = units.find((u) => u.label === toUnit);
  if (!from || !to) return val;
  const standardVal = val * from.toStandard;
  return standardVal / to.toStandard;
}

export function toStandardValue(field: string, displayVal: number, currentUnit: string): number {
  const units = UNIT_DEFINITIONS[field];
  if (!units) return displayVal;
  const cur = units.find((u) => u.label === currentUnit);
  if (!cur) return displayVal;
  return displayVal * cur.toStandard;
}

export function fromStandardValue(field: string, standardVal: number, targetUnit: string): number {
  const units = UNIT_DEFINITIONS[field];
  if (!units) return standardVal;
  const tgt = units.find((u) => u.label === targetUnit);
  if (!tgt) return standardVal;
  return standardVal / tgt.toStandard;
}

/** 15 种 design_orbit 轨道类型分支默认值 */
export const DESIGN_ORBIT_BRANCH_DEFAULTS: Record<string, Record<string, unknown>> = {
  HALO: { amplitude: 30000, phase: 0.0, collinear_point: 2, north_south: 2 },
  DRO: { amplitude: 60000, phase: 0.5001 },
  DPO: { amplitude: 20000, phase: 0.5001 },
  NRHO: { perilune_height: 5000, north_south: 2, phase: 0.5, collinear_point: 2 },
  LISSAJOUS: { amplitude_in: 2500, amplitude_out: 7500, phase_in: 0.01, phase_out: 0.55, collinear_point: 2 },
  AXIAL: { amplitude: 5000, phase: 0.0, collinear_point: 2 },
  L4: { amplitude_in: 8000, amplitude_out: 6000, phase_in: 0.0, phase_out: 0.0 },
  L5: { amplitude_in: 8000, amplitude_out: 6000, phase_in: 0.0, phase_out: 0.0 },
  L4_SPO: { amplitude: 10000, phase: 0.0 },
  L5_SPO: { amplitude: 10000, phase: 0.0 },
  L4_LPO: { amplitude: 50000, phase: 0.0 },
  L5_LPO: { amplitude: 50000, phase: 0.0 },
  L4_HORSESHOE: { amplitude: 100000, phase: 0.0 },
  L5_HORSESHOE: { amplitude: 100000, phase: 0.0 },
  ELFO: { semi_major_axis: 6500, inclination: 75, arg_of_pericenter: 270, perilune_height: 200 },
};

/** 族生成分支默认值 */
export const FAMILY_BRANCH_DEFAULTS: Record<string, Record<string, unknown>> = {
  HALO: { libration_point: 2, max_amplitude_km: 30000 },
  NRHO: { libration_point: 2, north_south: 2, perilune_height_max_km: 5000 },
  AXIAL: { libration_point: 2, max_amplitude_km: 5000 },
  LISSAJOUS: { libration_point: 2, amplitude_in_km: 2500, amplitude_out_km: 7500, phase_in: 0.01, phase_out: 0.55 },
  SPO: { libration_point: 4, min_amplitude_km: 1737, max_amplitude_km: 75000, continuation_direction: "decrease-x0", match_tolerance_km: 0.01 },
  LPO: { libration_point: 4, min_amplitude_km: 1000, max_amplitude_km: 110000, continuation_direction: "decrease-x0", match_tolerance_km: 0.01 },
  HORSESHOE: { libration_point: 4, min_amplitude_km: 50000, max_amplitude_km: 110000, continuation_direction: "decrease-x0", match_tolerance_km: 0.01 },
  DRO: { min_amplitude_km: 1737, max_amplitude_km: 110000 },
};

export const BRANCH_DEFAULTS: Record<string, Record<string, Record<string, unknown>>> = {
  design_orbit: DESIGN_ORBIT_BRANCH_DEFAULTS,
  orbit_family_generation: FAMILY_BRANCH_DEFAULTS,
};

export function getBranchDefaults(toolName: string, branchType: string): Record<string, unknown> {
  return BRANCH_DEFAULTS[toolName]?.[branchType] ?? {};
}

/** 整数枚举中文/英文标签映射 */
export const ENUM_OPTIONS: Record<string, { label: string; value: number | string }[]> = {
  collinear_point: [
    { label: "1 (L1)", value: 1 },
    { label: "2 (L2)", value: 2 },
    { label: "3 (L3)", value: 3 },
  ],
  libration_point: [
    { label: "1 (L1)", value: 1 },
    { label: "2 (L2)", value: 2 },
    { label: "3 (L3)", value: 3 },
    { label: "4 (L4)", value: 4 },
    { label: "5 (L5)", value: 5 },
  ],
  north_south: [
    { label: "1 (北族 Class I)", value: 1 },
    { label: "2 (南族 Class II)", value: 2 },
  ],
  is_nrho: [
    { label: "0 (否)", value: 0 },
    { label: "1 (是)", value: 1 },
  ],
  special_mode: [
    { label: "1 (Lissajous ẋ=0)", value: 1 },
    { label: "2 (Halo/NRHO ẋ=0, ż=0)", value: 2 },
  ],
  control_mode: [
    { label: "1 目标点控制（宽松）", value: 1 },
    { label: "2 目标点控制（严格）", value: 2 },
    { label: "3 特征点控制", value: 3 },
    { label: "4 目标点控制 + 角动量管理", value: 4 },
    { label: "5 目标点严格控制 + 角动量管理", value: 5 },
    { label: "6 特征点控制 + 角动量管理", value: 6 },
  ],
  continuation_direction: [
    { label: "decrease-x0", value: "decrease-x0" },
    { label: "increase-x0", value: "increase-x0" },
  ],
  correction_method: [
    { label: "two_level (双层打靶)", value: "two_level" },
  ],
};

/** 字段多行 Tooltip 提示表 */
export const FIELD_TOOLTIPS: Record<string, string> = {
  orbit_type: "轨道族或轨道类型。不同轨道类型将激活对应参数集与默认初猜值。",
  amplitude: "轨道主振幅（km）。Halo 为 z 向振幅；DRO/DPO/Axial 为 x/y 向振幅；北族取正、南族取负。",
  phase: "轨道初始相位（0~1 周期份额）。DRO/DPO 默认 0.5001；NRHO 默认 0.5；Halo 默认 0.0。",
  collinear_point: "共线平动点编号：1=L1, 2=L2, 3=L3。",
  north_south: "Halo / NRHO 轨道的南北族分类：1=北族 (Class I, z>0), 2=南族 (Class II, z<0)。",
  perilune_height: "近月点高度（km）。NRHO 轨道通常在 1000~10000 km 之间。",
  semi_major_axis: "半长轴（km）。ELFO 轨道必填，默认 6500 km。",
  inclination: "轨道倾角（度）。0~180 度，ELFO 默认 75 度。",
  arg_of_pericenter: "近月点幅角（度）。0~360 度，ELFO 默认 270 度。",
  duration: "传播/积分时长。GUI 默认以年/月输入，提交时换算为秒。",
  output_step: "轨迹输出步长（秒）。默认 3600 秒（1小时）。",
  correction_method: "星历修正方法：two_level（Rust 多重打靶 + 速度加权，稳定轨道默认）；不稳定轨道由算法自动切换分段打靶拼接 (segmented)。",
  perturbation: "天体摄动力开关字典 JSON，例如 {\"sun_body\": 1, \"planets\": 1}（留空表示默认全开）。",
  dyb: "9 分量光压面质比与摄动系数数组，dyb[0] 为等效面质比 m²/kg（留空表示默认）。",
  n_orbits: "生成的族成员轨道数量上限（1~100，默认 50）。",
  num_controls: "站保控制次数上限（1~10000，默认 120）。",
  num_monte_carlo: "蒙特卡洛仿真样本数（1~1000，默认 5；生产通常设 100）。",
  tight_tolerance_km: "严格位置控制容差（km），默认 0.1 km。",
  control_interval: "站保控制评估间隔（天），默认 0.25 天（短弧）。",
  feedback_arc: "站保反馈弧段时长（天），默认 0.125 天。",
};

/** 格式化范围占位提示 */
export function formatRangePrompt(
  min: number | undefined,
  max: number | undefined,
  unitLabel: string
): string {
  if (min !== undefined && max !== undefined) {
    return `可填范围: ${min} ~ ${max} ${unitLabel}`;
  }
  if (min !== undefined) {
    return `可填范围: ≥ ${min} ${unitLabel}`;
  }
  if (max !== undefined) {
    return `可填范围: ≤ ${max} ${unitLabel}`;
  }
  return "无范围约束";
}

/** 动态计算字段适用性（取代原有的硬表，支持 design_orbit 全部 15 种类型） */
export function getFieldApplicability(toolName: string, orbitType: string): string[] {
  if (toolName === "orbit_family_generation") {
    const common = ["orbit_type", "libration_point", "n_orbits"];
    const specific: Record<string, string[]> = {
      HALO: ["max_amplitude_km"],
      NRHO: ["north_south", "perilune_height_max_km", "continuation_direction"],
      AXIAL: ["max_amplitude_km"],
      LISSAJOUS: ["amplitude_in_km", "amplitude_out_km", "phase_in", "phase_out"],
      SPO: ["max_amplitude_km", "min_amplitude_km", "continuation_direction", "match_tolerance_km"],
      LPO: ["max_amplitude_km", "min_amplitude_km", "continuation_direction", "match_tolerance_km"],
      HORSESHOE: ["max_amplitude_km", "min_amplitude_km", "continuation_direction", "match_tolerance_km"],
      DRO: ["max_amplitude_km", "min_amplitude_km"],
    };
    const fields = [...common, ...(specific[orbitType] ?? [])];
    if (orbitType === "DRO") {
      return fields.filter((f) => f !== "libration_point");
    }
    return fields;
  }

  if (toolName === "design_orbit") {
    // design_orbit 公共字段
    const common = [
      "orbit_type",
      "epoch",
      "duration",
      "output_step",
      "perturbation",
      "dyb",
      "earth_degree",
      "moon_degree",
      "correction_method",
      "correction_revolutions",
    ];

    const specific: Record<string, string[]> = {
      HALO: ["amplitude", "phase", "collinear_point", "north_south"],
      DRO: ["amplitude", "phase"],
      DPO: ["amplitude", "phase"],
      NRHO: ["perilune_height", "north_south", "phase", "collinear_point"],
      LISSAJOUS: ["amplitude_in", "amplitude_out", "phase_in", "phase_out", "collinear_point"],
      AXIAL: ["amplitude", "phase", "collinear_point"],
      L4: ["amplitude_in", "amplitude_out", "phase_in", "phase_out"],
      L5: ["amplitude_in", "amplitude_out", "phase_in", "phase_out"],
      L4_SPO: ["amplitude", "phase"],
      L5_SPO: ["amplitude", "phase"],
      L4_LPO: ["amplitude", "phase"],
      L5_LPO: ["amplitude", "phase"],
      L4_HORSESHOE: ["amplitude", "phase"],
      L5_HORSESHOE: ["amplitude", "phase"],
      ELFO: ["semi_major_axis", "inclination", "arg_of_pericenter", "perilune_height"],
    };

    return [...(specific[orbitType] ?? ["amplitude", "phase"]), ...common];
  }

  return [];
}

/** 当前工具+轨道类型下可见（参与表单渲染与校验）的字段列表，表单与提交校验同源 */
export function getActiveFields(toolName: string, schema: ToolSchema, orbitType: string): string[] {
  if (toolName === "orbit_stability") {
    return ["orbit_record_id", "dynamics_model"];
  }
  const applicability = getFieldApplicability(toolName, orbitType);
  if (applicability.length > 0) {
    return applicability.filter((f) => schema.properties[f]);
  }
  return Object.keys(schema.properties);
}

export interface ParamIssue {
  field: string;
  label: string;
  reason: string;
}

/** 提交前防呆校验：必填缺失与数值越界（值为标准物理单位，直接对照 schema 范围） */
export function validateToolParams(
  toolName: string,
  schema: ToolSchema,
  values: Record<string, unknown>,
): ParamIssue[] {
  const orbitType = (values["orbit_type"] as string) || "HALO";
  const issues: ParamIssue[] = [];

  for (const field of getActiveFields(toolName, schema, orbitType)) {
    const prop = schema.properties[field];
    // 与 ParamsPanel 相同的 anyOf 展开：可空字段的约束在非 null 分支
    const isOptional = prop.anyOf?.some((v) => v.type === "null") ?? false;
    const inner: SchemaProperty = isOptional
      ? prop.anyOf!.find((v) => v.type !== "null") || prop
      : prop;
    const label = prop.title || field;
    const value = values[field];

    if (value === null || value === undefined || value === "") {
      if (schema.required?.includes(field)) {
        issues.push({ field, label, reason: "必填，当前为空" });
      }
      continue;
    }

    if (typeof value === "number" && !Number.isNaN(value)) {
      const { minimum, maximum, exclusiveMinimum, exclusiveMaximum } = inner;
      const bounds: string[] = [];
      if (minimum !== undefined && value < minimum) bounds.push(`≥ ${minimum}`);
      if (exclusiveMinimum !== undefined && value <= exclusiveMinimum) bounds.push(`> ${exclusiveMinimum}`);
      if (maximum !== undefined && value > maximum) bounds.push(`≤ ${maximum}`);
      if (exclusiveMaximum !== undefined && value >= exclusiveMaximum) bounds.push(`< ${exclusiveMaximum}`);
      if (bounds.length > 0) {
        issues.push({ field, label, reason: `${value} 超出可填范围: ${bounds.join(" 且 ")}` });
      }
    }
  }
  return issues;
}
