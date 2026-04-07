"""Tests for _try_remove_empty_tree path containment guard."""

from __future__ import annotations

import logging

from patchy_bot.plex_organizer import _try_remove_empty_tree, organize_movie


class TestTryRemoveEmptyTree:
    """_try_remove_empty_tree respects allowed_roots and rejects unsafe paths."""

    def test_removes_empty_dir_inside_allowed_root(self, tmp_path):
        """Empty dir inside allowed root is removed."""
        root = tmp_path / "media"
        root.mkdir()
        target = root / "ShowName" / "Season 01"
        target.mkdir(parents=True)
        # Add a non-media file (should still count as "empty" of media)
        (target / "readme.txt").write_text("info")

        _try_remove_empty_tree(str(target), allowed_roots=(str(root),))
        assert not target.exists()

    def test_keeps_dir_with_media_files(self, tmp_path):
        """Dir containing media files is NOT removed."""
        root = tmp_path / "media"
        root.mkdir()
        target = root / "ShowName"
        target.mkdir()
        (target / "episode.mkv").write_text("fake video")

        _try_remove_empty_tree(str(target), allowed_roots=(str(root),))
        assert target.exists()

    def test_rejects_path_outside_allowed_roots(self, tmp_path, caplog):
        """Path outside allowed roots is NOT removed, warning logged."""
        allowed_root = tmp_path / "media"
        allowed_root.mkdir()
        outside = tmp_path / "other" / "stuff"
        outside.mkdir(parents=True)

        with caplog.at_level(logging.WARNING):
            _try_remove_empty_tree(str(outside), allowed_roots=(str(allowed_root),))

        assert outside.exists()
        assert "outside media roots" in caplog.text

    def test_rejects_symlinked_path(self, tmp_path, caplog):
        """Symlinked path is NOT removed, warning logged."""
        root = tmp_path / "media"
        root.mkdir()
        real_dir = root / "real_show"
        real_dir.mkdir()
        link = root / "linked_show"
        link.symlink_to(real_dir)

        with caplog.at_level(logging.WARNING):
            _try_remove_empty_tree(str(link), allowed_roots=(str(root),))

        assert link.exists()
        assert real_dir.exists()
        assert "symlinked path" in caplog.text.lower()

    def test_rejects_path_equal_to_root(self, tmp_path, caplog):
        """Path resolving to the root itself is NOT removed."""
        root = tmp_path / "media"
        root.mkdir()

        with caplog.at_level(logging.WARNING):
            _try_remove_empty_tree(str(root), allowed_roots=(str(root),))

        assert root.exists()
        assert "outside media roots" in caplog.text

    def test_no_allowed_roots_original_behavior(self, tmp_path):
        """Empty allowed_roots — removes empty dir (backward compat)."""
        target = tmp_path / "some_dir"
        target.mkdir()
        (target / "notes.txt").write_text("not media")

        _try_remove_empty_tree(str(target))  # no allowed_roots
        assert not target.exists()


class TestOrganizeMovie:
    """organize_movie handles single and multi-video directories correctly."""

    def test_single_video_renamed(self, tmp_path):
        """Single video file is renamed to match the movie name."""
        movies_root = tmp_path / "Movies"
        movies_root.mkdir()
        # Create a scene-named movie directory
        content = tmp_path / "The.Matrix.1999.1080p.BluRay.x264"
        content.mkdir()
        (content / "the.matrix.1999.1080p.bluray.x264.mkv").write_text("video")
        (content / "the.matrix.1999.1080p.bluray.x264.srt").write_text("subs")

        result = organize_movie(str(content), str(movies_root))

        assert result.moved is True
        assert result.files_moved == 1
        target_dir = movies_root / "The Matrix (1999)"
        assert target_dir.exists()
        # Video file should be renamed to match movie name
        assert (target_dir / "The Matrix (1999).mkv").exists()
        # Subtitle should keep original name (not a VIDEO_EXT)
        assert (target_dir / "the.matrix.1999.1080p.bluray.x264.srt").exists()

    def test_multi_video_not_renamed(self, tmp_path):
        """Multiple video files keep their original names."""
        movies_root = tmp_path / "Movies"
        movies_root.mkdir()
        content = tmp_path / "The.Matrix.1999.1080p.BluRay.x264"
        content.mkdir()
        (content / "the.matrix.mkv").write_text("main movie")
        (content / "bonus.features.mkv").write_text("extras")

        result = organize_movie(str(content), str(movies_root))

        assert result.moved is True
        assert result.files_moved == 2
        target_dir = movies_root / "The Matrix (1999)"
        assert target_dir.exists()
        # Both files should keep their ORIGINAL names
        assert (target_dir / "the.matrix.mkv").exists()
        assert (target_dir / "bonus.features.mkv").exists()
        # Should NOT have a renamed file
        assert not (target_dir / "The Matrix (1999).mkv").exists()

    def test_no_video_files(self, tmp_path):
        """Directory with no video files is rejected to prevent junk in Plex."""
        movies_root = tmp_path / "Movies"
        movies_root.mkdir()
        content = tmp_path / "The.Matrix.1999.1080p.BluRay.x264"
        content.mkdir()
        (content / "readme.nfo").write_text("info")

        result = organize_movie(str(content), str(movies_root))

        assert result.moved is False
        assert result.files_moved == 0
        assert "no real video files" in result.summary or "no video files" in result.summary
