// i18n：中英双语（对齐 ADR-0001 的 PyQt 翻译范围，范式参照 altgo）。
// localStorage 持久化，默认中文。

import { useEffect, useState } from "react";

const LANG_KEY = "tod-lang";

const translations: Record<string, Record<string, string>> = {
  zh: {
    "project.title": "项目",
    "catalog.title": "轨道库",
    "project.empty": "暂无产物",
    "tool.family": "轨道族生成",
    "action.generate": "生成",
    "action.generating": "生成中…",
    "action.fit": "适配",
    "action.chart_settings": "图表设置",
    "action.export_animation": "导出动画",
    "action.recording": "录制中",
    "tree.orbit": "🪐 轨道",
    "tree.family": "🌀 轨道族",
    "tree.transfer": "🚀 转移",
    "tree.ephemeris": "📡 星历",
    "tree.remove": "移除",
    "family.members": "族成员",
    "family.catalog_members": "条库轨迹",
    "family.record": "记录",
    "status.none": "",
  },
  en: {
    "project.title": "Project",
    "catalog.title": "Catalog",
    "project.empty": "No artifacts",
    "tool.family": "Orbit Family Generation",
    "action.generate": "Generate",
    "action.generating": "Generating…",
    "action.fit": "Fit",
    "action.chart_settings": "Chart Settings",
    "action.export_animation": "Export Animation",
    "action.recording": "Recording",
    "tree.orbit": "🪐 Orbits",
    "tree.family": "🌀 Families",
    "tree.transfer": "🚀 Transfers",
    "tree.ephemeris": "📡 Ephemerides",
    "tree.remove": "Remove",
    "family.members": "family members",
    "family.catalog_members": "catalog orbits",
    "family.record": "record",
    "status.none": "",
  },
};

export function useTranslation() {
  const [lang, setLangState] = useState<string>(
    () => localStorage.getItem(LANG_KEY) || "zh",
  );

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = (code: string) => {
    setLangState(code);
    localStorage.setItem(LANG_KEY, code);
  };

  const t = (key: string): string => translations[lang]?.[key] ?? translations["zh"]?.[key] ?? key;

  return { lang, setLang, t };
}
