# Auction Flip Analyzer

Streamlit MVP untuk analisis kelayakan rumah lelang dan property flipping. Kerangka kerja mengutamakan **Sell first, buy second**: perkirakan exit yang bisa dipertanggungjawabkan, hitung biaya dan risiko, baru tentukan maximum bid.

## Fitur yang tersedia

- Input objek lelang, kode lot, link, limit, deposit, LT/LB, sertifikat, legalitas, dan penguasaan fisik.
- Tabel comparable manual dengan skor kualitas transparan, penyesuaian ukuran heuristik, weighted median, serta rentang conservative/base/optimistic.
- Mesin biaya deterministik: bea lelang pembeli, BPHTB berdasarkan dasar yang dipilih, PPN hanya jika diaktifkan, legal/sertifikat, renovasi, penguasaan/kerahiman, holding, contingency, pajak/fee penjual, dan marketing.
- Hurdle rate dinamis: profit minimum, ROI minimum atas modal pra-penjualan, profit bulanan, maksimum holding, dan kemampuan kas.
- Pencarian numerik recommended ceiling (exit konservatif + risk ceiling) dan absolute maximum (exit base), mengikuti increment bid.
- Perbandingan empat skenario penguasaan sebagai alternatif (bukan menjumlahkan kerahiman + eksekusi sekaligus), dengan kebutuhan modal skenario terburuk dan tambahan cadangan.
- RAB renovasi itemized serta porsi anggaran yang masih berkepastian rendah; biaya kesempatan modal opsional dan terpisah dari kebutuhan kas aktual.
- Risk-weighted score dan hard stops: legal belum diverifikasi, identitas objek belum cocok, penguasaan belum terverifikasi, aturan pajak belum diverifikasi, pembanding lemah, dan kemampuan pendanaan belum dikonfirmasi.
- Gemini opsional untuk Google Search grounding, ekstraksi dokumen/foto/PDF, dan investment memo. Gemini menjelaskan; Python menghitung.
- Ekspor laporan Markdown dan snapshot JSON. Supabase opsional untuk riwayat lintas sesi.

## Apa yang belum otomatis

- Aplikasi **belum melakukan scraping langsung ke semua portal properti**. Setiap portal memiliki kebijakan/akses yang berbeda; hasil riset Gemini harus diverifikasi, lalu dimasukkan ke tabel comparable.
- Snapshot tidak otomatis bertahan lintas sesi kecuali Supabase dikonfigurasi. Download JSON untuk arsip lokal.
- Perhitungan pajak tidak mengklaim penetapan legal yang final. Tarif dan NPOPTKP sengaja harus dikonfirmasi; NPOPTKP default 0 agar aplikasi tidak diam-diam memilih asumsi Rp60 juta atau Rp80 juta.
- Tidak ada OCR khusus untuk semua jenis scan. Gemini multimodal dapat membantu, tetapi hasilnya harus dibandingkan dengan dokumen asli.
- Login bawaan adalah single shared password untuk MVP, bukan sistem multi-user. Set `APP_PASSWORD` sebelum aplikasi dipakai melalui internet.

## A. Jalankan di komputer sendiri (Windows)

