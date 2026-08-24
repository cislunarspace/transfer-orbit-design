// OrbitCanvas 渲染层回归测试：轨道线必须在场景重建后仍然存在。
//
// 复现 #405 后续：App 每次重渲染都传新的 onReady 内联函数，若建场景
// effect 依赖 [onReady]，场景会被整体重建而轨迹 effect（依赖未变）
// 不会重跑，轨迹丢失——用户看到空画布。

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render } from "@testing-library/react";
import { Line } from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { OrbitCanvas, type CenterMode } from "./OrbitCanvas";
import { DEFAULT_CHART_SETTINGS } from "./chartSettings";

// jsdom 无 WebGL：只替换 WebGLRenderer，其余 three 类保持真实实现。
vi.mock("three", async (importOriginal) => {
  const actual = await importOriginal<typeof import("three")>();
  class FakeRenderer {
    domElement: HTMLCanvasElement;
    lastScene: unknown = null;
    lastCamera: unknown = null;
    static instances: FakeRenderer[] = [];
    constructor() {
      this.domElement = document.createElement("canvas");
      FakeRenderer.instances.push(this);
    }
    setSize() {}
    render(scene: unknown, camera: unknown) {
      this.lastScene = scene;
      this.lastCamera = camera;
    }
    dispose() {}
  }
  return { ...actual, WebGLRenderer: FakeRenderer };
});

vi.mock("three/examples/jsm/controls/OrbitControls.js", () => ({
  OrbitControls: class {
    // target 记录 x/y/z：fitView 的 copy/sub 需要可读字段，
    // 测试靠它断言相机注视点是否跟随中心切换。
    static instances: unknown[] = [];
    target = { x: 0, y: 0, z: 0, set(x: number, y: number, z: number) { this.x = x; this.y = y; this.z = z; }, copy(v: { x: number; y: number; z: number }) { this.x = v.x; this.y = v.y; this.z = v.z; return this; } };
    enableDamping = false;
    autoRotate = false;
    autoRotateSpeed = 0.3;
    constructor() { (this.constructor as unknown as { instances: unknown[] }).instances.push(this); }
    update() {}
    dispose() {}
  },
}));;

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
  // 只数轨道线：标注组里的网格/箭头/天体不算（视图适配与轨迹计数都只针对轨道）
  const orbits = (scene as import("three").Scene).getObjectByName("orbits");
  if (!orbits) return [];
  return orbits.children.filter((o) => (o as Line).isLine) as unknown as Line[];
}

function annotationsOf(scene: unknown): import("three").Group {
  const g = (scene as import("three").Scene).getObjectByName("annotations");
  expect(g).toBeDefined();
  return g as import("three").Group;
}

const MU = 0.01215058560962404;
const TRAJECTORIES: number[][][] = [
  Array.from({ length: 50 }, (_, i) => [Math.cos((i / 50) * Math.PI * 2), Math.sin((i / 50) * Math.PI * 2), 0]),
];
const LIBRATION = [
  { label: "L1", x: 0.8369 },
  { label: "L2", x: 1.1557 },
];

// L2 附近的偏心轨迹（模拟 Halo/NRHO 族）：fitView 后 target 会在盒中心
// x≈1.16，而不是原点——用于复现“适配后切中心，target 不跟随”的偏移。
const L2_ORBIT: number[][][] = [
  Array.from({ length: 60 }, (_, i) => {
    const a = (i / 60) * Math.PI * 2;
    return [1.1557 + 0.05 * Math.cos(a), 0.05 * Math.sin(a), 0.02 * Math.sin(a)];
  }),
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
  (OrbitControls as unknown as { instances: unknown[] }).instances.length = 0;
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
    const scene = instances[instances.length - 1].lastScene as { children: import("three").Group[] };

    // annotations 组的位置必须是居中偏移（barycenter → 原点），
    // 不能被天体坐标覆盖；天体按各自坐标摆放。
    const annotations = annotationsOf(scene);
    expect(annotations.position.x).toBeCloseTo(0, 10);

    // 地球 mesh（颜色 0x2196f3）应位于 (-mu, 0, 0)
    const meshes = annotations.children.filter((c) => (c as unknown as { isMesh?: boolean }).isMesh) as unknown as {
      position: { x: number; y: number; z: number };
      material: { color: { getHex(): number } };
    }[];
    const earth = meshes.find((m) => m.material.color.getHex() === 0x2196f3);
    expect(earth).toBeDefined();
    expect(earth!.position.x).toBeCloseTo(-MU, 10);
  });
});

