from core.maximum_bid import find_maximum_bid
from tests.test_calculator import base_params


def test_maximum_bid_satisfies_roi_and_cash_constraints():
    params = base_params()
    params["finance"]["cash_available"] = 180_000_000
    result = find_maximum_bid(params, exit_price=200_000_000, minimum_bid=100_000_000, increment=1_000_000)
    assert result["maximum_bid"] is not None
    assert result["maximum_bid"] % 1_000_000 == 0
    calc = result["result"]
    assert calc["roi_pct"] >= 20
    assert calc["pre_sale_investment"] <= calc["available_for_project"]


def test_maximum_bid_returns_none_when_even_limit_fails():
    params = base_params()
    params["finance"]["cash_available"] = 90_000_000
    result = find_maximum_bid(params, exit_price=200_000_000, minimum_bid=100_000_000, increment=1_000_000)
    assert result["maximum_bid"] is None


def test_risk_ceiling_limits_recommended_bid():
    params = base_params()
    result = find_maximum_bid(params, exit_price=200_000_000, minimum_bid=100_000_000, increment=1_000_000, risk_ceiling=130_000_000)
    assert result["maximum_bid"] == 130_000_000
