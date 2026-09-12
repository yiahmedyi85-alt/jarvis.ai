from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    capability: str
    api_key: str
    model: str
    base_url: str = ""


class LLMProvider(Protocol):
    def chat(self, text: str, memory=None) -> str: ...


class ProviderError(RuntimeError):
    pass


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


class GeminiProvider:
    """Gemini text provider. Secrets are read only on the local backend."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or _env("GEMINI_API_KEY")
        self.model = model or _env("JARVIS_LLM_MODEL", "gemini-2.5-flash")

    def chat(self, text: str, memory=None) -> str:
        if not self.api_key:
            return "Gemini is not configured. Add GEMINI_API_KEY to your local .env file."
        prompt = text
        if memory:
            prompt = "Local memory:\n" + json.dumps(memory[-20:], ensure_ascii=False) + "\n\nUser:\n" + text
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        body = {"contents": [{"parts": [{"text": prompt}]}]}
        request = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as exc:
            raise ProviderError(f"Gemini request failed: {exc}") from exc


class CapabilityProvider:
    """Configuration holder for specialized providers.

    Specialized capabilities are deliberately not exposed to the browser. Concrete
    adapters can be added without changing the orchestrator or UI.
    """

    def __init__(self, config: ProviderConfig):
        self.config = config

    @property
    def configured(self) -> bool:
        return bool(self.config.api_key)


class ProviderRegistry:
    def __init__(self):
        self._providers: dict[str, CapabilityProvider] = {
            "conversation": CapabilityProvider(ProviderConfig("gemini", "conversation", _env("GEMINI_API_KEY"), _env("JARVIS_LLM_MODEL", "gemini-2.5-flash"))),
            "vision": CapabilityProvider(ProviderConfig(_env("JARVIS_VISION_PROVIDER", "gemini"), "vision", _env("JARVIS_VISION_API_KEY", _env("GEMINI_API_KEY")), _env("JARVIS_VISION_MODEL", "gemini-2.5-flash"))),
            "image_generation": CapabilityProvider(ProviderConfig(_env("JARVIS_IMAGE_PROVIDER", ""), "image_generation", _env("JARVIS_IMAGE_API_KEY"), _env("JARVIS_IMAGE_MODEL", ""))),
            "file_analysis": CapabilityProvider(ProviderConfig(_env("JARVIS_FILE_PROVIDER", "gemini"), "file_analysis", _env("JARVIS_FILE_API_KEY", _env("GEMINI_API_KEY")), _env("JARVIS_FILE_MODEL", "gemini-2.5-flash"))),
        }

    def get(self, capability: str) -> CapabilityProvider:
        if capability not in self._providers:
            raise ProviderError(f"Unknown capability: {capability}")
        return self._providers[capability]

    def status(self) -> dict[str, Any]:
        return {key: {"provider": value.config.name, "model": value.config.model, "configured": value.configured} for key, value in self._providers.items()}


registry = ProviderRegistry()
