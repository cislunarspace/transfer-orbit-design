//! sidecar 子进程管理：拉起 `e2m2e serve-stdio`、写出请求、解析事件流。
//!
//! 协议见 e2m2e ADR 0035（信封 JSON 行 + 二进制帧）。行/帧解析在
//! [`super::StreamParser`]；本模块只管进程与 IO 路由。
//!
//! 生命周期：Windows 上 spawn 后立刻把子进程划入 kill-on-close 的
//! Job Object（见 [`job`]），app 无论怎么退出（关窗口、崩溃、被杀、
//! updater 重启），内核都会终结整棵 sidecar 子树——这是唯一能覆盖
//! "孙进程 + 忙碌中" 的手段：e2m2e 的 stdin EOF 只在空闲读循环时生效，
//! 深陷计算时收不到；TerminateProcess 又只杀直接子进程（dev 期 uv 的
//! python、分发期 onefile bootloader 的子进程都是孙进程）。

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
/// Windows 上还持有 kill-on-close 的 Job Object 句柄（见 [`job`]）：句柄
/// 随本结构 drop（或 app 进程死亡时被 OS 关闭）即终结整棵子树。
///
/// 一次只跑一个任务（与 GUI 交互形态一致）；并发需求出现时再加队列。
#[derive(Clone)]
pub struct SidecarHandle {
    tx: mpsc::UnboundedSender<Cmd>,
    child: Arc<Mutex<Option<Child>>>,
    #[cfg(windows)]
    _job: Option<Arc<job::JobHandle>>,
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
        // Windows：第一时间把子进程划入 kill-on-close Job Object（本仓
        // ADR《sidecar 子树生命周期》；竞态说明见 job 模块注释）
        #[cfg(windows)]
        let job_handle = job::assign_tree_to_kill_on_close_job(&mut child);
        let stdin = child.stdin.take().expect("piped stdin");
        let stdout = child.stdout.take().expect("piped stdout");

        let (tx, rx) = mpsc::unbounded_channel();
        let child = Arc::new(Mutex::new(Some(child)));
        let child2 = Arc::clone(&child);

        tokio::spawn(reader_loop(stdout, stdin, rx));
        tokio::spawn(reaper(child2));

        Ok(Self {
            tx,
            child,
            #[cfg(windows)]
            _job: job_handle,
        })
    }

    /// 发起一个工具调用，等待最终信封。
    ///
    /// 单任务串行：已有任务在执行时立即拒绝（不排队、不覆盖，覆盖会丢
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

/// Windows Job Object：sidecar 子树的内核级生命周期兑底。
///
/// 为什么不用其它手段（本仓 ADR《sidecar 子树生命周期》）：
/// - stdin EOF：e2m2e 空闲时收到 EOF 自行退出，但深陷计算时不读
///   stdin，EOF 感知不到，计算跑完前（可达分钟级）进程一直残留；
/// - TerminateProcess / kill_on_drop：只杀直接子进程，够不到
///   dev 期 uv 的 python、分发期 onefile bootloader 的子进程；
/// - 退出事件里显式 shutdown：无调用时机能覆盖崩溃、被杀、
///   updater std::process::exit 等路径。
///
/// kill-on-close 的句柄由内核追踪：最后一份句柄关闭（SidecarHandle
/// 链 drop、或 app 进程死亡时 OS 统一关闭句柄）即终结 job 内全部
/// 进程，不依赖用户态清理代码运行。
///
/// 竞态窗口：job 成员资格在进程创建时继承。此处 assign 在 spawn 返回
/// 后立刻执行（微秒级），而解释器（uv / bootloader）需完成自身启动
/// 才会拉孙进程（毫秒级以上），孙进程必已入 job。只要圈住 spawn 后
/// 的直接子进程，整棵树就都在。
///
/// Unix 无此机制：空闲态由 EOF 覆盖；忙碌态会跑完当前计算后经 EOF
/// 退出，不产生永久残留。
#[cfg(windows)]
mod job {
    use std::sync::Arc;

    use windows_sys::Win32::Foundation::CloseHandle;
    use windows_sys::Win32::System::JobObjects::{
        AssignProcessToJobObject, CreateJobObjectW, JobObjectExtendedLimitInformation,
        SetInformationJobObject, JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
    };

