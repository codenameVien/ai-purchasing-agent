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
    """Build the X-PAYMENT header value.

    mock: a base64 JSON stub (no signature).
    real: sign an ERC-3009 transferWithAuthorization (EIP-712) — Phase A.
    """
    if mode == "mock":
        stub = {"mock": True, "amount": str(amount),
                "accepts": requirements.get("accepts", [])}
        return base64.b64encode(json.dumps(stub).encode()).decode()
    # --- Phase A: real ERC-3009 signing ---
    # from eth_account import Account; from web3 import Web3
    # accept = requirements["accepts"][0]
    # authorization = {from, to=accept["payTo"], value, validAfter, validBefore, nonce}
    # signature = Account.sign_typed_data(WALLET_PRIVATE_KEY, eip712_domain, types, authorization)
    # return base64(json({"x402Version":1,"scheme":"exact","network":...,"payload":{authorization,signature}}))
    raise NotImplementedError("real ERC-3009 signing is wired in Phase A")


def _decode_tx(header_val: str) -> str:
    if not header_val:
        return ""
    try:
        return json.loads(base64.b64decode(header_val)).get("txHash", "")
    except Exception:
        return header_val


def pay_and_call(entry: CatalogEntry, prompt: str, guard: SpendGuard, *,
                 mode: str | None = None, url: str | None = None,
                 post=requests.post, timeout: float = 30.0) -> dict:
    """Pay for and call one model. `post` is injectable for testing (TestClient)."""
    mode = mode or os.environ.get("X402_MODE", "mock")
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
