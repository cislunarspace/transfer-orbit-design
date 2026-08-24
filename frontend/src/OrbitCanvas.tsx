// Three.js 主画布

import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import type { ChartSettings } from "./chartSettings";

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
    scene.background = new THREE.Color(0x101418);

    const camera = new THREE.PerspectiveCamera(50, mount.clientWidth / mount.clientHeight, 1e-4, 100);
    camera.position.set(1.5, -1.5, 1);
    cameraRef.current = camera;

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controlsRef.current = controls;

    const content = new THREE.Group();
    contentRef.current = content;
    scene.add(content);

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

    onReadyRef.current?.({
      canvasElement: () => renderer.domElement,
      setAutoRotate: (on, speed = 0.3) => {
        controls.autoRotate = on;
        controls.autoRotateSpeed = speed;
      },
      fitView: () => {
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
      },
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
    if (!content) return;
    while (content.children.length) {
      content.remove(content.children[0]);
    }

    const [ox, oy, oz] = getCenterOffset();
    content.position.set(ox, oy, oz);

    const lpColorNum = parseInt((settings?.lpColor ?? "#fdd835").slice(1), 16);
    const colors = (settings?.colorCycle ?? ["#4fc3f7", "#ffb74d", "#81c784", "#e57373", "#ba68c8"]).map((c) =>
      parseInt(c.slice(1), 16)
    );

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

    const addSphere = (x: number, y: number, z: number, color: number, radius: number, label: string) => {
      // 注意：Object3D.add() 返回的是父 group，mesh 的位置必须显式设置，
      // 否则天体堆在原点、group 位置被覆盖，整个场景（含轨道线）被平移。
      const body = new THREE.Mesh(
        new THREE.SphereGeometry(radius, 24, 24),
        new THREE.MeshBasicMaterial({ color })
      );
      body.position.set(x, y, z);
      content.add(body);

      const canvas = document.createElement("canvas");
      canvas.width = 256;
      canvas.height = 64;
      const ctx = canvas.getContext("2d")!;
      ctx.fillStyle = "#ddd";
      ctx.font = "28px system-ui";
      ctx.fillText(label, 4, 40);
      const sprite = new THREE.Sprite(
        new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(canvas), depthTest: false })
      );
      sprite.position.set(x + radius * 2, y + radius, z);
      sprite.scale.set(0.08, 0.02, 1);
      content.add(sprite);
    };

    const s = settings;
    addSphere(-mu, 0, 0, 0x2196f3, s?.earthSize ?? 0.02, "地球");
    addSphere(1 - mu, 0, 0, 0x9e9e9e, s?.moonSize ?? 0.01, "月球");
    libration.forEach((lp) => addSphere(lp.x, 0, 0, lpColorNum, s?.lpSize ?? 0.003, lp.label));
  }, [trajectories, mu, libration, center, settings]);

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
