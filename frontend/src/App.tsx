// 主应用入口：基于 Ant Design 6 构建的三栏现代化高密度桌面科学计算界面
// Main app entry: a three-pane, high-density desktop scientific-computing UI built on Ant Design 6.

import { useEffect, useState, useCallback, useRef, useMemo } from "react";
import {
  ConfigProvider,
  theme as antdTheme,
  Button,
  Select,
  Typography,
  Modal,
  Form,
  Slider,
  Switch,
  Divider,
  Row,
  Col,
  message,
} from "antd";
import {
  PlayCircleOutlined,
  InfoCircleOutlined,
  MoonOutlined,
  SunOutlined,
} from "@ant-design/icons";
import { themeBehavior, themeTokens, themeCssVars } from "./theme";
import { CanvasToolbar } from "./CanvasToolbar";
import { OrbitCanvas, type CanvasApi, type ProjectionMode, type CenterMode, type FrameMode } from "./OrbitCanvas";
import { TimelineBar } from "./TimelineBar";
import { ParamsPanel } from "./ParamsPanel";
import { ProjectTree } from "./ProjectTree";
import { RecordDetailPanel, type TransferCandidateView } from "./RecordDetailPanel";
import { StationKeepingModal } from "./StationKeepingModal";
import { CatalogFilterBar } from "./CatalogFilterBar";
import { UpdateModal } from "./UpdateModal";
import { AboutModal } from "./AboutModal";
import { checkForAppUpdates, type UpdateInfo } from "./updater";
import { TOOL_REGISTRY, toolEntry } from "./schema";
import { validateToolParams } from "./paramOverlay";
import { useTranslation } from "./i18n";
import { useChartSettings } from "./chartSettings";
import { CanvasRecorder, downloadBlob } from "./canvasRecorder";
import { listArtifacts, removeArtifact, registerArtifact, type ArtifactSummary } from "./projectApi";
import {
  DEFAULT_PLAYBACK,
  parseScenario,
  resolveScenarioRecords,
  serializeScenario,
  type ScenarioPlayback,
} from "./scenario";
import { saveScenarioFile, openScenarioFile } from "./scenarioApi";
import { runTool, getArtifact, ephemerisStatus, formatToolError, type EphemerisStatus } from "./sidecarApi";
import { AssistantSidebar } from "./assistant/AssistantSidebar";
import { AssistantSettingsForm } from "./assistant/AssistantSettingsForm";
import type { SelectionContext } from "./assistant/api";
import { DU_KM, TU_SECONDS, librationPoint } from "./cr3bp";
import { etFromEpoch } from "./timeBasis";
import { moonTrackFromResponse, moonTrackRequest, type MoonTrack } from "./moonEphemeris";
import { boundariesResponseToRegionLayer, type BoundaryElementPayload, type RegionElement } from "./regionLayer";
import {
  designEphemerisToCanvasData,
  familyMembersToTrajectoryData,
  framesToTrajectoryData,
  trajectoryTimeRange,
  timelineMode,
  timesForMode,
  transferTrajectoryToCanvasData,
  transferCandidateToArcData,
  propagationToCanvasData,
  filterByRole,
  type TrajectoryData,
  type TimeBasis,
  type DataFrameTag,
  type ContentMode,
} from "./trajectoryParsing";
import type { TimelineEvent } from "./TimelineBar";
import { type CatalogRecord, catalogQuery } from "./catalogApi";

const { Text, Title } = Typography;
const EARTH_MOON_MU = 0.01215058560962404;

/** 固定层软上限：超过提示但不拦截 */
/** Soft cap of the pinned layer: warn past it without blocking. */
const PINNED_LIMIT = 5;

/**
 * 转移响应 details → 出发/到达脉冲事件旗标（Q6/Q9 决策：本期用 details
 * 现成字段，机动事件结构化契约随转移存档下批做；近月点无时刻字段不做）。
 * dv_departure_km_s/dv_arrival_km_s 为 LGA/WSB 字段，dv1_km_s/dv2_km_s 为
 * HMN 字段，兼容取用；时刻 = tli et + (0 | tof_sec)。
 * Transfer details → departure/arrival pulse event flags (Q6/Q9: ready-made
 * details fields this round; the structured maneuver-event contract ships with
 * transfer catalog records next batch; perilune has no time field, skipped).
 * dv_departure_km_s/dv_arrival_km_s are the LGA/WSB fields, dv1_km_s/dv2_km_s
 * the HMN ones; times = tli et + (0 | tof_sec).
 */
function transferEventsFromDetails(
  details: unknown,
  tliEpoch: string | number | undefined,
  t: (key: string) => string,
): TimelineEvent[] {
  const det = (details ?? {}) as Record<string, unknown>;
  const tliEt = tliEpoch !== undefined ? etFromEpoch(tliEpoch) : NaN;
  if (!Number.isFinite(tliEt)) return [];
  const tof = Number(det.tof_sec);
  const events: TimelineEvent[] = [];
  const dvDep = Number(det.dv_departure_km_s ?? det.dv1_km_s);
  if (Number.isFinite(dvDep) && dvDep > 0) {
    events.push({ et: tliEt, label: t("event.departure_pulse"), dv: `${dvDep.toFixed(2)} km/s` });
  }
  const dvArr = Number(det.dv_arrival_km_s ?? det.dv2_km_s);
  if (Number.isFinite(tof) && tof > 0 && Number.isFinite(dvArr) && dvArr > 0) {
    events.push({
      et: tliEt + tof,
      label: t("event.arrival_pulse"),
      dv: `${dvArr.toFixed(2)} km/s`,
    });
  }
  return events;
}

/** 固定层条目：钉住的库记录及其解析出的轨迹数据 */
/** A pinned-layer entry: the pinned catalog record plus its parsed trajectory data. */
interface PinnedRecord {
  recordId: string;
  label: string;
  data: TrajectoryData;
}

