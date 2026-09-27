# Panduan Clone Server

Clone Server menyalin **seluruh isi server ini** ke server lain lewat SSH, **sekali jalan**:
MIT Panel, software (web server, PHP, MySQL/MariaDB, phpMyAdmin) dengan versi yang sama,
file website, vhost, SSL, sertifikat Let's Encrypt/acme.sh, database beserta user dan hak
aksesnya, serta daftar situs dan database di panel.

Setelah clone selesai, kedua server berjalan sendiri-sendiri. Perubahan setelahnya **tidak**
ikut tersalin — untuk itu pakai [Master–Slave](master-slave.md) (database) dan Rsyncd (file).

---

## Kapan dipakai

- Pindah ke VPS/server baru
- Menyiapkan server cadangan yang identik
- Membuat salinan untuk uji coba (staging)

## Yang perlu disiapkan

| Server | Syarat |
| --- | --- |
| **Sumber** (server ini) | MIT Panel terpasang; plugin **Clone Server** dipasang dari App Store |
| **Tujuan** | Linux baru (Ubuntu/Debian/Mint/CentOS/…), login SSH sebagai `root` (password atau private key), disk kosong minimal sebesar pemakaian server sumber |

Server tujuan **sebaiknya kosong**. Situs dan database dengan nama sama di tujuan akan
ditimpa. Kalau tujuan sudah punya MIT Panel, login panel dan password root database di
tujuan **tidak** diubah.

Tujuan tidak boleh memakai web server yang berbeda (misalnya sumber Apache, tujuan Nginx) —
clone akan berhenti dengan pesan yang jelas.

---

## Langkah-langkah

1. **App Store → Clone Server → Pasang** (sekali saja).
2. Buka **Clone Server**, tab **Clone Server**, isi:
   - **IP / host tujuan**, **Port SSH** (biasanya 22), **User** `root`
   - **Password SSH** *atau* path **private key** (misalnya `/root/.ssh/id_rsa`)
3. Pilih yang ingin disalin (semua dicentang secara bawaan):
   - Salin / pasang MIT Panel di tujuan
   - Pasang software yang belum ada (versi sama)
   - Situs, vhost, SSL, rewrite, proxy
   - Database + user database
4. Klik **Tes Koneksi**. Panel menampilkan sistem tujuan, RAM/disk kosong, dan tabel software:
   *sudah ada* atau *akan dipasang*.
5. Klik **Mulai Clone**. Panel pindah ke tab **Progres & Log**.
   - Kalau software perlu dikompilasi di tujuan, prosesnya bisa **10–60 menit per software**.
   - Halaman boleh ditutup; proses tetap berjalan di server. Buka lagi tab Progres & Log untuk
     melihat kelanjutannya. Tombol **Batalkan** menghentikan proses.
6. Setelah status **Selesai**, bagian akhir log berisi alamat login panel tujuan.
7. Periksa di tab **Terminal SSH** (lihat di bawah): klik **Status layanan** dan **Info sistem**.
8. Uji situs di server tujuan dengan mengarahkan domain di file `hosts` komputer Anda ke IP
   tujuan, lalu buka situsnya di browser.
9. Kalau semuanya benar, ubah **DNS** domain ke IP server tujuan.

Password SSH hanya dipakai selama proses berjalan dan tidak disimpan ke disk.

---

## Tab Terminal SSH

Setelah data server tujuan diisi di tab Clone Server:

- **Buka Terminal Interaktif** — terminal penuh ke server tujuan (bisa `top`, `nano`, `mysql`).
  Bila memakai private key, key tidak dikirim ke browser; server tujuan didaftarkan di daftar
  host WebSSH.
- **Perintah cepat**: Info sistem, Status layanan, Login panel, Watchdog log, Error web server,
  Proses teratas — atau ketik perintah sendiri lalu **Jalankan** (batas waktu 2 menit; untuk
  proses panjang pakai terminal interaktif).

---

## Yang tidak ikut tersalin

- **Jadwal Cron** di menu Cron — buat ulang di server tujuan.
- **Konfigurasi firewall** panel dan port panel.
- File di luar folder situs (misalnya folder aplikasi di `/home/...`) — salin manual atau
  pakai Rsyncd.

## Mengatasi masalah

| Pesan | Penyebab / solusi |
| --- | --- |
| `SSH gagal` / `Permission denied` | Password/key salah, atau login root lewat SSH dimatikan di tujuan (`PermitRootLogin`) |
| `sshpass belum terpasang` | Pasang ulang plugin Clone Server, atau pakai private key |
| `Server tujuan memakai openresty/apache` | Hapus web server yang berbeda di tujuan dulu |
| `Instalasi … di tujuan gagal` | Lihat `/tmp/mit-clone-<nama>.log` di server tujuan (bisa lewat Terminal SSH) |
| `mysqldump … gagal` | Periksa database sumber berjalan normal; ruang disk tujuan cukup |
