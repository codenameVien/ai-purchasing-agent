"""Show the agent's spend summary (total + per seller/model). python scripts/spend.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agent.accounting import spend_summary

s = spend_summary()
print(f"total: {s['total_usdc']:.4f} USDC over {s['calls']} calls")
print("by seller:")
for k, v in sorted(s["by_seller"].items(), key=lambda x: -x[1]):
    print(f"  {k:16} {v:.4f}")
print("by model:")
for k, v in sorted(s["by_model"].items(), key=lambda x: -x[1]):
    print(f"  {k:16} {v:.4f}")
