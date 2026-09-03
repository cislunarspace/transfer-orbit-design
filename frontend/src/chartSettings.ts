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
  /** 地月空间分区图层（Primer 分区边界：Hill/SOI/Battin/r_L 圆族与平动点） */
  /** Cislunar partition region layer (Primer boundaries: Hill/SOI/Battin/r_L circles and libration points). */
  regionsVisible: boolean;
  /** 画布背景色；null = 跟随应用主题（浅色白底、夜间深灰）。默认固定深空
   *  黑——STK 式视口不随应用主题（#469），改 null 可恢复跟随。 */
  /** Canvas background; null = follow the app theme (white in light mode, dark
   *  gray at night). Defaults to fixed space black — an STK-style viewport that
   *  ignores the app theme (#469); set null to restore theme-following. */
  bgColor: string | null;
  /** 量程（DU）：网格半宽与刻度范围 */
  /** Range (DU): grid half-width and tick extent. */
  gridRange: number;
}

/** 地月真实半径（DU）：6378.137 km / 1737.4 km ÷ 384400 km */
/** Real Earth/Moon radii in DU: 6378.137 km / 1737.4 km ÷ 384400 km. */
export const EARTH_RADIUS_DU = 6378.137 / 384400;
export const MOON_RADIUS_DU = 1737.4 / 384400;

/** 天体默认显示放大倍数（#469）：真实半径在全系统图（~2.6 DU 宽）里只是
 *  像素点。×3 后地球显示半径 ≈0.050 DU ≫ μ≈0.012 DU，质心原点视觉上稳定
 *  落在地球体内；地球:月球保持 3.67:1 物理比。设置项仍可覆盖。 */
/** Default body display magnification (#469): at true radii the bodies are
 *  single pixels in the full-system view (~2.6 DU wide). At ×3 Earth's display
 *  radius ≈0.050 DU ≫ μ≈0.012 DU, so the barycenter origin lands inside the
 *  drawn Earth; the Earth:Moon ratio stays at the physical 3.67:1. The settings
 *  entries still override. */
export const BODY_DISPLAY_SCALE = 3;

export const DEFAULT_CHART_SETTINGS: ChartSettings = {
  orbitLinewidth: 1.0,
  // seaborn muted：matplotlib 生态经典科研配色，低饱和不刺眼
  // seaborn muted: the classic matplotlib-ecosystem scientific palette — low saturation, easy on the eyes.
  colorCycle: ["#4c72b0", "#dd8452", "#55a868", "#c44e52", "#8172b3"],
  earthSize: EARTH_RADIUS_DU * BODY_DISPLAY_SCALE,
  moonSize: MOON_RADIUS_DU * BODY_DISPLAY_SCALE,
  lpColor: "#d4b106",
  lpSize: 0.003,
  labelFontsize: 12,
  zRatio: 0.5,
  axesVisible: true,
  regionsVisible: true,
  bgColor: "#050a14",
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