# Kedeka untuk aplikasi AI

Plugin resmi [Kedeka](https://kedeka.com) untuk Claude, ChatGPT/Codex, Gemini CLI, dan aplikasi AI lain yang mendukung MCP. Hubungkan aplikasi AI dengan workspace Kedeka untuk mengurus administrasi bisnis dari percakapan: cek siapa yang belum membayar, minta insight kondisi keuangan, cari klien dan proyek, buat draf invoice atau penawaran, catat pembayaran, lalu kirim dokumen ke klien setelah Anda memeriksanya di Kedeka.

Repo ini berisi plugin, bukan source code server. Server MCP Kedeka berjalan di `https://kedeka.com/mcp/kedeka`.

## Isi plugin

- **Connector Kedeka** di `https://kedeka.com/mcp/kedeka`, dengan 13 tool berdasarkan jenis operasi untuk membaca dan mengelola data workspace.
- **Skill** yang mengajari aplikasi AI alur kerja Kedeka. Instruksinya berbahasa Inggris, dan aplikasi AI membalas dalam bahasa pengguna:
  - `get-started`: perkenalan setelah dipasang, workspace yang terhubung, dan izin yang aktif.
  - `financial-summary`: omzet, pengeluaran, laba, pajak, perbandingan periode, dan insight bisnis.
  - `collect-receivables`: invoice belum lunas, prioritas penagihan, dan draf pesan pengingat.
  - `draft-invoice`: draf invoice atau penawaran, termasuk dari penawaran yang disetujui.
  - `record-payment`: mencatat pembayaran yang sudah masuk, termasuk dari bukti transfer.
  - `project-briefs`: untuk coding agent, membaca brief proyek dari Kedeka berdasarkan git remote repo, lalu memperbarui status paket kerja. Repo tidak perlu menyimpan dokumen brief.
  - `write-brief`: menyimpan hasil diskusi, kebutuhan, dan keputusan menjadi brief proyek.
  - `track-work`: menyiapkan task dan brief untuk implementasi yang diminta, mencatat waktu serta hasil terverifikasi, terpisah dari waktu manual.
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

Owner atau admin workspace menentukan apa saja yang boleh dilakukan aplikasi AI di **Pengaturan → Integrasi AI**. Menerbitkan dokumen, mencatat pembayaran, membatalkan, dan menghapus data nonaktif secara default, dan perubahan data mengikuti instruksi serta persetujuan Anda. Permintaan coding mencakup pencarian/pembuatan task, tracking, dan pencatatan hasil terverifikasi pada brief terkait tanpa konfirmasi tambahan hanya untuk tracking.

Data sensitif seperti NPWP, NITKU, dan nomor rekening tidak diisi di chat. Aplikasi AI memberi link ke halaman aman Kedeka yang hanya bisa dibuka akun Anda, berlaku 30 menit, dan sekali pakai. Mengirim dokumen ke email klien juga lewat halaman itu: Anda memeriksa penerima dan isi email, lalu menekan Kirim sendiri.

## Data

Pemasangan plugin biasa memuat instruksi dan alamat connector. Adapter hook Python opsional di `.agents/hooks/` hanya berjalan setelah Anda memasangnya dan mempercayainya pada harness coding; pemasangan plugin tidak mengaktifkannya otomatis. Saat Anda bertanya, aplikasi AI memanggil server Kedeka di `kedeka.com` dengan izin yang Anda setujui. Data yang diminta, seperti dokumen, klien, proyek, dan laporan, dikirim dari Kedeka ke penyedia aplikasi AI tersebut untuk menjawab pertanyaan Anda. Nilai yang Anda isi di halaman aman Kedeka tidak dikirim ke aplikasi AI; aplikasi AI hanya diberi tahu bahwa aksinya sudah selesai. Kedeka hanya mengirim email ke klien setelah Anda menekan Kirim di halaman aman itu, atau email terima kasih otomatis saat pembayaran melunasi invoice bila diaktifkan di pengaturan Email.

Koneksi yang tidak dipakai selama 30 hari berakhir otomatis. Koneksi juga bisa diputus kapan saja dari **Pengaturan → Integrasi AI** di Kedeka. Kebijakan privasi: https://kedeka.com/privacy-policy. Bantuan: https://kedeka.com/support.

## Struktur

| File | Dipakai oleh |
|---|---|
| `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.mcp.json` | Claude (directory, Cowork, Claude Code) |
| `plugin.json`, `mcp.json` | Format [Agent Plugins](https://agent-plugins.org/) (ChatGPT/Codex dan aplikasi lain) |
| `gemini-extension.json` | Gemini CLI |
| `skills/` | Semua aplikasi di atas |

## Hook lifecycle untuk coding agent

Skill mengikuti protokol MCP yang sama pada semua host. Hook hanya membantu tracking: menyiapkan task/brief sebelum mutasi proyek, heartbeat, finish eksplisit, dan pause saat sesi berakhir. Hook tidak memilih workflow atau mengatur izin delegasi; tidak ada whitelist per skill. Investigasi baca saja dan diskusi tidak memerlukan prepared task. Klasifikasi perintah adalah bantuan tracking, bukan sandbox keamanan: perintah yang tidak dikenali mendapat pengingat tanpa penolakan.

Adapter opt-in untuk **macOS/Linux dengan Python 3** disinkronkan dari source Kedeka `ec10454573e7bed492387d6be64851eced9d694f`:

- `.agents/hooks/kedeka.py`: Codex, memakai klien OAuth native `codex app-server` tanpa membaca/menyalin token atau menjalankan model/worker AI.
- `.agents/hooks/kedeka_claude.py`: Claude Code, memakai receipt respons MCP native server `kedeka` dan callback penutupan bertanda tangan. Identitas serta kredensial Claude terpisah dari Codex.
- `integrations/codex/hooks.json` dan `integrations/claude/settings.json`: konfigurasi proyek, bukan hook plugin global yang otomatis aktif. Salin kedua script ke `.agents/hooks/` pada repo tujuan, lalu **gabungkan** konfigurasi harness ke `.codex/hooks.json` atau `.claude/settings.json` tanpa menimpa hook yang sudah ada. Command mengacu pada root repo tujuan, bukan direktori instalasi plugin.

Sebelum mengaktifkan, tautkan repo tujuan melalui **Brief → Hubungkan agent**, sambungkan server MCP bernama `kedeka` ke workspace yang benar lewat OAuth native harness, lalu tinjau/percayai hook melalui `/hooks`. Claude memerlukan dukungan `mcp_tool` hooks; lihat [referensi resmi](https://code.claude.com/docs/en/hooks). Codex memerlukan `codex` di PATH dan dukungan lifecycle hook. Perubahan script memerlukan peninjauan trust ulang; paket ini tidak mengubah trust atau konfigurasi global Anda.

Gunakan `session_key` persis dari konteks hook, exact `worktree`, serta `lifecycle_hooks: true` hanya saat hook aktif. Ikuti `get_help projects/tracking/prepare`; untuk Claude baca juga `projects/tracking/claude`. Guard Claude diperbarui melalui `get_report current_work` dan receipt berlaku 60 detik. Finish eksplisit menyimpan summary, verification, revision brief dan commit/PR: `done` setelah acceptance lulus, `review` bila masih menunggu pemeriksaan; pause untuk pekerjaan belum selesai.

State lokal privat berada di `~/.local/state/kedeka/hooks` atau `claude-hooks`: identitas, metadata run dan antrean callback; bukan isi prompt atau token OAuth. Claude menyimpan kapabilitas penutupan terbatas milik run, yang hanya dapat menghentikan timer. Callback offline dicoba ulang dengan waktu kejadian asli. Proses yang mati tanpa event tetap bergantung pada idle lease server; jangan menganggap Stop berarti selesai.

Gemini CLI dan host tanpa adapter memakai protokol MCP eksplisit serta idle lease; paket ini tidak mengklaim dukungan hook otomatis pada host tersebut. Jangan pasang kedua adapter untuk satu harness atau menggandakan hook proyek yang sudah aktif.

Uji tanpa OAuth, model, atau jaringan:

```sh
python3 -m unittest discover -s tests/Unit -p 'test_*.py'
```
