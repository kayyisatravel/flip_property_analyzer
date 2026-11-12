from core.occupancy import compare_possession_scenarios
from tests.test_calculator import base_params


def test_mutually_exclusive_possession_scenarios_are_compared_not_summed():
    params = base_params()
    params["costs"]["possession_scenario_data"] = {"cost": 0, "delay_months": 0}
    scenarios = {
        "empty": {"key": "empty", "label": "A empty", "cost": 2_000_000, "delay_months": 0},
        "execution": {"key": "execution", "label": "D execution", "cost": 100_000_000, "delay_months": 12},
    }
    result = compare_possession_scenarios(params, 100_000_000, 200_000_000, scenarios, "empty")
    assert result["selected"]["scenario_key"] == "empty"
    assert result["worst_scenario_name"] == "D execution"
    assert result["incremental_reserve_to_worst_case"] == 98_000_000
    assert len(result["scenarios"]) == 2
