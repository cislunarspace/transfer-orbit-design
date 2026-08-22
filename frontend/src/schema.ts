// JSON Schema → 表单（对齐 PyQt 版 params_panel 的映射约定）。
// schema 来源：frontend/src/toolSchemas/*.json（tools/export_tool_schemas.py 导出）。

import familySchema from "./toolSchemas/orbit_family_generation.json";

export interface SchemaProperty {
  type?: string;
  description?: string;
  enum?: (string | number)[];
  anyOf?: { type?: string; enum?: (string | number)[] }[];
  default?: unknown;
  minimum?: number;
  maximum?: number;
  exclusiveMinimum?: number;
  exclusiveMaximum?: number;
}

export interface ToolSchema {
  properties: Record<string, SchemaProperty>;
  required?: string[];
}

/** 族按 orbit_type 的适用字段（schema description 里的分派规则，硬表驱动）。
 *  未列出的公共字段（orbit_type/libration_point/n_orbits）各族通用。 */
const FAMILY_FIELDS: Record<string, string[]> = {
  HALO: ["max_amplitude_km"],
  NRHO: ["north_south", "perilune_height_max_km", "continuation_direction"],
  AXIAL: ["max_amplitude_km"],
  LISSAJOUS: ["amplitude_in_km", "amplitude_out_km", "phase_in", "phase_out"],
  SPO: ["max_amplitude_km", "min_amplitude_km", "continuation_direction", "match_tolerance_km"],
  LPO: ["max_amplitude_km", "min_amplitude_km", "continuation_direction", "match_tolerance_km"],
  HORSESHOE: ["max_amplitude_km", "min_amplitude_km", "continuation_direction", "match_tolerance_km"],
  DRO: ["max_amplitude_km", "min_amplitude_km"],
};

const ORBIT_TYPES = Object.keys(FAMILY_FIELDS);

/** 当前 orbit_type 下适用的字段集（公共字段 + 族特定字段）。 */
export function applicableFields(schema: ToolSchema, orbitType: string): string[] {
  const common = ["orbit_type", "libration_point", "n_orbits"];
  const specific = FAMILY_FIELDS[orbitType] ?? [];
  return [...common, ...specific].filter((f) => schema.properties[f]);
}

export function familyGenerationSchema(): ToolSchema {
  return familySchema as unknown as ToolSchema;
}

export { ORBIT_TYPES };
