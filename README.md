# Kedeka untuk aplikasi AI

Plugin resmi [Kedeka](https://kedeka.com) untuk Claude, ChatGPT/Codex, Gemini CLI, dan aplikasi AI lain yang mendukung MCP. Hubungkan aplikasi AI dengan workspace Kedeka untuk mengurus administrasi bisnis dari percakapan: cek invoice yang belum dibayar, lihat piutang dan laporan keuangan, cari klien dan proyek, lalu buat draf invoice atau penawaran, tugas, dan catatan waktu kerja.

Repo ini berisi plugin, bukan source code server. Server MCP Kedeka berjalan di `https://kedeka.com/mcp/kedeka`.

## Isi plugin

- **Connector Kedeka** di `https://kedeka.com/mcp/kedeka`, dengan 36 tool untuk membaca dan mengelola data workspace.
- **Skill** yang mengajari aplikasi AI alur kerja Kedeka:
  - `cek-piutang`: invoice belum lunas, umur piutang, dan detail dokumen.
  - `buat-draf-invoice`: draf invoice atau penawaran dari klien dan katalog.
  - `laporan-keuangan`: omzet, PPN, PPh, pengeluaran, dan laba per periode.
  - `catat-tugas-waktu`: tugas proyek dan catatan jam kerja.

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
3. Tanyakan sesuatu, misalnya "Invoice mana yang belum dibayar dan sudah lewat jatuh tempo?" atau "Buatkan draf invoice untuk PT Kopi Senja: desain logo 1 paket."

Owner atau admin workspace menentukan apa saja yang boleh dilakukan aplikasi AI di **Pengaturan → Integrasi AI**. Menerbitkan dokumen, mencatat pembayaran, membatalkan, dan menghapus data nonaktif secara default, dan aplikasi AI selalu meminta konfirmasi Anda sebelum mengubah data.

## Data

Plugin ini hanya berisi instruksi dan alamat connector; tidak ada kode yang berjalan di komputer Anda. Saat Anda bertanya, aplikasi AI memanggil server Kedeka di `kedeka.com` dengan izin yang Anda setujui. Data yang diminta, seperti dokumen, klien, proyek, dan laporan, dikirim dari Kedeka ke penyedia aplikasi AI tersebut untuk menjawab pertanyaan Anda. Kedeka tidak mengirim email ke klien atas permintaan aplikasi AI, kecuali email terima kasih otomatis saat pembayaran melunasi invoice bila diaktifkan di pengaturan Email.

Koneksi bisa diputus kapan saja dari **Pengaturan → Integrasi AI** di Kedeka. Kebijakan privasi: https://kedeka.com/privacy-policy. Bantuan: https://kedeka.com/support.

## Struktur

| File | Dipakai oleh |
|---|---|
| `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.mcp.json` | Claude (directory, Cowork, Claude Code) |
| `plugin.json`, `mcp.json` | Format [Agent Plugins](https://agent-plugins.org/) (ChatGPT/Codex dan aplikasi lain) |
| `gemini-extension.json` | Gemini CLI |
| `skills/` | Semua aplikasi di atas |
