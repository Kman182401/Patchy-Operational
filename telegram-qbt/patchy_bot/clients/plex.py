"""Plex Media Server inventory and library management client."""

from __future__ import annotations

import logging
import os
import time
from typing import Any
from xml.etree import ElementTree as ET

import requests

from ..utils import build_requests_session, episode_code, normalize_title

LOG = logging.getLogger("qbtg")


class PlexInventoryClient:
    def __init__(self, base_url: str | None, token: str | None, tv_root: str, timeout_s: int = 12):
        self.base_url = (base_url or "").rstrip("/")
        self.token = token or ""
        self.tv_root = tv_root
        self.timeout_s = timeout_s
        self.session = build_requests_session("qbtg-bot/plex", pool_connections=4, pool_maxsize=4)
        self._section_key: str | None = None

    def ready(self) -> bool:
        return bool(self.base_url and self.token)

    def _request(self, method: str, path: str, *, params: dict[str, Any] | None = None) -> requests.Response:
        if not self.ready():
            raise RuntimeError("Plex inventory is not configured")
        qp = dict(params or {})
        headers = {"X-Plex-Token": self.token}
        try:
            r = self.session.request(method.upper(), f"{self.base_url}{path}", params=qp, headers=headers, timeout=self.timeout_s)
        except requests.RequestException as e:
            raise RuntimeError(f"Plex API request failed: {e}") from e
        if r.status_code >= 400:
            raise RuntimeError(f"Plex API error {r.status_code}: {r.text[:240]}")
        return r

    def _get_xml(self, path: str, *, params: dict[str, Any] | None = None) -> ET.Element:
        r = self._request("GET", path, params=params)
        try:
            return ET.fromstring(r.text or "<MediaContainer />")
        except ET.ParseError as e:
            raise RuntimeError("Plex API returned invalid XML") from e

    @staticmethod
    def _norm_media_path(path: str) -> str:
        return os.path.normpath(str(path or "").strip())

    @classmethod
    def _path_matches_remove_target(cls, candidate_path: str, target_path: str, remove_kind: str) -> bool:
        candidate = cls._norm_media_path(candidate_path)
        target = cls._norm_media_path(target_path)
        if not candidate or not target:
            return False
        if remove_kind == "episode":
            return candidate == target
        return candidate == target or candidate.startswith(target + os.sep)

    def _metadata_exists(self, rating_key: str) -> bool:
        if not str(rating_key or "").strip():
            return False
        try:
            self._request("GET", f"/library/metadata/{str(rating_key).strip()}")
        except RuntimeError as e:
            if "Plex API error 404" in str(e):
                return False
            raise
        return True

    def _tv_section(self) -> str | None:
        if self._section_key:
            return self._section_key
        root = self._get_xml("/library/sections")
        fallback: str | None = None
        want = os.path.normpath(self.tv_root)
        for directory in root.findall(".//Directory"):
            if str(directory.attrib.get("type") or "") != "show":
                continue
            key = str(directory.attrib.get("key") or "").strip()
            if key and fallback is None:
                fallback = key
            for location in directory.findall("./Location"):
                location_path = os.path.normpath(str(location.attrib.get("path") or "").strip())
                if location_path and (location_path == want or want.startswith(location_path) or location_path.startswith(want)):
                    self._section_key = key
                    return key
        self._section_key = fallback
        return fallback

    def episode_inventory(self, show_name: str, year: int | None = None) -> tuple[set[str], str]:
        section_key = self._tv_section()
        if not section_key:
            raise RuntimeError("No Plex TV library section was found")
        root = self._get_xml(f"/library/sections/{section_key}/all", params={"type": 2, "title": show_name})
        candidates: list[tuple[int, str]] = []
        want = normalize_title(show_name)
        for meta in root.findall(".//*[@ratingKey]"):
            media_type = str(meta.attrib.get("type") or "")
            if media_type and media_type != "show":
                continue
            rating_key = str(meta.attrib.get("ratingKey") or "").strip()
            title = str(meta.attrib.get("title") or "").strip()
            title_norm = normalize_title(title)
            score = 0
            if title_norm == want:
                score += 6
            elif want and want in title_norm:
                score += 3
            elif title_norm and title_norm in want:
                score += 2
            candidate_year = str(meta.attrib.get("year") or "").strip()
            if year and candidate_year.isdigit() and int(candidate_year) == year:
                score += 3
            if rating_key:
                candidates.append((score, rating_key))
        if not candidates:
            return set(), "plex (show not found; falling back)"
        rating_key = sorted(candidates, reverse=True)[0][1]
        leaves = self._get_xml(f"/library/metadata/{rating_key}/allLeaves")
        found: set[str] = set()
        for meta in leaves.findall(".//*[@parentIndex][@index]"):
            parent_index = str(meta.attrib.get("parentIndex") or "").strip()
            ep_index = str(meta.attrib.get("index") or "").strip()
            if not parent_index.isdigit() or not ep_index.isdigit():
                continue
            found.add(episode_code(int(parent_index), int(ep_index)))
        return found, "plex"

    def _sections(self) -> list[dict[str, Any]]:
        root = self._get_xml("/library/sections")
        sections: list[dict[str, Any]] = []
        for directory in root.findall(".//Directory"):
            key = str(directory.attrib.get("key") or "").strip()
            if not key:
                continue
            locations = []
            for location in directory.findall("./Location"):
                location_path = os.path.normpath(str(location.attrib.get("path") or "").strip())
                if location_path:
                    locations.append(location_path)
            sections.append(
                {
                    "key": key,
                    "title": str(directory.attrib.get("title") or "").strip(),
                    "type": str(directory.attrib.get("type") or "").strip(),
                    "locations": locations,
                    "refreshing": str(directory.attrib.get("refreshing") or "").strip() in {"1", "true", "True"},
                }
            )
        return sections

    @staticmethod
    def _parts_for_meta(meta: ET.Element) -> list[str]:
        files: list[str] = []
        for part in meta.findall(".//Part"):
            raw = str(part.attrib.get("file") or "").strip()
            if raw:
                files.append(os.path.normpath(raw))
        return files

    def _movie_identity_for_path(self, section_key: str, target_path: str) -> dict[str, Any] | None:
        root = self._get_xml(f"/library/sections/{section_key}/all", params={"type": 1})
        for meta in root.findall(".//*[@ratingKey]"):
            rating_key = str(meta.attrib.get("ratingKey") or "").strip()
            if not rating_key:
                continue
            part_files = self._parts_for_meta(meta)
            if any(self._path_matches_remove_target(path, target_path, "movie") for path in part_files):
                return {
                    "section_key": section_key,
                    "primary_rating_key": rating_key,
                    "rating_keys": [rating_key],
                    "title": str(meta.attrib.get("title") or "").strip() or os.path.basename(target_path),
                    "verification_mode": "rating_keys",
                }
        return None

    def _tv_identity_for_path(self, section_key: str, target_path: str, remove_kind: str) -> dict[str, Any] | None:
        root = self._get_xml(f"/library/sections/{section_key}/all", params={"type": 2})
        for meta in root.findall(".//*[@ratingKey]"):
            show_rating_key = str(meta.attrib.get("ratingKey") or "").strip()
            if not show_rating_key:
                continue
            leaves = self._get_xml(f"/library/metadata/{show_rating_key}/allLeaves")
            matching_leaf_keys: list[str] = []
            saw_match = False
            for leaf in leaves.findall(".//*[@ratingKey]"):
                leaf_key = str(leaf.attrib.get("ratingKey") or "").strip()
                part_files = self._parts_for_meta(leaf)
                if any(self._path_matches_remove_target(path, target_path, remove_kind) for path in part_files):
                    saw_match = True
                    if leaf_key:
                        matching_leaf_keys.append(leaf_key)
            if not saw_match:
                continue
            title = str(meta.attrib.get("title") or "").strip() or os.path.basename(target_path)
            if remove_kind == "show":
                return {
                    "section_key": section_key,
                    "primary_rating_key": show_rating_key,
                    "rating_keys": [show_rating_key],
                    "title": title,
                    "verification_mode": "show",
                }
            return {
                "section_key": section_key,
                "primary_rating_key": matching_leaf_keys[0] if matching_leaf_keys else show_rating_key,
                "rating_keys": matching_leaf_keys,
                "title": title,
                "verification_mode": "rating_keys",
            }
        return None

    def resolve_remove_identity(self, media_path: str, remove_kind: str) -> dict[str, Any]:
        best, scan_path = self._section_for_path(media_path)
        section_key = str(best.get("key") or "").strip()
        section_type = str(best.get("type") or "").strip().lower()
        identity: dict[str, Any] | None = None
        if section_type == "movie":
            identity = self._movie_identity_for_path(section_key, media_path)
        elif section_type == "show":
            identity = self._tv_identity_for_path(section_key, media_path, remove_kind)
        if identity is None:
            identity = {
                "section_key": section_key,
                "primary_rating_key": None,
                "rating_keys": [],
                "title": os.path.basename(str(media_path or "").rstrip(os.sep)) or str(best.get("title") or "item"),
                "verification_mode": "path_fallback",
            }
        identity["scan_path"] = scan_path
        return identity

    def _section_for_path(self, media_path: str) -> tuple[dict[str, Any], str]:
        target = os.path.normpath(str(media_path or "").strip())
        if not target:
            raise RuntimeError("Missing media path for Plex refresh")
        best: dict[str, Any] | None = None
        best_location = ""
        best_len = -1
        for section in self._sections():
            for location in list(section.get("locations") or []):
                if not location:
                    continue
                if target == location or target.startswith(location + os.sep) or location.startswith(target + os.sep):
                    if len(location) > best_len:
                        best = section
                        best_location = location
                        best_len = len(location)
        if not best:
            raise RuntimeError("No Plex library section matched the deleted path")
        scan_path = target
        while scan_path != best_location and not os.path.exists(scan_path):
            parent = os.path.dirname(scan_path)
            if not parent or parent == scan_path:
                scan_path = best_location
                break
            scan_path = parent
        try:
            if os.path.commonpath([scan_path, best_location]) != best_location:
                scan_path = best_location
        except ValueError:
            scan_path = best_location
        return best, scan_path

    def _wait_for_section_idle(self, section_key: str, *, timeout_s: int = 45, poll_s: float = 1.0, min_wait_s: float = 3.0) -> bool:
        deadline = time.monotonic() + max(2.0, float(timeout_s))
        checks = 0
        first_not_refreshing_at: float | None = None
        observed_refresh = False
        while True:
            checks += 1
            section = next((item for item in self._sections() if str(item.get("key") or "") == section_key), None)
            if section is None:
                return True
            refreshing = bool(section.get("refreshing"))
            if refreshing:
                observed_refresh = True
                first_not_refreshing_at = None
            else:
                if first_not_refreshing_at is None:
                    first_not_refreshing_at = time.monotonic()
                waited_long_enough = (time.monotonic() - first_not_refreshing_at) >= max(0.5, float(min_wait_s))
                if (observed_refresh or checks >= 4) and waited_long_enough:
                    return True
            if time.monotonic() >= deadline:
                return not refreshing
            time.sleep(min(max(0.1, poll_s), max(0.1, deadline - time.monotonic())))

    def refresh_for_path(self, media_path: str) -> str:
        best, scan_path = self._section_for_path(media_path)
        self._request("POST", f"/library/sections/{best['key']}/refresh", params={"path": scan_path})
        title = str(best.get("title") or best.get("type") or best.get("key") or "library")
        return f"Plex scan triggered for {title}"

    def purge_deleted_path(self, media_path: str) -> str:
        best, scan_path = self._section_for_path(media_path)
        section_key = str(best.get("key") or "").strip()
        title = str(best.get("title") or best.get("type") or section_key or "library")
        self._request("POST", f"/library/sections/{section_key}/refresh", params={"path": scan_path})
        if not self._wait_for_section_idle(section_key):
            raise RuntimeError(f"Plex scan did not finish before timeout for {title}")
        self._request("PUT", f"/library/sections/{section_key}/emptyTrash")
        return f"Plex scan and trash empty completed for {title}"

    def refresh_all_by_type(self, section_types: list[str]) -> list[str]:
        """Refresh + emptyTrash on every Plex section whose type matches section_types.

        Used as a fallback when the target path cannot be matched to a specific
        section. Returns a list of section titles that were refreshed.
        """
        types = {str(t).lower() for t in section_types}
        refreshed: list[str] = []
        for section in self._sections():
            if str(section.get("type") or "").lower() not in types:
                continue
            key = str(section.get("key") or "").strip()
            if not key:
                continue
            title = str(section.get("title") or key)
            self._request("POST", f"/library/sections/{key}/refresh")
            idle = self._wait_for_section_idle(key, timeout_s=30, min_wait_s=3.0)
            if idle:
                self._request("PUT", f"/library/sections/{key}/emptyTrash")
            refreshed.append(title)
        return refreshed

    def verify_remove_identity_absent(self, target_path: str, remove_kind: str, verification: dict[str, Any] | None) -> tuple[bool, str]:
        data = dict(verification or {})
        mode = str(data.get("verification_mode") or "path_fallback")
        rating_keys = [str(x).strip() for x in list(data.get("rating_keys") or []) if str(x).strip()]
        title = str(data.get("title") or os.path.basename(str(target_path or "").rstrip(os.sep)) or "item")
        if mode == "show" and rating_keys:
            if not self._metadata_exists(rating_keys[0]):
                return True, f"Plex metadata removed for {title}"
            return False, f"Plex still has show metadata for {title}"
        if mode == "rating_keys" and rating_keys:
            remaining = [rk for rk in rating_keys if self._metadata_exists(rk)]
            if not remaining:
                return True, f"Plex metadata removed for {title}"
            return False, f"Plex still has {len(remaining)} metadata item(s) for {title}"
        section_key = str(data.get("section_key") or "").strip()
        if not section_key:
            # No section key — scan all movie and show sections for the target path.
            for section in self._sections():
                sec_key = str(section.get("key") or "").strip()
                sec_type = str(section.get("type") or "").strip().lower()
                if not sec_key:
                    continue
                if sec_type == "movie":
                    root = self._get_xml(f"/library/sections/{sec_key}/all", params={"type": 1})
                    for meta in root.findall(".//*[@ratingKey]"):
                        if any(
                            self._path_matches_remove_target(path, target_path, remove_kind)
                            for path in self._parts_for_meta(meta)
                        ):
                            return False, f"Plex still has media parts for {title}"
                elif sec_type == "show":
                    # type=4 fetches all episodes directly — one request instead of one per show
                    root = self._get_xml(f"/library/sections/{sec_key}/all", params={"type": 4})
                    for meta in root.findall(".//*[@ratingKey]"):
                        if any(self._path_matches_remove_target(path, target_path, remove_kind) for path in self._parts_for_meta(meta)):
                            return False, f"Plex still has media parts for {title}"
            return True, f"Plex media parts removed for {title} (all-section scan)"
        section_type = next((str(item.get("type") or "").strip().lower() for item in self._sections() if str(item.get("key") or "") == section_key), "")
        if section_type == "movie":
            root = self._get_xml(f"/library/sections/{section_key}/all", params={"type": 1})
            for meta in root.findall(".//*[@ratingKey]"):
                if any(self._path_matches_remove_target(path, target_path, "movie") for path in self._parts_for_meta(meta)):
                    return False, f"Plex still has media parts for {title}"
            return True, f"Plex media parts removed for {title}"
        if section_type == "show":
            root = self._get_xml(f"/library/sections/{section_key}/all", params={"type": 2})
            for meta in root.findall(".//*[@ratingKey]"):
                show_rating_key = str(meta.attrib.get("ratingKey") or "").strip()
                if not show_rating_key:
                    continue
                leaves = self._get_xml(f"/library/metadata/{show_rating_key}/allLeaves")
                for leaf in leaves.findall(".//*[@ratingKey]"):
                    if any(self._path_matches_remove_target(path, target_path, remove_kind) for path in self._parts_for_meta(leaf)):
                        return False, f"Plex still has media parts for {title}"
            return True, f"Plex media parts removed for {title}"
        return False, f"Unsupported Plex section type for {title}"

