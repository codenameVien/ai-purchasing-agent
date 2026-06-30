"""Catalog: which benchmark models the agent can buy via x402, and from whom.

Selection candidates = intersection(AA benchmark scores, this catalog).
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import yaml

_CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")
_CATALOG_PATH = os.path.join(_CONFIG_DIR, "catalog.yaml")


@dataclass(frozen=True)
class CatalogEntry:
    aa_slug: str
    seller: str            # "heurist" | "proxy"
    seller_url: str
    model_id: str          # provider-side model id to send in the request
    price_usdc_per_call: float


class Catalog:
    def __init__(self, entries: dict[str, CatalogEntry], priority_presets: dict[str, dict[str, float]]):
        self.entries = entries
        self.priority_presets = priority_presets

    @classmethod
    def load(cls, path: str = _CATALOG_PATH) -> "Catalog":
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        entries = {
            m["aa_slug"]: CatalogEntry(
                aa_slug=m["aa_slug"],
                seller=m["seller"],
                seller_url=m["seller_url"],
                model_id=m["model_id"],
                price_usdc_per_call=float(m["price_usdc_per_call"]),
            )
            for m in raw.get("models", [])
        }
        presets = raw.get("priority_presets", {})
        return cls(entries, presets)

    def buyable_slugs(self) -> set[str]:
        return set(self.entries.keys())

    def get(self, slug: str) -> CatalogEntry | None:
        return self.entries.get(slug)
