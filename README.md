# MIT Panel

Panel kontrol hosting berbasis web untuk server Linux dan desktop Linux, bergaya aaPanel.
Kelola website, database, PHP, SSL, file, cron, backup, dan firewall langsung dari browser.

- **Web server** (pilih salah satu): Nginx (OpenResty) atau Apache 2.4
- **PHP**: 5.6, 7.0 – 7.4, 8.0 – 8.5 (beberapa versi sekaligus, pilih per situs)
- **Database**: MySQL 5.7, 8.0, 8.2, 8.3, 8.4, 9.0 – 9.4 / MariaDB 10.6 – 12.1
- **Cache**: Redis 7.2, 7.4, 8.0, 8.2, 8.4 (patch terbaru diambil otomatis)
- **Sistem**: Ubuntu, Debian, **Linux Mint**, Pop!_OS, Zorin, elementary, CentOS, AlmaLinux,
  Rocky, Fedora, openSUSE, Arch — server maupun desktop (GUI) — dan **Windows 10/11 lewat WSL2**

---

## Daftar isi
1. [Kebutuhan](#kebutuhan)
2. [Instalasi di Linux](#instalasi-di-linux)
3. [Instalasi di Windows](#instalasi-di-windows)
4. [Setelah instalasi](#setelah-instalasi)
5. [Fitur](#fitur)
6. [Panduan](#panduan)
7. [Perintah](#perintah)
8. [Update dan uninstall](#update-dan-uninstall)

---

## Kebutuhan

| | Minimal | Disarankan |
| --- | --- | --- |
| RAM | 1 GB | 2 GB atau lebih |
| Disk kosong | 10 GB | 20 GB atau lebih (kompilasi Apache/PHP/MySQL butuh ruang) |
| Akses | user `root` atau `sudo` | |
| Internet | untuk mengunduh paket dan source software | |

Pasang di **server/VM yang bersih**. Jangan pasang di server yang sudah memakai aaPanel,
cPanel, atau Apache/Nginx/MySQL bawaan distro pada port 80/443/3306.

---

## Instalasi di Linux

Semua cara di bawah memasang panel ke `/opt/mit/server/panel`.

### Cara 1 — Satu perintah, langsung dari GitHub (paling mudah)

```bash
curl -fsSL https://raw.githubusercontent.com/tauviec/MIT-Panel/main/install.sh | sudo bash
```

Kalau `curl` belum ada (misalnya Debian minimal):

```bash
sudo apt-get update && sudo apt-get install -y curl
curl -fsSL https://raw.githubusercontent.com/tauviec/MIT-Panel/main/install.sh | sudo bash
```

Installer akan:
1. mendeteksi distro (termasuk Linux Mint dan turunan Ubuntu/Debian lain),
2. memasang paket dasar (Python, wget, curl, zip, cron, ...),
3. mengunduh kode dari repo `tauviec/MIT-Panel` branch `main`,
4. memasang dan menyalakan panel, lalu menampilkan alamat login, username, dan password.

### Cara 2 — Dengan `git clone`

```bash
sudo apt-get install -y git          # Fedora/CentOS: sudo dnf install -y git
git clone https://github.com/tauviec/MIT-Panel.git
cd MIT-Panel
sudo bash install.sh
```

Installer memakai folder hasil clone itu sebagai sumber (tidak mengunduh ulang).

### Cara 3 — Dari folder salinan (tanpa internet ke GitHub)

Salin folder proyek ke server (USB, `scp`, dsb.), lalu:

```bash
cd MIT-Panel
sudo bash install.sh
```

### Linux Mint / Linux desktop (GUI)

Pakai salah satu cara di atas dari **Terminal**. Setelah selesai, buka alamat
`MIT-Panel-Url-Localhost` (contoh `http://localhost:12345/xxxxxx`) di Firefox/Chrome
pada komputer yang sama.

### Memakai repo atau branch lain

```bash
curl -fsSL https://raw.githubusercontent.com/tauviec/MIT-Panel/main/install.sh \
  | sudo MIT_REPO=https://github.com/tauviec/MIT-Panel MIT_BRANCH=main bash
```

---

## Instalasi di Windows

MIT Panel adalah panel Linux, jadi di Windows ia berjalan di dalam **WSL2 + Ubuntu**.
Panel dibuka dari browser Windows lewat `http://localhost:...`.

Syarat: Windows 10 versi 2004 (build 19041) atau lebih baru / Windows 11, virtualisasi
aktif di BIOS (biasanya sudah aktif).

### Cara 1 — Satu perintah dari GitHub

1. Klik kanan **Start** → **Terminal (Admin)** atau **Windows PowerShell (Admin)**.
2. Jalankan:

   ```powershell
   irm https://raw.githubusercontent.com/tauviec/MIT-Panel/main/install-windows.ps1 | iex
   ```

### Cara 2 — Unduh ZIP

1. Buka https://github.com/tauviec/MIT-Panel → **Code** → **Download ZIP**, lalu ekstrak.
2. Klik dua kali **`install-windows.bat`** dan setujui permintaan Administrator.

### Yang dilakukan installer Windows

1. Memasang WSL2 dan Ubuntu. **Pertama kali, Windows minta restart** — setelah restart,
   jalankan perintah/`install-windows.bat` **sekali lagi**.
2. Menyalakan systemd di dalam WSL.
3. Memasang MIT Panel di Ubuntu (WSL) — 10–30 menit.
4. Membuat tugas **autostart saat login** (Task Scheduler: *MIT Panel (WSL)*).
5. Membuat shortcut **MIT Panel** di desktop dan membuka panel di browser.

Perintah panel dari Windows:

```powershell
wsl -d Ubuntu -u root -- mit default     # alamat, username, password
wsl -d Ubuntu -u root -- mit restart
```

---

## Setelah instalasi

1. Lihat alamat login kapan saja: `sudo mit default`

   ```text
   MIT-Panel default info!
   MIT-Panel-Url-Ipv4: http://203.0.113.10:12345/abcdefgh
   MIT-Panel-Url-Local: http://192.168.1.10:12345/abcdefgh
   MIT-Panel-Url-Localhost: http://localhost:12345/abcdefgh
   username: xxxxxxxx
   password: xxxxxxxx
   ```

2. Buka port panel di firewall/security group penyedia VPS (port ditampilkan di alamat).
3. Login, lalu di **App Store** pasang:
   - web server: **Nginx (OpenResty)** *atau* **Apache**,
   - **PHP** (versi yang dibutuhkan),
   - **MySQL** atau **MariaDB**,
   - opsional: Redis, phpMyAdmin, Google Drive, Clone Server, dll.
4. Ganti username dan password panel di menu **Pengaturan**.

---

## Fitur

### Website
Domain dan port, binding subdirektori, SSL (Let's Encrypt / ACME / sertifikat sendiri),
paksa HTTPS, redirect, reverse proxy, proteksi password, anti-leech, batas trafik,
rewrite (aturan Nginx / `.htaccess` Apache), situs default. Semua fitur ini berjalan di Nginx
maupun Apache. Pindah dari Nginx ke Apache: hapus Nginx, pasang Apache — vhost Apache untuk
situs lama dibuat otomatis (menu **Rebuild Vhost** di plugin Apache).

### Database
Kelola database dan user, phpMyAdmin, dan **replikasi Master–Slave** (MySQL dan MariaDB):
user replikasi, sinkronisasi lewat SSH atau user, sinkronisasi penuh, status slave.
Pada MySQL 8.4 / 9.x perintah lama `SLAVE`/`MASTER` otomatis diterjemahkan ke sintaks
`REPLICA`/`SOURCE`.

### Tuning performa (RAM 1 GB – 128 GB+)
- MySQL/MariaDB: preset 1–2 GB sampai 128 GB+ dan mode **Otomatis** sesuai RAM server;
  perkiraan pemakaian memori maksimum dijaga di bawah 85% RAM.
- Apache dan Nginx: tombol **Tuning Otomatis (RAM)**.
- Setiap tuning membuat backup konfigurasi dan mengembalikannya otomatis bila layanan gagal start.

### Backup
- Menu **Cron**: backup terjadwal situs, database, folder, dan log — ke disk lokal atau Google Drive.
- Plugin **Google Drive** (gratis, 15 GB akun Google): **Backup Otomatis** harian semua situs
  dan semua database, menyimpan N backup terbaru di Drive.
  Siapkan sekali: tombol **Kredensial** (panduan membuat OAuth client gratis di Google Cloud),
  lalu **Otorisasi**. Aplikasi Google harus di-*Publish* (In production) agar izin tidak
  kedaluwarsa tiap 7 hari.

### Clone Server
Salin server ini ke server baru lewat SSH: MIT Panel, software dengan versi yang sama,
situs, vhost/SSL, sertifikat, database beserta user-nya. Login panel dan password root
database di tujuan tidak ditimpa. Tab **Terminal SSH** membuka terminal interaktif ke server
tujuan dan menyediakan perintah cepat (status layanan, disk, log).

### Watchdog
Tiap menit memeriksa web server, MySQL/MariaDB, dan PHP-FPM. Layanan yang crash
(misalnya dimatikan kernel karena RAM habis) dinyalakan ulang, maksimal 3 kali per jam.
Peringatan disk > 90% dan RAM > 95%. Semua kejadian masuk `logs/watchdog.log`, log panel,
dan notifikasi Telegram (bila diatur). Layanan yang sengaja dihentikan tidak disentuh.

---

## Panduan

| Panduan | Isi |
| --- | --- |
| [Clone Server](docs/clone-server.md) | Menyalin seluruh server ke server baru lewat SSH, sekali jalan |
| [Master–Slave](docs/master-slave.md) | Replikasi database MySQL/MariaDB terus-menerus ke server cadangan |
| [Server utama + cadangan](docs/server-cadangan.md) | Menggabungkan Clone Server, Master–Slave, Rsyncd, dan backup Google Drive, termasuk langkah pindah ke server cadangan bila server utama rusak |

**Clone atau Master–Slave?** Clone = salinan seluruh server **sekali** (pindah server,
menyiapkan server cadangan). Master–Slave = **database** tersalin **terus-menerus**.
Untuk server cadangan: clone sekali, lalu aktifkan Master–Slave (database) dan Rsyncd (file).

Ringkasan panduan juga ada di dalam panel: plugin **Clone Server → Panduan** dan
**MySQL / MariaDB → Panduan Master-Slave**.

---

## Perintah

| Perintah | Keterangan |
| --- | --- |
| `mit start` | Menyalakan panel dan tugas latar belakang |
| `mit stop` | Mematikan panel |
| `mit restart` | Restart panel |
| `mit status` | Status panel |
| `mit default` | Alamat login, username, password |

Layanan:

```bash
systemctl [start|stop|restart|status] openresty     # Nginx
systemctl [start|stop|restart|status] apache
systemctl [start|stop|restart|status] mysql         # atau mariadb
systemctl [start|stop|restart|status] redis
systemctl [start|stop|restart|status] php74         # php56 ... php85
tail -f /opt/mit/server/panel/logs/watchdog.log
```

---

## Update dan uninstall

Update kode panel ke versi terbaru di GitHub:

```bash
curl -fsSL https://raw.githubusercontent.com/tauviec/MIT-Panel/main/scripts/update.sh | sudo bash
```

Uninstall (bisa membackup situs dan database dulu):

```bash
sudo bash /opt/mit/server/panel/scripts/uninstall.sh
```

Di Windows, panel ikut terhapus bila distro WSL dihapus: `wsl --unregister Ubuntu`
(**menghapus semua data di Ubuntu WSL**), lalu hapus tugas *MIT Panel (WSL)* di Task Scheduler.
