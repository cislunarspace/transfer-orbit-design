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
        extra={"source_artifact_id": "aaaa1111"},
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
