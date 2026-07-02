"""Register a seller as an ERC-8004 agent on-chain (Identity Registry) — the last
prerequisite for a REAL on-chain giveFeedback.

BROADCASTS a real transaction from SELLER_PRIVATE_KEY (needs a little testnet ETH
for gas). Testnet + disposable wallet ONLY. After it prints the agentId (tokenId),
map it so the buyer's feedback lands on the right agent:

  export SELLER_AGENT_IDS='{"<seller_id>": <agentId>}'

  python scripts/register_seller.py --seller gamma
  python scripts/register_seller.py --seller gamma --uri https://example.com/agent.json

The seller wallet must DIFFER from the buyer wallet (WALLET_PRIVATE_KEY): the
registry blocks self-feedback, so the buyer can't own the agent it rates.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from reputation.identity import register_agent


def main() -> int:
    ap = argparse.ArgumentParser(description="Register a seller on the ERC-8004 Identity Registry")
    ap.add_argument("--seller", required=True, help="human seller_id (for the printed mapping hint)")
    ap.add_argument("--uri", default="", help="optional agent metadata URI (agentURI)")
    ap.add_argument("--network", default=None, help="CAIP-2 network (default: X402_NETWORK or Base Sepolia)")
    args = ap.parse_args()

    key = os.environ.get("SELLER_PRIVATE_KEY")
    if not key:
        print("SELLER_PRIVATE_KEY not set. Run scripts/gen_wallet.py, then fund the SELLER "
              "address with a little Base Sepolia ETH for gas.", file=sys.stderr)
        return 1
    buyer = os.environ.get("WALLET_PRIVATE_KEY")
    if buyer:
        from eth_account import Account
        # compare derived addresses, not raw strings (0x-prefix/case differences)
        if Account.from_key(buyer.strip()).address == Account.from_key(key.strip()).address:
            print("SELLER_PRIVATE_KEY must differ from WALLET_PRIVATE_KEY (buyer) — the registry "
                  "blocks self-feedback, so the buyer cannot own the agent it rates.", file=sys.stderr)
            return 1

    print(f"Registering seller '{args.seller}' on-chain… (broadcasts a real tx)")
    res = register_agent(key, agent_uri=args.uri, network=args.network)
    print(f"✓ registered. agentId (tokenId) = {res['agent_id']}")
    print(f"  owner = {res['owner']}")
    print(f"  tx    = {res['tx_hash']}")
    print("\nNow map it so feedback targets this agent:")
    print(f"  export SELLER_AGENT_IDS='{{\"{args.seller}\": {res['agent_id']}}}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
