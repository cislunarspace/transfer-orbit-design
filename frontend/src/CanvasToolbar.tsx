// 画布工具栏：归拢投影/中心选择与适配/导出动画/图表设置操作，停靠于画布上方
// （替代原先分居画布两角的悬浮层）
// Canvas toolbar: gathers projection/center selection and fit/export-animation/chart-settings actions,
// docked above the canvas (replacing the floating layers that used to sit in opposite corners).

import { Button, Radio, Tooltip } from "antd";
import {
  CompressOutlined,
  VideoCameraOutlined,
  SettingOutlined,
  SaveOutlined,
  FolderOpenOutlined,
} from "@ant-design/icons";
import type { ProjectionMode, CenterMode, FrameMode } from "./OrbitCanvas";
import type { ContentMode } from "./trajectoryParsing";

export interface CanvasToolbarProps {
  projection: ProjectionMode;
  center: CenterMode;
  /** 视图系（#428）：synodic 默认；inertial 下月心/L1/L2 居中禁用 */
  /** The view frame (#428): synodic by default; moon/L1/L2 centering disabled under inertial. */
  frame?: FrameMode;
  /** 绘制内容（eph-fig）：双段产物画哪段；all 双段同屏 */
  /** The content switch (eph-fig): which segment of a dual-segment product to draw; all shows both. */
  contentMode?: ContentMode;
  recording: boolean;
  onProjectionChange: (p: ProjectionMode) => void;
  onCenterChange: (c: CenterMode) => void;
  onFrameChange?: (f: FrameMode) => void;
  onContentModeChange?: (m: ContentMode) => void;
  onFitView: () => void;
  onExportAnimation: () => void;
  onOpenSettings: () => void;
  /** 情景保存/打开（#429）：固定层记录集 + 参考历元 + 播放配置 */
  /** Scenario save/open (#429): pinned-layer record set + reference epoch + playback config. */
  onSaveScenario?: () => void;
  onOpenScenario?: () => void;
}

export function CanvasToolbar({
  projection,
  center,
  frame,
  contentMode,
  recording,
  onProjectionChange,
  onCenterChange,
  onFrameChange,
  onContentModeChange,
  onFitView,
  onExportAnimation,
  onOpenSettings,
  onSaveScenario,
  onOpenScenario,
}: CanvasToolbarProps) {
  const inertial = frame === "inertial";
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        padding: "4px 8px",
        flexWrap: "wrap",
      }}
    >
      <Radio.Group
        size="small"
        value={projection}
        onChange={(e) => onProjectionChange(e.target.value as ProjectionMode)}
        buttonStyle="solid"
      >
        <Radio.Button value="3d">3D</Radio.Button>
        <Radio.Button value="xy">XY</Radio.Button>
        <Radio.Button value="xz">XZ</Radio.Button>
        <Radio.Button value="yz">YZ</Radio.Button>
      </Radio.Group>

      {/* 视图系切换（#428，ADR 0013：会合系 ⇄ 惯性 GCRS）：显示选择，
          不改任何数据与时刻语义 */}
      {/* The view-frame switch (#428, ADR 0013: synodic ⇄ inertial GCRS):
          a display choice that changes no data or time semantics. */}
      <Radio.Group
        size="small"
        value={frame ?? "synodic"}
        onChange={(e) => onFrameChange?.(e.target.value as FrameMode)}
        buttonStyle="solid"
      >
        <Radio.Button value="synodic">会合系</Radio.Button>
        <Radio.Button value="inertial">惯性 (GCRS)</Radio.Button>
      </Radio.Group>

      {/* 绘制内容切换（eph-fig）：双段并存的产物（CR3BP 参考段 + 星历段）
          画哪段；无段语义的产物（转移弧、预报、族成员）不受影响 */}
      {/* The content switch (eph-fig): which segment of a dual-segment
          product (CR3BP reference + ephemeris arc) to draw; products without
          segment semantics (transfer arcs, propagations, family members)
          are unaffected. */}
      <Radio.Group
        size="small"
        value={contentMode ?? "all"}
        onChange={(e) => onContentModeChange?.(e.target.value as ContentMode)}
        buttonStyle="solid"
      >
        <Radio.Button value="all">全部</Radio.Button>
        <Radio.Button value="cr3bp">CR3BP</Radio.Button>
        <Radio.Button value="ephemeris">星历</Radio.Button>
      </Radio.Group>

      <Radio.Group
        size="small"
        value={center}
        onChange={(e) => onCenterChange(e.target.value as CenterMode)}
        buttonStyle="solid"
      >
        <Radio.Button value="barycenter">质心</Radio.Button>
        <Radio.Button value="earth">地心</Radio.Button>
        <Tooltip title={inertial ? "月心是会合系概念，惯性视图下不可用" : ""}>
          <Radio.Button value="moon" disabled={inertial}>月心</Radio.Button>
        </Tooltip>
        <Tooltip title={inertial ? "L1/L2 是会合系概念，惯性视图下不可用" : ""}>
          <Radio.Button value="l1" disabled={inertial}>L1</Radio.Button>
        </Tooltip>
        <Tooltip title={inertial ? "L1/L2 是会合系概念，惯性视图下不可用" : ""}>
          <Radio.Button value="l2" disabled={inertial}>L2</Radio.Button>
        </Tooltip>
      </Radio.Group>

      {/* 叠加模式开关已由双层模型取代（结果层/固定层，钉住走项目树图钉） */}
      {/* The overlay-mode switch was superseded by the two-layer model (result/pinned layers; pinning lives in the project tree pushpin). */}

      <div style={{ flex: 1 }} />

      {onSaveScenario && (
        <Button
          size="small"
          icon={<SaveOutlined />}
          onClick={onSaveScenario}
          title="保存情景（固定层记录集 + 参考历元 + 播放配置）"
        />
      )}
      {onOpenScenario && (
        <Button
          size="small"
          icon={<FolderOpenOutlined />}
          onClick={onOpenScenario}
          title="打开情景：重建固定层并校准时间轴"
        />
      )}
      <Button
        size="small"
        icon={<CompressOutlined />}
        onClick={onFitView}
        title="按轨道包围盒自适应缩放 (适配)"
      >
        适配
      </Button>
      <Button
        size="small"
        icon={<VideoCameraOutlined />}
        loading={recording}
        onClick={onExportAnimation}
        title="录制自转动画并导出 WebM"
      >
        导出动画
      </Button>
      <Button
        size="small"
        icon={<SettingOutlined />}
        onClick={onOpenSettings}
        title="图表显示设置"
      />
    </div>
  );
}