export default function App() {
  const { lang, setLang, t } = useTranslation();
  const [themeMode, setThemeMode] = useState<"dark" | "light">(() => {
    // 默认白底黑字（日间）；夜间模式经右上角按钮切换并持久化
    // Defaults to white background with black text (daytime); night mode toggles via the top-right button and persists.
    return (localStorage.getItem("tod-theme-mode") as "dark" | "light") || "light";
  });
  const [fontSize, setFontSize] = useState<number>(() => {
    return Number(localStorage.getItem("tod-font-size") || "12");
  });

  const [leftTab, setLeftTab] = useState<"project" | "catalog">("project");
  const [selectedTool, setSelectedTool] = useState<string>(TOOL_REGISTRY[0].name);
  const [toolParams, setToolParams] = useState<Record<string, unknown>>({});
  // 提交校验问题（字段名 → 原因），传给参数面板内联标红；改动参数即清
  // Submission validation problems (field name → reason), passed to the params panel for inline red flags; cleared on any change.
  const [paramIssues, setParamIssues] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<boolean>(false);

  const [artifacts, setArtifacts] = useState<ArtifactSummary[]>([]);
  const [selectedArtifact, setSelectedArtifact] = useState<ArtifactSummary | null>(null);
  const [selectedRecordDetail, setSelectedRecordDetail] = useState<CatalogRecord | null>(null);

  // 画布状态（双层模型，CONTEXT.md「结果层」「固定层」）：
  // 结果层 = 最近一次计算/查看的轨迹集合（新内容整体替换）；
  // 固定层 = 项目树图钉钉住的记录，持续同屏直到取消。
  // Canvas state (two-layer model, see CONTEXT.md "result layer"/"pinned layer"):
  // the result layer holds the latest run/record view (replaced wholesale);
  // the pinned layer keeps project-tree records pinned on screen until unpinned.
  const [resultData, setResultData] = useState<TrajectoryData>({
    trajectories: [],
    times: [],
  });
  const [pinned, setPinned] = useState<PinnedRecord[]>([]);
  // top-N 候选会话层（#430）：非选中候选的弧，随每次转移运行整体替换
  // （非用户钉住，不进情景保存与项目树）；候选展示模型同步持有（无轨迹
  // 降级的候选也在面板列参数）。
  // The top-N candidate session layer (#430): non-selected candidate arcs,
  // wholesale-replaced on each transfer run (not user pins — never entering
  // scenario saves or the project tree); the display models ride along
  // (trackless degraded candidates still list parameters in the panel).
  const [candidateLayer, setCandidateLayer] = useState<PinnedRecord[]>([]);
  const [candidateViews, setCandidateViews] = useState<TransferCandidateView[]>([]);
  const [timelineEvents, setTimelineEvents] = useState<TimelineEvent[]>([]);
  const [currentEt, setCurrentEt] = useState<number | null>(null);
  // 分区图层（地月空间分区边界，spatiography_boundaries 产物；固定参照物，
  // 不随结果层替换而消失，受图表设置 regionsVisible 开关控制）
  // Region layer (cislunar partition boundaries from spatiography_boundaries; fixed reference
  // geometry that survives result-layer replacement, toggled by the regionsVisible chart setting).
  const [regionData, setRegionData] = useState<RegionElement[]>([]);

  const [projection, setProjection] = useState<ProjectionMode>("3d");
  const [center, setCenter] = useState<CenterMode>("barycenter");
  // 视图系（#428 第一步，ADR 0013）：显示选择，与数据/时刻语义正交——切
  // 换不改 currentEt、播放状态与任何轨迹数据（TimelineBar 在 props 之外
  // 持有播放态，不受本状态影响）。
  // The view frame (#428 step 1, ADR 0013): a display choice orthogonal to
  // data/time semantics — switching changes no currentEt, playback state, or
  // trajectory data (TimelineBar owns its playback state beyond these props).
  const [frame, setFrame] = useState<FrameMode>("synodic");
  // 绘制内容切换（eph-fig）：双段并存的产物（CR3BP 参考段 + 星历段）画哪段；
  // all 双段同屏。纯显示选择，不改任何数据。
  // The content switch (eph-fig): which segment of a dual-segment product
  // (the CR3BP reference + the ephemeris arc) to draw; all shows both. A
  // display choice that changes no data.
  const [contentMode, setContentMode] = useState<ContentMode>("all");
  // 惯性视图的月球 SPICE 轨迹：按时间轴跨度缓存（moonCacheKey），跨度变
  // 化失效重取；切换回会合视图不清缓存。
  // The Moon's SPICE track for the inertial view: cached by timeline span
  // (moonCacheKey), refetched when the span changes; switching back to the
  // synodic view keeps the cache.
  const [moonTrack, setMoonTrack] = useState<MoonTrack | null>(null);
  const moonCacheKeyRef = useRef("");

  const [api, setApi] = useState<CanvasApi | null>(null);
  const [chart, setChart] = useChartSettings();
  const [chartModalOpen, setChartModalOpen] = useState(false);
  const [stationKeepingOpen, setStationKeepingOpen] = useState(false);
  const [aboutModalOpen, setAboutModalOpen] = useState(false);
  const [updateModalOpen, setUpdateModalOpen] = useState(false);
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null);
  const [recording, setRecording] = useState(false);
  const [progressMsg, setProgressMsg] = useState<string>("");
  const [ephStatus, setEphStatus] = useState<EphemerisStatus | null>(null);

  // 启动时查一次星历配置状态（设置面板展示；数据随 git/安装包分发，
  // 正常情况永远就绪，缺失多为安装损坏或 kernels/ 被删）
  // Query the ephemeris config status once at startup (shown in the settings panel; data ships
  // with git/the installer, so it is normally always ready — absence means a broken install or deleted kernels/).
  useEffect(() => {
    ephemerisStatus().then(setEphStatus).catch(() => setEphStatus(null));
  }, []);

  // 主题与字号持久化
  // Theme and font-size persistence.
  const handleToggleTheme = () => {
    const next = themeMode === "dark" ? "light" : "dark";
    setThemeMode(next);
    localStorage.setItem("tod-theme-mode", next);
  };

  const handleChangeFontSize = (size: number) => {
    setFontSize(size);
    localStorage.setItem("tod-font-size", String(size));
  };

  // 启动后后台静默检查更新
  // Silent update check in the background after startup.
  useEffect(() => {
    const timer = setTimeout(async () => {
      try {
        const update = await checkForAppUpdates();
        if (update) {
          setUpdateInfo(update);
          setUpdateModalOpen(true);
        }
      } catch (e) {
        // 静默检查失败不打扰用户
        // A failed silent check never disturbs the user.
        console.warn("Silent update check failed:", e);
      }
    }, 3000);
    return () => clearTimeout(timer);
  }, []);

  // 监听 sidecar 进度
  // Listen to sidecar progress events.
  useEffect(() => {
    // 同 AssistantSidebar 的监听竞态：StrictMode 双挂载下泄漏首个监听器
    // Same listen race as AssistantSidebar: StrictMode double-mount leaks the
    // first mount's listener.
    let cancelled = false;
    let unlisten: (() => void) | undefined;
    import("@tauri-apps/api/event").then(({ listen }) => {
      listen<{ meta: { message: string } }>("sidecar-progress", (ev) => {
        setProgressMsg(ev.payload.meta.message);
      }).then((u) => {
        if (cancelled) {
          u();
          return;
        }
        unlisten = u;
      });
    });
    return () => {
      cancelled = true;
      unlisten?.();
    };
  }, []);

  const refreshArtifacts = useCallback(async () => {
    const list = await listArtifacts();
    setArtifacts(list);
  }, []);

  useEffect(() => {
    refreshArtifacts();
  }, [refreshArtifacts]);

  // 结果层写入：新内容整体替换，事件旗标（若有）随本次运行重置。当前时刻
  // 置空——红点不自动出现，待用户拖动时间轴或播放后出现。
  // 视图适配不在此同步触发，改由下方 useEffect 在 canvasData 提交后驱动（#438）。
  // Result-layer write: the new content replaces wholesale; event flags (if any)
  // reset with this run. The current moment resets to null so the time marker
  // never appears automatically — it shows only after the user drags or plays.
  // View fitting is not triggered here synchronously; the useEffect below drives it
  // after canvasData commits (#438).
  const applyTrajectoryData = (data: TrajectoryData, events: TimelineEvent[] = []) => {
    setResultData(data);
    setTimelineEvents(events);
    setCurrentEt(null);
  };

  // 画布装配（useMemo）：固定层在前、结果层在后拼一条数组；时间轴按
  // ADR 0021 修订的两级基准——任一 et 产物在屏即全局 et 钟，相对/无基准
  // 轨迹置空时刻（marker 自动隐藏），相对与绝对不混排。
  // Canvas assembly (useMemo): pinned layer first, result layer second, one array; the
  // timeline follows the ADR 0021 revised two-tier basis — any et product on
  // screen switches to the global et clock, relative/untimed trajectories get
  // blanked times (markers hide), and relative never mixes with absolute.
  const canvasData = useMemo(() => {
    // 固定层 = 用户钉住的记录 + 本轮候选弧（#430）：候选排在钉住记录之后，
    // 钉住记录的色环序跨运行稳定。绘制内容切换（eph-fig）逐层先过滤：
    // cr3bp/ephemeris 模式下双段产物只保留对应段，无段语义层原样保留。
    // The fixed layer = user-pinned records plus this run's candidate arcs
    // (#430): candidates trail the pins so the pins' color-cycle indices stay
    // stable across runs. The content switch (eph-fig) filters per layer
    // first: cr3bp/ephemeris modes keep the matching segment of dual-segment
    // products, untagged layers pass through.
    const layers = [
      ...pinned.map((p) => filterByRole(p.data, contentMode)),
      ...candidateLayer.map((c) => filterByRole(c.data, contentMode)),
      filterByRole(resultData, contentMode),
    ];
    const combined: TrajectoryData = {
      trajectories: layers.flatMap((l) => l.trajectories),
      times: layers.flatMap((l) => l.times),
      timeBasis: layers.flatMap((l) => l.timeBasis ?? l.trajectories.map(() => "relative" as const)),
      frames: layers.flatMap((l) => l.frames ?? l.trajectories.map(() => "synodic_nd" as const)),
      labels: layers.flatMap((l) => l.labels ?? l.trajectories.map(() => "")),
      // Jacobi 逐层拼接：未携带的层补 undefined（色环回退），归一化在画布侧
      // 按全屏有值轨迹计算（#435）
      // Jacobi concatenated per layer: layers without it fill undefined (color-cycle
      // fallback); normalization happens canvas-side over all valued trajectories (#435).
      jacobi: layers.flatMap(
        (l) => l.jacobi ?? l.trajectories.map(() => undefined),
      ),
      // 惯性几何逐层拼接（#428 第二步）：未携带的层补 null（无惯性段，
      // 惯性视图下照灰显口径处理）。
      // Inertial geometry concatenated per layer (#428 step 2): layers without
      // it fill null (no inertial segment — the degraded-graying case in the
      // inertial view).
      inertialGeometries: layers.flatMap(
        (l) =>
          l.inertialGeometries ??
          l.trajectories.map(() => null as number[][] | null),
      ),
    };
    const mode = timelineMode(combined);
    return {
      ...combined,
      displayTimes: timesForMode(combined, mode),
      mode,
      timeRange: trajectoryTimeRange(timesForMode(combined, mode)),
    };
  }, [pinned, candidateLayer, resultData, contentMode]);

  // 自动视图适配（#438 确认式，不再用固定时长 setTimeout）：canvasData 提交后
  // 适配一次。React 保证子组件（OrbitCanvas）的几何重建 effect 先于本父组件
  // effect 运行，故此处轨道包围盒已就绪，与几何构建耗时无关；api 未就绪或画面
  // 无内容时不适配。覆盖原两处调用点：结果层写入（applyTrajectoryData）与固定层
  // 增减——两者都改变 canvasData。用户手动 fitView（工具栏）不变。
  // Auto view-fit (#438, confirmed instead of a fixed setTimeout): fit once after
  // canvasData commits. React guarantees the child (OrbitCanvas) geometry-rebuild
  // effect runs before this parent effect, so the orbit bounding box is ready here
  // regardless of how long geometry construction takes; skip when api is not ready
  // or the canvas is empty. Covers both former call sites — result-layer write
  // (applyTrajectoryData) and pinned-layer changes — since both alter canvasData.
  // The manual fitView (toolbar) is unchanged.
  useEffect(() => {
    if (!api || canvasData.trajectories.length === 0) return;
    api.fitView();
  }, [canvasData, api]);

  // 惯性视图的月球轨迹获取（#428）：仅 et 钟模式下有时间轴跨度可取；经
  // run_tool 调 spacetime_transform（synodic_to_j2000，旋转链由 SPICE 真实
  // 月历构造）取跨度内月球位置序列。按跨度缓存（中点历元由跨度唯一决
  // 定，不单独判失效）；失败降级为无月球（ADR 0013 离线降级）并提示。
  // Moon-track fetching for the inertial view (#428): only the et-clock mode
  // offers a timeline span to sample; run_tool calls spacetime_transform
  // (synodic_to_j2000, the rotation chain built from the real SPICE lunar
  // ephemeris) for the Moon's positions across the span. Cached by span (the
  // midpoint epoch follows uniquely from the span, no separate invalidation);
  // failures degrade to no Moon (the ADR 0013 offline fallback) with a hint.
  useEffect(() => {
    if (frame !== "inertial" || canvasData.mode !== "et" || !canvasData.timeRange) return;
    const [lo, hi] = canvasData.timeRange;
    const key = `${lo.toFixed(1)}|${hi.toFixed(1)}`;
    if (key === moonCacheKeyRef.current) return;
    moonCacheKeyRef.current = key;
    let cancelled = false;
    (async () => {
      try {
        const resp = await runTool("spacetime_transform", {
          ...moonTrackRequest([lo, hi]),
        });
        if (cancelled) return;
        if (resp.error) {
          throw new Error(String(resp.error.message ?? resp.error.code));
        }
        const track = moonTrackFromResponse(resp.data, [lo, hi]);
        if (!track) throw new Error("bad spacetime_transform payload");
        setMoonTrack(track);
      } catch (e) {
        if (!cancelled) {
          setMoonTrack(null);
          console.warn("月球惯性轨迹获取失败", e);
          message.warning(t("canvas.moon_track_failed"));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [frame, canvasData.mode, canvasData.timeRange, t]);

  // 库记录工件 → 画布轨迹（选中查看 / 绘制所选 / 钉住共用）。
  // 记录可含 CR3BP 段与星历段（双段并存，CONTEXT.md）：CR3BP 闭曲线之外，
  // eph/ 星历段（会合系无量纲 + UTC 分量 → et）同样入画——修"设计产物
  // 只画周期曲线、星历弧不可见"（会话诊断 2026-08-30）。
  // An orbit artifact record → canvas data (shared by select / plot-selected / pin).
  // A record may hold both the CR3BP segment and the ephemeris segment
  // (CONTEXT.md): beyond the closed CR3BP curve, the eph/ segment (dimensionless
  // synodic + UTC components → et) is drawn too.
  const parseArtifactToTrajectoryData = (
    data: Awaited<ReturnType<typeof getArtifact>>,
  ): TrajectoryData | null => {
    let base: TrajectoryData | null = null;
    // 转移记录（#428 第二步）：transfer/ 段与 live 响应共用同一解析函数
    // （位置 ÷DU_KM 归一、tli_epoch → et 基准、gcrs 惯性段随行携带）；
    // 转移记录无 CR3BP/星历段，早返回不走下面的双段合并。
    // A transfer record (#428 step 2): the transfer/ segment goes through the
    // same parse as the live response (positions ÷DU_KM, tli_epoch → the et
    // basis, the gcrs inertial segment riding along); transfer records carry
    // no CR3BP/ephemeris segments, so the dual-segment merge below is skipped.
    if (data.transfer && data.transfer.states.length > 0) {
      return transferTrajectoryToCanvasData(
        data.transfer.states,
        data.transfer.times,
        data.transfer.tliEpoch ?? undefined,
        t("canvas.transfer_arc"),
        data.transfer.gcrsStates ?? null,
      );
    }
    if (data.familyMembers && data.familyMembers.length > 0) {
      // 成员自带 jacobi 优先；族成员表缺值时回退记录级 jacobi（设计轨道单条通道，#435）
      // A member's own jacobi wins; the record-level jacobi is the fallback for
      // member tables lacking it (the single-orbit design-record channel, #435).
      base = familyMembersToTrajectoryData(data.familyMembers, data.mu ?? EARTH_MOON_MU, data.jacobi);
    } else if (data.members && data.members.length > 0) {
      // 裸点集无时刻：每成员是 n×3 平铺数组，重排为 xyz 点列
      // Bare point sets carry no times: each member is a flat n×3 array, reshaped into xyz points.
      const pts = data.members
        .map((flat) => {
          const rows: number[][] = [];
          for (let i = 0; i + 3 <= flat.length; i += 3) {
            rows.push([flat[i], flat[i + 1], flat[i + 2]]);
          }
          return rows;
        })
        .filter((rows) => rows.length > 0);
      base = {
        trajectories: pts,
        times: pts.map(() => []),
        timeBasis: pts.map(() => "none" as const),
        frames: pts.map(() => "synodic_nd" as const),
        jacobi: pts.map(() => undefined),
      };
    }
    const ephTd = data.ephemeris
      ? designEphemerisToCanvasData(
          data.ephemeris as unknown as Record<string, unknown>,
          t("canvas.design_ephemeris"),
        )
      : null;
    if (!ephTd) return base;
    if (!base || base.trajectories.length === 0) return ephTd;
    // 星历段与 CR3BP 段是同一条轨道：单条 base 时星历段同携该 Jacobi 值（#435）。
    // The ephemeris segment is the same orbit as the CR3BP segment: with a single-
    // trajectory base it carries the same Jacobi value (#435).
    const ephJacobi =
      base.trajectories.length === 1 ? base.jacobi?.[0] : undefined;
    // 星历段惯性几何（eph-fig）：槽位与轨迹逐条对齐——base 轨迹（族成员/
    // 裸点集，会合系）无惯性几何填 null，星历段带则追加。
    // The ephemeris segment's inertial geometry (eph-fig): slots align with
    // trajectories — base trajectories (family members / bare point sets,
    // synodic) fill null, the ephemeris arc's own geometry appends when
    // carried.
    const ephInertial = ephTd.inertialGeometries?.[0] ?? null;
    return {
      trajectories: [...base.trajectories, ...ephTd.trajectories],
      times: [...base.times, ...ephTd.times],
      timeBasis: [
        ...(base.timeBasis ?? base.trajectories.map(() => "relative" as const)),
        ...(ephTd.timeBasis ?? ephTd.trajectories.map(() => "none" as const)),
      ],
      frames: [
        ...(base.frames ?? base.trajectories.map(() => "synodic_nd" as const)),
        ...(ephTd.frames ?? ephTd.trajectories.map(() => "synodic_nd" as const)),
      ],
      labels: [
        ...base.trajectories.map(() => t("canvas.cr3bp_reference")),
        ...(ephTd.labels ?? []),
      ],
      jacobi: [
        ...(base.jacobi ?? base.trajectories.map(() => undefined)),
        ...ephTd.trajectories.map(() => ephJacobi),
      ],
      ...(ephInertial
        ? {
            inertialGeometries: [
              ...base.trajectories.map(() => null),
              ephInertial,
            ],
          }
        : {}),
      // 段角色（eph-fig）：base 是 CR3BP 参考段，星历段自带 ephemeris 标注
      // Segment roles (eph-fig): base is the CR3BP reference segment; the
      // ephemeris arc carries its own ephemeris tag.
      roles: [
        ...base.trajectories.map(() => "cr3bp" as const),
        ...(ephTd.roles ?? ephTd.trajectories.map(() => "ephemeris" as const)),
      ],
    };
  };

  // 图钉切换：钉住 = 拉取记录解析进固定层（软上限提示）；取消 = 移出。
  // Pushpin toggle: pin = fetch and parse the record into the pinned layer (soft-cap hint);
  // unpin = remove it.
  const handleTogglePin = async (item: ArtifactSummary) => {
    const rid = item.recordId;
    if (!rid) return;
    if (pinned.some((p) => p.recordId === rid)) {
      setPinned((prev) => prev.filter((p) => p.recordId !== rid));
      return;
    }
    if (pinned.length >= PINNED_LIMIT) {
      message.warning(t("tree.pin_limit"));
      return;
    }
    try {
      const data = await getArtifact(rid);
      const td = parseArtifactToTrajectoryData(data);
      if (!td || td.trajectories.length === 0) {
        message.warning(t("tree.pin_load_failed"));
        return;
      }
      // 图例显示记录名（Q8 决策）：每条轨迹一个标签；双段记录带段名
      // （记录名·CR3BP 参考 / 记录名·星历段）。
      // Legend shows the record name (Q8 decision): one label per trajectory;
      // dual-segment records carry a segment tag.
      const segLabels =
        td.labels && td.labels.length === td.trajectories.length
          ? td.labels.map((l) => `${item.label}·${l}`)
          : td.trajectories.map(() => item.label);
      const labeled: TrajectoryData = {
        ...td,
        labels: segLabels,
      };
      setPinned((prev) => [...prev, { recordId: rid, label: item.label, data: labeled }]);
    } catch {
      message.error(t("tree.pin_load_failed"));
    }
  };

  // 选中记录时，从 catalog 拉取详细信息与轨迹（进结果层，替换上次内容）
  // When a record is selected, fetch its details and trajectory from the catalog
  // (into the result layer, replacing the previous content).
  const handleSelectArtifact = async (a: ArtifactSummary | null) => {
    setSelectedArtifact(a);
    if (!a) {
      setSelectedRecordDetail(null);
      return;
    }

    try {
      if (a.recordId) {
        const queryResp = await catalogQuery({ record_id: a.recordId });
        if (queryResp.records && queryResp.records.length > 0) {
          setSelectedRecordDetail(queryResp.records[0]);
        }
        const data = await getArtifact(a.recordId);
        const td = parseArtifactToTrajectoryData(data);
        if (td && td.trajectories.length > 0) {
          applyTrajectoryData(td);
        }
      }
    } catch (e) {
      console.error("加载记录失败", e);
    }
  };

  // —— AI 助手产物（ADR 0022 A1：AI 产物与手动运行同一棵项目树）——
  // AI 工具产出 record_id 时自动登记入项目树（与 run_tool 手动运行同语义），
  // ref 去重防止重复登记；画布绘图走既有 getArtifact 通道按需触发。
  // AI assistant artifacts (ADR 0022 A1: AI artifacts share the manual-run
  // project tree). A record_id from an AI tool auto-registers into the project
  // tree (same semantics as a manual run_tool), deduped via a ref; canvas
  // plotting goes through the existing getArtifact channel on demand.
  const assistantRegistered = useRef<Set<string>>(new Set());

  const handleAssistantArtifact = async (recordId: string, tool: string) => {
    if (assistantRegistered.current.has(recordId)) return;
    assistantRegistered.current.add(recordId);
    try {
      const entry = TOOL_REGISTRY.find((t) => t.name === tool);
      await registerArtifact({
        artifactType: entry?.artifactType ?? "orbit",
        label: `AI · ${entry?.title ?? tool}`,
        orbitType: undefined,
        sourceTool: tool,
        recordId,
      });
      await refreshArtifacts();
    } catch (e) {
      console.warn("AI 产物登记失败", e);
    }
  };

  const handleAssistantOpenRecord = async (recordId: string) => {
    try {
      const data = await getArtifact(recordId);
      const td = parseArtifactToTrajectoryData(data);
      if (td && td.trajectories.length > 0) {
        applyTrajectoryData(td);
      }
    } catch (e) {
      message.error(`${t("record.load_failed")}: ${String(e)}`);
    }
  };

  // 助手随消息携带的当前选择上下文（态势层素材，ADR 0023 决策 5）
  // The selection context the assistant carries with each message (situation-layer
  // material, ADR 0023 decision 5).
  const assistantSelection: SelectionContext | null = selectedArtifact
    ? {
        recordId: selectedArtifact.recordId,
        label: selectedArtifact.label,
        artifactType: selectedArtifact.artifactType,
        orbitType: selectedArtifact.orbitType,
      }
    : null;

  // 勾选多条后“绘制所选”：逐条复用解析链路，轨迹/时刻/基准拼接成一份结果层数据；
  // 单条失败跳过并提示，不阻塞其余。
  // "Plot Selected" after multi-check: reuse the parse chain per record, concatenate
  // trajectories/times/bases into one result-layer dataset; a failed record is skipped with a hint.
  const handlePlotSelected = async (items: ArtifactSummary[]) => {
    const trajParts: number[][][] = [];
    const timeParts: number[][] = [];
    const basisParts: TimeBasis[] = [];
    const frameParts: DataFrameTag[] = [];
    const labelParts: string[] = [];
    for (const item of items) {
      if (!item.recordId) continue;
      try {
        const data = await getArtifact(item.recordId);
        const td = parseArtifactToTrajectoryData(data);
        if (td) {
          trajParts.push(...td.trajectories);
          timeParts.push(...td.times);
          basisParts.push(...(td.timeBasis ?? td.trajectories.map(() => "relative" as const)));
          frameParts.push(...(td.frames ?? td.trajectories.map(() => "synodic_nd" as const)));
          labelParts.push(
            ...(td.labels && td.labels.length === td.trajectories.length
              ? td.labels.map((l) => `${item.label}·${l}`)
              : td.trajectories.map(() => item.label)),
          );
        }
      } catch (e) {
        message.warning(`${t("tree.plot_skip_failed")}: ${item.label}`);
      }
    }
    if (trajParts.length > 0) {
      applyTrajectoryData({
        trajectories: trajParts,
        times: timeParts,
        timeBasis: basisParts,
        frames: frameParts,
        labels: labelParts,
      });
    }
  };

  // —— 情景 v1（#429，grilling 2026-08-30 定稿）：固定层记录集 + 参考历元
  // + 播放配置的保存/打开。播放配置归 App 持有（TimelineBar 只上报变
  // 更），情景保存时随当前历元一并导出。——
  // Scenario v1 (#429, finalized by the 2026-08-30 grilling): save/open of
  // the pinned-layer record set + reference epoch + playback config. App owns
  // the playback config (TimelineBar only reports changes); scenario save
  // exports it alongside the current epoch.
  const [playback, setPlayback] = useState<ScenarioPlayback>(DEFAULT_PLAYBACK);

  // 保存情景：仅 et 钟模式（有真实历元产物）且固定层非空时可存——情景的
  // 核心语义是固定层+历元回放，相对时刻模式下无 et 基准、语义不完整。
  // 当前历元即参考历元；对话框取消静默。
  // Save a scenario: storable only in et-clock mode (a real-epoch product on
  // screen) with a non-empty pinned layer — the scenario's core semantics are
  // pinned layer + epoch replay, meaningless without the et basis in relative
  // mode. The current moment becomes the reference epoch; a cancelled dialog
  // stays silent.
  const handleSaveScenario = async () => {
    if (pinned.length === 0) {
      message.warning(t("scenario.save_empty_pinned"));
      return;
    }
    if (canvasData.mode !== "et" || currentEt === null) {
      message.warning(t("scenario.save_needs_et"));
      return;
    }
    const text = serializeScenario({
      records: pinned.map((p) => p.recordId),
      referenceEpoch: { et: currentEt },
      playback: { ...playback, startOffsetEt: 0 },
    });
    try {
      const saved = await saveScenarioFile(text);
      if (saved) message.success(t("scenario.saved"));
    } catch (e) {
      message.error(`${t("scenario.save_failed")}: ${String(e)}`);
    }
  };

  // 打开情景：逐 record_id 解析重建固定层（缺失跳过并列出、超上限截
  // 断，均提示不静默）；时间轴校准到参考历元（含播放起点偏移）；应用
  // 播放配置。结果层不动（情景只描述固定层）。对话框与助手「应用情景」
  // 共用同一条解析路径（ADR 0027）。
  // Open a scenario: resolve record ids one by one to rebuild the pinned layer
  // (missing ones skipped and listed, over-cap references truncated — both
  // hinted, never silent); calibrate the timeline onto the reference epoch
  // (with the playback start offset); apply the playback config. The result
  // layer stays untouched (a scenario describes only the pinned layer). The
  // dialog and the assistant's "apply scenario" share this one parse path
  // (ADR 0027).
  const applyScenarioText = async (text: string) => {
    const parsed = parseScenario(text);
    if ("error" in parsed) {
      message.error(parsed.error);
      return;
    }
    const fetchRecord = async (rid: string): Promise<PinnedRecord | null> => {
      try {
        // 项目树是会话内的（重启即空）：label 从 catalog 记录合成，不依赖
        // 项目树现状。
        // The project tree is session-scoped (empty after restart): the label
        // synthesizes from the catalog record, independent of the tree.
        let label = rid;
        try {
          const resp = await catalogQuery({ record_id: rid });
          const family = resp.records?.[0]?.orbit_family;
          if (family) label = `${family}·${rid.slice(0, 8)}`;
        } catch {
          // label 合成失败不阻塞轨迹解析，退回 rid
          // A failed label synthesis never blocks trajectory resolution; fall
          // back to the rid.
        }
        const data = await getArtifact(rid);
        const td = parseArtifactToTrajectoryData(data);
        if (!td || td.trajectories.length === 0) return null;
        const segLabels =
          td.labels && td.labels.length === td.trajectories.length
            ? td.labels.map((l) => `${label}·${l}`)
            : td.trajectories.map(() => label);
        return { recordId: rid, label, data: { ...td, labels: segLabels } };
      } catch {
        return null;
      }
    };
    let resolution: Awaited<ReturnType<typeof resolveScenarioRecords<PinnedRecord>>>;
    try {
      resolution = await resolveScenarioRecords(parsed.scenario.records, PINNED_LIMIT, fetchRecord);
    } catch (e) {
      message.error(`${t("scenario.open_failed")}: ${String(e)}`);
      return;
    }
    setPinned(resolution.resolved);
    if (resolution.missing.length > 0) {
      message.warning(
        t("scenario.missing_records").replace("{ids}", resolution.missing.join("、")),
      );
    }
    if (resolution.truncated) {
      message.warning(t("scenario.truncated").replace("{limit}", String(PINNED_LIMIT)));
    }
    setPlayback(parsed.scenario.playback);
    setCurrentEt(parsed.scenario.referenceEt + parsed.scenario.playback.startOffsetEt);
    if (resolution.resolved.length > 0) {
      message.success(
        t("scenario.opened").replace("{count}", String(resolution.resolved.length)),
      );
    }
  };

  const handleOpenScenario = async () => {
    let text: string | null;
    try {
      text = await openScenarioFile();
    } catch (e) {
      message.error(`${t("scenario.open_failed")}: ${String(e)}`);
      return;
    }
    if (text === null) return;
    await applyScenarioText(text);
  };

  // 助手「应用情景」（ADR 0027）：scenario_write 完成卡片的同语义跳转——
  // 按路径直读（不经对话框），复用手动打开的解析/软失败路径。
  // The assistant's "apply scenario" (ADR 0027): the same-semantics jump from
  // a completed scenario_write card — read by path (no dialog) and reuse the
  // manual-open parse/soft-failure path.
  const handleApplyScenario = async (path: string) => {
    let text: string;
    try {
      const { invoke } = await import("@tauri-apps/api/core");
      text = await invoke<string>("open_scenario", { path });
    } catch (e) {
      message.error(`${t("scenario.open_failed")}: ${String(e)}`);
      return;
    }
    await applyScenarioText(text);
  };

  // 星标/备注保存成功后同步树行数据（本地更新，不重查整表）
  // Sync the tree row after a successful star/note save (local update; no full re-query).
  const updateArtifactMeta = (recordId: string, tags: string[], note?: string) => {
    setArtifacts((prev) =>
      prev.map((a) =>
        a.recordId === recordId ? { ...a, tags, ...(note !== undefined ? { note } : {}) } : a
      )
    );
  };
  // 执行通用工具（提交前防呆校验：必填/越界不过则不提交）
  // Run the generic tool (preflight checks before submit: missing required fields or out-of-range values block submission).
  const handleRunTool = async () => {
    const entry = toolEntry(selectedTool);
    const issues = validateToolParams(selectedTool, entry.schema, toolParams);
    if (issues.length > 0) {
      setParamIssues(Object.fromEntries(issues.map((i) => [i.field, i.reason])));
      message.error(issues.map((i) => `${i.label}(${i.field}): ${i.reason}`).join("；"));
      return;
    }

    setBusy(true);
    setProgressMsg(t("run.submitting"));
    try {
      const cleaned = Object.fromEntries(
        Object.entries(toolParams).filter(([, v]) => v !== null && v !== undefined && v !== "")
      );

      // LGA/WSB 目标注入（legacy facade_bridge.py 同款）：取项目树选中轨道
      // 工件 CR3BP 状态序列末行，换算会合系物理 km/km/s 注入 target_ephemeris
      // （e2m2e#516 契约）；LGA 无显式搜索参数时注入加密相位网格。未选中
      // 工件则拦截提交（老 PyQt 行为：状态栏拦截）。
      // LGA/WSB target injection (same as the legacy facade_bridge.py): take
      // the last row of the selected orbit artifact's CR3BP state sequence,
      // convert to rotating-frame physical km/km/s for target_ephemeris
      // (e2m2e#516 contract); inject the denser phase grid when LGA search
      // params are absent. Block submission without a selection (matching the
      // legacy PyQt interception).
      if (
        selectedTool === "transfer_design" &&
        (cleaned.transfer_type === "LGA" || cleaned.transfer_type === "WSB")
      ) {
        if (!selectedArtifact?.recordId) {
          message.warning(t("run.lga_needs_target"));
          return;
        }
        try {
          const art = await getArtifact(selectedArtifact.recordId);
          const s = art.familyMembers?.[0]?.states;
          if (!s || s.length < 6) {
            message.warning(t("run.lga_no_states"));
            return;
          }
          const rows: number[][] = [];
          for (let i = 0; i + 6 <= s.length; i += 6) rows.push(s.slice(i, i + 6));
          const last = rows[rows.length - 1];
          cleaned.target_ephemeris = [
            ...last.slice(0, 3).map((v) => v * DU_KM),
            ...last.slice(3, 6).map((v) => (v * DU_KM) / TU_SECONDS),
          ];
        } catch (e) {
          message.error(`${t("run.artifact_load_failed")}: ${String(e)}`);
          return;
        }
        if (cleaned.transfer_type === "LGA" && !cleaned.lga_search_params) {
          cleaned.lga_search_params = { n_departure_phase: 360, n_tof: 5 };
        }
      }

      const resp = await runTool(
        selectedTool,
        cleaned,
        entry.binaryDtype ?? undefined,
        entry.artifactType
          ? {
              artifactType: entry.artifactType,
              label: `${entry.title} - ${new Date().toLocaleTimeString()}`,
              orbitType: (cleaned.orbit_type as string) || undefined,
              }
          : undefined
      );

      if (resp.error) {
        // 错误优先取 message 字段以人话呈现（#450），不再整体 JSON 序列化
        // Prefer the error message field (#450) over dumping the whole serialized object.
        message.error(`${t("run.error_prefix")}: ${formatToolError(resp.error)}`);
        return;
      }

      message.success(t("run.complete"));
      await refreshArtifacts();

      // 新一轮计算开始：上一轮的候选会话层整体清空（#430）——候选集属于
      // 产生它的那次转移运行；转移分支随后重建。
      // A new run begins: the previous candidate session layer clears wholesale
      // (#430) — the candidate set belongs to the transfer run that produced
      // it; the transfer branch rebuilds it right after.
      setCandidateLayer([]);
      setCandidateViews([]);

      // 分区边界（spatiography_boundaries）：元素进区域图层（regionLayer），
      // 不进结果层——固定参照物语义，结果层/时间轴链路全部旁路。
      // Spatiography boundaries: elements go to the region layer (regionLayer), not the
      // result layer — fixed-reference semantics, bypassing the result/timeline chain entirely.
      if (selectedTool === "spatiography_boundaries" && resp.data) {
        const d = resp.data as { elements?: BoundaryElementPayload[] };
        setRegionData(boundariesResponseToRegionLayer(d, EARTH_MOON_MU));
        message.info(t("run.regions_updated").replace("{n}", String(d.elements?.length ?? 0)));
        return;
      }

      // 若有轨迹数据，装配到画布（解析逻辑见 trajectoryParsing）
      // If trajectory data is present, assemble it onto the canvas (parsing logic in trajectoryParsing).
      if (resp.frames && resp.frames.length > 0) {
        const td = framesToTrajectoryData(resp.frames, resp.data, EARTH_MOON_MU);
        if (td.trajectories.length > 0) {
          applyTrajectoryData(td);
        }
      } else if (resp.data) {
        const d = resp.data as any;
        // 转移设计（e2m2e ≥5.9.0，ADR 0040）：trajectory 是会合系物理 km/km/s，
        // ÷DU_KM 归一后上画布；trajectory_times（TLI 起算秒）+ 提交的
        // tli_epoch → et 绝对基准接时间轴；details 现成字段 → 出发/到达
        // 脉冲旗标（Q9：近月点无时刻字段，不做）。
        // Transfer design (e2m2e ≥5.9.0, ADR 0040): trajectory is rotating-frame
        // physical km/km/s — normalize by DU_KM; trajectory_times (seconds
        // since TLI) plus the submitted tli_epoch give the et absolute basis;
        // ready-made details fields feed the departure/arrival pulse flags
        // (Q9: perilune has no time field, skipped).
        if (Array.isArray(d.trajectory) && d.trajectory.length > 0) {
          const tliEpoch = cleaned.tli_epoch as string | number | undefined;
          const td = transferTrajectoryToCanvasData(
            d.trajectory,
            d.trajectory_times,
            tliEpoch,
            t("canvas.transfer_arc"),
            // 惯性段（#428 第二步，e2m2e 5.9.1 trajectory_gcrs_km）：low_thrust
            // 与零结果为 null，解析层自行降级
            // The inertial segment (#428 step 2, e2m2e 5.9.1
            // trajectory_gcrs_km): null for low_thrust and zero results — the
            // parsing layer degrades on its own.
            (d.trajectory_gcrs_km as number[][] | null | undefined) ?? null,
          );
          // —— top-N 可行解（#430，e2m2e 5.9.1 candidates）：恰一候选
          //（low_thrust/HMN 或未开启）退化为单解现状；多候选时非选中解入
          // 候选会话层（受固定层上限约束），面板并列参数，TLI 时刻加 chip。 ——
          // —— top-N feasible solutions (#430, e2m2e 5.9.1 candidates): a
          // single candidate (low_thrust/HMN, or top_n off) degrades to the
          // single-solution status quo; with several, non-selected ones enter
          // the candidate session layer (bounded by the pinned-layer cap),
          // the panel lists parameters side by side, and TLI moments get chips. ——
          const rawCandidates = Array.isArray(d.candidates) ? (d.candidates as Record<string, unknown>[]) : null;
          let events = transferEventsFromDetails(d.details, tliEpoch, t);
          if (rawCandidates && rawCandidates.length > 1) {
            const views: TransferCandidateView[] = [];
            const arcs: PinnedRecord[] = [];
            const chips: TimelineEvent[] = [];
            const trackless: number[] = [];
            const headroom = Math.max(0, PINNED_LIMIT - pinned.length);
            let truncated = false;
            rawCandidates.forEach((c, i) => {
              const rank = i + 1;
              const hasTrajectory = Array.isArray(c.trajectory) && c.trajectory.length > 0;
              views.push({
                key: `cand-${rank}`,
                rank,
                deltaVKmS: Number(c.delta_v_km_s),
                tliEpochText:
                  c.tli_epoch === undefined || c.tli_epoch === null
                    ? t("panel.cand_no_epoch")
                    : String(c.tli_epoch),
                tofSecText:
                  c.tof_sec === undefined || c.tof_sec === null
                    ? t("panel.cand_no_epoch")
                    : `${(Number(c.tof_sec) / 86400).toFixed(1)} ${t("unit.days")}`,
                selected: c.selected === true,
                refined: c.refined === true,
                hasTrajectory,
              });
              if (c.selected === true || !hasTrajectory) {
                if (!hasTrajectory) trackless.push(rank);
                return;
              }
              if (arcs.length >= headroom) {
                truncated = true;
                return;
              }
              const arc = transferCandidateToArcData(
                {
                  trajectory: c.trajectory,
                  trajectory_times: c.trajectory_times,
                  tli_epoch: c.tli_epoch,
                },
                t("canvas.transfer_candidate")
                  .replace("{k}", String(rank))
                  .replace("{dv}", Number(c.delta_v_km_s).toFixed(2)),
              );
              if (!arc) {
                trackless.push(rank);
                return;
              }
              arcs.push({ recordId: `cand-${rank}`, label: `#${rank}`, data: arc.data });
              if (arc.tliEt !== null) {
                chips.push({
                  et: arc.tliEt,
                  label: t("event.candidate_pulse").replace("{k}", String(rank)),
                  dv: `${Number(c.delta_v_km_s).toFixed(2)} km/s`,
                });
              }
            });
            setCandidateLayer(arcs);
            setCandidateViews(views);
            if (truncated) {
              message.warning(t("transfer.candidates_truncated").replace("{n}", String(headroom)));
            }
            if (trackless.length > 0) {
              message.warning(t("transfer.candidates_trackless").replace("{ks}", trackless.map((k) => `#${k}`).join("、")));
            }
            events = [...events, ...chips];
          }
          applyTrajectoryData(td, events);
        } else {
          // 轨道预报（#421 修复）：position_km 是 GCRS 惯性 km，÷DU_KM 后按
          // 惯性系几何如实绘制并图例标注（惯性视图落地前），times_jd_tdb →
          // et 基准。state_frame 契约（ADR 0040 增补）到位后按标签替换硬编码。
          // Orbit propagation (#421 fix): position_km is GCRS inertial km —
          // drawn honestly as inertial-frame geometry after ÷DU_KM with a
          // legend note (until the inertial view lands); times_jd_tdb → the et
          // basis. Replace this hardcode by the state_frame label once that
          // contract (ADR 0040 amendment) ships.
          const prop = propagationToCanvasData(
            d.position_km,
            d.times_jd_tdb,
            t("canvas.propagation")
          );
          if (prop) {
            applyTrajectoryData(prop);
          } else {
            // 通用回退：任务轨道设计双段并存（CONTEXT.md：记录可含 CR3BP 段
            // 与星历段）——CR3BP 参考闭曲线（states，会合无量纲）＋ 星历段
            //（ephemeris.synodic_position 会合无量纲 (n,3)，UTC 分量 → et）。
            // 修"画布只见周期曲线"：设计响应本就携带完整星历表，此前无
            // 渲染路径（会话诊断 2026-08-30）。
            // Generic fallback: mission-orbit design dual segments (a record
            // may hold both the CR3BP segment and the ephemeris segment) —
            // the CR3BP reference closed curve (states, dimensionless
            // synodic) plus the ephemeris arc (ephemeris.synodic_position,
            // dimensionless synodic (n,3); UTC components → et). The design
            // response always carried the full ephemeris table — it just had
            // no render path (session diagnosis 2026-08-30).
            const ephTd = designEphemerisToCanvasData(
              d.ephemeris as Record<string, unknown> | null | undefined,
              t("canvas.design_ephemeris")
            );
            const rawStates = d.states;
            const cr3bpPts =
              Array.isArray(rawStates) && rawStates.length > 0 && Array.isArray(rawStates[0])
                ? (rawStates as number[][]).map((s: number[]) => [
                    Number(s[0]),
                    Number(s[1]),
                    Number(s[2]),
                  ])
                : null;
            const relTimes =
              cr3bpPts && Array.isArray(d.times) && d.times.length === cr3bpPts.length
                ? (d.times as unknown[]).map(Number)
                : null;
            const trajectories = [
              ...(cr3bpPts ? [cr3bpPts] : []),
              ...(ephTd?.trajectories ?? []),
            ];
            if (trajectories.length > 0) {
              // 设计响应顶层 cr3bp_jacobi 是该轨道唯一 Jacobi 值：CR3BP 段与
              // 星历段同一轨道，两段同携（#435）
              // The design response's top-level cr3bp_jacobi is the orbit's only
              // Jacobi value: the CR3BP and ephemeris segments are the same orbit
              // and carry it alike (#435).
              const designJacobi =
                typeof d.cr3bp_jacobi === "number" && Number.isFinite(d.cr3bp_jacobi)
                  ? (d.cr3bp_jacobi as number)
                  : undefined;
              // 星历段惯性几何（eph-fig）：CR3BP 参考曲线槽位填 null
              // The ephemeris segment's inertial geometry (eph-fig): the CR3BP
              // reference curve's slot stays null.
              const ephInertial = ephTd?.inertialGeometries?.[0] ?? null;
              applyTrajectoryData({
                trajectories,
                times: [...(cr3bpPts ? [relTimes ?? []] : []), ...(ephTd?.times ?? [])],
                timeBasis: [
                  ...(cr3bpPts ? [(relTimes ? "relative" : "none") as TimeBasis] : []),
                  ...(ephTd?.timeBasis ?? []),
                ],
                frames: [
                  ...(cr3bpPts ? ["synodic_nd" as DataFrameTag] : []),
                  ...(ephTd?.frames ?? []),
                ],
                labels: [
                  ...(cr3bpPts ? [t("canvas.cr3bp_reference")] : []),
                  ...(ephTd?.labels ?? []),
                ],
                jacobi: trajectories.map(() => designJacobi),
                ...(ephInertial
                  ? {
                      inertialGeometries: [
                        ...(cr3bpPts ? [null] : []),
                        ephInertial,
                      ],
                    }
                  : {}),
                roles: [
                  ...(cr3bpPts ? ["cr3bp" as const] : []),
                  ...(ephTd?.roles ?? []),
                ],
              });
            }
          }
        }
      }
    } catch (e) {
      message.error(`${t("run.failed")}: ${String(e)}`);
    } finally {
      setBusy(false);
      setProgressMsg("");
    }
  };

  // 录制动画导出
  // Record and export the animation.
  const handleExportAnimation = async () => {
    if (!api) return;
    const el = api.canvasElement();
    if (!el || !CanvasRecorder.supported()) {
      message.warning(t("run.record_unsupported"));
      return;
    }
    setRecording(true);
    const rec = new CanvasRecorder();
    api.setAutoRotate(true);
    rec.start(el, 30);
    setTimeout(async () => {
      api.setAutoRotate(false);
      const res = await rec.stop();
      if (res) downloadBlob(res.blob, "orbit-animation.webm");
      setRecording(false);
      message.success(t("run.record_done"));
    }, 8000);
  };

  // PNG 静态图导出（#450）：渲染器常驻 RAF 循环逐帧渲染且开启了
  // preserveDrawingBuffer，画布 buffer 始终新鲜，toBlob 直接取当前帧
  // 即所见即所得；文件名带时刻避免重复导出互相覆盖。
  // PNG still-image export (#450): the renderer's continuous RAF loop plus
  // preserveDrawingBuffer keep the drawing buffer fresh, so toBlob grabs the
  // current frame as-seen; the timestamped filename avoids overwrite clashes.
  const handleExportPng = () => {
    const el = api?.canvasElement();
    if (!el) return;
    el.toBlob((blob) => {
      if (blob) {
        downloadBlob(blob, `orbit-view-${new Date().toISOString().replace(/[:.]/g, "-")}.png`);
      }
    }, "image/png");
  };

  const libration = [
    { label: "L1", x: librationPoint(EARTH_MOON_MU, 1) },
    { label: "L2", x: librationPoint(EARTH_MOON_MU, 2) },
  ];

  return (
    <ConfigProvider
      theme={{
        algorithm: themeMode === "dark" ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
        ...themeBehavior,
        token: {
          fontSize: fontSize,
          ...themeTokens,
        },
      }}
    >
      <div
        style={
          {
            display: "flex",
            width: "100vw",
            height: "100vh",
            overflow: "hidden",
            background: themeMode === "dark" ? "#141414" : "#f0f2f5",
            color: themeMode === "dark" ? "#fff" : "#000",
            // --tod-* 主题变量随明暗注入（#450）：助手边栏/会话视图/工具卡片
            // 的 var(--tod-*) 引用在此获得定义，深色不再落到浅色 fallback
            // The --tod-* theme vars injected per theme (#450): the var(--tod-*)
            // references in the assistant sidebar/chat view/tool cards get their
            // definition here — dark mode no longer falls back to light values.
            ...themeCssVars(themeMode),
          } as React.CSSProperties
        }
      >
        {/* 左栏 */}
        <div
          style={{
            width: 280,
            borderRight: themeMode === "dark" ? "1px solid #303030" : "1px solid #e8e8e8",
            display: "flex",
            flexDirection: "column",
            background: themeMode === "dark" ? "#1f1f1f" : "#fff",
            padding: 8,
          }}
        >
          {/* 页签与设置栏：底边指示线页签 + 无边框工具按钮（IDE 侧栏风格） */}
          <div
            style={{
              display: "flex",
              alignItems: "flex-end",
              gap: 10,
              borderBottom: themeMode === "dark" ? "1px solid #303030" : "1px solid #e8e8e8",
              marginBottom: 8,
            }}
          >
            {(
              [
                ["project", t("app.tab.project")],
                ["catalog", t("app.tab.catalog")],
              ] as const
            ).map(([key, label]) => {
              const active = leftTab === key;
              return (
                <Button
                  key={key}
                  type="text"
                  size="small"
                  onClick={() => setLeftTab(key)}
                  style={{
                    padding: "1px 2px 5px",
                    borderRadius: 0,
                    marginBottom: -1,
                    borderBottom: active
                      ? `2px solid ${themeMode === "dark" ? "#4096ff" : "#0958d9"}`
                      : "2px solid transparent",
                    color: active ? (themeMode === "dark" ? "#fff" : "#0958d9") : "inherit",
                    fontWeight: active ? 500 : 400,
                  }}
                >
                  {label}
                </Button>
              );
            })}
            <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 2, paddingBottom: 3 }}>
              <Button
                type="text"
                size="small"
                onClick={() => setLang(lang === "zh" ? "en" : "zh")}
                title={t("app.lang_toggle_title")}
              >
                {lang === "zh" ? "EN" : "中"}
              </Button>
              <Button
                type="text"
                size="small"
                icon={themeMode === "dark" ? <SunOutlined /> : <MoonOutlined />}
                onClick={handleToggleTheme}
                title={t("app.theme_toggle_title")}
              />
              <Button
                type="text"
                size="small"
                icon={<InfoCircleOutlined />}
                onClick={() => setAboutModalOpen(true)}
                title={t("app.about_title")}
              />
            </div>
          </div>

          {/* 列表/过滤内容 */}
          <div style={{ flex: 1, overflowY: "auto", minHeight: 0 }}>
            {leftTab === "catalog" && (
              <CatalogFilterBar onResults={(arts) => setArtifacts(arts)} />
            )}
            <ProjectTree
              artifacts={artifacts}
              selectedId={selectedArtifact?.artifactId || null}
              onSelect={handleSelectArtifact}
              onRemove={async (id) => {
                await removeArtifact(id);
                refreshArtifacts();
              }}
              onOpenStationKeeping={(item) => {
                setSelectedArtifact(item);
                setStationKeepingOpen(true);
              }}
              onRefresh={refreshArtifacts}
              onPlotSelected={handlePlotSelected}
              onMetaChange={updateArtifactMeta}
              pinnedRecordIds={pinned.map((p) => p.recordId)}
              onTogglePin={handleTogglePin}
            />
          </div>

          {/* 详情面板 */}
          <div style={{ maxHeight: 280, overflowY: "auto", borderTop: themeMode === "dark" ? "1px solid #303030" : "1px solid #e8e8e8" }}>
            <RecordDetailPanel
              record={selectedRecordDetail}
              transferCandidates={candidateViews}
              onRefresh={refreshArtifacts}
              onOpenStationKeeping={() => setStationKeepingOpen(true)}
            />
          </div>
        </div>

        {/* 中栏：工具选择与参数面板 */}
        <div
          style={{
            width: 320,
            borderRight: themeMode === "dark" ? "1px solid #303030" : "1px solid #e8e8e8",
            display: "flex",
            flexDirection: "column",
            background: themeMode === "dark" ? "#1a1a1a" : "#fafafa",
            padding: 10,
          }}
        >
          <Title level={5} style={{ margin: "0 0 8px 0" }}>
            {t("panel.tool_title")}
          </Title>
          <Select
            size="small"
            style={{ width: "100%", marginBottom: 8 }}
            value={selectedTool}
            onChange={(val) => {
              setSelectedTool(val);
              setToolParams({});
              setParamIssues({});
            }}
            options={TOOL_REGISTRY.map((t) => ({ label: t.title, value: t.name }))}
          />

          <div style={{ flex: 1, overflowY: "auto", minHeight: 0 }}>
            <ParamsPanel
              toolName={selectedTool}
              schema={toolEntry(selectedTool).schema}
              values={toolParams}
              onChange={(vals) => {
                setToolParams(vals);
                setParamIssues({});
              }}
              fieldErrors={paramIssues}
            />
          </div>

          <div style={{ marginTop: 8 }}>
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              loading={busy}
              onClick={handleRunTool}
              style={{ width: "100%" }}
            >
              {busy ? t("run.executing") : t("run.execute")}
            </Button>
            {progressMsg && (
              <Text type="secondary" style={{ fontSize: 11, display: "block", marginTop: 4 }}>
                {progressMsg}
              </Text>
            )}
          </div>
        </div>

        {/* 右栏：主画布与时间轴 */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
          {/* 画布工具栏：投影/中心选择 + 适配/导出/设置，停靠于画布上方 */}
          <div
            style={{
              background: themeMode === "dark" ? "#1a1a1a" : "#fff",
              borderBottom: themeMode === "dark" ? "1px solid #303030" : "1px solid #e8e8e8",
            }}
          >
            <CanvasToolbar
              projection={projection}
              center={center}
              frame={frame}
              contentMode={contentMode}
              recording={recording}
              onProjectionChange={setProjection}
              onCenterChange={setCenter}
              onFrameChange={setFrame}
              onContentModeChange={setContentMode}
              onFitView={() => api?.fitView()}
              onExportAnimation={handleExportAnimation}
              onExportPng={handleExportPng}
              onOpenSettings={() => setChartModalOpen(true)}
              onSaveScenario={handleSaveScenario}
              onOpenScenario={handleOpenScenario}
            />
          </div>

          {/* Three.js Canvas */}
          <div style={{ flex: 1, minHeight: 0 }}>
            <OrbitCanvas
              trajectories={canvasData.trajectories}
              times={canvasData.displayTimes}
              currentEt={currentEt}
              labels={canvasData.labels}
              frameLabels={canvasData.frames?.map((f, i) =>
                // 惯性视图下带 gcrs 段的转移弧实际画的是惯性几何，标注跟着
                // 换成地心惯性 km（#428 第二步）；其余情形标注随数据系。
                // In the inertial view a gcrs-carrying transfer arc actually
                // draws its inertial geometry, so the note switches to
                // geocentric inertial km (#428 step 2); otherwise the note
                // follows the data frame.
                frame === "inertial" && canvasData.inertialGeometries?.[i]
                  ? t("canvas.frame.inertial_km")
                  : t(`canvas.frame.${f}`)
              )}
              jacobi={canvasData.jacobi}
              regions={regionData}
              frame={frame}
              dataFrames={canvasData.frames}
              inertialGeometries={canvasData.inertialGeometries}
              moonTrack={frame === "inertial" ? moonTrack : null}
              synodicUnavailableNote={t("canvas.frame.synodic_unavailable")}
              mu={EARTH_MOON_MU}
              libration={libration}
              projection={projection}
              center={center}
              settings={chart}
              background={chart.bgColor ?? (themeMode === "dark" ? "#121212" : "#ffffff")}
              onReady={(a) => setApi(a)}
            />
          </div>

          {/* 底部时间轴 */}
          <div style={{ padding: "4px 8px", background: themeMode === "dark" ? "#1a1a1a" : "#fff" }}>
            <TimelineBar
              timeRange={canvasData.timeRange}
              currentEt={currentEt}
              onTimeChange={setCurrentEt}
              mode={canvasData.mode}
              events={timelineEvents}
              playbackRate={playback.rate}
              loop={playback.loop}
              onPlaybackConfigChange={(c) => setPlayback((prev) => ({ ...prev, ...c }))}
            />
          </div>
        </div>

        {/* 最右栏：AI 助手边栏（CONTEXT.md 术语：助手边栏）。可折叠、可拖宽，
            agent loop 在后端，此处仅交互转发（ADR 0022/0023） */}
        <AssistantSidebar
          lang={lang}
          selection={assistantSelection}
          onArtifactProduced={handleAssistantArtifact}
          onOpenRecord={(recordId) => handleAssistantOpenRecord(recordId)}
          onApplyScenario={handleApplyScenario}
          onOpenSettings={() => setChartModalOpen(true)}
        />

        {/* 独立弹窗：轨道保持 */}
        <StationKeepingModal
          open={stationKeepingOpen}
          sourceRecord={selectedRecordDetail || selectedArtifact}
          onClose={() => setStationKeepingOpen(false)}
          onSuccess={refreshArtifacts}
        />

        {/* 独立弹窗：图表设置。双列栅格排布（滑块/开关/下拉短控件两列），
            弹窗更紧凑，避免单列下控件稀疏拉出大片空白。 */}
        {/* Standalone modal: chart settings. A two-column grid (short controls
            — sliders/switches/selects — share a row) keeps the modal compact,
            avoiding the sparse single-column look full of dead space. */}
        <Modal
          title={t("chart.title")}
          open={chartModalOpen}
          onCancel={() => setChartModalOpen(false)}
          footer={null}
          width={430}
        >
          <Form layout="vertical" size="small">
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item label={t("chart.font_size")}>
                  <Slider
                    min={8}
                    max={16}
                    value={fontSize}
                    onChange={handleChangeFontSize}
                    marks={{ 8: "8pt", 12: "12pt", 16: "16pt" }}
                  />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item label={t("chart.linewidth")}>
                  <Slider
                    min={0.2}
                    max={3.0}
                    step={0.1}
                    value={chart.orbitLinewidth}
                    onChange={(v) => setChart({ ...chart, orbitLinewidth: v })}
                  />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item label={t("chart.z_ratio")}>
                  <Slider
                    min={0.1}
                    max={2.0}
                    step={0.05}
                    value={chart.zRatio}
                    onChange={(v) => setChart({ ...chart, zRatio: v })}
                  />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item label={t("chart.grid_range")}>
                  <Slider
                    min={0.5}
                    max={3.0}
                    step={0.1}
                    value={chart.gridRange}
                    onChange={(v) => setChart({ ...chart, gridRange: v })}
                    marks={{ 0.5: "0.5", 1.3: "1.3", 3: "3" }}
                  />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item label={t("chart.axes")}>
                  <Switch
                    size="small"
                    checked={chart.axesVisible}
                    onChange={(v) => setChart({ ...chart, axesVisible: v })}
                  />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item label={t("chart.regions")}>
                  <Switch
                    size="small"
                    checked={chart.regionsVisible}
                    onChange={(v) => setChart({ ...chart, regionsVisible: v })}
                  />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item label={t("chart.background")}>
                  <Select
                    size="small"
                    value={chart.bgColor ?? "theme"}
                    style={{ width: "100%" }}
                    onChange={(v) => setChart({ ...chart, bgColor: v === "theme" ? null : v })}
                    options={[
                      { label: t("chart.bg.theme"), value: "theme" },
                      { label: t("chart.bg.white"), value: "#ffffff" },
                      { label: t("chart.bg.dark_gray"), value: "#121212" },
                      { label: t("chart.bg.black"), value: "#000000" },
                    ]}
                  />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item label={t("chart.ephemeris")}>
                  {ephStatus === null ? (
                    <Text type="secondary" style={{ fontSize: 12 }}>{t("chart.eph.checking")}</Text>
                  ) : ephStatus.usable ? (
                    <Text type="success" style={{ fontSize: 12 }}>
                      {t("chart.eph.ready").replace(
                        "{n}",
                        String(ephStatus.files.filter((f) => f.endsWith(".bsp")).length),
                      )}
                    </Text>
                  ) : (
                    <Text type="danger" style={{ fontSize: 12 }}>
                      {t("chart.eph.missing").replace(
                        "{missing}",
                        `${!ephStatus.ephemerisReady ? t("chart.eph.missing_eph") : ""}${!ephStatus.leapsecondReady ? t("chart.eph.missing_tls") : ""}`,
                      )}
                    </Text>
                  )}
                </Form.Item>
              </Col>
            </Row>

            {/* AI 助手分区：模型服务配置（BYOK，OpenAI 兼容协议）。key 只进
                后端 keyring，不回读（ADR 0022 决策 5 / 0023 决策 6） */}
            <Divider titlePlacement="start" style={{ margin: "12px 0 8px" }}>
              <Text strong style={{ fontSize: 13 }}>
                {t("assistant.settings.section_title")}
              </Text>
            </Divider>
            <AssistantSettingsForm />
          </Form>
        </Modal>
        {/* 独立弹窗：关于 tod */}
        <AboutModal
          open={aboutModalOpen}
          onClose={() => setAboutModalOpen(false)}
          onUpdateAvailable={(info) => {
            setUpdateInfo(info);
            setUpdateModalOpen(true);
          }}
        />

        {/* 独立弹窗：软件自动更新 */}
        <UpdateModal
          open={updateModalOpen}
          updateInfo={updateInfo}
          onClose={() => setUpdateModalOpen(false)}
        />
      </div>
    </ConfigProvider>
  );
}