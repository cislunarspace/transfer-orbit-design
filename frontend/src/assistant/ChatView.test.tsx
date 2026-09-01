// ChatView 行为回归（#450）：
// - 用户消息发出时无条件滚底（自己刚说的话必须可见）
// - 生成中（running）显示动态指示（Spin），空闲时不显示
// 注：贴底才跟随的条件滚动依赖 scrollHeight/clientHeight 布局量测，jsdom
// 不提供（恒 0 → 视为贴底），非贴底路径以手工验证兜底（规格测试决策注明）。
// ChatView behavior regressions (#450):
// - a user message always forces a scroll-to-bottom (one's own words must be visible)
// - running shows an animated indicator (Spin); idle shows none
// Note: stick-to-bottom gating needs scrollHeight/clientHeight layout metrics
// that jsdom lacks (always 0 → treated as stuck); the not-stuck path is
// covered by manual verification (as stated in the spec's testing decisions).

import { describe, it, expect, vi, beforeAll, afterEach } from "vitest";
import { render, cleanup } from "@testing-library/react";
import { ChatView } from "./ChatView";
import type { ChatItem } from "./chatModel";

beforeAll(() => {
  const mm = (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  });
  vi.stubGlobal("matchMedia", mm);
  window.matchMedia = mm as unknown as typeof window.matchMedia;
  window.HTMLElement.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  cleanup();
  vi.mocked(window.HTMLElement.prototype.scrollIntoView).mockClear();
});

const USER_MSG: ChatItem[] = [{ kind: "user", text: "画一条 NRHO" }];

describe("ChatView 滚动与生成中指示（#450）", () => {
  it("用户消息发出时无条件滚底（scrollIntoView 被调用）", () => {
    render(<ChatView items={USER_MSG} running={false} onOpenRecord={vi.fn()} />);
    expect(window.HTMLElement.prototype.scrollIntoView).toHaveBeenCalled();
  });

  it("running 时显示生成中指示（Spin），空闲时不显示", () => {
    const { rerender } = render(
      <ChatView items={USER_MSG} running={true} onOpenRecord={vi.fn()} />,
    );
    expect(document.querySelector(".ant-spin")).not.toBeNull();
    rerender(<ChatView items={USER_MSG} running={false} onOpenRecord={vi.fn()} />);
    expect(document.querySelector(".ant-spin")).toBeNull();
  });
});
