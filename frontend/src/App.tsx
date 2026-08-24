// 主应用入口：基于 Ant Design 5 构建的三栏现代化高密度桌面科学计算界面

import { useEffect, useState, useCallback } from "react";
import {
  ConfigProvider,
  theme as antdTheme,
  Button,
  Select,
  Space,
  Radio,
  Typography,
  Modal,
  Form,
  Slider,
  message,
} from "antd";
import {
  SettingOutlined,
  PlayCircleOutlined,
  CompressOutlined,
  VideoCameraOutlined,
  BulbOutlined,
  InfoCircleOutlined,
} from "@ant-design/icons";
import { OrbitCanvas, type CanvasApi, type ProjectionMode, type CenterMode } from "./OrbitCanvas";
import { TimelineBar } from "./TimelineBar";
import { ParamsPanel } from "./ParamsPanel";
import { ProjectTree } from "./ProjectTree";
import { RecordDetailPanel } from "./RecordDetailPanel";
import { StationKeepingModal } from "./StationKeepingModal";
import { CatalogFilterBar } from "./CatalogFilterBar";
import { UpdateModal } from "./UpdateModal";
import { AboutModal } from "./AboutModal";
import { checkForAppUpdates, type UpdateInfo } from "./updater";
import { TOOL_REGISTRY, toolEntry } from "./schema";
import { useTranslation } from "./i18n";
import { useChartSettings } from "./chartSettings";
import { CanvasRecorder, downloadBlob } from "./canvasRecorder";
import { listArtifacts, removeArtifact, type ArtifactSummary } from "./projectApi";
import { runTool, getArtifact } from "./sidecarApi";
import { librationPoint } from "./cr3bp";
import { familyMembersToTrajectories, framesToTrajectories } from "./trajectoryParsing";
import { type CatalogRecord, catalogQuery } from "./catalogApi";

const { Text, Title } = Typography;
const EARTH_MOON_MU = 0.01215058560962404;

