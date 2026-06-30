"""Buyer agent orchestrator.

Phase 1 (now):   request + priorities -> select model -> show ranking -> MOCK call.
Phase 2 (next):  replace the mock call with payer.pay_and_call() (x402 + ERC-3009).

Usage:
  python -m agent.main --prompt "Write a binary search in Rust" --priority coding
  python -m agent.main --prompt "..." --priority cheap fast --live
"""
from __future__ import annotations

import argparse

from .catalog import Catalog
from .selector import Ranked, fetch_scores, select


def explain(ranked: list[Ranked]) -> str:
    lines = [f"{'model':<22} {'seller':<8} {'score':>6}  contributions"]
    for r in ranked:
        contrib = ", ".join(f"{k}={v:.2f}" for k, v in sorted(r.metric_contrib.items()))
        lines.append(f"{r.name:<22} {r.entry.seller:<8} {r.score:>6.3f}  {contrib}")
    return "\n".join(lines)


def run(prompt: str, priorities, use_live: bool = False) -> dict:
    catalog = Catalog.load()
    scores = fetch_scores(use_live=use_live)
    ranked = select(priorities, scores, catalog)
    if not ranked:
        raise SystemExit("No buyable model matched the catalog ∩ benchmark scores.")

    winner = ranked[0]
    print(f"Priorities: {priorities}")
    print(explain(ranked))
    print(f"\n=> SELECTED: {winner.name} via {winner.entry.seller} "
          f"(~{winner.entry.price_usdc_per_call} USDC/call)")

    # --- Phase 2 plugs in here ---
    # from .payer import pay_and_call
    # result = pay_and_call(winner.entry, prompt)
    result = f"[MOCK RESULT from {winner.entry.model_id}] (payer not wired yet — Phase 2)"
    print(f"\n--- Result ---\n{result}")
    return {"selected": winner.entry.aa_slug, "seller": winner.entry.seller, "result": result}


def main():
    ap = argparse.ArgumentParser(description="x402 AI purchasing agent (Phase 1: selection)")
    ap.add_argument("--prompt", required=True, help="the task to send to the chosen model")
    ap.add_argument("--priority", nargs="+", default=["balanced"],
                    help="one or more: intelligence coding agentic cheap fast balanced")
    ap.add_argument("--live", action="store_true", help="fetch live AA scores (needs AA_API_KEY)")
    args = ap.parse_args()
    run(args.prompt, args.priority, use_live=args.live)


if __name__ == "__main__":
    main()
