// CR3BP 归一化单位下的轨道传播与轨道族数据加载。
// CR3BP orbit propagation in normalized units plus orbit-family data loading.

export interface OrbitSeed {
  orbitId: string;
  mu: number;
  period: number; // 归一化时间单位
  state: [number, number, number, number, number, number]; // x y z vx vy vz
}

/** CR3BP 运动方程（会合坐标系，归一化单位）。 */
/** CR3BP equations of motion (rotating frame, normalized units). */
export function deriv(mu: number, s: number[]): number[] {
  const [x, y, z, vx, vy, vz] = s;
  const r1 = Math.sqrt((x + mu) ** 2 + y * y + z * z);
  const r2 = Math.sqrt((x - 1 + mu) ** 2 + y * y + z * z);
  const r13 = r1 ** 3;
  const r23 = r2 ** 3;
  return [
    vx,
    vy,
    vz,
    2 * vy + x - (1 - mu) * (x + mu) / r13 - mu * (x - 1 + mu) / r23,
    -2 * vx + y - (1 - mu) * y / r13 - mu * y / r23,
    -(1 - mu) * z / r13 - mu * z / r23,
  ];
}

/** RK4 定步长积分一个周期，返回采样点（含起点，不含终点重复）。 */
/** Integrate one period with fixed-step RK4; returns samples (start included, no duplicate endpoint). */
export function propagate(mu: number, seed: OrbitSeed, steps: number): number[][] {
  const h = seed.period / steps;
  let s = [...seed.state];
  const pts: number[][] = [[s[0], s[1], s[2]]];
  for (let i = 0; i < steps; i++) {
    const k1 = deriv(mu, s);
    const k2 = deriv(mu, s.map((v, j) => v + h / 2 * k1[j]));
    const k3 = deriv(mu, s.map((v, j) => v + h / 2 * k2[j]));
    const k4 = deriv(mu, s.map((v, j) => v + h * k3[j]));
    s = s.map((v, j) => v + h / 6 * (k1[j] + 2 * k2[j] + 2 * k3[j] + k4[j]));
    pts.push([s[0], s[1], s[2]]);
  }
  return pts;
}

/** 平动点合力方程 f(x)=0（会合坐标系 x 轴）。 */
/** Net-force equation for libration points f(x)=0 (rotating-frame x axis). */
function collinearAccel(mu: number, x: number): number {
  const r1 = Math.abs(x + mu);
  const r2 = Math.abs(x - 1 + mu);
  // (x±)/|x±|³ = sign(x±)/(x±)²
  const g1 = (x + mu) >= 0 ? 1 : -1;
  const g2 = (x - 1 + mu) >= 0 ? 1 : -1;
  return x - (1 - mu) * g1 / r1 ** 2 - mu * g2 / r2 ** 2;
}

/** 牛顿法解共线平动点位置（会合坐标系）。which: 1 (L1) / 2 (L2) / 3 (L3)。 */
/** Solve collinear libration-point positions by Newton's method (rotating frame). which: 1 (L1) / 2 (L2) / 3 (L3). */
export function librationPoint(mu: number, which: 1 | 2 | 3): number {
  let x = which === 1 ? 0.85 : which === 2 ? 1.15 : -1.0;
  for (let i = 0; i < 50; i++) {
    const eps = 1e-9;
    const d = (collinearAccel(mu, x + eps) - collinearAccel(mu, x - eps)) / (2 * eps);
    const step = collinearAccel(mu, x) / d;
    x -= step;
    if (Math.abs(step) < 1e-14) break;
  }
  return x;
}