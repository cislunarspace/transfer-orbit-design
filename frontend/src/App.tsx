import { useEffect, useState, useCallback } from "react";
import { OrbitCanvas, type CanvasApi } from "./OrbitCanvas";
import { propagate, librationPoint } from "./cr3bp";
import { generateFamily, getArtifact, type FamilyResponse } from "./sidecarApi";
import { listArtifacts, removeArtifact, type ArtifactSummary } from "./projectApi";
import { ParamsPanel } from "./ParamsPanel";
import { ProjectTree } from "./ProjectTree";
import { familyGenerationSchema } from "./schema";

const DEFAULT_PARAMS: Record<string, unknown> = {
  orbit_type: "HALO",
  libration_point: 1,
  max_amplitude_km: 5000,
  n_orbits: 10,
};

const EARTH_MOON_MU = 0.01215058560962404;

export default function App() {
  const [mu, setMu] = useState(EARTH_MOON_MU);
  const [api, setApi] = useState<CanvasApi | null>(null);
  const [family, setFamily] = useState<FamilyResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [artifacts, setArtifacts] = useState<ArtifactSummary[]>([]);
  const [params, setParams] = useState<Record<string, unknown>>(DEFAULT_PARAMS);
  const [progressMessage, setProgressMessage] = useState<string>("");
  const [catalogPoints, setCatalogPoints] = useState<number[][][]>([]);

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
      const resp = await generateFamily(cleaned);
      setFamily(resp);
      if (resp.mu) setMu(resp.mu);
      setArtifacts(await listArtifacts());
    } catch (e) {
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
  const canvasTrajectories = [...familyPoints, ...catalogPoints];

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
        <div style={{ fontWeight: 600, marginBottom: 8 }}>项目</div>
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
        <div style={{ fontWeight: 600, marginBottom: 8 }}>轨道族生成</div>
        <ParamsPanel schema={familyGenerationSchema()} params={params} onParamsChange={setParams} />
        <button onClick={onGenerate} disabled={busy} style={{ width: "100%", marginTop: 8 }}>
          {busy ? "生成中…" : "生成"}
        </button>
        {family && (
          <div
            style={{
              fontSize: 12,
              marginTop: 8,
              color: family.error ? "#e57373" : "#81c784",
              wordBreak: "break-all",
            }}
          >
            {family.error
              ? `${family.error.code}: ${family.error.message}`
              : `record ${family.recordId}（${family.generatedMembers} 成员）`}
          </div>
        )}
      </div>
      <div style={{ flex: 1, position: "relative" }}>
        {canvasTrajectories.length > 0 && (
          <OrbitCanvas trajectories={canvasTrajectories} mu={mu} libration={libration} onReady={onReady} />
        )}
        <button
          onClick={() => api?.fitView()}
          style={{ position: "absolute", top: 8, right: 8 }}
        >
          适配
        </button>
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
