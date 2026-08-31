// i18n：中英双语，localStorage 持久化，默认中文。
// 语言是全应用共享状态（#447）：根部挂 I18nProvider，切换按钮改写共享
// state，所有已挂载组件立即以新语言重渲染；无 Provider 的裸渲染（组件
// 单测直接挂载）退回组件本地 state，读写同一 localStorage 键。
// i18n: Chinese/English bilingual, persisted in localStorage, Chinese by default.
// The language is app-wide shared state (#447): the root mounts an
// I18nProvider, the toggle button writes the shared state, and every mounted
// component re-renders in the new language; bare renders without a Provider
// (component tests mounting directly) fall back to component-local state
// reading/writing the same localStorage key.

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

const LANG_KEY = "tod-lang";

const translations: Record<string, Record<string, string>> = {
  zh: {
    "action.save": "保存",
    "action.cancel": "取消",
    "tree.plot_selected": "绘制所选",
    "tree.plot_skip_failed": "已跳过加载失败的记录",
    "tree.star_toggle": "星标",
    "tree.pin_toggle": "钉到画布（固定层）",
    "tree.pin_limit": "固定层最多 5 条，请先取消其他图钉",
    "tree.pin_load_failed": "钉住失败：无法读取该记录",
    "canvas.transfer_arc": "转移弧",
    "canvas.propagation": "轨道预报",
    "canvas.cr3bp_reference": "CR3BP 参考轨道",
    "canvas.design_ephemeris": "星历段（会合系）",
    "canvas.frame.synodic_nd": "会合系无量纲",
    "canvas.frame.synodic_km": "会合系物理 km",
    "canvas.frame.inertial_km": "地心惯性 km",
    "canvas.frame.synodic_unavailable": "会合系几何，惯性视图下不可画",
    "canvas.moon_track_failed": "月球惯性轨迹获取失败（星历内核不可用？），惯性视图暂不显示月球",
    "scenario.save_empty_pinned": "固定层为空，情景固定住的是钉住的库记录，请先在项目树钉住记录",
    "scenario.save_needs_et": "情景需要真实历元时间轴：同屏有带历元的产物（星历段/转移弧）且时间轴已选时刻后才能保存",
    "scenario.saved": "情景已保存",
    "scenario.save_failed": "情景保存失败",
    "scenario.open_failed": "情景打开失败",
    "scenario.missing_records": "已跳过 {ids} 条缺失记录（已删除或无法读取），其余已加载",
    "scenario.truncated": "情景引用超过固定层上限 {limit} 条，已截断",
    "scenario.opened": "情景已打开：固定层 {count} 条记录，时间轴已校准到参考历元",
    "event.departure_pulse": "出发脉冲",
    "event.arrival_pulse": "到达脉冲",
    "event.candidate_pulse": "候选 {k} TLI",
    "panel.candidates_title": "可行解对比（top-N，Δv 升序）",
    "panel.cand_selected": "选中",
    "panel.cand_refined_true": "打靶精化",
    "panel.cand_refined_false": "网格估计",
    "panel.cand_no_traj": "无轨迹",
    "panel.cand_no_epoch": "—",
    "canvas.transfer_candidate": "转移候选 {k}·Δv {dv}",
    "unit.days": "天",
    "transfer.candidates_truncated": "候选数超固定层剩余容量，仅画前 {n} 条（其余参数见详情面板）",
    "transfer.candidates_trackless": "候选 {ks} 无轨迹快照，未上画布（参数见详情面板）",
    "tree.edit_note": "编辑备注...",
    "tree.note_saved": "备注已保存",
    "tree.note_save_failed": "保存备注失败",
    "tree.note_placeholder": "备注内容...",
    "panel.annotation_title": "备注与标签",
    "panel.annotation_saved": "备注保存成功",
    "panel.star_reserved": "星标 (★) 是保留标签，请在项目树的星形图标处设置",
    "catalog.star_only": "仅看星标",
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
    "assistant.title": "AI 助手",
    "assistant.clear": "清空会话",
    "assistant.collapse": "收起",
    "assistant.empty_config": "尚未配置模型服务。AI 助手通过你自带的模型服务（OpenAI 兼容协议）工作，需先填写服务地址、模型名与 API key。",
    "assistant.go_settings": "去设置",
    "assistant.input_placeholder": "向助手提问或下达任务…（Enter 发送，Shift+Enter 换行）",
    "assistant.card.proposed": "待确认",
    "assistant.card.running": "运行中",
    "assistant.card.done": "已完成",
    "assistant.card.failed": "失败",
    "assistant.card.rejected": "已拒绝",
    "assistant.card.confirm": "确认运行",
    "assistant.card.edit": "编辑参数",
    "assistant.card.reject": "拒绝",
    "assistant.card.view_artifact": "查看产物",
    "assistant.card.apply_scenario": "应用情景",
    "assistant.card.edit_title": "编辑工具参数（JSON）",
    "assistant.card.edit_bad_json": "参数不是合法 JSON，请修正后再确认",
    "assistant.card.cancel": "取消",
    "assistant.settings.section_title": "AI 助手（模型服务）",
    "assistant.settings.provider": "服务商预设",
    "assistant.settings.provider_placeholder": "选择服务商以填入服务地址（可改）",
    "assistant.settings.base_url": "服务地址（base URL）",
    "assistant.settings.model": "模型名",
    "assistant.settings.api_key": "API Key",
    "assistant.settings.key_kept": "已保存（留空保持不变）",
    "assistant.settings.key_hint": "Key 仅保存在系统凭据管理器，不会写入界面或本地文件缓存。",
    "assistant.settings.save": "保存",
    "assistant.settings.test": "测试连接",
    "assistant.settings.saved": "配置已保存",
    "assistant.settings.test_ok": "连接成功：",
    "assistant.settings.test_fail": "连接失败：",
    "assistant.settings.thinking_default": "默认思考等级（新会话继承）",
    "assistant.session.new": "新建会话",
    "assistant.session.untitled": "未命名会话",
    "assistant.session.rename": "重命名",
    "assistant.session.rename_title": "重命名会话",
    "assistant.session.delete": "删除",
    "assistant.session.delete_title": "删除会话",
    "assistant.session.delete_confirm": "删除后不可恢复。删除会话不会删除轨道库记录（会话里只保存记录引用）。",
    "assistant.session.switch_busy": "有回复进行中或确认未决，完成后才能切换会话",
    "assistant.thinking.title": "已思考",
    "assistant.level.label": "思考等级",
    "assistant.level.off": "关",
    "assistant.level.standard": "标准",
    "assistant.level.deep": "深度",
  },
  en: {
    "action.save": "Save",
    "action.cancel": "Cancel",
    "tree.plot_selected": "Plot Selected",
    "tree.plot_skip_failed": "Skipped a record that failed to load",
    "tree.star_toggle": "Star",
    "tree.pin_toggle": "Pin to canvas (pinned layer)",
    "tree.pin_limit": "The pinned layer holds at most 5 records — unpin others first",
    "tree.pin_load_failed": "Pin failed: unable to load the record",
    "canvas.transfer_arc": "Transfer arc",
    "canvas.propagation": "Propagation",
    "canvas.cr3bp_reference": "CR3BP reference orbit",
    "canvas.design_ephemeris": "Ephemeris arc (synodic)",
    "canvas.frame.synodic_nd": "synodic (nd)",
    "canvas.frame.synodic_km": "synodic (km)",
    "canvas.frame.inertial_km": "geocentric inertial (km)",
    "canvas.frame.synodic_unavailable": "synodic geometry, not drawable in the inertial view",
    "canvas.moon_track_failed": "Failed to fetch the Moon's inertial track (ephemeris kernels unavailable?); the Moon is hidden in the inertial view for now",
    "scenario.save_empty_pinned": "The pinned layer is empty — a scenario pins catalog records, so pin some in the project tree first",
    "scenario.save_needs_et": "A scenario needs the real-epoch timeline: save after an epoch-bearing product (ephemeris segment / transfer arc) is on screen and the timeline has a picked moment",
    "scenario.saved": "Scenario saved",
    "scenario.save_failed": "Failed to save the scenario",
    "scenario.open_failed": "Failed to open the scenario",
    "scenario.missing_records": "Skipped {ids} missing record(s) (deleted or unreadable); the rest are loaded",
    "scenario.truncated": "The scenario references more than the pinned-layer cap of {limit}; truncated",
    "scenario.opened": "Scenario opened: {count} pinned record(s), timeline calibrated to the reference epoch",
    "event.departure_pulse": "Departure burn",
    "event.arrival_pulse": "Arrival burn",
    "event.candidate_pulse": "Candidate {k} TLI",
    "panel.candidates_title": "Feasible solutions (top-N, Δv ascending)",
    "panel.cand_selected": "selected",
    "panel.cand_refined_true": "targeting refined",
    "panel.cand_refined_false": "grid estimate",
    "panel.cand_no_traj": "no trajectory",
    "panel.cand_no_epoch": "—",
    "canvas.transfer_candidate": "Candidate {k} · Δv {dv}",
    "unit.days": "d",
    "transfer.candidates_truncated": "Candidates exceed the pinned-layer headroom: only the first {n} drawn (the rest in the detail panel)",
    "transfer.candidates_trackless": "Candidates {ks} carry no trajectory snapshot — not drawn (parameters in the detail panel)",
    "tree.edit_note": "Edit Note...",
    "tree.note_saved": "Note saved",
    "tree.note_save_failed": "Failed to save note",
    "tree.note_placeholder": "Note text...",
    "panel.annotation_title": "Notes & Tags",
    "panel.annotation_saved": "Notes saved",
    "panel.star_reserved": "The star (★) is a reserved tag; toggle it via the star icon in the project tree",
    "catalog.star_only": "Starred only",
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
    "assistant.title": "AI Assistant",
    "assistant.clear": "Clear session",
    "assistant.collapse": "Collapse",
    "assistant.empty_config": "Model service not configured yet. The assistant works through your own model service (OpenAI-compatible protocol) — fill in the base URL, model name, and API key first.",
    "assistant.go_settings": "Open Settings",
    "assistant.input_placeholder": "Ask the assistant or give it a task… (Enter to send, Shift+Enter for a newline)",
    "assistant.card.proposed": "Pending",
    "assistant.card.running": "Running",
    "assistant.card.done": "Done",
    "assistant.card.failed": "Failed",
    "assistant.card.rejected": "Rejected",
    "assistant.card.confirm": "Confirm & Run",
    "assistant.card.edit": "Edit Args",
    "assistant.card.reject": "Reject",
    "assistant.card.view_artifact": "View Artifact",
    "assistant.card.apply_scenario": "Apply Scenario",
    "assistant.card.edit_title": "Edit tool arguments (JSON)",
    "assistant.card.edit_bad_json": "Arguments are not valid JSON — fix before confirming",
    "assistant.card.cancel": "Cancel",
    "assistant.settings.section_title": "AI Assistant (Model Service)",
    "assistant.settings.provider": "Provider Preset",
    "assistant.settings.provider_placeholder": "Pick a provider to fill in the base URL (editable)",
    "assistant.settings.base_url": "Base URL",
    "assistant.settings.model": "Model Name",
    "assistant.settings.api_key": "API Key",
    "assistant.settings.key_kept": "Saved (leave empty to keep unchanged)",
    "assistant.settings.key_hint": "The key is stored only in the OS credential manager — never written to the UI or a local file cache.",
    "assistant.settings.save": "Save",
    "assistant.settings.test": "Test Connection",
    "assistant.settings.saved": "Configuration saved",
    "assistant.settings.test_ok": "Connected: ",
    "assistant.settings.test_fail": "Connection failed: ",
    "assistant.settings.thinking_default": "Default thinking level (inherited by new sessions)",
    "assistant.session.new": "New session",
    "assistant.session.untitled": "Untitled session",
    "assistant.session.rename": "Rename",
    "assistant.session.rename_title": "Rename session",
    "assistant.session.delete": "Delete",
    "assistant.session.delete_title": "Delete session",
    "assistant.session.delete_confirm": "This cannot be undone. Deleting a session does not delete catalog records — sessions only store record references.",
    "assistant.session.switch_busy": "A reply is running or a confirmation is pending — wait before switching sessions",
    "assistant.thinking.title": "Thought process",
    "assistant.level.label": "Thinking level",
    "assistant.level.off": "Off",
    "assistant.level.standard": "Standard",
    "assistant.level.deep": "Deep",
  },
};