    /// 持有即保活；drop（链尾）或进程死亡时内核终结 job 内进程树。
    ///
    /// 存 usize 而非裸指针：HANDLE 是 *mut c_void，未 Send 的指针会让
    /// Arc<JobHandle> 过不了 SidecarHandle 的克隆/跨任务移动。
    pub struct JobHandle(#[allow(dead_code)] usize);

    impl Drop for JobHandle {
        fn drop(&mut self) {
            // usize 转回 HANDLE；关闭句柄即触发 kill-on-close
            unsafe { CloseHandle(self.0 as _) };
        }
    }

    // 句柄只是内核对象 id（整数语义），跨线程传递安全
    unsafe impl Send for JobHandle {}
    unsafe impl Sync for JobHandle {}

    /// 把 child 划入新建的 kill-on-close job，返回随 [`super::SidecarHandle`]
    /// 存活的句柄。创建或划入失败时降级为 None（返回警告日志，不阻断
    /// 应用启动——泄漏风险回到修复前水平，而非不可用）。
    pub fn assign_tree_to_kill_on_close_job(child: &mut tokio::process::Child) -> Option<Arc<JobHandle>> {
        let job = unsafe { CreateJobObjectW(std::ptr::null(), std::ptr::null()) };
        if job.is_null() {
            eprintln!("sidecar job object 创建失败，进程残留风险回到无兑底状态");
            return None;
        }
        let mut info: JOBOBJECT_EXTENDED_LIMIT_INFORMATION =
            unsafe { std::mem::zeroed() };
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
        let ok = unsafe {
            SetInformationJobObject(
                job,
                JobObjectExtendedLimitInformation,
                &mut info as *mut _ as *mut core::ffi::c_void,
                std::mem::size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as u32,
            )
        };
        if ok == 0 {
            eprintln!("sidecar job object 设置 kill-on-close 失败，进程残留风险回到无兑底状态");
            unsafe { CloseHandle(job) };
            return None;
        }
        // child.raw_handle 是 CreateProcess 返回的原生句柄，权限足够
        let assigned = child
            .raw_handle()
            .map(|h| unsafe { AssignProcessToJobObject(job, h as _) } != 0)
            .unwrap_or(false);
        if !assigned {
            eprintln!("sidecar 子进程划入 job object 失败，进程残留风险回到无兑底状态");
            unsafe { CloseHandle(job) };
            return None;
        }
        Some(Arc::new(JobHandle(job as _)))
    }
}
#[cfg(all(test, windows))]
mod tests {
    use super::*;

    /// 回归测试：drop 句柄后，忙碌中的 sidecar 孙进程子树必须被内核终结
    /// （kill-on-close Job Object，见上方 job 模块说明与本仓 ADR 0019）。
    /// drop(handle) 模拟 app 退出。
    #[test]
    fn busy_grandchild_tree_killed_when_handle_dropped() {
        // uv 缺失（如无 uv 的 CI 环境）则跳过：本测试验证的是 Windows 机制
        if std::process::Command::new("uv").arg("--version").output().is_err() {
            eprintln!("uv 不可用，跳过");
            return;
        }
        // 孙进程忙 300 秒：若 job object 未生效，drop 后它必然还活着
        let busy = "import time\n# leak-regression-marker\nfor _ in range(30): time.sleep(1)\n";
        let repo_root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .unwrap();

        let rt = tokio::runtime::Runtime::new().unwrap();
        let handle = rt.block_on(async {
            let h =
                SidecarHandle::spawn(&["uv", "run", "python", "-c", busy], Some(repo_root)).unwrap();
            // 等 uv 拉起孙进程并进入忙循环
            tokio::time::sleep(std::time::Duration::from_secs(5)).await;
            h
        });
        drop(handle); // 模拟 app 退出：句柄链销毁 → job 关闭
        std::thread::sleep(std::time::Duration::from_secs(3)); // 给内核终结树的时间

        let out = std::process::Command::new("powershell")
            .args([
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'leak-regression-marker' -and $_.Name -in 'python.exe','uv.exe' }).Count",
            ])
            .output()
            .unwrap();
        let count: i32 = String::from_utf8_lossy(&out.stdout).trim().parse().unwrap_or(-1);
        assert_eq!(count, 0, "drop 句柄后忙碌 sidecar 子树仍存活（残留回归）");
    }
}
