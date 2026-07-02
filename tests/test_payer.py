"""Real-path payer pre-checks: USDC balance guard + on-chain confirmation wait.
web3 is mocked — no network, no real tx."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import agent.payer as payer
from agent.payer import PaymentError

NET = "eip155:84532"


# --- balance pre-check -------------------------------------------------------

def test_precheck_raises_when_short(monkeypatch):
    monkeypatch.setattr(payer, "_usdc_balance", lambda net: 0.0005)
    try:
        payer._precheck_balance(0.001, NET)
    except PaymentError as e:
        assert "insufficient USDC" in str(e)
        return
    raise AssertionError("expected PaymentError when balance < required")


def test_precheck_passes_when_enough(monkeypatch):
    monkeypatch.setattr(payer, "_usdc_balance", lambda net: 5.0)
    payer._precheck_balance(0.001, NET)     # no raise


def test_precheck_skips_when_unreadable(monkeypatch):
    # best-effort: if balance can't be read, proceed (settlement is the real gate)
    monkeypatch.setattr(payer, "_usdc_balance", lambda net: None)
    payer._precheck_balance(999.0, NET)     # no raise despite huge amount


# --- confirmation wait -------------------------------------------------------

class _FakeEth:
    def __init__(self, status): self._status = status
    def wait_for_transaction_receipt(self, tx, timeout=None): return {"status": self._status}

class _FakeW3:
    def __init__(self, status): self.eth = _FakeEth(status)


def test_wait_confirmation_success(monkeypatch):
    monkeypatch.setattr(payer, "_rpc_web3", lambda net: _FakeW3(1))
    assert payer._wait_for_confirmation("0xabc", NET, 5) is True


def test_wait_confirmation_reverted(monkeypatch):
    monkeypatch.setattr(payer, "_rpc_web3", lambda net: _FakeW3(0))
    assert payer._wait_for_confirmation("0xabc", NET, 5) is False


def test_wait_confirmation_no_tx(monkeypatch):
    monkeypatch.setattr(payer, "_rpc_web3", lambda net: _FakeW3(1))
    assert payer._wait_for_confirmation("", NET, 5) is None    # nothing to wait on


def test_wait_confirmation_no_web3(monkeypatch):
    monkeypatch.setattr(payer, "_rpc_web3", lambda net: None)
    assert payer._wait_for_confirmation("0xabc", NET, 5) is None


def test_wait_confirmation_timeout_is_unknown_not_false(monkeypatch):
    # a slow-but-fine tx (timeout) must read as unknown (None), not a revert (False)
    class _Eth:
        def wait_for_transaction_receipt(self, tx, timeout=None):
            raise TimeoutError("not mined in window")
    monkeypatch.setattr(payer, "_rpc_web3", lambda net: type("W", (), {"eth": _Eth()})())
    assert payer._wait_for_confirmation("0xabc", NET, 5) is None


def test_wait_confirmation_adds_0x_prefix(monkeypatch):
    seen = {}
    class _Eth:
        def wait_for_transaction_receipt(self, tx, timeout=None):
            seen["tx"] = tx
            return {"status": 1}
    monkeypatch.setattr(payer, "_rpc_web3", lambda net: type("W", (), {"eth": _Eth()})())
    assert payer._wait_for_confirmation("abc123", NET, 5) is True
    assert seen["tx"] == "0xabc123"        # bare-hex normalized before the node call


# --- balance read wiring (contract call mocked) ------------------------------

def test_usdc_balance_reads_and_scales(monkeypatch):
    import eth_account
    import web3

    class _Fn:
        def __init__(self, v): self._v = v
        def call(self): return self._v

    class _Funcs:
        def balanceOf(self, addr): return _Fn(2_500_000)   # raw
        def decimals(self): return _Fn(6)

    class _Eth:
        def contract(self, address, abi): return type("C", (), {"functions": _Funcs()})()

    class _W3:
        def __init__(self, *a): self.eth = _Eth()
        @staticmethod
        def HTTPProvider(u): return object()
        @staticmethod
        def to_checksum_address(a): return a

    monkeypatch.setenv("WALLET_PRIVATE_KEY", "0x" + "11" * 32)
    monkeypatch.setattr(web3, "Web3", _W3)
    monkeypatch.setattr(eth_account.Account, "from_key",
                        staticmethod(lambda k: type("A", (), {"address": "0xB"})()))
    assert payer._usdc_balance(NET) == 2.5      # 2_500_000 / 10**6
