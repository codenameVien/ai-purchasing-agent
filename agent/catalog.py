"""Catalog: the offers the agent can buy — each offer is a (seller × model) pair.

Multiple sellers may offer the SAME benchmark model (aa_slug) at different prices
and reputations (open models are resold by anyone). Selection picks the best
*offer*, not just the best model. Candidates = offers whose aa_slug has a score.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import yaml

_CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")
_CATALOG_PATH = os.path.join(_CONFIG_DIR, "catalog.yaml")


@dataclass(frozen=True)
class CatalogEntry:
    """One offer = a seller selling a specific model at a price."""
    aa_slug: str           # benchmark model id (maps to AA scores)
    seller_id: str         # unique seller identity — reputation is keyed on this
    seller: str            # seller kind, for display ("proxy" | "heurist" | ...)
    seller_url: str
    model_id: str          # provider-side model id sent in the request
    price_usdc_per_call: float
    backend: str = "mock"  # who fulfills inference: mock | heurist | openrouter_free | anthropic | openai
    speed_tps: float | None = None  # per-seller speed (tokens/s); overrides model's benchmark speed


class Catalog:
    def __init__(self, offers: list[CatalogEntry], priority_presets: dict[str, dict[str, float]]):
        self.offers = offers
        self.priority_presets = priority_presets

    @classmethod
    def load(cls, path: str = _CATALOG_PATH) -> "Catalog":
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        offers = [
            CatalogEntry(
                aa_slug=m["aa_slug"],
                seller_id=m["seller_id"],
                seller=m.get("seller", "proxy"),
                seller_url=m["seller_url"],
                model_id=m["model_id"],
                price_usdc_per_call=float(m["price_usdc_per_call"]),
                backend=m.get("backend", "mock"),
                speed_tps=(float(m["speed_tps"]) if m.get("speed_tps") is not None else None),
            )
            for m in raw.get("offers", [])
        ]
        presets = raw.get("priority_presets", {})
        return cls(offers, presets)

    def aa_slugs(self) -> set[str]:
        """Benchmark models present in the catalog (some may have multiple sellers)."""
        return {o.aa_slug for o in self.offers}

    def get(self, aa_slug: str) -> CatalogEntry | None:
        """First offer for a benchmark model (convenience; selection uses .offers)."""
        return next((o for o in self.offers if o.aa_slug == aa_slug), None)
