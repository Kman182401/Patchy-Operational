"""Tests for patchy_bot.plex_organizer — media file organization into Plex structure."""

from __future__ import annotations

import os
from pathlib import Path

from patchy_bot.plex_organizer import (
    _parse_movie,
    _parse_tv,
    _strip_site_prefix,
    organize_download,
    organize_movie,
    organize_tv,
)

# ---------------------------------------------------------------------------
# _parse_tv
# ---------------------------------------------------------------------------


class TestParseTv:
    def test_standard_single_episode(self) -> None:
        result = _parse_tv("Show.Name.S01E02.1080p.WEB-DL")
        assert result is not None
        show, season, eps = result
        assert show == "Show Name"
        assert season == 1
        assert eps == [2]

    def test_multi_episode(self) -> None:
        result = _parse_tv("Show.S01E02E03.720p")
        assert result is not None
        show, season, eps = result
        assert show == "Show"
        assert season == 1
        assert eps == [2, 3]

    def test_season_pack_sXX(self) -> None:
        result = _parse_tv("Show.Name.S02.1080p.BluRay")
        assert result is not None
        show, season, eps = result
        assert show == "Show Name"
        assert season == 2
        assert eps == []

    def test_site_prefix_stripped(self) -> None:
        result = _parse_tv("www.UIndex.org - Show.S01E02.1080p")
        assert result is not None
        show, season, eps = result
        assert show == "Show"
        assert season == 1
        assert eps == [2]

    def test_non_tv_returns_none(self) -> None:
        assert _parse_tv("Movie.Name.2024.1080p") is None

    def test_upper_case(self) -> None:
        result = _parse_tv("SHOW.NAME.S03E10.HDTV")
        assert result is not None
        show, season, eps = result
        assert show == "SHOW NAME"
        assert season == 3
        assert eps == [10]

    def test_year_stripped_from_show_name(self) -> None:
        result = _parse_tv("Show.Name.2021.S01E05.720p")
        assert result is not None
        show, season, eps = result
        assert "2021" not in show
        assert season == 1
        assert eps == [5]

    def test_tracker_tag_stripped(self) -> None:
        result = _parse_tv("Show.Name.S02E08.720p[EZTVx.to]")
        assert result is not None
        show, season, eps = result
        assert season == 2
        assert eps == [8]


# ---------------------------------------------------------------------------
# _parse_movie
# ---------------------------------------------------------------------------


class TestParseMovie:
    def test_scene_format(self) -> None:
        result = _parse_movie("Movie.Name.2024.1080p.BluRay")
        assert result is not None
        title, year = result
        assert title == "Movie Name"
        assert year == 2024

    def test_parens_year(self) -> None:
        result = _parse_movie("Movie Name (2023) 1080p")
        assert result is not None
        title, year = result
        assert title == "Movie Name"
        assert year == 2023

    def test_brackets_year_inside_returns_none(self) -> None:
        # Year is inside brackets — gets stripped along with everything else
        result = _parse_movie("Movie Name [2024] [1080p] [YTS.MX]")
        assert result is None

    def test_brackets_tracker_only(self) -> None:
        # Year in scene format, only tracker tag in brackets
        result = _parse_movie("Movie.Name.2024.1080p.BluRay [YTS.MX]")
        assert result is not None
        title, year = result
        assert title == "Movie Name"
        assert year == 2024

    def test_no_year_returns_none(self) -> None:
        # No 19xx/20xx year pattern -> None
        assert _parse_movie("Movie.Title.1080p.WEB-DL") is None

    def test_old_year(self) -> None:
        result = _parse_movie("Classic.Film.1995.DVDRip")
        assert result is not None
        title, year = result
        assert title == "Classic Film"
        assert year == 1995

    def test_site_prefix_stripped(self) -> None:
        result = _parse_movie("www.SomeSite.org - Movie.Name.2022.1080p")
        assert result is not None
        title, year = result
        assert title == "Movie Name"
        assert year == 2022


