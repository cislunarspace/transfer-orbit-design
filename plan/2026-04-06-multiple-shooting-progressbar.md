# 优化 Multiple Shooting 进度条

## 目标
改进 e2m2e 中 `MultipleShooting.correct()` 的进度条显示，增加段级别进度、预估剩余时间和更丰富的残差收敛信息。

## 任务列表
- [x] 1. 分析当前 tqdm 进度条实现，设计改进方案
- [x] 2. 修改 `MultipleShooting.correct()` 添加段级别进度和预估时间
- [x] 3. 测试优化后的进度条效果

## 改进内容
1. **段级别进度**: 每个迭代内显示 "Seg X/n_seg" 传播进度
2. **预估剩余时间**: tqdm 原生 ETA 功能
3. **残差收敛信息**: 显示当前残差值及与上次的比值（如 "res=1.23e-4 ↓0.52" 表示下降52%）

## 修改点
文件: `C:\Users\ouyan\codes\e2m2e\e2m2e\algorithms\multiple_shooting.py`

### 进度条改进
- 主进度条: 显示 "iter X/max_iter" + 当前残差
- 段传播时: 在主进度条 postfix 中显示 "Seg X/n_seg" + segment 进度
- 残差下降指示: 用 ↓ 和百分比显示残差下降速率

## 技术方案
1. 在 propagation 阶段使用 `pbar.set_postfix()` 动态显示段进度
2. 利用 `tqdm` 的 `leave=True` 保持最终结果可见
3. 添加残差下降率计算和显示