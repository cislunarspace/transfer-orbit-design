//! 阶段 2 前置测试：sidecar 结果解码开销量测（与 tools/bench_serialization.py 配对）。
//! 运行：cargo run --release --example bench_decode -- /tmp/bench_1000

use std::fs;
use std::time::Instant;

fn main() {
    let prefix = std::env::args().nth(1).expect("用法: bench_decode <前缀，如 /tmp/bench_1000>");

    let json_path = format!("{prefix}.json");
    let bin_path = format!("{prefix}.bin");

    let text = fs::read_to_string(&json_path).expect("读取 JSON 失败");
    let t0 = Instant::now();
    let v: serde_json::Value = serde_json::from_str(&text).expect("JSON 解析失败");
    let t_json = t0.elapsed();

    let blob = fs::read(&bin_path).expect("读取二进制失败");
    let t0 = Instant::now();
    let floats = {
        let bytes = blob.as_slice();
        let n = bytes.len() / 8;
        let mut out = Vec::with_capacity(n);
        for chunk in bytes.chunks_exact(8) {
            out.push(f64::from_le_bytes(chunk.try_into().unwrap()));
        }
        out
    };
    let t_bin = t0.elapsed();

    let json_floats = v["members"].as_array().map(|a| {
        a.iter().map(|m| m.as_array().map(|x| x.len()).unwrap_or(0)).sum::<usize>()
    }).unwrap_or(0);
    println!(
        "{}: JSON 解码 {:>7.0} ms（{} 层点）  二进制解码 {:>5.0} ms（{} 浮点）",
        prefix.rsplit('/').next().unwrap(),
        t_json.as_secs_f64() * 1000.0,
        json_floats,
        t_bin.as_secs_f64() * 1000.0,
        floats.len(),
    );
}
