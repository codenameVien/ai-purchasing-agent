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

# CAIP-2 network -> JSON-RPC endpoint + USDC token address (override RPC via X402_RPC_URL).
_RPC = {"eip155:84532": "https://sepolia.base.org", "eip155:8453": "https://mainnet.base.org"}
_USDC = {
    "eip155:84532": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",   # Base Sepolia
    "eip155:8453": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",    # Base mainnet
}
_ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "a", "type": "address"}], "name": "balanceOf",
     "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"constant": True, "inputs": [], "name": "decimals",
     "outputs": [{"name": "", "type": "uint8"}], "stateMutability": "view", "type": "function"},
]


class SpendingError(Exception):
    """Raised when a payment would exceed a configured cap."""


class PaymentError(Exception):
    """Raised when a real payment fails (rejected, seller/facilitator error)."""


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
    confirmed: bool | None = None   # True/False after on-chain wait; None = not checked (mock)


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


def _rpc_web3(network: str):
    """Web3 connected to the network's RPC, or None if web3/RPC is unavailable.
    Used for read-only pre-checks — the on-chain settlement is the real source of
    truth, so a failed read here degrades to 'skip the pre-check', never a false OK.
    """
    # NOTE: if you set X402_RPC_URL it MUST point at the same chain as X402_NETWORK —
    # the USDC token address is keyed by network, so a mismatched RPC reads the wrong token.
    rpc = os.environ.get("X402_RPC_URL") or _RPC.get(network)
    if not rpc:
        return None
    try:
        from web3 import Web3
        return Web3(Web3.HTTPProvider(rpc))
    except Exception:
        return None


def _usdc_balance(network: str) -> float | None:
    """Wallet USDC balance (float), or None if it can't be read."""
    token = _USDC.get(network)
    key = os.environ.get("WALLET_PRIVATE_KEY")
    w3 = _rpc_web3(network)
    if not (token and key and w3):
        return None
    try:
        from eth_account import Account
        from web3 import Web3
        addr = Account.from_key(key).address
        c = w3.eth.contract(address=Web3.to_checksum_address(token), abi=_ERC20_ABI)
        raw = c.functions.balanceOf(addr).call()
        decimals = c.functions.decimals().call()
        return raw / (10 ** decimals)
    except Exception:
        return None


def _precheck_balance(amount: float, network: str) -> None:
    """Abort BEFORE signing if the wallet plainly can't cover `amount` (avoids a
    live payment that would fail on-chain). Best-effort: if the balance can't be
    read, we proceed and let settlement be the gate."""
    bal = _usdc_balance(network)
    if bal is not None and bal < amount:
        raise PaymentError(
            f"insufficient USDC: wallet holds {bal:.6f}, need {amount:.6f}. "
            "Fund the buyer address at https://faucet.circle.com (testnet).")


def _wait_for_confirmation(tx_hash: str, network: str, timeout: float) -> bool | None:
    """Poll for the tx receipt so a 200 isn't trusted before the chain settles.
    Returns True (status=1) / False (on-chain revert) / None (unknown: timed out,
    unreadable, or nothing to wait on). A slow-but-fine tx is 'unknown', not 'failed'.
    """
    if not tx_hash:
        return None
    h = tx_hash if tx_hash.startswith("0x") else "0x" + tx_hash   # node rejects bare-hex
    w3 = _rpc_web3(network)
    if not w3:
        return None
    try:
        rcpt = w3.eth.wait_for_transaction_receipt(h, timeout=timeout)
    except Exception:
        return None         # timeout / not-found within window -> unknown, NOT a revert
    return int(rcpt.get("status", 0)) == 1


