//! sidecar 子进程管理：拉起 `e2m2e serve-stdio`、写出请求、解析事件流。
//!
//! 协议见 e2m2e ADR 0035（信封 JSON 行 + 二进制帧）。行/帧解析在
//! [`super::StreamParser`]；本模块只管进程与 IO 路由。

use std::sync::Arc;

use serde_json::{json, Value};
use tokio::io::{AsyncReadExt, AsyncWriteExt, BufWriter};
use tokio::process::{Child, ChildStdin, Command};
use tokio::sync::{mpsc, oneshot, Mutex};

use super::{FrameArray, ProtocolEvent, StreamParser};

/// 一个已完成任务的完整结果：最终信封 + 二进制帧。
#[derive(Debug, Clone)]
pub struct JobResult {
    pub status: String,
    pub data: Value,
    pub error: Option<Value>,
    pub frames: Vec<FrameArray>,
}

enum Cmd {
    Request {
        tool: String,
        arguments: Value,
        binary_dtype: Option<&'static str>,
        reply: oneshot::Sender<JobResult>,
    },
    Progress {
        tx: mpsc::UnboundedSender<Value>,
    },
}

/// sidecar 句柄。克隆便宜（内部全是 Arc/通道）；进程随最后一份句柄
/// drop 被 `kill_on_drop` 终止，需要优雅退出用 [`SidecarHandle::shutdown`]。
///
/// 一次只跑一个任务（与 GUI 交互形态一致）；并发需求出现时再加队列。
#[derive(Clone)]
pub struct SidecarHandle {
    tx: mpsc::UnboundedSender<Cmd>,
    child: Arc<Mutex<Option<Child>>>,
}

impl SidecarHandle {
    /// 拉起 sidecar 子进程（stderr 继承到终端，便于排障）。
    ///
    /// `command` 形如 `["uv", "run", "e2m2e", "serve-stdio"]`，解释器策略
    /// （开发期 uv / 分发期打包产物）由调用方决定，本模块不猜。`cwd`
    /// 是 uv 项目根（分发期打包产物可传 None）。
    pub fn spawn(command: &[&str], cwd: Option<&std::path::Path>) -> anyhow::Result<Self> {
        let mut cmd = Command::new(command[0]);
        cmd.args(&command[1..])
            .stdin(std::process::Stdio::piped())
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::inherit())
            .kill_on_drop(true);
        if let Some(dir) = cwd {
            cmd.current_dir(dir);
        }
        let mut child = cmd.spawn()?;
        let stdin = child.stdin.take().expect("piped stdin");
        let stdout = child.stdout.take().expect("piped stdout");

        let (tx, rx) = mpsc::unbounded_channel();
        let child = Arc::new(Mutex::new(Some(child)));
        let child2 = Arc::clone(&child);

        tokio::spawn(reader_loop(stdout, stdin, rx));
        tokio::spawn(reaper(child2));

        Ok(Self { tx, child })
    }

    /// 发起一个工具调用，等待最终信封。
    ///
    /// 单任务串行：已有任务在执行时立即拒绝（不排队、不覆盖——覆盖会丢
    /// 前一任务的回复且错误信息误导）。并发需求出现时再加队列。
    pub async fn request(
        &self,
        tool: &str,
        arguments: &serde_json::Value,
        binary_dtype: Option<&'static str>,
    ) -> anyhow::Result<JobResult> {
        let (reply_tx, reply_rx) = oneshot::channel();
        self.tx.send(Cmd::Request {
            tool: tool.to_string(),
            arguments: arguments.clone(),
            binary_dtype,
            reply: reply_tx,
        })?;
        reply_rx
            .await
            .map_err(|_| anyhow::anyhow!("sidecar 读循环已退出（子进程可能已崩溃）"))
    }

    /// 读循环是否仍在运行（探活：死句柄判定）。
    pub fn is_alive(&self) -> bool {
        !self.tx.is_closed()
    }

    /// 订阅进度行（可丢弃事件）。每次调用替换订阅者。
    pub fn subscribe_progress(&self, tx: mpsc::UnboundedSender<Value>) {
        let _ = self.tx.send(Cmd::Progress { tx });
    }

    /// 终止子进程。e2m2e 计算任务无落盘中间态，直接杀、重启无副作用。
    ///
    /// 与 reaper 竞争所有权：先到手者负责收尾（reaper 持锁 `wait()` 会死锁，
    /// 改为取走 Child 再等）。
    pub async fn shutdown(&self) -> anyhow::Result<()> {
        if let Some(mut child) = self.child.lock().await.take() {
            child.start_kill()?;
            let _ = child.wait().await;
        }
        Ok(())
    }
}

