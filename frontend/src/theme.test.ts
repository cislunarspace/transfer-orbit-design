import { describe, expect, it } from "vitest";
import { themeTokens } from "./theme";

describe("themeTokens", () => {
  it("圆角全系列统一为 2px（严肃直角风格，偏离 antd 默认 6-8px）", () => {
    expect(themeTokens.borderRadius).toBe(2);
    expect(themeTokens.borderRadiusLG).toBe(2);
    expect(themeTokens.borderRadiusSM).toBe(2);
    expect(themeTokens.borderRadiusXS).toBe(2);
    expect(themeTokens.borderRadiusOuter).toBe(2);
  });

  it("主色与信息色为收敛深蓝 #0958d9（替换 antd 默认亮蓝）", () => {
    expect(themeTokens.colorPrimary).toBe("#0958d9");
    expect(themeTokens.colorInfo).toBe("#0958d9");
  });

  it("语义色沿用 antd 默认：绿=成功、橙=警告、红=错误", () => {
    expect(themeTokens.colorSuccess).toBe("#52c41a");
    expect(themeTokens.colorWarning).toBe("#faad14");
    expect(themeTokens.colorError).toBe("#ff4d4f");
  });
});
