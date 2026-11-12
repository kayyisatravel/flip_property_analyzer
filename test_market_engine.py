from datetime import date
from core.market_engine import estimate_market_range, score_comparable


def make_comp(i=0):
    return {
        "complex": "Kompleks A",
        "address": f"Blok {i}",
        "distance_km": 0.5,
        "land_area": 90,
        "building_area": 60,
        "price": 300_000_000 + i * 10_000_000,
        "price_type": "Transaksi terverifikasi",
        "condition": "Siap huni",
        "certificate": "SHM",
        "date_found": date.today().isoformat(),
        "source_url": f"https://example.com/{i}",
    }


def test_same_complex_and_size_comparable_scores_well():
    subject = {"complex": "Kompleks A", "land_area": 90, "building_area": 60, "condition": "Siap huni", "certificate": "SHM"}
    score = score_comparable(make_comp(), subject)["quality_score"]
    assert score >= 75


def test_market_confidence_accounts_for_number_of_comps():
    subject = {"complex": "Kompleks A", "land_area": 90, "building_area": 60, "condition": "Siap huni", "certificate": "SHM"}
    one = estimate_market_range([make_comp()], subject)
    five = estimate_market_range([make_comp(i) for i in range(5)], subject)
    assert one["confidence"] < five["confidence"]
    assert five["count"] == 5
    assert five["conservative_exit"] < five["base_exit"] < five["optimistic_exit"]
