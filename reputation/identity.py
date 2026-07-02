"""ERC-8004 Identity Registry — register a seller as an on-chain agent (ERC-721).

This is the missing prerequisite for a REAL on-chain giveFeedback: reputation is
keyed by `agentId`, which is the seller's ERC-721 tokenId here — not our human
seller_id. A seller registers itself once (msg.sender becomes the agent owner);
the returned tokenId is what you map via SELLER_AGENT_IDS so the buyer can leave
feedback. The buyer wallet must be DIFFERENT from the seller wallet — the contract
blocks self-feedback (owner/operator) via this registry.

ABI verified against erc-8004/erc-8004-contracts (abis/IdentityRegistry.json):
  register() -> uint256
  register(string agentURI) -> uint256
  event Registered(uint256 indexed agentId, string agentURI, address indexed owner)

register_agent() BROADCASTS a real tx — call it deliberately (scripts/register_seller.py),
never in the normal buy flow. Testnet + disposable wallet only.
"""
from __future__ import annotations

import json
import os

# CAIP-2 network -> Identity Registry address (per-chain singleton; verify before use).
IDENTITY_REGISTRY = {
    "eip155:84532": "0x8004A818BFB912233c491871b3d84c89A494BD9e",   # Base Sepolia
    "eip155:8453": "0x8004A169FB4a3325136EB29fA0ceB6D2e539a432",    # Base mainnet
}
_RPC = {"eip155:84532": "https://sepolia.base.org", "eip155:8453": "https://mainnet.base.org"}
_ABI_PATH = os.path.join(os.path.dirname(__file__), "abi", "IdentityRegistry.json")


def register_agent(private_key: str, *, agent_uri: str = "", network: str | None = None,
                   wait_timeout: float = 60.0) -> dict:
    """Register the caller as an ERC-8004 agent. Returns {agent_id, tx_hash, owner}.

    BROADCASTS a real transaction signed by `private_key` (the seller's wallet).
    """
    network = network or os.environ.get("X402_NETWORK", "eip155:84532")
    registry = IDENTITY_REGISTRY.get(network)
    if not registry:
        raise RuntimeError(f"no ERC-8004 Identity Registry known for network {network}")

    from eth_account import Account
    from web3 import Web3

    rpc = os.environ.get("X402_RPC_URL") or _RPC.get(network)
    if not rpc:
        raise RuntimeError(f"no RPC endpoint for {network}; set X402_RPC_URL")
    w3 = Web3(Web3.HTTPProvider(rpc))
    if not w3.is_connected():
        raise RuntimeError(f"cannot reach RPC {rpc} (network {network})")
    acct = Account.from_key(private_key)
    with open(_ABI_PATH, encoding="utf-8") as f:
        abi = json.load(f)
    contract = w3.eth.contract(address=Web3.to_checksum_address(registry), abi=abi)

    fn = contract.functions.register(agent_uri) if agent_uri else contract.functions.register()
    tx = fn.build_transaction({
        "from": acct.address,
        "nonce": w3.eth.get_transaction_count(acct.address, "pending"),
        "chainId": int(network.split(":")[1]),
    })
    signed = acct.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    rcpt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=wait_timeout)
    if int(rcpt.get("status", 0)) != 1:
        raise RuntimeError(f"registration tx reverted (status != 1): {tx_hash.hex()}")

    # agentId (tokenId) comes from the Registered event, not the tx return value.
    events = contract.events.Registered().process_receipt(rcpt)
    if not events:
        raise RuntimeError("registration mined but no Registered event found in receipt")
    agent_id = int(events[0]["args"]["agentId"])
    hexstr = tx_hash.hex()
    return {"agent_id": agent_id, "owner": acct.address,
            "tx_hash": hexstr if hexstr.startswith("0x") else "0x" + hexstr}
