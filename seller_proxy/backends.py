"""Provider-agnostic inference backends for the x402 proxy seller.

Selected by env PROXY_BACKEND:
  mock           -> echo (no key, offline; default for Phase 2)
  ollama         -> local Ollama (free, http://localhost:11434)
  openrouter_free-> OpenRouter free-tier models (OPENROUTER_API_KEY)
  anthropic      -> Claude (ANTHROPIC_API_KEY)   [Phase 5 final test]
  openai         -> GPT (OPENAI_API_KEY)          [Phase 5 final test]

call_backend(body) takes an OpenAI-style chat body and returns assistant text.
"""
from __future__ import annotations

import os

import requests


def _last_user(body: dict) -> str:
    msgs = body.get("messages", [])
    return msgs[-1]["content"] if msgs else ""


def call_backend(body: dict) -> str:
    backend = os.environ.get("PROXY_BACKEND", "mock")
    if backend == "mock":
        return f"[mock-backend echo for {body.get('model','?')}] {_last_user(body)[:300]}"
    if backend == "ollama":
        return _ollama(body)
    if backend == "openrouter_free":
        return _openai_compatible(body, "https://openrouter.ai/api/v1/chat/completions",
                                  os.environ.get("OPENROUTER_API_KEY"))
    if backend == "openai":
        return _openai_compatible(body, "https://api.openai.com/v1/chat/completions",
                                  os.environ.get("OPENAI_API_KEY"))
    if backend == "anthropic":
        return _anthropic(body)
    raise ValueError(f"unknown PROXY_BACKEND: {backend}")


def _ollama(body: dict) -> str:
    r = requests.post("http://localhost:11434/api/chat",
                      json={"model": body.get("model", "llama3.2"),
                            "messages": body["messages"], "stream": False}, timeout=120)
    r.raise_for_status()
    return r.json()["message"]["content"]


def _openai_compatible(body: dict, url: str, key: str | None) -> str:
    if not key:
        raise RuntimeError(f"missing API key for {url}")
    r = requests.post(url, headers={"Authorization": f"Bearer {key}"},
                      json={"model": body["model"], "messages": body["messages"]}, timeout=120)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _anthropic(body: dict) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("missing ANTHROPIC_API_KEY")
    r = requests.post("https://api.anthropic.com/v1/messages",
                      headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                      json={"model": body["model"], "max_tokens": 1024,
                            "messages": body["messages"]}, timeout=120)
    r.raise_for_status()
    return r.json()["content"][0]["text"]
