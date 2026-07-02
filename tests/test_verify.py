"""Objective verification (ROADMAP G) — ground-truth checks for verifiable tasks."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agent.judge import judge
from agent.verify import verify


def test_python_compiles_is_good():
    score, label, _ = verify("write a python function",
                             "```python\ndef add(a, b):\n    return a + b\n```")
    assert label == "good" and score == 1.0


def test_python_syntax_error_is_bad():
    score, label, reasons = verify("write a python function",
                                  "```python\ndef add(a, b)\n    return a+b\n```")
    assert label == "bad" and score == 0.0
    assert any("compile" in r for r in reasons)


def test_arithmetic_correct():
    score, label, _ = verify("what is 12 * 8?", "It is 96.")
    assert label == "good" and score == 1.0


def test_arithmetic_wrong():
    score, label, reasons = verify("what is 12 * 8?", "The answer is 100.")
    assert label == "bad" and any("expected" in r for r in reasons)


def test_coding_prompt_with_numbers_not_hijacked():
    # "add 2 + 3" is a CODE task; ground truth = the code compiles, not that prose says "5"
    score, label, _ = verify("write a python function to add 2 + 3",
                             "```python\ndef add():\n    return 2 + 3\n```")
    assert label == "good" and score == 1.0


def test_arithmetic_float_normalized():
    # 0.1 + 0.2 must accept "0.3", not demand "0.30000000000000004"
    score, label, _ = verify("what is 0.1 + 0.2?", "0.3")
    assert label == "good" and score == 1.0


def test_arithmetic_ignores_irrelevant_numbers():
    # expected result is the STATED (last) number, not any number appearing anywhere
    _, label, _ = verify("what is 3 * 3?", "I ate 9 cookies but the result is 25")
    assert label == "bad"


def test_non_verifiable_returns_none():
    # an open-ended prose task is not objectively checkable
    assert verify("write a poem about the sea", "The sea is deep and blue.") is None


def test_judge_objective_uses_ground_truth():
    # a non-compiling code answer is bad EVEN THOUGH it is long (heuristic would pass)
    bad_code = "```python\n" + "def f(:\n    pass\n" * 10 + "```"
    v = judge("write a python function", bad_code, mode="objective")
    assert v.is_bad


def test_judge_objective_falls_back_to_heuristic():
    # not objectively verifiable -> delivery heuristic still runs
    v = judge("write a poem", "", mode="objective")
    assert v.is_bad and v.score == 0.0        # empty -> heuristic bad


def test_execute_opt_in_catches_runtime_error(monkeypatch):
    monkeypatch.setenv("VERIFY_EXECUTE", "1")
    score, label, reasons = verify("write python", "```python\nraise ValueError('boom')\n```")
    assert label == "bad" and any("runtime" in r for r in reasons)
