"""Spend accounting — record every payment so the agent's costs are auditable.

Each paid call appends to a local JSON ledger. `spend_summary()` rolls it up by
seller and model. (mock/testnet amounts; real accounting for production spend.)
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass

_LEDGER_PATH = os.environ.get(
    "SPEND_LEDGER",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "spend_ledger.json"),
)


@dataclass
class SpendRecord:
    seller_id: str
    aa_slug: str
    model_id: str
    amount_usdc: float
    tx_hash: str
    mock: bool


def _load(path: str) -> list[dict]:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def record_spend(seller_id: str, aa_slug: str, model_id: str, amount_usdc: float,
                 tx_hash: str, mock: bool, ledger_path: str | None = None) -> SpendRecord:
    """Append one payment to the spend ledger."""
    path = ledger_path or _LEDGER_PATH
    rec = SpendRecord(seller_id, aa_slug, model_id, amount_usdc, tx_hash, mock)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    ledger = _load(path)
    ledger.append(asdict(rec))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2)
    return rec


def spend_summary(ledger_path: str | None = None) -> dict:
    """Roll up total spend + per-seller + per-model."""
    path = ledger_path or _LEDGER_PATH
    ledger = _load(path)
    total = sum(r["amount_usdc"] for r in ledger)
    by_seller: dict[str, float] = {}
    by_model: dict[str, float] = {}
    for r in ledger:
        by_seller[r["seller_id"]] = by_seller.get(r["seller_id"], 0.0) + r["amount_usdc"]
        by_model[r["aa_slug"]] = by_model.get(r["aa_slug"], 0.0) + r["amount_usdc"]
    return {"total_usdc": total, "calls": len(ledger),
            "by_seller": by_seller, "by_model": by_model}
