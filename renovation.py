"""Itemized renovation budget summaries."""
from __future__ import annotations
from typing import Any

CONFIDENCE_SCORE = {"Tinggi": 1.0, "Sedang": 0.65, "Rendah": 0.30}


def summarize_renovation_items(items: list[dict[str, Any]]) -> dict[str, Any]:
    total = 0.0
    weighted = 0.0
    low_confidence_cost = 0.0
    rows: list[dict[str, Any]] = []
    for item in items:
        try:
            amount = max(0.0, float(item.get("cost") or 0))
        except (TypeError, ValueError):
            amount = 0.0
        if amount <= 0:
            continue
        confidence = str(item.get("confidence") or "Rendah")
        score = CONFIDENCE_SCORE.get(confidence, 0.30)
        total += amount
        weighted += amount * score
        if confidence == "Rendah":
            low_confidence_cost += amount
        rows.append({**item, "cost": amount, "confidence_score": score})
    confidence_pct = weighted / total * 100 if total > 0 else 0.0
    return {
        "items": rows,
        "total_cost": total,
        "confidence_pct": round(confidence_pct, 1),
        "low_confidence_cost": low_confidence_cost,
        "low_confidence_share_pct": round(low_confidence_cost / total * 100, 1) if total > 0 else 0.0,
    }