interface I18n {
  lang: string;
  setLang: (code: string) => void;
  t: (key: string) => string;
}

const I18nContext = createContext<I18n | null>(null);

/** lang 状态的实现体：初始化读 localStorage、切换写回、<html lang> 同步。
 *  Provider 与无 Provider 退路共用，保证两条路径行为一致。 */
/** The lang-state implementation: initializes from localStorage, persists on
 *  switch, syncs <html lang>. Shared by the Provider and the no-Provider
 *  fallback so both paths behave identically. */
function useLangState(): I18n {
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

/** 应用根部的语言 Provider（main.tsx）：承载共享 lang 状态与上述副作用。 */
/** The app-root language Provider (main.tsx): holds the shared lang state and the side effects above. */
export function I18nProvider({ children }: { children: ReactNode }) {
  return <I18nContext.Provider value={useLangState()}>{children}</I18nContext.Provider>;
}

export function useTranslation(): I18n {
  const shared = useContext(I18nContext);
  if (shared) return shared;

  // 无 Provider 的退路（组件单测裸渲染）：与共享路径同一实现，仅作用域
  // 是组件本地。同一实例生命周期内 Provider 有无不变化，hook 序稳定。
  // The no-Provider fallback (bare-rendered component tests): same
  // implementation as the shared path, scoped to the component only. Whether
  // a Provider exists never changes within one instance's lifetime, so the
  // hook order is stable.
  return useLangState();
}