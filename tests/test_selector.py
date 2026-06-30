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
    # Best coding index (claude 3.7, 52) must win on 'coding'.
    assert coding_winner.entry.aa_slug == "claude-3-7-sonnet"
    assert cheap_winner.entry.aa_slug != coding_winner.entry.aa_slug


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
