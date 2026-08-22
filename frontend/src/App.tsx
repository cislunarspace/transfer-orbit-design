import { useEffect, useState, useCallback } from "react";
import { OrbitCanvas, type CanvasApi } from "./OrbitCanvas";
import { propagate, librationPoint } from "./cr3bp";
import { getArtifact, runTool, type FamilyResponse, type ToolResponse } from "./sidecarApi";
import { listArtifacts, removeArtifact, type ArtifactSummary } from "./projectApi";
import { ParamsPanel } from "./ParamsPanel";
import { ProjectTree } from "./ProjectTree";
import { TOOL_REGISTRY, toolEntry } from "./schema";
import { CatalogFilterBar } from "./CatalogFilterBar";
import { useTranslation } from "./i18n";
import { useChartSettings, DEFAULT_CHART_SETTINGS, type ChartSettings } from "./chartSettings";
import { CanvasRecorder, downloadBlob } from "./canvasRecorder";

const DEFAULT_PARAMS: Record<string, unknown> = {
  orbit_type: "HALO",
  libration_point: 1,
  max_amplitude_km: 5000,
  n_orbits: 10,
};

const EARTH_MOON_MU = 0.01215058560962404;

export default function App() {
  const { lang, setLang, t } = useTranslation();
  const [leftTab, setLeftTab] = useState<"project" | "catalog">("project");
  const [mu, setMu] = useState(EARTH_MOON_MU);
  const [api, setApi] = useState<CanvasApi | null>(null);
  const [family, setFamily] = useState<FamilyResponse | null>(null);
  const [toolResult, setToolResult] = useState<ToolResponse | null>(null);
  const [selectedTool, setSelectedTool] = useState(TOOL_REGISTRY[0].name);
  const [busy, setBusy] = useState(false);
  const [artifacts, setArtifacts] = useState<ArtifactSummary[]>([]);
  const [params, setParams] = useState<Record<string, unknown>>(DEFAULT_PARAMS);
  const [progressMessage, setProgressMessage] = useState<string>("");
  const [catalogPoints, setCatalogPoints] = useState<number[][][]>([]);
  const [chart, setChart] = useChartSettings();
  const [showSettings, setShowSettings] = useState(false);
  const [recording, setRecording] = useState(false);

  // 动画导出：录制期间自转 8 秒，产物 webm
  const onExportAnimation = async () => {
    if (!api) return;
    const el = api.canvasElement();
    if (!el || !CanvasRecorder.supported()) {
      setProgressMessage("此环境不支持录制");
      return;
    }
    setRecording(true);
    const rec = new CanvasRecorder();
    api.setAutoRotate(true);
    rec.start(el, 30);
    setTimeout(async () => {
      api.setAutoRotate(false);
      const result = await rec.stop();
      if (result) downloadBlob(result.blob, "orbit-animation.webm");
      setRecording(false);
    }, 8000);
  };

  // 执行状态：sidecar 进度事件（可丢弃行，最后一条即当前状态）
  useEffect(() => {
    let unlisten: (() => void) | undefined;
    import("@tauri-apps/api/event").then(({ listen }) => {
      listen<{ meta: { job_id: string; percent: number; message: string } }>(
        "sidecar-progress",
        (ev) => setProgressMessage(ev.payload.meta.message),
      ).then((u) => (unlisten = u));
    });
    return () => unlisten?.();
  }, []);

  useEffect(() => {
    listArtifacts().then(setArtifacts);
  }, []);

  const onReady = useCallback((a: CanvasApi) => setApi(a), []);

  // 首次数据到达时视图适配一次；此后保持（视图保持语义）

  const libration = [
    { label: "L1", x: librationPoint(mu, 1) },
    { label: "L2", x: librationPoint(mu, 2) },
  ];

  const onGenerate = async () => {
    setBusy(true);
    try {
      // None/null 字段剔除（e2m2e model_fields_set 语义：None 视为已设置）
      const cleaned = Object.fromEntries(
        Object.entries(params).filter(([, v]) => v !== null && v !== undefined && v !== ""),
      );
      const entry = toolEntry(selectedTool);
      const resp = await runTool(selectedTool, cleaned, entry.binaryDtype, entry.artifactType ? {
        artifactType: entry.artifactType, label: entry.title, orbitType: String(cleaned.orbit_type ?? ""),
      } : undefined);
      setToolResult(resp);
      if (selectedTool === "orbit_family_generation" && !resp.error) {
        const data = resp.data;
        const orbits = Array.isArray(data.orbits) ? data.orbits as Record<string, unknown>[] : [];
        const members = resp.frames.map((frame, i) => ({ states: frame.data, times: Array.isArray(orbits[i]?.times) ? orbits[i].times as number[] : [], period: typeof orbits[i]?.period === "number" ? orbits[i].period as number : null }));
        const next: FamilyResponse = { recordId: String(data.record_id ?? ""), familyType: String(data.family_type ?? ""), generatedMembers: Number(data.generated_members ?? members.length), mu: typeof data.mu === "number" ? data.mu : null, members, error: null };
        setFamily(next); if (next.mu) setMu(next.mu);
      }
      setArtifacts(await listArtifacts());
    } catch (e) {
      const error = { code: "INVOKE", message: String(e) };
      setToolResult({ data: {}, frames: [], error });
      setFamily({
        recordId: "",
        familyType: "",
        generatedMembers: 0,
        mu: null,
        members: [],
        error: { code: "INVOKE", message: String(e) },
      });
    } finally {
      setBusy(false);
    }
  };

  // sidecar 族 → 画布轨迹：period 在手则传播整条（e2m2e ≥5.8.5）
  const familyPoints =
    family && !family.error
      ? family.members
          .filter((m) => m.states.length >= 6 && m.period)
          .map((m) => {
            const [x, y, z, vx, vy, vz] = m.states.slice(0, 6);
            return propagate(
              family.mu ?? mu,
              {
                orbitId: "family-member",
                mu: family.mu ?? mu,
                period: m.period!,
                state: [x, y, z, vx, vy, vz],
              },
              800,
            );
          })
      : [];
  const genericPoints = toolResult && !toolResult.error && selectedTool !== "orbit_family_generation" ? (() => {
    const d = toolResult.data;
    const states = Array.isArray(d.states) ? d.states : Array.isArray(d.position_km) ? d.position_km : Array.isArray(d.trajectory) ? d.trajectory : [];
    const jsonPoints = Array.isArray(states) && states.length && Array.isArray(states[0]) ? [states.map((s) => [Number(s[0]), Number(s[1]), Number(s[2])])] : [];
    const framePoints = toolResult.frames.filter((frame) => frame.shape.length >= 2 && frame.shape[frame.shape.length - 1] >= 3).map((frame) => {
      const stride = frame.shape[frame.shape.length - 1];
      const points: number[][] = [];
      for (let i = 0; i + 2 < frame.data.length; i += stride) points.push([frame.data[i], frame.data[i + 1], frame.data[i + 2]]);
      return points;
    });
    return jsonPoints.length ? jsonPoints : framePoints;
  })() : [];
  const canvasTrajectories = [...familyPoints, ...genericPoints, ...catalogPoints];

  // 首次数据到达时视图适配一次；此后保持（视图保持语义）
  const [firstFit, setFirstFit] = useState(true);
  useEffect(() => {
    if (api && canvasTrajectories.length > 0 && firstFit) {
      api.fitView();
      setFirstFit(false);
    }
  }, [api, canvasTrajectories, firstFit]);

  return (
    <div style={{ display: "flex", height: "100%" }}>
      <div style={{ width: 230, borderRight: "1px solid #333", overflowY: "auto", padding: 8 }}>
        <div style={{ display: "flex", marginBottom: 8, gap: 8, alignItems: "center" }}>
          <button
            onClick={() => setLeftTab("project")}
            style={{ fontWeight: leftTab === "project" ? 600 : 400, flex: 1 }}
          >
            {t("project.title")}
          </button>
          <button
            onClick={() => setLeftTab("catalog")}
            style={{ fontWeight: leftTab === "catalog" ? 600 : 400, flex: 1 }}
          >
            {t("catalog.title")}
          </button>
          <select value={lang} onChange={(e) => setLang(e.target.value)} style={{ width: 44 }}>
            <option value="zh">中</option>
            <option value="en">EN</option>
          </select>
        </div>
        {leftTab === "catalog" && (
          <CatalogFilterBar
            onResults={(items) => setArtifacts(items)}
          />
        )}
        <ProjectTree
          artifacts={artifacts}
          onSelect={async (a) => {
            // 项目树选中 → catalog 拉取 → 画布（叠加）
            if (!a?.recordId) return;
            const data = await getArtifact(a.recordId);
            if (data.error) {
              setProgressMessage(`${data.error.code}: ${data.error.message}`);
              return;
            }
            setCatalogPoints(
              data.members.map((flat) => {
                const pts: number[][] = [];
                for (let i = 0; i * 3 + 2 < flat.length; i++) {
                  pts.push([flat[i * 3], flat[i * 3 + 1], flat[i * 3 + 2]]);
                }
                return pts;
              }),
            );
          }}
          onRemove={async (id) => {
            await removeArtifact(id);
            setArtifacts(await listArtifacts());
          }}
        />
      </div>
      <div style={{ width: 300, borderRight: "1px solid #333", overflowY: "auto", padding: 8 }}>
        <div style={{ fontWeight: 600, marginBottom: 8 }}>工具面板</div>
        <select value={selectedTool} onChange={(e) => { setSelectedTool(e.target.value); setParams(e.target.value === "orbit_family_generation" ? DEFAULT_PARAMS : {}); setFamily(null); setToolResult(null); }} style={{ width: "100%", marginBottom: 8 }}>
          {TOOL_REGISTRY.map((entry) => <option key={entry.name} value={entry.name}>{entry.title}</option>)}
        </select>
        <ParamsPanel schema={toolEntry(selectedTool).schema} params={params} onParamsChange={setParams} />
        <button onClick={onGenerate} disabled={busy} style={{ width: "100%", marginTop: 8 }}>
          {busy ? "执行中…" : "执行"}
        </button>
        {(family || toolResult) && (
          <div
            style={{
              fontSize: 12,
              marginTop: 8,
              color: toolResult?.error ? "#e57373" : "#81c784",
              wordBreak: "break-all",
            }}
          >
            {toolResult?.error
              ? `${toolResult.error.code}: ${toolResult.error.message}`
              : family ? `record ${family.recordId}（${family.generatedMembers} 成员）` : `工具 ${selectedTool} 执行成功`}
          </div>
        )}
      </div>
      <div style={{ flex: 1, position: "relative" }}>
        {canvasTrajectories.length > 0 && (
          <OrbitCanvas trajectories={canvasTrajectories} mu={mu} libration={libration} settings={chart} onReady={onReady} />
        )}
        <div style={{ position: "absolute", top: 8, right: 8, display: "flex", gap: 8 }}>
          <button onClick={() => api?.fitView()}>{t("action.fit")}</button>
          <button onClick={onExportAnimation} disabled={recording}>
            {recording ? `${t("action.recording")}…` : t("action.export_animation")}
          </button>
          <button onClick={() => setShowSettings((v) => !v)}>{t("action.chart_settings")}</button>
        </div>
        {showSettings && (
          <ChartSettingsPanel value={chart} onChange={setChart} onClose={() => setShowSettings(false)} />
        )}
        <div
          style={{
            position: "absolute",
            bottom: 8,
            left: 8,
            fontSize: 12,
            color: "#888",
          }}
        >
          {busy && progressMessage ? `${progressMessage}… ` : ""}
          {familyPoints.length > 0 && `${familyPoints.length} 族成员`}
          {catalogPoints.length > 0 && `${catalogPoints.length} 条库轨迹`}
        </div>
      </div>
    </div>
  );
}


