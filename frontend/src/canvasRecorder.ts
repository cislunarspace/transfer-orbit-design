// 画布动画录制：captureStream + MediaRecorder 编 webm；webview 内原生编码，
// 不引额外依赖。自转动画由调用方驱动。

export interface RecordingResult {
  blob: Blob;
  seconds: number;
}

/** 录制 canvas 的 start/stop 控制器。 */
export class CanvasRecorder {
  private recorder: MediaRecorder | null = null;
  private chunks: Blob[] = [];
  private startedAt = 0;

  static supported(): boolean {
    return typeof MediaRecorder !== "undefined" &&
      typeof HTMLCanvasElement.prototype.captureStream === "function";
  }

  start(canvas: HTMLCanvasElement, fps = 30): void {
    this.chunks = [];
    const stream = canvas.captureStream(fps);
    const mime = ["video/webm;codecs=vp9", "video/webm"].find(
      (m) => MediaRecorder.isTypeSupported(m),
    );
    this.recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
    this.recorder.ondataavailable = (e) => {
      if (e.data.size > 0) this.chunks.push(e.data);
    };
    this.recorder.start(100);
    this.startedAt = performance.now();
  }

  async stop(): Promise<RecordingResult | null> {
    const recorder = this.recorder;
    if (!recorder) return null;
    const seconds = (performance.now() - this.startedAt) / 1000;
    await new Promise<void>((resolve) => {
      recorder.onstop = () => resolve();
      recorder.stop();
    });
    this.recorder = null;
    return { blob: new Blob(this.chunks, { type: "video/webm" }), seconds };
  }
}

/** 触发浏览器下载（Tauri webview 内走 download 事件）。 */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}