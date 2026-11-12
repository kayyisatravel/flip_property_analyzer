"""Numerical maximum-bid search, separate from the financial calculator."""
from __future__ import annotations
from typing import Any
import math

from .calculator import calculate_project, _num


def find_maximum_bid(
    params: dict[str, Any],
    exit_price: float,
    *,
    minimum_bid: float | None = None,
    increment: float | None = None,
    risk_ceiling: float | None = None,
    require_cash: bool = True,
) -> dict[str, Any]:
    """Find the highest valid bid using integer-grid binary search.

    All conditions are treated as monotonic with bid price. `None` means even the
    minimum bid does not satisfy all requirements.
    """
    prop = params.get("property", {})
    limit = max(0.0, float(minimum_bid if minimum_bid is not None else _num(prop, "auction_limit")))
    step = max(1.0, float(increment if increment is not None else _num(params.get("finance", {}), "bid_increment", 1_000_000.0)))
    if limit <= 0 or exit_price <= 0:
        return {"maximum_bid": None, "reason": "Limit lelang dan harga jual harus lebih besar dari nol."}

    # Bid steps start at the actual auction limit; all candidate bids are rounded to the configured increment.
    if risk_ceiling is not None:
        high_price = min(max(exit_price * 3.0, limit), risk_ceiling)
    else:
        high_price = max(exit_price * 3.0, limit * 3.0, limit + 1_000_000_000.0)
    if high_price < limit:
        return {"maximum_bid": None, "reason": "Batas risiko berada di bawah limit lelang."}

    max_steps = max(0, int(math.floor((high_price - limit) / step)))

    def feasible(step_index: int) -> tuple[bool, dict[str, Any]]:
        bid = limit + step_index * step
        result = calculate_project(params, bid_price=bid, exit_price=exit_price)
        checks = result["return_checks"].copy()
        if not require_cash:
            checks["cash_available_met"] = True
            checks["all_financial_targets_met"] = all(v for k, v in checks.items() if k != "all_financial_targets_met")
        if risk_ceiling is not None and bid > risk_ceiling:
            return False, result
        return bool(checks["all_financial_targets_met"]), result

    ok0, result0 = feasible(0)
    if not ok0:
        return {
            "maximum_bid": None,
            "reason": "Limit lelang tidak memenuhi semua target ROI/profit/periode/kas pada skenario ini.",
            "at_limit": result0,
        }

    lo, hi = 0, max_steps
    best = result0
    while lo < hi:
        mid = (lo + hi + 1) // 2
        ok, candidate = feasible(mid)
        if ok:
            lo = mid
            best = candidate
        else:
            hi = mid - 1
    best_bid = limit + lo * step
    _, best = feasible(lo)
    return {"maximum_bid": best_bid, "result": best, "reason": "Batas tertinggi yang memenuhi semua target pada parameter saat ini."}
