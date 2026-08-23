# 文档维护

本目录记录项目文档维护约定。项目使用 Sphinx 构建文档，并以中文源文档为源语言。

## 安装文档依赖

文档构建依赖位于 `docs` optional dependencies。首次维护文档前先同步依赖：

```bash
uv sync --extra docs
```

后续文档命令均通过 `uv run` 执行。

## 文档国际化范围

Sphinx 文档国际化使用标准 `gettext` / `sphinx-intl` 流程。当前基础设施会处理整棵 `docs/source/` 文档树，因此英文 `.po` 文件中可能出现 API `.rst` 壳文件的页面标题、toctree 文本等静态条目。

需要注意：`autodoc` 从 Python docstring 动态生成的 API 正文也可能被 Sphinx 提取到 `.po` 文件中，但当前工作只落地可维护的翻译基础设施，不承诺完成 API 正文英文翻译。英文 `.po` 初始条目可以保持空 `msgstr`；未翻译条目会回退显示中文原文。

## 更新 gettext 模板

从 Sphinx 源文档提取 gettext 模板：

```bash
uv run sphinx-build -b gettext docs/source docs/build/gettext
```

生成的 `.pot` 文件位于 `docs/build/gettext/`，属于构建产物，不提交到仓库。

## 更新英文 `.po`

根据最新 gettext 模板更新英文翻译文件：

```bash
uv run sphinx-intl update -l en -p docs/build/gettext -d docs/source/locale
```

英文 `.po` 文件位于 `docs/source/locale/en/LC_MESSAGES/`，需要提交到仓库。中文是源语言，不维护单独的 `zh` `.po`。

## 构建 HTML 文档

构建中文文档：

```bash
uv run sphinx-build -b html -D language=zh docs/source docs/build/html/zh
```

构建英文文档：

```bash
uv run sphinx-build -b html -D language=en docs/source docs/build/html/en
```

`docs/build/` 和 `.mo` 文件均为构建产物，不提交到仓库。