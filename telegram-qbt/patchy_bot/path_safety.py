"""Shared path-safety guards for file deletion operations.

These helpers enforce three invariants for every filesystem mutation:

  1. Traversal containment — the target must live under a known base directory.
  2. Symlink rejection — neither the target nor any ancestor may be a symlink.
  3. Depth validation — the target may be at most ``max_depth`` segments below
     the base directory.

All guards raise :class:`PathSafetyError` on violation. They never return a
boolean — callers must catch the exception or let it propagate.

Containment checks use ``PurePosixPath.is_relative_to()`` per project
convention (never ``str.startswith``).
"""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath


class PathSafetyError(Exception):
    """Raised when a filesystem operation violates a path-safety guard."""


def _resolve_no_symlinks(target: Path) -> Path:
    """Return the absolute form of ``target`` without following symlinks.

    ``Path.resolve(strict=False)`` follows symlinks, which defeats the
    symlink-rejection guard: a symlink pointing outside the base would resolve
    to a path that appears valid. We build the absolute path manually instead,
    normalising ``..`` and ``.`` segments without consulting the filesystem.
    """
    if target.is_absolute():
        return Path(os.path.normpath(str(target)))
    return Path(os.path.normpath(os.path.join(os.getcwd(), str(target))))


def assert_within_base(target: Path, base: Path) -> None:
    """Raise :class:`PathSafetyError` if ``target`` is not contained in ``base``.

    Rejects traversal via ``..`` segments and rejects any symlink encountered
    along the target's ancestor chain. The check uses
    ``PurePosixPath.is_relative_to`` — never string prefix comparison.
    """
    if target is None or base is None:
        raise PathSafetyError("target and base are required")

    abs_base = _resolve_no_symlinks(Path(base))
    abs_target = _resolve_no_symlinks(Path(target))

    if abs_target == abs_base:
        raise PathSafetyError(f"target equals base directory: {abs_target}")

    # Reject symlinks along the ancestor chain (including the target itself).
    reject_symlink(abs_target)

    base_posix = PurePosixPath(str(abs_base))
    target_posix = PurePosixPath(str(abs_target))
    if not target_posix.is_relative_to(base_posix):
        raise PathSafetyError(f"target {abs_target} is not contained in base {abs_base}")


def reject_symlink(target: Path) -> None:
    """Raise :class:`PathSafetyError` if ``target`` or any ancestor is a symlink.

    The check walks the ancestor chain using ``os.path.islink`` on each level.
    ``islink`` does not follow symlinks (unlike ``Path.resolve``), so a
    symlink anywhere in the chain is detected even if the link itself would
    resolve to a safe location.
    """
    if target is None:
        raise PathSafetyError("target is required")

    abs_target = _resolve_no_symlinks(Path(target))

    # Check the target itself.
    try:
        if os.path.islink(str(abs_target)):
            raise PathSafetyError(f"target is a symlink: {abs_target}")
    except OSError as exc:
        raise PathSafetyError(f"cannot stat target {abs_target}: {exc}") from exc

    # Walk ancestors toward the root.
    parent = abs_target.parent
    seen: set[str] = set()
    while True:
        key = str(parent)
        if key in seen:
            break
        seen.add(key)
        if parent == parent.parent:
            break
        try:
            if os.path.islink(key):
                raise PathSafetyError(f"ancestor is a symlink: {parent}")
        except OSError as exc:
            raise PathSafetyError(f"cannot stat ancestor {parent}: {exc}") from exc
        parent = parent.parent


def assert_depth_within(target: Path, base: Path, max_depth: int) -> None:
    """Raise if ``target`` is deeper than ``max_depth`` segments below ``base``.

    Depth is the number of path components between the base and the target.
    A direct child of ``base`` has depth 1. ``max_depth`` must be positive.
    """
    if max_depth <= 0:
        raise PathSafetyError(f"max_depth must be positive, got {max_depth}")

    abs_base = _resolve_no_symlinks(Path(base))
    abs_target = _resolve_no_symlinks(Path(target))

    base_posix = PurePosixPath(str(abs_base))
    target_posix = PurePosixPath(str(abs_target))

    if not target_posix.is_relative_to(base_posix):
        raise PathSafetyError(f"target {abs_target} is not contained in base {abs_base}")

    rel = target_posix.relative_to(base_posix)
    depth = len(rel.parts)
    if depth == 0:
        raise PathSafetyError(f"target equals base directory: {abs_target}")
    if depth > max_depth:
        raise PathSafetyError(f"target depth {depth} exceeds max_depth {max_depth}: {abs_target}")


def safe_delete_file(target: Path, *, base: Path, max_depth: int = 6) -> None:
    """Delete a regular file after running all three path-safety guards.

    Raises :class:`PathSafetyError` if any guard rejects the path. Raises
    ``FileNotFoundError`` if the file does not exist and ``OSError`` on other
    filesystem failures.
    """
    abs_target = _resolve_no_symlinks(Path(target))
    abs_base = _resolve_no_symlinks(Path(base))

    assert_within_base(abs_target, abs_base)
    assert_depth_within(abs_target, abs_base, max_depth)
    # reject_symlink is already called by assert_within_base, but call again
    # defensively in case assert_within_base is bypassed in the future.
    reject_symlink(abs_target)

    if not abs_target.exists():
        raise FileNotFoundError(f"target does not exist: {abs_target}")
    if not abs_target.is_file():
        raise PathSafetyError(f"target is not a regular file: {abs_target}")

    os.unlink(str(abs_target))
