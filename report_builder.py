"""Export-friendly Markdown investment memo."""
from __future__ import annotations
from typing import Any


def idr(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return "Rp" + f"{float(value):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return str(value)


def build_markdown_report(payload: dict[str, Any]) -> str:
    prop = payload.get("property", {})
    calc = payload.get("current_calculation", {})
    decision = payload.get("decision", {})
    market = payload.get("market", {})
    bids = payload.get("bid_analysis", {})
    rows = [
        f"# Investment Memo — {prop.get('name') or 'Objek rumah lelang'}",
        "",
        f"**Tanggal analisis:** {payload.get('analysis_date', '—')}",
        f"**Lokasi:** {prop.get('address') or 'Belum diisi'}",
        f"**Link/kode lot:** {prop.get('auction_url') or '—'} / {prop.get('lot_code') or '—'}",
        f"**Keputusan:** {decision.get('status', 'HOLD')} — {decision.get('summary', '')}",
        "",
        "## Ringkasan finansial",
        f"- Limit lelang: {idr(prop.get('auction_limit'))}",
        f"- Bid simulasi: {idr(calc.get('bid_price'))}",
        f"- Harga jual konservatif/base/optimistis: {idr(market.get('conservative_exit'))} / {idr(market.get('base_exit'))} / {idr(market.get('optimistic_exit'))}",
        f"- Total modal sebelum penjualan: {idr(calc.get('pre_sale_investment'))}",
        f"- Biaya penjualan (dipotong sekali dari proceeds): {idr(calc.get('selling_cost'))}",
        f"- Biaya kesempatan modal (bukan cash outflow): {idr(calc.get('opportunity_cost'))}",
        f"- Modal proyek ekonomis termasuk biaya penjualan: {idr(calc.get('total_project_cost_including_sale'))}",
        f"- Profit bersih setelah biaya kesempatan modal: {idr(calc.get('net_profit'))}",
        f"- Profit kas sebelum biaya kesempatan modal: {idr(calc.get('cash_net_profit'))}",
        f"- ROI atas modal sebelum penjualan: {calc.get('roi_pct') if calc.get('roi_pct') is not None else '—'}%",
        f"- Profit rata-rata per bulan: {idr(calc.get('profit_per_month'))}",
        f"- Perkiraan holding: {calc.get('total_holding_months', '—')} bulan",
        f"- Recommended ceiling (skenario konservatif): {idr(bids.get('recommended_ceiling'))}",
        f"- Absolute maximum (skenario base): {idr(bids.get('absolute_maximum'))}",
        "",
        "## Rincian modal",
    ]
    for label, key in [
        ("Harga bid", "bid_price"), ("Bea lelang pembeli", "auction_fee"), ("BPHTB", "bphtb"),
        ("PPN bila berlaku", "ppn"), ("Legal/sertifikat", "certificate_legal_cost"),
        ("Renovasi", "renovation_cost"), ("Tunggakan/utilitas", "arrears_utilities_cost"), ("Penguasaan/kerahiman", "possession_cost"),
        ("Holding cost", "holding_cost"), ("Contingency", "contingency"), ("Biaya kesempatan modal", "opportunity_cost"),
        ("Biaya agen", "agent_cost"), ("Pajak penjual asumsi input", "seller_tax_cost"),
    ]:
        rows.append(f"- {label}: {idr(calc.get(key))}")
    rows += ["", "## Data pasar dan keyakinan", f"- Jumlah pembanding: {market.get('count', 0)}", f"- Confidence: {market.get('confidence', 0)}/100", ""]
    comps = market.get("comparables", [])
    if comps:
        rows += ["| Comparable | Harga input | Harga disesuaikan | Skor kualitas | Jenis harga | Sumber |", "|---|---:|---:|---:|---|---|"]
        for c in comps:
            rows.append(f"| {c.get('complex') or c.get('address') or '—'} | {idr(c.get('price'))} | {idr(c.get('adjusted_price'))} | {c.get('quality_score', '—')} | {c.get('price_type', '—')} | {c.get('source_url', '—')} |")
        rows.append("")
    rows += ["## Risiko / hard stop"]
    for item in decision.get("blockers", []):
        rows.append(f"- **BLOCKER:** {item}")
    for item in decision.get("warnings", []):
        rows.append(f"- **PERINGATAN:** {item}")
    for item in decision.get("reasons", []):
        rows.append(f"- {item}")
    rows += ["", "## Catatan penggunaan", "Angka pajak, biaya administrasi, kondisi penguasaan, estimasi penjualan, dan data pembanding adalah input/asumsi yang harus diverifikasi untuk lot spesifik. Aplikasi ini alat bantu keputusan, bukan appraisal, nasihat hukum, atau nasihat pajak.", ""]
    if payload.get("ai_memo"):
        rows += ["## Memo AI (penjelasan, bukan mesin hitung)", payload["ai_memo"], ""]
    return "\n".join(rows)
