"""TVMaze + TMDB metadata client for schedule tracking."""

from __future__ import annotations

import logging
from typing import Any

import requests

from ..utils import (
    build_requests_session,
    episode_code,
    normalize_title,
    parse_release_ts,
    strip_summary_html,
)

LOG = logging.getLogger("qbtg")


class TVMetadataClient:
    def __init__(self, tmdb_api_key: str | None, timeout_s: int = 15):
        self.tmdb_api_key = tmdb_api_key or ""
        self.timeout_s = timeout_s
        self.session = build_requests_session("qbtg-bot/schedule", pool_connections=4, pool_maxsize=4)

    def _get_json(self, url: str, *, params: dict[str, Any] | None = None) -> Any:
        try:
            r = self.session.get(url, params=params, timeout=self.timeout_s)
        except requests.RequestException as e:
            raise RuntimeError(f"TV metadata request failed: {e}") from e
        if r.status_code >= 400:
            raise RuntimeError(f"TV metadata request failed: HTTP {r.status_code} {r.text[:240]}")
        try:
            return r.json()
        except ValueError as e:
            raise RuntimeError("TV metadata request failed: invalid JSON response") from e

    @staticmethod
    def _show_card(show: dict[str, Any]) -> dict[str, Any]:
        premiered = str(show.get("premiered") or "")
        year = int(premiered[:4]) if len(premiered) >= 4 and premiered[:4].isdigit() else None
        net = show.get("network") or show.get("webChannel") or {}
        network = str(net.get("name") or "") if isinstance(net, dict) else ""
        country = ""
        if isinstance(net, dict):
            country_meta = net.get("country") or {}
            if isinstance(country_meta, dict):
                country = str(country_meta.get("code") or country_meta.get("name") or "")
        externals = show.get("externals") or {}
        return {
            "id": int(show.get("id") or 0),
            "name": str(show.get("name") or "Unknown show").strip(),
            "year": year,
            "premiered": premiered,
            "status": str(show.get("status") or "Unknown").strip() or "Unknown",
            "network": network,
            "country": country,
            "summary": strip_summary_html(str(show.get("summary") or "")),
            "genres": list(show.get("genres") or []),
            "language": str(show.get("language") or ""),
            "url": str(show.get("url") or ""),
            "imdb_id": str(externals.get("imdb") or "").strip() or None,
            "tmdb_id": None,
        }

    def search_shows(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        rows = self._get_json("https://api.tvmaze.com/search/shows", params={"q": query})
        out: list[dict[str, Any]] = []
        for item in rows or []:
            show = item.get("show") if isinstance(item, dict) else None
            if not isinstance(show, dict):
                continue
            card = self._show_card(show)
            if card["id"] <= 0:
                continue
            out.append(card)
            if len(out) >= max(1, limit):
                break
        return out

    def _lookup_tmdb_id(self, name: str, year: int | None) -> int | None:
        if not self.tmdb_api_key:
            return None
        params: dict[str, Any] = {"api_key": self.tmdb_api_key, "query": name}
        if year:
            params["first_air_date_year"] = year
        try:
            data = self._get_json("https://api.themoviedb.org/3/search/tv", params=params)
        except Exception:
            return None
        best_id: int | None = None
        best_score = -1
        target = normalize_title(name)
        for row in list(data.get("results") or [])[:8]:
            candidate_name = str(row.get("name") or row.get("original_name") or "")
            candidate_norm = normalize_title(candidate_name)
            score = 0
            if candidate_norm == target:
                score += 5
            elif candidate_norm and candidate_norm in target:
                score += 2
            first_air = str(row.get("first_air_date") or "")
            if year and len(first_air) >= 4 and first_air[:4].isdigit() and int(first_air[:4]) == year:
                score += 3
            if score > best_score:
                best_score = score
                try:
                    best_id = int(row.get("id") or 0) or None
                except Exception:
                    best_id = None
        return best_id

    def get_show_bundle(self, show_id: int, *, lookup_tmdb: bool = False) -> dict[str, Any]:
        show = self._get_json(
            f"https://api.tvmaze.com/shows/{int(show_id)}",
            params={"embed": "episodeswithspecials"},
        )
        embedded = show.get("_embedded") or {}
        episodes = embedded.get("episodeswithspecials") or embedded.get("episodes") or []
        bundle = self._show_card(show)
        bundle["genres"] = list(show.get("genres") or [])
        bundle["language"] = str(show.get("language") or bundle.get("language") or "")
        bundle["runtime"] = int(show.get("runtime") or 0) if str(show.get("runtime") or "").isdigit() else 0
        bundle["official_site"] = str(show.get("officialSite") or "")
        bundle["schedule"] = show.get("schedule") or {}
        bundle["tmdb_id"] = self._lookup_tmdb_id(bundle["name"], bundle.get("year")) if lookup_tmdb else None
        parsed_episodes: list[dict[str, Any]] = []
        available_seasons: set[int] = set()
        for episode in episodes or []:
            if not isinstance(episode, dict):
                continue
            season = int(episode.get("season") or 0)
            number = episode.get("number")
            if season > 0 and number is not None:
                try:
                    available_seasons.add(int(season))
                except Exception:
                    pass
            ep_number = int(number) if isinstance(number, int) or str(number).isdigit() else None
            parsed_episodes.append(
                {
                    "season": season,
                    "number": ep_number,
                    "code": episode_code(season, ep_number) if season > 0 and ep_number is not None else None,
                    "name": str(episode.get("name") or "").strip(),
                    "airdate": str(episode.get("airdate") or "").strip(),
                    "airstamp": str(episode.get("airstamp") or "").strip(),
                    "air_ts": parse_release_ts(
                        str(episode.get("airstamp") or "").strip() or None,
                        str(episode.get("airdate") or "").strip() or None,
                    ),
                }
            )
        bundle["episodes"] = parsed_episodes
        bundle["available_seasons"] = sorted(s for s in available_seasons if s > 0)
        return bundle

