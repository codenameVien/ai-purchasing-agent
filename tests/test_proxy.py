"""Phase 2 verification: x402 402-handshake + spending guardrails (mock crypto)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient

from agent.catalog import Catalog
from agent.payer import SpendGuard, SpendingError, pay_and_call
from seller_proxy.main import app

client = TestClient(app)


def test_402_without_payment():
    r = client.post("/inference", json={"model": "x", "messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 402
    body = r.json()
    assert body["accepts"][0]["scheme"] == "exact"
    assert body["accepts"][0]["asset"] == "USDC"


def test_e2e_mock_payment():
    entry = Catalog.load().get("gpt-4o")
    guard = SpendGuard(per_call=0.10, per_session=1.0)
    out = pay_and_call(entry, "ping-123", guard, mode="mock", url="/inference", post=client.post)
    rec = out["receipt"]
    assert rec.mock is True
    assert rec.tx_hash.startswith("0xMOCK")
    assert guard.spent == entry.price_usdc_per_call
    # mock backend echoes the prompt
    assert "ping-123" in out["result"]["choices"][0]["message"]["content"]


def test_guard_blocks_overspend():
    entry = Catalog.load().get("claude-3-7-sonnet")  # 0.025 USDC/call
    guard = SpendGuard(per_call=0.01, per_session=1.0)  # cap below price
    try:
        pay_and_call(entry, "ping", guard, mode="mock", url="/inference", post=client.post)
    except SpendingError:
        assert guard.spent == 0.0  # nothing spent on refusal
        return
    raise AssertionError("expected SpendingError")


def test_session_cap_accumulates():
    entry = Catalog.load().get("gpt-4o")  # 0.02 each
    guard = SpendGuard(per_call=0.10, per_session=0.03)  # room for one, not two
    pay_and_call(entry, "a", guard, mode="mock", url="/inference", post=client.post)
    try:
        pay_and_call(entry, "b", guard, mode="mock", url="/inference", post=client.post)
    except SpendingError:
        return
    raise AssertionError("expected session cap to block the second call")
