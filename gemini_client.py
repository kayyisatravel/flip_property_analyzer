"""Optional Gemini integration. Deterministic financial calculations stay in Python."""
from __future__ import annotations

import json
from typing import Any


def _client(api_key: str):
    try:
        from google import genai
    except ImportError as exc:  # pragma: no cover - depends on optional installation
        raise RuntimeError("Paket google-genai belum terpasang. Jalankan pip install -r requirements.txt.") from exc
    return genai.Client(api_key=api_key)


def grounded_market_research(api_key: str, model: str, query: str) -> str:
    """Research current market information using Gemini's Google Search grounding."""
    client = _client(api_key)
    prompt = f"""Anda adalah analis riset pasar properti Indonesia. Teliti permintaan berikut menggunakan Google Search.
Permintaan: {query}

Ketentuan:
- Utamakan listing yang relevan dan masih baru; tuliskan tanggal pencarian dan tanggal listing bila terlihat.
- Untuk setiap pembanding, tuliskan kompleks/alamat area, harga penawaran atau harga transaksi, LT/LB, kondisi, sertifikat jika tersedia, status listing, tanggal, dan URL sumber.
- Pisahkan harga penawaran dari transaksi yang benar-benar terverifikasi. Jangan menyebut listing aktif sebagai harga transaksi.
- Jangan mengarang detail yang tidak ditemukan; tulis "tidak tercantum".
- Cari minimal 5 kandidat bila tersedia. Jika tidak, katakan keterbatasannya.
- Akhiri dengan rentang indikasi awal, tingkat keyakinan, dan hal yang wajib diverifikasi secara manual.
- Sertakan tautan sumber yang dapat diklik.
- Ini riset awal, bukan appraisal dan bukan bukti harga transaksi final.
Jawab dalam Bahasa Indonesia dengan tabel yang mudah disalin."""
    response = client.interactions.create(
        model=model,
        input=prompt,
        tools=[{"type": "google_search"}],
    )
    answer = str(getattr(response, "output_text", "") or "Tidak ada teks hasil dari Gemini.")
    citations: list[tuple[str, str]] = []
    for step in (getattr(response, "steps", None) or []):
        if getattr(step, "type", None) != "model_output":
            continue
        for block in (getattr(step, "content", None) or []):
            if getattr(block, "type", None) != "text":
                continue
            for annotation in (getattr(block, "annotations", None) or []):
                if getattr(annotation, "type", None) == "url_citation":
                    url = str(getattr(annotation, "url", "") or "").strip()
                    title = str(getattr(annotation, "title", "") or url).strip()
                    if url and (url, title) not in citations:
                        citations.append((url, title))
    if citations:
        answer += "\n\n### Referensi grounding Gemini\n" + "\n".join(f"- [{title}]({url})" for url, title in citations)
    return answer


def write_investment_memo(api_key: str, model: str, payload: dict[str, Any]) -> str:
    """Explain Python-calculated results without altering numerical outputs."""
    client = _client(api_key)
    prompt = f"""Tulis memo keputusan investasi rumah lelang dalam Bahasa Indonesia berdasarkan payload JSON berikut.

ATURAN WAJIB:
1. Angka financial engine di payload adalah sumber kebenaran. Jangan mengubah, membulatkan secara berbeda, atau menghitung ulang angka keuangan.
2. Bedakan fakta terverifikasi, informasi sumber, asumsi, dan hal yang belum terverifikasi.
3. Jangan mengarang harga pasar, transaksi, status hukum, tarif pajak, atau biaya.
4. Jelaskan alasan keputusan, target pembeli, skenario downside, mitigasi yang realistis, batas bid, kebutuhan modal, estimasi holding, dan apa yang membuat keputusan berubah.
5. Jika status HOLD/NO-GO, jangan mengubah rekomendasi menjadi GO hanya karena ada peluang keuntungan.
6. Nyatakan bahwa pajak/biaya harus dikonfirmasi untuk lot dan wilayah ini, dan memo bukan nasihat hukum/perpajakan/appraisal.

PAYLOAD:
{json.dumps(payload, ensure_ascii=False, default=str, indent=2)}
"""
    response = client.models.generate_content(model=model, contents=prompt)
    return str(getattr(response, "text", "") or "Tidak ada teks hasil dari Gemini.")


def extract_document_with_gemini(
    api_key: str, model: str, file_bytes: bytes, mime_type: str, filename: str = "dokumen"
) -> str:
    """Extract structured property-auction facts from an image/PDF using Gemini multimodal input."""
    from google.genai import types

    client = _client(api_key)
    instruction = f"""Ekstrak informasi dari dokumen lelang/properti bernama {filename}.
Kembalikan JSON valid tanpa markdown fence dengan skema:
{{
  "nama_objek": null,
  "alamat": null,
  "kode_lot": null,
  "limit_lelang_idr": null,
  "uang_jaminan_idr": null,
  "tanggal_lelang": null,
  "luas_tanah_m2": null,
  "luas_bangunan_m2": null,
  "jenis_sertifikat": null,
  "nomor_hak": null,
  "penghuni_atau_penguasaan": null,
  "tunggakan_yang_disebutkan": null,
  "dokumen_yang_disebutkan": [],
  "catatan_penting": [],
  "data_belum_jelas": [],
  "kutipan_pendek_pendukung": []
}}
Aturan: nilai yang tidak ditemukan harus null atau array kosong. Jangan menebak. Jika beberapa nilai bertentangan, cantumkan di catatan dan data_belum_jelas. Semua nilai uang sebagai angka Rupiah tanpa pemisah ribuan. Pertahankan bahasa dokumen bila dibutuhkan. Ini hanya ekstraksi awal; pengguna harus memverifikasi ke dokumen asli."""
    part = types.Part.from_bytes(data=file_bytes, mime_type=mime_type)
    response = client.models.generate_content(model=model, contents=[instruction, part])
    return str(getattr(response, "text", "") or "{}")
