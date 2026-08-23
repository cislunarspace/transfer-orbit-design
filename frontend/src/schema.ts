// JSON Schema → 表单（对齐 PyQt 版 params_panel 的映射约定）。
// schema 来源：frontend/src/toolSchemas/*.json（tools/export_tool_schemas.py 导出）。

import familySchema from "./toolSchemas/orbit_family_generation.json";
import designOrbitSchema from "./toolSchemas/design_orbit.json";
import controlOrbitSchema from "./toolSchemas/control_orbit.json";
import propagationSchema from "./toolSchemas/orbit_propagation.json";
import transferSchema from "./toolSchemas/transfer_design.json";
import stabilitySchema from "./toolSchemas/orbit_stability.json";
import transformSchema from "./toolSchemas/spacetime_transform.json";

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
  items?: SchemaProperty;
  minItems?: number;
  maxItems?: number;
  [key: string]: unknown;
}

export interface ToolSchema {
  properties: Record<string, SchemaProperty>;
  type?: string;
  description?: string;
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
  if (!schema.properties.orbit_type) return Object.keys(schema.properties);
  const common = ["orbit_type", "libration_point", "n_orbits"];
  const specific = FAMILY_FIELDS[orbitType] ?? [];
  return [...common, ...specific].filter((f) => schema.properties[f]);
}

export function familyGenerationSchema(): ToolSchema {
  return familySchema as unknown as ToolSchema;
}

export { ORBIT_TYPES };

export interface ToolEntry {
  name: string;
  title: string;
  schema: ToolSchema;
  binaryDtype?: "f32" | "f64";
  artifactType?: string;
  hasTrajectory?: boolean;
}

export const TOOL_REGISTRY: ToolEntry[] = [
  { name: "orbit_family_generation", title: "轨道族生成", schema: familySchema as ToolSchema, binaryDtype: "f32", artifactType: "family", hasTrajectory: true },
  { name: "design_orbit", title: "任务轨道设计", schema: designOrbitSchema as ToolSchema, artifactType: "orbit", hasTrajectory: true },
  { name: "control_orbit", title: "轨道保持", schema: controlOrbitSchema as ToolSchema, artifactType: "ephemeris", hasTrajectory: true },
  { name: "orbit_propagation", title: "轨道预报", schema: propagationSchema as ToolSchema, artifactType: "ephemeris", hasTrajectory: true },
  { name: "transfer_design", title: "转移轨道设计", schema: transferSchema as ToolSchema, artifactType: "transfer", hasTrajectory: true },
  { name: "orbit_stability", title: "轨道稳定性", schema: stabilitySchema as ToolSchema, artifactType: "orbit" },
  { name: "spacetime_transform", title: "时空坐标转换", schema: transformSchema as ToolSchema, artifactType: "orbit", hasTrajectory: true },
];

export function toolEntry(name: string): ToolEntry {
  const entry = TOOL_REGISTRY.find((item) => item.name === name);
  if (!entry) throw new Error(`未知工具: ${name}`);
  return entry;
}
