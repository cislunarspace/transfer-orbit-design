// 画布时间轴（时刻选择滑块组件）

import { useState, useEffect, useRef } from "react";
import { Slider, Typography, Space, Button } from "antd";
import { PlayCircleOutlined, PauseCircleOutlined, FieldTimeOutlined } from "@ant-design/icons";

const { Text } = Typography;

export interface TimelineBarProps {
  timeRange: [number, number] | null;
  currentEt: number | null;
  onTimeChange: (et: number) => void;
}

export function TimelineBar({ timeRange, currentEt, onTimeChange }: TimelineBarProps) {
  const [playing, setPlaying] = useState(false);
  const playTimerRef = useRef<number | null>(null);

  const disabled = !timeRange || timeRange[0] >= timeRange[1];
  const minEt = timeRange ? timeRange[0] : 0;
  const maxEt = timeRange ? timeRange[1] : 100;
  const val = currentEt !== null && currentEt >= minEt && currentEt <= maxEt ? currentEt : minEt;

  const formatEt = (et: number) => {
    if (disabled) return "无星历时间";
    const deltaDays = (et - minEt) / 86400;
    return `T + ${deltaDays.toFixed(2)} 天 (ET: ${Math.round(et)})`;
  };

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
      <Text style={{ fontSize: 11, minWidth: 140, textAlign: "right", color: disabled ? "#595959" : "#bfbfbf" }}>
        {formatEt(val)}
      </Text>
    </div>
  );
}
