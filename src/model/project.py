from __future__ import annotations

from src.model.artifact import Artifact


class Project:
    """Container for artifacts belonging to a single project."""

    def __init__(self, name: str) -> None:
        self.name: str = name
        self._artifacts: list[Artifact] = []

    def add(self, artifact: Artifact) -> None:
        """Add an artifact to the project."""
        self._artifacts.append(artifact)

    def remove(self, artifact_id: str) -> bool:
        """Remove an artifact by id. Returns True if found and removed."""
        for i, art in enumerate(self._artifacts):
            if art.artifact_id == artifact_id:
                self._artifacts.pop(i)
                return True
        return False

    @property
    def artifacts(self) -> list[Artifact]:
        """Return a shallow copy of the artifact list."""
        return list(self._artifacts)

    def get_by_id(self, artifact_id: str) -> Artifact | None:
        """Find an artifact by its id, or None."""
        for art in self._artifacts:
            if art.artifact_id == artifact_id:
                return art
        return None

    def get_by_type(self, artifact_type: str) -> list[Artifact]:
        """Return artifacts matching the given artifact_type."""
        return [a for a in self._artifacts if a.artifact_type == artifact_type]

    def get_by_orbit_type(self, orbit_type: str) -> list[Artifact]:
        """Return artifacts matching the given orbit_type."""
        return [a for a in self._artifacts if a.orbit_type == orbit_type]

    def find_upstream(self, artifact: Artifact) -> Artifact | None:
        """Find the upstream artifact referenced by extra['source_artifact_id']."""
        source_id = artifact.extra.get("source_artifact_id")
        if source_id is None:
            return None
        return self.get_by_id(source_id)
