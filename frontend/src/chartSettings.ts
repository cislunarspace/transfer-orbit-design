// 图表设置：localStorage 持久化（对齐 PyQt 版 ChartSettings 的可调参数，
// Three.js 语义：线宽 / 颜色循环 / 天体与平动点标注尺寸 / 字号 / z 轴比例）。

import { useEffect, useState } from "react";

export interface ChartSettings {
  orbitLinewidth: number;
  /** 轨迹颜色循环（hex 数组，对应 PyQt 的 colormap） */
  colorCycle: string[];
  earthSize: number;
  moonSize: number;
  lpColor: string;
  lpSize: number;
  labelFontsize: number;
  /** 等比模式下 Z 轴区间相对 XY 的最小比例（近平面轨道防压扁） */
  zRatio: number;
  /** 坐标轴与网格图层（matplotlib 式参照系） */
  axesVisible: boolean;
}

export const DEFAULT_CHART_SETTINGS: ChartSettings = {
  orbitLinewidth: 1.0,
  colorCycle: ["#4fc3f7", "#ffb74d", "#81c784", "#e57373", "#ba68c8"],
  earthSize: 0.02,
  moonSize: 0.01,
  lpColor: "#fdd835",
  lpSize: 0.003,
  labelFontsize: 12,
  zRatio: 0.5,
  axesVisible: true,
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