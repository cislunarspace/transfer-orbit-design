// 主应用入口：基于 Ant Design 6 构建的三栏现代化高密度桌面科学计算界面

import { useEffect, useState, useCallback } from "react";
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
  message,
} from "antd";
import {
  PlayCircleOutlined,
  InfoCircleOutlined,
  MoonOutlined,
  SunOutlined,
} from "@ant-design/icons";
import { themeBehavior, themeTokens } from "./theme";
import { CanvasToolbar } from "./CanvasToolbar";
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
import { validateToolParams } from "./paramOverlay";
import { useTranslation } from "./i18n";
import { useChartSettings } from "./chartSettings";
import { CanvasRecorder, downloadBlob } from "./canvasRecorder";
import { listArtifacts, removeArtifact, type ArtifactSummary } from "./projectApi";
import { runTool, getArtifact, ephemerisStatus, type EphemerisStatus } from "./sidecarApi";
import { librationPoint } from "./cr3bp";
import { familyMembersToTrajectoryData, framesToTrajectoryData, trajectoryTimeRange } from "./trajectoryParsing";
import { type CatalogRecord, catalogQuery } from "./catalogApi";

const { Text, Title } = Typography;
const EARTH_MOON_MU = 0.01215058560962404;

export default function App() {
  const { lang, setLang } = useTranslation();
  const [themeMode, setThemeMode] = useState<"dark" | "light">(() => {
    // 默认白底黑字（日间）；夜间模式经右上角按钮切换并持久化
    return (localStorage.getItem("tod-theme-mode") as "dark" | "light") || "light";
  });
  const [fontSize, setFontSize] = useState<number>(() => {
    return Number(localStorage.getItem("tod-font-size") || "12");
  });

  const [leftTab, setLeftTab] = useState<"project" | "catalog">("project");
  const [selectedTool, setSelectedTool] = useState<string>(TOOL_REGISTRY[0].name);
  const [toolParams, setToolParams] = useState<Record<string, unknown>>({});
  // 提交校验问题（字段名 → 原因），传给参数面板内联标红；改动参数即清
  const [paramIssues, setParamIssues] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<boolean>(false);

  const [artifacts, setArtifacts] = useState<ArtifactSummary[]>([]);
  const [selectedArtifact, setSelectedArtifact] = useState<ArtifactSummary | null>(null);
  const [selectedRecordDetail, setSelectedRecordDetail] = useState<CatalogRecord | null>(null);

  // 画布状态
  const [trajectories, setTrajectories] = useState<number[][][]>([]);
  const [trajectoryTimes, setTrajectoryTimes] = useState<number[][]>([]);
  const [timeRange, setTimeRange] = useState<[number, number] | null>(null);
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
  const [ephStatus, setEphStatus] = useState<EphemerisStatus | null>(null);

  // 启动时查一次星历配置状态（设置面板展示；数据随 git/安装包分发，
  // 正常情况永远就绪，缺失多为安装损坏或 kernels/ 被删）
  useEffect(() => {
    ephemerisStatus().then(setEphStatus).catch(() => setEphStatus(null));
  }, []);

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

  // 轨迹上画布的同时接通时间轴：写入时刻数组与全局范围，当前时刻置于起点
  const applyTrajectoryData = (data: { trajectories: number[][][]; times: number[][] }) => {
    setTrajectories(data.trajectories);
    setTrajectoryTimes(data.times);
    const range = trajectoryTimeRange(data.times);
    setTimeRange(range);
    setCurrentEt(range ? range[0] : null);
    setTimeout(() => api?.fitView(), 100);
  };

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
          const td = familyMembersToTrajectoryData(data.familyMembers, muVal);
          if (td.trajectories.length > 0) {
            applyTrajectoryData(td);
            return;
          }
        }
        if (data.members && data.members.length > 0) {
          // 裸点集无时刻信息：时间轴保持禁用
          setTrajectories(data.members as unknown as number[][][]);
          setTrajectoryTimes([]);
          setTimeRange(null);
          setCurrentEt(null);
          setTimeout(() => api?.fitView(), 100);
        }
      }
    } catch (e) {
      console.error("加载记录失败", e);
    }
  };

  // 执行通用工具（提交前防呆校验：必填/越界不过则不提交）
  const handleRunTool = async () => {
    const entry = toolEntry(selectedTool);
    const issues = validateToolParams(selectedTool, entry.schema, toolParams);
    if (issues.length > 0) {
      setParamIssues(Object.fromEntries(issues.map((i) => [i.field, i.reason])));
      message.error(issues.map((i) => `${i.label}(${i.field}): ${i.reason}`).join("；"));
      return;
    }

    setBusy(true);
    setProgressMsg("正在提交计算任务...");
    try {
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
        const td = framesToTrajectoryData(resp.frames, resp.data, EARTH_MOON_MU);
        if (td.trajectories.length > 0) {
          applyTrajectoryData(td);
        }
      } else if (resp.data) {
        const d = resp.data as any;
        const rawStates = d.states || d.position_km || d.trajectory;
        if (Array.isArray(rawStates) && rawStates.length > 0) {
          if (Array.isArray(rawStates[0])) {
            const pts = rawStates.map((s: number[]) => [Number(s[0]), Number(s[1]), Number(s[2])]);
            setTrajectories([pts]);
            setTrajectoryTimes([]);
            setTimeRange(null);
            setCurrentEt(null);
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
        ...themeBehavior,
        token: {
          fontSize: fontSize,
          ...themeTokens,
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
                ["project", "项目"],
                ["catalog", "轨道库"],
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
                title="切换语言"
              >
                {lang === "zh" ? "EN" : "中"}
              </Button>
              <Button
                type="text"
                size="small"
                icon={themeMode === "dark" ? <SunOutlined /> : <MoonOutlined />}
                onClick={handleToggleTheme}
                title="切换浅色/深色主题"
              />
              <Button
                type="text"
                size="small"
                icon={<InfoCircleOutlined />}
                onClick={() => setAboutModalOpen(true)}
                title="关于 tod"
              />
            </div>
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
              recording={recording}
              onProjectionChange={setProjection}
              onCenterChange={setCenter}
              onFitView={() => api?.fitView()}
              onExportAnimation={handleExportAnimation}
              onOpenSettings={() => setChartModalOpen(true)}
            />
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
              background={chart.bgColor ?? (themeMode === "dark" ? "#121212" : "#ffffff")}
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
            <Form.Item label="坐标轴与网格">
              <Switch
                size="small"
                checked={chart.axesVisible}
                onChange={(v) => setChart({ ...chart, axesVisible: v })}
              />
            </Form.Item>
            <Form.Item label="画布背景">
              <Select
                size="small"
                value={chart.bgColor ?? "theme"}
                style={{ width: 140 }}
                onChange={(v) => setChart({ ...chart, bgColor: v === "theme" ? null : v })}
                options={[
                  { label: "跟随界面主题", value: "theme" },
                  { label: "白色", value: "#ffffff" },
                  { label: "深灰", value: "#121212" },
                  { label: "黑色", value: "#000000" },
                ]}
              />
            </Form.Item>
            <Form.Item label="量程 (DU，网格半宽)">
              <Slider
                min={0.5}
                max={3.0}
                step={0.1}
                value={chart.gridRange}
                onChange={(v) => setChart({ ...chart, gridRange: v })}
                marks={{ 0.5: "0.5", 1.3: "1.3", 3: "3" }}
              />
            </Form.Item>
            <Form.Item label="星历内核（自动配置，随安装分发）">
              {ephStatus === null ? (
                <Text type="secondary" style={{ fontSize: 12 }}>检测中...</Text>
              ) : ephStatus.usable ? (
                <Text type="success" style={{ fontSize: 12 }}>
                  就绪（{ephStatus.files.filter((f) => f.endsWith(".bsp")).join("、")}）
                </Text>
              ) : (
                <Text type="danger" style={{ fontSize: 12 }}>
                  缺失：{!ephStatus.ephemerisReady && "行星历 .bsp "}
                  {!ephStatus.leapsecondReady && "闰秒 .tls "}
                  请重装或恢复 kernels/ 目录
                </Text>
              )}
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