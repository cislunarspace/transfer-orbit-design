// sidecar 前端封装：Tauri command 调用 + 类型。
// Frontend wrappers for the sidecar: Tauri command calls plus types.

export interface FamilyMember {
  states: number[]; // n×6 状态（初态帧时 n=1）
  times: number[];
  period: number | null;
  /** 该成员的 Jacobi 常数（族记录通道，#435）；无值为 null */
  /** The member's Jacobi constant (family-record channel, #435); null when absent. */
  jacobi?: number | null;
}

/** 记录的星历段（eph/ 前缀数组）：会合系无量纲位置 (n,3) 平铺 + UTC 分量；
 *  键名与 e2m2e EphemerisTable 一致（snake_case，与设计响应 ephemeris 同形），
 *  解析走 trajectoryParsing.designEphemerisToCanvasData。 */
export interface EphemerisSegment {
  synodic_position: number[];
  year: number[];
  month: number[];
  day: number[];
  hour: number[];
  minute: number[];
  second: number[];
}

export interface ArtifactData {
  recordId: string;
  orbitFamily: string;
  memberCount: number;
  mu?: number | null;
  familyMembers?: FamilyMember[];
  members: number[][]; // 每成员 n×3 xyz
  /** 记录级 Jacobi 常数（设计轨道记录通道，#435）：设计记录是该轨道唯一值；
   *  族记录为包络下限（成员值优先、缺值时回退本值）；无 CR3BP 段为 null */
  /** Record-level Jacobi constant (design-orbit record channel, #435): the orbit's
   *  only value for design records; the envelope floor for family records (a member's
   *  own value wins, this fills in when missing); null without a CR3BP segment. */
  jacobi?: number | null;
  ephemeris?: EphemerisSegment | null;
  /** 转移段（#428 第二步）：states/times 会合系物理 km/km/s 与 TLI 起算秒，
   *  gcrsStates 惯性段（旧记录缺位为 null）；非转移记录为 null */
  /** The transfer segment (#428 step 2): states/times in rotating-frame physical
   *  km/km/s and seconds since TLI, plus gcrsStates (the inertial segment, null
   *  for legacy records); null for non-transfer records. */
  transfer?: TransferSegment | null;
  error: { code: string; message: string } | null;
}

export interface TransferSegment {
  states: number[][]; // (n,6) 行
  times: number[]; // TLI 起算秒（秒，seconds since TLI）
  gcrsStates?: number[][] | null;
  tliEpoch?: string | number | null; // UTC 字符串或 JD_TDB 浮点，原样透传（UTC string or JD_TDB float, passed through as-is）
  transferType?: string | null;
  deltaVKmS?: number | null;
}

export async function getArtifact(recordId: string): Promise<ArtifactData> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke("get_artifact", { recordId });
}

export interface ToolFrame { dtype: "f32" | "f64"; shape: number[]; data: number[]; }
export interface ToolResponse { data: Record<string, unknown>; frames: ToolFrame[]; error: { code: string; message: string } | null; }

export async function runTool(
  tool: string, arguments_: Record<string, unknown>, binaryDtype?: "f32" | "f64", artifact?: { artifactType: string; label: string; orbitType?: string },
): Promise<ToolResponse> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke("run_tool", { tool, arguments: arguments_, binaryDtype, artifact });
}

/** 星历内核配置状态（自动配置：随 git/安装包分发，正常永远就绪）。 */
/** Ephemeris kernel config status (auto-configured: ships with git/the installer, normally always ready). */
export interface EphemerisStatus {
  kernelDir: string | null;
  files: string[];
  ephemerisReady: boolean;
  leapsecondReady: boolean;
  usable: boolean;
}

export async function ephemerisStatus(): Promise<EphemerisStatus> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke("ephemeris_status");
}
