# PRD: 修复 CI 与 Release 工作流

## Problem Statement

当前项目的持续集成（CI）与自动发布（Release）工作流存在多个结构性缺陷，导致自动化流程无法正常运行：

1. **PyInstaller spec 文件缺失**：`release.yml` 引用 `TransferOrbitDesign.spec` 用于构建 Windows 可执行文件，但项目中该文件完全不存在，导致 Windows 构建 **100% 失败**。
2. **pyproject.toml 包含本地路径依赖**：`[tool.uv.sources]` 和 `[tool.pyright.extraPaths]` 均指向 `../e2m2e`（本地文件系统路径），在 GitHub Actions 环境中不存在，导致 pip 安装或 pyright 类型检查可能失败。
3. **pip 约束文件无法覆盖依赖来源**：`constraints-ci.txt` 试图通过 `-c` 约束文件将 `e2m2e` 的来源从本地路径替换为 git URL，但 pip 的约束文件只能限制版本，**不能改变依赖来源**。因此 CI 实际会从 PyPI 安装 e2m2e（或失败），而非从 git 仓库安装。
4. **文档部署工作流与项目文档栈不匹配**：`deploy-docs.yml` 假设 docs 目录使用 Docusaurus（npm），但项目实际使用 Sphinx（Python），工作流完全不匹配，触发即失败。
5. **PyInstaller 无入口点定义**：`pyproject.toml` 未定义 `[project.scripts]`，PyInstaller 构建时无法自动识别主入口模块。

## Solution

对 CI/CD 相关配置文件进行全面修复和重构：

1. 修复 `pyproject.toml` 中的本地路径配置，确保 CI 友好
2. 修复 `ci.yml` 中的依赖安装步骤，确保 e2m2e 从 git 正确安装
3. 创建 `TransferOrbitDesign.spec`（PyInstaller 配置文件），使 Release 能成功构建 Windows 可执行文件
4. 重写 `deploy-docs.yml`，从 Docusaurus 改为 Sphinx 构建流程
5. 修复 `release.yml` 的依赖安装步骤，与 CI 保持一致
6. 清理无效的 `constraints-ci.txt`

## User Stories

1. 作为项目维护者，我希望 CI 在所有操作系统和 Python 版本上都能正确安装依赖并运行测试，以便及时捕获回归问题
2. 作为项目维护者，我希望 pyright 类型检查在 CI 中能通过，以便保证代码类型安全
3. 作为项目维护者，我希望推送 `v*` 标签时能自动生成 Release 并附带 Windows 可执行文件，以便用户无需安装 Python 环境即可运行软件
4. 作为项目维护者，我希望 docs 目录的变更能自动构建 Sphinx 文档并部署到 GitHub Pages，以便保持在线文档的最新状态
5. 作为贡献者，我希望提交 PR 时 CI 能正确安装 e2m2e（即使我没有本地路径），以便获得有效的 CI 反馈
6. 作为 GUI 用户，我希望下载 Windows exe 后能正常运行软件（包括界面语言切换和轨道族绘图功能），以便在无 Python 环境的情况下使用
7. 作为项目维护者，我希望 `pyproject.toml` 中不再包含 CI 不友好的本地绝对/相对路径，以便配置文件对任何环境都可用

## Implementation Decisions

### 1. 修复 pyproject.toml 中的 CI 不友好配置

- **删除 `[tool.uv.sources]`**：该节仅用于本地 `uv` 开发环境，在 CI 中无意义。本地 `uv` 用户可在个人配置中覆盖。
- **删除 `[tool.pyright]` 中的 `extraPaths`**：e2m2e 在 CI 中通过 pip 安装到 site-packages，pyright 应能自动解析。如有本地开发需要，使用 `.gitignore` 的 `pyrightconfig.json` 覆盖。
- **新增 `[project.scripts]`**：定义 `transfer-orbit-design = "tod.gui.main:main"`，为 PyInstaller 提供明确的入口点信息。

### 2. 修复 ci.yml 的依赖安装

- 在 Install dependencies 步骤中，将 e2m2e 的安装显式前置：
  ```
  pip install e2m2e@git+https://github.com/ouyangjiahong/e2m2e.git
  pip install -e ".[test]"
  ```
- 移除对 `constraints-ci.txt` 的依赖（该方式无法正确覆盖来源）。

### 3. 创建 TransferOrbitDesign.spec

- 使用 PyInstaller 的 `Analysis + PYZ + EXE + COLLECT` 模式（onedir），因为 `tod/gui/main.py` 的 frozen 子进程执行逻辑需要访问目录中的 `.py` 脚本文件。
- 配置 `datas` 包含 `tod/gui/i18n/` 下的 `.qm` 和 `.json` 翻译资源文件。
- 配置 `hiddenimports` 包含 e2m2e 及其子模块、PyQt6 相关子模块（如 `PyQt6.QtWebEngineCore`）。
- 设置 `console=False`（GUI 应用）。
- 注意 PyQt6-WebEngine 的二进制依赖（DLL、翻译文件、资源文件），可能需要额外的 `binaries` 配置或 `hook` 文件。

