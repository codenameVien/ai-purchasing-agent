"""Discover offers from a marketplace endpoint instead of a hardcoded catalog.

The buyer asks the market "what's for sale right now?" (GET /marketplace) and
builds its candidate set live. Priority presets stay local (they're agent config,
not market data). `get` is injectable for testing.
"""
from __future__ import annotations

import requests

from .catalog import Catalog, CatalogEntry


def discover_catalog(url: str, *, get=requests.get, timeout: float = 10.0) -> Catalog:
    """Fetch offers from a /marketplace endpoint and return a Catalog."""
    resp = get(url, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    offers = [
        CatalogEntry(
            aa_slug=o["aa_slug"],
            seller_id=o["seller_id"],
            seller=o.get("seller", "proxy"),
            seller_url=o["seller_url"],
            model_id=o["model_id"],
            price_usdc_per_call=float(o["price_usdc_per_call"]),
            backend=o.get("backend", "mock"),
            speed_tps=(float(o["speed_tps"]) if o.get("speed_tps") is not None else None),
        )
        for o in data.get("offers", [])
    ]
    presets = Catalog.load().priority_presets       # presets stay local (agent config)
    return Catalog(offers, presets)