# ---------------------------------------------------------------------------
# _strip_site_prefix
# ---------------------------------------------------------------------------


class TestStripSitePrefix:
    def test_removes_prefix(self) -> None:
        assert _strip_site_prefix("www.Site.org - Show.S01E02") == "Show.S01E02"

    def test_no_prefix_unchanged(self) -> None:
        assert _strip_site_prefix("Show.S01E02") == "Show.S01E02"

    def test_dash_variant(self) -> None:
        assert _strip_site_prefix("www.Example.com  -  Name.2024") == "Name.2024"


# ---------------------------------------------------------------------------
# organize_download — filesystem tests using tmp_path
# ---------------------------------------------------------------------------


class TestOrganizeDownload:
    def test_movie_single_file(self, tmp_path: Path) -> None:
        movies_root = tmp_path / "Movies"
        movies_root.mkdir()
        tv_root = tmp_path / "TV"
        tv_root.mkdir()

        src = tmp_path / "Cool.Movie.2024.1080p.BluRay.mkv"
        src.write_bytes(b"\x00" * 100)

        result = organize_download(str(src), "Movies", str(tv_root), str(movies_root))
        assert result.moved is True
        assert result.files_moved == 1
        # Should end up in Movies/Cool Movie (2024)/Cool Movie (2024).mkv
        expected_dir = movies_root / "Cool Movie (2024)"
        assert expected_dir.is_dir()
        expected_file = expected_dir / "Cool Movie (2024).mkv"
        assert expected_file.exists()

    def test_tv_single_file(self, tmp_path: Path) -> None:
        tv_root = tmp_path / "TV"
        tv_root.mkdir()
        movies_root = tmp_path / "Movies"
        movies_root.mkdir()

        src = tmp_path / "Show.Name.S01E02.720p.mkv"
        src.write_bytes(b"\x00" * 100)

        result = organize_download(str(src), "TV", str(tv_root), str(movies_root))
        assert result.moved is True
        assert result.files_moved == 1
        season_dir = tv_root / "Show Name" / "Season 01"
        assert season_dir.is_dir()

    def test_tv_directory_video_and_subtitle(self, tmp_path: Path) -> None:
        tv_root = tmp_path / "TV"
        tv_root.mkdir()
        movies_root = tmp_path / "Movies"

        src_dir = tmp_path / "Show.Name.S02E05.1080p"
        src_dir.mkdir()
        (src_dir / "Show.Name.S02E05.1080p.mkv").write_bytes(b"\x00" * 100)
        (src_dir / "Show.Name.S02E05.srt").write_bytes(b"subtitle")

        result = organize_download(str(src_dir), "TV", str(tv_root), str(movies_root))
        assert result.moved is True
        assert result.files_moved == 2
        season_dir = tv_root / "Show Name" / "Season 02"
        assert season_dir.is_dir()
        # Both video and subtitle should be in the season dir
        files_in_season = os.listdir(str(season_dir))
        assert len(files_in_season) == 2

    def test_tv_directory_junk_files_skipped(self, tmp_path: Path) -> None:
        tv_root = tmp_path / "TV"
        tv_root.mkdir()
        movies_root = tmp_path / "Movies"

        src_dir = tmp_path / "Show.Name.S01E01.HDTV"
        src_dir.mkdir()
        (src_dir / "episode.mkv").write_bytes(b"\x00" * 100)
        (src_dir / "readme.txt").write_text("junk")
        (src_dir / "setup.exe").write_bytes(b"\x00")

        result = organize_download(str(src_dir), "TV", str(tv_root), str(movies_root))
        assert result.moved is True
        assert result.files_moved == 1  # only the .mkv
        season_dir = tv_root / "Show Name" / "Season 01"
        files_in_season = os.listdir(str(season_dir))
        exts = {os.path.splitext(f)[1] for f in files_in_season}
        assert ".txt" not in exts
        assert ".exe" not in exts

    def test_movie_directory(self, tmp_path: Path) -> None:
        movies_root = tmp_path / "Movies"
        movies_root.mkdir()
        tv_root = tmp_path / "TV"

        src_dir = tmp_path / "Great.Film.2023.1080p.BluRay"
        src_dir.mkdir()
        (src_dir / "Great.Film.2023.1080p.BluRay.mkv").write_bytes(b"\x00" * 100)

        result = organize_download(str(src_dir), "Movies", str(tv_root), str(movies_root))
        assert result.moved is True
        target_dir = movies_root / "Great Film (2023)"
        assert target_dir.is_dir()

    def test_nonexistent_path(self, tmp_path: Path) -> None:
        fake = str(tmp_path / "does_not_exist")
        result = organize_download(fake, "Movies", "/tmp/tv", "/tmp/movies")
        assert result.moved is False
        assert "path does not exist" in result.summary

    def test_unknown_category(self, tmp_path: Path) -> None:
        src = tmp_path / "file.mkv"
        src.write_bytes(b"\x00")
        result = organize_download(str(src), "Anime", "/tmp/tv", "/tmp/movies")
        assert result.moved is False
        assert "unknown category" in result.summary

    def test_empty_directory_no_media(self, tmp_path: Path) -> None:
        tv_root = tmp_path / "TV"
        tv_root.mkdir()
        movies_root = tmp_path / "Movies"

        src_dir = tmp_path / "Show.Name.S01E01.720p"
        src_dir.mkdir()
        # Only junk — no KEEP_EXTS files
        (src_dir / "readme.txt").write_text("no media here")

        result = organize_download(str(src_dir), "TV", str(tv_root), str(movies_root))
        assert result.files_moved == 0