### 4. 重写 deploy-docs.yml

- 移除所有 Node/npm/Docusaurus 相关步骤（Setup Node、npm ci、npm run build）。
- 替换为 Python/Sphinx 构建流程：
  - Setup Python 3.13
  - Install e2m2e from git
  - Install project with `pip install -e ".[docs]"`
  - Build with `sphinx-build -b html docs/source docs/build/html`
- artifact 上传路径从 `docs/build` 改为 `docs/build/html`。

### 5. 修复 release.yml

- `release` job（生成 changelog + 创建 GitHub Release）逻辑保持不变。
- `build-windows` job 的依赖安装步骤与 `ci.yml` 一致：
  ```
  pip install e2m2e@git+https://github.com/ouyangjiahong/e2m2e.git
  pip install .
  pip install pyinstaller
  ```
- 使用 `pyinstaller TransferOrbitDesign.spec` 构建。

### 6. 清理 constraints-ci.txt

- 删除该文件或将其内容清空并标注弃用。该文件的设计假设（`-c` 约束文件可覆盖依赖来源）在 pip 中不成立。

## Testing Decisions

### 测试覆盖范围

由于本 PRD 的目标是修复 CI/CD 工作流（基础设施层面），而非修改业务代码，因此测试主要通过以下方式验证：

1. **手动触发 CI 验证**：
   - 推送代码到分支，确认 CI 在 Ubuntu/macOS/Windows × Python 3.11/3.13 全部通过
   - 确认 e2m2e 从 git 正确安装
   - 确认 pytest 测试通过
   - 确认 pyright 类型检查通过（无需 `extraPaths`）

2. **本地 PyInstaller 构建验证**：
   - 在本地 Windows 环境运行 `pyinstaller TransferOrbitDesign.spec`
   - 确认 `dist/TransferOrbitDesign/` 目录生成
   - 运行生成的 exe，确认 GUI 能正常启动
   - 确认界面语言切换功能正常
   - 确认轨道族绘图功能正常（验证 frozen 子进程执行逻辑）

3. **本地 Sphinx 文档构建验证**：
   - 运行 `sphinx-build -b html docs/source docs/build/html`
   - 确认 HTML 输出无致命错误
   - 确认 autodoc 能正确解析 e2m2e 相关模块

4. **Release 流程验证**：
   - 推送测试标签（如 `v0.1.0-test`），确认 Release 自动创建
   - 确认 Windows zip 附件成功上传
   - 下载 zip 并在干净的 Windows 环境中测试运行

### 现有测试参考

- `tests/` 目录下的 pytest 测试套件（CI 已通过）
- `docs/source/conf.py` 中的 Sphinx autodoc 配置

## Out of Scope

- 修改业务代码或轨道族脚本逻辑
- 新增功能或 GUI 改进
- 修改 e2m2e 仓库本身
- 添加 macOS 或 Linux 的可执行文件构建
- 自动化 PyInstaller spec 文件的生成（本次为手动配置）
- 为 CI 添加 Docker 构建或缓存优化
- 修改 pyproject.toml 中的项目版本号（Release 时通过 tag 管理）

## Further Notes

- **e2m2e 仓库**：`github.com/ouyangjiahong/e2m2e` 是公开仓库，CI runner 无需额外认证即可通过 https URL 克隆。如果将来改为私有仓库，需要在 CI 中配置 `GITHUB_TOKEN` 或 SSH key。
- **PyQt6-WebEngine 打包**：Qt WebEngine 有大量二进制依赖（DLL、翻译文件、资源），PyInstaller 的自动分析通常能捕获大部分，但可能需要手动验证 `PyQt6/Qt6/resources/` 和 `PyQt6/Qt6/translations/` 目录是否被打包。
- **frozen 子进程执行**：`tod/gui/main.py` 实现了 `sys.frozen` 模式下的 `.py` 脚本子进程执行，需要确保打包后的目录结构中 `tod/` 下的脚本文件可被访问。onedir 模式（`COLLECT`）比 onefile 模式更适合此场景。
- **Sphinx 文档路径**：当前 `docs/source/conf.py` 配置下，`sphinx-build` 默认输出到 `docs/build/html`。`deploy-docs.yml` 中的 artifact 路径需与此匹配。
- **GUI 翻译资源**：PyInstaller 打包时必须包含 `tod/gui/i18n/*.qm` 和 `tod/gui/i18n/*.json`，否则切换界面语言时翻译文件加载失败。
