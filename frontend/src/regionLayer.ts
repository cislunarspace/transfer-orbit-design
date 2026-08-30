// 地月空间分区图层：e2m2e spatiography_boundaries 响应 → 画布区域元素。
// The cislunar partition region layer: e2m2e spatiography_boundaries response → canvas region elements.
//
// 界面不碰算法：本模块只做单位归一（物理 km ÷ DU_KM）与画布对齐，不做任何
// 数值计算；边界几何（圆 / Battin 非对称曲线 / 平动点）全部由 e2m2e 离散化后给出。
// The UI never computes: this module only normalizes units (physical km ÷ DU_KM) and aligns to
// the canvas; all boundary geometry (circles / Battin asymmetric curve / libration points) is
// pre-discretized by e2m2e.

import { DU_KM } from "./cr3bp";

/** 画布区域元素（DU 归一）。 */
/** A canvas region element (normalized to DU). */
export interface RegionElement {
  /** 元素类型：circle=闭合圆族折线，polyline=闭合非对称曲线，point=点标记 */
  /** Element kind: circle=closed circle polyline, polyline=closed asymmetric curve, point=marker. */
  kind: "circle" | "polyline" | "point";
  label: string;
  /** 圆心/点位置（画布会合系 DU） */
  /** Center/position in canvas synodic DU. */
  centerDU: [number, number, number];
  /** 圆半径（DU）；仅 circle/polyline */
  /** Circle radius (DU); circle/polyline only. */
  radiusDU?: number;
  /** 离散折线点（DU，z=0 平面，首尾闭合） */
  /** Discrete polyline points (DU, z=0 plane, closed). */
  pointsDU?: [number, number, number][];
  /** 论文式号/表出处（调试与提示用） */
  /** Paper formula/table provenance (for tooltips/debugging). */
  formulaId?: string;
}

/** e2m2e spatiography_boundaries 响应里的单个元素（km 域，snake_case 直传）。 */
/** One element from the e2m2e spatiography_boundaries response (km domain, snake_case as sent). */
export interface BoundaryElementPayload {
  kind: string;
  label: string;
  formula_id?: string;
  center_km?: number[] | null;
  radius_km?: number | null;
  points_km?: number[][] | null;
  /** (a,e) 根数空间曲线点（三维画布不消费，类型上保留以对齐响应） */
  /** (a,e) element-space curve points (unused by the 3D canvas; kept for response parity). */
  points_ae?: number[][] | null;
  /** (a,e) 竖直线位置（三维画布不消费） */
  /** (a,e) vertical-line position (unused by the 3D canvas). */
  a_km?: number | null;
}

const toDU = (p: number[]): [number, number, number] => [p[0] / DU_KM, p[1] / DU_KM, p[2] / DU_KM];

/**
 * km 响应 → 画布区域元素。
 * km response → canvas region elements.
 *
 * (a,e) 根数空间元素（curve_ae/vertical_ae）不进三维画布，跳过。圆/曲线的
 * 圆心吸附：后端以 Primer 物理常数（a☾=383397.7725 km）给绝对 km，而画布
 * 天体固定在 (0,0)/(1−mu,0)（DU=384400 口径）——把圆心吸附到最近天体的
 * 规范位置，避免 ~0.26% 的中心错位（与 ÷DU_KM 既有容差同源）；点标记
 * （平动点）为绝对位置，不吸附。
 * Element-space entries (curve_ae/vertical_ae) are skipped — they are not 3D-canvas geometry.
 * Center snapping for circles/curves: the backend emits absolute km with Primer constants
 * (a☾=383397.7725 km) while canvas bodies sit at (0,0)/(1−mu,0) (DU=384400) — snap each center
 * to the nearest body's canonical position to avoid a ~0.26% offset (same tolerance class as the
 * established ÷DU_KM convention); point markers (libration points) are absolute and never snapped.
 */
export function boundariesResponseToRegionLayer(
  payload: { elements?: BoundaryElementPayload[] },
  mu: number,
): RegionElement[] {
  const moonX = 1 - mu;
  const out: RegionElement[] = [];
  for (const el of payload.elements ?? []) {
    if (el.kind !== "circle" && el.kind !== "polyline" && el.kind !== "point") continue;
    if (!el.center_km || el.center_km.length < 3) continue;
    const rawCenter = toDU(el.center_km);
    const formulaId = el.formula_id;
    if (el.kind === "point") {
      out.push({ kind: "point", label: el.label, centerDU: rawCenter, formulaId });
      continue;
    }
    if (el.radius_km == null || !el.points_km || el.points_km.length < 3) continue;
    // 吸附到最近天体（地心 x=0 / 月心 x=1−mu），平移点列保持几何
    // Snap to the nearest body (Earth x=0 / Moon x=1−mu) and translate the point list.
    const centerDU: [number, number, number] =
      Math.abs(rawCenter[0] - moonX) <= Math.abs(rawCenter[0]) ? [moonX, 0, 0] : [0, 0, 0];
    const dx = centerDU[0] - rawCenter[0];
    const dy = centerDU[1] - rawCenter[1];
    const pointsDU = el.points_km.map(
      (p) => [toDU(p)[0] + dx, toDU(p)[1] + dy, toDU(p)[2]] as [number, number, number],
    );
    out.push({
      kind: el.kind,
      label: el.label,
      centerDU,
      radiusDU: el.radius_km / DU_KM,
      pointsDU,
      formulaId,
    });
  }
  return out;
}
