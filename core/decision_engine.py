"""Decision overlay. Hard-stop rules override weighted scores."""
from __future__ import annotations
from typing import Any

from .risk_engine import RISK_WEIGHTS, weighted_risk_score


def evaluate_decision(
    params: dict[str, Any],
    current_calculation: dict[str, Any],
    recommended_bid: float | None,
    absolute_maximum_bid: float | None,
    market_result: dict[str, Any],
) -> dict[str, Any]:
    prop = params.get("property", {})
    finance = params.get("finance", {})
    risk_scores = params.get("risk_scores", {})
    score = weighted_risk_score(risk_scores)
    reasons: list[str] = []
    blockers: list[str] = []
    warnings: list[str] = []

    if not prop.get("identity_verified", False):
        blockers.append("Identitas objek (alamat, LT/LB, nomor hak) belum dicocokkan dengan dokumen resmi.")
    if prop.get("legal_status", "Belum terverifikasi") != "Terverifikasi":
        blockers.append("Status legalitas belum berstatus Terverifikasi.")
    if not prop.get("title_match", False):
        blockers.append("Data fisik dan dokumen hak belum dinyatakan cocok.")
    if prop.get("dispute_detected", False):
        blockers.append("Ada indikasi sengketa/masalah hukum yang belum diselesaikan.")
    if prop.get("occupancy_status", "Belum diketahui") == "Belum diketahui":
        blockers.append("Status penguasaan/penghuni belum diketahui atau belum diverifikasi.")
    if not prop.get("occupancy_verified", False):
        blockers.append("Status penguasaan belum didukung verifikasi lapangan yang memadai.")
    if not params.get("fees", {}).get("tax_rules_verified", False):
        blockers.append("Aturan pajak/biaya untuk wilayah dan lot ini belum dikonfirmasi dengan sumber resmi yang berlaku.")

    if not finance.get("funding_data_confirmed", False):
        blockers.append("Kas, komitmen proyek, dan cadangan belum dikonfirmasi sebagai data aktual.")
    if market_result.get("count", 0) < 3:
        blockers.append("Pembanding pasar kurang dari 3 data yang dapat dipakai.")
    if market_result.get("confidence", 0) < 50:
        blockers.append("Confidence pembanding pasar di bawah 50/100.")

    limit = float(prop.get("auction_limit", 0) or 0)
    if recommended_bid is None or recommended_bid < limit:
        reasons.append("Pada skenario konservatif, limit lelang tidak memenuhi semua target finansial yang ditetapkan.")
    if absolute_maximum_bid is None or absolute_maximum_bid < limit:
        reasons.append("Pada skenario base, limit lelang tidak memenuhi target finansial atau kapasitas kas.")
    if not current_calculation.get("return_checks", {}).get("cash_available_met", False):
        warnings.append("Simulasi bid saat ini membutuhkan modal lebih besar daripada kas yang dialokasikan.")
    if current_calculation.get("roi_pct") is not None and current_calculation["roi_pct"] < float(finance.get("minimum_roi_pct", 20) or 0):
        warnings.append("ROI pada bid simulasi berada di bawah ROI minimum.")
    if current_calculation.get("total_holding_months", 0) > float(finance.get("maximum_holding_months", 12) or 12):
        warnings.append("Estimasi holding melewati batas waktu yang ditetapkan.")
    if not prop.get("interior_inspected", False):
        warnings.append("Interior belum diperiksa; gunakan allowance renovasi konservatif dan jangan menganggap kondisi interior aman dari foto fasad.")
    if prop.get("condition", "Tidak diketahui") == "Tidak diketahui":
        warnings.append("Kondisi fisik belum diklasifikasikan berdasarkan bukti lapangan.")

    if blockers:
        status = "HOLD"
        summary = "Data kritis belum cukup aman untuk keputusan bidding."
    elif recommended_bid is None or recommended_bid < limit or absolute_maximum_bid is None or absolute_maximum_bid < limit:
        status = "NO-GO"
        summary = "Limit lelang tidak memenuhi hurdle rate atau kapasitas kas pada parameter saat ini."
    elif score < 2.5:
        status = "HOLD"
        summary = "Skor risiko tertimbang terlalu rendah untuk melanjutkan tanpa mitigasi besar."
    elif score < 3.5 or warnings:
        status = "CONDITIONAL"
        summary = "Dapat dipertimbangkan hanya setelah syarat dan mitigasi yang tercantum diselesaikan."
    else:
        status = "GO"
        summary = "Parameter saat ini lolos pemeriksaan; tetap berhenti pada batas bid yang dihitung."

    if not reasons:
        reasons.append("Batas bid telah diuji terhadap profit minimum, ROI minimum, profit bulanan, periode holding, kapasitas kas, dan ceiling risiko bila berlaku.")
    return {
        "status": status,
        "summary": summary,
        "weighted_risk_score": score,
        "blockers": blockers,
        "warnings": warnings,
        "reasons": reasons,
        "risk_weights": RISK_WEIGHTS,
    }
