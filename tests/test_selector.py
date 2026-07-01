"""Phase 1 verification: selection is deterministic and priority-sensitive."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agent.catalog import Catalog
from agent.selector import fetch_scores, select, weights_from_priorities


def _setup():
    catalog = Catalog.load()
    scores = fetch_scores(use_live=False)
    return catalog, scores


def test_buyable_intersection_nonempty():
    catalog, scores = _setup()
    ranked = select("balanced", scores, catalog)
    assert ranked, "expected at least one buyable candidate"
    # every ranked model must be in the catalog
    assert all(r.entry is not None for r in ranked)


def test_priority_changes_winner():
    """Different top priority should be able to pick a different model."""
    catalog, scores = _setup()
    cheap_winner = select("cheap", scores, catalog)[0]
    coding_winner = select("coding", scores, catalog)[0]
    # Cheapest model (llama, $0.6) must win on 'cheap'.
    assert cheap_winner.entry.aa_slug == "llama-3.3-70b"
    # Best coding index (Opus 4.8, 60) must win on 'coding'.
    assert coding_winner.entry.aa_slug == "claude-opus-4-8"


def test_sellers_compete_on_price_vs_speed():
    """Same model, different sellers: cheapest ≠ fastest (price↔speed tradeoff)."""
    catalog, scores = _setup()
    cheap = select("cheap", scores, catalog)[0]
    fast = select("fast", scores, catalog)[0]
    # both are Llama offers but from different sellers
    assert cheap.entry.aa_slug == "llama-3.3-70b" and fast.entry.aa_slug == "llama-3.3-70b"
    assert cheap.entry.seller_id == "gamma"   # cheapest, slow
    assert fast.entry.seller_id == "alpha"    # priciest, fastest
    assert cheap.entry.seller_id != fast.entry.seller_id


def test_deterministic():
    catalog, scores = _setup()
    a = [r.entry.aa_slug for r in select("balanced", scores, catalog)]
    b = [r.entry.aa_slug for r in select("balanced", scores, catalog)]
    assert a == b


def test_weights_normalized():
    catalog, _ = _setup()
    w = weights_from_priorities(["coding", "cheap"], catalog)
    assert abs(sum(w.values()) - 1.0) < 1e-9
    assert set(w.keys()) == {"coding", "price"}


def test_unknown_priority_raises():
    catalog, _ = _setup()
    try:
        weights_from_priorities("nonsense-label", catalog)
    except ValueError:
        return
    raise AssertionError("expected ValueError for unknown priority")
