"""Generate throwaway TESTNET wallets and write a ready-to-use .env.

Creates a fresh buyer keypair (signs payments) + a seller receiving address, and
writes them to .env (chmod 600, gitignored). Prints ONLY the addresses — the
private key goes to .env, never to stdout.

  python scripts/gen_wallet.py          # write .env (refuses to overwrite)
  python scripts/gen_wallet.py --force  # overwrite existing .env

SECURITY: these are disposable testnet wallets. NEVER put a MetaMask / mainnet /
funded personal key here — a private key controls ALL chains, so a leak is total
and irreversible. Fund only the printed BUYER address at https://faucet.circle.com.
"""
import os
import sys

from eth_account import Account

ROOT = os.path.dirname(os.path.dirname(__file__))
ENV = os.path.join(ROOT, ".env")


def main() -> int:
    if os.path.exists(ENV) and "--force" not in sys.argv:
        print(f".env already exists at {ENV} — pass --force to overwrite. Aborting.")
        return 1

    buyer = Account.create()
    seller = Account.create()
    lines = [
        "# auto-generated throwaway TESTNET wallets. NEVER commit. NEVER reuse a real key.",
        "X402_MODE=real",
        f"WALLET_PRIVATE_KEY={buyer.key.hex()}",
        "X402_NETWORK=eip155:84532",
        "X402_FACILITATOR_URL=https://x402.org/facilitator",
        f"X402_PAY_TO={seller.address}",
        "PROXY_PRICE=0.001",          # BARE number — a leading $ would be shell-expanded
        "PROXY_BACKEND=mock",
        "REPUTATION_MODE=mock",
        "MAX_USDC_PER_CALL=0.10",
        "MAX_USDC_PER_SESSION=1.00",
        "",
    ]
    with open(ENV, "w") as f:
        f.write("\n".join(lines))
    os.chmod(ENV, 0o600)

    print(f"wrote {ENV} (chmod 600, gitignored)")
    print(f"BUYER_ADDRESS  (FUND THIS at faucet.circle.com, Base Sepolia): {buyer.address}")
    print(f"SELLER_ADDRESS (receives; no funding needed)                 : {seller.address}")
    print("private key is in .env only — not printed here.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
