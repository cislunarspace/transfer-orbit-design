# Docusaurus 网站搭建设计

## 背景

将项目文档从纯 Markdown 文件转为可网页展示的 Docusaurus 静态站点，部署到 GitHub Pages。

## 技术方案

**工具链：**
- Docusaurus v3（静态网站生成）
- `@docusaurus/preset-classic`（经典主题：文档 + 导航 + 侧边栏）
- GitHub Actions（Push 到 master 时自动构建部署）
- TypeScript 配置文件

**目录结构：**
```
transfer-orbit-design/
├── docs/                          # Docusaurus 文档源
│   ├── docusaurus.config.ts      # 新增：Docusaurus 配置
│   ├── sidebars.ts                # 新增：侧边栏配置
│   ├── static/                   # 新增：静态资源
│   ├── index.md                   # 现有：文档首页
│   ├── guides/                   # 现有：使用指南（待更新）
│   ├── reference/                 # 现有：脚本参考（待更新）
│   ├── design/                    # 现有：设计文档（待重写）
│   ├── theory/                    # 现有：理论文档（待更新）
│   └── algorithms/                # 现有：算法文档（待更新）
├── package.json                    # 新增：Docusaurus 依赖
├── .github/
│   └── workflows/
│       └── deploy.yml            # 新增：GitHub Pages 部署
└── README.md                      # 更新：使用 uv sync
```

## 配置要点

### Docusaurus 配置（`docusaurus.config.ts`）

```typescript
const config: ConfigDoc = {
  title: "Transfer Orbit Design",
  tagline: "DRO to RO Two-Impulse Transfer",
  url: "https://ouyangjiahong.github.io",  // 需根据实际 GitHub 用户名调整
  baseUrl: "/transfer-orbit-design/",
  organizationName: "ouyangjiahong",
  projectName: "transfer-orbit-design",
  onBrokenLinks: "warn",
  onBrokenMarkdownLinks: "warn",
  docs: {
    sidebarPath: "./sidebars.ts",
  },
  themeConfig: {
    navbar: {
      title: "Transfer Orbit Design",
      items: [
        { type: "doc", docId: "index", position: "left", label: "Docs" },
        { href: "https://github.com/ouyangjiahong/transfer-orbit-design", label: "GitHub", position: "right" },
      ],
    },
    footer: {
      copyright: `© ${new Date().getFullYear()} Transfer Orbit Design`,
    },
  },
};
```

### GitHub Actions 部署（`.github/workflows/deploy.yml`）

- Trigger: push 到 `master` 分支
- 使用官方 `actions/deploy-pages@v4`
- 构建产物：`build/` 目录

### 侧边栏（`sidebars.ts`）

按现有目录结构生成侧边栏分组：
- `guides/` → "使用指南"
- `reference/` → "参考"
- `design/` → "设计文档"
- `theory/` → "理论基础"
- `algorithms/` → "算法说明"

## 待完成内容更新

文档上线前需要同步更新的文件：

| 文件 | 更新内容 |
|------|----------|
| `README.md` | `pip` → `uv sync`，脚本路径修正 |
| `docs/guides/development-guide.md` | `uv` 替代 `pip` |
| `docs/guides/system-overview.md` | `uv` 替代 `pip`，目录结构修正 |
| `docs/reference/scripts-reference.md` | 脚本路径修正（`generate/`、`plot/` 子目录） |
| `docs/index.md` | 快速开始命令更新 |
| `docs/design/*` | 内容过时，需重写（本次不包含，按需单独处理） |
| `docs/theory/*` | 内容可能过时，需审核更新 |
| `docs/algorithms/*` | 内容可能过时，需审核更新 |

> 注：`docs/design/`、`docs/theory/`、`docs/algorithms/` 将在后续按需单独重写，不属于本次站点搭建范围。

## 实施顺序

1. 初始化 Docusaurus 配置文件
2. 添加 `package.json` 依赖
3. 配置 GitHub Actions 部署流程
4. 本地验证 `docusaurus start` 可正常运行
5. 更新文档内容（README、guides、reference、index）
6. Push 并验证 GitHub Pages 部署成功
