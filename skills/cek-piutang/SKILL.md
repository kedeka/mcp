---
name: cek-piutang
description: Cek invoice yang belum dibayar, piutang per umur, dan detail invoice di Kedeka. Gunakan saat pengguna bertanya siapa yang belum bayar, invoice yang lewat jatuh tempo, total tagihan, atau ingin membuka satu invoice, penawaran, kuitansi, atau proposal.
---

# Cek piutang dan dokumen

1. Untuk gambaran piutang, panggil `get_receivables`. Tampilkan total per umur (belum jatuh tempo, 0-30, 31-60, 61-90, lebih dari 90 hari), lalu klien dengan piutang terbesar, lalu invoice yang paling lama lewat jatuh tempo.
2. Untuk dokumen tertentu, panggil `search_documents` dengan nama klien, nomor, atau status, lalu `get_document` untuk dokumen yang dipilih. Tampilkan baris item, subtotal, pajak, total, pembayaran, dan sisa tagihan.
3. Bila hasil pencarian berisi `selection.required: true`, tanyakan ke pengguna dokumen mana yang dimaksud. Jangan memilih sendiri.
4. Tulis nominal dalam Rupiah dengan pemisah ribuan titik, misalnya Rp8.325.000.

Batasan:

- Bagian ini hanya membaca data. Jangan mengubah status atau mencatat pembayaran kecuali pengguna memintanya.
- Kedeka tidak mengirim invoice ke email klien dari percakapan. Bila diminta, jelaskan bahwa pengiriman dilakukan dari dashboard Kedeka dan berikan link dokumennya.
- `get_receivables` hanya untuk pemilik atau admin workspace. Bila ditolak, sampaikan apa adanya.
