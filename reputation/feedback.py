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


def _give_feedback_real(agent_id: str, value: int, decimals: int,
                        label: str, reasons: list[str], network: str,
                        source: str = "auto") -> Feedback:
    """Call ERC-8004 Reputation Registry giveFeedback on-chain. Needs a funded wallet.

    Verify the ABI/param order against ERC8004SPEC.md + the live contract before use;
    the client-authorization signature gate must also be satisfied.
    """
    registry = REPUTATION_REGISTRY.get(network)
    if not registry:
        raise RuntimeError(f"no ERC-8004 Reputation Registry known for network {network}")
    key = os.environ.get("WALLET_PRIVATE_KEY")
    if not key:
        raise RuntimeError("WALLET_PRIVATE_KEY required for real reputation feedback")
    # from web3 import Web3
    # token_id = int(agent_id)  # seller must be a registered ERC-721 agent
    # contract.functions.giveFeedback(token_id, value, decimals, "quality", label,
    #     "/inference", feedback_uri, feedback_hash).build_transaction(...) -> sign -> send
    raise NotImplementedError(
        "real ERC-8004 giveFeedback: wire web3 contract call against the verified ABI "
        f"at {registry} (network {network}). Mock mode records to the local ledger.")
