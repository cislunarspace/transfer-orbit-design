"""Project 数据模型 — 原型。

验证点：Artifact 注册 + 按类型检索 + 元数据携带是否足够支撑 GUI 的数据管理需求。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class Artifact:
    """一次计算产出物。

    Attributes:
        artifact_id:  唯一标识。
        artifact_type:  类别（"orbit", "family", "transfer", "ephemeris"）。
        label:  用户可见名称。
        orbit_type:  轨道类型（DRO, Halo 等），可选。
        state_data:  状态矩阵 (n, 6)，用于可视化。
        times:  时间向量 (n,)。
        extra:  其他元数据（Jacobi 常数、初始状态、收敛信息等）。
    """

    artifact_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    artifact_type: str = "orbit"
    label: str = ""
    orbit_type: str = ""
    state_data: np.ndarray | None = None
    times: np.ndarray | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class Project:
    """工作项目：管理一次任务会话中的全部产出物。

    GUI 侧边栏从 Project 读取 artifact 列表；可视化面板从 Artifact 取数据绑画布。
    """

    def __init__(self, name: str = "未命名项目", path: Path | None = None):
        self.name = name
        self.path = path
        self._artifacts: list[Artifact] = []

    # -- 写 --

    def add_artifact(self, artifact: Artifact) -> None:
        self._artifacts.append(artifact)

    def remove_artifact(self, artifact_id: str) -> bool:
        before = len(self._artifacts)
        self._artifacts = [a for a in self._artifacts if a.artifact_id != artifact_id]
        return len(self._artifacts) < before

    # -- 读 --

    @property
    def artifacts(self) -> list[Artifact]:
        return list(self._artifacts)

    def get_by_id(self, artifact_id: str) -> Artifact | None:
        for a in self._artifacts:
            if a.artifact_id == artifact_id:
                return a
        return None

    def get_by_type(self, artifact_type: str) -> list[Artifact]:
        return [a for a in self._artifacts if a.artifact_type == artifact_type]

    def find_by_orbit_type(self, orbit_type: str) -> list[Artifact]:
        return [a for a in self._artifacts if a.orbit_type == orbit_type]
