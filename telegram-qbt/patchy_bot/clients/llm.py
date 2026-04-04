"""OpenAI-compatible LLM chat client for Patchy personality."""

from __future__ import annotations

import logging
from typing import Any

from ..utils import build_requests_session

LOG = logging.getLogger("qbtg")


class PatchyLLMClient:
    def __init__(self, base_url: str | None, api_key: str | None, timeout_s: int = 35):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key or ""
        self.timeout_s = timeout_s
        self.session = build_requests_session("qbtg-bot/patchy-chat", pool_connections=4, pool_maxsize=4)
        self._unsupported_models: set[str] = set()

    def ready(self) -> bool:
        return bool(self.base_url and self.api_key)

    @staticmethod
    def _extract_content(data: dict[str, Any]) -> str:
        choices = data.get("choices") if isinstance(data, dict) else None
        if not choices or not isinstance(choices, list):
            return ""
        msg = choices[0].get("message") if isinstance(choices[0], dict) else None
        if not isinstance(msg, dict):
            return ""
        content = msg.get("content")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    txt = item.get("text")
                    if isinstance(txt, str) and txt.strip():
                        parts.append(txt.strip())
            return "\n".join(parts).strip()
        return ""

    def chat(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        fallback_model: str | None,
        max_tokens: int,
        temperature: float,
    ) -> tuple[str, str]:
        if not self.ready():
            raise RuntimeError("Patchy chat model provider is not configured")

        models_to_try: list[str] = []
        for candidate in [model, fallback_model]:
            if not candidate:
                continue
            if candidate in models_to_try:
                continue
            if candidate in self._unsupported_models:
                continue
            models_to_try.append(candidate)
        if not models_to_try:
            # If everything was marked unsupported earlier, try fallback anyway.
            models_to_try = [fallback_model or model]

        last_error = "Patchy chat request failed"
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        for model_id in models_to_try:
            payload = {
                "model": model_id,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            try:
                r = self.session.post(url, headers=headers, json=payload, timeout=self.timeout_s)
            except Exception as e:
                last_error = f"model={model_id}: request error ({e})"
                continue

            if r.status_code >= 400:
                err_text = r.text[:400]
                low_err = err_text.lower()
                if r.status_code in {400, 404} and ("model not supported" in low_err or "invalid model" in low_err):
                    self._unsupported_models.add(model_id)
                last_error = f"model={model_id}: HTTP {r.status_code} {err_text}"
                continue

            try:
                data = r.json()
            except Exception:
                last_error = f"model={model_id}: invalid JSON response"
                continue

            content = self._extract_content(data)
            if content:
                return content, model_id

            last_error = f"model={model_id}: empty response"

        raise RuntimeError(last_error)

