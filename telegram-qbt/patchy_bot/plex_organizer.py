"""
Post-download media organizer for Plex.

Parses scene-release torrent names and moves files into Plex-standard
directory structure:
  TV:     Show Name/Season XX/original_filename.mkv
  Movies: Movie Name (Year)/original_filename.mkv

Called by the bot after download completes, before Plex library scan.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
from dataclasses import dataclass

LOG = logging.getLogger("qbtg.organizer")

VIDEO_EXTS = frozenset({".mkv", ".mp4", ".avi", ".m4v", ".ts", ".wmv"})
KEEP_EXTS = VIDEO_EXTS | frozenset({".srt", ".ass", ".ssa", ".sub", ".idx", ".vtt", ".nfo"})


@dataclass
class OrganizeResult:
    moved: bool
    new_path: str  # final content path (for Plex scan)
    summary: str  # human-readable one-liner
    files_moved: int


def _strip_site_prefix(name: str) -> str:
    """Remove leading site prefixes like 'www.UIndex.org    -    '."""
    return re.sub(r"^www\.\S+\s*[-–—]+\s*", "", name).strip()


def _strip_tracker_tags(name: str) -> str:
    """Remove trailing tracker tags like [EZTVx.to], [TGx], etc."""
    return re.sub(r"\[[\w.]+\]", "", name).strip()


def _strip_brackets(name: str) -> str:
    """Remove all bracket-enclosed tags like [1080p], [YTS.MX], [BluRay]."""
    cleaned = re.sub(r"\s*\[.*?\]\s*", " ", name).strip()
    return re.sub(r"\s+", " ", cleaned)


def _dots_to_spaces(name: str) -> str:
    """Convert dot-separated scene names to spaces, preserving extensions."""
    # Don't convert if it already has spaces (non-scene name)
    if " " in name and "." not in name.replace(".mkv", "").replace(".mp4", ""):
        return name
    return re.sub(r"\.(?!mkv$|mp4$|avi$|srt$|nfo$)", " ", name)


def _parse_tv(name: str) -> tuple[str, int, list[int]] | None:
    """Extract (show_name, season_num, [episode_nums]) from a torrent name.

    Returns None if not detected as TV.
    """
    cleaned = _strip_site_prefix(name)
    cleaned = _strip_tracker_tags(cleaned)

    # Match S01E02 or S01E02E03 patterns
    m = re.search(r"[.\s]S(\d{1,2})E(\d{1,3})(?:E(\d{1,3}))?", cleaned, re.IGNORECASE)
    if m:
        show_part = cleaned[: m.start()]
        show_name = _dots_to_spaces(show_part).strip(" .-")
        # Remove year suffix if present (e.g. "Invincible 2021" -> "Invincible")
        show_name = re.sub(r"\s+\d{4}\s*$", "", show_name).strip()
        season = int(m.group(1))
        episodes = [int(m.group(2))]
        if m.group(3):
            episodes.append(int(m.group(3)))
        if show_name:
            return show_name, season, episodes

    # Match "Season X" or "SEASON.XX.SXX" in directory names (complete season packs)
    m = re.search(r"[.\s](?:SEASON[.\s]*)?S(\d{1,2})[.\s]", cleaned, re.IGNORECASE)
    if m:
        show_part = cleaned[: m.start()]
        show_name = _dots_to_spaces(show_part).strip(" .-")
        show_name = re.sub(r"\s+\d{4}\s*$", "", show_name).strip()
        season = int(m.group(1))
        if show_name:
            return show_name, season, []  # empty episodes = season pack

    return None


def _parse_movie(name: str) -> tuple[str, int | None] | None:
    """Extract (movie_title, year) from a torrent name.

    Returns None if not detected as a movie.
    """
    cleaned = _strip_site_prefix(name)
    cleaned = _strip_tracker_tags(cleaned)
    cleaned = _strip_brackets(cleaned)

    # Try "Title (Year)" format first (already clean)
    m = re.match(r"^(.+?)\s*\((\d{4})\)", cleaned)
    if m:
        return m.group(1).strip(), int(m.group(2))

    # Try scene format: "Title.Name.Year.quality.stuff"
    m = re.match(r"^(.+?)[.\s]((?:19|20)\d{2})[.\s]", cleaned)
    if m:
        title = _dots_to_spaces(m.group(1)).strip(" .-")
        return title, int(m.group(2))

    # Try "Title Year quality" with spaces
    m = re.match(r"^(.+?)\s+((?:19|20)\d{2})\s+", cleaned)
    if m:
        return m.group(1).strip(), int(m.group(2))

    return None


def _find_existing_show_dir(tv_root: str, parsed_name: str) -> str | None:
    """Find an existing show directory that matches the parsed name.

    Handles case differences and minor variations.
    """
    if not os.path.isdir(tv_root):
        return None
    normalized = parsed_name.lower().strip()
    for entry in os.listdir(tv_root):
        entry_path = os.path.join(tv_root, entry)
        if not os.path.isdir(entry_path):
            continue
        # Compare base name without year suffix
        entry_base = re.sub(r"\s*\(\d{4}\)\s*$", "", entry).strip().lower()
        if entry_base == normalized or entry.lower() == normalized:
            return entry
    return None


def _find_existing_movie_dir(movies_root: str, parsed_title: str, year: int | None) -> str | None:
    """Find an existing movie directory matching title and year."""
    if not os.path.isdir(movies_root):
        return None
    norm_title = parsed_title.lower().strip()
    for entry in os.listdir(movies_root):
        entry_path = os.path.join(movies_root, entry)
        if not os.path.isdir(entry_path):
            continue
        entry_clean = _strip_brackets(entry)
        entry_base = re.sub(r"\s*\(\d{4}\)\s*$", "", entry_clean).strip().lower()
        if entry_base == norm_title:
            return entry
    return None


def organize_tv(content_path: str, tv_root: str) -> OrganizeResult:
    """Organize a completed TV download into Show/Season XX/ structure."""
    name = os.path.basename(content_path.rstrip("/"))
    parsed = _parse_tv(name)
    if not parsed:
        return OrganizeResult(False, content_path, "could not parse TV name", 0)

    show_name, season, episodes = parsed

    # Find existing show dir or use parsed name
    existing_dir = _find_existing_show_dir(tv_root, show_name)
    show_dir_name = existing_dir or show_name
    season_dir = os.path.join(tv_root, show_dir_name, f"Season {season:02d}")
    os.makedirs(season_dir, exist_ok=True)

    files_moved = 0

    if os.path.isfile(content_path):
        # Single file download
        dst = os.path.join(season_dir, _strip_tracker_tags(name))
        if not os.path.exists(dst):
            shutil.move(content_path, dst)
            files_moved = 1
            return OrganizeResult(True, dst, f"{show_dir_name} S{season:02d} -> Season {season:02d}/", files_moved)
        else:
            return OrganizeResult(False, content_path, f"already exists: {os.path.basename(dst)}", 0)

    elif os.path.isdir(content_path):
        # Directory download — move media files into season dir
        moved_files = []
        for f in os.listdir(content_path):
            ext = os.path.splitext(f)[1].lower()
            if ext in KEEP_EXTS:
                src = os.path.join(content_path, f)
                clean_name = _strip_tracker_tags(f)
                dst = os.path.join(season_dir, clean_name)
                if not os.path.exists(dst):
                    shutil.move(src, dst)
                    moved_files.append(clean_name)
                    files_moved += 1
            elif os.path.isdir(os.path.join(content_path, f)):
                # Check subdirs for season packs (e.g., S01/, S02/)
                subdir = os.path.join(content_path, f)
                sub_parsed = _parse_tv(f)
                if sub_parsed:
                    sub_season = sub_parsed[1]
                    sub_season_dir = os.path.join(tv_root, show_dir_name, f"Season {sub_season:02d}")
                    os.makedirs(sub_season_dir, exist_ok=True)
                    for sf in os.listdir(subdir):
                        if os.path.splitext(sf)[1].lower() in KEEP_EXTS:
                            src = os.path.join(subdir, sf)
                            clean_sf = _strip_tracker_tags(sf)
                            dst = os.path.join(sub_season_dir, clean_sf)
                            if not os.path.exists(dst):
                                shutil.move(src, dst)
                                files_moved += 1

        # Clean up empty source dir
        if files_moved > 0:
            _try_remove_empty_tree(content_path, allowed_roots=(tv_root,))

        ep_str = f"E{episodes[0]:02d}" if episodes else f"{files_moved} files"
        return OrganizeResult(
            files_moved > 0,
            season_dir,
            f"{show_dir_name} S{season:02d}{ep_str} -> Season {season:02d}/",
            files_moved,
        )

    return OrganizeResult(False, content_path, "path not found", 0)


def organize_movie(content_path: str, movies_root: str) -> OrganizeResult:
    """Organize a completed movie download into Movie Name (Year)/ structure."""
    name = os.path.basename(content_path.rstrip("/"))
    parsed = _parse_movie(name)
    if not parsed:
        return OrganizeResult(False, content_path, "could not parse movie name", 0)

    title, year = parsed
    target_name = f"{title} ({year})" if year else title

    # Check for existing dir
    existing = _find_existing_movie_dir(movies_root, title, year)

    if os.path.isfile(content_path):
        # Loose movie file — move into a directory
        movie_dir = os.path.join(movies_root, existing or target_name)
        os.makedirs(movie_dir, exist_ok=True)
        ext = os.path.splitext(name)[1]
        dst_name = target_name + ext
        dst = os.path.join(movie_dir, dst_name)
        if not os.path.exists(dst):
            shutil.move(content_path, dst)
            return OrganizeResult(True, movie_dir, f"-> {target_name}/", 1)
        return OrganizeResult(False, content_path, f"already exists: {dst_name}", 0)

    elif os.path.isdir(content_path):
        # Directory download — rename dir if needed, rename main video file
        clean_dirname = _strip_brackets(name)
        parsed_again = _parse_movie(clean_dirname)
        if parsed_again:
            target_name = f"{parsed_again[0]} ({parsed_again[1]})" if parsed_again[1] else parsed_again[0]

        if existing:
            target_name = existing

        target_dir = os.path.join(movies_root, target_name)

        if content_path == target_dir:
            return OrganizeResult(False, content_path, "already organized", 0)

        if os.path.exists(target_dir) and target_dir != content_path:
            return OrganizeResult(False, content_path, f"target exists: {target_name}/", 0)

        # Rename directory
        shutil.move(content_path, target_dir)

        # Rename main video file inside to match Plex convention
        video_files = [f for f in os.listdir(target_dir) if os.path.splitext(f)[1].lower() in VIDEO_EXTS]
        files_moved = len(video_files)

        if len(video_files) == 1:
            f = video_files[0]
            ext = os.path.splitext(f)[1].lower()
            new_name = target_name + ext
            src = os.path.join(target_dir, f)
            dst = os.path.join(target_dir, new_name)
            if src != dst and not os.path.exists(dst):
                os.rename(src, dst)
        elif len(video_files) > 1:
            LOG.info("Movie dir has %d video files — skipping rename: %s", len(video_files), target_dir)

        return OrganizeResult(True, target_dir, f"-> {target_name}/", files_moved)

    return OrganizeResult(False, content_path, "path not found", 0)


def organize_download(
    content_path: str,
    category: str,
    tv_root: str,
    movies_root: str,
) -> OrganizeResult:
    """Main entry point. Routes to TV or movie organizer based on category."""
    if not content_path or not os.path.exists(content_path):
        return OrganizeResult(False, content_path or "", "path does not exist", 0)

    cat = category.lower().strip()

    if cat in ("tv", "shows", "tv shows"):
        result = organize_tv(content_path, tv_root)
    elif cat in ("movies", "movie", "films"):
        result = organize_movie(content_path, movies_root)
    else:
        LOG.info("Organizer: unknown category '%s', skipping", category)
        return OrganizeResult(False, content_path, f"unknown category: {category}", 0)

    if result.moved:
        LOG.info("Organized: %s -> %s (%d files)", content_path, result.new_path, result.files_moved)
    else:
        LOG.info("Organizer skipped: %s (%s)", content_path, result.summary)

    return result


def _try_remove_empty_tree(path: str, *, allowed_roots: tuple[str, ...] = ()) -> None:
    """Remove a directory tree if it contains no more media files.

    When *allowed_roots* is given, the path must resolve inside one of them
    and must not be a symlink.
    """
    if not os.path.isdir(path):
        return

    real_path = os.path.realpath(path)

    # Reject symlinks — content_path should never be a symlink
    if os.path.islink(path):
        LOG.warning("Refusing to remove symlinked path: %s -> %s", path, real_path)
        return

    # Path containment: must be inside one of the allowed media roots
    if allowed_roots:
        inside = False
        for root in allowed_roots:
            real_root = os.path.realpath(root)
            if real_path.startswith(real_root + os.sep):
                inside = True
                break
        if not inside:
            LOG.warning(
                "Refusing to remove path outside media roots: %s (resolves to %s, allowed: %s)",
                path,
                real_path,
                allowed_roots,
            )
            return

    has_media = False
    for root, dirs, files in os.walk(path):
        for f in files:
            if os.path.splitext(f)[1].lower() in KEEP_EXTS:
                has_media = True
                break
        if has_media:
            break
    if not has_media:
        try:
            shutil.rmtree(path)
            LOG.info("Removed empty source dir: %s", path)
        except Exception:
            LOG.warning("Failed to remove source dir: %s", path, exc_info=True)
