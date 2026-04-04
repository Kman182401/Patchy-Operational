"""qBittorrent WebUI API client."""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

import requests

from ..utils import build_requests_session

LOG = logging.getLogger("qbtg")


class QBClient:
    def __init__(self, base_url: str, username: str | None, password: str | None):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.session = build_requests_session("qbtg-bot/3.1", pool_connections=4, pool_maxsize=4)
        self._lock = threading.Lock()
        self._authed = False

    def _login(self) -> None:
        if not self.username:
            self._authed = True
            return
        payload = {"username": self.username, "password": self.password or ""}
        try:
            r = self.session.post(f"{self.base_url}/api/v2/auth/login", data=payload, timeout=15)
        except requests.RequestException as e:
            raise RuntimeError(f"qBittorrent login request failed: {e}") from e
        if r.status_code != 200 or r.text.strip() != "Ok.":
            raise RuntimeError(f"qBittorrent login failed: HTTP {r.status_code} {r.text.strip()}")
        self._authed = True

    def _request(self, method: str, path: str, *, retry_auth: bool = True, **kwargs: Any) -> requests.Response:
        with self._lock:
            if not self._authed:
                self._login()
            try:
                r = self.session.request(method, f"{self.base_url}{path}", timeout=30, **kwargs)
            except requests.RequestException as e:
                raise RuntimeError(f"qBittorrent request failed for {path}: {e}") from e
            if r.status_code == 403 and retry_auth and self.username:
                self._authed = False
                self._login()
                try:
                    r = self.session.request(method, f"{self.base_url}{path}", timeout=30, **kwargs)
                except requests.RequestException as e:
                    raise RuntimeError(f"qBittorrent request failed for {path}: {e}") from e
            if r.status_code >= 400:
                raise RuntimeError(f"qBittorrent API error {r.status_code}: {r.text[:300]}")
            return r

    def search(
        self,
        query: str,
        *,
        plugin: str = "enabled",
        search_cat: str = "all",
        timeout_s: int = 90,
        poll_interval_s: float = 1.0,
        early_exit_min_results: int = 20,
        early_exit_idle_s: float = 2.5,
        early_exit_max_wait_s: float = 12.0,
    ) -> list[dict[str, Any]]:
        start = self._request(
            "POST",
            "/api/v2/search/start",
            data={"pattern": query, "plugins": plugin, "category": search_cat},
        )
        data = start.json()
        search_id = data.get("id")
        if search_id is None:
            raise RuntimeError(f"Search start failed: {start.text[:200]}")

        out: list[dict[str, Any]] = []
        offset = 0
        chunk = 200
        last_growth = time.time()

        def fetch_new_results() -> bool:
            nonlocal offset, last_growth
            grew = False
            while True:
                rows = self._request(
                    "GET",
                    "/api/v2/search/results",
                    params={"id": search_id, "limit": chunk, "offset": offset},
                ).json()
                results = rows.get("results", []) if isinstance(rows, dict) else []
                if not results:
                    break
                out.extend(results)
                offset += len(results)
                last_growth = time.time()
                grew = True
                if len(results) < chunk:
                    break
            return grew

        deadline = time.time() + timeout_s
        started_at = time.time()
        status = "Running"
        while time.time() < deadline:
            fetch_new_results()

            st = self._request("GET", "/api/v2/search/status", params={"id": search_id}).json()
            if st and isinstance(st, list):
                status = st[0].get("status", "Unknown")
            else:
                status = "Unknown"

            if status in {"Stopped", "Unknown"}:
                break

            elapsed_s = time.time() - started_at
            idle_s = time.time() - last_growth

            if len(out) > 0 and elapsed_s >= early_exit_max_wait_s:
                LOG.info(
                    "Search id=%s early exit after %.1fs with %d partial results",
                    search_id,
                    elapsed_s,
                    len(out),
                )
                break

            if early_exit_min_results > 0 and len(out) >= early_exit_min_results and idle_s >= early_exit_idle_s:
                LOG.info(
                    "Search id=%s early exit after %.1fs idle with %d results",
                    search_id,
                    idle_s,
                    len(out),
                )
                break

            time.sleep(poll_interval_s)

        # Final drain for anything that arrived between last poll and stop/timeout.
        fetch_new_results()

        try:
            self._request("POST", "/api/v2/search/delete", data={"id": search_id})
        except Exception:
            LOG.warning("Failed to delete search id=%s", search_id, exc_info=True)

        return out

    def add_url(
        self,
        url: str,
        *,
        category: str | None = None,
        savepath: str | None = None,
        paused: bool = False,
    ) -> str:
        payload: dict[str, Any] = {"urls": url, "paused": "true" if paused else "false"}
        if category:
            payload["category"] = category
        if savepath:
            payload["savepath"] = savepath
        r = self._request("POST", "/api/v2/torrents/add", data=payload)
        return r.text.strip()

    def list_categories(self) -> dict[str, dict[str, Any]]:
        r = self._request("GET", "/api/v2/torrents/categories")
        return r.json()

    def create_category(self, name: str, save_path: str | None = None) -> str:
        payload = {"category": name}
        if save_path is not None:
            payload["savePath"] = save_path
        r = self._request("POST", "/api/v2/torrents/createCategory", data=payload)
        return r.text.strip() or "Ok."

    def edit_category(self, name: str, save_path: str) -> str:
        payload = {"category": name, "savePath": save_path}
        r = self._request("POST", "/api/v2/torrents/editCategory", data=payload)
        return r.text.strip() or "Ok."

    def ensure_category(self, name: str, save_path: str) -> None:
        cats = self.list_categories()
        current = cats.get(name)
        if current is None:
            self.create_category(name, save_path)
            return
        current_path = str(current.get("savePath") or "").rstrip("/")
        desired = str(save_path).rstrip("/")
        if current_path != desired:
            self.edit_category(name, save_path)

    def list_active(self, limit: int = 10) -> list[dict[str, Any]]:
        r = self._request(
            "GET",
            "/api/v2/torrents/info",
            params={"filter": "active", "sort": "dlspeed", "reverse": "true", "limit": limit},
        )
        return r.json() if r.text.strip() else []

    def get_transfer_info(self) -> dict[str, Any]:
        r = self._request("GET", "/api/v2/transfer/info")
        return r.json()

    def get_preferences(self) -> dict[str, Any]:
        r = self._request("GET", "/api/v2/app/preferences")
        return r.json()

    def set_preferences(self, prefs: dict[str, Any]) -> None:
        self._request("POST", "/api/v2/app/setPreferences", data={"json": json.dumps(prefs)})

    def get_torrent(self, torrent_hash: str) -> dict[str, Any] | None:
        if not torrent_hash:
            return None
        r = self._request("GET", "/api/v2/torrents/info", params={"hashes": torrent_hash})
        rows = r.json() if r.text.strip() else []
        if not rows:
            return None
        return rows[0]

    def delete_torrent(self, torrent_hash: str, *, delete_files: bool = True) -> None:
        self._request("POST", "/api/v2/torrents/delete", data={"hashes": torrent_hash, "deleteFiles": str(delete_files).lower()})

    def list_torrents(
        self,
        *,
        filter_name: str = "all",
        category: str | None = None,
        sort: str = "added_on",
        reverse: bool = True,
        limit: int = 200,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "filter": filter_name,
            "sort": sort,
            "reverse": "true" if reverse else "false",
            "limit": limit,
            "offset": offset,
        }
        if category:
            params["category"] = category
        r = self._request("GET", "/api/v2/torrents/info", params=params)
        return r.json() if r.text.strip() else []

    def list_search_plugins(self) -> list[dict[str, Any]]:
        r = self._request("GET", "/api/v2/search/plugins")
        return r.json() if r.text.strip() else []