export default function App() {
  const { lang, setLang } = useTranslation();
  const [themeMode, setThemeMode] = useState<"dark" | "light">(() => {
    return (localStorage.getItem("tod-theme-mode") as "dark" | "light") || "dark";
  });
  const [fontSize, setFontSize] = useState<number>(() => {
    return Number(localStorage.getItem("tod-font-size") || "12");
  });

  const [leftTab, setLeftTab] = useState<"project" | "catalog">("project");
  const [selectedTool, setSelectedTool] = useState<string>(TOOL_REGISTRY[0].name);
  const [toolParams, setToolParams] = useState<Record<string, unknown>>({});
  const [busy, setBusy] = useState<boolean>(false);

  const [artifacts, setArtifacts] = useState<ArtifactSummary[]>([]);
  const [selectedArtifact, setSelectedArtifact] = useState<ArtifactSummary | null>(null);
  const [selectedRecordDetail, setSelectedRecordDetail] = useState<CatalogRecord | null>(null);

  // 画布状态
  const [trajectories, setTrajectories] = useState<number[][][]>([]);
  const [trajectoryTimes] = useState<number[][]>([]);
  const [timeRange] = useState<[number, number] | null>(null);
  const [currentEt, setCurrentEt] = useState<number | null>(null);

  const [projection, setProjection] = useState<ProjectionMode>("3d");
  const [center, setCenter] = useState<CenterMode>("barycenter");

  const [api, setApi] = useState<CanvasApi | null>(null);
  const [chart, setChart] = useChartSettings();
  const [chartModalOpen, setChartModalOpen] = useState(false);
  const [stationKeepingOpen, setStationKeepingOpen] = useState(false);
  const [aboutModalOpen, setAboutModalOpen] = useState(false);
  const [updateModalOpen, setUpdateModalOpen] = useState(false);
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null);
  const [recording, setRecording] = useState(false);
  const [progressMsg, setProgressMsg] = useState<string>("");

  // 主题与字号持久化
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
        console.warn("Silent update check failed:", e);
      }
    }, 3000);
    return () => clearTimeout(timer);
  }, []);

  // 监听 sidecar 进度
  useEffect(() => {
    let unlisten: (() => void) | undefined;
    import("@tauri-apps/api/event").then(({ listen }) => {
      listen<{ meta: { message: string } }>("sidecar-progress", (ev) => {
        setProgressMsg(ev.payload.meta.message);
      }).then((u) => (unlisten = u));
    });
    return () => unlisten?.();
  }, []);

  const refreshArtifacts = useCallback(async () => {
    const list = await listArtifacts();
    setArtifacts(list);
  }, []);

  useEffect(() => {
    refreshArtifacts();
  }, [refreshArtifacts]);

  // 选中记录时，从 catalog 拉取详细信息与轨迹
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
        if (data.familyMembers && data.familyMembers.length > 0) {
          const muVal = data.mu ?? EARTH_MOON_MU;
          const trajectoriesList = familyMembersToTrajectories(data.familyMembers, muVal);
          if (trajectoriesList.length > 0) {
            setTrajectories(trajectoriesList);
            setTimeout(() => api?.fitView(), 100);
            return;
          }
        }
        if (data.members && data.members.length > 0) {
          setTrajectories(data.members as unknown as number[][][]);
          setTimeout(() => api?.fitView(), 100);
        }
      }
    } catch (e) {
      console.error("加载记录失败", e);
    }
  };

  // 执行通用工具
  const handleRunTool = async () => {
    setBusy(true);
    setProgressMsg("正在提交计算任务...");
    try {
      const entry = toolEntry(selectedTool);
      const cleaned = Object.fromEntries(
        Object.entries(toolParams).filter(([, v]) => v !== null && v !== undefined && v !== "")
      );

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
        message.error(`计算错误: ${JSON.stringify(resp.error)}`);
        return;
      }

      message.success("计算完成！");
      await refreshArtifacts();

      // 若有轨迹数据，装配到画布（解析逻辑见 trajectoryParsing）
      if (resp.frames && resp.frames.length > 0) {
        const trajectoriesList = framesToTrajectories(resp.frames, resp.data, EARTH_MOON_MU);
        if (trajectoriesList.length > 0) {
          setTrajectories(trajectoriesList);
          setTimeout(() => api?.fitView(), 100);
        }
      } else if (resp.data) {
        const d = resp.data as any;
        const rawStates = d.states || d.position_km || d.trajectory;
        if (Array.isArray(rawStates) && rawStates.length > 0) {
          if (Array.isArray(rawStates[0])) {
            const pts = rawStates.map((s: number[]) => [Number(s[0]), Number(s[1]), Number(s[2])]);
            setTrajectories([pts]);
            setTimeout(() => api?.fitView(), 100);
          }
        }
      }
    } catch (e) {
      message.error(`执行失败: ${String(e)}`);
    } finally {
      setBusy(false);
      setProgressMsg("");
    }
  };

  // 录制动画导出
  const handleExportAnimation = async () => {
    if (!api) return;
    const el = api.canvasElement();
    if (!el || !CanvasRecorder.supported()) {
      message.warning("当前环境不支持录制");
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
      message.success("动画导出完成！");
    }, 8000);
  };

  const libration = [
    { label: "L1", x: librationPoint(EARTH_MOON_MU, 1) },
    { label: "L2", x: librationPoint(EARTH_MOON_MU, 2) },
  ];

  return (
    <ConfigProvider
      theme={{
        algorithm: themeMode === "dark" ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
        token: {
          fontSize: fontSize,
          colorPrimary: "#1890ff",
        },
      }}
    >
      <div
        style={{
          display: "flex",
          width: "100vw",
          height: "100vh",
          overflow: "hidden",
          background: themeMode === "dark" ? "#141414" : "#f0f2f5",
          color: themeMode === "dark" ? "#fff" : "#000",
        }}
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
          {/* 页签与设置栏 */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <Radio.Group
              size="small"
              value={leftTab}
              onChange={(e) => setLeftTab(e.target.value)}
              buttonStyle="solid"
            >
              <Radio.Button value="project">项目</Radio.Button>
              <Radio.Button value="catalog">轨道库</Radio.Button>
            </Radio.Group>
            <Space orientation="horizontal" size={4}>
              <Button
                type="text"
                size="small"
                icon={<InfoCircleOutlined />}
                onClick={() => setAboutModalOpen(true)}
                title="关于 tod"
              />
              <Button
                type="text"
                size="small"
                icon={<BulbOutlined />}
                onClick={handleToggleTheme}
                title="切换浅色/深色主题"
              />
              <Select
                size="small"
                value={lang}
                style={{ width: 60 }}
                onChange={setLang}
                options={[
                  { label: "中", value: "zh" },
                  { label: "EN", value: "en" },
                ]}
              />
            </Space>
          </div>

          {/* 列表/过滤内容 */}
          <div style={{ flex: 1, overflowY: "auto", minHeight: 0 }}>
            {leftTab === "catalog" && (
              <CatalogFilterBar
                onResults={(arts) => setArtifacts(arts)}
                onSelectRecord={(rec) => setSelectedRecordDetail(rec)}
              />
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
            />
          </div>

          {/* 详情面板 */}
          <div style={{ maxHeight: 280, overflowY: "auto", borderTop: themeMode === "dark" ? "1px solid #303030" : "1px solid #e8e8e8" }}>
            <RecordDetailPanel
              record={selectedRecordDetail}
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
            动力学设计工具
          </Title>
          <Select
            size="small"
            style={{ width: "100%", marginBottom: 8 }}
            value={selectedTool}
            onChange={(val) => {
              setSelectedTool(val);
              setToolParams({});
            }}
            options={TOOL_REGISTRY.map((t) => ({ label: t.title, value: t.name }))}
          />

          <div style={{ flex: 1, overflowY: "auto", minHeight: 0 }}>
            <ParamsPanel
              toolName={selectedTool}
              schema={toolEntry(selectedTool).schema}
              values={toolParams}
              onChange={setToolParams}
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
              {busy ? "执行计算中..." : "执行"}
            </Button>
            {progressMsg && (
              <Text type="secondary" style={{ fontSize: 11, display: "block", marginTop: 4 }}>
                {progressMsg}
              </Text>
            )}
          </div>
        </div>

        {/* 右栏：主画布与时间轴 */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", position: "relative" }}>
          {/* 画布顶部工具栏 */}
          <div
            style={{
              position: "absolute",
              top: 10,
              left: 10,
              right: 10,
              display: "flex",
              justifyContent: "space-between",
              zIndex: 10,
              pointerEvents: "none",
            }}
          >
            {/* 投影与中心控制 */}
            <Space orientation="horizontal" size={6} style={{ pointerEvents: "auto" }}>
              <Radio.Group
                size="small"
                value={projection}
                onChange={(e) => setProjection(e.target.value)}
                buttonStyle="solid"
              >
                <Radio.Button value="3d">3D</Radio.Button>
                <Radio.Button value="xy">XY</Radio.Button>
                <Radio.Button value="xz">XZ</Radio.Button>
                <Radio.Button value="yz">YZ</Radio.Button>
              </Radio.Group>

              <Select
                size="small"
                value={center}
                style={{ width: 85 }}
                onChange={setCenter}
                options={[
                  { label: "质心居中", value: "barycenter" },
                  { label: "月心居中", value: "moon" },
                  { label: "L1 居中", value: "l1" },
                  { label: "L2 居中", value: "l2" },
                ]}
              />
            </Space>

            {/* 功能操作按钮组 */}
            <Space orientation="horizontal" size={6} style={{ pointerEvents: "auto" }}>
              <Button
                size="small"
                icon={<CompressOutlined />}
                onClick={() => api?.fitView()}
                title="按轨道包围盒自适应缩放 (适配)"
              >
                适配
              </Button>
              <Button
                size="small"
                icon={<VideoCameraOutlined />}
                loading={recording}
                onClick={handleExportAnimation}
                title="录制自转动画并导出 WebM"
              >
                导出动画
              </Button>
              <Button
                size="small"
                icon={<SettingOutlined />}
                onClick={() => setChartModalOpen(true)}
                title="图表显示设置"
              />
            </Space>
          </div>

          {/* Three.js Canvas */}
          <div style={{ flex: 1, minHeight: 0 }}>
            <OrbitCanvas
              trajectories={trajectories}
              times={trajectoryTimes}
              currentEt={currentEt}
              mu={EARTH_MOON_MU}
              libration={libration}
              projection={projection}
              center={center}
              settings={chart}
              onReady={(a) => setApi(a)}
            />
          </div>

          {/* 底部时间轴 */}
          <div style={{ padding: "4px 8px", background: themeMode === "dark" ? "#1a1a1a" : "#fff" }}>
            <TimelineBar
              timeRange={timeRange}
              currentEt={currentEt}
              onTimeChange={setCurrentEt}
            />
          </div>
        </div>

        {/* 独立弹窗：轨道保持 */}
        <StationKeepingModal
          open={stationKeepingOpen}
          sourceRecord={selectedRecordDetail || selectedArtifact}
          onClose={() => setStationKeepingOpen(false)}
          onSuccess={refreshArtifacts}
        />

        {/* 独立弹窗：图表设置 */}
        <Modal
          title="图表与界面偏好设置"
          open={chartModalOpen}
          onCancel={() => setChartModalOpen(false)}
          footer={null}
          width={450}
        >
          <Form layout="vertical" size="small">
            <Form.Item label="界面基准字号">
              <Slider
                min={8}
                max={16}
                value={fontSize}
                onChange={handleChangeFontSize}
                marks={{ 8: "8pt", 12: "12pt", 16: "16pt" }}
              />
            </Form.Item>
            <Form.Item label="轨道线宽">
              <Slider
                min={0.2}
                max={3.0}
                step={0.1}
                value={chart.orbitLinewidth}
                onChange={(v) => setChart({ ...chart, orbitLinewidth: v })}
              />
            </Form.Item>
            <Form.Item label="Z 轴缩放比例 (防压扁)">
              <Slider
                min={0.1}
                max={2.0}
                step={0.05}
                value={chart.zRatio}
                onChange={(v) => setChart({ ...chart, zRatio: v })}
              />
            </Form.Item>
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