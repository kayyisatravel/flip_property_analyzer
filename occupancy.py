"""Compare alternative possession scenarios without summing mutually exclusive costs."""
from __future__ import annotations
from typing import Any

from .calculator import calculate_project


def compare_possession_scenarios(
    params: dict[str, Any], bid_price: float, exit_price: float, scenarios: dict[str, dict[str, Any]], selected_key: str
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for key, scenario in scenarios.items():
        calc = calculate_project(params, bid_price=bid_price, exit_price=exit_price, possession_scenario=scenario)
        results.append({
            "scenario_key": key,
            "scenario_name": scenario.get("label", key),
            "possession_cost": calc["possession_cost"],
            "delay_months": calc["possession_delay_months"],
            "total_holding_months": calc["total_holding_months"],
            "cash_investment_before_sale": calc["pre_sale_investment"],
            "net_profit_after_opportunity_cost": calc["net_profit"],
            "roi_pct": calc["roi_pct"],
            "cash_available_met": calc["return_checks"]["cash_available_met"],
        })
    worst = max(results, key=lambda row: row["cash_investment_before_sale"]) if results else None
    selected = next((row for row in results if row["scenario_key"] == selected_key), None)
    selected_cash = selected["cash_investment_before_sale"] if selected else 0.0
    worst_cash = worst["cash_investment_before_sale"] if worst else 0.0
    return {
        "scenarios": results,
        "selected": selected,
        "worst_reasonable_capital_requirement": worst_cash,
        "worst_scenario_name": worst["scenario_name"] if worst else None,
        "incremental_reserve_to_worst_case": max(0.0, worst_cash - selected_cash),
    }
