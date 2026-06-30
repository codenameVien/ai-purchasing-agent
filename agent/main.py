"""Buyer agent orchestrator.

Phase 1 (now):   request + priorities -> select model -> show ranking -> MOCK call.
Phase 2 (next):  replace the mock call with payer.pay_and_call() (x402 + ERC-3009).

Usage:
  python -m agent.main --prompt "Write a binary search in Rust" --priority coding
  python -m agent.main --prompt "..." --priority cheap fast --live
"""
from __future__ import annotations

import argparse
import os

from reputation.feedback import give_feedback

from .catalog import Catalog
from .judge import judge
from .payer import SpendGuard, SpendingError, pay_and_call
from .selector import Ranked, fetch_scores, select


def explain(ranked: list[Ranked]) -> str:
    lines = [f"{'model':<22} {'seller':<8} {'score':>6}  contributions"]
    for r in ranked:
        contrib = ", ".join(f"{k}={v:.2f}" for k, v in sorted(r.metric_contrib.items()))
        lines.append(f"{r.name:<22} {r.entry.seller:<8} {r.score:>6.3f}  {contrib}")
    return "\n".join(lines)


def run(prompt: str, priorities, use_live: bool = False,
        min_quality: float = 0.5, judge_mode: str = "heuristic") -> dict:
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

    # Pay-per-call via x402. In mock mode every seller is routed to the local
    # proxy (real Heurist needs real on-chain payment -> Phase A).
    mode = os.environ.get("X402_MODE", "mock")
    proxy_url = os.environ.get("X402_PROXY_URL", "http://localhost:8402/inference")
    url = proxy_url if mode == "mock" else None
    guard = SpendGuard.from_env()
    try:
        out = pay_and_call(winner.entry, prompt, guard, mode=mode, url=url)
    except SpendingError as e:
        raise SystemExit(f"payment refused by guardrail: {e}")

    receipt = out["receipt"]
    content = out["result"]["choices"][0]["message"]["content"]
    if receipt:
        tag = "MOCK tx" if receipt.mock else "tx"
        print(f"\n[paid {receipt.paid_usdc} USDC | {tag} {receipt.tx_hash}]")
    print(f"\n--- Result ---\n{content}")

    # Judge the result; record ERC-8004 reputation feedback if it was bad.
    verdict = judge(prompt, content, mode=judge_mode, min_acceptable=min_quality)
    print(f"\n[quality: {verdict.label} {verdict.score:.2f}"
          + (f" — {', '.join(verdict.reasons)}" if verdict.reasons else "") + "]")
    feedback = None
    if verdict.is_bad:
        agent_id = f"{winner.entry.seller}:{winner.entry.model_id}"
        feedback = give_feedback(agent_id, verdict.score, label="bad", reasons=verdict.reasons)
        tag = "MOCK fb tx" if feedback.mock else "fb tx"
        print(f"[reputation: ERC-8004 giveFeedback recorded for {agent_id} | {tag} {feedback.tx_hash}]")

    return {"selected": winner.entry.aa_slug, "seller": winner.entry.seller,
            "result": content, "receipt": receipt, "verdict": verdict, "feedback": feedback}


def main():
    ap = argparse.ArgumentParser(description="x402 AI purchasing agent (Phase 1: selection)")
    ap.add_argument("--prompt", required=True, help="the task to send to the chosen model")
    ap.add_argument("--priority", nargs="+", default=["balanced"],
                    help="one or more: intelligence coding agentic cheap fast balanced")
    ap.add_argument("--live", action="store_true", help="fetch live AA scores (needs AA_API_KEY)")
    ap.add_argument("--min-quality", type=float, default=0.5,
                    help="below this score the result is judged bad -> reputation feedback")
    ap.add_argument("--judge", default="heuristic", choices=["heuristic", "llm"])
    args = ap.parse_args()
    run(args.prompt, args.priority, use_live=args.live,
        min_quality=args.min_quality, judge_mode=args.judge)


if __name__ == "__main__":
    main()
