# Checklist pengumpulan — FinTechathon 2026, International Track, Topik F

**Tenggat daftar + kumpul karya: Selasa 20 Okt 2026, 23:59 waktu Beijing = 22:59 WIB.**
**Target aman: semua sudah terkirim paling lambat Selasa 20 Okt pukul 18:00 WIB.**
Email pendaftaran sebaiknya terkirim **hari ini (Senin 19 Okt)** karena panitia membalas dalam ≤ 48 jam.

Diperbarui: Senin 19 Okt 2026, ±16:00 WIB.

---

## A. Apa kata aturan resmi (dicek 19 Okt dari dokumen + situs resmi)

* **Kanal:** semua lewat **email resmi fintechathon@ican-x.com**. Situs (halaman Rules → International Track): *"Register by official email, select one of six topics and submit the required English materials by 24:00 on 20 October (UTC+8)."* Tidak ada portal upload.
* **Subjek email pendaftaran** (dari formulir): `International Track Registration – Team Name – Team Leader Name`.
* **Tim 2–5 orang**, ≥ 60% bukan WN Tiongkok, mahasiswa full-time kampus luar Tiongkok, usia ≥ 18. Satu orang hanya boleh di satu tim. **Tim satu orang tidak sah.**
* **Bahasa Inggris** untuk semua materi.
* **Aturan AI:** tidak ada larangan memakai alat AI di dokumen aturan maupun situs. Yang dilarang: plagiarisme, pelanggaran HKI, kecurangan. Komponen open-source harus berlisensi benar (repo ini MIT; forge-std MIT/Apache, OpenZeppelin MIT).
* **Perbedaan dengan analisis 9 Okt (ikuti yang lebih ketat):**
  1. **Video demo**: docx aturan menulis *optional*, tetapi halaman Rules di situs menulis **"Demo video, up to 5 minutes (Required)"**. → Anggap **wajib**.
  2. Situs menyediakan **template resmi**: Technical Document (.docx), Presentation (.pptx), Demo Video Guide, README, Security Self-assessment, Execution Evidence. Isi kita sudah mencakup semua bagian template (lihat bagian D). Memakai template tidak disebut wajib.
  3. Situs juga menautkan formulir kedua, `team-information-form.xlsx` (nama, kewarganegaraan, kampus, jurusan, angkatan, email, telepon). Formulir utama tetap **Attachment 3** (`international-registration-form-en.xlsx`). Supaya aman, lampirkan keduanya.
  4. Formulir: *"no scans are required at registration"* untuk nomor paspor/ID, tetapi kolom L meminta **gambar halaman biodata paspor** dan instruksi 4 meminta **scan bukti status mahasiswa**. → Lampirkan keduanya.

---

## B. Status setiap item wajib

| # | Item | Status | Keterangan |
|---|---|---|---|
| 0 | Email pendaftaran + formulir | 🟡 perlu kamu | Draf: `submission/REGISTRATION_EMAIL_DRAFT.md`. Formulir sudah diisi bagian non-pribadi: `submission/registration-form-TOFILL.xlsx` (+ `team-information-form-TOFILL.xlsx`) |
| 1 | Dokumentasi teknis | ✅ selesai | `docs/TECHNICAL_DOCUMENTATION.md` (+ PDF lewat `--pdf`, langkah 5) |
| 2 | Deck ≤ 10 menit | ✅ selesai (cek isi) | `submission/Kendali_FinTechathon2026_Deck.pptx`, 12 slide, catatan pembicara ±1.250 kata ≈ 8,3–9,6 menit. Placeholder nama tim sudah diganti "Kendali". Sisa 1 placeholder: link GitHub di slide 12 (otomatis terisi di langkah 5) |
| 3 | Video demo ≤ 5 menit | 🟡 perlu kamu | Naskah + shot list: `submission/DEMO_VIDEO_SCRIPT.md` |
| 4 | Source code + README + cara deploy + test case | 🟡 perlu kamu (push) | Repo lokal siap & sudah di-commit. README sudah GitHub-ready. Tinggal buat repo GitHub + push |
| 5 | Security self-assessment | ✅ selesai | `docs/SECURITY_SELF_ASSESSMENT.md` |
| 6 | Bukti eksekusi: **hash transaksi on-chain asli** | 🟡 perlu kamu (isi faucet) | Kunci Sepolia sudah dibuat (`.env`, tidak ikut git). Gladi di fork Sepolia sukses 14/14 langkah. Tinggal isi saldo alamat deployer lalu jalankan 1 perintah |

