//! Windows Job Object：子进程树的内核级生命周期兜底（sidecar 与 mcp-serve
//! 共用；本仓 ADR 0019《sidecar 子树生命周期》）。
//!
//! 为什么不用其它手段：
//! - stdin EOF：子进程空闲时收到 EOF 自行退出，但深陷计算时不读
//!   stdin，EOF 感知不到，计算跑完前（可达分钟级）进程一直残留；
//! - TerminateProcess / kill_on_drop：只杀直接子进程，够不到
//!   dev 期 uv 的 python、分发期 onefile bootloader 的子进程；
//! - 退出事件里显式 shutdown：无调用时机能覆盖崩溃、被杀、
//!   updater std::process::exit 等路径。
//!
//! kill-on-close 的句柄由内核追踪：最后一份句柄关闭（句柄链 drop、或
//! app 进程死亡时 OS 统一关闭句柄）即终结 job 内全部进程，不依赖
//! 用户态清理代码运行。
//!
//! 竞态窗口：job 成员资格在进程创建时继承。assign 在 spawn 返回后立刻
//! 执行（微秒级），而解释器（uv / bootloader）需完成自身启动才会拉孙
//! 进程（毫秒级以上），孙进程必已入 job。只要圈住 spawn 后的直接子
//! 进程，整棵树就都在。
//!
//! Unix 无此机制：空闲态由 EOF 覆盖；忙碌态会跑完当前计算后经 EOF
//! 退出，不产生永久残留。

#![cfg(windows)]

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
/// Arc<JobHandle> 过不了句柄结构的克隆/跨任务移动。
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

/// 把 child 划入新建的 kill-on-close job，返回的句柄随调用方句柄结构
/// 存活。创建或划入失败时降级为 None（警告日志，不阻断应用启动——
/// 泄漏风险回到修复前水平，而非不可用）。
pub fn assign_tree_to_kill_on_close_job(child: &mut tokio::process::Child) -> Option<Arc<JobHandle>> {
    let job = unsafe { CreateJobObjectW(std::ptr::null(), std::ptr::null()) };
    if job.is_null() {
        eprintln!("job object 创建失败，进程残留风险回到无兜底状态");
        return None;
    }
    let mut info: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = unsafe { std::mem::zeroed() };
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
        eprintln!("job object 设置 kill-on-close 失败，进程残留风险回到无兜底状态");
        unsafe { CloseHandle(job) };
        return None;
    }
    // child.raw_handle 是 CreateProcess 返回的原生句柄，权限足够
    let assigned = child
        .raw_handle()
        .map(|h| unsafe { AssignProcessToJobObject(job, h as _) } != 0)
        .unwrap_or(false);
    if !assigned {
        eprintln!("子进程划入 job object 失败，进程残留风险回到无兜底状态");
        unsafe { CloseHandle(job) };
        return None;
    }
    Some(Arc::new(JobHandle(job as _)))
}
