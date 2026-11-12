"""Weighted risk scoring; scores are 1 (poor) to 5 (good)."""
from __future__ import annotations
from typing import Any

RISK_WEIGHTS = {
    "liquidity": 25,
    "legal": 20,
    "possession": 20,
    "physical": 15,
    "funding": 15,
    "environment": 5,
}


def weighted_risk_score(scores: dict[str, Any]) -> float:
    total_weight = sum(RISK_WEIGHTS.values())
    return round(sum(max(1, min(5, int(scores.get(key, 3)))) * weight for key, weight in RISK_WEIGHTS.items()) / total_weight, 2)
