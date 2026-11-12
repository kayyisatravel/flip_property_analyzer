"""Deterministic financial model for auction property flipping.

All monetary amounts are IDR. Tax/fee rates are user-editable assumptions, not legal advice.
"""
from __future__ import annotations

from typing import Any
import math

from .tax_rules import calculate_bphtb


def _num(data: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        value = float(data.get(key, default) or 0)
        return value if math.isfinite(value) else default
    except (TypeError, ValueError):
        return default


def calculate_project(
    params: dict[str, Any],
    bid_price: float | None = None,
    exit_price: float | None = None,
    possession_scenario: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Calculate project costs, net profit and returns without double-counting sale costs.

    `pre_sale_investment` contains acquisition and all pre-exit costs. Selling costs are
    deducted once from proceeds, and `total_project_cost_including_sale` is provided for
    a full cost view only.
    """
    prop = params.get("property", {})
    fees = params.get("fees", {})
    costs = params.get("costs", {})
    finance = params.get("finance", {})
    market = params.get("market", {})

    bid = max(0.0, float(bid_price if bid_price is not None else _num(params, "simulated_bid", _num(prop, "auction_limit"))))
    exit_value = max(0.0, float(exit_price if exit_price is not None else _num(market, "base_exit")))

    auction_fee = bid * _num(fees, "buyer_auction_fee_pct") / 100.0
    bphtb_tax_base, bphtb = calculate_bphtb(
        bid_price=bid,
        njop=_num(prop, "njop"),
        rate_pct=_num(fees, "bphtb_rate_pct"),
        npoptkp=_num(fees, "npoptkp"),
        basis_mode=str(fees.get("bphtb_basis_mode", "Harga bid")),
    )

    ppn_applicable = bool(fees.get("ppn_applicable", False))
    ppn = bid * _num(fees, "ppn_rate_pct") / 100.0 if ppn_applicable else 0.0

    certificate_legal = max(0.0, _num(costs, "certificate_legal_cost"))
    renovation = max(0.0, _num(costs, "renovation_cost"))
    misc_presale = max(0.0, _num(costs, "other_presale_cost"))
    arrears_cost = max(0.0, _num(costs, "arrears_utilities_cost"))
    holding_monthly = max(0.0, _num(costs, "monthly_holding_cost"))
    target_sale_months = max(0.0, _num(costs, "sale_months_after_ready", 3.0))
    renovation_months = max(0.0, _num(costs, "renovation_months", 2.0))

    scenario = possession_scenario or costs.get("possession_scenario_data", {}) or {}
    possession_cost = max(0.0, _num(scenario, "cost"))
    possession_delay_months = max(0.0, _num(scenario, "delay_months"))
    total_holding_months = target_sale_months + renovation_months + possession_delay_months
    holding_cost = holding_monthly * total_holding_months

    contingency_pct = max(0.0, _num(costs, "contingency_pct")) / 100.0
    contingency_basis = renovation + certificate_legal + misc_presale + arrears_cost + possession_cost + holding_cost
    contingency = contingency_basis * contingency_pct

    acquisition = bid + auction_fee + bphtb + ppn
    pre_sale_investment = acquisition + certificate_legal + renovation + misc_presale + arrears_cost + possession_cost + holding_cost + contingency
    annual_opportunity_cost_pct = max(0.0, _num(finance, "annual_opportunity_cost_pct"))
    opportunity_cost = pre_sale_investment * (annual_opportunity_cost_pct / 100.0) * (total_holding_months / 12.0)

    agent_cost = exit_value * max(0.0, _num(fees, "selling_agent_pct")) / 100.0
    seller_tax_cost = exit_value * max(0.0, _num(fees, "seller_tax_pct")) / 100.0
    marketing_cost = max(0.0, _num(costs, "marketing_cost"))
    other_selling_cost = max(0.0, _num(costs, "other_selling_cost"))
    selling_cost = agent_cost + seller_tax_cost + marketing_cost + other_selling_cost

    net_proceeds = exit_value - selling_cost
    cash_net_profit = net_proceeds - pre_sale_investment
    net_profit = cash_net_profit - opportunity_cost
    roi_pct = (net_profit / pre_sale_investment * 100.0) if pre_sale_investment > 0 else None
    cash_roi_pct = (cash_net_profit / pre_sale_investment * 100.0) if pre_sale_investment > 0 else None
    profit_per_month = net_profit / total_holding_months if total_holding_months > 0 else None
    annualized_roi_pct = ((1.0 + roi_pct / 100.0) ** (12.0 / total_holding_months) - 1.0) * 100.0 if roi_pct is not None and total_holding_months > 0 and (1.0 + roi_pct / 100.0) > 0 else None

    actual_cash = max(0.0, _num(finance, "cash_available"))
    committed = max(0.0, _num(finance, "ongoing_project_commitments"))
    household_reserve = max(0.0, _num(finance, "household_operating_reserve"))
    mandatory_risk_reserve = max(0.0, _num(finance, "mandatory_risk_reserve"))
    available_for_project = max(0.0, actual_cash - committed - household_reserve - mandatory_risk_reserve)
    cash_surplus = available_for_project - pre_sale_investment

    required_profit = max(0.0, _num(finance, "minimum_net_profit"))
    required_roi = max(0.0, _num(finance, "minimum_roi_pct", 20.0))
    required_profit_month = max(0.0, _num(finance, "minimum_profit_per_month"))
    max_holding_months = max(0.0, _num(finance, "maximum_holding_months", 12.0))
    return_checks = {
        "minimum_profit_met": net_profit >= required_profit,
        "minimum_roi_met": roi_pct is not None and roi_pct >= required_roi,
        "minimum_monthly_profit_met": profit_per_month is not None and profit_per_month >= required_profit_month,
        "maximum_holding_period_met": total_holding_months <= max_holding_months if max_holding_months > 0 else True,
        "cash_available_met": pre_sale_investment <= available_for_project,
    }
    return_checks["all_financial_targets_met"] = all(return_checks.values())

    return {
        "bid_price": bid,
        "exit_price": exit_value,
        "auction_fee": auction_fee,
        "bphtb_tax_base": bphtb_tax_base,
        "bphtb": bphtb,
        "ppn": ppn,
        "acquisition_cost": acquisition,
        "certificate_legal_cost": certificate_legal,
        "renovation_cost": renovation,
        "possession_cost": possession_cost,
        "possession_delay_months": possession_delay_months,
        "monthly_holding_cost": holding_monthly,
        "total_holding_months": total_holding_months,
        "holding_cost": holding_cost,
        "other_presale_cost": misc_presale,
        "arrears_utilities_cost": arrears_cost,
        "contingency": contingency,
        "pre_sale_investment": pre_sale_investment,
        "opportunity_cost": opportunity_cost,
        "cash_net_profit": cash_net_profit,
        "cash_roi_pct": cash_roi_pct,
        "agent_cost": agent_cost,
        "seller_tax_cost": seller_tax_cost,
        "marketing_cost": marketing_cost,
        "other_selling_cost": other_selling_cost,
        "selling_cost": selling_cost,
        "net_proceeds": net_proceeds,
        "total_project_cost_including_sale": pre_sale_investment + opportunity_cost + selling_cost,
        "net_profit": net_profit,
        "roi_pct": roi_pct,
        "profit_per_month": profit_per_month,
        "annualized_roi_pct": annualized_roi_pct,
        "cash_actual": actual_cash,
        "cash_committed": committed,
        "household_reserve": household_reserve,
        "mandatory_risk_reserve": mandatory_risk_reserve,
        "available_for_project": available_for_project,
        "cash_surplus": cash_surplus,
        "return_checks": return_checks,
    }