Hasil verifikasi ulang 19 Okt (Windows 11, Python 3.11.9, Foundry 1.8.5): **pytest 84/84 lulus · forge test 18/18 lulus · eval 57/57 skenario lulus (113 transaksi)** (setelah perbaikan red-team).

---

## C. Langkah yang harus kamu kerjakan, berurutan

### 1. Pastikan tim sah (2–5 orang) — 15 menit, HARI INI
Formulir dan aturan menolak tim satu orang. Kumpulkan dari tiap anggota: nama lengkap sesuai paspor, gender, usia, kewarganegaraan, jenis + nomor paspor/ID, NIM, jurusan, angkatan (mis. `UG Year 4`), email, WhatsApp, foto halaman biodata paspor, bukti mahasiswa aktif (KTM atau surat keterangan aktif kuliah).

### 2. Isi formulir — 20 menit, HARI INI
1. Buka `submission/registration-form-TOFILL.xlsx` di Excel.
2. Sudah terisi: Team Name `Kendali`, Topic `F`, Entry Title, baris 11–12 kolom Role, Country (`Indonesia`), University (`Institut Teknologi Bandung`). Ganti kalau anggota dari kampus/negara lain.
3. Isi sendiri: B7 Team Email (wajib), B5 Advisor (opsional), B6 Proposal Summary (opsional; ada draf di `REGISTRATION_EMAIL_DRAFT.md`, tulis ulang dengan kata-katamu), dan semua kolom anggota (B–O). Dropdown di kolom D dan H salah tempat (bawaan template); ketik saja nilainya.
4. Baris 19: tanda tangan ketua + tanggal (boleh gambar tanda tangan atau ketik nama).
5. **Simpan sebagai** `Kendali_International_Registration_Form.xlsx` **di luar folder repo** atau di `submission/private/` (folder ini di-ignore git). File ini berisi data pribadi: jangan pernah di-commit.
6. (Opsional, disarankan) Isi juga `team-information-form-TOFILL.xlsx` dengan cara yang sama.

### 3. Kirim email pendaftaran — 10 menit, HARI INI (target sebelum 21:00 WIB)
* Ke: `fintechathon@ican-x.com` · Subjek: `International Track Registration – Kendali – [Nama Lengkap Ketua]`
* Lampiran: formulir xlsx terisi + foto biodata paspor tiap anggota + bukti mahasiswa aktif tiap anggota.
* Isi: salin dari `submission/REGISTRATION_EMAIL_DRAFT.md` (Email 1), ganti semua `[...]`.

### 4. Isi saldo Sepolia lalu jalankan bukti on-chain — 15–60 menit (tergantung faucet) + 6 menit jalan
**Alamat deployer (publik, aman dibagikan):**

```
0x1bD652D9EaF19f2a1869932A374528D3332103f8
```

* Butuh **minimal 0,05 Sepolia ETH** (terukur di gladi), 0,1 lebih lega. Gas Sepolia sekarang sangat murah (base fee ±16 wei).
* Pilihan faucet (cek sendiri syarat terbarunya; semua butuh login/captcha, jadi harus kamu yang klik):
  * **Google Cloud Web3 Faucet** (cloud.google.com/application/web3/faucet/ethereum/sepolia): login akun Google, ±0,05 ETH/hari.
  * **Sepolia PoW Faucet** (sepolia-faucet.pk910.de): tanpa akun, "menambang" di browser ±15–60 menit.
  * **Alchemy / QuickNode / Infura (MetaMask) faucet**: perlu akun dan biasanya saldo kecil ETH mainnet.
  * Paling cepat: minta teman yang punya Sepolia ETH mengirim 0,05–0,1 ETH ke alamat di atas.
* Cek saldo masuk: buka `https://sepolia.etherscan.io/address/0x1bD652D9EaF19f2a1869932A374528D3332103f8`.
* Lalu di terminal (PowerShell), dari folder repo:

```powershell
cd C:\Users\POGGY\Downloads\barengpoggy\FinTechathon2026\kendali
$env:KENDALI_ANVIL = "C:\Users\POGGY\Downloads\barengpoggy\FinTechathon2026\tools\foundry-v1.8.5\anvil.exe"
.\.venv-local\Scripts\python.exe scripts\testnet_evidence.py
```
* Hasil: `reports/TESTNET_EVIDENCE.md` berisi link Etherscan tiap transaksi. Buka 2–3 link untuk memastikan (terutama baris "stolen agent key … REVERTED": status harus **Fail**).
* Salin alamat vault + 6 hash utama ke tabel "Public Sepolia hashes" di `docs/EXECUTION_EVIDENCE.md` (cari `FILL-AFTER-SEPOLIA-RUN`) dan ubah status E1 dari PENDING ke Done.
* Commit:

