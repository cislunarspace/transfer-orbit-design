// 严肃视觉语言：直角(2px) + 收敛语义色板（黑/白/灰/红/蓝/绿/橙）
// 有意偏离 antd 圆润亮色默认，见 docs/adr/0020-serious-semantic-ui-visual-language.md
export const themeTokens = {
  // 直角：antd 默认 6–8px 圆角，全系列统一收到 2px
  borderRadius: 2,
  borderRadiusLG: 2,
  borderRadiusSM: 2,
  borderRadiusXS: 2,
  borderRadiusOuter: 2,
  // 主色/信息色：收敛深蓝（替换 antd 默认亮蓝 #1677ff）
  colorPrimary: "#0958d9",
  colorInfo: "#0958d9",
  // 语义色沿用 antd 默认：绿=成功、橙=警告、红=错误
  colorSuccess: "#52c41a",
  colorWarning: "#faad14",
  colorError: "#ff4d4f",
} as const;
