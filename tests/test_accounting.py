"""Spend accounting — records payments and rolls them up."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agent.accounting import record_spend, spend_summary


def test_spend_summary(tmp_path):
    ledger = str(tmp_path / "spend.json")
    record_spend("alpha", "llama-3.3-70b", "m", 0.002, "0x1", True, ledger_path=ledger)
    record_spend("alpha", "llama-3.3-70b", "m", 0.002, "0x2", True, ledger_path=ledger)
    record_spend("beta", "llama-3.3-70b", "m", 0.0015, "0x3", True, ledger_path=ledger)
    s = spend_summary(ledger_path=ledger)
    assert s["calls"] == 3
    assert abs(s["total_usdc"] - 0.0055) < 1e-9
    assert abs(s["by_seller"]["alpha"] - 0.004) < 1e-9
    assert abs(s["by_model"]["llama-3.3-70b"] - 0.0055) < 1e-9
