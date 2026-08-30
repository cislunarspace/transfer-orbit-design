// 画布时间轴（时刻选择滑块组件）。时刻模式两级（ADR 0021 修订）：
// et = 全局绝对钟（UTC 显示），relative = 相对时刻（T+天），null = 禁用。
// 机动事件旗标（出发/到达脉冲）以芯片展示，点击跳到该时刻。
// Canvas timeline (the time-moment slider). Two-tier time mode (ADR 0021
// revision): et = global absolute clock (UTC label), relative = relative time
// (T+ days), null = disabled. Maneuver events (departure/arrival pulses) show
// as chips; clicking one jumps to that moment.

import { useState, useEffect, useRef } from "react";
import { Slider, Typography, Space, Button, Tooltip } from "antd";
import { PlayCircleOutlined, PauseCircleOutlined, FieldTimeOutlined } from "@ant-design/icons";
import { etToUtcLabel } from "./timeBasis";

const { Text } = Typography;

/** 时间轴机动事件：et 为该事件的全局时刻；dv 文案缺省时不显示量值 */
/** A timeline maneuver event: et is its global moment; the Δv text is optional. */
export interface TimelineEvent {
  et: number;
  label: string;
  dv?: string;
}

export interface TimelineBarProps {
  timeRange: [number, number] | null;
  currentEt: number | null;
  onTimeChange: (et: number) => void;
  /** 时刻模式：决定标签口径（UTC vs T+天）；缺省按相对时刻显示（旧行为） */
  /** Time mode deciding the label convention (UTC vs T+days); defaults to relative (legacy behavior). */
  mode?: "et" | "relative" | null;
  /** 机动事件旗标（et 模式下才有意义；越出量程的不显示） */
  /** Maneuver-event flags (meaningful in et mode; out-of-range ones hidden). */
  events?: TimelineEvent[];
}

export function TimelineBar({ timeRange, currentEt, onTimeChange, mode, events }: TimelineBarProps) {
  const [playing, setPlaying] = useState(false);
  const playTimerRef = useRef<number | null>(null);

  const disabled = !timeRange || timeRange[0] >= timeRange[1];
  const minEt = timeRange ? timeRange[0] : 0;
  const maxEt = timeRange ? timeRange[1] : 100;
  const val = currentEt !== null && currentEt >= minEt && currentEt <= maxEt ? currentEt : minEt;
  const isEt = mode === "et";

  const formatEt = (et: number) => {
    if (disabled) return "无星历时间";
    if (isEt) return `${etToUtcLabel(et)} UTC`;
    const deltaDays = (et - minEt) / 86400;
    return `T + ${deltaDays.toFixed(2)} 天 (ET: ${Math.round(et)})`;
  };

  const visibleEvents = (events ?? []).filter(
    (e) => Number.isFinite(e.et) && !disabled && e.et >= minEt && e.et <= maxEt
  );

  useEffect(() => {
    if (playing && !disabled) {
      playTimerRef.current = window.setInterval(() => {
        const step = (maxEt - minEt) / 200;
        let next = val + step;
        if (next > maxEt) next = minEt;
        onTimeChange(next);
      }, 50);
    } else {
      if (playTimerRef.current) clearInterval(playTimerRef.current);
    }
    return () => {
      if (playTimerRef.current) clearInterval(playTimerRef.current);
    };
  }, [playing, disabled, minEt, maxEt, val, onTimeChange]);

  return (
    <div
      style={{
        padding: "4px 12px",
        background: "rgba(20, 24, 30, 0.85)",
        borderRadius: 2,
        display: "flex",
        alignItems: "center",
        gap: 12,
      }}
    >
      <Button
        type="text"
        size="small"
        disabled={disabled}
        icon={playing ? <PauseCircleOutlined style={{ fontSize: 16 }} /> : <PlayCircleOutlined style={{ fontSize: 16 }} />}
        onClick={() => setPlaying(!playing)}
      />
      <Space orientation="horizontal" style={{ flex: 1 }} size={8}>
        <FieldTimeOutlined style={{ color: disabled ? "#595959" : "#0958d9" }} />
        <Slider
          style={{ flex: 1, margin: "6px 0" }}
          min={minEt}
          max={maxEt}
          step={(maxEt - minEt) / 1000}
          value={val}
          disabled={disabled}
          tooltip={{ formatter: (v) => formatEt(v || minEt) }}
          onChange={(v) => onTimeChange(v)}
        />
      </Space>
      {visibleEvents.length > 0 && (
        <Space orientation="horizontal" size={4}>
          {visibleEvents.map((e, i) => (
            <Tooltip key={`${e.label}-${i}`} title={e.dv ? `${e.label}：${e.dv}` : e.label}>
              <Button
                size="small"
                type="dashed"
                style={{ padding: "0 6px", fontSize: 11, lineHeight: "18px", height: 20 }}
                onClick={() => onTimeChange(e.et)}
              >
                {e.dv ? `${e.label} ${e.dv}` : e.label}
              </Button>
            </Tooltip>
          ))}
        </Space>
      )}
      <Text style={{ fontSize: 11, minWidth: 140, textAlign: "right", color: disabled ? "#595959" : "#bfbfbf" }}>
        {formatEt(val)}
      </Text>
    </div>
  );
}
