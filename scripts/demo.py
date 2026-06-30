"""End-to-end demo of the purchasing agent.

Prereq (Phase 2, mock): start the seller proxy in another terminal:
    X402_MODE=mock PROXY_BACKEND=mock uvicorn seller_proxy.main:app --port 8402

Then:  python scripts/demo.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agent.main import run

SCENARIOS = [
    ("Write a binary search in Rust", ["coding"]),
    ("Summarize this article in two lines", ["cheap", "fast"]),
    ("Plan a multi-step research task", ["agentic"]),
]

for prompt, priorities in SCENARIOS:
    print("=" * 70)
    print(f"REQUEST: {prompt!r}  priorities={priorities}")
    print("-" * 70)
    run(prompt, priorities)
    print()
