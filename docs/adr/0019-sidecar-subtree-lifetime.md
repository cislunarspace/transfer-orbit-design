# sidecar 子树生命周期

关闭应用后，sidecar 进程（e2m2e）留在后台继续运行——包括正在计算的轨道族任务。我们决定在 Windows 上把 sidecar 子树划入 kill-on-close 的 Job Object，由内核保证其随应用进程死亡而终结。

## 背景与根因

sidecar 的 stdin EOF 只在空闲读循环时生效：e2m2e `run_loop` 逐行读请求，深陷计算（轨道族延拓可达分钟级）时不读 stdin，感知不到 EOF。而现有杀进程手段全都够不到真正干活的进程：

- `TerminateProcess` / `kill_on_drop` 只杀直接子进程。dev 期命令是 `uv run e2m2e serve-stdio`（uv.exe → python.exe），分发期 sidecar 是 PyInstaller onefile（bootloader 运行时再拉一个子进程）——两种形态下 python 都是孙进程；
- 显式 `shutdown()` 无调用时机能覆盖崩溃、被杀、updater `std::process::exit` 等退出路径。

## Considered Options

- **Windows Job Object（kill-on-close）**：spawn 后立刻把直接子进程划入新建 job；job 成员资格在进程创建时继承，孙进程自动入内。应用无论怎么退出（关窗口、崩溃、被杀、updater 重启），OS 关闭 job 句柄即由内核终结整棵树，不依赖任何用户态清理代码运行。只圈 sidecar 子树、不圈应用自身，updater 拉起的安装器等外部进程不受影响。
- **退出事件里显式 shutdown + 树杀（taskkill /T 或手工枚举）**：只覆盖优雅退出路径，崩溃与被杀路径仍残留；进程树枚举代码量更大且需维护。
- **依赖 stdin EOF（维持现状）**：仅空闲态有效，忙碌态残留分钟级；用户在计算中途关窗即复现。

## Consequences

- `SidecarHandle`（`src-tauri/src/sidecar/process.rs`）持有 job 句柄，句柄链随应用状态销毁或进程死亡关闭，内核即终结子树。回归测试 `busy_grandchild_tree_killed_when_handle_dropped` 固化了"drop 句柄 → 忙碌孙进程树被终结"。
- 竞态窗口可忽略：assign 在 spawn 返回后微秒级执行，解释器（uv / bootloader）启动到拉孙进程是毫秒级以上。
- job 创建或划入失败时降级为无兜底（警告日志），不阻断应用启动。
- Unix 无 Job Object 等价物：空闲态由 EOF 覆盖，忙碌态会跑完当前计算后经 EOF 退出，不产生永久残留；如未来 Linux 用户报告计算中关窗残留，再引入进程组（`setsid` + `killpg`）方案。