describe("中心点居中几何", () => {
  // 选定中心后，该天体/平动点的世界坐标应为原点（相机 target 默认 0,0,0）
  const CASES: { name: string; center: CenterMode; bodyLocalX: number }[] = [
    { name: "月心居中", center: "moon", bodyLocalX: 1 - MU },
    { name: "L1 居中", center: "l1", bodyLocalX: LIBRATION[0].x },
    { name: "L2 居中", center: "l2", bodyLocalX: LIBRATION[1].x },
  ];

  it.each(CASES)("$name：中心天体世界坐标在原点", async ({ center, bodyLocalX }) => {
    const { Vector3 } = await import("three");
    render(
      <OrbitCanvas
        trajectories={TRAJECTORIES}
        mu={MU}
        libration={LIBRATION}
        projection="3d"
        center={center}
        onReady={() => {}}
      />,
    );
    flushFrames();
    const instances = (WebGLRenderer as unknown as { instances: FakeRendererInstance[] }).instances;
    const scene = instances[instances.length - 1].lastScene as import("three").Scene;
    scene.updateMatrixWorld(true);
    const annotations = annotationsOf(scene);
    const meshes = annotations.children.filter(
      (c) => (c as unknown as { isMesh?: boolean }).isMesh,
    ) as unknown as import("three").Mesh[];
    const target = meshes.find((m) => Math.abs(m.position.x - bodyLocalX) < 1e-9);
    expect(target, `未找到 local x=${bodyLocalX} 的天体`).toBeDefined();
    const world = new Vector3();
    target!.getWorldPosition(world);
    expect(world.x).toBeCloseTo(0, 6);
  });
});

describe("中心切换的相机注视点", () => {
  // 用户场景：L2 轨道族 + 适配（注视点在轨道盒中心）→ 手动切“质心居中”，
 // 期望质心（世界原点）成为画面中心，而不是重新适配又盯回轨道盒。
  const stateOf = () => {
    const r = (WebGLRenderer as unknown as { instances: FakeRendererInstance[] }).instances;
    const last = r[r.length - 1] as unknown as { lastCamera: { position: { x: number; y: number; z: number } } };
    const list = (OrbitControls as unknown as { instances: { target: { x: number; y: number; z: number } }[] }).instances;
    return { camera: last.lastCamera, target: list[list.length - 1].target };
  };

  it("切换到质心居中：注视点移到原点，视角与距离保持", () => {
    let api!: { fitView: () => void };
    const view = render(
      <OrbitCanvas
        trajectories={L2_ORBIT}
        mu={MU}
        libration={LIBRATION}
        projection="3d"
        center="l2"
        onReady={(a) => (api = a)}
      />,
    );
    flushFrames();
    api.fitView();
    const before = stateOf();
    // L2 居中 + 适配后，注视点在轨道盒中心（原点附近）
    expect(before.target.x).toBeCloseTo(0, 2);
    const offsetBefore = {
      x: before.camera.position.x - before.target.x,
      y: before.camera.position.y - before.target.y,
      z: before.camera.position.z - before.target.z,
    };

    view.rerender(
      <OrbitCanvas
        trajectories={L2_ORBIT}
        mu={MU}
        libration={LIBRATION}
        projection="3d"
        center="barycenter"
        onReady={(a) => (api = a)}
      />,
    );
    flushFrames();

    const after = stateOf();
    // center 状态确实传到了画布：质心居中时 annotations 偏移归零（区分假设 2）
    const scene = (WebGLRenderer as unknown as { instances: FakeRendererInstance[] }).instances;
    const s = scene[scene.length - 1].lastScene as import("three").Scene;
    expect(annotationsOf(s).position.x).toBeCloseTo(0, 10);
    // 质心居中：注视点应为世界原点，而不是轨道盒中心（当前实现变红处）
    expect(after.target.x).toBeCloseTo(0, 6);
    expect(after.target.y).toBeCloseTo(0, 6);
    // 视图保持：相机相对注视点的方向与距离不变
    expect(after.camera.position.x - after.target.x).toBeCloseTo(offsetBefore.x, 6);
    expect(after.camera.position.y - after.target.y).toBeCloseTo(offsetBefore.y, 6);
    expect(after.camera.position.z - after.target.z).toBeCloseTo(offsetBefore.z, 6);
  });
});

describe("坐标轴图层", () => {
  it("默认显示：三轴箭头 + X/Y/Z 标注 + 轨道面网格", () => {
    render(
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
    const scene = instances[instances.length - 1].lastScene as import("three").Scene;
    const axes = annotationsOf(scene).getObjectByName("axes");
    expect(axes).toBeDefined();
    // 3 箭头 + 3 轴名 sprite + 1 网格
    expect(axes!.children.length).toBe(7);
    const sprites = axes!.children.filter((c) => (c as unknown as { isSprite?: boolean }).isSprite);
    expect(sprites.length).toBe(3);
    const grid = axes!.children.find((c) => (c as unknown as { isLineSegments?: boolean }).isLineSegments);
    expect(grid).toBeDefined(); // GridHelper 继承 LineSegments
  });

  it("axesVisible=false 时不渲染坐标轴", () => {
    render(
      <OrbitCanvas
        trajectories={TRAJECTORIES}
        mu={MU}
        libration={LIBRATION}
        projection="3d"
        center="barycenter"
        settings={{ ...DEFAULT_CHART_SETTINGS, axesVisible: false }}
        onReady={() => {}}
      />,
    );
    flushFrames();
    const instances = (WebGLRenderer as unknown as { instances: FakeRendererInstance[] }).instances;
    const scene = instances[instances.length - 1].lastScene as import("three").Scene;
    expect(annotationsOf(scene).getObjectByName("axes")).toBeUndefined();
  });
});
