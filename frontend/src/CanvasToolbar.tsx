// 画布工具栏：归拢投影/中心选择与适配/导出动画/图表设置操作，停靠于画布上方
// （替代原先分居画布两角的悬浮层）
// Canvas toolbar: gathers projection/center selection and fit/export-animation/chart-settings actions,
// docked above the canvas (replacing the floating layers that used to sit in opposite corners).

import { Button, Radio } from "antd";
import {
  CompressOutlined,
  VideoCameraOutlined,
  SettingOutlined,
} from "@ant-design/icons";
import type { ProjectionMode, CenterMode } from "./OrbitCanvas";

export interface CanvasToolbarProps {
  projection: ProjectionMode;
  center: CenterMode;
  recording: boolean;
  onProjectionChange: (p: ProjectionMode) => void;
  onCenterChange: (c: CenterMode) => void;
  onFitView: () => void;
  onExportAnimation: () => void;
  onOpenSettings: () => void;
}

export function CanvasToolbar({
  projection,
  center,
  recording,
  onProjectionChange,
  onCenterChange,
  onFitView,
  onExportAnimation,
  onOpenSettings,
}: CanvasToolbarProps) {
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

      <Radio.Group
        size="small"
        value={center}
        onChange={(e) => onCenterChange(e.target.value as CenterMode)}
        buttonStyle="solid"
      >
        <Radio.Button value="barycenter">质心</Radio.Button>
        <Radio.Button value="earth">地心</Radio.Button>
        <Radio.Button value="moon">月心</Radio.Button>
        <Radio.Button value="l1">L1</Radio.Button>
        <Radio.Button value="l2">L2</Radio.Button>
      </Radio.Group>

      <div style={{ flex: 1 }} />

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
