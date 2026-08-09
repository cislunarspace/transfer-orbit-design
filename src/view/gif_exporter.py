"""动画导出 -- 把单条星历 Artifact 按时间窗逐帧渲染合成 GIF。

不进画布实时播放，仅离线渲染。每帧按当前时刻范围构造新的 CanvasState：
- synodic 视图：position/state 取子集，地月/L 点固定（重复画）。
- inertial 视图：position_km 取子集；月球 SPICE 轨迹按同一 times_et 子集绘制
  （``viz_adapter.draw_moon_gcrs_trajectory`` 已支持子集）。

窗口模式：
- ``cumulative``（默认）：每帧画 [t0, ti]，轨迹逐帧累加。
- ``sliding``：每帧画 [ti-w, ti]，w 为滑动窗宽度（秒）。

合成器用 Pillow 手写逐帧 ``save(append_images=...)``，不依赖 ffmpeg。
Pillow 是 matplotlib 的既有传递依赖（image handling），加为直接依赖仅为
显式声明本模块的使用，不引入新外部代码。
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from src.view.canvas import OrbitCanvas

# 默认滑动窗宽度（秒）：与目标轨道周期的合理量级对齐（地月 DRO ~14 天），
# 用户可在导出对话框覆盖。该常量无物理严格性，仅作 UI 默认。
DEFAULT_SLIDING_WINDOW_SECONDS = 3.0 * 86400.0


def _export_times(
    times_et: np.ndarray,
    *,
    time_range: tuple[float, float] | None,
    n_frames: int,
) -> np.ndarray:
    """生成 n_frames 个采样时刻（ET 秒），单调递增。

    time_range=None 时取 times_et 的首末；否则用给定 [t0, t1]。n_frames<2 时
    强制为 2（GIF 至少 2 帧才有动画意义）。
    """
    times_et = np.asarray(times_et, dtype=float)
    if time_range is None:
        t0, t1 = float(times_et.min()), float(times_et.max())
    else:
        t0, t1 = float(time_range[0]), float(time_range[1])
    n = max(2, int(n_frames))
    return np.linspace(t0, t1, n)


def _frame_index_ranges(
    export_times: np.ndarray,
    times_et: np.ndarray,
    *,
    window_mode: str,
    sliding_window_seconds: float | None,
) -> list[np.ndarray]:
    """为每帧导出时刻 ti 计算源数据索引段（cumulative / sliding）。

    cumulative：[t0, ti]；sliding：[ti-w, ti]，w 由 sliding_window_seconds 给定
    （默认 DEFAULT_SLIDING_WINDOW_SECONDS）。

    返回 list[idx]，idx 为源数据 times_et 的整数索引数组。每段保证非空
    （落在采样间隙时取最近点）。
    """
    times_et = np.asarray(times_et, dtype=float)
    t0 = float(export_times[0])
    w = (
        sliding_window_seconds
        if sliding_window_seconds is not None
        else DEFAULT_SLIDING_WINDOW_SECONDS
    )
    ranges: list[np.ndarray] = []
    for ti in export_times:
        lo = ti - float(w) if window_mode == "sliding" else t0
        mask = (times_et >= lo) & (times_et <= float(ti))
        idx = np.nonzero(mask)[0]
        if len(idx) == 0:
            i = int(np.argmin(np.abs(times_et - float(ti))))
            idx = np.array([i])
        ranges.append(idx)
    return ranges


def _annotate_timestamp(canvas: OrbitCanvas, utc_label: str) -> None:
    """在当前帧 figure 右下角叠加 UTC 时间戳文本。

    用 figure-level 文本（transAxes 在 3D Axes 上不直接可用），render() 会
    clear 整个 figure，故下一帧自动清掉，无需手动移除。
    """
    canvas._fig.text(
        0.99,
        0.01,
        utc_label,
        ha="right",
        va="bottom",
        fontsize=9,
        bbox=dict(facecolor="white", alpha=0.7, edgecolor="none", pad=2),
    )


def export_animation(
    canvas: OrbitCanvas,
    artifact_data: dict,
    *,
    frame: str,
    time_range: tuple[float, float] | None,
    n_frames: int,
    window_mode: str,
    output_path: str | Path,
    sliding_window_seconds: float | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> Path:
    """把单条星历 Artifact 按时间窗逐帧渲染合成 GIF。

    Args:
        canvas: 已配置好 artifacts provider 的画布实例。渲染期间不修改其
            常驻状态（sync_state 临时切换，结束时恢复）。
        artifact_data: 单条 Artifact 的渲染数据，来自 main_window._artifact_for_id
            （#359 契约）。synodic 视图用 ``ephemeris_synodic``，inertial 视图用
            ``ephemeris_position_km``；二者都需要 ``ephemeris_times_et``。
            ``initial_guess_states`` 不参与动画（无物理时间轴）。
        frame: ``"synodic"`` 或 ``"inertial"``。
        time_range: (t0, t1) ET 秒，None 则用 times_et 首末。
        n_frames: 帧数（<2 强制为 2）。
        window_mode: ``"cumulative"`` 或 ``"sliding"``。
        output_path: GIF 输出路径。
        sliding_window_seconds: sliding 模式的窗口宽度；None 用默认。
        progress_callback: (i, n) 每帧回调（主线程状态栏更新用）。

    Returns:
        输出文件 Path。

    Raises:
        ValueError: frame 非法 / 数据缺失 / Pillow 不可用。
    """
    from PIL import Image

    from src.view.canvas import CanvasState

    if frame not in ("synodic", "inertial"):
        raise ValueError(f"frame 非法: {frame}")
    if window_mode not in ("cumulative", "sliding"):
        raise ValueError(f"window_mode 非法: {window_mode}")

    # 数据完备性校验（降级由调用方提示，本层直接报错以便测试覆盖）
    times_et = artifact_data.get("ephemeris_times_et")
    if times_et is None:
        raise ValueError("该 Artifact 无 ephemeris_times_et，无法按物理时间导出动画")
    times_et = np.asarray(times_et, dtype=float)
    if frame == "synodic" and artifact_data.get("ephemeris_synodic") is None:
        raise ValueError("该 Artifact 无 ephemeris_synodic 数据")
    if frame == "inertial" and artifact_data.get("ephemeris_position_km") is None:
        raise ValueError("该 Artifact 无 ephemeris_position_km 数据，惯性系不可导出")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    export_times = _export_times(times_et, time_range=time_range, n_frames=n_frames)
    index_ranges = _frame_index_ranges(
        export_times,
        times_et,
        window_mode=window_mode,
        sliding_window_seconds=sliding_window_seconds,
    )

    # 保存 canvas 当前 provider / state，结束后恢复
    saved_provider = canvas._artifacts_provider
    saved_state = canvas._state.copy()

    frames: list[Image.Image] = []
    artifact_id = "__gif_export__"
    n = len(export_times)
    try:
        for i, (ti, idx) in enumerate(zip(export_times, index_ranges, strict=True)):
            eph_syn = artifact_data.get("ephemeris_synodic")
            eph_pos = artifact_data.get("ephemeris_position_km")
            sub_syn = np.asarray(eph_syn)[idx] if eph_syn is not None else None
            sub_pos = np.asarray(eph_pos)[idx] if eph_pos is not None else None
            sub_times_et = times_et[idx]
            sub_artifact: dict[str, Any] = {
                # 动画只消费星历槽（初猜无物理时间轴）。canvas 在 synodic 帧下
                # 默认按 plot_content="overlay" 同时尝试画初猜 + 星历；这里把星历
                # 同时灌进两个槽，让初猜槽为 None、渲染只画星历。
                "initial_guess_states": None,
                "ephemeris_synodic": sub_syn,
                "ephemeris_position_km": sub_pos,
                "ephemeris_times_et": sub_times_et,
                "label": artifact_data.get("label", ""),
                "mu": artifact_data.get("mu"),
            }

            def _provider(_aid: str, _data: dict = sub_artifact) -> dict:
                return _data

            canvas.set_artifacts_provider(_provider)
            frame_state = CanvasState(
                projection=canvas._state.projection,
                visible_artifacts=[artifact_id],
                show_bodies=canvas._state.show_bodies,
                show_libration=canvas._state.show_libration,
                frame=frame,
                # 初猜槽为 None，"overlay" 与 "ephemeris" 等价（只画星历）
                plot_content=canvas._state.plot_content,
            )
            canvas.sync_state(frame_state, [artifact_id])
            canvas.render()
            _annotate_timestamp(canvas, _utc_label(float(ti)))
            canvas.draw_idle()
            canvas.flush_events() if hasattr(canvas, "flush_events") else None

            buf = np.asarray(canvas.buffer_rgba())
            frames.append(Image.fromarray(buf, "RGBA").convert("P"))

            if progress_callback is not None:
                progress_callback(i + 1, n)
    finally:
        canvas.set_artifacts_provider(saved_provider)
        canvas.sync_state(saved_state, list(saved_state.visible_artifacts))
        canvas.render()

    if len(frames) < 2:
        raise ValueError(f"帧数不足 2，无法合成 GIF（{len(frames)} 帧）")

    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=200,  # 每帧 200ms（5fps），GIF 视觉默认
        loop=0,  # 循环播放
        optimize=True,
        disposal=2,
    )
    return output_path


def _utc_label(et: float) -> str:
    """ET 秒 -> UTC 字符串（透传 viz_adapter.et_to_utc_label）。"""
    from src.engine.viz_adapter import et_to_utc_label

    return et_to_utc_label(et)
