# Server Utama + Server Cadangan (Clone Server + Master–Slave)

Panduan ini menyiapkan **dua server** untuk aplikasi web yang memakai MySQL/MariaDB,
agar layanan bisa dipindah ke server cadangan bila server utama rusak.

```
                     pengguna / aplikasi klien
                                 │
                          domain aplikasi (DNS)
                                 │
   ┌─────────────────────────────▼───────────┐        ┌──────────────────────────────────┐
   │ SERVER A  (UTAMA)                        │        │ SERVER B  (CADANGAN)              │
   │  aplikasi web                            │ rsync  │  aplikasi web (salinan)           │
   │  file upload  ───────────────────────────┼───────►│  file upload                      │
   │  MySQL  MASTER ──────────────────────────┼───────►│  MySQL  SLAVE (read only)         │
   │  cron / scheduler AKTIF                  │ replik.│  cron / scheduler MATI            │
   │  backup harian → Google Drive            │        │  tidak menerima pengguna          │
   └──────────────────────────────────────────┘        └──────────────────────────────────┘
```

| Alat | Tugas |
| --- | --- |
| **Clone Server** | sekali di awal: membuat server B identik dengan A (software, situs, SSL, database) |
| **Master–Slave** | terus-menerus: setiap perubahan database di A tersalin ke B |
| **Rsyncd** | terus-menerus: file upload tersalin ke B |
| **Google Drive** | backup harian — pelindung dari data terhapus/rusak (replikasi ikut menyalin kesalahan) |

Rincian tiap alat: [Clone Server](clone-server.md) · [Master–Slave](master-slave.md).

> Uji seluruh langkah dengan **dua VM** dan data contoh sebelum dipakai untuk data penting.

---

## 0. Yang disiapkan

| | Server A (utama) | Server B (cadangan) |
| --- | --- | --- |
| Spesifikasi | sesuai beban aplikasi | **minimal sama dengan A** (bila A mati, B menanggung semua beban) |
| Sistem | Linux + MIT Panel | Linux baru (boleh kosong) |
| Jaringan | B bisa menjangkau A di port **3306** (MySQL) dan **873** (rsync); A bisa SSH ke B | |

Catat sebelum mulai:
- nama database aplikasi,
- folder aplikasi dan semua folder tempat file upload disimpan,
- tugas terjadwal (cron / scheduler) aplikasi, terutama yang **mengirim data ke layanan luar**,
- perangkat/aplikasi yang terhubung langsung ke **IP** server A (aplikasi desktop yang
  membuka database langsung, perangkat absensi, dsb.).

Turunkan **TTL DNS** domain aplikasi ke 300 detik (5 menit) di pengelola DNS, supaya
perpindahan ke server B cepat berlaku.

---

## 1. Server A: aplikasi di MIT Panel

Lewati bagian ini bila aplikasi sudah berjalan di MIT Panel.

