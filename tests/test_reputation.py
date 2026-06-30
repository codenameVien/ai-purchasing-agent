"""Phase 4 verification: judge verdicts + ERC-8004 feedback (mock ledger)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agent.judge import judge
from reputation.feedback import give_feedback


def test_judge_empty_is_bad():
    v = judge("q", "")
    assert v.is_bad and v.score == 0.0


def test_judge_refusal_is_bad():
    v = judge("q", "As an AI, I cannot help with that.")
    assert v.is_bad


def test_judge_good_answer():
    v = judge("explain X", "Here is a thorough, correct multi-sentence explanation of X.")
    assert v.label == "good" and not v.is_bad


def test_judge_threshold_relabels():
    # a short-but-not-failing answer can be pushed to bad by a high bar
    v = judge("q", "ok.", min_acceptable=0.9)
    assert v.is_bad


def test_feedback_mock_writes_ledger(tmp_path):
    ledger = str(tmp_path / "ledger.json")
    fb = give_feedback("proxy:gpt-4o", 0.2, label="bad",
                       reasons=["empty result"], mode="mock", ledger_path=ledger)
    assert fb.mock and fb.tx_hash.startswith("0xMOCKFB")
    assert (fb.value, fb.value_decimals) == (20, 2)   # 0.2 -> 20 / 2 decimals
    saved = json.loads((tmp_path / "ledger.json").read_text())
    assert len(saved) == 1 and saved[0]["agent_id"] == "proxy:gpt-4o"
    assert saved[0]["tag2"] == "bad"


def test_feedback_appends(tmp_path):
    ledger = str(tmp_path / "ledger.json")
    give_feedback("a:1", 0.1, label="bad", reasons=["x"], mode="mock", ledger_path=ledger)
    give_feedback("a:2", 0.3, label="bad", reasons=["y"], mode="mock", ledger_path=ledger)
    saved = json.loads((tmp_path / "ledger.json").read_text())
    assert len(saved) == 2
