from __future__ import annotations
import json, os, urllib.request
from typing import Protocol

class LLMProvider(Protocol):
    def chat(self, text: str, memory=None) -> str: ...

class GeminiProvider:
    name = "Gemini"
    def __init__(self):
        self.key = os.getenv("GEMINI_API_KEY")
        self.model = os.getenv("JARVIS_LLM_MODEL", "gemini-2.5-flash")
    def chat(self, text: str, memory=None) -> str:
        if not self.key:
            raise RuntimeError("AI provider is not configured. Set GEMINI_API_KEY in your local environment.")
        mem = "\n".join(x.get("text", "") for x in (memory or [])[-10:])
        system = ("You are JARVIS, a local-first desktop assistant. Be concise and useful. "
                  "Never claim that a computer action happened unless a local tool returned success. "
                  "Private files stay local unless the user explicitly requests an external service.")
        if mem: system += "\nLocal non-sensitive memory:\n" + mem
        body = json.dumps({"systemInstruction":{"parts":[{"text":system}]},"contents":[{"role":"user","parts":[{"text":text}]}]}).encode()
        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.key}",
            data=body, headers={"Content-Type":"application/json"})
        try:
            with urllib.request.urlopen(req, timeout=45) as r: data=json.load(r)
        except Exception as exc:
            raise RuntimeError(f"LLM request failed: {exc}") from exc
        try: return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as exc: raise RuntimeError("LLM returned no usable response") from exc
