---
name: catat-tugas-waktu
description: Tambah atau ubah tugas proyek dan catat jam kerja di Kedeka. Gunakan saat pengguna ingin menambahkan to-do ke proyek, mengganti tenggat atau status tugas, melihat tugas yang belum selesai, atau mencatat berapa jam yang sudah dikerjakan.
---

# Tugas dan catatan waktu

1. Temukan proyek dengan `search_projects`. Bila hasil berisi `selection.required: true`, tanyakan ke pengguna proyek mana yang dimaksud.
2. Untuk melihat tugas, panggil `list_tasks`; untuk detail proyek, `get_project`.
3. Untuk tugas baru, konfirmasi judul, proyek, tenggat, dan penanggung jawab, lalu panggil `create_task`. Untuk perubahan, pakai `update_task`.
4. Untuk jam kerja, konfirmasi proyek, durasi, dan tanggal, lalu panggil `log_time`. Ubah tanggal relatif ("kemarin", "Jumat ini") menjadi tanggal persis dan sebutkan tanggal itu saat konfirmasi.

Batasan:

- `log_time` mencatat waktu untuk pengguna yang sedang terhubung, bukan untuk anggota lain.
- Tarif mengikuti pengaturan proyek atau workspace; jangan menghitung nilai rupiah sendiri.
- Penanggung jawab tugas mendapat notifikasi dari Kedeka, seperti saat tugas dibuat dari dashboard.
