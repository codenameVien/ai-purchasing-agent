"""ERC-8004 Identity Registry registration — web3 mocked, NO real broadcast."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from reputation.identity import register_agent


def _install_fake_chain(monkeypatch, captured, *, status=1, with_event=True):
    import eth_account
    import web3

    class _Fn:
        def build_transaction(self, tx):
            captured["tx"] = tx
            return {**tx, "gas": 200000}

    class _Funcs:
        def register(self, *args):
            captured["register_args"] = args
            return _Fn()

    class _RegisteredEvent:
        def process_receipt(self, rcpt):
            return [{"args": {"agentId": 42, "owner": "0xSELLER"}}] if with_event else []

    class _Events:
        def Registered(self):
            return _RegisteredEvent()

    class _Eth:
        def contract(self, address, abi):
            captured["address"] = address
            return type("C", (), {"functions": _Funcs(), "events": _Events()})()

        def get_transaction_count(self, addr, block=None):
            return 5

        def send_raw_transaction(self, raw):
            return bytes.fromhex("cd" * 32)

        def wait_for_transaction_receipt(self, tx, timeout=None):
            return {"status": status}

    class _Web3:
        def __init__(self, provider): self.eth = _Eth()
        def is_connected(self): return True
        @staticmethod
        def HTTPProvider(url): return object()
        @staticmethod
        def to_checksum_address(a): return a

    class _Acct:
        address = "0xSELLER"
        def sign_transaction(self, tx):
            return type("S", (), {"raw_transaction": b"\x01"})()

    monkeypatch.setattr(web3, "Web3", _Web3)
    monkeypatch.setattr(eth_account.Account, "from_key", staticmethod(lambda k: _Acct()))


def test_register_returns_agent_id(monkeypatch):
    captured: dict = {}
    _install_fake_chain(monkeypatch, captured)
    res = register_agent("0x" + "22" * 32, network="eip155:84532")

    assert res["agent_id"] == 42
    assert res["owner"] == "0xSELLER"
    assert res["tx_hash"] == "0x" + "cd" * 32          # 0x-prefixed
    assert res["agent_id"] == 42
    assert captured["register_args"] == ()             # no uri -> no-arg register()
    assert captured["tx"]["chainId"] == 84532
    assert captured["tx"]["nonce"] == 5


def test_register_with_uri_passes_arg(monkeypatch):
    captured: dict = {}
    _install_fake_chain(monkeypatch, captured)
    register_agent("0x" + "22" * 32, agent_uri="https://x/agent.json", network="eip155:84532")
    assert captured["register_args"] == ("https://x/agent.json",)   # string overload


def test_register_reverts_raises(monkeypatch):
    captured: dict = {}
    _install_fake_chain(monkeypatch, captured, status=0)
    try:
        register_agent("0x" + "22" * 32, network="eip155:84532")
    except RuntimeError as e:
        assert "reverted" in str(e)
        return
    raise AssertionError("expected RuntimeError on reverted registration")


def test_register_no_event_raises(monkeypatch):
    captured: dict = {}
    _install_fake_chain(monkeypatch, captured, with_event=False)
    try:
        register_agent("0x" + "22" * 32, network="eip155:84532")
    except RuntimeError as e:
        assert "Registered event" in str(e)
        return
    raise AssertionError("expected RuntimeError when no Registered event")


def test_register_unknown_network_raises(monkeypatch):
    try:
        register_agent("0x" + "22" * 32, network="eip155:999999")
    except RuntimeError as e:
        assert "Identity Registry" in str(e)
        return
    raise AssertionError("expected RuntimeError for unknown network")
