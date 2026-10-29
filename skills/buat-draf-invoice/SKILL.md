---
name: buat-draf-invoice
description: Buat atau ubah draf invoice dan penawaran (quote) di Kedeka dari klien dan produk yang sudah ada. Gunakan saat pengguna meminta membuatkan invoice, tagihan, penawaran harga, mengubah draf, atau menjadikan penawaran sebagai invoice.
---

# Buat draf invoice atau penawaran

1. Cari klien dengan `search_clients` dan produk atau jasa dengan `search_catalog_items`. Pakai harga dan satuan dari katalog kecuali pengguna menyebut harga lain.
2. Bila klien atau produk tidak ditemukan, tanyakan ke pengguna apakah perlu ditambahkan (`create_client`, `create_catalog_item`) sebelum lanjut.
3. Bila hasil berisi `selection.required: true`, tanyakan ke pengguna data mana yang dimaksud.
4. Tunjukkan ringkasan sebelum menyimpan: jenis dokumen, klien, baris item (jumlah × harga), dan perkiraan total. Simpan hanya setelah pengguna setuju.
5. Panggil `create_document_draft`, atau `update_document_draft` untuk draf yang sudah ada. Untuk penawaran yang disetujui, pakai `convert_quote_to_invoice`.
6. Bagikan `links.edit` dari hasil tool supaya pengguna bisa mengecek draf di Kedeka.

Batasan:

- Dokumen selalu berupa draf: belum terbit, belum bernomor final, dan tidak dikirim ke klien.
- Menerbitkan dokumen (`publish_document`) hanya bila pengguna memintanya secara eksplisit dan kemampuan itu sudah diaktifkan owner. Bila muncul `CAPABILITY_DISABLED`, sampaikan ke pengguna dan jangan mencoba cara lain.
- Data pengirim, rekening, nomor, dan jatuh tempo mengikuti pengaturan workspace; jangan mengarangnya.
