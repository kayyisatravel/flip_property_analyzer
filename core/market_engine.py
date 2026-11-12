"""Comparable scoring and price range estimation (heuristic, transparent)."""
from __future__ import annotations
from datetime import date, datetime
from statistics import median
from typing import Any


def _float(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        x = float(value)
        if x != x or x in (float("inf"), float("-inf")):
            return default
        return x if x >= 0 else default
    except (ValueError, TypeError):
        return default


def _date_age_days(value: Any) -> int | None:
    if not value:
        return None
    try:
        if isinstance(value, datetime):
            d = value.date()
        elif isinstance(value, date):
            d = value
        else:
            d = date.fromisoformat(str(value)[:10])
        return max(0, (date.today() - d).days)
    except (ValueError, TypeError):
        return None


def score_comparable(comp: dict[str, Any], subject: dict[str, Any]) -> dict[str, Any]:
    """Return an initial 0-100 comparable score using the agreed weight model."""
    score = 0.0
    reasons: list[str] = []
    subject_complex = str(subject.get("complex", "")).strip().lower()
    comp_complex = str(comp.get("complex", "")).strip().lower()
    if subject_complex and comp_complex and subject_complex == comp_complex:
        score += 25
        reasons.append("Kompleks sama +25")

    distance = _float(comp.get("distance_km"), -1)
    if distance >= 0:
        distance_points = 15 * max(0.0, 1.0 - distance / 15.0)
        score += distance_points
        reasons.append(f"Kedekatan lokasi +{distance_points:.1f}")

    for field, weight, label in [("land_area", 10, "LT"), ("building_area", 15, "LB")]:
        target = _float(subject.get(field))
        other = _float(comp.get(field))
        if target > 0 and other > 0:
            value = weight * max(0.0, 1.0 - abs(target - other) / target)
            score += value
            reasons.append(f"Kemiripan {label} +{value:.1f}")

    subj_cond = str(subject.get("condition", "")).lower().strip()
    comp_cond = str(comp.get("condition", "")).lower().strip()
    if subj_cond and comp_cond and subj_cond != "tidak diketahui" and comp_cond != "tidak diketahui":
        condition_points = 10 if subj_cond == comp_cond else 5 if any(w in subj_cond and w in comp_cond for w in ["kosmetik", "renovasi", "rusak", "siap huni"]) else 2
        score += condition_points
        reasons.append(f"Kondisi +{condition_points}")

    subj_type = str(subject.get("property_type", "")).lower().strip()
    comp_type = str(comp.get("property_type", "")).lower().strip()
    if subj_type and comp_type and subj_type != "tidak diketahui" and comp_type != "tidak diketahui":
        type_points = 5 if subj_type == comp_type else 2
        score += type_points
        reasons.append(f"Tipe/karakter rumah +{type_points}")

    subj_cert = str(subject.get("certificate", "")).lower().strip()
    comp_cert = str(comp.get("certificate", "")).lower().strip()
    if subj_cert and comp_cert and subj_cert != "belum diketahui" and comp_cert != "tidak diketahui":
        cert_points = 5 if subj_cert == comp_cert else 1
        score += cert_points
        reasons.append(f"Status hak +{cert_points}")

    price_type = str(comp.get("price_type", "Listing aktif")).lower()
    if "transaksi terverifikasi" in price_type:
        source_points = 10
    elif "terjual" in price_type or "marked sold" in price_type:
        source_points = 7
    elif "lelang" in price_type:
        source_points = 5
    elif "developer" in price_type:
        source_points = 5
    elif "listing aktif" in price_type or "asking" in price_type:
        source_points = 4
    else:
        source_points = 2
    score += source_points
    reasons.append(f"Keandalan/status harga +{source_points}")

    age = _date_age_days(comp.get("date_found"))
    if age is not None:
        freshness_points = 5 * max(0.0, 1.0 - age / 365.0)
        score += freshness_points
        reasons.append(f"Kebaruan data +{freshness_points:.1f}")
    score = max(0.0, min(100.0, score))
    return {"quality_score": round(score, 1), "score_reasons": reasons}


def adjusted_comparables(comparables: list[dict[str, Any]], subject: dict[str, Any]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    target_lt = _float(subject.get("land_area"))
    target_lb = _float(subject.get("building_area"))
    for raw in comparables:
        comp = dict(raw)
        price = _float(comp.get("price"))
        if price <= 0:
            continue
        scored = score_comparable(comp, subject)
        comp.update(scored)
        lt = _float(comp.get("land_area"))
        lb = _float(comp.get("building_area"))
        # Moderated size adjustment: land dominates, building has a smaller exponent.
        lt_factor = (target_lt / lt) ** 0.50 if target_lt > 0 and lt > 0 else 1.0
        lb_factor = (target_lb / lb) ** 0.20 if target_lb > 0 and lb > 0 else 1.0
        comp["adjusted_price"] = price * lt_factor * lb_factor
        typ = str(comp.get("price_type", "Listing aktif")).lower()
        evidence_multiplier = 1.5 if "transaksi terverifikasi" in typ else 1.15 if ("terjual" in typ or "marked sold" in typ) else 0.85 if ("listing aktif" in typ or "asking" in typ) else 1.0
        comp["analysis_weight"] = max(0.1, comp["quality_score"] * evidence_multiplier)
        output.append(comp)
    return output


def weighted_median(values: list[tuple[float, float]]) -> float | None:
    valid = [(float(v), max(0.0, float(w))) for v, w in values if v > 0 and w > 0]
    if not valid:
        return None
    valid.sort(key=lambda pair: pair[0])
    total = sum(w for _, w in valid)
    running = 0.0
    for value, weight in valid:
        running += weight
        if running >= total / 2.0:
            return value
    return valid[-1][0]


def estimate_market_range(
    comparables: list[dict[str, Any]], subject: dict[str, Any], conservative_haircut_pct: float = 10.0, optimistic_premium_pct: float = 10.0
) -> dict[str, Any]:
    scored = adjusted_comparables(comparables, subject)
    if not scored:
        return {"comparables": [], "count": 0, "base_exit": None, "conservative_exit": None, "optimistic_exit": None, "confidence": 0.0, "median_raw_price": None}
    base = weighted_median([(c["adjusted_price"], c["analysis_weight"]) for c in scored])
    avg_quality = sum(c["quality_score"] for c in scored) / len(scored)
    coverage_factor = min(1.0, len(scored) / 5.0)
    # A small number of comps should visibly lower confidence.
    confidence = round(avg_quality * coverage_factor, 1)
    haircut = max(0.0, min(50.0, conservative_haircut_pct)) / 100.0
    premium = max(0.0, min(50.0, optimistic_premium_pct)) / 100.0
    raw_prices = [c["price"] for c in scored]
    return {
        "comparables": scored,
        "count": len(scored),
        "base_exit": round(base) if base is not None else None,
        "conservative_exit": round(base * (1 - haircut)) if base is not None else None,
        "optimistic_exit": round(base * (1 + premium)) if base is not None else None,
        "confidence": confidence,
        "median_raw_price": median(raw_prices),
    }
