"""Human 👍/👎 for a seller — the async quality signal that feeds reputation.

Machines don't judge quality here (circular/untrusted today). Instead the human
rates a seller AFTER the fact (Uber-star style, not a per-call gate), and that
feeds the same ERC-8004 reputation the agent reads on the next selection.

  python scripts/rate.py <seller_id> up      # 👍 -> reputation 1.0
  python scripts/rate.py <seller_id> down    # 👎 -> reputation 0.0
  python scripts/rate.py alpha down --reason "wrong model, slow"
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from reputation.feedback import give_feedback, load_reputation


def main() -> int:
    ap = argparse.ArgumentParser(description="Human thumbs up/down for a seller (feeds reputation)")
    ap.add_argument("seller_id", help="seller to rate (e.g. alpha, beta, anthropic-store)")
    ap.add_argument("rating", choices=["up", "down"], help="up = 👍, down = 👎")
    ap.add_argument("--reason", default="", help="optional note")
    args = ap.parse_args()

    score = 1.0 if args.rating == "up" else 0.0
    label = "human_good" if args.rating == "up" else "human_bad"
    reasons = [args.reason] if args.reason else [f"human {args.rating}"]

    fb = give_feedback(args.seller_id, score, label=label, reasons=reasons, source="human")
    emoji = "👍" if args.rating == "up" else "👎"
    print(f"{emoji} recorded for '{args.seller_id}' (source=human) | {fb.tx_hash}")

    rep = load_reputation().get(args.seller_id)
    if rep:
        print(f"   reputation now: {rep['rep']:.2f} over {rep['count']} feedback(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
