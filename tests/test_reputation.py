"""Phase 4 verification: judge verdicts + ERC-8004 feedback (mock ledger)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agent.catalog import Catalog
from agent.judge import judge
from agent.selector import fetch_scores, select
from reputation.feedback import give_feedback, load_reputation


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


def test_reputation_downranks_bad_seller(tmp_path):
    catalog = Catalog.load()
    scores = fetch_scores(use_live=False)

    # baseline: Claude wins on coding (best coding index)
    base = select("coding", scores, catalog)
    assert base[0].entry.aa_slug == "claude-opus-4-8"
    claude_seller = base[0].entry.seller_id           # e.g. "anthropic-store"

    # give Claude's seller repeated bad feedback (reputation is per-seller)
    ledger = str(tmp_path / "ledger.json")
    for _ in range(2):
        give_feedback(claude_seller, 0.1, label="bad",
                      reasons=["bad result"], mode="mock", ledger_path=ledger)
    rep = load_reputation(ledger)

    # default weight only modifies; a strong weight lets bad rep flip a leader
    ranked = select("coding", scores, catalog, reputation=rep, reputation_weight=0.8)
    claude = next(r for r in ranked if r.entry.aa_slug == "claude-opus-4-8")
    assert claude.score < claude.base_score          # reputation factor applied
    assert ranked[0].entry.aa_slug != "claude-opus-4-8"  # bad rep flipped the winner


def test_feedback_appends(tmp_path):
    ledger = str(tmp_path / "ledger.json")
    give_feedback("a:1", 0.1, label="bad", reasons=["x"], mode="mock", ledger_path=ledger)
    give_feedback("a:2", 0.3, label="bad", reasons=["y"], mode="mock", ledger_path=ledger)
    saved = json.loads((tmp_path / "ledger.json").read_text())
    assert len(saved) == 2
