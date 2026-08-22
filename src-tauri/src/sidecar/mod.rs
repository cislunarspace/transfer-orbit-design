//! e2m2e sidecar 客户端：帧/流解析（frames）与子进程管理（process）。
//!
//! 协议契约：e2m2e ADR 0035（信封 JSON 行 + 二进制帧）。

pub mod frames;
pub mod process;

pub use frames::{
    decode_frame, FrameArray, ProtocolError, ProtocolEvent, StreamParser, MAGIC,
};
pub use process::{JobResult, SidecarHandle};
