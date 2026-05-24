# PRD: 简化 CI 测试矩阵与 Release 配置

## Problem Statement

当前项目的 CI 测试矩阵包含 6 个组合（Ubuntu/macOS/Windows × Python 3.11/3.13），但实际上：

- 项目没有 macOS 用户群体，macOS 构建是资源浪费
- Python 3.11 是旧版本，Python 3.13 是当前稳定版，更值得优先保障
- 过多组合增加 CI 运行时间和维护成本

## Solution

简化 CI 测试矩阵为 2 个组合（Ubuntu/Windows × Python 3.13），移除 macOS 和 Python 3.11 支持，同时更新 pyproject.toml 与 CI 保持一致。

## User Stories

1. 作为项目维护者，我希望 CI 只需要在 Ubuntu 和 Windows 两个操作系统上测试，以便聚焦资源
2. 作为项目维护者，我希望 CI 只测试 Python 3.13 版本，以便保证最新稳定版的兼容性
3. 作为项目贡献者，我希望 CI 运行更快，以便快速获得反馈
4. 作为项目维护者，我希望 pyproject.toml 中的 `requires-python` 与 CI 测试版本一致，以便用户不会在旧版本上浪费时间
5. 作为项目贡献者，我希望 CI 配置简洁易懂，以便理解测试覆盖范围
6. 作为项目维护者，我希望移除冗余的 type check 条件判断，以便代码更清晰

## Implementation Decisions

### 1. 简化 ci.yml 测试矩阵

修改 `.github/workflows/ci.yml` 中的矩阵配置：

**变更前**：
```yaml
matrix:
  os: [ubuntu-latest, macos-latest, windows-latest]
  python-version: ["3.11", "3.13"]
```

**变更后**：
```yaml
matrix:
  os: [ubuntu-latest, windows-latest]
  python-version: ["3.13"]
```

测试组合从 6 个减少到 2 个。

### 2. 移除冗余的 type check 条件

当前 `type check` 步骤有条件判断：
```yaml
if: matrix.python-version == '3.13'
```

由于矩阵只剩 3.13，此条件冗余，应移除以简化代码。

### 3. 更新 pyproject.toml

- 将 `requires-python` 从 `">=3.11"` 更新为 `">=3.13"`
- 从 classifiers 中移除 `"Programming Language :: Python :: 3.11"` 和 `"Programming Language :: Python :: 3.12"`

### 4. 检查 release.yml 一致性

确认 `.github/workflows/release.yml` 中已使用 Python 3.13 构建 Windows 版本（经确认已正确）。

## Testing Decisions

- 推送修改后，验证 CI 在 Ubuntu × Python 3.13 和 Windows × Python 3.13 两个组合上均通过
- 验证 pytest 测试正常运行
- 验证 pyright 类型检查正常执行（无 `if` 条件后）
- 创建测试 tag 验证 Release 流程正常工作

## Out of Scope

- 修改业务代码或轨道族脚本逻辑
- 添加新的平台（macOS、Linux 桌面）或 Python 版本
- 修改 release.yml 的打包流程（保持 Windows zip 不变）
- 修改 e2m2e 依赖或项目依赖
- 添加新的 CI 检查项（如 lint、coverage）

## Further Notes

- macOS 用户可自行从源码安装，CI 不再覆盖
- 将来如需扩展回多版本，矩阵配置易于恢复
- `requires-python` 更新为 `>=3.13` 后，pip 安装时会强制要求 3.13+