def _real_pay_and_call(entry: CatalogEntry, prompt: str, guard: SpendGuard,
                       url: str | None, timeout: float) -> dict:
    target = url or entry.seller_url
    body = {"model": entry.model_id, "backend": entry.backend,
            "messages": [{"role": "user", "content": prompt}]}
    # Preflight: read the 402 (no payment) to enforce the cap against the ACTUAL
    # amount the seller asks for, before the paying session signs anything.
    amount = entry.price_usdc_per_call
    try:
        pre = requests.post(target, json=body, timeout=timeout)
        if pre.status_code == 402:
            parsed = _required_usdc(_extract_requirements(pre), atomic=True)
            if parsed is not None:
                amount = parsed
    except requests.RequestException:
        pass                                       # fall back to catalog price
    guard.authorize(amount)                        # actual required amount vs cap
    network = os.environ.get("X402_NETWORK", "eip155:84532")
    _precheck_balance(amount, network)             # early abort if wallet can't cover it
    session = build_paying_session()

    # Pay, with clear errors + one retry on a transient seller/facilitator 5xx.
    r = None
    for attempt in (1, 2):
        r = session.post(target, json=body, timeout=timeout)
        if r.status_code == 402:
            raise PaymentError("payment rejected — insufficient USDC or verification failed "
                               "(check wallet balance / facilitator)")
        if r.status_code >= 500 and attempt == 1:
            continue                               # transient: retry once
        break
    try:
        r.raise_for_status()
    except requests.HTTPError as e:
        raise PaymentError(f"seller/facilitator error: {e}") from e
    guard.record(amount)
    # v2 settlement comes back in the PAYMENT-RESPONSE header (base64 JSON).
    tx = _decode_tx(r.headers.get("PAYMENT-RESPONSE", r.headers.get("X-PAYMENT-RESPONSE", "")))
    # Don't trust the 200 as final — wait for on-chain confirmation (opt out via X402_WAIT_CONFIRM=0).
    confirmed = None
    if os.environ.get("X402_WAIT_CONFIRM", "1") not in ("0", "false", "False"):
        confirmed = _wait_for_confirmation(tx, network, float(os.environ.get("X402_CONFIRM_TIMEOUT", "30")))
    return {"result": r.json(),
            "receipt": PaymentReceipt(paid_usdc=amount, tx_hash=tx, mock=False, confirmed=confirmed)}


def _extract_requirements(resp) -> dict | None:
    """Get the x402 PaymentRequirements from a 402 response.

    mock proxy puts them in the JSON body; the real x402 v2 middleware puts them
    (base64 JSON) in the PAYMENT-REQUIRED header with an empty body.
    """
    try:
        body = resp.json()
        if isinstance(body, dict) and body.get("accepts"):
            return body
    except Exception:
        pass
    hdr = resp.headers.get("PAYMENT-REQUIRED") or resp.headers.get("payment-required")
    if hdr:
        try:
            return json.loads(base64.b64decode(hdr))
        except Exception:
            return None
    return None


def _required_usdc(requirements: dict | None, atomic: bool, decimals: int = 6) -> float | None:
    """Actual USDC the seller is asking for, from accepts[0].

    real v2 uses atomic `amount` ("1000" = 0.001 at 6 decimals); our mock uses a
    dollar string `maxAmountRequired` ("0.02"). Returns None if unparseable.
    """
    if not requirements:
        return None
    accepts = requirements.get("accepts") or []
    if not accepts:
        return None
    a = accepts[0]
    val = a.get("amount", a.get("maxAmountRequired"))
    if val is None:
        return None
    try:
        return int(val) / (10 ** decimals) if atomic else float(val)
    except (ValueError, TypeError):
        return None


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
    body = {"model": entry.model_id, "backend": entry.backend,
            "messages": [{"role": "user", "content": prompt}]}

    r = post(target, json=body, timeout=timeout)
    if r.status_code != 402:
        r.raise_for_status()
        return {"result": r.json(), "receipt": None}

    requirements = _extract_requirements(r) or {}
    amount = _required_usdc(requirements, atomic=False)     # ACTUAL 402 amount, not catalog estimate
    if amount is None:
        amount = entry.price_usdc_per_call                 # fallback if unparseable
    guard.authorize(amount)                                # refuse before paying if over cap
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
