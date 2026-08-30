// 画布时间轴（时刻选择滑块组件）。时刻模式两级（ADR 0021 修订）：
// et = 全局绝对钟（UTC 显示），relative = 相对时刻（T+天），null = 禁用。
// 机动事件旗标（出发/到达脉冲）以芯片展示，点击跳到该时刻。
// 播放配置（#429 情景）：rate = 物理秒/真实秒（档位 1时/1天/1周每秒），
// loop = 循环开关；配置归 App 持有（情景保存/打开的素材），本组件只
// 上报变更。
// Canvas timeline (the time-moment slider). Two-tier time mode (ADR 0021
// revision): et = global absolute clock (UTC label), relative = relative time
// (T+ days), null = disabled. Maneuver events (departure/arrival pulses) show
// as chips; clicking one jumps to that moment.
// Playback config (#429 scenarios): rate = physical seconds per wall second
// (steps of 1 hour / 1 day / 1 week per second), loop = the looping switch;
// App owns the config (the material scenario save/open persists) — this
// component only reports changes.

import { useState, useEffect, useRef } from "react";
import { Slider, Typography, Space, Button, Tooltip, Select } from "antd";
import { PlayCircleOutlined, PauseCircleOutlined, FieldTimeOutlined, RetweetOutlined } from "@ant-design/icons";
import { etToUtcLabel } from "./timeBasis";

const { Text } = Typography;

/** 播放速率档位（物理秒/真实秒） */
/** Playback rate steps (physical seconds per wall second). */
const RATE_OPTIONS = [
  { label: "1时/秒", value: 3600 },
  { label: "1天/秒", value: 86400 },
  { label: "1周/秒", value: 604800 },
];

/** 播放 tick 周期（毫秒）：步长 = rate × tick / 1000 */
/** The playback tick period (ms): step = rate × tick / 1000. */
const PLAY_TICK_MS = 50;

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
  /** 播放速率（物理秒/真实秒，#429 情景配置）；缺省 86400（1天/秒） */
  /** The playback rate (physical seconds per wall second, the #429 scenario
   *  config); defaults to 86400 (one day per second). */
  playbackRate?: number;
  /** 循环播放开关（#429 情景配置）；缺省开（既有行为） */
  /** The looping switch (#429 scenario config); defaults to on (legacy behavior). */
  loop?: boolean;
  /** 播放配置变更上报（App 持有配置，情景保存时读取） */
  /** Reports playback-config changes (App owns the config; scenario save reads it). */
  onPlaybackConfigChange?: (config: { rate: number; loop: boolean }) => void;
}

export function TimelineBar({
  timeRange,
  currentEt,
  onTimeChange,
  mode,
  events,
  playbackRate,
  loop,
  onPlaybackConfigChange,
}: TimelineBarProps) {
  const [playing, setPlaying] = useState(false);
  const playTimerRef = useRef<number | null>(null);

  const rate = playbackRate ?? 86400;
  const doLoop = loop ?? true;
  const setConfig = (patch: { rate?: number; loop?: boolean }) => {
    onPlaybackConfigChange?.({ rate: patch.rate ?? rate, loop: patch.loop ?? doLoop });
  };

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
        // 步长 = 速率 × tick：速率是物理秒/真实秒，与量程解耦（#429）
        // Step = rate × tick: the rate is physical seconds per wall second,
        // decoupled from the range (#429).
        const step = (rate * PLAY_TICK_MS) / 1000;
        let next = val + step;
        if (next > maxEt) {
          if (!doLoop) {
            onTimeChange(maxEt);
            setPlaying(false);
            return;
          }
          next = minEt;
        }
        onTimeChange(next);
      }, PLAY_TICK_MS);
    } else {
      if (playTimerRef.current) clearInterval(playTimerRef.current);
    }
    return () => {
      if (playTimerRef.current) clearInterval(playTimerRef.current);
    };
  }, [playing, disabled, minEt, maxEt, val, onTimeChange, rate, doLoop]);

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
        title={playing ? "暂停" : "播放"}
        disabled={disabled}
        icon={playing ? <PauseCircleOutlined style={{ fontSize: 16 }} /> : <PlayCircleOutlined style={{ fontSize: 16 }} />}
        onClick={() => setPlaying(!playing)}
      />
      {/* 播放配置（#429 情景素材）：速率档位 + 循环开关 */}
      {/* Playback config (#429 scenario material): rate steps + looping switch. */}
      <Select
        size="small"
        variant="borderless"
        value={RATE_OPTIONS.some((o) => o.value === rate) ? rate : 86400}
        options={RATE_OPTIONS}
        disabled={disabled}
        onChange={(v) => setConfig({ rate: v })}
        style={{ width: 92 }}
        title="播放速率"
      />
      <Button
        size="small"
        disabled={disabled}
        icon={
          <RetweetOutlined
            style={{ fontSize: 14, color: doLoop ? undefined : "#595959" }}
          />
        }
        onClick={() => setConfig({ loop: !doLoop })}
        title={doLoop ? "循环播放（点击关闭）" : "单程播放（点击开启循环）"}
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
