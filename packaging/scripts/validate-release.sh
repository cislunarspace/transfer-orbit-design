#!/usr/bin/env bash
# 校验 Release tag 与各构建入口的版本一致，并要求 CHANGELOG 有对应版本小节。
# 依赖环境变量：GITHUB_REF_NAME（如 v4.8.0）。
set -euo pipefail

TAG="${GITHUB_REF_NAME:?缺少 GITHUB_REF_NAME}"
if [[ ! "${TAG}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*)?(\+[0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*)?$ ]]; then
    echo "Release tag 必须是 vMAJOR.MINOR.PATCH（可带预发布或构建后缀）：${TAG}" >&2
    exit 1
fi

VERSION="${TAG#v}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# 本仓四处版本：pyproject（Python 包与 tag 同步的唯一事实源）、Rust 壳、
# Tauri 配置（安装包产品版本）、前端。全部行首锚定 grep，不引入 node/cargo 依赖。
PYPROJECT_VERSION="$(sed -n 's/^version = "\(.*\)"$/\1/p' "${REPO_ROOT}/pyproject.toml" | head -1)"
CARGO_VERSION="$(sed -n 's/^version = "\(.*\)"$/\1/p' "${REPO_ROOT}/src-tauri/Cargo.toml" | head -1)"
CONFIG_VERSION="$(sed -n 's/.*"version": "\(.*\)",/\1/p' "${REPO_ROOT}/src-tauri/tauri.conf.json" | head -1)"
FRONTEND_VERSION="$(sed -n 's/.*"version": "\(.*\)",/\1/p' "${REPO_ROOT}/frontend/package.json" | head -1)"

for entry in "Pyproject=${PYPROJECT_VERSION}" "Cargo=${CARGO_VERSION}" "Tauri=${CONFIG_VERSION}" "Frontend=${FRONTEND_VERSION}"; do
    name="${entry%%=*}"
    version="${entry#*=}"
    if [[ "${version}" != "${VERSION}" ]]; then
        echo "${name} 版本 ${version} 与 tag ${TAG} 不一致" >&2
        exit 1
    fi
done

# CHANGELOG 小节形如 "## 4.7.0 (2026-08-31)"，版本号无 v 前缀。
if ! grep -Fq "## ${VERSION} " "${REPO_ROOT}/CHANGELOG.md"; then
    echo "CHANGELOG.md 缺少 ${VERSION} 版本小节" >&2
    exit 1
fi

echo "Release ${TAG} 版本校验通过（Pyproject/Cargo/Tauri/Frontend/CHANGELOG）"
