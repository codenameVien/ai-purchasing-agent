"""Benchmark-driven model selection.

Pipeline:
  1. fetch_scores()  -> per-model benchmark metrics (live Artificial Analysis API, or cached fixture)
  2. weights_from_priorities() -> weight vector from user priority labels
  3. select() -> rank buyable candidates by weighted, normalized score

The scoring is deterministic: same scores + same weights => same ranking.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import requests

from .catalog import Catalog, CatalogEntry

_CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")
_CACHE_PATH = os.path.join(_CONFIG_DIR, "scores_cache.json")

_AA_BASE = "https://artificialanalysis.ai/api/v2"
_AA_FREE_ENDPOINT = f"{_AA_BASE}/language/models/free"

# metric key -> (AA field name, higher_is_better)
_METRIC_FIELDS = {
    "intelligence": ("artificial_analysis_intelligence_index", True),
    "coding": ("artificial_analysis_coding_index", True),
    "agentic": ("artificial_analysis_agentic_index", True),
    "price": ("price_1m_blended_3_to_1", False),          # cheaper is better
    "speed": ("median_output_tokens_per_second", True),
}

# priority label (used by user / catalog presets) -> metric key
_PRIORITY_TO_METRIC = {
    "intelligence": "intelligence",
    "coding": "coding",
    "agentic": "agentic",
    "cheap": "price",
    "fast": "speed",
}


@dataclass
class ModelScore:
    slug: str
    name: str
    raw: dict[str, float]                 # metric_key -> raw value (may be missing)


@dataclass
class Ranked:
    entry: CatalogEntry
    name: str
    score: float
    metric_contrib: dict[str, float] = field(default_factory=dict)
    raw: dict[str, float] = field(default_factory=dict)


def fetch_scores(use_live: bool = False, api_key: str | None = None,
                 cache_path: str = _CACHE_PATH, timeout: float = 10.0) -> list[ModelScore]:
    """Return benchmark metrics per model.

    use_live=True hits the AA free endpoint (needs api_key). On any failure, or
    use_live=False, falls back to the cached fixture so Phase 1 runs offline.
    """
    payload = None
    if use_live:
        key = api_key or os.environ.get("AA_API_KEY")
        if key:
            try:
                resp = requests.get(_AA_FREE_ENDPOINT, headers={"x-api-key": key}, timeout=timeout)
                resp.raise_for_status()
                body = resp.json()
                payload = body.get("data", body.get("models", body))
            except Exception:
                payload = None  # graceful fallback to cache
    if payload is None:
        with open(cache_path, "r", encoding="utf-8") as f:
            payload = json.load(f)["models"]

    out: list[ModelScore] = []
    for m in payload:
        raw: dict[str, float] = {}
        for metric_key, (aa_field, _) in _METRIC_FIELDS.items():
            val = m.get(aa_field)
            if isinstance(val, (int, float)):
                raw[metric_key] = float(val)
        out.append(ModelScore(slug=m.get("slug", m.get("id", "")), name=m.get("name", ""), raw=raw))
    return out


def weights_from_priorities(priorities, catalog: Catalog) -> dict[str, float]:
    """Combine one or more priority labels into a normalized metric-weight vector.

    Accepts preset names (e.g. 'balanced', 'coding') and raw labels
    ('intelligence','coding','agentic','cheap','fast'). Multiple labels are summed.
    """
    if isinstance(priorities, str):
        priorities = [priorities]
    weights: dict[str, float] = {}
    for p in priorities:
        if p in catalog.priority_presets:
            for label, w in catalog.priority_presets[p].items():
                metric = _PRIORITY_TO_METRIC.get(label, label)
                weights[metric] = weights.get(metric, 0.0) + float(w)
        elif p in _PRIORITY_TO_METRIC:
            metric = _PRIORITY_TO_METRIC[p]
            weights[metric] = weights.get(metric, 0.0) + 1.0
        else:
            raise ValueError(f"unknown priority label: {p!r}")
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("priority weights sum to zero")
    return {k: v / total for k, v in weights.items()}


def _normalize(values: dict[str, float], higher_is_better: bool) -> dict[str, float]:
    """Min-max normalize a {slug: value} map to 0..1. Missing slugs handled by caller.

    If all values equal, every candidate gets 0.5 (neutral, avoids div-by-zero).
    """
    if not values:
        return {}
    lo, hi = min(values.values()), max(values.values())
    if hi == lo:
        return {k: 0.5 for k in values}
    out = {}
    for k, v in values.items():
        n = (v - lo) / (hi - lo)
        out[k] = n if higher_is_better else (1.0 - n)
    return out


def select(priorities, scores: list[ModelScore], catalog: Catalog) -> list[Ranked]:
    """Rank buyable candidates (catalog ∩ scores) by weighted normalized score."""
    weights = weights_from_priorities(priorities, catalog)
    buyable = catalog.buyable_slugs()
    candidates = [s for s in scores if s.slug in buyable]
    if not candidates:
        return []

    # Per-metric normalization across the candidate set only.
    normalized: dict[str, dict[str, float]] = {}
    for metric, weight in weights.items():
        if weight == 0:
            continue
        _, higher = _METRIC_FIELDS[metric]
        raw_vals = {c.slug: c.raw[metric] for c in candidates if metric in c.raw}
        normalized[metric] = _normalize(raw_vals, higher)

    ranked: list[Ranked] = []
    for c in candidates:
        contrib: dict[str, float] = {}
        total = 0.0
        for metric, weight in weights.items():
            n = normalized.get(metric, {}).get(c.slug)
            if n is None:
                continue  # model missing this metric -> contributes nothing
            contrib[metric] = weight * n
            total += contrib[metric]
        ranked.append(Ranked(
            entry=catalog.get(c.slug),
            name=c.name,
            score=total,
            metric_contrib=contrib,
            raw=c.raw,
        ))
    # Deterministic tie-break: score desc, then slug asc.
    ranked.sort(key=lambda r: (-r.score, r.entry.aa_slug))
    return ranked
