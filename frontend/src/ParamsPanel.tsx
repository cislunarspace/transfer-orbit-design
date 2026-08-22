// 参数面板：从工具 schema 生成表单（阶段 3，首个工具 orbit_family_generation）。

import { useMemo, useState } from "react";
import { type SchemaProperty, type ToolSchema, applicableFields, ORBIT_TYPES } from "./schema";

interface FieldProps {
  name: string;
  prop: SchemaProperty;
  value: unknown;
  onChange: (v: unknown) => void;
}

/** 单字段控件：Optional 勾选 + 类型化输入（对齐 PyQt 版映射约定）。 */
function Field({ name, prop, value, onChange }: FieldProps) {
  const isOptional = prop.anyOf?.some((v) => v.type === "null") ?? false;
  const [enabled, setEnabled] = useState(!isOptional || value !== null);
  const inner: SchemaProperty = isOptional
    ? prop.anyOf!.find((v) => v.type !== "null")!
    : prop;
  const hasEnum = inner.enum !== undefined;

  const control = (() => {
    if (hasEnum) {
      return (
        <select value={String(value ?? inner.enum![0])} onChange={(e) => onChange(e.target.value)}>
          {inner.enum!.map((v) => (
            <option key={String(v)} value={String(v)}>{String(v)}</option>
          ))}
        </select>
      );
    }
    if (inner.type === "number" || inner.type === "integer") {
      return (
        <input
          type="number"
          value={value === null || value === undefined ? "" : Number(value)}
          min={inner.minimum}
          max={inner.maximum}
          onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
        />
      );
    }
    const isArray = inner.type === "array" || inner.type === "object" || !inner.type;
    return (
      <input
        type="text"
        value={value === null || value === undefined ? "" : isArray ? JSON.stringify(value) : String(value)}
        placeholder={isArray ? "JSON" : undefined}
        onChange={(e) => {
          if (!isArray) return onChange(e.target.value);
          try { onChange(JSON.parse(e.target.value)); } catch { onChange(e.target.value); }
        }}
      />
    );
  })();

  return (
    <label style={{ display: "block", marginBottom: 6, fontSize: 12 }}>
      {isOptional && (
        <input
          type="checkbox"
          checked={enabled}
          style={{ marginRight: 6 }}
          onChange={(e) => {
            setEnabled(e.target.checked);
            onChange(e.target.checked ? (inner.default ?? null) : null);
          }}
        />
      )}
      <span style={{ display: "inline-block", minWidth: 140 }}>{name}</span>
      {enabled ? control : <span style={{ color: "#666" }}>（未设置）</span>}
      {prop.description && (
        <div style={{ color: "#888", fontSize: 11, marginLeft: isOptional ? 22 : 0 }}>
          {prop.description.split("\n")[0]}
        </div>
      )}
    </label>
  );
}

export interface ParamsPanelProps {
  schema: ToolSchema;
  params: Record<string, unknown>;
  onParamsChange: (p: Record<string, unknown>) => void;
}

/** orbit_type 切换时裁剪字段（不适用的字段剔除，与 e2m2e 校验规则一致）。 */
export function ParamsPanel({ schema, params, onParamsChange }: ParamsPanelProps) {
  const isFamily = Boolean(schema.properties.orbit_type);
  const orbitType = String(params.orbit_type ?? "HALO");
  const fields = useMemo(() => applicableFields(schema, orbitType), [schema, orbitType]);

  return (
    <div>
      {isFamily && <>
      {/* orbit_type 单独渲染为下拉（驱动字段裁剪） */}
      <label style={{ display: "block", marginBottom: 8, fontSize: 12 }}>
        <span style={{ display: "inline-block", minWidth: 140 }}>orbit_type</span>
        <select
          value={orbitType}
          onChange={(e) => {
            const next: Record<string, unknown> = { orbit_type: e.target.value };
            // 只保留新类型下仍适用的字段
            for (const f of applicableFields(schema, e.target.value)) {
              if (f !== "orbit_type" && params[f] !== undefined && params[f] !== null) {
                next[f] = params[f];
              }
            }
            onParamsChange(next);
          }}
        >
          {ORBIT_TYPES.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </label>
      </>}
      {fields
        .filter((f) => f !== "orbit_type")
        .map((f) => (
          <Field
            key={f}
            name={f}
            prop={schema.properties[f]}
            value={params[f] ?? null}
            onChange={(v) => onParamsChange({ ...params, [f]: v })}
          />
        ))}
    </div>
  );
}
