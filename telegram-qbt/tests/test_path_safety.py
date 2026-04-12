"""Unit tests for patchy_bot.path_safety."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from patchy_bot.path_safety import (
    PathSafetyError,
    assert_depth_within,
    assert_within_base,
    reject_symlink,
    safe_delete_file,
)


@pytest.fixture
def base_dir(tmp_path: Path) -> Path:
    base = tmp_path / "tv"
    base.mkdir()
    return base


def test_safe_delete_file_happy_path(base_dir: Path) -> None:
    show_dir = base_dir / "Example Show"
    show_dir.mkdir()
    target = show_dir / "episode.mkv"
    target.write_bytes(b"data")

    safe_delete_file(target, base=base_dir)

    assert not target.exists()


def test_assert_within_base_rejects_traversal(base_dir: Path) -> None:
    # base/../etc/passwd — classic traversal attempt.
    evil = base_dir / ".." / "etc" / "passwd"
    with pytest.raises(PathSafetyError, match="not contained in base"):
        assert_within_base(evil, base_dir)


def test_safe_delete_file_rejects_symlink_target(base_dir: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"x")
    link = base_dir / "link.mkv"
    link.symlink_to(outside)

    with pytest.raises(PathSafetyError, match="symlink"):
        safe_delete_file(link, base=base_dir)

    assert outside.exists()  # guard must prevent any deletion
    assert link.is_symlink()


def test_safe_delete_file_rejects_symlink_ancestor(base_dir: Path, tmp_path: Path) -> None:
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    (real_dir / "ep.mkv").write_bytes(b"x")
    link_dir = base_dir / "Linked Show"
    link_dir.symlink_to(real_dir)

    target = link_dir / "ep.mkv"
    with pytest.raises(PathSafetyError, match="symlink"):
        safe_delete_file(target, base=base_dir)


def test_assert_depth_within_rejects_too_deep(base_dir: Path) -> None:
    # Build base/a/b/c/d/e/f/g — depth 7.
    cursor = base_dir
    for seg in ("a", "b", "c", "d", "e", "f", "g"):
        cursor = cursor / seg
    with pytest.raises(PathSafetyError, match="depth"):
        assert_depth_within(cursor, base_dir, max_depth=6)


def test_safe_delete_file_rejects_base_itself(base_dir: Path) -> None:
    with pytest.raises(PathSafetyError, match="equals base"):
        safe_delete_file(base_dir, base=base_dir)


def test_safe_delete_file_rejects_base_dot(base_dir: Path) -> None:
    dot_target = Path(str(base_dir) + os.sep + ".")
    with pytest.raises(PathSafetyError, match="equals base"):
        safe_delete_file(dot_target, base=base_dir)


def test_reject_symlink_plain_file_is_ok(base_dir: Path) -> None:
    target = base_dir / "ok.txt"
    target.write_bytes(b"x")
    # Should not raise.
    reject_symlink(target)