```powershell
git add reports/TESTNET_EVIDENCE.md reports/testnet-evidence.json deployments/sepolia-11155111.json docs/EXECUTION_EVIDENCE.md
git commit -m "Add public Sepolia execution evidence"
Rename-Item .env .env.sepolia    # supaya demo lokal kembali ke devnet
```

Kalau faucet gagal sampai Selasa siang: tetap kirim karya. Di email tulis jujur bahwa hash Sepolia menyusul, dan lampirkan `reports/EVAL_REPORT.md` (113 transaksi di devnet lokal). Karya boleh diperbarui sampai tenggat.

### 5. Buat repo GitHub dan push — 10 menit
1. Buka github.com → **New repository** → nama `kendali` → **Public** → *jangan* centang README/.gitignore/license (sudah ada) → Create.
2. Di terminal:

```powershell
cd C:\Users\POGGY\Downloads\barengpoggy\FinTechathon2026\kendali
.\.venv-local\Scripts\python.exe scripts\finalize_submission.py --repo-url https://github.com/poggymacello/kendali --pdf
git status                 # pastikan TIDAK ada .env, .venv-local, xlsx, foto paspor
git add -A
git commit -m "Set repository URL"
git branch -M main
git remote add origin https://github.com/poggymacello/kendali.git
git push -u origin main
```
`finalize_submission.py` mengganti placeholder username GitHub di README, dokumen, dan deck (slide 12), lalu membuat PDF lampiran di `submission/pdf/`. Cek `--check` harus menampilkan `0 open placeholder(s)`.
3. Buka repo di browser: pastikan README tampil, gambar arsitektur muncul, dan `.env` **tidak** ada.

### 6. Rekam video demo — 60–90 menit
Ikuti `submission/DEMO_VIDEO_SCRIPT.md`: ±4:30, 1080p, subtitle Inggris, nama file `InternationalAI-Kendali-DemoVideo.mp4`. Upload ke YouTube (Unlisted) atau Google Drive (Anyone with the link). Jangan tampilkan `.env`, paspor, atau nomor HP.

### 7. Cek deck — 15 menit
* Slide 1 & 12: nama tim "Kendali" (ganti lewat `finalize_submission.py --team "Nama"` kalau beda).
* Slide 9 dan 11 menyebut hash public testnet. **Kalau langkah 4 belum berhasil**, ubah kalimat itu (mis. "Public-testnet run: hashes to follow") agar tidak overclaim.
* Latih bicara dengan timer: ≤ 10 menit.
* Ekspor juga ke PDF (File → Export → PDF).

### 8. Kirim email karya — 15 menit, Selasa 20 Okt, paling lambat 18:00 WIB
* Balas di thread email pendaftaran (Email 2 di `REGISTRATION_EMAIL_DRAFT.md`).
* Lampiran: 3 PDF dari `submission/pdf/` + deck `.pptx` (+ PDF-nya) · link GitHub · link video.
* Setelah kirim: cek folder Sent, simpan screenshot bukti kirim + jam.
* Pantau balasan panitia; kalau ada perbaikan, kirim versi baru sebelum 22:59 WIB (versi terakhir yang dipakai).

---

## D. Pemetaan ke template resmi

| Template resmi (situs) | Bagian template | Ada di |
|---|---|---|
| Technical Document | Overview, Architecture, Agent Design, Security Design, Deployment & Testing | `docs/TECHNICAL_DOCUMENTATION.md` §1–§10 |
| Security Self-assessment | Permission model, Security tests, Data & privacy, Known risks | `docs/SECURITY_SELF_ASSESSMENT.md` |
| Execution Evidence | Summary, Logs/transactions (hash Topik F), Reproduction guide | `docs/EXECUTION_EVIDENCE.md` + `reports/TESTNET_EVIDENCE.md` |
| Source Code README | Overview, Architecture, Environment, Install, Testing, Repository, Security | `README.md` |
| Demo Video Guide | struktur 3 bagian, 16:9, 1080p, subtitle, nama file | `submission/DEMO_VIDEO_SCRIPT.md` |
| Presentation | deck ≤ 10 menit | `submission/Kendali_FinTechathon2026_Deck.pptx` |

## E. Estimasi waktu total kamu
≈ 3,5–4,5 jam kerja aktif (tim + formulir 35 mnt, email 10 mnt, faucet 15–60 mnt + run 6 mnt, GitHub 10 mnt, video 60–90 mnt, cek deck 15 mnt, email karya 15 mnt).
