"""Probe a REAL x402 seller's 402 response — read-only, no wallet, no payment.

Proves the buyer agent parses a genuine x402 PaymentRequirements envelope from a
live third-party seller (not just our mock proxy). We deliberately send NO payment,
so nothing is ever charged. Also surfaces the x402 protocol version the seller
advertises (Heurist Mesh currently serves v1; our paying client targets v2).

Run:  python scripts/probe_real_402.py
"""
import json
import sys

import requests

# A real, live x402-gated Heurist Mesh tool (Base MAINNET seller). We only read its
# 402; we never pay it. Discovery list (free): https://mesh.heurist.xyz/x402/agents
RESOURCE = "https://mesh.heurist.xyz/x402/agents/AIXBTProjectInfoAgent/get_market_summary"


def main() -> int:
    print(f"POST (no payment) -> {RESOURCE}")
    try:
        r = requests.post(RESOURCE, json={}, timeout=20)
    except requests.RequestException as e:
        print(f"network error (probe needs internet): {e}")
        return 2

    print(f"status: {r.status_code}  (expect 402 Payment Required)")
    if r.status_code != 402:
        print("unexpected — seller did not return 402; body:", r.text[:300])
        return 1

    body = r.json()
    accepts = body.get("accepts", [])
    print(f"x402Version advertised: {body.get('x402Version')}  "
          f"(our paying client targets v2 — note any mismatch)")
    if not accepts:
        print("no 'accepts' array — parsing assumption broken:", json.dumps(body)[:300])
        return 1

    a = accepts[0]
    print("\nour payer reads these PaymentRequirements fields:")
    for k in ("scheme", "network", "asset", "payTo", "maxAmountRequired", "maxTimeoutSeconds"):
        print(f"  {k:18}= {a.get(k)}")
    print("\nOK — buyer parses a real third-party x402 402 envelope. "
          "(This seller is Base MAINNET; paying it needs real USDC, so we stop here.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
