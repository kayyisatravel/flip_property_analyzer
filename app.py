from __future__ import annotations

import hmac
import json
import os
from datetime import date, datetime, timezone
from io import BytesIO
from typing import Any

import pandas as pd
import streamlit as st

from core.calculator import calculate_project
from core.maximum_bid import find_maximum_bid
from core.occupancy import compare_possession_scenarios
from core.renovation import summarize_renovation_items
from core.decision_engine import evaluate_decision
from core.market_engine import estimate_market_range
from reports.report_builder import build_markdown_report, idr
from services.document_parser import extract_text
from storage.repository import is_configured, list_snapshots, save_snapshot

st.set_page_config(page_title="Auction Flip Analyzer", page_icon="🏠", layout="wide")

# Lightweight, optional single-user gate. Set APP_PASSWORD in Streamlit Secrets before deployment.
def secret_value(key: str, default: str = "") -> str:
    try:
        value = st.secrets.get(key, default)
        if value is not None and str(value):
            return str(value)
    except Exception:
        pass
    return os.getenv(key, default)


APP_PASSWORD = secret_value("APP_PASSWORD", "")
if APP_PASSWORD:
    if not st.session_state.get("authenticated", False):
        st.title("Auction Flip Analyzer")
        st.caption("Akses terbatas")
        with st.form("login_form"):
            password = st.text_input("Kata sandi aplikasi", type="password")
            submitted = st.form_submit_button("Masuk", use_container_width=True)
        if submitted:
            if hmac.compare_digest(password, APP_PASSWORD):
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Kata sandi tidak cocok.")
        st.stop()
else:
    st.sidebar.warning("APP_PASSWORD belum diatur. Siapa pun yang memiliki URL aplikasi dapat membukanya.")

