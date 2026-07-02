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
    """Same model, different sellers: cheapest ≠ fastest (price↔speed tradeoff).

    Compared among the Llama sellers specifically (other models may rank higher
    globally on a given axis — e.g. Gemini is faster overall)."""
    catalog, scores = _setup()

    def top_llama(priority):
        ranked = [r for r in select(priority, scores, catalog)
                  if r.entry.aa_slug == "llama-3.3-70b"]
        return ranked[0].entry.seller_id

    assert top_llama("cheap") == "gamma"   # cheapest Llama seller (slow)
    assert top_llama("fast") == "alpha"    # fastest Llama seller (priciest)
    assert top_llama("cheap") != top_llama("fast")


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
