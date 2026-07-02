"""Phase 2 verification: x402 402-handshake + spending guardrails (mock crypto)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

os.environ["PROXY_BACKEND"] = "mock"  # force mock backend regardless of catalog

from fastapi.testclient import TestClient

from agent.catalog import Catalog
from agent.payer import SpendGuard, SpendingError, pay_and_call
from seller_proxy.main import app

client = TestClient(app)


def test_marketplace_discovery_endpoint():
    r = client.get("/marketplace")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] >= 1
    o = data["offers"][0]
    for k in ("aa_slug", "seller_id", "price_usdc_per_call", "reputation"):
        assert k in o


def test_discover_catalog_matches_local():
    from agent.catalog import Catalog
    from agent.discovery import discover_catalog
    discovered = discover_catalog("/marketplace", get=client.get)
    assert discovered.aa_slugs() == Catalog.load().aa_slugs()   # same models, fetched live
    assert len(discovered.offers) == len(Catalog.load().offers)


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


def test_required_usdc_parser():
    from agent.payer import _required_usdc
    assert _required_usdc({"accepts": [{"maxAmountRequired": "0.02"}]}, atomic=False) == 0.02
    assert _required_usdc({"accepts": [{"amount": "1000"}]}, atomic=True) == 0.001  # 6 decimals
    assert _required_usdc(None, atomic=False) is None
    assert _required_usdc({"accepts": []}, atomic=False) is None


def test_guard_uses_actual_402_amount_not_catalog():
    """The cap must be checked against what the seller actually charges, not the
    catalog estimate. Cheap catalog price but the proxy charges more -> refuse."""
    entry = Catalog.load().get("llama-3.3-70b")   # catalog price ~0.002
    assert entry.price_usdc_per_call < 0.005
    guard = SpendGuard(per_call=0.005, per_session=1.0)   # between catalog price and proxy's 0.02
    try:
        pay_and_call(entry, "ping", guard, mode="mock", url="/inference", post=client.post)
    except SpendingError:
        return                                    # correct: actual 0.02 > 0.005
    raise AssertionError("expected SpendingError from the ACTUAL 402 amount")


def test_guard_blocks_overspend():
    entry = Catalog.load().get("claude-opus-4-8")  # 0.025 USDC/call
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
