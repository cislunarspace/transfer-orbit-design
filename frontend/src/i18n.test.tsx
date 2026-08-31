// i18n 单测（#447）：语言切换是全应用共享状态——同一 Provider 下所有
// 已挂载组件同步切换、localStorage 持久化（重载恢复）、<html lang> 同步。
// i18n tests (for #447): the language is app-wide shared state — every
// mounted component under one Provider switches together, the choice
// persists in localStorage (restored on reload), and <html lang> follows.

import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { I18nProvider, useTranslation } from "./i18n";

/** 测试桩：渲染一条双语固定文案与切换按钮，探针语义与顶栏按钮一致。 */
function LangProbe() {
  const { lang, setLang, t } = useTranslation();
  return (
    <div>
      <span>{t("action.save")}</span>
      <button onClick={() => setLang(lang === "zh" ? "en" : "zh")}>
        {lang === "zh" ? "EN" : "中"}
      </button>
    </div>
  );
}

beforeEach(() => {
  localStorage.clear();
  document.documentElement.lang = "";
});

describe("i18n 语言共享状态（#447）", () => {
  it("同一 Provider 下两个组件：切换后双方文案立即同步，无需重挂载", () => {
    render(
      <I18nProvider>
        <LangProbe />
        <LangProbe />
      </I18nProvider>,
    );
    expect(screen.getAllByText("保存")).toHaveLength(2);

    fireEvent.click(screen.getAllByRole("button")[0]);

    expect(screen.getAllByText("Save")).toHaveLength(2);
    expect(screen.queryByText("保存")).toBeNull();
  });

  it("语言持久化：切换写入 localStorage，重新挂载 Provider 后恢复", () => {
    const { unmount } = render(
      <I18nProvider>
        <LangProbe />
      </I18nProvider>,
    );
    fireEvent.click(screen.getByRole("button"));
    expect(localStorage.getItem("tod-lang")).toBe("en");

    unmount();
    render(
      <I18nProvider>
        <LangProbe />
      </I18nProvider>,
    );
    expect(screen.getByText("Save")).toBeDefined();
    expect(screen.queryByText("保存")).toBeNull();
  });

  it("document.documentElement.lang 随切换更新", () => {
    render(
      <I18nProvider>
        <LangProbe />
      </I18nProvider>,
    );
    expect(document.documentElement.lang).toBe("zh");

    fireEvent.click(screen.getByRole("button"));

    expect(document.documentElement.lang).toBe("en");
  });
});
