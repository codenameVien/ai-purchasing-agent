"""ERC-8004 reputation feedback — record how a paid seller performed.

mock mode (default, testable offline): append a feedback record to a local JSON
ledger + a deterministic fake tx. real mode: call the ERC-8004 Reputation
Registry `giveFeedback(...)` on Base Sepolia (needs a funded wallet — Phase A).

ERC-8004 interface (DRAFT — verify against ERC8004SPEC.md + live ABI; pin a commit):
  giveFeedback(uint256 agentId, int128 value, uint8 valueDecimals,
               string tag1, string tag2, string endpoint,
               string feedbackURI, bytes32 feedbackHash)
  - agentId = seller's ERC-721 tokenId in the Identity Registry
  - score encoded as value + valueDecimals (exact range UNCERTAIN)
  - a client-authorization signature (EIP-191/ERC-1271) gates feedback — verify
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass

# Reference deployments (DRAFT, MAY CHANGE — verify on-chain before sending value).
REPUTATION_REGISTRY = {
    "eip155:84532": "0x8004B663056A597Dffe9eCcC1965A193B7388713",   # Base Sepolia
    "eip155:1": "0x8004BAa17C55a88189AE136b182e5fdA19dE9b63",       # Mainnet
}

# CAIP-2 network -> JSON-RPC endpoint for the on-chain path (override via X402_RPC_URL).
_RPC = {"eip155:84532": "https://sepolia.base.org", "eip155:1": "https://mainnet.base.org"}

_ABI_PATH = os.path.join(os.path.dirname(__file__), "abi", "ReputationRegistry.json")

_LEDGER_PATH = os.environ.get(
    "REPUTATION_LEDGER",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "reputation_ledger.json"),
)


@dataclass
class Feedback:
    agent_id: str          # seller agent id (mock: seller_id; real: ERC-721 tokenId)
    value: int             # score, encoded with value_decimals
    value_decimals: int
    tag1: str              # e.g. "quality"
    tag2: str              # e.g. "bad" / "good"
    reasons: list[str]
    tx_hash: str
    mock: bool
    source: str = "auto"   # "auto" = machine delivery-check (judge); "human" = user 👍/👎


def _encode_score(score_0_1: float) -> tuple[int, int]:
    """Map a 0..1 judge score to (value, valueDecimals). 0.42 -> (42, 2)."""
    return int(round(score_0_1 * 100)), 2


def _load_ledger(path: str) -> list[dict]:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


# human 👍/👎 is the real quality signal; the machine delivery-check is a weak prior.
_SOURCE_WEIGHT = {"human": 3.0, "auto": 1.0}


def load_reputation(ledger_path: str | None = None) -> dict[str, dict]:
    """Aggregate the feedback ledger into per-seller reputation.

    Returns {agent_id: {"rep": 0..1 weighted mean, "count": n, "human": h}}. Human
    feedback is weighted more than the machine delivery-check. Feeds selector so
    sellers with bad history get down-ranked. Empty {} if no ledger yet.
    """
    path = ledger_path or _LEDGER_PATH
    out: dict[str, dict] = {}
    for rec in _load_ledger(path):
        agent = rec.get("agent_id")
        if not agent:
            continue
        q = rec["value"] / (10 ** rec.get("value_decimals", 0))   # decode 0..1 quality
        w = _SOURCE_WEIGHT.get(rec.get("source", "auto"), 1.0)
        acc = out.setdefault(agent, {"wsum": 0.0, "wtot": 0.0, "count": 0, "human": 0})
        acc["wsum"] += q * w
        acc["wtot"] += w
        acc["count"] += 1
        if rec.get("source") == "human":
            acc["human"] += 1
    return {a: {"rep": v["wsum"] / v["wtot"], "count": v["count"], "human": v["human"]}
            for a, v in out.items()}


def give_feedback(agent_id: str, score: float, *, label: str, reasons: list[str],
                  source: str = "auto", mode: str | None = None, network: str | None = None,
                  ledger_path: str | None = None) -> Feedback:
    """Record reputation feedback for a seller. Returns the Feedback receipt.

    source: "auto" (machine delivery-check via judge) or "human" (user 👍/👎).
    Quality is a human call — the auto signal only catches obvious non-delivery.
    """
    # Reputation mode is independent of payment mode, so a live x402 payment run
    # (X402_MODE=real) keeps recording feedback to the local ledger unless you
    # explicitly opt into on-chain giveFeedback via REPUTATION_MODE=real.
    mode = mode or os.environ.get("REPUTATION_MODE", "mock")
    network = network or os.environ.get("X402_NETWORK", "eip155:84532")
    value, decimals = _encode_score(score)

    if mode == "real":
        return _give_feedback_real(agent_id, value, decimals, label, reasons, network, source)

    # mock: deterministic fake tx + append to local ledger
    digest = hashlib.sha256(f"{agent_id}|{value}|{label}|{source}|{';'.join(reasons)}".encode()).hexdigest()
    fb = Feedback(agent_id=agent_id, value=value, value_decimals=decimals,
                  tag1="quality", tag2=label, reasons=list(reasons),
                  tx_hash="0xMOCKFB" + digest[:56], mock=True, source=source)
    path = ledger_path or _LEDGER_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    ledger = _load_ledger(path)
    ledger.append(asdict(fb))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2)
    return fb


def _resolve_agent_id(agent_id: str) -> int:
    """Seller identity on-chain is an ERC-721 tokenId in the Identity Registry, NOT
    our human seller_id. Accept a numeric id directly, else map via SELLER_AGENT_IDS
    ('{"gamma": 7}'). Fail loud if a seller isn't registered — we can't fake a tokenId.
    """
    if str(agent_id).isdigit():
        return int(agent_id)
    mapping = json.loads(os.environ.get("SELLER_AGENT_IDS", "{}"))
    if agent_id in mapping:
        return int(mapping[agent_id])
    raise RuntimeError(
        f"seller '{agent_id}' has no on-chain agentId. Register it in the ERC-8004 "
        "Identity Registry and map it via SELLER_AGENT_IDS='{\"%s\": <tokenId>}'." % agent_id)


def _feedback_hash(reasons: list[str], label: str) -> bytes:
    """bytes32 commitment to the off-chain feedback detail (emitted, not stored)."""
    blob = json.dumps({"label": label, "reasons": reasons}, sort_keys=True).encode()
    return hashlib.sha256(blob).digest()   # 32 bytes; keccak also fine, sha256 is deterministic here


def _give_feedback_real(agent_id: str, value: int, decimals: int,
                        label: str, reasons: list[str], network: str,
                        source: str = "auto") -> Feedback:
    """Call ERC-8004 Reputation Registry giveFeedback on-chain. Broadcasts a real tx.

    ABI verified against erc-8004/erc-8004-contracts (abis/ReputationRegistry.json):
      giveFeedback(uint256 agentId, int128 value, uint8 valueDecimals,
                   string tag1, string tag2, string endpoint,
                   string feedbackURI, bytes32 feedbackHash)
    msg.sender is recorded as the client; the contract blocks self-feedback via the
    Identity Registry, so the buyer wallet (payer) leaving feedback is exactly right.
    """
    registry = REPUTATION_REGISTRY.get(network)
    if not registry:
        raise RuntimeError(f"no ERC-8004 Reputation Registry known for network {network}")
    key = os.environ.get("WALLET_PRIVATE_KEY")
    if not key:
        raise RuntimeError("WALLET_PRIVATE_KEY required for real reputation feedback")

    from web3 import Web3                                    # lazy: mock mode needs no web3
    from eth_account import Account

    rpc = os.environ.get("X402_RPC_URL") or _RPC.get(network)
    if not rpc:
        raise RuntimeError(f"no RPC endpoint for {network}; set X402_RPC_URL")
    w3 = Web3(Web3.HTTPProvider(rpc))
    acct = Account.from_key(key)
    token_id = _resolve_agent_id(agent_id)
    with open(_ABI_PATH, encoding="utf-8") as f:
        abi = json.load(f)
    contract = w3.eth.contract(address=Web3.to_checksum_address(registry), abi=abi)

    fn = contract.functions.giveFeedback(
        token_id, int(value), int(decimals), "quality", label,
        "/inference", "", _feedback_hash(reasons, label))
    tx = fn.build_transaction({
        "from": acct.address,
        "nonce": w3.eth.get_transaction_count(acct.address, "pending"),   # pending: safe if batched
        "chainId": int(network.split(":")[1]),
    })
    signed = acct.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    # hexbytes.hex() drops the 0x prefix on the web3 7.x stack; keep receipts 0x-prefixed
    # so they match mock tx hashes and every block explorer.
    hexstr = tx_hash.hex()
    return Feedback(agent_id=str(token_id), value=value, value_decimals=decimals,
                    tag1="quality", tag2=label, reasons=list(reasons),
                    tx_hash=hexstr if hexstr.startswith("0x") else "0x" + hexstr,
                    mock=False, source=source)
