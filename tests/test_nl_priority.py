"""NL priority inference (rules mode) — keyword prompts map to priority labels."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import agent.nl_priority as nlp
from agent.llm import LLMError
from agent.nl_priority import infer_priorities


def test_coding_prompt():
    assert "coding" in infer_priorities("Write a binary search in Rust")
    assert "coding" in infer_priorities("이 함수 버그 좀 디버그해줘")


def test_cheap_and_fast_combine():
    p = infer_priorities("빠르고 저렴하게 요약해줘")
    assert "fast" in p and "cheap" in p


def test_intelligence_prompt():
    assert "intelligence" in infer_priorities("이 복잡한 문제를 심층 분석해줘")


def test_no_match_defaults_balanced():
    assert infer_priorities("hello there") == ["balanced"]


def test_llm_mode_parses_labels(monkeypatch):
    # LLM returns a comma list; we keep only valid labels, in order, deduped
    monkeypatch.setattr(nlp, "chat", lambda *a, **k: "fast, cheap, cheap, bogus")
    assert infer_priorities("어떤 프롬프트", mode="llm") == ["fast", "cheap"]


def test_llm_mode_empty_falls_to_balanced(monkeypatch):
    monkeypatch.setattr(nlp, "chat", lambda *a, **k: "balanced")
    assert infer_priorities("x", mode="llm") == ["balanced"]


def test_llm_mode_falls_back_to_rules(monkeypatch):
    # no key / network error -> fall back to offline rules, agent still runs
    def boom(*a, **k):
        raise LLMError("no key")
    monkeypatch.setattr(nlp, "chat", boom)
    assert "coding" in infer_priorities("write a function in rust", mode="llm")


def test_llm_null_content_raises_llmerror(monkeypatch):
    # a provider returning content: null must surface as LLMError (so callers fall back),
    # not as an AttributeError from None.replace(...)
    import agent.llm as llm

    class _Resp:
        def raise_for_status(self): pass
        def json(self): return {"choices": [{"message": {"content": None}}]}

    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: _Resp())
    try:
        llm.chat("hi", backend="gemini")
    except LLMError:
        return
    raise AssertionError("expected LLMError on null content")
