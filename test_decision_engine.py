from core.decision_engine import evaluate_decision


def clean_params():
    return {
        "property": {
            "auction_limit": 100_000_000,
            "identity_verified": True,
            "legal_status": "Terverifikasi",
            "title_match": True,
            "dispute_detected": False,
            "occupancy_status": "Kosong dan terverifikasi",
            "occupancy_verified": True,
        },
        "fees": {"tax_rules_verified": True},
        "finance": {"funding_data_confirmed": True, "minimum_roi_pct": 20, "maximum_holding_months": 12},
        "risk_scores": {"liquidity": 4, "legal": 4, "possession": 4, "physical": 4, "funding": 4, "environment": 4},
    }


def test_critical_missing_data_forces_hold():
    params = clean_params()
    params["property"]["legal_status"] = "Belum terverifikasi"
    result = evaluate_decision(params, {"return_checks": {"cash_available_met": True}, "roi_pct": 25, "total_holding_months": 6}, 120_000_000, 130_000_000, {"count": 5, "confidence": 80})
    assert result["status"] == "HOLD"
    assert result["blockers"]


def test_no_go_when_limit_does_not_meet_financial_hurdle():
    params = clean_params()
    result = evaluate_decision(params, {"return_checks": {"cash_available_met": True}, "roi_pct": 5, "total_holding_months": 6}, None, None, {"count": 5, "confidence": 80})
    assert result["status"] == "NO-GO"
