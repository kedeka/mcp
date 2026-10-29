---
name: laporan-keuangan
description: Ringkas laporan keuangan bisnis di Kedeka untuk satu periode. Gunakan saat pengguna bertanya omzet, PPN, PPh, pengeluaran, laba, pembayaran yang diterima, klien teratas, atau perbandingan antarbulan.
---

# Laporan keuangan

1. Tentukan periode dari pertanyaan pengguna (misalnya "bulan ini", "kuartal lalu", "2026"). Bila tidak jelas, tanyakan.
2. Panggil `get_financial_report` untuk periode itu. Angkanya sama dengan halaman Laporan di Kedeka.
3. Mulai dengan angka yang ditanyakan, lalu tambahkan konteks singkat: omzet, omzet bersih, PPN, PPh dipotong, pengeluaran, dan laba. Sebutkan rincian per bulan atau klien teratas hanya bila relevan.
4. Untuk rincian pengeluaran atau pembayaran, pakai `search_expenses` atau `search_payments`.

Batasan:

- Perkiraan PPh Final 0,5% hanyalah perkiraan, bukan perhitungan pajak resmi. Sampaikan itu setiap kali menyebutnya.
- Laporan hanya untuk pemilik atau admin workspace. Bila ditolak, sampaikan apa adanya dan jangan menghitung ulang dari data lain.
- Tulis nominal dalam Rupiah dengan pemisah ribuan titik.
