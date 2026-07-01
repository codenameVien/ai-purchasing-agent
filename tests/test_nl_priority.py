"""NL priority inference (rules mode) — keyword prompts map to priority labels."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

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


def test_llm_mode_stub():
    try:
        infer_priorities("x", mode="llm")
    except NotImplementedError:
        return
    raise AssertionError("expected NotImplementedError for llm mode")
