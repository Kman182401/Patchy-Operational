"""
Unit tests for the _delete_remove_candidate path-safety guards.

These tests verify that the deletion workflow correctly rejects:
- path traversal attempts (../escapes)
- symbolic links
- wrong depth for each media type (movies, tv shows, seasons, episodes)
- unsupported root keys

And correctly allows:
- valid movie folder deletion
- valid TV show/season/episode deletion
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from qbt_telegram_bot import BotApp, Config

# ---------------------------------------------------------------------------
# Helpers to build a minimal BotApp that doesn't touch real services
# ---------------------------------------------------------------------------


def _make_config(tmp_path: Any) -> Config:
    """Build a Config whose media roots point into tmp_path."""
    movies = str(tmp_path / "movies")
    tv = str(tmp_path / "tv")
    spam = str(tmp_path / "spam")
    os.makedirs(movies, exist_ok=True)
    os.makedirs(tv, exist_ok=True)
    os.makedirs(spam, exist_ok=True)
    return Config(
        telegram_token="fake:token",
        allowed_user_ids={1},
        allow_group_chats=False,
        access_password="test",
        access_session_ttl_s=3600,
        vpn_required_for_downloads=False,
        vpn_service_name="",
        vpn_interface_name="",
        qbt_base_url="http://127.0.0.1:9999",
        qbt_username=None,
        qbt_password=None,
        tmdb_api_key=None,
        tmdb_region="US",
        plex_base_url=None,
        plex_token=None,
        db_path=str(tmp_path / "test.sqlite3"),
        page_size=5,
        search_timeout_s=30,
        poll_interval_s=1.0,
        search_early_exit_min_results=5,
        search_early_exit_idle_s=3.0,
        search_early_exit_max_wait_s=10.0,
        default_limit=10,
        default_sort="seeders",
        default_order="desc",
        default_min_quality=0,
        default_min_seeds=5,
        movies_category="movies",
        tv_category="tv",
        spam_category="spam",
        movies_path=movies,
        tv_path=tv,
        spam_path=spam,
        nvme_mount_path="",
        require_nvme_mount=False,
        patchy_chat_enabled=False,
        patchy_chat_name="Patchy",
        patchy_chat_model="",
        patchy_chat_fallback_model="",
        patchy_chat_timeout_s=30,
        patchy_chat_max_tokens=500,
        patchy_chat_temperature=0.7,
        patchy_chat_history_turns=5,
        patchy_llm_base_url=None,
        patchy_llm_api_key=None,
        progress_refresh_s=2.0,
        progress_edit_min_s=1.0,
        progress_smoothing_alpha=0.3,
        progress_track_timeout_s=300,
        backup_dir=None,
    )


def _make_bot(tmp_path: Any) -> BotApp:
    """Build a BotApp whose Plex client reports not-ready (skips Plex calls)."""
    cfg = _make_config(tmp_path)
    bot = BotApp(cfg)
    return bot


# ---------------------------------------------------------------------------
# Movie deletion guards
# ---------------------------------------------------------------------------


class TestMovieDeletion:
    """Tests for movies root_key — expects exactly depth 1 (one folder)."""

    def test_valid_movie_folder_is_deleted(self, tmp_path: Any) -> None:
        bot = _make_bot(tmp_path)
        movie_dir = tmp_path / "movies" / "Some Movie (2024)"
        movie_dir.mkdir()
        (movie_dir / "movie.mkv").write_text("data")

        result = bot._delete_remove_candidate(
            {
                "root_path": str(tmp_path / "movies"),
                "path": str(movie_dir),
                "root_key": "movies",
                "remove_kind": "movie",
            }
        )
        assert result["disk_status"] == "deleted"
        assert not movie_dir.exists()

    def test_path_traversal_dot_dot_is_rejected(self, tmp_path: Any) -> None:
        bot = _make_bot(tmp_path)
        # Create a target outside the media root
        escape_dir = tmp_path / "private_data"
        escape_dir.mkdir()
        traversal_path = str(tmp_path / "movies" / ".." / "private_data")

        with pytest.raises(RuntimeError, match="outside configured media roots"):
            bot._delete_remove_candidate(
                {
                    "root_path": str(tmp_path / "movies"),
                    "path": traversal_path,
                    "root_key": "movies",
                    "remove_kind": "movie",
                }
            )
        # Verify the directory was NOT deleted
        assert escape_dir.exists()

    def test_symlink_target_is_rejected(self, tmp_path: Any) -> None:
        bot = _make_bot(tmp_path)
        real_dir = tmp_path / "important"
        real_dir.mkdir()
        link_path = tmp_path / "movies" / "sneaky_link"
        link_path.symlink_to(real_dir)

        with pytest.raises(RuntimeError, match="symbolic links"):
            bot._delete_remove_candidate(
                {
                    "root_path": str(tmp_path / "movies"),
                    "path": str(link_path),
                    "root_key": "movies",
                    "remove_kind": "movie",
                }
            )
        assert real_dir.exists()

    def test_nested_movie_path_is_rejected(self, tmp_path: Any) -> None:
        """Movies must be exactly 1 level deep — a subfolder inside a movie dir is rejected."""
        bot = _make_bot(tmp_path)
        nested = tmp_path / "movies" / "SomeMovie" / "Extras"
        nested.mkdir(parents=True)

        with pytest.raises(RuntimeError, match="nested paths"):
            bot._delete_remove_candidate(
                {
                    "root_path": str(tmp_path / "movies"),
                    "path": str(nested),
                    "root_key": "movies",
                    "remove_kind": "movie",
                }
            )

    def test_root_path_itself_is_rejected(self, tmp_path: Any) -> None:
        """Trying to delete the media root itself must fail."""
        bot = _make_bot(tmp_path)
        movies_root = str(tmp_path / "movies")

        with pytest.raises(RuntimeError, match="nested paths"):
            bot._delete_remove_candidate(
                {
                    "root_path": movies_root,
                    "path": movies_root,
                    "root_key": "movies",
                    "remove_kind": "movie",
                }
            )


# ---------------------------------------------------------------------------
# Spam deletion guards (same rules as movies — depth 1)
# ---------------------------------------------------------------------------


class TestSpamDeletion:
    def test_valid_spam_folder_is_deleted(self, tmp_path: Any) -> None:
        bot = _make_bot(tmp_path)
        spam_dir = tmp_path / "spam" / "Junk.Torrent"
        spam_dir.mkdir()
        (spam_dir / "file.bin").write_text("data")

        result = bot._delete_remove_candidate(
            {
                "root_path": str(tmp_path / "spam"),
                "path": str(spam_dir),
                "root_key": "spam",
                "remove_kind": "spam",
            }
        )
        assert result["disk_status"] == "deleted"
        assert not spam_dir.exists()


# ---------------------------------------------------------------------------
# TV show deletion guards
# ---------------------------------------------------------------------------


class TestTVShowDeletion:
    """TV show removal (remove_kind='show') expects depth 1."""

    def test_valid_show_folder_is_deleted(self, tmp_path: Any) -> None:
        bot = _make_bot(tmp_path)
        show_dir = tmp_path / "tv" / "Breaking Bad"
        show_dir.mkdir()
        (show_dir / "s01e01.mkv").write_text("data")

        result = bot._delete_remove_candidate(
            {
                "root_path": str(tmp_path / "tv"),
                "path": str(show_dir),
                "root_key": "tv",
                "remove_kind": "show",
            }
        )
        assert result["disk_status"] == "deleted"
        assert not show_dir.exists()

    def test_nested_path_as_show_is_rejected(self, tmp_path: Any) -> None:
        bot = _make_bot(tmp_path)
        nested = tmp_path / "tv" / "Show" / "Season 1"
        nested.mkdir(parents=True)

        with pytest.raises(RuntimeError, match="outside a top-level TV series"):
            bot._delete_remove_candidate(
                {
                    "root_path": str(tmp_path / "tv"),
                    "path": str(nested),
                    "root_key": "tv",
                    "remove_kind": "show",
                }
            )


class TestTVSeasonDeletion:
    """TV season removal (remove_kind='season') expects depth 2."""

    def test_valid_season_folder_is_deleted(self, tmp_path: Any) -> None:
        bot = _make_bot(tmp_path)
        season_dir = tmp_path / "tv" / "Breaking Bad" / "Season 1"
        season_dir.mkdir(parents=True)
        (season_dir / "s01e01.mkv").write_text("data")

        result = bot._delete_remove_candidate(
            {
                "root_path": str(tmp_path / "tv"),
                "path": str(season_dir),
                "root_key": "tv",
                "remove_kind": "season",
            }
        )
        assert result["disk_status"] == "deleted"
        assert not season_dir.exists()

    def test_show_root_as_season_is_rejected(self, tmp_path: Any) -> None:
        """Depth 1 path with remove_kind='season' must be rejected."""
        bot = _make_bot(tmp_path)
        show_dir = tmp_path / "tv" / "Breaking Bad"
        show_dir.mkdir()

        with pytest.raises(RuntimeError, match="outside a direct season path"):
            bot._delete_remove_candidate(
                {
                    "root_path": str(tmp_path / "tv"),
                    "path": str(show_dir),
                    "root_key": "tv",
                    "remove_kind": "season",
                }
            )

    def test_episode_path_as_season_is_rejected(self, tmp_path: Any) -> None:
        """Depth 3 path with remove_kind='season' must be rejected."""
        bot = _make_bot(tmp_path)
        ep = tmp_path / "tv" / "Show" / "Season 1" / "s01e01.mkv"
        ep.parent.mkdir(parents=True)
        ep.write_text("data")

        with pytest.raises(RuntimeError, match="outside a direct season path"):
            bot._delete_remove_candidate(
                {
                    "root_path": str(tmp_path / "tv"),
                    "path": str(ep),
                    "root_key": "tv",
                    "remove_kind": "season",
                }
            )


class TestTVEpisodeDeletion:
    """TV episode removal (remove_kind='episode') expects depth 1-3, must be a file."""

    def test_valid_episode_file_depth_2_is_deleted(self, tmp_path: Any) -> None:
        bot = _make_bot(tmp_path)
        ep = tmp_path / "tv" / "Show" / "s01e01.mkv"
        ep.parent.mkdir(parents=True)
        ep.write_text("data")

        result = bot._delete_remove_candidate(
            {
                "root_path": str(tmp_path / "tv"),
                "path": str(ep),
                "root_key": "tv",
                "remove_kind": "episode",
            }
        )
        assert result["disk_status"] == "deleted"
        assert not ep.exists()

    def test_valid_episode_file_depth_3_is_deleted(self, tmp_path: Any) -> None:
        bot = _make_bot(tmp_path)
        ep = tmp_path / "tv" / "Show" / "Season 1" / "s01e01.mkv"
        ep.parent.mkdir(parents=True)
        ep.write_text("data")

        result = bot._delete_remove_candidate(
            {
                "root_path": str(tmp_path / "tv"),
                "path": str(ep),
                "root_key": "tv",
                "remove_kind": "episode",
            }
        )
        assert result["disk_status"] == "deleted"
        assert not ep.exists()

    def test_directory_as_episode_is_rejected(self, tmp_path: Any) -> None:
        """A directory cannot be deleted as an 'episode' — only files."""
        bot = _make_bot(tmp_path)
        ep_dir = tmp_path / "tv" / "Show" / "Season 1"
        ep_dir.mkdir(parents=True)

        with pytest.raises(RuntimeError, match="outside a direct episode path"):
            bot._delete_remove_candidate(
                {
                    "root_path": str(tmp_path / "tv"),
                    "path": str(ep_dir),
                    "root_key": "tv",
                    "remove_kind": "episode",
                }
            )

    def test_too_deep_episode_is_rejected(self, tmp_path: Any) -> None:
        """Depth 4+ must be rejected."""
        bot = _make_bot(tmp_path)
        deep = tmp_path / "tv" / "Show" / "Season 1" / "extras" / "bonus.mkv"
        deep.parent.mkdir(parents=True)
        deep.write_text("data")

        with pytest.raises(RuntimeError, match="outside a direct episode path"):
            bot._delete_remove_candidate(
                {
                    "root_path": str(tmp_path / "tv"),
                    "path": str(deep),
                    "root_key": "tv",
                    "remove_kind": "episode",
                }
            )


# ---------------------------------------------------------------------------
# Unsupported root key
# ---------------------------------------------------------------------------


class TestUnsupportedRootKey:
    def test_unknown_root_key_is_rejected(self, tmp_path: Any) -> None:
        bot = _make_bot(tmp_path)
        target = tmp_path / "movies" / "Whatever"
        target.mkdir()

        with pytest.raises(RuntimeError, match="Unsupported library root"):
            bot._delete_remove_candidate(
                {
                    "root_path": str(tmp_path / "movies"),
                    "path": str(target),
                    "root_key": "audiobooks",
                    "remove_kind": "audiobook",
                }
            )

    def test_unsupported_tv_remove_kind_is_rejected(self, tmp_path: Any) -> None:
        bot = _make_bot(tmp_path)
        target = tmp_path / "tv" / "Show"
        target.mkdir()

        with pytest.raises(RuntimeError, match="Unsupported TV removal type"):
            bot._delete_remove_candidate(
                {
                    "root_path": str(tmp_path / "tv"),
                    "path": str(target),
                    "root_key": "tv",
                    "remove_kind": "clip",
                }
            )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_nonexistent_target_is_rejected(self, tmp_path: Any) -> None:
        bot = _make_bot(tmp_path)
        ghost = str(tmp_path / "movies" / "Ghost Movie")

        with pytest.raises(RuntimeError, match="no longer exists"):
            bot._delete_remove_candidate(
                {
                    "root_path": str(tmp_path / "movies"),
                    "path": ghost,
                    "root_key": "movies",
                    "remove_kind": "movie",
                }
            )

    def test_empty_path_is_rejected(self, tmp_path: Any) -> None:
        bot = _make_bot(tmp_path)

        with pytest.raises(RuntimeError, match="Invalid removal target"):
            bot._delete_remove_candidate(
                {
                    "root_path": str(tmp_path / "movies"),
                    "path": "",
                    "root_key": "movies",
                    "remove_kind": "movie",
                }
            )

    def test_symlink_inside_movie_dir_still_allows_dir_delete(self, tmp_path: Any) -> None:
        """The symlink check is on the target path itself, not contents inside it.
        A movie folder that CONTAINS a symlink can still be deleted (rmtree handles it)."""
        bot = _make_bot(tmp_path)
        movie_dir = tmp_path / "movies" / "MovieWithLink"
        movie_dir.mkdir()
        (movie_dir / "movie.mkv").write_text("data")
        # symlink inside the directory — this is fine, only top-level symlink is blocked
        (movie_dir / "link.txt").symlink_to(movie_dir / "movie.mkv")

        result = bot._delete_remove_candidate(
            {
                "root_path": str(tmp_path / "movies"),
                "path": str(movie_dir),
                "root_key": "movies",
                "remove_kind": "movie",
            }
        )
        assert result["disk_status"] == "deleted"
