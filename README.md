# Kedeka untuk aplikasi AI

Plugin resmi [Kedeka](https://kedeka.com) untuk Claude, ChatGPT/Codex, Gemini CLI, dan aplikasi AI lain yang mendukung MCP. Hubungkan aplikasi AI dengan workspace Kedeka untuk mengurus administrasi bisnis dari percakapan: cek siapa yang belum membayar, minta insight kondisi keuangan, cari klien dan proyek, buat draf invoice atau penawaran, catat pembayaran, lalu kirim dokumen ke klien setelah Anda memeriksanya di Kedeka.

Repo ini berisi plugin, bukan source code server. Server MCP Kedeka berjalan di `https://kedeka.com/mcp/kedeka`.

## Isi plugin

- **Connector Kedeka** di `https://kedeka.com/mcp/kedeka`, dengan 12 tool berdasarkan jenis operasi untuk membaca dan mengelola data workspace.
- **Skill** yang mengajari aplikasi AI alur kerja Kedeka. Instruksinya berbahasa Inggris, dan aplikasi AI membalas dalam bahasa pengguna:
  - `get-started`: perkenalan setelah dipasang, workspace yang terhubung, dan izin yang aktif.
  - `financial-summary`: omzet, pengeluaran, laba, pajak, perbandingan periode, dan insight bisnis.
  - `collect-receivables`: invoice belum lunas, prioritas penagihan, dan draf pesan pengingat.
  - `draft-invoice`: draf invoice atau penawaran, termasuk dari penawaran yang disetujui.
  - `record-payment`: mencatat pembayaran yang sudah masuk, termasuk dari bukti transfer.
  - `project-briefs`: untuk coding agent, membaca brief proyek dari Kedeka berdasarkan git remote repo, lalu memperbarui status paket kerja. Repo tidak perlu menyimpan dokumen brief.
  - `write-brief`: menyimpan hasil diskusi, kebutuhan, dan keputusan menjadi brief proyek.
  - `track-work`: mencatat sesi pekerjaan agen pada tugas yang dipilih, terpisah dari waktu manual.
  - `manage-records`: mencari dan mengelola klien, proyek, tugas, waktu, dan data lainnya.

## Pemasangan

**Claude Code**

```
/plugin marketplace add kedeka/mcp
/plugin install kedeka@kedeka
```

**Codex**

```
codex plugin marketplace add kedeka/mcp
codex plugin add kedeka@kedeka
```

**Gemini CLI**

```
gemini extensions install https://github.com/kedeka/mcp
```

**Aplikasi lain**: tambahkan server MCP remote dengan URL `https://kedeka.com/mcp/kedeka`. Skill di folder `skills/` mengikuti format `SKILL.md` dan bisa disalin ke folder skill aplikasi Anda.

## Cara pakai

1. Setelah plugin terpasang, hubungkan connector **Kedeka**.
2. Masuk ke akun Kedeka, pilih satu workspace, dan setujui akses.
3. Tanyakan sesuatu, misalnya "Berikan insight bisnis saya: apa yang berjalan baik dan apa yang perlu saya perhatikan?" atau "Buatkan draf invoice untuk PT Kopi Senja: desain logo 1 paket."

Owner atau admin workspace menentukan apa saja yang boleh dilakukan aplikasi AI di **Pengaturan → Integrasi AI**. Menerbitkan dokumen, mencatat pembayaran, membatalkan, dan menghapus data nonaktif secara default, dan aplikasi AI selalu meminta konfirmasi Anda sebelum mengubah data.

Data sensitif seperti NPWP, NITKU, dan nomor rekening tidak diisi di chat. Aplikasi AI memberi link ke halaman aman Kedeka yang hanya bisa dibuka akun Anda, berlaku 30 menit, dan sekali pakai. Mengirim dokumen ke email klien juga lewat halaman itu: Anda memeriksa penerima dan isi email, lalu menekan Kirim sendiri.

## Data

Plugin ini hanya berisi instruksi dan alamat connector; tidak ada kode yang berjalan di komputer Anda. Saat Anda bertanya, aplikasi AI memanggil server Kedeka di `kedeka.com` dengan izin yang Anda setujui. Data yang diminta, seperti dokumen, klien, proyek, dan laporan, dikirim dari Kedeka ke penyedia aplikasi AI tersebut untuk menjawab pertanyaan Anda. Nilai yang Anda isi di halaman aman Kedeka tidak dikirim ke aplikasi AI; aplikasi AI hanya diberi tahu bahwa aksinya sudah selesai. Kedeka hanya mengirim email ke klien setelah Anda menekan Kirim di halaman aman itu, atau email terima kasih otomatis saat pembayaran melunasi invoice bila diaktifkan di pengaturan Email.

Koneksi yang tidak dipakai selama 30 hari berakhir otomatis. Koneksi juga bisa diputus kapan saja dari **Pengaturan → Integrasi AI** di Kedeka. Kebijakan privasi: https://kedeka.com/privacy-policy. Bantuan: https://kedeka.com/support.

## Struktur

| File | Dipakai oleh |
|---|---|
| `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.mcp.json` | Claude (directory, Cowork, Claude Code) |
| `plugin.json`, `mcp.json` | Format [Agent Plugins](https://agent-plugins.org/) (ChatGPT/Codex dan aplikasi lain) |
| `gemini-extension.json` | Gemini CLI |
| `skills/` | Semua aplikasi di atas |
