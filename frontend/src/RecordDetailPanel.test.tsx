// RecordDetailPanel hooks 规则回归测试（#437）。
//
// 复现：组件曾在全部 hooks 之前对空 record 早返回，首次选中记录时同一
// 组件实例的 hook 数量从 0 变为 6，React 抛
// "Rendered more hooks than during the previous render." 并带崩渲染树。
// Regression test for RecordDetailPanel's hooks-rule violation (#437).
// The component used to early-return before its hooks when record was null;
// selecting the first record raised the hook count from 0 to 6, crashing the tree.

import { describe, it, expect, vi, beforeAll } from "vitest";
import { render, screen } from "@testing-library/react";
import { RecordDetailPanel } from "./RecordDetailPanel";
import type { CatalogRecord } from "./catalogApi";

// jsdom 无 matchMedia / ResizeObserver，antd Descriptions 与 TextArea 需要
// jsdom lacks matchMedia / ResizeObserver, required by antd Descriptions and TextArea.
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
  vi.stubGlobal("ResizeObserver", class {
    observe() {}
    unobserve() {}
    disconnect() {}
  });
});

const RECORD_A: CatalogRecord = {
  record_id: "rec-a",
  orbit_family: "HALO",
  libration_point: 2,
  jacobi: 3.15,
  member_count: 1,
  has_cr3bp: true,
  has_ephemeris: true,
  tags: ["候选", "A组"],
  note: "记录A的备注",
};

const RECORD_B: CatalogRecord = {
  record_id: "rec-b",
  orbit_family: "NRHO",
  libration_point: 1,
  jacobi: 3.01,
  member_count: 3,
  has_cr3bp: true,
  has_ephemeris: false,
  tags: ["B标签"],
  note: "记录B的备注",
};

describe("RecordDetailPanel hooks 规则（#437）", () => {
  it("record 从 null 变为有效记录的 rerender 不抛错", () => {
    const view = render(<RecordDetailPanel record={null} />);
    expect(() => {
      view.rerender(<RecordDetailPanel record={RECORD_A} />);
    }).not.toThrow();
    // 详情内容确实渲染出来（record_id 出现在 copyable 文本中）
    expect(screen.getByText("rec-a")).toBeDefined();
  });

  it("record 为 null 时显示空态提示卡片", () => {
    render(<RecordDetailPanel record={null} />);
    expect(screen.getByText("记录详情")).toBeDefined();
    expect(screen.getByText(/请在上方项目树或轨道库中选中一条记录查看详情/)).toBeDefined();
  });

  it("在两条不同记录间切换时，标签与备注输入框同步为新记录的值", () => {
    const view = render(<RecordDetailPanel record={RECORD_A} />);
    const tagsInput = screen.getByPlaceholderText("标签 (逗号分隔)") as HTMLInputElement;
    const noteInput = screen.getByPlaceholderText("笔记说明...") as HTMLTextAreaElement;
    expect(tagsInput.value).toBe("候选, A组");
    expect(noteInput.value).toBe("记录A的备注");

    view.rerender(<RecordDetailPanel record={RECORD_B} />);
    expect(tagsInput.value).toBe("B标签");
    expect(noteInput.value).toBe("记录B的备注");
  });

  it("选中记录后再切回 null 也不抛错（hook 数量恒定）", () => {
    const view = render(<RecordDetailPanel record={RECORD_A} />);
    expect(() => {
      view.rerender(<RecordDetailPanel record={null} />);
    }).not.toThrow();
    expect(screen.getByText(/请在上方项目树或轨道库中选中一条记录查看详情/)).toBeDefined();
  });
});
