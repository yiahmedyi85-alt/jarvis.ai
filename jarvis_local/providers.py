from __future__ import annotations
import json, os, urllib.request

class GeminiProvider:
    def __init__(self):
        self.key=os.getenv("GEMINI_API_KEY")
        self.model=os.getenv("JARVIS_LLM_MODEL","gemini-2.5-flash")
    def chat(self,text):
        if not self.key: raise RuntimeError("AI provider is not configured. Set GEMINI_API_KEY.")
        body=json.dumps({"contents":[{"parts":[{"text":text}]}]}).encode()
        req=urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.key}",data=body,headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req,timeout=45) as r: data=json.load(r)
        return data["candidates"][0]["content"]["parts"][0]["text"]