# ---------------------------------------------------------------------------
# organize_tv — existing show directory reuse & season creation
# ---------------------------------------------------------------------------


class TestOrganizeTvExistingDir:
    def test_uses_existing_show_dir(self, tmp_path: Path) -> None:
        tv_root = tmp_path / "TV"
        tv_root.mkdir()
        # Pre-create an existing show dir with different casing
        existing = tv_root / "Show Name"
        existing.mkdir()

        src = tmp_path / "show.name.S01E03.720p.mkv"
        src.write_bytes(b"\x00" * 100)

        result = organize_tv(str(src), str(tv_root))
        assert result.moved is True
        # Should use the existing "Show Name" dir, not create "show name"
        season_dir = existing / "Season 01"
        assert season_dir.is_dir()

    def test_season_dir_auto_created(self, tmp_path: Path) -> None:
        tv_root = tmp_path / "TV"
        tv_root.mkdir()

        src = tmp_path / "New.Show.S03E01.1080p.mkv"
        src.write_bytes(b"\x00" * 100)

        result = organize_tv(str(src), str(tv_root))
        assert result.moved is True
        season_dir = tv_root / "New Show" / "Season 03"
        assert season_dir.is_dir()


# ---------------------------------------------------------------------------
# organize_movie — already organized
# ---------------------------------------------------------------------------


class TestOrganizeMovieAlreadyOrganized:
    def test_already_organized_returns_false(self, tmp_path: Path) -> None:
        movies_root = tmp_path / "Movies"
        movies_root.mkdir()
        # Create target dir that matches what the organizer would produce
        target = movies_root / "Film (2024)"
        target.mkdir()
        (target / "Film.2024.1080p.mkv").write_bytes(b"\x00" * 100)

        # content_path == target_dir => already organized
        result = organize_movie(str(target), str(movies_root))
        assert result.moved is False
        assert "already organized" in result.summary


# ---------------------------------------------------------------------------
# Edge case: empty content_path
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_content_path(self) -> None:
        result = organize_download("", "Movies", "/tmp/tv", "/tmp/movies")
        assert result.moved is False
        assert "path does not exist" in result.summary

    def test_none_content_path(self) -> None:
        result = organize_download(None, "Movies", "/tmp/tv", "/tmp/movies")  # type: ignore[arg-type]
        assert result.moved is False
