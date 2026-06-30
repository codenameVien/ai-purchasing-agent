"""Result quality evaluation — decides whether a paid result was good enough.

A bad verdict triggers an ERC-8004 reputation feedback against the seller.

mode="heuristic" (default): cheap offline signals (empty / error / refusal / length).
mode="llm": an LLM-judge scores the answer — wire in a model call later. The
heuristic is intentionally crude; it exists so the select->pay->judge->feedback
loop is demonstrable without a wallet or a judge model.
"""
from __future__ import annotations

from dataclasses import dataclass, field

_ERROR_MARKERS = ("error", "exception", "traceback", "null", "undefined")
_REFUSAL_MARKERS = ("i cannot", "i can't", "i'm unable", "cannot help", "as an ai")


@dataclass
class Verdict:
    score: float                       # 0.0 (worst) .. 1.0 (best)
    label: str                         # "good" | "ok" | "bad"
    reasons: list[str] = field(default_factory=list)

    @property
    def is_bad(self) -> bool:
        return self.label == "bad"


def _heuristic(prompt: str, text: str) -> Verdict:
    reasons: list[str] = []
    t = (text or "").strip()
    low = t.lower()

    if not t:
        return Verdict(0.0, "bad", ["empty result"])
    if any(m in low for m in _REFUSAL_MARKERS):
        return Verdict(0.2, "bad", ["model refused / non-answer"])
    if any(m in low for m in _ERROR_MARKERS):
        return Verdict(0.3, "bad", ["error marker in output"])

    score = 1.0
    if len(t) < 20:
        score -= 0.5
        reasons.append("very short answer")
    if len(t) < 5:
        score -= 0.3

    label = "good" if score >= 0.8 else "ok" if score >= 0.5 else "bad"
    if label != "good":
        reasons.append(f"length/signal score {score:.2f}")
    return Verdict(max(0.0, score), label, reasons)


def judge(prompt: str, result_text: str, *, mode: str = "heuristic",
          min_acceptable: float = 0.5) -> Verdict:
    if mode == "heuristic":
        v = _heuristic(prompt, result_text)
    elif mode == "llm":
        # Wire an LLM-judge call here (score the answer against the prompt).
        raise NotImplementedError("LLM-judge mode not wired yet")
    else:
        raise ValueError(f"unknown judge mode: {mode!r}")

    # Re-label against the caller's acceptance threshold.
    if v.score < min_acceptable and not v.is_bad:
        v.label = "bad"
        v.reasons.append(f"below min_acceptable {min_acceptable}")
    return v
