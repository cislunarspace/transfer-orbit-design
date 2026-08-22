import { useEffect, useState, useCallback } from "react";
import { OrbitCanvas, type CanvasApi } from "./OrbitCanvas";
import { loadHaloSeeds, propagate, librationPoint, type OrbitSeed } from "./cr3bp";
import { generateFamily, type FamilyResponse } from "./sidecarApi";
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

export default function App() {
  const [seeds, setSeeds] = useState<OrbitSeed[]>([]);
  const [selected] = useState<number[]>([0]);
  const [trajectories, setTrajectories] = useState<number[][][]>([]);
  const [mu, setMu] = useState(0.01215058560962404);
  const [api, setApi] = useState<CanvasApi | null>(null);
  const [family, setFamily] = useState<FamilyResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [artifacts, setArtifacts] = useState<ArtifactSummary[]>([]);
  const [params, setParams] = useState<Record<string, unknown>>(DEFAULT_PARAMS);
  const [progressMessage, setProgressMessage] = useState<string>("");

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
    loadHaloSeeds().then((all) => {
      setSeeds(all.filter((s) => s.orbitId.includes("_L1_")));
    });
    listArtifacts().then(setArtifacts);
  }, []);

  useEffect(() => {
    if (seeds.length === 0) return;
    setMu(seeds[0].mu);
    setTrajectories(
      selected
        .filter((i) => i < seeds.length)
        .map((i) => propagate(seeds[i].mu, seeds[i], 2000)),
    );
  }, [seeds, selected]);

  const onReady = useCallback((a: CanvasApi) => setApi(a), []);

  // 布局不变的轨迹变化不重置视图（视图保持语义，阶段 3 起生效）
  const [firstFit, setFirstFit] = useState(true);
  useEffect(() => {
    if (api && trajectories.length && firstFit) {
      api.fitView();
      setFirstFit(false);
    }
  }, [api, trajectories, firstFit]);

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
      setArtifacts(await listArtifacts());
    } catch (e) {
      setFamily({
        recordId: "",
        familyType: "",
        generatedMembers: 0,
        members: [],
        error: { code: "INVOKE", message: String(e) },
      });
    } finally {
      setBusy(false);
    }
  };

  // sidecar 族 → 画布点集（当前每成员初态单点，#525 后接整条轨迹）
  const familyPoints =
    family && !family.error
      ? family.members.map((m) => {
          const pts: number[][] = [];
          for (let i = 0; i < m.pointCount; i++) {
            pts.push([m.positions[i * 3], m.positions[i * 3 + 1], m.positions[i * 3 + 2]]);
          }
          return pts;
        })
      : [];
  const canvasTrajectories = [...trajectories, ...familyPoints];

  return (
    <div style={{ display: "flex", height: "100%" }}>
      <div style={{ width: 230, borderRight: "1px solid #333", overflowY: "auto", padding: 8 }}>
        <div style={{ fontWeight: 600, marginBottom: 8 }}>项目</div>
        <ProjectTree
          artifacts={artifacts}
          onSelect={(a) => a && setArtifacts((prev) => [...prev]) /* 选中高亮阶段 3 后续 */}
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
      </div>
      <div
        style={{
          position: "absolute",
          bottom: 8,
          left: 546,
          fontSize: 12,
          color: "#888",
        }}
      >
        {busy && progressMessage ? `${progressMessage}… ` : ""}
        {selected.length} 条 CSV 轨迹{familyPoints.length > 0 ? ` + ${familyPoints.length} 族成员` : ""}
      </div>
    </div>
  );
}
