"""阶段 2 前置测试：sidecar 结果序列化开销量测。

对比 JSON 文本行协议与二进制（原始 f64 数组）在真实规模轨道族数据上的
编码耗时、解码耗时与体积。数据形态对齐画布渲染契约：每成员 (200, 6)。
"""
import json
import time

import numpy as np

MU = 0.01215058560962404
# halo L1 北族第一条种子，逐条微扰 x 模拟族成员差异
SEED = np.array([
    0.8760656451170601, 1.0491502986863478e-26, 0.191813535688546,
    -3.928226786817226e-14, 0.2305575388925067, 1.0601974505638561e-13,
])


def make_family(n_members: int, samples: int = 200) -> np.ndarray:
    """(n_members, samples, 6) 状态数组，数值特征与真实传播结果同量级。"""
    t = np.linspace(0, 2 * np.pi, samples)
    rng = np.random.default_rng(42)
    xs = 0.876 + rng.uniform(-0.01, 0.01, n_members)
    # 圆环扰动叠加正弦，量级与 halo 轨迹同阶；只求数值特征真实，不求轨道学精确
    out = np.empty((n_members, samples, 6))
    for i in range(n_members):
        out[i, :, 0] = xs[i] + 0.1 * np.sin(t)
        out[i, :, 1] = 0.1 * np.sin(2 * t) + 0.01 * np.cos(3 * t)
        out[i, :, 2] = 0.19 + 0.05 * np.sin(t + 0.3)
        out[i, :, 3:] = 0.2 * np.cos(t[:, None] * np.arange(1, 4))
    return out


def bench(n_members: int) -> None:
    data = make_family(n_members)
    n_floats = data.size

    # JSON 文本
    t0 = time.perf_counter()
    text = json.dumps({"members": data.tolist()})
    t_enc_json = time.perf_counter() - t0
    size_json = len(text.encode())

    # 二进制
    t0 = time.perf_counter()
    blob = data.tobytes()
    t_enc_bin = time.perf_counter() - t0

    print(f"{n_members:>6} 成员 ({n_floats/1e6:>6.1f}M 浮点):")
    print(f"  JSON  编码 {t_enc_json*1000:8.0f} ms  体积 {size_json/1e6:8.1f} MB")
    print(f"  二进制 编码 {t_enc_bin*1000:8.0f} ms  体积 {len(blob)/1e6:8.1f} MB")

    with open(f"/tmp/bench_{n_members}.json", "w") as f:
        f.write(text)
    with open(f"/tmp/bench_{n_members}.bin", "wb") as f:
        f.write(blob)


if __name__ == "__main__":
    for n in (100, 1000, 26882):
        bench(n)