// 图表设置：localStorage 持久化（线宽 / 颜色循环 / 天体与平动点标注尺寸 /
// 字号 / z 轴比例）。
// Chart settings persisted in localStorage (line width / color cycle / body & libration-point marker
// sizes / font sizes / Z-axis ratio).

import { useEffect, useState } from "react";

export interface ChartSettings {
  orbitLinewidth: number;
  /** 轨迹颜色循环（hex 数组，族成员与库轨迹依次取色） */
  /** Trajectory color cycle (hex array; family members and catalog trajectories take colors in turn). */
  colorCycle: string[];
  earthSize: number;
  moonSize: number;
  lpColor: string;
  lpSize: number;
  labelFontsize: number;
  /** 等比模式下 Z 轴区间相对 XY 的最小比例（近平面轨道防压扁） */
  /** Minimum Z-range ratio relative to XY in equal-aspect mode (keeps near-planar orbits from flattening). */
  zRatio: number;
  /** 坐标轴与网格图层（matplotlib 式参照系） */
  /** Axes and grid layer (a matplotlib-style reference frame). */
  axesVisible: boolean;
  /** 画布背景色；null = 跟随应用主题（浅色白底、夜间深灰） */
  /** Canvas background; null = follow the app theme (white in light mode, dark gray at night). */
  bgColor: string | null;
  /** 量程（DU）：网格半宽与刻度范围 */
  /** Range (DU): grid half-width and tick extent. */
  gridRange: number;
}

/** 地月真实半径（DU）：6378.137 km / 1737.4 km ÷ 384400 km */
/** Real Earth/Moon radii in DU: 6378.137 km / 1737.4 km ÷ 384400 km. */
export const EARTH_RADIUS_DU = 6378.137 / 384400;
export const MOON_RADIUS_DU = 1737.4 / 384400;

export const DEFAULT_CHART_SETTINGS: ChartSettings = {
  orbitLinewidth: 1.0,
  // seaborn muted：matplotlib 生态经典科研配色，低饱和不刺眼
  // seaborn muted: the classic matplotlib-ecosystem scientific palette — low saturation, easy on the eyes.
  colorCycle: ["#4c72b0", "#dd8452", "#55a868", "#c44e52", "#8172b3"],
  earthSize: EARTH_RADIUS_DU,
  moonSize: MOON_RADIUS_DU,
  lpColor: "#d4b106",
  lpSize: 0.003,
  labelFontsize: 12,
  zRatio: 0.5,
  axesVisible: true,
  bgColor: null,
  gridRange: 1.3,
};

const KEY = "tod-chart-settings";

export function useChartSettings(): [ChartSettings, (s: ChartSettings) => void] {
  const [settings, setSettings] = useState<ChartSettings>(() => {
    try {
      const raw = localStorage.getItem(KEY);
      return raw ? { ...DEFAULT_CHART_SETTINGS, ...JSON.parse(raw) } : DEFAULT_CHART_SETTINGS;
    } catch {
      return DEFAULT_CHART_SETTINGS;
    }
  });

  useEffect(() => {
    localStorage.setItem(KEY, JSON.stringify(settings));
  }, [settings]);

  return [settings, setSettings];
}