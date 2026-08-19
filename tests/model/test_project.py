from __future__ import annotations

import pytest

from src.model.artifact import Artifact
from src.model.project import Project


@pytest.fixture
def project() -> Project:
    return Project("test-project")


@pytest.fixture
def orbit_artifact() -> Artifact:
    return Artifact(
        artifact_id="aaaa1111",
        artifact_type="orbit",
        label="DRO A",
        orbit_type="DRO",
    )


@pytest.fixture
def family_artifact() -> Artifact:
    return Artifact(
        artifact_id="bbbb2222",
        artifact_type="family",
        label="Family B",
        orbit_type="DRO",
        extra={"source_record_id": "aaaa1111"},
    )


@pytest.fixture
def transfer_artifact() -> Artifact:
    return Artifact(
        artifact_id="cccc3333",
        artifact_type="transfer",
        label="Transfer C",
        orbit_type="",
    )


class TestAddAndGetById:
    def test_roundtrip(self, project: Project, orbit_artifact: Artifact) -> None:
        project.add(orbit_artifact)
        assert project.get_by_id("aaaa1111") is orbit_artifact

    def test_missing_returns_none(self, project: Project) -> None:
        assert project.get_by_id("no-such-id") is None


class TestRemove:
    def test_remove_existing(self, project: Project, orbit_artifact: Artifact) -> None:
        project.add(orbit_artifact)
        assert project.remove("aaaa1111") is True
        assert project.get_by_id("aaaa1111") is None

    def test_remove_missing(self, project: Project) -> None:
        assert project.remove("no-such-id") is False


class TestArtifactsProperty:
    def test_returns_shallow_copy(
        self, project: Project, orbit_artifact: Artifact
    ) -> None:
        project.add(orbit_artifact)
        copy = project.artifacts
        copy.append(Artifact())  # mutate the copy
        assert len(project.artifacts) == 1  # original unaffected


class TestGetByType:
    def test_filters(
        self,
        project: Project,
        orbit_artifact: Artifact,
        family_artifact: Artifact,
        transfer_artifact: Artifact,
    ) -> None:
        project.add(orbit_artifact)
        project.add(family_artifact)
        project.add(transfer_artifact)
        assert project.get_by_type("orbit") == [orbit_artifact]
        assert project.get_by_type("family") == [family_artifact]
        assert project.get_by_type("transfer") == [transfer_artifact]
        assert project.get_by_type("ephemeris") == []


class TestGetByOrbitType:
    def test_filters(
        self,
        project: Project,
        orbit_artifact: Artifact,
        family_artifact: Artifact,
        transfer_artifact: Artifact,
    ) -> None:
        project.add(orbit_artifact)
        project.add(family_artifact)
        project.add(transfer_artifact)
        dro = project.get_by_orbit_type("DRO")
        assert orbit_artifact in dro
        assert family_artifact in dro
        assert transfer_artifact not in dro


class TestFindUpstream:
    def test_with_upstream(
        self,
        project: Project,
        orbit_artifact: Artifact,
        family_artifact: Artifact,
    ) -> None:
        project.add(orbit_artifact)
        project.add(family_artifact)
        assert project.find_upstream(family_artifact) is orbit_artifact

    def test_without_upstream(
        self, project: Project, orbit_artifact: Artifact
    ) -> None:
        project.add(orbit_artifact)
        assert project.find_upstream(orbit_artifact) is None


class TestLineage:
    """issue #375：谱系读 source_record_id，断链显示降级标记。"""

    def test_broken_lineage_when_upstream_deleted(
        self,
        project: Project,
        orbit_artifact: Artifact,
        family_artifact: Artifact,
    ) -> None:
        project.add(family_artifact)  # 上游不在清单（已删）
        assert project.find_upstream(family_artifact) is None
        assert project.has_broken_lineage(family_artifact) is True

    def test_intact_lineage(
        self,
        project: Project,
        orbit_artifact: Artifact,
        family_artifact: Artifact,
    ) -> None:
        project.add(orbit_artifact)
        project.add(family_artifact)
        assert project.has_broken_lineage(family_artifact) is False

    def test_no_lineage_is_not_broken(
        self, project: Project, orbit_artifact: Artifact
    ) -> None:
        project.add(orbit_artifact)
        assert project.has_broken_lineage(orbit_artifact) is False

    def test_known_record_ids_judge_against_full_library(
        self,
        project: Project,
        orbit_artifact: Artifact,
        family_artifact: Artifact,
    ) -> None:
        """断链按全库判定：过滤视图不含上游（但库里有）不算断链。"""
        project.add(family_artifact)  # 清单里只有下游
        project.known_record_ids = {"aaaa1111", "bbbb2222"}  # 全库两条都在
        assert project.has_broken_lineage(family_artifact) is False

        project.known_record_ids = {"bbbb2222"}  # 全库里上游确实没了
        assert project.has_broken_lineage(family_artifact) is True
