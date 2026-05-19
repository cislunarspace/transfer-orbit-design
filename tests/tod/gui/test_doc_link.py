"""Tests for documentation link functionality."""

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from tod.gui.doc_link_mixin import DocLinkMixin, make_doc_link_label


class TestableDocLinkMixin(DocLinkMixin):
    """Test implementation with DocLinkMixin."""

    def __init__(self, repo_root: Path):
        self._repo_root = repo_root


def test_get_doc_url_existing_doc(tmp_path: Path) -> None:
    """Test that _get_doc_url returns correct URL for existing docs."""
    # Create mock structure: docs/build/html/{script_path_without_ext}.html
    docs = tmp_path / "docs" / "build" / "html"
    script_file = docs / "tod" / "generates" / "cr3bp" / "dro" / "generate_dro_family.html"
    script_file.parent.mkdir(parents=True)
    script_file.touch()

    mixin = TestableDocLinkMixin(tmp_path)
    url = mixin._get_doc_url("tod/generates/cr3bp/dro/generate_dro_family.py")

    assert url is not None
    assert "file://" in url
    assert "tod/generates/cr3bp/dro/generate_dro_family.html" in url


def test_get_doc_url_missing_doc(tmp_path: Path) -> None:
    """Test that _get_doc_url returns None for missing docs."""
    mixin = TestableDocLinkMixin(tmp_path)
    url = mixin._get_doc_url("tod/nonexistent/script.py")

    assert url is None


def test_get_doc_url_no_py_extension(tmp_path: Path) -> None:
    """Test that _get_doc_url works with or without .py extension."""
    docs = tmp_path / "docs" / "build" / "html"
    script_file = docs / "tod" / "generates" / "cr3bp" / "dro" / "generate_dro_family.html"
    script_file.parent.mkdir(parents=True)
    script_file.touch()

    mixin = TestableDocLinkMixin(tmp_path)

    # With .py extension
    url_with_py = mixin._get_doc_url("tod/generates/cr3bp/dro/generate_dro_family.py")
    assert url_with_py is not None

    # Without .py extension
    url_without_py = mixin._get_doc_url("tod/generates/cr3bp/dro/generate_dro_family")
    assert url_without_py is not None


def test_make_doc_link_label_with_url() -> None:
    """Test that make_doc_link_label creates clickable label with URL."""
    app = QApplication.instance() or QApplication([])
    label = make_doc_link_label("Test Script", "file:///path/to/doc")

    assert label.property("doc_url") == "file:///path/to/doc"
    assert label.cursor().shape() == Qt.CursorShape.PointingHandCursor


def test_make_doc_link_label_without_url() -> None:
    """Test that make_doc_link_label creates non-clickable label without URL."""
    app = QApplication.instance() or QApplication([])
    label = make_doc_link_label("Test Script", None)

    assert label.property("doc_url") is None
