// 任务轨道设计预置参数回归测试：orbit_type 渲染为预置下拉（15 种轨道类型，
// 告别手填大写字符串），面板挂载自动填入模型默认值（schema default）与
// 轨道类型分支默认值。
// Task-orbit-design preset regression tests: orbit_type renders as a preset
// dropdown (15 orbit types, no more hand-typed uppercase strings), and mounting
// the panel fills model defaults (schema `default`) plus orbit-type branch defaults.

import { describe, it, expect, vi, beforeAll } from "vitest";
import { render, screen, within, waitFor, fireEvent } from "@testing-library/react";
import { ParamsPanel } from "./ParamsPanel";
import { toolEntry } from "./schema";

// jsdom 无 matchMedia / ResizeObserver，antd Select/DatePicker 需要
// jsdom lacks matchMedia / ResizeObserver, needed by antd Select/DatePicker.
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

function renderDesignOrbit(onChange = vi.fn()) {
  const entry = toolEntry("design_orbit");
  render(
    <ParamsPanel
      toolName={entry.name}
      schema={entry.schema}
      values={{}}
      onChange={onChange}
    />
  );
  return onChange;
}

/** 取 Orbit Type 字段所在表单项内的下拉控件 */
/** Locate the Select control inside the Orbit Type form item. */
function orbitTypeCombo(): HTMLElement {
  // closest 泛型收窄到 HTMLElement：within() 不收 Element
  // Narrow closest to HTMLElement: within() does not accept Element.
  const item = screen.getByText("Orbit Type").closest<HTMLElement>(".ant-form-item")!;
  return within(item).getByRole("combobox");
}

describe("ParamsPanel 任务轨道设计预置参数", () => {
  it("orbit_type 是预置下拉而非手填文本框：展开含全部 15 种轨道类型", async () => {
    renderDesignOrbit();
    const combo = await waitFor(orbitTypeCombo);
    const item = combo.closest<HTMLElement>(".ant-form-item")!;
    expect(within(item).queryByRole("textbox")).toBeNull();

    // rc-select 的展开事件挂在 .ant-select 根节点上（combobox 是其内部搜索输入）
    // rc-select binds open on the .ant-select root (the combobox is its inner search input).
    fireEvent.mouseDown(combo);
    fireEvent.focus(combo);
    expect(await screen.findByRole("listbox")).toBeTruthy();
    // 虚拟滚动只渲染首屏选项（15 项全覆盖由 overlay.test.ts 保证）
    // Virtual scrolling renders only the first window (full 15-item coverage is
    // guaranteed by overlay.test.ts).
    expect(screen.getByText("HALO 晕轨道")).toBeTruthy();
    expect(screen.getByText("LISSAJOUS 利萨如轨道")).toBeTruthy();
  });

  it("挂载即填入模型默认值（epoch/output_step/引力场阶数/修正方法）+ HALO 分支默认值", async () => {
    const onChange = renderDesignOrbit();
    await waitFor(() => {
      const call = onChange.mock.calls.find(([vals]) => (vals as Record<string, unknown>).orbit_type === "HALO");
      expect(call).toBeTruthy();
      expect(call![0]).toMatchObject({
        orbit_type: "HALO",
        amplitude: 30000,
        phase: 0,
        collinear_point: 2,
        north_south: 2,
        epoch: [2024, 1, 1, 0, 0, 0],
        output_step: 3600,
        earth_degree: 10,
        moon_degree: 10,
        correction_method: "two_level",
        correction_revolutions: 1,
      });
    });
  });
});