function ChartSettingsPanel({
  value,
  onChange,
  onClose,
}: {
  value: ChartSettings;
  onChange: (s: ChartSettings) => void;
  onClose: () => void;
}) {
  const num = (k: keyof ChartSettings, label: string, step = 0.1) => (
    <label key={k} style={{ display: "block", marginBottom: 6, fontSize: 12 }}>
      <span style={{ display: "inline-block", minWidth: 110 }}>{label}</span>
      <input
        type="number"
        step={step}
        value={value[k] as number}
        onChange={(e) => onChange({ ...value, [k]: Number(e.target.value) })}
      />
    </label>
  );
  return (
    <div
      style={{
        position: "absolute",
        top: 44,
        right: 8,
        width: 240,
        background: "#1b2026",
        border: "1px solid #333",
        borderRadius: 6,
        padding: 12,
        zIndex: 10,
      }}
    >
      <div style={{ fontWeight: 600, marginBottom: 8 }}>图表设置</div>
      {num("orbitLinewidth", "轨道线宽")}
      {num("earthSize", "地球大小", 0.005)}
      {num("moonSize", "月球大小", 0.005)}
      {num("lpSize", "平动点大小", 0.001)}
      <label style={{ display: "block", marginBottom: 6, fontSize: 12 }}>
        <span style={{ display: "inline-block", minWidth: 110 }}>平动点颜色</span>
        <input
          type="color"
          value={value.lpColor}
          onChange={(e) => onChange({ ...value, lpColor: e.target.value })}
        />
      </label>
      {num("zRatio", "Z 轴比例", 0.05)}
      <button onClick={() => onChange(DEFAULT_CHART_SETTINGS)} style={{ marginRight: 8 }}>
        恢复默认
      </button>
      <button onClick={onClose}>关闭</button>
    </div>
  );
}