GEMINI_API_KEY = secret_value("GEMINI_API_KEY", "")
GEMINI_MODEL = secret_value("GEMINI_MODEL", "gemini-3.8-flash")
SUPABASE_URL = secret_value("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = secret_value("SUPABASE_SERVICE_ROLE_KEY", "")

# -------- UI style --------
st.markdown(
    """
    <style>
    .block-container {padding-top: 1.3rem; padding-bottom: 2.5rem; max-width: 1500px;}
    h1, h2, h3 {letter-spacing: -0.025em;}
    div[data-testid="stMetric"] {background: rgba(120,130,140,0.07); padding: 0.8rem 1rem; border-radius: 12px;}
    .small-muted {color: #718096; font-size: 0.85rem;}
    div[data-testid="stAlert"] {border-radius: 10px;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Auction Flip Analyzer")
st.caption("Investment Decision System untuk rumah lelang · Sell first, buy second · mesin hitung deterministik + AI opsional")

# -------- Session state --------
if "analysis_history" not in st.session_state:
    st.session_state["analysis_history"] = []
if "ai_memo" not in st.session_state:
    st.session_state["ai_memo"] = ""
if "ai_market_research" not in st.session_state:
    st.session_state["ai_market_research"] = ""
if "document_extraction" not in st.session_state:
    st.session_state["document_extraction"] = ""
if "comps_seeded" not in st.session_state:
    st.session_state["comps_seeded"] = True
if "comparables_editor" not in st.session_state:
    st.session_state["comparables_editor"] = pd.DataFrame(
        [{
            "complex": "", "address": "", "distance_km": None, "land_area": None,
            "building_area": None, "price": None, "price_type": "Listing aktif",
            "property_type": "Tidak diketahui", "condition": "Tidak diketahui", "certificate": "Tidak diketahui",
            "date_found": str(date.today()), "source_url": ""
        }]
    )
if "renovation_editor" not in st.session_state:
    st.session_state["renovation_editor"] = pd.DataFrame(
        [{"item": "", "cost": None, "confidence": "Rendah", "notes": ""}]
    )

# -------- Tabs and placeholders --------
tab_dashboard, tab_property, tab_market, tab_costs, tab_ai, tab_history = st.tabs([
    "📊 Dashboard & keputusan", "🏡 Properti & legal", "🔎 Market comparables",
    "🧮 Biaya, risiko & kas", "✨ Gemini AI & dokumen", "🗂️ Riwayat"
])
dashboard_slot = tab_dashboard.empty()
market_summary_slot = tab_market.empty()
ai_slot = tab_ai.empty()
history_slot = tab_history.empty()

# -------- Property and legal input --------
with tab_property:
    st.subheader("1. Identitas objek lelang")
    c1, c2, c3 = st.columns(3)
    with c1:
        property_name = st.text_input("Nama objek / proyek", key="property_name", placeholder="Contoh: Perumahan Blok A-12")
        complex_name = st.text_input("Nama perumahan/kompleks", key="complex_name")
        address = st.text_input("Alamat / area", key="address", placeholder="Desa, kecamatan, kabupaten")
        auction_url = st.text_input("Link pengumuman lelang", key="auction_url")
    with c2:
        lot_code = st.text_input("Kode lot", key="lot_code")
        auction_source = st.selectbox("Sumber/jenis lelang", ["KPKNL / lelang.go.id", "Bank BUMN", "Bank swasta", "Pengadilan", "Lainnya / belum diketahui"], key="auction_source")
        auction_date = st.date_input("Tanggal lelang", value=None, key="auction_date")
        bank_seller = st.text_input("Bank / kreditur penjual", key="bank_seller")
    with c3:
        auction_limit = st.number_input("Limit lelang (Rp)", min_value=0, step=1_000_000, value=0, key="auction_limit")
        deposit_amount = st.number_input("Uang jaminan (Rp)", min_value=0, step=1_000_000, value=0, key="deposit_amount")
        auction_increment = st.number_input("Kelipatan/increment bid (Rp)", min_value=100_000, step=100_000, value=1_000_000, key="auction_increment")
        njop = st.number_input("NJOP (Rp, bila diketahui)", min_value=0, step=1_000_000, value=0, key="njop")

    st.divider()
    st.subheader("2. Spesifikasi, dokumen, dan status penguasaan")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        certificate = st.selectbox("Jenis hak", ["SHM", "SHGB/HGB", "Hak lain", "Belum diketahui"], key="certificate")
        land_area = st.number_input("Luas tanah (m²)", min_value=0.0, step=1.0, value=0.0, key="land_area")
        building_area = st.number_input("Luas bangunan (m²)", min_value=0.0, step=1.0, value=0.0, key="building_area")
    with c2:
        bedrooms = st.number_input("Kamar tidur", min_value=0, max_value=30, value=0, step=1, key="bedrooms")
        bathrooms = st.number_input("Kamar mandi", min_value=0, max_value=30, value=0, step=1, key="bathrooms")
        property_type = st.selectbox("Tipe/karakter rumah", ["Tidak diketahui", "Rumah 1 lantai", "Rumah 2 lantai", "Rumah kecil/standar", "Rumah besar", "Cluster/modern"], key="property_type")
    with c3:
        legal_status = st.selectbox("Status verifikasi legalitas", ["Belum terverifikasi", "Informasi sumber", "Informasi lapangan", "Terverifikasi", "Bertentangan"], key="legal_status")
        identity_verified = st.checkbox("Alamat, luas, dan identitas objek dicocokkan dengan dokumen", value=False, key="identity_verified")
        title_match = st.checkbox("Data fisik cocok dengan dokumen hak/pengumuman", value=False, key="title_match")
    with c4:
        occupancy_status = st.selectbox("Status aktual penguasaan", ["Belum diketahui", "Kosong dan terverifikasi", "Penghuni kooperatif", "Penghuni sulit", "Pengosongan formal/eksekusi riil"], key="occupancy_status")
        occupancy_verified = st.checkbox("Status penguasaan diverifikasi saat survei", value=False, key="occupancy_verified")
        dispute_detected = st.checkbox("Ada indikasi sengketa / masalah hukum yang belum selesai", value=False, key="dispute_detected")

    st.markdown("#### Kondisi fisik dan lingkungan")
    p1, p2, p3 = st.columns(3)
    with p1:
        subject_condition = st.selectbox("Kondisi bangunan berdasarkan bukti", ["Tidak diketahui", "Siap huni", "Renovasi kosmetik", "Rusak berat"], key="subject_condition")
        exterior_inspected = st.checkbox("Fasad/eksterior sudah diperiksa", value=False, key="exterior_inspected")
        interior_inspected = st.checkbox("Interior sudah diperiksa", value=False, key="interior_inspected")
    with p2:
        access_type = st.selectbox("Akses kendaraan", ["Belum diketahui", "Mobil bisa masuk/parkir", "Mobil hanya sampai jalan utama", "Gang sempit / motor saja"], key="access_type")
        flood_history = st.selectbox("Riwayat banjir", ["Belum diketahui", "Tidak ada indikasi setelah verifikasi", "Pernah/terindikasi"], key="flood_history")
    with p3:
        physical_notes = st.text_area("Catatan survei / kondisi / pihak terkait", key="physical_notes", height=95, placeholder="Catat sumber dan tanggal: atap, plafon, rembes, pagar, barang, pemegang kunci, dll.")

    st.info("Foto fasad dan keterangan tetangga tidak membuktikan kondisi interior atau legalitas. Jika interior belum diperiksa, masukkan allowance renovasi konservatif; aplikasi akan memberi peringatan.")

# -------- Market comparables input --------
with tab_market:
    st.subheader("3. Data pembanding pasar")
    st.write("Masukkan listing yang Anda temukan, termasuk URL dan tanggal ditemukan. Harga transaksi terverifikasi harus dibedakan dari harga penawaran aktif.")
    st.caption("Skor awal /100: kompleks sama 25, kedekatan 15, kesamaan LT 10, LB 15, kondisi 10, sertifikat 5, keandalan/status harga 10, kebaruan data 5. Penyesuaian luas adalah heuristik yang terlihat di hasil.")
    edited_comps = st.data_editor(
        st.session_state["comparables_editor"],
        key="comparables_editor_widget",
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "complex": st.column_config.TextColumn("Kompleks", help="Isi nama kompleks agar sama persis bila lokasinya memang satu kompleks."),
            "address": st.column_config.TextColumn("Alamat / area"),
            "distance_km": st.column_config.NumberColumn("Jarak km", min_value=0.0, step=0.5, format="%.1f"),
            "land_area": st.column_config.NumberColumn("LT m²", min_value=0, step=1),
            "building_area": st.column_config.NumberColumn("LB m²", min_value=0, step=1),
            "price": st.column_config.NumberColumn("Harga Rp", min_value=0, step=1_000_000, format="%.0f"),
            "price_type": st.column_config.SelectboxColumn("Jenis harga", options=["Transaksi terverifikasi", "Terjual/marked sold", "Listing aktif", "Lelang", "Developer", "Informasi agen/lapangan"], required=True),
            "property_type": st.column_config.SelectboxColumn("Tipe/karakter", options=["Rumah 1 lantai", "Rumah 2 lantai", "Rumah kecil/standar", "Rumah besar", "Cluster/modern", "Tidak diketahui"], required=True),
            "condition": st.column_config.SelectboxColumn("Kondisi", options=["Siap huni", "Renovasi kosmetik", "Rusak berat", "Tidak diketahui"], required=True),
            "certificate": st.column_config.SelectboxColumn("Sertifikat", options=["SHM", "SHGB/HGB", "Tidak diketahui", "Lainnya"], required=True),
            "date_found": st.column_config.TextColumn("Tanggal ditemukan (YYYY-MM-DD)"),
            "source_url": st.column_config.TextColumn("URL sumber"),
        },
    )
    st.session_state["comparables_editor"] = edited_comps
    use_manual_exit = st.checkbox("Gunakan harga jual skenario manual (tetap wajib punya bukti pembanding)", value=False, key="use_manual_exit")
    haircut_col, premium_col, manual_col = st.columns(3)
    with haircut_col:
        conservative_haircut = st.slider("Diskon exit konservatif (%)", 0, 40, 10, key="conservative_haircut")
    with premium_col:
        optimistic_premium = st.slider("Premium exit optimistis (%)", 0, 40, 10, key="optimistic_premium")
    with manual_col:
        st.caption("Jika skenario manual diaktifkan, isi semua harga dengan dasar yang dapat diaudit.")
    if use_manual_exit:
        mx1, mx2, mx3 = st.columns(3)
        with mx1:
            manual_conservative_exit = st.number_input("Manual: harga jual konservatif (Rp)", min_value=0, step=5_000_000, value=0, key="manual_conservative_exit")
        with mx2:
            manual_base_exit = st.number_input("Manual: harga jual base (Rp)", min_value=0, step=5_000_000, value=0, key="manual_base_exit")
        with mx3:
            manual_optimistic_exit = st.number_input("Manual: harga jual optimistis (Rp)", min_value=0, step=5_000_000, value=0, key="manual_optimistic_exit")
    else:
        manual_conservative_exit = manual_base_exit = manual_optimistic_exit = 0
    st.caption("Catatan: scraping otomatis portal properti belum diaktifkan, karena akses tiap portal berbeda dan listing dapat kedaluwarsa. Riset web berbasis Gemini tersedia di tab AI, lalu hasilnya dapat diverifikasi dan dimasukkan ke tabel ini.")

# -------- Fees, cost, capital, risk input --------
with tab_costs:
    st.subheader("4. Tarif dan biaya transaksi")
    st.warning("Tarif awal di bawah adalah parameter input, bukan penetapan hukum. Verifikasi aturan yang berlaku untuk wilayah, tanggal, dan jenis lot sebelum bidding.")
    f1, f2, f3 = st.columns(3)
    with f1:
        buyer_auction_fee_pct = st.number_input("Bea lelang pembeli (%)", min_value=0.0, max_value=100.0, value=2.0, step=0.1, key="buyer_auction_fee_pct")
        bphtb_rate_pct = st.number_input("BPHTB (%)", min_value=0.0, max_value=100.0, value=5.0, step=0.1, key="bphtb_rate_pct")
        npoptkp = st.number_input("NPOPTKP / pengurang BPHTB (Rp)", min_value=0, step=1_000_000, value=0, key="npoptkp")
    with f2:
        bphtb_basis_mode = st.selectbox("Dasar BPHTB untuk simulasi", ["Harga bid", "Maksimum harga bid dan NJOP", "NJOP"], key="bphtb_basis_mode")
        ppn_applicable = st.checkbox("PPN relevan untuk transaksi ini (sudah diverifikasi)", value=False, key="ppn_applicable")
        ppn_rate_pct = st.number_input("Tarif efektif PPN yang akan dipakai (%)", min_value=0.0, max_value=100.0, value=0.0, step=0.1, key="ppn_rate_pct")
    with f3:
        selling_agent_pct = st.number_input("Komisi agen penjualan (%)", min_value=0.0, max_value=100.0, value=2.0, step=0.25, key="selling_agent_pct")
        seller_tax_pct = st.number_input("Pajak/biaya penjual asumsi (%)", min_value=0.0, max_value=100.0, value=2.5, step=0.1, key="seller_tax_pct")
        st.caption("Jangan aktifkan PPN kecuali karakter transaksi dan dasar pengenaannya sudah dicek.")

    tax_rule_col1, tax_rule_col2 = st.columns([2, 1])
    with tax_rule_col1:
        tax_rule_source_url = st.text_input("URL sumber resmi aturan pajak/biaya (JDIH/Kemenkeu/DJP)", key="tax_rule_source_url", placeholder="Tempel URL regulasi yang sudah diperiksa")
        tax_rule_version_note = st.text_input("Catatan aturan / wilayah / masa berlaku", key="tax_rule_version_note", placeholder="Contoh: BPHTB Kabupaten ...; berlaku sejak ...")
    with tax_rule_col2:
        tax_rules_verified = st.checkbox("Tarif dan dasar pengenaan sudah diverifikasi untuk lot ini", value=False, key="tax_rules_verified")
        tax_rule_verified_date = st.date_input("Tanggal verifikasi", value=None, key="tax_rule_verified_date")

    st.divider()
    st.subheader("5. Renovasi, legal, holding, dan penguasaan")
    c1, c2, c3 = st.columns(3)
    with c1:
        certificate_legal_cost = st.number_input("Sertifikat, PPAT/legal, administrasi (Rp)", min_value=0, step=1_000_000, value=10_000_000, key="certificate_legal_cost")
        renovation_cost_manual = st.number_input("Anggaran renovasi total manual (Rp)", min_value=0, step=5_000_000, value=0, key="renovation_cost_manual")
        other_presale_cost = st.number_input("Biaya pra-penjualan lain (Rp)", min_value=0, step=1_000_000, value=0, key="other_presale_cost")
        arrears_utilities_cost = st.number_input("Tunggakan PBB/IPL/utilitas yang harus dibayar (Rp)", min_value=0, step=1_000_000, value=0, key="arrears_utilities_cost")
        contingency_pct = st.number_input("Contingency atas biaya non-akuisisi (%)", min_value=0.0, max_value=100.0, value=15.0, step=1.0, key="contingency_pct")
    with c2:
        monthly_holding_cost = st.number_input("Holding cost per bulan: IPL, PBB prorata, utilitas, keamanan, perawatan (Rp)", min_value=0, step=500_000, value=1_000_000, key="monthly_holding_cost")
        renovation_months = st.number_input("Durasi renovasi (bulan)", min_value=0.0, max_value=60.0, value=2.0, step=0.5, key="renovation_months")
        sale_months_after_ready = st.number_input("Target lama jual setelah siap (bulan)", min_value=0.0, max_value=60.0, value=3.0, step=0.5, key="sale_months_after_ready")
        marketing_cost = st.number_input("Marketing saat penjualan (Rp)", min_value=0, step=500_000, value=1_000_000, key="marketing_cost")
        other_selling_cost = st.number_input("Biaya penjualan lain (Rp)", min_value=0, step=500_000, value=0, key="other_selling_cost")
    with c3:
        scenario_names = ["A — Kosong diserahkan", "B — Penghuni kooperatif/kerahiman", "C — Penghuni sulit", "D — Pengosongan formal/eksekusi riil"]
        possession_scenario_name = st.selectbox("Skenario biaya yang dipakai dalam base calculation", scenario_names, index=3, key="possession_scenario_name")
        st.caption("Angka skenario adalah cadangan awal yang harus diganti berdasarkan survei/advokat. Nilai biaya bukan kutipan biaya resmi.")
        possession_empty_cost = st.number_input("A: biaya serah terima/kunci/bersih-bersih (Rp)", min_value=0, step=1_000_000, value=2_000_000, key="possession_empty_cost")
        possession_coop_cost = st.number_input("B: kerahiman/kesepakatan (Rp)", min_value=0, step=1_000_000, value=17_000_000, key="possession_coop_cost")
        possession_difficult_cost = st.number_input("C: negosiasi/pendampingan tambahan (Rp)", min_value=0, step=5_000_000, value=35_000_000, key="possession_difficult_cost")
        possession_execution_cost = st.number_input("D: cadangan pengosongan formal/eksekusi (Rp)", min_value=0, step=10_000_000, value=100_000_000, key="possession_execution_cost")
        possession_empty_delay = st.number_input("A: tambahan delay (bulan)", min_value=0.0, max_value=60.0, value=0.5, step=0.5, key="possession_empty_delay")
        possession_coop_delay = st.number_input("B: tambahan delay (bulan)", min_value=0.0, max_value=60.0, value=1.0, step=0.5, key="possession_coop_delay")
        possession_difficult_delay = st.number_input("C: tambahan delay (bulan)", min_value=0.0, max_value=60.0, value=3.0, step=0.5, key="possession_difficult_delay")
        possession_execution_delay = st.number_input("D: tambahan delay (bulan)", min_value=0.0, max_value=60.0, value=12.0, step=1.0, key="possession_execution_delay")

    use_itemized_renovation = st.checkbox("Gunakan total RAB dari tabel item renovasi", value=False, key="use_itemized_renovation")
    edited_renovation = st.data_editor(
        st.session_state["renovation_editor"], key="renovation_editor_widget", num_rows="dynamic",
        use_container_width=True, hide_index=True,
        column_config={
            "item": st.column_config.TextColumn("Item pekerjaan"),
            "cost": st.column_config.NumberColumn("Estimasi Rp", min_value=0, step=500_000, format="%.0f"),
            "confidence": st.column_config.SelectboxColumn("Kepastian RAB", options=["Tinggi", "Sedang", "Rendah"], required=True),
            "notes": st.column_config.TextColumn("Dasar / catatan"),
        },
    )
    st.session_state["renovation_editor"] = edited_renovation
    renovation_items = []
    for renovation_row in edited_renovation.to_dict("records"):
        try:
            amount = float(renovation_row.get("cost") or 0)
        except (TypeError, ValueError):
            amount = 0.0
        if amount > 0:
            renovation_items.append({k: (None if pd.isna(v) else v) for k, v in renovation_row.items()})
    renovation_summary = summarize_renovation_items(renovation_items)
    itemized_renovation_cost = renovation_summary["total_cost"]
    renovation_cost = itemized_renovation_cost if use_itemized_renovation else float(renovation_cost_manual)
    if use_itemized_renovation:
        rm1, rm2, rm3 = st.columns(3)
        rm1.metric("Total RAB renovasi yang digunakan", idr(renovation_cost))
        rm2.metric("Keyakinan tertimbang RAB", f"{renovation_summary['confidence_pct']:.0f}%")
        rm3.metric("Porsi RAB berkepastian rendah", f"{renovation_summary['low_confidence_share_pct']:.0f}%")
        if renovation_summary["low_confidence_share_pct"] >= 50:
            st.warning("Sebagian besar RAB masih berkepastian rendah. Naikkan contingency atau verifikasi penawaran sebelum bidding.")

    st.divider()
    st.subheader("6. Profil pendanaan dan hurdle rate")
    cap1, cap2, cap3 = st.columns(3)
    with cap1:
        cash_available = st.number_input("Kas aktual tersedia sekarang (Rp)", min_value=0, step=10_000_000, value=0, key="cash_available")
        uncollected_receivables = st.number_input("Piutang belum cair (info saja; tidak dihitung sebagai kas) (Rp)", min_value=0, step=10_000_000, value=0, key="uncollected_receivables")
        ongoing_project_commitments = st.number_input("Komitmen proyek lain yang belum dibayar (Rp)", min_value=0, step=5_000_000, value=0, key="ongoing_project_commitments")
        household_operating_reserve = st.number_input("Cadangan rumah tangga/operasional yang tidak boleh dipakai (Rp)", min_value=0, step=5_000_000, value=0, key="household_operating_reserve")
        mandatory_risk_reserve = st.number_input("Cadangan risiko yang wajib tetap tersedia (Rp)", min_value=0, step=5_000_000, value=0, key="mandatory_risk_reserve")
        funding_data_confirmed = st.checkbox("Kas, komitmen, dan cadangan sudah saya konfirmasi sebagai angka aktual", value=False, key="funding_data_confirmed")
    with cap2:
        minimum_net_profit = st.number_input("Profit bersih minimum yang diterima (Rp)", min_value=0, step=5_000_000, value=0, key="minimum_net_profit")
        minimum_roi_pct = st.number_input("ROI minimum atas modal pra-penjualan (%)", min_value=0.0, max_value=500.0, value=20.0, step=1.0, key="minimum_roi_pct")
        minimum_profit_per_month = st.number_input("Profit bersih minimum rata-rata per bulan (Rp)", min_value=0, step=1_000_000, value=0, key="minimum_profit_per_month")
        maximum_holding_months = st.number_input("Batas maksimum holding dari pembelian sampai terjual (bulan)", min_value=1.0, max_value=120.0, value=12.0, step=1.0, key="maximum_holding_months")
        annual_opportunity_cost_pct = st.number_input("Biaya kesempatan modal per tahun (%) — 0 jika tidak dipakai", min_value=0.0, max_value=100.0, value=0.0, step=0.5, key="annual_opportunity_cost_pct")
    with cap3:
        simulate_at_limit = st.checkbox("Bid simulasi mengikuti limit lelang", value=True, key="simulate_at_limit")
        if simulate_at_limit:
            simulated_bid = float(auction_limit)
            st.caption(f"Bid simulasi saat ini: {idr(simulated_bid)}")
        else:
            simulated_bid = st.number_input("Bid simulasi saat ini (Rp)", min_value=0, step=max(100_000, int(auction_increment)), value=int(auction_limit), key="simulated_bid_custom")
        risk_ceiling_pct = st.slider("Ceiling bid sebagai % harga jual konservatif", min_value=20, max_value=100, value=70, step=5, key="risk_ceiling_pct")
        st.caption("Overlay risiko heuristik yang dapat Anda ubah. Bukan standar valuasi atau aturan lelang.")

    st.divider()
    st.subheader("7. Skor awal risiko (1 = buruk, 5 = baik)")
    r1, r2, r3 = st.columns(3)
    with r1:
        risk_liquidity = st.slider("Likuiditas pasar & exit", 1, 5, 3, key="risk_liquidity")
        risk_legal = st.slider("Legalitas", 1, 5, 3, key="risk_legal")
    with r2:
        risk_possession = st.slider("Penguasaan fisik", 1, 5, 2, key="risk_possession")
        risk_physical = st.slider("Kondisi fisik & renovasi", 1, 5, 3, key="risk_physical")
    with r3:
        risk_funding = st.slider("Kemampuan pendanaan", 1, 5, 3, key="risk_funding")
        risk_environment = st.slider("Lingkungan & fasilitas", 1, 5, 3, key="risk_environment")

# -------- Build normalized data and calculations --------
comps_rows: list[dict[str, Any]] = []
for row in edited_comps.to_dict("records"):
    try:
        price = float(row.get("price") or 0)
    except (TypeError, ValueError):
        price = 0.0
    if price > 0:
        clean = {}
        for key, value in row.items():
            if pd.isna(value):
                clean[key] = None
            elif key in {"price", "land_area", "building_area", "distance_km"}:
                try:
                    clean[key] = float(value)
                except (TypeError, ValueError):
                    clean[key] = None
            else:
                clean[key] = str(value) if value is not None else None
        comps_rows.append(clean)

subject = {
    "complex": complex_name,
    "address": address,
    "land_area": land_area,
    "building_area": building_area,
    "certificate": certificate,
    "property_type": property_type,
    "condition": subject_condition,
}
market_result = estimate_market_range(comps_rows, subject, conservative_haircut, optimistic_premium)
if use_manual_exit:
    market_result["conservative_exit"] = int(manual_conservative_exit) or None
    market_result["base_exit"] = int(manual_base_exit) or None
    market_result["optimistic_exit"] = int(manual_optimistic_exit) or None

scenario_map = {
    "A — Kosong diserahkan": {"key": "empty", "label": "A — Kosong diserahkan", "cost": possession_empty_cost, "delay_months": possession_empty_delay},
    "B — Penghuni kooperatif/kerahiman": {"key": "cooperative", "label": "B — Penghuni kooperatif/kerahiman", "cost": possession_coop_cost, "delay_months": possession_coop_delay},
    "C — Penghuni sulit": {"key": "difficult", "label": "C — Penghuni sulit", "cost": possession_difficult_cost, "delay_months": possession_difficult_delay},
    "D — Pengosongan formal/eksekusi riil": {"key": "formal_execution", "label": "D — Pengosongan formal/eksekusi riil", "cost": possession_execution_cost, "delay_months": possession_execution_delay},
}
selected_possession = scenario_map[possession_scenario_name]

property_data = {
    "name": property_name,
    "complex": complex_name,
    "address": address,
    "auction_url": auction_url,
    "lot_code": lot_code,
    "auction_source": auction_source,
    "auction_date": auction_date.isoformat() if isinstance(auction_date, date) else None,
    "bank_seller": bank_seller,
    "auction_limit": float(auction_limit),
    "deposit_amount": float(deposit_amount),
    "bid_increment": float(auction_increment),
    "njop": float(njop),
    "certificate": certificate,
    "land_area": float(land_area),
    "building_area": float(building_area),
    "bedrooms": int(bedrooms),
    "bathrooms": int(bathrooms),
    "power_va": int(power_va),
    "property_type": property_type,
    "condition": subject_condition,
    "exterior_inspected": bool(exterior_inspected),
    "interior_inspected": bool(interior_inspected),
    "access_type": access_type,
    "flood_history": flood_history,
    "physical_notes": physical_notes,
    "legal_status": legal_status,
    "identity_verified": bool(identity_verified),
    "title_match": bool(title_match),
    "occupancy_status": occupancy_status,
    "occupancy_verified": bool(occupancy_verified),
    "dispute_detected": bool(dispute_detected),
}
fees_data = {
    "buyer_auction_fee_pct": buyer_auction_fee_pct,
    "bphtb_rate_pct": bphtb_rate_pct,
    "npoptkp": npoptkp,
    "bphtb_basis_mode": bphtb_basis_mode,
    "ppn_applicable": ppn_applicable,
    "ppn_rate_pct": ppn_rate_pct,
    "selling_agent_pct": selling_agent_pct,
    "seller_tax_pct": seller_tax_pct,
    "tax_rules_verified": tax_rules_verified,
    "tax_rule_source_url": tax_rule_source_url,
    "tax_rule_version_note": tax_rule_version_note,
    "tax_rule_verified_date": tax_rule_verified_date.isoformat() if isinstance(tax_rule_verified_date, date) else None,
}
costs_data = {
    "certificate_legal_cost": certificate_legal_cost,
    "renovation_cost": renovation_cost,
    "other_presale_cost": other_presale_cost,
    "arrears_utilities_cost": arrears_utilities_cost,
    "renovation_items": renovation_items,
    "renovation_confidence_pct": renovation_summary["confidence_pct"],
    "renovation_low_confidence_share_pct": renovation_summary["low_confidence_share_pct"],
    "use_itemized_renovation": use_itemized_renovation,
    "contingency_pct": contingency_pct,
    "monthly_holding_cost": monthly_holding_cost,
    "renovation_months": renovation_months,
    "sale_months_after_ready": sale_months_after_ready,
    "marketing_cost": marketing_cost,
    "other_selling_cost": other_selling_cost,
    "possession_scenario": possession_scenario_name,
    "possession_scenario_data": selected_possession,
}
finance_data = {
    "cash_available": cash_available,
    "uncollected_receivables": uncollected_receivables,
    "ongoing_project_commitments": ongoing_project_commitments,
    "household_operating_reserve": household_operating_reserve,
    "mandatory_risk_reserve": mandatory_risk_reserve,
    "funding_data_confirmed": funding_data_confirmed,
    "minimum_net_profit": minimum_net_profit,
    "minimum_roi_pct": minimum_roi_pct,
    "minimum_profit_per_month": minimum_profit_per_month,
    "maximum_holding_months": maximum_holding_months,
    "annual_opportunity_cost_pct": annual_opportunity_cost_pct,
    "bid_increment": auction_increment,
}
risk_scores = {
    "liquidity": risk_liquidity,
    "legal": risk_legal,
    "possession": risk_possession,
    "physical": risk_physical,
    "funding": risk_funding,
    "environment": risk_environment,
}
params = {
    "property": property_data,
    "fees": fees_data,
    "costs": costs_data,
    "finance": finance_data,
    "market": market_result,
    "risk_scores": risk_scores,
    "simulated_bid": simulated_bid,
}

if market_result.get("base_exit"):
    current_calculation = calculate_project(params, bid_price=simulated_bid, exit_price=market_result["base_exit"])
else:
    current_calculation = calculate_project(params, bid_price=simulated_bid, exit_price=0)
scenario_analysis = compare_possession_scenarios(
    params=params, bid_price=simulated_bid, exit_price=float(market_result.get("base_exit") or 0),
    scenarios=scenario_map, selected_key=selected_possession["key"],
)

recommended_result = None
absolute_result = None
recommended_ceiling = None
absolute_maximum = None
if market_result.get("conservative_exit"):
    risk_ceiling = market_result["conservative_exit"] * risk_ceiling_pct / 100.0
    recommended_result = find_maximum_bid(
        params, market_result["conservative_exit"], minimum_bid=auction_limit,
        increment=auction_increment, risk_ceiling=risk_ceiling, require_cash=True,
    )
    recommended_ceiling = recommended_result.get("maximum_bid")
if market_result.get("base_exit"):
    absolute_result = find_maximum_bid(
        params, market_result["base_exit"], minimum_bid=auction_limit,
        increment=auction_increment, risk_ceiling=None, require_cash=True,
    )
    absolute_maximum = absolute_result.get("maximum_bid")

bid_analysis = {
    "recommended_ceiling": recommended_ceiling,
    "recommended_reason": recommended_result.get("reason") if recommended_result else "Harga jual konservatif belum tersedia.",
    "recommended_result": recommended_result.get("result") if recommended_result else None,
    "absolute_maximum": absolute_maximum,
    "absolute_reason": absolute_result.get("reason") if absolute_result else "Harga jual base belum tersedia.",
    "absolute_result": absolute_result.get("result") if absolute_result else None,
    "walk_away_price": recommended_ceiling,
    "risk_ceiling": risk_ceiling if market_result.get("conservative_exit") else None,
}
decision = evaluate_decision(params, current_calculation, recommended_ceiling, absolute_maximum, market_result)

payload: dict[str, Any] = {
    "analysis_date": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    "property": property_data,
    "fees": fees_data,
    "costs": costs_data,
    "finance": finance_data,
    "risk_scores": risk_scores,
    "market": market_result,
    "current_calculation": current_calculation,
    "scenario_analysis": scenario_analysis,
    "bid_analysis": bid_analysis,
    "decision": decision,
    "ai_memo": st.session_state.get("ai_memo", ""),
    "ai_market_research": st.session_state.get("ai_market_research", ""),
}
report_md = build_markdown_report(payload)

# -------- Populate dashboard only after all inputs exist --------
with dashboard_slot.container():
    st.subheader("Hasil keputusan investasi")
    status = decision["status"]
    if status == "GO":
        st.success(f"{status} — {decision['summary']}")
    elif status == "CONDITIONAL":
        st.warning(f"{status} — {decision['summary']}")
    elif status == "NO-GO":
        st.error(f"{status} — {decision['summary']}")
    else:
        st.info(f"{status} — {decision['summary']}")

    if market_result.get("base_exit"):
        a, b, c = st.columns(3)
        with a:
            st.metric("Exit konservatif", idr(market_result.get("conservative_exit")))
        with b:
            st.metric("Exit base", idr(market_result.get("base_exit")))
        with c:
            st.metric("Exit optimistis", idr(market_result.get("optimistic_exit")))
    else:
        st.info("Harga jual belum tersedia. Masukkan minimal 3 pembanding yang layak atau isi skenario manual dengan bukti pendukung.")

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Modal sebelum penjualan", idr(current_calculation.get("pre_sale_investment")))
    with k2:
        st.metric("Profit bersih simulasi", idr(current_calculation.get("net_profit")))
    with k3:
        roi = current_calculation.get("roi_pct")
        roi_label = "ROI setelah biaya modal" if annual_opportunity_cost_pct > 0 else "ROI atas modal"
        st.metric(roi_label, f"{roi:.1f}%" if roi is not None else "—")
    with k4:
        st.metric("Lama holding", f"{current_calculation.get('total_holding_months', 0):.1f} bulan")

    st.divider()
    b1, b2, b3 = st.columns(3)
    with b1:
        st.metric("Recommended ceiling", idr(recommended_ceiling) if recommended_ceiling is not None else "Tidak lolos")
        st.caption("Skenario konservatif + cash check + overlay risk ceiling")
    with b2:
        st.metric("Absolute maximum", idr(absolute_maximum) if absolute_maximum is not None else "Tidak lolos")
        st.caption("Skenario base + cash check + hurdle rate; bukan target bid")
    with b3:
        st.metric("Walk-away price", idr(bid_analysis.get("walk_away_price")) if bid_analysis.get("walk_away_price") is not None else "Jangan bid")
        st.caption("Lewat angka ini: berhenti, walau ada persaingan")

    with st.expander("Rincian arus biaya — dapat diaudit", expanded=True):
        expense_rows = [
            ("Harga bid simulasi", current_calculation["bid_price"]),
            ("Bea lelang pembeli", current_calculation["auction_fee"]),
            ("BPHTB (berdasarkan parameter yang dipilih)", current_calculation["bphtb"]),
            ("PPN bila diaktifkan", current_calculation["ppn"]),
            ("Legal/sertifikat", current_calculation["certificate_legal_cost"]),
            ("Renovasi", current_calculation["renovation_cost"]),
            ("Tunggakan PBB/IPL/utilitas", current_calculation["arrears_utilities_cost"]),
            ("Biaya penguasaan/kerahiman skenario", current_calculation["possession_cost"]),
            ("Holding cost", current_calculation["holding_cost"]),
            ("Contingency", current_calculation["contingency"]),
            ("Modal kas pra-penjualan", current_calculation["pre_sale_investment"]),
            ("Biaya kesempatan modal (non-cash)", current_calculation["opportunity_cost"]),
            ("Pajak/komisi/marketing penjualan", current_calculation["selling_cost"]),
            ("Total biaya proyek termasuk biaya penjualan", current_calculation["total_project_cost_including_sale"]),
            ("Net proceeds setelah biaya penjualan", current_calculation["net_proceeds"]),
            ("Profit kas sebelum biaya kesempatan modal", current_calculation["cash_net_profit"]),
            ("Profit ekonomi setelah biaya kesempatan modal", current_calculation["net_profit"]),
        ]
        st.dataframe(pd.DataFrame(expense_rows, columns=["Komponen", "Nilai (Rp)"]).assign(**{"Nilai (Rp)": lambda d: d["Nilai (Rp)"].map(lambda x: f"Rp{x:,.0f}".replace(",", "."))}), use_container_width=True, hide_index=True)
        st.caption("Penjualan tidak dihitung dua kali: selling cost dipotong satu kali dari proceeds, bukan dimasukkan lagi ke modal pra-penjualan.")

    with st.expander("Empat skenario penguasaan — biaya alternatif, bukan dijumlahkan", expanded=False):
        s1, s2, s3 = st.columns(3)
        s1.metric("Biaya skenario pilihan", idr(scenario_analysis.get("selected", {}).get("possession_cost") if scenario_analysis.get("selected") else 0))
        s2.metric("Modal terburuk yang wajar", idr(scenario_analysis.get("worst_reasonable_capital_requirement")))
        s3.metric("Cadangan tambahan menuju skenario terburuk", idr(scenario_analysis.get("incremental_reserve_to_worst_case")))
        st.caption(f"Skenario dengan kebutuhan modal tertinggi: {scenario_analysis.get('worst_scenario_name') or '—'}. Pengeluaran skenario lain tidak ditambahkan ke base case karena skenario saling alternatif.")
        scenario_table = pd.DataFrame(scenario_analysis.get("scenarios", []))
        if not scenario_table.empty:
            st.dataframe(scenario_table.rename(columns={
                "scenario_name": "Skenario", "possession_cost": "Biaya penguasaan Rp",
                "delay_months": "Delay bulan", "total_holding_months": "Total holding bulan",
                "cash_investment_before_sale": "Modal kas pra-penjualan Rp",
                "net_profit_after_opportunity_cost": "Profit ekonomi Rp", "roi_pct": "ROI %",
                "cash_available_met": "Kas cukup?",
            }).drop(columns=["scenario_key"], errors="ignore"), use_container_width=True, hide_index=True)

    st.subheader("Gate yang belum lolos")
    if decision["blockers"]:
        for item in decision["blockers"]:
            st.markdown(f"- ⛔ {item}")
    else:
        st.write("Tidak ada blocker otomatis berdasarkan data yang diinput.")
    if decision["warnings"]:
        for item in decision["warnings"]:
            st.markdown(f"- ⚠️ {item}")
    with st.expander("Rumus dan definisi indikator"):
        st.markdown(
            """
            - **Modal pra-penjualan** = harga bid + bea lelang + BPHTB + PPN bila berlaku + legal/sertifikat + renovasi + biaya penguasaan + holding + contingency.
            - **Net proceeds** = harga closing - biaya penjualan (pajak/fee/marketing) sesuai parameter input.
            - **Profit bersih** = net proceeds - modal pra-penjualan.
            - **ROI** = profit bersih setelah biaya kesempatan modal (jika diaktifkan) / modal kas pra-penjualan × 100%. Biaya kesempatan modal adalah biaya ekonomi, bukan pengeluaran kas nyata.
            - **Profit per bulan** = profit bersih / total holding sejak akuisisi sampai terjual.
            - **Kas siap proyek** = kas aktual - komitmen proyek - cadangan rumah tangga - cadangan risiko. Piutang belum cair tidak dihitung sebagai kas.
            - **Deposit lelang** adalah kebutuhan kas sebelum lelang dan tidak ditambahkan lagi ke harga bid karena diasumsikan dikreditkan ke pembayaran jika menang.
            - **Maximum bid** adalah pencarian numerik pada kelipatan bid; jika limit saja gagal memenuhi kriteria, hasilnya "Tidak lolos".
            """
        )
    with st.expander("Simpan snapshot dan ekspor laporan"):
        sc1, sc2 = st.columns(2)
        with sc1:
            if st.button("Simpan analisis ke riwayat", type="primary", use_container_width=True):
                snapshot = json.loads(json.dumps(payload, ensure_ascii=False, default=str))
                st.session_state["analysis_history"].insert(0, snapshot)
                if is_configured(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY):
                    try:
                        save_snapshot(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, snapshot)
                        st.success("Snapshot tersimpan ke session dan Supabase.")
                    except Exception as exc:
                        st.warning(f"Snapshot tersimpan sementara di session, tetapi Supabase gagal: {exc}")
                else:
                    st.success("Snapshot tersimpan di session browser ini. Unduh JSON untuk arsip permanen, atau konfigurasi Supabase untuk penyimpanan lintas sesi.")
        with sc2:
            st.download_button("Unduh laporan Markdown", data=report_md.encode("utf-8"), file_name="investment_memo.md", mime="text/markdown", use_container_width=True)
            st.download_button("Unduh snapshot JSON", data=json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8"), file_name="auction_analysis_snapshot.json", mime="application/json", use_container_width=True)

# -------- Market summary at bottom of market tab --------
with market_summary_slot.container():
    st.subheader("Hasil analisis pembanding")
    if market_result["count"] == 0:
        st.info("Belum ada pembanding dengan harga di atas nol. Tambahkan setidaknya 3 pembanding yang relevan sebelum menjadikan rekomendasi final.")
    else:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Jumlah pembanding", market_result["count"])
        m2.metric("Confidence awal", f"{market_result['confidence']:.0f}/100")
        m3.metric("Median harga mentah", idr(market_result.get("median_raw_price")))
        m4.metric("Base exit disesuaikan", idr(market_result.get("base_exit")))
        comp_df = pd.DataFrame(market_result["comparables"])
        show_cols = [c for c in ["complex", "address", "price", "adjusted_price", "quality_score", "analysis_weight", "price_type", "condition", "source_url"] if c in comp_df.columns]
        st.dataframe(comp_df[show_cols], use_container_width=True, hide_index=True)
        st.caption("Confidence = rata-rata skor kualitas × faktor jumlah data (maksimum penuh pada 5 pembanding). Satu listing berharga tinggi tidak otomatis berarti exit yang dapat dicapai.")

# -------- AI tab --------
with ai_slot.container():
    st.subheader("8. Gemini Flash — riset web, ekstraksi dokumen, memo investasi")
    st.write("Integrasi ini opsional. Python tetap menjadi sumber kebenaran untuk biaya, ROI, batas bid, dan status keputusan.")
    if not GEMINI_API_KEY:
        st.warning("GEMINI_API_KEY belum diatur. Kalkulator tetap berfungsi. Tambahkan key di Streamlit Secrets untuk mengaktifkan AI.")
    st.caption(f"Model AI yang dikonfigurasi: `{GEMINI_MODEL}`")

    with st.expander("A. Riset pembanding terbaru via Google Search grounding", expanded=True):
        suggested_query = f"Cari 5+ rumah dijual dekat {complex_name or address or 'area target'} dengan luas tanah sekitar {land_area or 'belum diketahui'} m² dan bangunan sekitar {building_area or 'belum diketahui'} m². Bandingkan listing aktif, marked sold, dan transaksi terverifikasi jika tersedia."
        research_query = st.text_area("Instruksi riset", value=suggested_query, height=95, key="research_query")
        if st.button("Cari pembanding di internet dengan Gemini", key="run_market_research", disabled=not bool(GEMINI_API_KEY), use_container_width=True):
            try:
                from services.gemini_client import grounded_market_research
                with st.spinner("Gemini sedang meneliti sumber web..."):
                    st.session_state["ai_market_research"] = grounded_market_research(GEMINI_API_KEY, GEMINI_MODEL, research_query)
            except Exception as exc:
                st.error(f"Riset Gemini gagal: {exc}")
        if st.session_state.get("ai_market_research"):
            st.markdown(st.session_state["ai_market_research"])
            st.download_button("Unduh hasil riset", st.session_state["ai_market_research"].encode("utf-8"), file_name="market_research.md", mime="text/markdown", key="download_market_research")

    with st.expander("B. Ekstrak fakta dari PDF, gambar, atau dokumen", expanded=False):
        uploaded_file = st.file_uploader("Unggah pengumuman lelang / sertifikat yang relevan / catatan survei", type=["pdf", "png", "jpg", "jpeg", "webp", "txt", "md", "docx"], key="document_upload")
        if uploaded_file:
            st.caption(f"File: {uploaded_file.name} · {uploaded_file.size:,} bytes. Jangan unggah data pribadi yang tidak diperlukan.")
            do_extract = st.button("Ekstrak fakta dengan Gemini", key="run_document_extract", disabled=not bool(GEMINI_API_KEY), use_container_width=True)
            if do_extract:
                try:
                    from services.gemini_client import extract_document_with_gemini
                    file_bytes = uploaded_file.getvalue()
                    mime_type = uploaded_file.type or "application/octet-stream"
                    if uploaded_file.name.lower().endswith((".txt", ".md", ".docx")):
                        text_content, _ = extract_text(file_bytes, uploaded_file.name)
                        if not text_content.strip():
                            raise RuntimeError("Tidak ada teks yang bisa diekstrak dari file ini.")
                        from google import genai
                        client = genai.Client(api_key=GEMINI_API_KEY)
                        prompt = "Ekstrak fakta properti lelang sebagai JSON: nama_objek, alamat, kode_lot, limit_lelang_idr, uang_jaminan_idr, tanggal_lelang, luas_tanah_m2, luas_bangunan_m2, jenis_sertifikat, nomor_hak, penguasaan, dokumen_yang_disebutkan, catatan_penting, data_belum_jelas. Nilai tak tersedia null. Jangan menebak.\n\nDOKUMEN:\n" + text_content
                        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
                        extracted = str(response.text or "{}")
                    else:
                        extracted = extract_document_with_gemini(GEMINI_API_KEY, GEMINI_MODEL, file_bytes, mime_type, uploaded_file.name)
                    st.session_state["document_extraction"] = extracted
                except Exception as exc:
                    st.error(f"Ekstraksi gagal: {exc}")
        if st.session_state.get("document_extraction"):
            st.code(st.session_state["document_extraction"], language="json")
            st.download_button("Unduh hasil ekstraksi", st.session_state["document_extraction"].encode("utf-8"), file_name="document_extraction.json", mime="application/json", key="download_extract")
            st.caption("Hasil ekstraksi tidak mengisi form otomatis. Periksa setiap nilai terhadap dokumen asli sebelum digunakan.")

    with st.expander("C. Memo keputusan investasi dari kalkulasi Python", expanded=True):
        ai_payload = {
            "property": property_data,
            "fees": fees_data,
            "costs": costs_data,
            "finance": finance_data,
            "market": market_result,
            "current_calculation": current_calculation,
            "bid_analysis": bid_analysis,
            "decision": decision,
        }
        if st.button("Buat / perbarui memo AI", key="run_ai_memo", disabled=not bool(GEMINI_API_KEY), use_container_width=True):
            try:
                from services.gemini_client import write_investment_memo
                with st.spinner("Gemini sedang menyusun memo berbasis hasil Python..."):
                    st.session_state["ai_memo"] = write_investment_memo(GEMINI_API_KEY, GEMINI_MODEL, ai_payload)
                st.rerun()
            except Exception as exc:
                st.error(f"Memo AI gagal dibuat: {exc}")
        if st.session_state.get("ai_memo"):
            st.markdown(st.session_state["ai_memo"])
            st.download_button("Unduh memo AI", st.session_state["ai_memo"].encode("utf-8"), file_name="ai_investment_memo.md", mime="text/markdown", key="download_ai_memo")

# -------- History tab --------
with history_slot.container():
    st.subheader("Riwayat analisis")
    st.write("Snapshot lokal hanya bertahan selama session aktif. Unduh JSON atau hubungkan Supabase untuk arsip lintas sesi.")
    local_history = st.session_state.get("analysis_history", [])
    if local_history:
        hist_rows = []
        for idx, item in enumerate(local_history):
            hist_rows.append({
                "No.": idx + 1,
                "Tanggal": item.get("analysis_date", "—"),
                "Objek": item.get("property", {}).get("name", "Tanpa nama"),
                "Lokasi": item.get("property", {}).get("address", "—"),
                "Keputusan": item.get("decision", {}).get("status", "—"),
                "Profit": idr(item.get("current_calculation", {}).get("net_profit")),
                "ROI": (f"{item.get('current_calculation', {}).get('roi_pct'):.1f}%" if item.get("current_calculation", {}).get("roi_pct") is not None else "—"),
            })
        st.dataframe(pd.DataFrame(hist_rows), use_container_width=True, hide_index=True)
        st.download_button("Unduh seluruh riwayat session sebagai JSON", json.dumps(local_history, ensure_ascii=False, indent=2, default=str).encode("utf-8"), file_name="auction_analysis_history.json", mime="application/json")
    else:
        st.info("Belum ada snapshot. Gunakan tombol Simpan analisis pada dashboard.")

    if is_configured(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY):
        if st.button("Muat arsip Supabase", key="load_supabase_history"):
            try:
                st.session_state["supabase_history"] = list_snapshots(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
            except Exception as exc:
                st.error(f"Gagal mengambil riwayat Supabase: {exc}")
        saved_rows = st.session_state.get("supabase_history", [])
        if saved_rows:
            st.markdown("#### Snapshot di Supabase")
            st.dataframe(pd.DataFrame([{"ID": r.get("id"), "Tanggal": r.get("analysis_date"), "Objek": r.get("project_name"), "Keputusan": r.get("status")} for r in saved_rows]), use_container_width=True, hide_index=True)
            st.download_button("Unduh arsip Supabase sebagai JSON", json.dumps(saved_rows, ensure_ascii=False, indent=2, default=str).encode("utf-8"), file_name="supabase_analysis_history.json", mime="application/json")
    else:
        st.caption("Supabase belum terkonfigurasi. Lihat README.md dan supabase_schema.sql untuk mengaktifkan database permanen.")

st.sidebar.divider()
st.sidebar.markdown("### Konfigurasi")
st.sidebar.write(f"Gemini: {'aktif' if GEMINI_API_KEY else 'belum diatur'}")
st.sidebar.write(f"Supabase: {'aktif' if is_configured(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY) else 'belum diatur'}")
st.sidebar.markdown("### Catatan")
st.sidebar.caption("Tarif pajak/biaya dan estimasi exit harus diverifikasi. Jangan menawar hanya berdasarkan skor total jika hard-stop masih terbuka.")
