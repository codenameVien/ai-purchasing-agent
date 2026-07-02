"""Tiny LLM client for the BUYER side (priority inference, delivery judging).

Separate from seller_proxy/backends.py on purpose: that module is the SELLER
fulfilling paid inference; this one is the buyer's own cheap reasoning (classify a
prompt, score an answer) and is NOT paid through x402 — it's local agent logic.

Provider is picked by env AGENT_LLM_BACKEND (default "gemini"), same OpenAI-compat
shape as the seller backends. Callers should catch LLMError and fall back to their
offline path (rules / heuristic) so the agent still runs with no key.
"""
from __future__ import annotations

import os

import requests

# backend -> (endpoint, api-key env, default model)
_PROVIDERS = {
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
               "GEMINI_API_KEY", "gemini-2.5-flash"),
    "openrouter": ("https://openrouter.ai/api/v1/chat/completions",
                   "OPENROUTER_API_KEY", "meta-llama/llama-3.3-70b-instruct:free"),
    "openai": ("https://api.openai.com/v1/chat/completions", "OPENAI_API_KEY", "gpt-4o-mini"),
}


class LLMError(RuntimeError):
    """Any failure reaching the buyer-side LLM (no key, network, bad response)."""


def chat(user: str, *, system: str | None = None, backend: str | None = None,
         model: str | None = None, timeout: int = 30) -> str:
    """One-shot chat completion, returns assistant text. Raises LLMError on failure."""
    backend = backend or os.environ.get("AGENT_LLM_BACKEND", "gemini")
    prov = _PROVIDERS.get(backend)
    if not prov:
        raise LLMError(f"unknown AGENT_LLM_BACKEND: {backend!r}")
    url, key_env, default_model = prov
    key = os.environ.get(key_env)
    if not key:
        raise LLMError(f"missing {key_env} for buyer-side LLM ({backend})")

    messages = ([{"role": "system", "content": system}] if system else []) + \
               [{"role": "user", "content": user}]
    try:
        r = requests.post(url, headers={"Authorization": f"Bearer {key}"},
                          json={"model": model or default_model, "messages": messages,
                                "temperature": 0}, timeout=timeout)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
    except (requests.RequestException, KeyError, IndexError, ValueError) as e:
        raise LLMError(f"buyer-side LLM call failed: {e}") from e
    if not isinstance(content, str):        # some providers return null content -> treat as failure
        raise LLMError(f"buyer-side LLM returned non-text content: {type(content).__name__}")
    return content
