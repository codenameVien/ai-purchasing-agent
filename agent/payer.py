"""x402 payment client with spending guardrails.

The HTTP 402 handshake is REAL even in mock mode; only the crypto (ERC-3009
signing + facilitator verification) is stubbed. Phase A swaps the two stubbed
spots for real signing/verification — nothing else changes.

Flow:
  POST /inference            -> 402 + PaymentRequired
  read required amount, check guard
  POST /inference + X-PAYMENT -> 200 + result + X-PAYMENT-RESPONSE (tx hash)
"""
from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass

import requests

from .catalog import CatalogEntry


class SpendingError(Exception):
    """Raised when a payment would exceed a configured cap."""


@dataclass
class SpendGuard:
    per_call: float
    per_session: float
    spent: float = 0.0

    @classmethod
    def from_env(cls) -> "SpendGuard":
        return cls(
            per_call=float(os.environ.get("MAX_USDC_PER_CALL", "0.10")),
            per_session=float(os.environ.get("MAX_USDC_PER_SESSION", "1.00")),
        )

    def authorize(self, amount: float) -> None:
        if amount > self.per_call:
            raise SpendingError(f"call {amount} USDC exceeds per-call cap {self.per_call}")
        if self.spent + amount > self.per_session:
            raise SpendingError(
                f"session would reach {self.spent + amount} USDC, cap {self.per_session}")

    def record(self, amount: float) -> None:
        self.spent += amount


@dataclass
class PaymentReceipt:
    paid_usdc: float
    tx_hash: str
    mock: bool


def _build_payment_header(requirements: dict, amount: float, mode: str) -> str:
    """Build the X-PAYMENT header value for the MOCK handshake (base64 JSON stub).

    Real ERC-3009 signing is not done here — in real mode the x402 library's own
    paying session handles the 402 -> sign -> retry loop (see _real_pay_and_call).
    """
    stub = {"mock": True, "amount": str(amount),
            "accepts": requirements.get("accepts", [])}
    return base64.b64encode(json.dumps(stub).encode()).decode()


# Verified against installed x402 v2.14.0 (pip install "x402[evm]").
def build_paying_session(network: str | None = None):
    """Return a requests.Session that auto-handles HTTP 402 by signing an
    EIP-3009 'exact' authorization with WALLET_PRIVATE_KEY (Base Sepolia testnet).
    """
    import os as _os

    from eth_account import Account
    from x402 import x402ClientSync
    from x402.http.clients import x402_requests
    from x402.mechanisms.evm import EthAccountSigner
    from x402.mechanisms.evm.exact.register import register_exact_evm_client

    key = _os.environ.get("WALLET_PRIVATE_KEY")
    if not key:
        raise RuntimeError("WALLET_PRIVATE_KEY not set (testnet key required for real mode)")
    network = network or _os.environ.get("X402_NETWORK", "eip155:84532")
    client = x402ClientSync()
    register_exact_evm_client(client, EthAccountSigner(Account.from_key(key)), networks=network)
    return x402_requests(client)


def _real_pay_and_call(entry: CatalogEntry, prompt: str, guard: SpendGuard,
                       url: str | None, timeout: float) -> dict:
    target = url or entry.seller_url
    body = {"model": entry.model_id, "messages": [{"role": "user", "content": prompt}]}
    amount = entry.price_usdc_per_call
    guard.authorize(amount)                       # soft pre-cap vs expected catalog price
    session = build_paying_session()
    r = session.post(target, json=body, timeout=timeout)
    r.raise_for_status()
    guard.record(amount)
    # v2 settlement comes back in the PAYMENT-RESPONSE header (base64 JSON).
    tx = _decode_tx(r.headers.get("PAYMENT-RESPONSE", r.headers.get("X-PAYMENT-RESPONSE", "")))
    return {"result": r.json(), "receipt": PaymentReceipt(paid_usdc=amount, tx_hash=tx, mock=False)}


def _decode_tx(header_val: str) -> str:
    if not header_val:
        return ""
    try:
        d = json.loads(base64.b64decode(header_val))
        for k in ("txHash", "transaction", "transactionHash", "tx_hash"):
            if d.get(k):
                return d[k]
        return ""
    except Exception:
        return header_val


def pay_and_call(entry: CatalogEntry, prompt: str, guard: SpendGuard, *,
                 mode: str | None = None, url: str | None = None,
                 post=requests.post, timeout: float = 30.0) -> dict:
    """Pay for and call one model. `post` is injectable for testing (TestClient)."""
    mode = mode or os.environ.get("X402_MODE", "mock")
    if mode == "real":
        return _real_pay_and_call(entry, prompt, guard, url, timeout)

    target = url or entry.seller_url
    body = {"model": entry.model_id, "messages": [{"role": "user", "content": prompt}]}

    r = post(target, json=body, timeout=timeout)
    if r.status_code != 402:
        r.raise_for_status()
        return {"result": r.json(), "receipt": None}

    requirements = r.json()
    amount = entry.price_usdc_per_call
    guard.authorize(amount)                       # refuse before paying if over cap
    header = _build_payment_header(requirements, amount, mode)

    r = post(target, json=body, headers={"X-PAYMENT": header}, timeout=timeout)
    r.raise_for_status()
    guard.record(amount)
    receipt = PaymentReceipt(
        paid_usdc=amount,
        tx_hash=_decode_tx(r.headers.get("X-PAYMENT-RESPONSE", "")),
        mock=(mode == "mock"),
    )
    return {"result": r.json(), "receipt": receipt}
