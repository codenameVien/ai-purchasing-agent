"""Objective verification — mechanical true/false for verifiable tasks (ROADMAP G).

When a task is objectively checkable, no human 👍/👎 or LLM judge is needed: run
the check, get ground truth. This is the *preferred* signal when it applies. Two
safe cases now:

  - code (Python): the answer's ```python block must COMPILE (syntax-valid). No
    execution by default — running a seller's code is unsafe. Opt in with
    VERIFY_EXECUTE=1 to actually run it (subprocess, timeout) for a stronger check.
  - arithmetic: "what is 12 * 8?" -> compute expected, check the answer states it.

verify(prompt, answer) -> (score, label, reasons) | None.
None = NOT objectively verifiable; caller falls back to delivery heuristic / human.
"""
from __future__ import annotations

import ast
import operator
import os
import re
import subprocess
import sys

from .nl_priority import infer_priorities

Result = tuple[float, str, list[str]]   # (score 0..1, label, reasons) — mirrors judge.Verdict

_CODE_BLOCK = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
_ARITH = re.compile(r"(-?\d+(?:\.\d+)?)\s*([+\-*/])\s*(-?\d+(?:\.\d+)?)")
_OPS = {"+": operator.add, "-": operator.sub, "*": operator.mul, "/": operator.truediv}


_CODE_HINT = ("def ", "class ", "import ", "return", "for ", "while ", "if ", "=", "print(")


def _extract_python(text: str) -> str | None:
    """First fenced python block, else the whole text if it *looks* like code AND
    parses. The code-hint gate stops bare prose that happens to be valid Python
    (e.g. a single word) from being accepted as a compilable answer."""
    m = _CODE_BLOCK.search(text or "")
    if m:
        return m.group(1).strip()
    stripped = (text or "").strip()
    if stripped and any(h in stripped for h in _CODE_HINT):
        try:
            ast.parse(stripped)
            return stripped
        except SyntaxError:
            return None
    return None


def _verify_python(code: str) -> Result:
    try:
        compile(code, "<answer>", "exec")
    except SyntaxError as e:
        return 0.0, "bad", [f"code does not compile: {e.msg} (line {e.lineno})"]
    reasons = ["code compiles (syntax-valid)"]
    if os.environ.get("VERIFY_EXECUTE") in ("1", "true", "True"):
        # Opt-in ONLY: runs seller-provided code. Isolated subprocess + hard timeout,
        # but still real execution — never enable for untrusted output you can't sandbox.
        try:
            p = subprocess.run([sys.executable, "-c", code], capture_output=True,
                               text=True, timeout=5)
        except subprocess.TimeoutExpired:
            return 0.3, "bad", ["code timed out (>5s)"]
        if p.returncode != 0:
            err = (p.stderr or "").strip().splitlines()[-1:] or ["nonzero exit"]
            return 0.2, "bad", [f"code raised at runtime: {err[0]}"]
        reasons = ["code runs clean (exit 0)"]
    return 1.0, "good", reasons


def _verify_arithmetic(prompt: str, answer: str) -> Result | None:
    m = _ARITH.search(prompt or "")
    if not m:
        return None
    a, op, b = float(m.group(1)), m.group(2), float(m.group(3))
    if op == "/" and b == 0:
        return None
    expected = _OPS[op](a, b)
    want = f"{expected:g}"                                    # normalize: 0.1+0.2 -> 0.3, not 0.30000..4
    nums = re.findall(r"-?\d+(?:\.\d+)?", answer or "")
    if not nums:
        return 0.0, "bad", [f"arithmetic wrong: expected {m.group(0)} = {want}, no number in answer"]
    # the result is what the answer STATES — compare the last number, numerically w/ tolerance
    stated = float(nums[-1])
    if abs(stated - expected) <= 1e-9 * max(1.0, abs(expected)):
        return 1.0, "good", [f"arithmetic correct ({m.group(0)} = {want})"]
    return 0.0, "bad", [f"arithmetic wrong: expected {m.group(0)} = {want}, answer said {nums[-1]}"]


def verify(prompt: str, answer: str) -> Result | None:
    """Objectively verify an answer if the task allows it, else None.

    Coding is checked FIRST and exclusively: a code prompt like "add 2 + 3 in python"
    contains an arithmetic pattern, but the ground truth is whether the CODE is valid,
    not whether the prose repeats "5". Only non-coding prompts fall through to the
    arithmetic check.
    """
    if "coding" in infer_priorities(prompt):     # a code task -> check the code itself
        code = _extract_python(answer)
        if code is not None:
            return _verify_python(code)
        return None                              # code task, no code found -> not verifiable
    return _verify_arithmetic(prompt, answer)
