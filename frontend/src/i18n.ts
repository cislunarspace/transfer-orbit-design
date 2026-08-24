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
    "updater.checking": "正在检查更新…",
    "updater.latest": "当前已是最新版本",
    "updater.available_title": "发现新版本",
    "updater.available_desc": "新版本 {version} 已发布。是否立即更新？",
    "updater.download_now": "立即更新",
    "updater.downloading": "正在下载更新…",
    "updater.downloaded_title": "更新已就绪",
    "updater.downloaded_desc": "新版本已下载并校验完毕，点击重启以完成更新。",
    "updater.restart_now": "立即重启",
    "updater.later": "稍后",
    "updater.check_action": "检查更新",
    "updater.error": "更新失败",
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
    "updater.checking": "Checking for updates…",
    "updater.latest": "You are already on the latest version",
    "updater.available_title": "Update Available",
    "updater.available_desc": "New version {version} is available. Update now?",
    "updater.download_now": "Update Now",
    "updater.downloading": "Downloading update…",
    "updater.downloaded_title": "Update Ready",
    "updater.downloaded_desc": "New version downloaded and verified. Restart to apply update.",
    "updater.restart_now": "Restart Now",
    "updater.later": "Later",
    "updater.check_action": "Check for Updates",
    "updater.error": "Update failed",
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