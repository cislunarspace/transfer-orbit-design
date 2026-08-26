// 严肃视觉语言：直角(2px) + 高密度平面化 + 收敛语义色板（黑/白/灰/红/蓝/绿/橙）
// 有意偏离 antd 圆润亮色默认，见 docs/adr/0020-serious-semantic-ui-visual-language.md

// 与 token 平级的主题开关
export const themeBehavior = {
  // 关闭全部过渡动画：按钮/弹窗/下拉的缓动是"卡通感"的主要来源
  motion: false,
  // 线框风：组件去渐变、阴影改边框式，走向平面观感
  wireframe: true,
} as const;

export const themeTokens = {
  // 直角：antd 默认 6–8px 圆角，全系列统一收到 2px
  borderRadius: 2,
  borderRadiusLG: 2,
  borderRadiusSM: 2,
  borderRadiusXS: 2,
  borderRadiusOuter: 2,
  // 密度：控件高度从默认 32/24/40 收紧到桌面工具量级
  controlHeight: 26,
  controlHeightSM: 22,
  controlHeightLG: 30,
  // 平面阴影：只留一层浅投影，不用 antd 默认的大扩散多层阴影
  boxShadow: "0 1px 2px rgba(0, 0, 0, 0.10)",
  boxShadowSecondary: "0 2px 6px rgba(0, 0, 0, 0.12)",
  // 字体：桌面系统 UI 栈，Windows 上 Segoe UI + 雅黑
  fontFamily:
    '"Segoe UI", "Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", system-ui, sans-serif',
  // 主色/信息色：收敛深蓝（替换 antd 默认亮蓝 #1677ff）
  colorPrimary: "#0958d9",
  colorInfo: "#0958d9",
  // 语义色沿用 antd 默认：绿=成功、橙=警告、红=错误
  colorSuccess: "#52c41a",
  colorWarning: "#faad14",
  colorError: "#ff4d4f",
} as const;
