import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CanvasToolbar } from "./CanvasToolbar";

const baseProps = {
  projection: "3d" as const,
  center: "barycenter" as const,
  recording: false,
  onProjectionChange: vi.fn(),
  onCenterChange: vi.fn(),
  onFitView: vi.fn(),
  onExportAnimation: vi.fn(),
  onOpenSettings: vi.fn(),
};

function setup(overrides: Partial<typeof baseProps> = {}) {
  const props = { ...baseProps, ...overrides };
  render(<CanvasToolbar {...props} />);
  return props;
}

describe("CanvasToolbar component", () => {
  it("渲染全部投影与中心选项及操作按钮", () => {
    setup();
    for (const name of ["3D", "XY", "XZ", "YZ"]) {
      expect(screen.getByRole("radio", { name })).toBeDefined();
    }
    for (const name of ["质心", "地心", "月心", "L1", "L2"]) {
      expect(screen.getByRole("radio", { name })).toBeDefined();
    }
    expect(screen.getByRole("button", { name: /适配/ })).toBeDefined();
    expect(screen.getByRole("button", { name: /导出动画/ })).toBeDefined();
  });

  it("切换投影与中心触发对应回调", () => {
    const props = setup();
    fireEvent.click(screen.getByRole("radio", { name: "XY" }));
    expect(props.onProjectionChange).toHaveBeenCalledWith("xy");
    fireEvent.click(screen.getByRole("radio", { name: "月心" }));
    expect(props.onCenterChange).toHaveBeenCalledWith("moon");
  });

  it("点击适配/导出动画/设置触发对应回调", () => {
    const props = setup();
    fireEvent.click(screen.getByRole("button", { name: /适配/ }));
    expect(props.onFitView).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: /导出动画/ }));
    expect(props.onExportAnimation).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByTitle("图表显示设置"));
    expect(props.onOpenSettings).toHaveBeenCalledTimes(1);
  });

  it("录制中导出按钮呈 loading", () => {
    setup({ recording: true });
    const btn = screen.getByRole("button", { name: /导出动画/ });
    expect(btn.className).toContain("ant-btn-loading");
  });
});