1. Pasang MIT Panel ([README](../README.md#instalasi-di-linux)), lalu dari App Store pasang:
   **Nginx** *atau* **Apache**, **PHP** (versi yang dibutuhkan aplikasi),
   **MySQL** atau **MariaDB**, **phpMyAdmin**.
2. **Website → Tambah situs** dengan domain aplikasi, folder misalnya `/opt/mit/wwwroot/app`.
3. Unggah kode aplikasi, lalu atur situs:
   - **Direktori run**: `/public` untuk aplikasi Laravel
   - **Rewrite**: template yang sesuai (misalnya **laravel5**, **wordpress**)
   - **SSL** → Let's Encrypt, aktifkan **paksa HTTPS**
4. Impor database: **Database → Tambah**, lalu impor dump lewat phpMyAdmin atau
   `mysql -uroot -p nama_db < dump.sql`.
5. **Cron**: tambahkan tugas terjadwal aplikasi. Contoh Laravel, setiap menit:
   ```bash
   cd /opt/mit/wwwroot/app && php artisan schedule:run >> /dev/null 2>&1
   ```
6. **Tuning**: MySQL → **Optimization** → *Otomatis (sesuai RAM server)* →
   **Tuning Otomatis & Restart**; di Nginx/Apache: **Tuning** → **Tuning Otomatis (RAM)**.
7. Buka port 3306 di firewall **hanya** untuk IP yang memang perlu (dan nanti IP server B).

---

## 2. Membuat server B dengan Clone Server

Di **server A**:

1. App Store → **Clone Server** → Pasang → buka.
2. Isi IP server B, port SSH, user `root`, password/private key. Centang semua opsi.
3. **Tes Koneksi** → periksa daftar software → **Mulai Clone**.
4. Tunggu status **Selesai** di tab **Progres & Log** (bisa lebih dari 1 jam bila software
   dikompilasi di B).
5. Tab **Terminal SSH** → **Status layanan**: semua layanan di B harus `active`.

---

## 3. Server B: jadikan cadangan pasif

Login ke panel **server B** (alamatnya ada di akhir log clone).

1. **Matikan cron / scheduler aplikasi di B.** Menu **Cron**: buat tugas yang sama seperti di A,
   lalu **nonaktifkan**. Bila berjalan di A *dan* B, tugas yang mengirim data ke layanan luar
   (laporan, notifikasi, sinkronisasi) **terkirim dua kali**.
2. Jangan arahkan pengguna atau aplikasi klien ke B.
3. Jangan ubah data lewat aplikasi di B — semua perubahan datang dari replikasi.

---

## 4. Replikasi database (Master–Slave)

Ikuti [Master–Slave](master-slave.md) dengan **A = master**, **B = slave**:

1. **A**: Master-Slave Config → mode **GTID** → **Master Config: Started** → **Join**
   database aplikasi → **Add sync account** dengan IP server B.
   *Join me-restart MySQL A — lakukan di luar jam layanan.*
2. **B**: mode **GTID** → **Slave Config: Started** → **Sync configuration** (*Sync account*,
   isi IP A dan akun tadi) → **Initialization** → **Full sync**.
   Full sync **tetap wajib** walaupun data sudah ter-clone: langkah ini menyamakan posisi
   replikasi dengan master.
3. **B**: tambahkan `read_only = 1` dan `super_read_only = 1` di konfigurasi MySQL, lalu restart.
4. Uji: tambahkan data uji lewat aplikasi di A; dalam beberapa detik data itu terlihat di
   database B (phpMyAdmin B). Hapus data uji di A — penghapusan juga tersalin.

---

## 5. Sinkronisasi file upload (Rsyncd)

Master–Slave hanya menyalin database. Folder file upload (misalnya `storage/app`,
`public/uploads`, atau folder upload lain milik aplikasi) disalin dengan **Rsyncd**.
Pasang plugin **Rsyncd** di A dan B.

1. **B (penerima)**: Rsyncd → **Receive Config** → **Add** (*Create receive*) untuk folder
   aplikasi. Catat **nama** dan **kunci** (*Receive key*). Buka port **873** di B hanya untuk IP A.
2. **A (pengirim)**: Rsyncd → **Send config** → **Create send task**:
   - **Source directory**: folder aplikasi, misalnya `/opt/mit/wwwroot/app`
   - **Server IP**: IP B, **Receive key**: kunci dari B
   - **Sync cycle**: **Real time**
   - **Excluded files and directories**: `storage/logs`, `storage/framework`, `bootstrap/cache`, `.env`
3. Ulangi untuk setiap folder upload di luar folder aplikasi.
4. Uji: unggah file lewat aplikasi di A, cek file muncul di B.

`.env` dikecualikan agar perubahan konfigurasi di salah satu server tidak menimpa yang lain;
ubah `.env` di kedua server bila ada perubahan.

---

## 6. Backup harian

Di **server A**: plugin **Google Drive** → **Kredensial** → **Otorisasi** →
**Backup Otomatis** (misalnya jam 02:30, simpan 14). Replikasi ikut menyalin data yang
terhapus, jadi backup inilah yang menyelamatkan bila ada kesalahan input massal atau
serangan ransomware.

---

## 7. Pemeriksaan rutin

| Kapan | Periksa |
| --- | --- |
| Harian | B: Master-Slave → status IO/SQL tanpa error; ketertinggalan (detik) kecil |
| Harian | Log backup Google Drive (menu Cron) berhasil |
| Mingguan | File upload terbaru ada di B; `logs/watchdog.log` di A dan B |
| Bulanan | **Latihan pindah server** (langkah 8) di VM uji |
| Setiap update aplikasi | Terapkan update di A; file ikut via rsync, struktur database ikut via replikasi. Bersihkan cache aplikasi juga di B (Laravel: `php artisan config:clear`) |

---

## 8. Bila server A rusak: pindah ke server B

1. **Pastikan A benar-benar mati** atau diputus dari jaringan. Bila A masih menerima input
   sementara B diaktifkan, data terbelah dua dan sulit digabung.
2. **B → MySQL → Master-Slave** → tombol **Delete** pada replikasi (menghentikan slave).
3. **B → MySQL → Config**: hapus `read_only` dan `super_read_only`, restart MySQL.
4. **B → Cron**: aktifkan tugas terjadwal aplikasi.
5. Arahkan pengguna ke B:
   - DNS: ubah A record domain aplikasi ke IP B (berlaku ≤ 5 menit bila TTL sudah 300);
   - ubah alamat server di aplikasi/perangkat yang memakai IP server A.
6. Uji fungsi utama aplikasi: login, input data, integrasi ke layanan luar, cetak.
   Pengguna perlu login ulang bila sesi disimpan di server A.

## 9. Setelah server A diperbaiki

1. Jangan langsung menyalakan A di jaringan layanan.
2. Jadikan **A sebagai slave dari B** (langkah 4 dengan peran terbalik, termasuk **Full sync**),
   dan rsync dengan arah **B → A**.
3. Pada jam sepi, bila ingin kembali ke A: hentikan input di B, tunggu A tidak tertinggal,
   lalu ulangi langkah 8 dengan peran terbalik. Atau biarkan B tetap menjadi server utama.
