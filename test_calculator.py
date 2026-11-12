from core.calculator import calculate_project


def base_params():
    return {
        "property": {"auction_limit": 100_000_000, "njop": 0},
        "fees": {
            "buyer_auction_fee_pct": 0,
            "bphtb_rate_pct": 0,
            "npoptkp": 0,
            "bphtb_basis_mode": "Harga bid",
            "ppn_applicable": False,
            "ppn_rate_pct": 0,
            "selling_agent_pct": 0,
            "seller_tax_pct": 0,
        },
        "costs": {
            "certificate_legal_cost": 0,
            "renovation_cost": 0,
            "other_presale_cost": 0,
            "contingency_pct": 0,
            "monthly_holding_cost": 0,
            "renovation_months": 0,
            "sale_months_after_ready": 3,
            "marketing_cost": 0,
            "other_selling_cost": 0,
            "possession_scenario_data": {"cost": 0, "delay_months": 0},
        },
        "finance": {
            "cash_available": 500_000_000,
            "ongoing_project_commitments": 0,
            "household_operating_reserve": 0,
            "mandatory_risk_reserve": 0,
            "minimum_net_profit": 0,
            "minimum_roi_pct": 20,
            "minimum_profit_per_month": 0,
            "maximum_holding_months": 12,
        },
    }


def test_profit_and_roi_are_consistent():
    params = base_params()
    result = calculate_project(params, bid_price=100_000_000, exit_price=200_000_000)
    assert result["pre_sale_investment"] == 100_000_000
    assert result["net_proceeds"] == 200_000_000
    assert result["net_profit"] == 100_000_000
    assert result["roi_pct"] == 100.0


def test_selling_cost_is_not_double_counted():
    params = base_params()
    params["fees"]["selling_agent_pct"] = 10
    result = calculate_project(params, bid_price=100_000_000, exit_price=200_000_000)
    assert result["selling_cost"] == 20_000_000
    assert result["net_proceeds"] == 180_000_000
    assert result["pre_sale_investment"] == 100_000_000
    assert result["net_profit"] == 80_000_000
    assert result["total_project_cost_including_sale"] == 120_000_000


def test_bphtb_uses_selected_basis_and_npoptkp():
    params = base_params()
    params["fees"].update({"bphtb_rate_pct": 5, "npoptkp": 60_000_000, "bphtb_basis_mode": "Maksimum harga bid dan NJOP"})
    params["property"]["njop"] = 150_000_000
    result = calculate_project(params, bid_price=100_000_000, exit_price=200_000_000)
    assert result["bphtb_tax_base"] == 150_000_000
    assert result["bphtb"] == 4_500_000


def test_cash_available_subtracts_reserves_and_commitments():
    params = base_params()
    params["finance"].update({"cash_available": 200_000_000, "ongoing_project_commitments": 20_000_000, "household_operating_reserve": 30_000_000, "mandatory_risk_reserve": 10_000_000})
    result = calculate_project(params, bid_price=100_000_000, exit_price=200_000_000)
    assert result["available_for_project"] == 140_000_000


def test_opportunity_cost_is_separate_from_cash_requirement():
    params = base_params()
    params["finance"]["annual_opportunity_cost_pct"] = 12
    result = calculate_project(params, bid_price=100_000_000, exit_price=200_000_000)
    assert result["opportunity_cost"] == 3_000_000
    assert result["cash_net_profit"] == 100_000_000
    assert result["net_profit"] == 97_000_000
    # Opportunity cost is economic, not an additional cash outflow needed to fund the project.
    assert result["pre_sale_investment"] == 100_000_000


def test_arrears_and_contingency_are_included_in_cash_requirement():
    params = base_params()
    params["costs"].update({"arrears_utilities_cost": 10_000_000, "contingency_pct": 10})
    result = calculate_project(params, bid_price=100_000_000, exit_price=200_000_000)
    # 10% contingency on the 10m arrears plus zero other non-acquisition costs.
    assert result["arrears_utilities_cost"] == 10_000_000
    assert result["contingency"] == 1_000_000
    assert result["pre_sale_investment"] == 111_000_000
