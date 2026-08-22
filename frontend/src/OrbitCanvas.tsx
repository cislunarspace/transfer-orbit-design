import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import type { ChartSettings } from "./chartSettings";

export interface CanvasProps {
  /** 轨迹点（归一化会合坐标系），多条即多轨道。 */
  trajectories: number[][][];
  mu: number;
  /** 平动点 x 坐标（会合坐标系）。 */
  libration: { label: string; x: number }[];
  settings?: ChartSettings;
  onReady?: (api: CanvasApi) => void;
}

export interface CanvasApi {
  /** 视图适配：按当前轨迹包围盒重设相机，每侧留 5% 余量。 */
  fitView: () => void;
  /** 录制用的 canvas 元素。 */
  canvasElement: () => HTMLCanvasElement | null;
  /** 自动旋转开关（GIF/webm 动画导出用）。 */
  setAutoRotate: (on: boolean, speed?: number) => void;
}

export function OrbitCanvas({ trajectories, mu, libration, settings, onReady }: CanvasProps) {
  const mountRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<THREE.Group | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);

  useEffect(() => {
    const mount = mountRef.current!;
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(mount.clientWidth, mount.clientHeight);
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

    const resize = () => {
      camera.aspect = mount.clientWidth / mount.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(mount.clientWidth, mount.clientHeight);
    };
    const observer = new ResizeObserver(resize);
    observer.observe(mount);

    const animate = () => {
      requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    onReady?.({
      canvasElement: () => renderer.domElement,
      setAutoRotate: (on, speed = 0.3) => {
        controls.autoRotate = on;
        controls.autoRotateSpeed = speed;
      },
      fitView: () => {
        const box = new THREE.Box3().setFromObject(content);
        if (box.isEmpty()) return;
        box.expandByScalar(box.getSize(new THREE.Vector3()).length() * 0.05);
        const center = box.getCenter(new THREE.Vector3());
        const radius = box.getSize(new THREE.Vector3()).length() / 2;
        const dist = radius / Math.sin((camera.fov * Math.PI) / 360);
        const dir = camera.position.clone().sub(controls.target).normalize();
        controls.target.copy(center);
        camera.position.copy(center.clone().add(dir.multiplyScalar(dist)));
        camera.near = dist / 100;
        camera.far = dist * 100;
        camera.updateProjectionMatrix();
      },
    });

    return () => {
      observer.disconnect();
      renderer.dispose();
      mount.removeChild(renderer.domElement);
    };
  }, [onReady]);

  // 轨迹与标注（地月、平动点）在 content 组内重建。
  useEffect(() => {
    const content = contentRef.current;
    if (!content) return;
    while (content.children.length) {
      const child = content.children[0];
      content.remove(child);
    }

    const lpColorNum = parseInt((settings?.lpColor ?? "#fdd835").slice(1), 16);
    const colors = (settings?.colorCycle ?? ["#4fc3f7", "#ffb74d", "#81c784", "#e57373", "#ba68c8"]).map(c => parseInt(c.slice(1), 16));
    trajectories.forEach((pts, i) => {
      const positions = new Float32Array(pts.length * 3);
      pts.forEach((p, j) => {
        positions[j * 3] = p[0];
        positions[j * 3 + 1] = p[1];
        positions[j * 3 + 2] = p[2];
      });
      const geom = new THREE.BufferGeometry();
      geom.setAttribute("position", new THREE.BufferAttribute(positions, 3));
      content.add(new THREE.Line(
        geom,
        new THREE.LineBasicMaterial({ color: colors[i % colors.length], linewidth: settings?.orbitLinewidth ?? 1.0 }),
      ));
    });

    const addSphere = (x: number, color: number, radius: number, label: string) => {
      content.add(new THREE.Mesh(
        new THREE.SphereGeometry(radius, 24, 24),
        new THREE.MeshBasicMaterial({ color }),
      )).position.set(x, 0, 0);
      const canvas = document.createElement("canvas");
      canvas.width = 256;
      canvas.height = 64;
      const ctx = canvas.getContext("2d")!;
      ctx.fillStyle = "#ddd";
      ctx.font = "28px system-ui";
      ctx.fillText(label, 4, 40);
      const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
        map: new THREE.CanvasTexture(canvas),
        depthTest: false,
      }));
      sprite.position.set(x + radius * 2, radius, 0);
      sprite.scale.set(0.08, 0.02, 1);
      content.add(sprite);
    };

    const s = settings;
    addSphere(-mu, 0x2196f3, s?.earthSize ?? 0.02, "地球");
    addSphere(1 - mu, 0x9e9e9e, s?.moonSize ?? 0.01, "月球");
    libration.forEach((lp) => addSphere(lp.x, lpColorNum, s?.lpSize ?? 0.003, lp.label));
  }, [trajectories, mu, libration]);

  return <div ref={mountRef} style={{ width: "100%", height: "100%" }} />;
}