/// 读循环：stdout 事件路由 + stdin 请求写出（单任务串行，stdin 无并发写）。
async fn reader_loop(
    mut stdout: tokio::process::ChildStdout,
    stdin: ChildStdin,
    mut rx: mpsc::UnboundedReceiver<Cmd>,
) {
    let mut parser = StreamParser::new();
    let mut stdin = BufWriter::new(stdin);
    let mut pending: Option<oneshot::Sender<JobResult>> = None;
    let mut progress_tx: Option<mpsc::UnboundedSender<Value>> = None;
    let mut frames: Vec<FrameArray> = Vec::new();
    // 带 binary_frames 声明的信封行先到，帧后到：暂存信封，帧齐后交付
    let mut waiting: Option<Value> = None;

    let mut buf = Vec::with_capacity(64 * 1024);

    loop {
        tokio::select! {
            cmd = rx.recv() => {
                match cmd {
                    Some(Cmd::Request { tool, arguments, binary_dtype, reply }) => {
                        let mut req = json!({"tool": tool, "arguments": arguments});
                        if let Some(dt) = binary_dtype {
                            req["binary_dtype"] = json!(dt);
                        }
                        if write_line(&mut stdin, &req).await.is_err() {
                            let _ = reply.send(JobResult {
                                status: "error".into(),
                                data: Value::Null,
                                error: Some(json!({"code": "SIDECAR_IO", "message": "写请求失败（子进程可能已退出）"})),
                                frames: vec![],
                            });
                            break;
                        }
                        pending = Some(reply);
                        frames.clear();
                    }
                    Some(Cmd::Progress { tx }) => { progress_tx = Some(tx); }
                    None => break, // 所有句柄已 drop
                }
            }
            n = stdout.read_buf(&mut buf) => {
                match n {
                    Ok(0) | Err(_) => {
                        // EOF / IO 错误：子进程已死。若请求刚进来还没写出去（或
                        // 写出去了但等不到回复），唤醒等待者走自愈路径。
                        pending.take();
                        break;
                    }
                    Ok(_) => {
                        let events = match parser.push(&buf) {
                            Ok(ev) => ev,
                            Err(e) => {
                                // 坏帧：协议流不可恢复。唤醒等待者（SIDECAR_EXIT
                                // 错误码走 state 层自愈重建），终止读循环。
                                eprintln!("sidecar 协议错误，终止读循环：{e}");
                                break;
                            }
                        };
                        for ev in events {
                            match ev {
                                ProtocolEvent::Line(v) => {
                                    let status = v.get("status").and_then(Value::as_str);
                                    match status {
                                        Some("progress") => {
                                            if let Some(tx) = &progress_tx {
                                                let _ = tx.send(v);
                                            }
                                        }
                                        Some("ok") | Some("error") => {
                                            let n_frames = v.get("binary_frames").and_then(Value::as_u64);
                                            match n_frames {
                                                Some(n) if n > 0 => waiting = Some(v),
                                                _ => deliver(&mut pending, v, std::mem::take(&mut frames)),
                                            }
                                        }
                                        _ => {} // 未知状态行：忽略（前向兼容）
                                    }
                                }
                                ProtocolEvent::Frame(f) => {
                                    frames.push(f);
                                    if let Some(line) = &waiting {
                                        let want = line.get("binary_frames").and_then(Value::as_u64).unwrap_or(0) as usize;
                                        if frames.len() >= want {
                                            let line = waiting.take().expect("checked above");
                                            deliver(&mut pending, line, std::mem::take(&mut frames));
                                        }
                                    }
                                }
                            }
                        }
                        buf.clear();
                    }
                }
            }
        }
    }
    // 循环退出（子进程死/句柄尽）：唤醒仍在等待的任务
    if let Some(reply) = pending.take() {
        let _ = reply.send(JobResult {
            status: "error".into(),
            data: Value::Null,
            error: Some(json!({"code": "SIDECAR_EXIT", "message": "sidecar 子进程提前退出"})),
            frames: std::mem::take(&mut frames),
        });
    }
}

/// 把最终信封交付给等待者（若有）。
fn deliver(pending: &mut Option<oneshot::Sender<JobResult>>, v: Value, frames: Vec<FrameArray>) {
    if let Some(reply) = pending.take() {
        let _ = reply.send(JobResult {
            status: v.get("status").and_then(Value::as_str).unwrap_or("").to_string(),
            data: v.get("data").cloned().unwrap_or(Value::Null),
            error: v.get("error").cloned(),
            frames,
        });
    }
}

async fn write_line(stdin: &mut BufWriter<ChildStdin>, req: &Value) -> std::io::Result<()> {
    let mut text = serde_json::to_string(req)?;
    text.push('\n');
    stdin.write_all(text.as_bytes()).await?;
    stdin.flush().await
}

/// 子进程退出收割（避免僵尸）：取走 Child 所有权再等，不长期持锁。
async fn reaper(child: Arc<Mutex<Option<Child>>>) {
    // 注意：take 后立刻释放锁（guard 不能括进 wait 的块里，2021 版
    // if-let 临时值活到块尾，会把 shutdown 锁死）
    let taken = child.lock().await.take();
    if let Some(mut child) = taken {
        let _ = child.wait().await;
    }
}