1. Instal Python 3.12 dari [python.org](https://www.python.org/downloads/) dan centang **Add Python to PATH**.
2. Ekstrak ZIP proyek ini ke folder seperti `C:\auction-flip-analyzer`.
3. Buka Command Prompt / PowerShell di folder proyek tersebut.
4. Jalankan:

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   streamlit run app.py
   ```

   Jika PowerShell menolak aktivasi environment, buka Command Prompt dan jalankan `.venv\Scripts\activate.bat`, kemudian lanjutkan dari `pip install -r requirements.txt`.
5. Browser akan membuka alamat lokal Streamlit. Kalkulator dasar bisa digunakan tanpa API key Gemini.
6. Untuk mengaktifkan Gemini lokal, salin `.streamlit/secrets.toml.example` menjadi `.streamlit/secrets.toml`, lalu isi `GEMINI_API_KEY` dan `APP_PASSWORD`. Jangan pernah mengunggah `secrets.toml` ke GitHub. Cara membuat Gemini API key: [Google AI Studio](https://aistudio.google.com/apikey).

## B. Buat repository GitHub dari awal

### Cara yang disarankan (GitHub Desktop — tidak perlu mengetik banyak perintah)

1. Buat akun/masuk ke [GitHub](https://github.com/) dan instal [GitHub Desktop](https://desktop.github.com/).
2. Ekstrak ZIP ini. Di GitHub Desktop pilih **File → Add Local Repository** lalu pilih folder `auction-flip-analyzer`.
3. Jika folder belum menjadi repository, pilih tautan **create a repository** pada dialog yang muncul. Pastikan root repository adalah folder proyek yang berisi `app.py`, `core`, `services`, dan `requirements.txt`.
4. Isi nama repository `auction-flip-analyzer`, lalu buat repository lokal.
5. Di GitHub Desktop pilih **Publish repository**. Untuk data kode yang tidak sensitif, repository bisa public; jika ingin private, matikan opsi public. Klik **Publish Repository**.
6. Setelah publish, buka repository di GitHub dan pastikan `app.py`, `requirements.txt`, `core/`, `services/`, dan file lainnya tampak di root repository, bukan terkubur di folder ZIP.
7. Pastikan `.streamlit/secrets.toml` tidak ada di GitHub. File tersebut sudah dikecualikan oleh `.gitignore` bila dibuat setelah ekstraksi.

### Alternatif lewat Git command line

Buat repository kosong di GitHub terlebih dahulu, tanpa README/license awal. Buka terminal di root folder proyek, lalu ganti `USERNAME` dengan username GitHub Anda:

```bash
git init
git add .
git commit -m "Initial Auction Flip Analyzer"
git branch -M main
git remote add origin https://github.com/USERNAME/auction-flip-analyzer.git
git push -u origin main
```

Git mungkin meminta login melalui browser. Setelah kode diperbarui, gunakan `git add .`, `git commit -m "Update analyzer"`, dan `git push`.

## C. Deploy ke Streamlit Community Cloud

1. Pastikan repository GitHub sudah memiliki `app.py` dan `requirements.txt` di root.
2. Buka [Streamlit Community Cloud](https://share.streamlit.io/) dan masuk menggunakan akun GitHub yang sama.
3. Pilih **Create app** → pilih repository `USERNAME/auction-flip-analyzer`, branch `main`, dan main file path `app.py`.
4. Di **Advanced settings**, pilih Python 3.12 bila tersedia.
5. Isi bagian **Secrets** sebelum menjalankan aplikasi. Minimal, gunakan kata sandi yang kuat:

   ```toml
   APP_PASSWORD = "GANTI_DENGAN_PASSWORD_PANJANG_DAN_UNIK"
   ```

   Untuk Gemini, tambahkan:

   ```toml
   GEMINI_API_KEY = "API_KEY_ANDA"
   GEMINI_MODEL = "gemini-3.8-flash"
   ```

   Untuk Supabase, tambahkan juga `SUPABASE_URL` dan `SUPABASE_SERVICE_ROLE_KEY` setelah mengikuti bagian E di bawah.
6. Klik **Deploy**. Setelah deploy, aplikasi menampilkan URL berakhiran `streamlit.app`. Uji login, kalkulasi, ekspor, dan log aplikasi.
7. Setiap `git push` ke branch yang dipakai akan memicu pembaruan deployment. Jangan memasukkan API key ke source code.

Dokumentasi resmi deployment: [Deploy Streamlit app](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app) dan [Streamlit secrets](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management).

## D. Mengaktifkan Gemini Flash

1. Buat API key melalui [Google AI Studio](https://aistudio.google.com/apikey).
2. Masukkan sebagai `GEMINI_API_KEY` di local `secrets.toml` atau Streamlit Cloud Secrets.
3. Default model adalah `gemini-3.8-flash`, tetapi dapat diganti dengan `GEMINI_MODEL` tanpa mengubah kode.
4. Fitur Google Search grounding dapat dikenai kuota/biaya API sesuai akun dan skema harga Google yang berlaku. Pantau billing/usage di akun Google Anda.
5. AI hanya mendukung riset/ekstraksi/penjelasan. Verifikasi URL listing, status, LT/LB, tanggal, dan pajak secara manual. Perhitungan angka/maximum bid tetap berasal dari Python.

## E. Mengaktifkan penyimpanan permanen dengan Supabase (opsional)

Tanpa Supabase, riwayat hanya ada dalam session aktif dan harus diunduh sebagai JSON untuk disimpan permanen.

1. Buat project di [Supabase](https://supabase.com/).
2. Buka **SQL Editor**, salin isi `supabase_schema.sql`, lalu jalankan.
3. Dari **Project Settings → API**, salin Project URL dan `service_role` key. Jangan pakai key ini di kode front-end atau repository; key hanya boleh berada di Streamlit Secrets.
4. Tambahkan ke Secrets:

   ```toml
   SUPABASE_URL = "https://PROJECT_ID.supabase.co"
   SUPABASE_SERVICE_ROLE_KEY = "SERVICE_ROLE_KEY_ANDA"
   ```
5. Simpan snapshot dari dashboard. Buka tab **Riwayat** dan klik **Muat arsip Supabase**.

MVP ini memakai satu password aplikasi bersama. Jika beberapa orang akan mengakses aplikasi, Anda perlu autentikasi individual dan otorisasi data per pengguna sebelum menyimpan data finansial sensitif.

## Struktur repository

```text
auction-flip-analyzer/
├── app.py
├── core/
│   ├── calculator.py       # biaya, profit, ROI, holding, kas
│   ├── maximum_bid.py      # numerical search untuk batas bid
│   ├── tax_rules.py        # helper BPHTB berbasis parameter input
│   ├── market_engine.py    # skor comparable dan rentang harga
│   ├── occupancy.py        # perbandingan empat skenario penguasaan
│   ├── renovation.py       # RAB itemized / confidence
│   ├── risk_engine.py      # skor risiko berbobot
│   └── decision_engine.py  # GO / CONDITIONAL / HOLD / NO-GO
├── services/
│   ├── gemini_client.py    # Gemini, Search grounding, memo & ekstraksi
│   └── document_parser.py  # ekstraksi lokal PDF/TXT/DOCX
├── storage/repository.py  # Supabase optional
├── reports/report_builder.py
├── rules/fee_rules.yaml   # checklist rule/versioning, bukan tarif legal final
├── tests/
├── supabase_schema.sql
├── requirements.txt
└── README.md
```

## F. Uji otomatis di lokal

```powershell
pytest -q
```

## Definisi finansial

- **Modal pra-penjualan** = harga bid + bea lelang + BPHTB + PPN jika berlaku + legal/sertifikat + renovasi + penguasaan + holding + contingency.
- **Net proceeds** = closing price dikurangi biaya penjualan.
- **Net profit** = net proceeds dikurangi modal pra-penjualan.
- **ROI** = net profit / modal pra-penjualan × 100%.
- **Profit per month** = net profit / total holding dari pembelian sampai aset terjual.
- **Kas proyek tersedia** = kas aktual - komitmen proyek berjalan - cadangan rumah tangga - cadangan risiko. Piutang belum cair tidak masuk kas tersedia.
- Uang jaminan dibutuhkan sebelum lelang dan diasumsikan dikreditkan ke pelunasan jika menang. Karena itu uang jaminan tidak ditambahkan sekali lagi sebagai biaya akuisisi.
- **Recommended ceiling** memakai exit konservatif, hurdle rate, kapasitas kas, dan overlay risk ceiling.
- **Absolute maximum** memakai exit base dan hurdle rate serta kapasitas kas, tanpa overlay risk ceiling. Angka ini bukan anjuran untuk membid di sana.
- **Walk-away price** sama dengan recommended ceiling; jika limit lebih tinggi atau hasil tidak lolos target, jangan menawar pada konfigurasi tersebut.

## Keterbatasan / disclaimer

Aplikasi adalah alat bantu screening dan bukan pengganti appraisal KJPP, pemeriksaan hukum/PPAT/advokat, konfirmasi pajak ke pemda/DJP/KPKNL, inspeksi teknis bangunan, atau verifikasi okupansi. Output GO pun bukan jaminan aset akan laku pada harga dan waktu yang diproyeksikan. Selalu simpan sumber dan tanggal verifikasi.
