"""Infer priority labels from a natural-language prompt.

mode="rules" (default): keyword matching (KR+EN), no API key. Cheap and offline.
mode="llm": ask a model to classify — wire later for real understanding.

So the user can say "write a binary search in Rust" instead of "--priority coding".
Multiple matches are returned (the selector sums their weights); no match -> balanced.
"""
from __future__ import annotations

from .llm import LLMError, chat

# the closed set of priority labels the selector understands
_LABELS = ("coding", "cheap", "fast", "intelligence", "agentic", "balanced")

# priority label -> trigger keywords (substring match, KR + EN, lowercased for EN)
_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("coding", ("code", "coding", "program", "function", "bug", "debug", "refactor",
                "script", "algorithm", "api", "compile", "rust", "python", "java",
                "코드", "코딩", "프로그램", "함수", "버그", "디버그", "알고리즘", "리팩터", "구현")),
    ("cheap", ("cheap", "cheapest", "budget", "inexpensive", "low cost", "low-cost",
               "저렴", "싸게", "싼", "가성비", "최저가", "비용 아", "돈 아")),
    ("fast", ("fast", "fastest", "quick", "quickly", "realtime", "real-time", "latency",
              "빠르", "빨리", "신속", "속도", "실시간", "지연")),
    ("intelligence", ("complex", "hard", "difficult", "deep", "reasoning", "analyze",
                      "analysis", "strategy", "research", "think", "smart",
                      "복잡", "어려", "심층", "추론", "분석", "전략", "깊이", "고난도", "똑똑")),
    ("agentic", ("agent", "agentic", "tool use", "multi-step", "multistep", "workflow",
                 "autonomous", "plan the", "에이전트", "도구", "멀티스텝", "워크플로우", "자율", "여러 단계")),
]


_LLM_SYSTEM = (
    "You classify a user's request into buying priorities for choosing an AI model. "
    "Allowed labels: coding, cheap, fast, intelligence, agentic. "
    "Return ONLY the applicable labels as a comma-separated list, most important first. "
    "Return 'balanced' if none clearly apply. No prose, no explanation."
)


def _infer_llm(prompt: str) -> list[str]:
    """Classify via an LLM (understands intent, not just keywords). Raises LLMError."""
    raw = chat(prompt or "", system=_LLM_SYSTEM)
    picked = [tok.strip().lower() for tok in raw.replace("\n", ",").split(",")]
    matched = [p for p in picked if p in _LABELS and p != "balanced"]
    # de-dup, preserve LLM's priority order
    seen: set[str] = set()
    ordered = [m for m in matched if not (m in seen or seen.add(m))]
    return ordered or ["balanced"]


def infer_priorities(prompt: str, mode: str = "rules") -> list[str]:
    """Return priority labels inferred from the prompt. Falls back to ['balanced'].

    mode="rules" (default): offline keyword match. mode="llm": ask a model to
    classify intent; on any LLM failure (no key/network) it falls back to rules so
    the agent still runs offline.
    """
    if mode == "llm":
        try:
            return _infer_llm(prompt)
        except LLMError as e:
            print(f"[nl_priority: LLM unavailable ({e}); falling back to rules]")
            mode = "rules"
    if mode != "rules":
        raise ValueError(f"unknown mode: {mode!r}")

    low = (prompt or "").lower()
    matched = [label for label, kws in _RULES if any(kw in low for kw in kws)]
    return matched or ["balanced"]
