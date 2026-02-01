"""Tests for path traversal validation in backup module."""

import os
from pathlib import Path
import pytest
from mcp_memoria.storage.backup import PathTraversalError, validate_safe_path


class TestValidateSafePath:
    """Tests for validate_safe_path function."""

    def test_valid_home_path(self, tmp_path: Path) -> None:
        """Test that paths under home directory are allowed."""
        # tmp_path is under /tmp which is allowed by default
        test_file = tmp_path / "test.json"
        result = validate_safe_path(test_file)
        assert result == test_file.resolve()

    def test_valid_tmp_path(self) -> None:
        """Test that paths under /tmp are allowed."""
        test_path = Path("/tmp/memoria_test/export.json")
        result = validate_safe_path(test_path)
        assert result == test_path.resolve()

    def test_path_traversal_blocked(self, tmp_path: Path) -> None:
        """Test that path traversal attempts are blocked."""
        # Try to escape with ../
        malicious_path = tmp_path / ".." / ".." / ".." / "etc" / "passwd"

        with pytest.raises(PathTraversalError) as exc_info:
            validate_safe_path(malicious_path, allowed_dirs=[tmp_path])

        assert "outside allowed directories" in str(exc_info.value)

    def test_absolute_path_outside_allowed(self) -> None:
        """Test that absolute paths outside allowed dirs are blocked."""
        # /etc is not under home or /tmp
        with pytest.raises(PathTraversalError):
            validate_safe_path(Path("/etc/passwd"))

    def test_symlink_resolution(self, tmp_path: Path) -> None:
        """Test that symlinks are resolved and validated."""
        # Create a symlink that points outside allowed directory
        link_path = tmp_path / "link"
        target = Path("/etc")

        try:
            link_path.symlink_to(target)
        except (OSError, PermissionError):
            pytest.skip("Cannot create symlinks")

        with pytest.raises(PathTraversalError):
            validate_safe_path(link_path / "passwd", allowed_dirs=[tmp_path])

    def test_custom_allowed_dirs(self, tmp_path: Path) -> None:
        """Test that custom allowed directories work."""
        custom_dir = tmp_path / "custom"
        custom_dir.mkdir()
        test_file = custom_dir / "test.json"

        result = validate_safe_path(test_file, allowed_dirs=[custom_dir])
        assert result == test_file.resolve()

    def test_custom_allowed_dirs_blocks_others(self, tmp_path: Path) -> None:
        """Test that only custom allowed dirs are permitted."""
        custom_dir = tmp_path / "allowed"
        other_dir = tmp_path / "other"
        custom_dir.mkdir()
        other_dir.mkdir()

        test_file = other_dir / "test.json"

        with pytest.raises(PathTraversalError):
            validate_safe_path(test_file, allowed_dirs=[custom_dir])

    def test_relative_path_in_allowed(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that relative paths are resolved correctly."""
        # Change to tmp_path
        monkeypatch.chdir(tmp_path)

        result = validate_safe_path(Path("test.json"), allowed_dirs=[tmp_path])
        assert result == (tmp_path / "test.json").resolve()
