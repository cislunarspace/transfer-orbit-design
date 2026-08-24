// Three.js 主画布

import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import type { ChartSettings } from "./chartSettings";
import { EARTH_RADIUS_DU, MOON_RADIUS_DU } from "./chartSettings";
import earthTextureUrl from "./assets/earth_2048.jpg";
import moonTextureUrl from "./assets/moon_1024.jpg";

export type ProjectionMode = "3d" | "xy" | "xz" | "yz";
export type FrameMode = "synodic" | "inertial";
export type CenterMode = "barycenter" | "moon" | "l1" | "l2";

export interface OrbitCanvasProps {
  trajectories: number[][][];
  times?: number[][];
  currentEt?: number | null;
  mu: number;
  libration: { label: string; x: number }[];
  projection: ProjectionMode;
  center: CenterMode;
  settings?: ChartSettings;
  onReady?: (api: CanvasApi) => void;
}

export interface CanvasApi {
  fitView: () => void;
  canvasElement: () => HTMLCanvasElement | null;
  setAutoRotate: (on: boolean, speed?: number) => void;
}

export function OrbitCanvas({
  trajectories,
  times,
  currentEt,
  mu,
  libration,
  projection,
  center,
  settings,
  onReady,
}: OrbitCanvasProps) {
  const mountRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<THREE.Group | null>(null);
  const annotationsRef = useRef<THREE.Group | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const markerRef = useRef<THREE.Mesh | null>(null);
  // onReady 走 ref：建场景 effect 依赖 []，调用方传内联函数（如
  // App 的 onReady={(a) => setApi(a)}）不会触发场景重建导致轨迹丢失。
  const onReadyRef = useRef(onReady);
  onReadyRef.current = onReady;

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    rendererRef.current = renderer;
    mount.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    // matplotlib dark_background 同源的中性深灰，不带蓝色色偏
    scene.background = new THREE.Color(0x121212);

    // 光照：太阳平行光（晨昏线）+ 环境光（夜面可辨），照亮真实贴图天体
    scene.add(new THREE.AmbientLight(0xffffff, 0.4));
    const sun = new THREE.DirectionalLight(0xfff3e0, 1.6);
    sun.position.set(3, 2, 4);
    scene.add(sun);

    const camera = new THREE.PerspectiveCamera(50, mount.clientWidth / mount.clientHeight, 1e-4, 100);
    camera.position.set(1.5, -1.5, 1);
    cameraRef.current = camera;

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    // 旋转方向与旧 PyQt 画布（matplotlib mplot3d）一致：拖拽旋转“物体
    // 本身”，场景跟随光标；OrbitControls 默认是“拖拽移动相机”，往左拖
    // 场景看起来往右转，体感方向相反。负值只反转旋转，平移/缩放不受影响。
    controls.rotateSpeed = -1.0;
    controlsRef.current = controls;

    const content = new THREE.Group();
    content.name = "orbits"; // 仅供测试定位：fitView 只按轨道范围适配
    contentRef.current = content;
    scene.add(content);

    // 标注组（天体/平动点/坐标轴/网格）：与 content 同偏移，但不参与视图适配
    const annotations = new THREE.Group();
    annotations.name = "annotations";
    annotationsRef.current = annotations;
    scene.add(annotations);

    const marker = new THREE.Mesh(
      new THREE.SphereGeometry(0.015, 16, 16),
      new THREE.MeshBasicMaterial({ color: 0xff0055 })
    );
    marker.visible = false;
    markerRef.current = marker;
    scene.add(marker);

    const resize = () => {
      if (!mount) return;
      camera.aspect = mount.clientWidth / mount.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(mount.clientWidth, mount.clientHeight);
    };
    const observer = new ResizeObserver(resize);
    observer.observe(mount);

    let frameId: number;
    const animate = () => {
      frameId = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    const fitView = () => {
      const box = new THREE.Box3().setFromObject(content);
      if (box.isEmpty()) return;
      box.expandByScalar(box.getSize(new THREE.Vector3()).length() * 0.05);
      const bCenter = box.getCenter(new THREE.Vector3());
      const radius = box.getSize(new THREE.Vector3()).length() / 2;
      const dist = radius / Math.sin((camera.fov * Math.PI) / 360);
      const dir = camera.position.clone().sub(controls.target).normalize();
      controls.target.copy(bCenter);
      camera.position.copy(bCenter.clone().add(dir.multiplyScalar(dist)));
      camera.near = dist / 100;
      camera.far = dist * 100;
      camera.updateProjectionMatrix();
    };

    onReadyRef.current?.({
      canvasElement: () => renderer.domElement,
      setAutoRotate: (on, speed = 0.3) => {
        controls.autoRotate = on;
        controls.autoRotateSpeed = speed;
      },
      fitView,
    });

    return () => {
      cancelAnimationFrame(frameId);
      observer.disconnect();
      renderer.dispose();
      if (mount.contains(renderer.domElement)) {
        mount.removeChild(renderer.domElement);
      }
    };
  }, []);

  useEffect(() => {
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    if (!camera || !controls) return;

    if (projection === "xy") {
      camera.position.set(0, 0, 3);
      camera.up.set(0, 1, 0);
      controls.target.set(0, 0, 0);
    } else if (projection === "xz") {
      camera.position.set(0, -3, 0);
      camera.up.set(0, 0, 1);
      controls.target.set(0, 0, 0);
    } else if (projection === "yz") {
      camera.position.set(3, 0, 0);
      camera.up.set(0, 0, 1);
      controls.target.set(0, 0, 0);
    } else {
      camera.position.set(1.5, -1.5, 1);
      camera.up.set(0, 0, 1);
    }
    camera.updateProjectionMatrix();
    controls.update();
  }, [projection]);

  const getCenterOffset = (): [number, number, number] => {
    if (center === "moon") return [-(1 - mu), 0, 0];
    if (center === "l1") {
      const l1 = libration.find((l) => l.label === "L1");
      return [-(l1?.x ?? (1 - mu - 0.15)), 0, 0];
    }
    if (center === "l2") {
      const l2 = libration.find((l) => l.label === "L2");
      return [-(l2?.x ?? (1 - mu + 0.15)), 0, 0];
    }
    return [0, 0, 0];
  };

  useEffect(() => {
    const content = contentRef.current;
    const annotations = annotationsRef.current;
    if (!content || !annotations) return;
    while (content.children.length) {
      content.remove(content.children[0]);
    }
    while (annotations.children.length) {
      annotations.remove(annotations.children[0]);
    }

    const [ox, oy, oz] = getCenterOffset();
    content.position.set(ox, oy, oz);
    annotations.position.set(ox, oy, oz);

    const lpColorNum = parseInt((settings?.lpColor ?? "#d4b106").slice(1), 16);
    const colors = (settings?.colorCycle ?? ["#4c72b0", "#dd8452", "#55a868", "#c44e52", "#8172b3"]).map((c) =>
      parseInt(c.slice(1), 16)
    );

    // 轨道线独占 content 组：视图适配只按可见轨道范围（标注不参与）
    trajectories.forEach((pts, i) => {
      const positions = new Float32Array(pts.length * 3);
      pts.forEach((p, j) => {
        positions[j * 3] = p[0];
        positions[j * 3 + 1] = p[1];
        positions[j * 3 + 2] = p[2] * (settings?.zRatio ?? 1.0);
      });
      const geom = new THREE.BufferGeometry();
      geom.setAttribute("position", new THREE.BufferAttribute(positions, 3));
      content.add(
        new THREE.Line(
          geom,
          new THREE.LineBasicMaterial({ color: colors[i % colors.length], linewidth: settings?.orbitLinewidth ?? 1.0 })
        )
      );
    });

    // 文本标注 sprite（天体名/平动点/轴名共用）
    const makeLabelSprite = (text: string, color = "#c9d3dd"): THREE.Sprite => {
      const canvas = document.createElement("canvas");
      canvas.width = 256;
      canvas.height = 64;
      const ctx = canvas.getContext("2d")!;
      ctx.fillStyle = color;
      ctx.font = "600 30px system-ui";
      ctx.fillText(text, 4, 42);
      const sprite = new THREE.Sprite(
        new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(canvas), depthTest: false })
      );
      sprite.scale.set(0.08, 0.02, 1);
      return sprite;
    };

    const addSphere = (x: number, y: number, z: number, color: number, radius: number, label: string) => {
      // 注意：Object3D.add() 返回的是父 group，mesh 的位置必须显式设置，
      // 否则天体堆在原点、group 位置被覆盖，整个场景（含轨道线）被平移。
      const body = new THREE.Mesh(
        new THREE.SphereGeometry(radius, 24, 24),
        new THREE.MeshBasicMaterial({ color })
      );
      body.position.set(x, y, z);
      annotations.add(body);

      const sprite = makeLabelSprite(label);
      sprite.position.set(x + radius * 2, y + radius, z);
      annotations.add(sprite);
    };

    const s = settings;
    // 地月：NASA 公有领域贴图（Blue Marble / LROC）+ Phong 光照，
    // 半径取真实比例（chartSettings 常量），替代旧卡通纯色球
    const texLoader = new THREE.TextureLoader();
    const addTexturedBody = (
      name: string, label: string, x: number, radius: number, textureUrl: string,
      specular: number, shininess: number,
    ) => {
      const tex = texLoader.load(textureUrl);
      tex.colorSpace = THREE.SRGBColorSpace;
      const body = new THREE.Mesh(
        new THREE.SphereGeometry(radius, 32, 24),
        new THREE.MeshPhongMaterial({
          map: tex,
          specular: new THREE.Color(specular),
          shininess,
        }),
      );
      body.name = name;
      body.position.set(x, 0, 0);
      annotations.add(body);

      const sprite = makeLabelSprite(label);
      sprite.position.set(x + radius * 2, radius, 0);
      annotations.add(sprite);
    };
    addTexturedBody("earth", "地球", -mu, s?.earthSize ?? EARTH_RADIUS_DU, earthTextureUrl, 0x2a2a2a, 14);
    addTexturedBody("moon", "月球", 1 - mu, s?.moonSize ?? MOON_RADIUS_DU, moonTextureUrl, 0x111111, 4);

    libration.forEach((lp) => addSphere(lp.x, 0, 0, lpColorNum, s?.lpSize ?? 0.003, lp.label));

    // 坐标轴图层（matplotlib 式三轴 + 轨道面网格），随中心偏移，可开关
    if (settings?.axesVisible ?? true) {
      const axes = new THREE.Group();
      axes.name = "axes";
      const LEN = 0.45;
      const tips: [THREE.Vector3, number, string][] = [
        [new THREE.Vector3(1, 0, 0), 0xe57373, "X"],
        [new THREE.Vector3(0, 1, 0), 0x81c784, "Y"],
        [new THREE.Vector3(0, 0, 1), 0x4fc3f7, "Z"],
      ];
      for (const [dir, color, label] of tips) {
        axes.add(new THREE.ArrowHelper(dir, new THREE.Vector3(), LEN, color, 0.06, 0.035));
        const sprite = makeLabelSprite(label, `#${color.toString(16).padStart(6, "0")}`);
        sprite.position.copy(dir.clone().multiplyScalar(LEN + 0.07));
        axes.add(sprite);
      }
      // 网格默认在 XZ 面，转到 XY 轨道面；间距 0.1 DU，覆盖地月系范围
      const grid = new THREE.GridHelper(2.6, 26, 0x33415c, 0x1d2634);
      grid.rotation.x = Math.PI / 2;
      axes.add(grid);
      annotations.add(axes);
    }
  }, [trajectories, mu, libration, center, settings]);

  // 中心切换：所选中心点已移到世界原点，相机注视点同步移到原点（“居中”
  // 语义），保持注视方向与距离（视图保持）。不能改为按轨道盒重新适配：
  // 那样会把画面中心钉回轨道所在区域（如 L2 的 Halo 族），中心切换在
  // 画面上成为无操作，用户无法把质心/月心调到画面中心。
  useEffect(() => {
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    if (!camera || !controls) return;
    const delta = new THREE.Vector3().sub(controls.target);
    camera.position.add(delta);
    controls.target.set(0, 0, 0);
    controls.update();
  }, [center]);

  useEffect(() => {
    const marker = markerRef.current;
    if (!marker || currentEt === null || currentEt === undefined || trajectories.length === 0 || !times || times.length === 0) {
      if (marker) marker.visible = false;
      return;
    }

    const tList = times[0];
    const pts = trajectories[0];
    if (!tList || tList.length === 0 || pts.length === 0) {
      marker.visible = false;
      return;
    }

    let idx = tList.findIndex((t) => t >= currentEt);
    if (idx <= 0) idx = 1;
    if (idx >= tList.length) idx = tList.length - 1;

    const t0 = tList[idx - 1];
    const t1 = tList[idx];
    const alpha = (currentEt - t0) / Math.max(1e-6, t1 - t0);
    const p0 = pts[idx - 1] || pts[0];
    const p1 = pts[idx] || pts[0];

    const [ox, oy, oz] = getCenterOffset();
    const x = (p0[0] + (p1[0] - p0[0]) * alpha) + ox;
    const y = (p0[1] + (p1[1] - p0[1]) * alpha) + oy;
    const z = (p0[2] + (p1[2] - p0[2]) * alpha) * (settings?.zRatio ?? 1.0) + oz;

    marker.position.set(x, y, z);
    marker.visible = true;
  }, [currentEt, trajectories, times, center, settings]);

  return <div ref={mountRef} style={{ width: "100%", height: "100%", position: "relative" }} />;
}
