"""Minimal OpenRouter chat client (OpenAI-compatible). Returns None when no key is configured,
so every caller has a deterministic fallback and the app still works without an LLM."""
from __future__ import annotations

import json
import urllib.request

from app.settings import get_settings

URL = "https://openrouter.ai/api/v1/chat/completions"


def chat(system: str, user: str, temperature: float = 0.1, max_tokens: int = 700, json_mode: bool = False) -> str | None:
    s = get_settings()
    if not s.openrouter_api_key:
        return None
    body = {"model": s.llm_model, "temperature": temperature, "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={
        "Authorization": f"Bearer {s.openrouter_api_key}", "Content-Type": "application/json",
        "X-Title": "NeighborHealth"})
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return json.loads(resp.read())["choices"][0]["message"]["content"]
    except Exception:
        return None
