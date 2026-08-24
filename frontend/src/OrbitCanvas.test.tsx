// OrbitCanvas 渲染层回归测试：轨道线必须在场景重建后仍然存在。
//
// 复现 #405 后续：App 每次重渲染都传新的 onReady 内联函数，若建场景
// effect 依赖 [onReady]，场景会被整体重建而轨迹 effect（依赖未变）
// 不会重跑，轨迹丢失——用户看到空画布。

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render } from "@testing-library/react";
import { Line, Group } from "three";
import { OrbitCanvas } from "./OrbitCanvas";

// jsdom 无 WebGL：只替换 WebGLRenderer，其余 three 类保持真实实现。
vi.mock("three", async (importOriginal) => {
  const actual = await importOriginal<typeof import("three")>();
  class FakeRenderer {
    domElement: HTMLCanvasElement;
    lastScene: unknown = null;
    static instances: FakeRenderer[] = [];
    constructor() {
      this.domElement = document.createElement("canvas");
      FakeRenderer.instances.push(this);
    }
    setSize() {}
    render(scene: unknown) {
      this.lastScene = scene;
    }
    dispose() {}
  }
  return { ...actual, WebGLRenderer: FakeRenderer };
});

vi.mock("three/examples/jsm/controls/OrbitControls.js", () => ({
  OrbitControls: class {
    target = { set() {}, copy() {} };
    enableDamping = false;
    autoRotate = false;
    autoRotateSpeed = 0.3;
    update() {}
    dispose() {}
  },
}));

const { WebGLRenderer } = await import("three");
type FakeRendererInstance = InstanceType<typeof WebGLRenderer> & {
  lastScene: unknown;
  static: unknown;
};

let rafQueue: FrameRequestCallback[] = [];

function flushFrames() {
  const q = rafQueue;
  rafQueue = [];
  q.forEach((cb) => cb(0));
}

function sceneLines(scene: unknown): Line[] {
  const out: Line[] = [];
  (scene as { traverse: (cb: (o: { isLine?: boolean }) => void) => void }).traverse((o) => {
    if (o.isLine) out.push(o as unknown as Line);
  });
  return out;
}

function sceneGroups(scene: unknown): Group[] {
  const out: Group[] = [];
  (scene as { traverse: (cb: (o: { isGroup?: boolean }) => void) => void }).traverse((o) => {
    if (o.isGroup) out.push(o as unknown as Group);
  });
  return out;
}

const MU = 0.01215058560962404;
const TRAJECTORIES: number[][][] = [
  Array.from({ length: 50 }, (_, i) => [Math.cos((i / 50) * Math.PI * 2), Math.sin((i / 50) * Math.PI * 2), 0]),
];
const LIBRATION = [
  { label: "L1", x: 0.8369 },
  { label: "L2", x: 1.1557 },
];

const noopReady = () => {};

function renderCanvas(props?: Partial<Parameters<typeof OrbitCanvas>[0]>) {
  return render(
    <OrbitCanvas
      trajectories={TRAJECTORIES}
      mu={MU}
      libration={LIBRATION}
      projection="3d"
      center="barycenter"
      onReady={noopReady}
      {...props}
    />,
  );
}

beforeEach(() => {
  rafQueue = [];
  vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
    rafQueue.push(cb);
    return rafQueue.length;
  });
  vi.stubGlobal("cancelAnimationFrame", () => {});
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      disconnect() {}
      unobserve() {}
    },
  );
  // jsdom 无 2D canvas：stub 给天体标注用的 getContext("2d")
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(
    () => ({ fillText: () => {} }) as unknown as CanvasRenderingContext2D,
  );
  (WebGLRenderer as unknown as { instances: unknown[] }).instances.length = 0;
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("OrbitCanvas 轨迹渲染", () => {
  it("渲染后场景中存在与 trajectories 等量的轨迹线", () => {
    renderCanvas();
    flushFrames();
    const instances = (WebGLRenderer as unknown as { instances: FakeRendererInstance[] }).instances;
    expect(instances.length).toBeGreaterThanOrEqual(1);
    const lines = sceneLines(instances[instances.length - 1].lastScene);
    expect(lines.length).toBe(TRAJECTORIES.length);
  });

  it("无关重渲染（onReady 新引用）不清空已画轨迹", () => {
    const view = renderCanvas();
    flushFrames();

    // 模拟 App 任意状态变化（setBusy/setApi/...）：onReady 是内联函数，
    // 每次渲染都是新引用，其余 props 不变。
    view.rerender(
      <OrbitCanvas
        trajectories={TRAJECTORIES}
        mu={MU}
        libration={LIBRATION}
        projection="3d"
        center="barycenter"
        onReady={() => {}}
      />,
    );
    flushFrames();

    const instances = (WebGLRenderer as unknown as { instances: FakeRendererInstance[] }).instances;
    const last = instances[instances.length - 1];
    const lines = sceneLines(last.lastScene);
    expect(lines.length).toBe(TRAJECTORIES.length);
  });

  it("天体按各自坐标摆放，不堆在原点、不移动整个场景", () => {
    renderCanvas();
    flushFrames();
    const instances = (WebGLRenderer as unknown as { instances: FakeRendererInstance[] }).instances;
    const scene = instances[instances.length - 1].lastScene as { children: Group[] };

    // content group 的位置必须是居中偏移（barycenter → 原点），
    // 不能被 addSphere 覆盖成某个天体坐标。
    const content = sceneGroups(scene).find((g) => g.children.length > 0);
    expect(content).toBeDefined();
    expect(content!.position.x).toBeCloseTo(0, 10);

    // 地球 mesh（半径最大、颜色 0x2196f3）应位于 (-mu, 0, 0)
    const meshes = content!.children.filter((c) => (c as unknown as { isMesh?: boolean }).isMesh) as unknown as {
      position: { x: number; y: number; z: number };
      material: { color: { getHex(): number } };
    }[];
    const earth = meshes.find((m) => m.material.color.getHex() === 0x2196f3);
    expect(earth).toBeDefined();
    expect(earth!.position.x).toBeCloseTo(-MU, 10);
  });
});
