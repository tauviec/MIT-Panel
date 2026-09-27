# Panduan Replikasi Master–Slave (MySQL / MariaDB)

Replikasi membuat server **slave** menyalin setiap perubahan database dari server **master**
secara **terus-menerus** (biasanya dalam hitungan detik). Slave menjadi cadangan database
yang selalu terbaru dan bisa diambil alih bila master rusak.

| | Clone Server | Master–Slave |
| --- | --- | --- |
| Kapan menyalin | sekali | terus-menerus |
| Yang disalin | seluruh server | **database saja** (bukan file situs) |

Replikasi **bukan pengganti backup**: data yang terhapus atau rusak di master ikut terhapus
atau rusak di slave. Tetap jalankan backup harian (menu Cron / Google Drive).

---

## Syarat

- Dua server dengan MIT Panel, **engine dan versi database yang sama**
  (misalnya MySQL 8.0 ↔ MySQL 8.0, atau MariaDB 10.11 ↔ MariaDB 10.11).
  Cara termudah menyiapkan slave: [Clone Server](clone-server.md) dari master.
- Slave bisa menjangkau **port 3306** master. Di master, buka port 3306 **hanya untuk IP slave**
  (menu **Keamanan / Firewall** panel dan firewall penyedia VPS).
- Untuk mode sinkronisasi **SSH**: slave bisa login SSH ke master.
- Jam kedua server sama (NTP aktif).

> **Perhatian:** menambahkan database ke replikasi di master (tombol **Join**) mengubah
> `my.cnf` dan **me-restart MySQL/MariaDB master** — aplikasi terputus beberapa detik.
> Lakukan di luar jam layanan.

Nama tombol di bawah sesuai tampilan panel (sebagian berbahasa Inggris).

---

## Bagian A — Di server MASTER

1. **App Store → MySQL** (atau MariaDB) → **Atur** → menu **Master-Slave Config**
   (di MariaDB namanya **Master - Slave**).
2. **Master-slave mode**: pilih **GTID** (disarankan untuk MySQL 5.7+ dan MariaDB 10.x) atau
   **Classic**. Mode harus **sama** di master dan slave.
3. **Master Config**: klik tombol **No Started** sampai berubah menjadi **Started**
   (mengaktifkan binary log; MySQL di-restart).
4. Di tabel database, klik **Join** pada setiap database yang ingin direplikasi
   (misalnya database aplikasi). Setiap klik me-restart MySQL master.
5. Klik **Sync account list** → **Add sync account**:
   - **Username** dan **Password**: akun khusus replikasi (bukan root)
   - **IP**: IP server slave (beberapa IP dipisah koma)
6. Pada akun itu, buka **Sync command** dan salin perintahnya — dipakai di slave pada mode
   *Sync account*.

## Bagian B — Di server SLAVE

1. **App Store → MySQL** (atau MariaDB) → **Atur** → **Master-Slave Config** / **Master - Slave**.
2. **Master-slave mode**: pilih mode yang **sama** dengan master.
3. **Slave Config**: klik **Not started** sampai menjadi **Started**.
4. Klik **Sync configuration** dan pilih cara slave mengambil data dari master:
   - **Sync account** (disarankan): isi IP master, port 3306, **Sync account**,
     **Sync password**, dan tempel **CMD** (Sync command dari langkah A6).
   - **SSH**: isi IP dan port SSH master; slave login ke master untuk mengambil perintah
     sinkronisasi secara otomatis. Setelah mengatur login tanpa password, jalankan
     **Manual command** sekali.
5. Klik **Initialization** untuk mendaftarkan master di slave.
6. Klik **Full sync** (semua database) atau **Synchronize** pada satu database. Slave
   mengekspor data dari master, mengimpornya, lalu menjalankan replikasi. Tunggu progres 100%.
7. Periksa tabel status: kolom **IO** dan **SQL** harus **Yes** / tanpa **Error IO**,
   **Error SQL**. Di sana juga ada tombol **Delete** untuk menghentikan replikasi.

## Uji replikasi

Di master (phpMyAdmin atau `mysql`):

```sql
CREATE TABLE uji_replikasi (id INT PRIMARY KEY, isi VARCHAR(20));
INSERT INTO uji_replikasi VALUES (1, 'halo');
```

Beberapa detik kemudian tabel dan barisnya harus muncul di slave. Hapus lagi tabelnya di master:
`DROP TABLE uji_replikasi;`

## Disarankan: kunci slave agar tidak bisa ditulis aplikasi

Aplikasi yang menulis langsung ke slave merusak replikasi. Di slave: **MySQL → Config** (MariaDB: **Configuration file**),
tambahkan di bagian `[mysqld]`, lalu restart:

```ini
read_only = 1
# MySQL 5.7+/8.x juga:
super_read_only = 1
```

Replikasi tetap berjalan; hanya penulisan dari aplikasi/user yang ditolak.
Saat slave diambil alih menjadi master, hapus kedua baris ini.

---

## Memantau

- **Master-Slave Config** di slave: status IO/SQL dan pesan error.
- Perintah di slave:
  ```bash
  mysql -uroot -p -e "SHOW REPLICA STATUS\G"    # MySQL 8.0.22+ / 8.4 / 9.x
  mysql -uroot -p -e "SHOW SLAVE STATUS\G"      # MySQL 5.7 / MariaDB
  ```
  Perhatikan `Seconds_Behind_Source` / `Seconds_Behind_Master` (ketertinggalan, detik).
- Watchdog MIT Panel menyalakan ulang MySQL/MariaDB yang crash dan mengirim peringatan.

## Masalah umum

| Gejala | Penyebab / solusi |
| --- | --- |
| IO: `Connecting` / error 2003 | Port 3306 master tertutup untuk IP slave, atau IP master salah |
| IO: error 1045 | Username/password akun sinkronisasi salah, atau IP slave tidak diizinkan |
| SQL: `Duplicate entry` / `1062` | Ada data yang ditulis langsung ke slave. Aktifkan `read_only`, lalu ulangi **Full sync** |
| Replikasi tertinggal jauh | Slave kekurangan RAM/disk; jalankan tuning otomatis di slave |
| Mode tidak cocok | Master GTID, slave Classic (atau sebaliknya) — samakan, lalu Full sync |

MySQL 8.4 dan 9.x tidak lagi mengenal perintah `SLAVE`/`MASTER`; MIT Panel menerjemahkannya
otomatis ke `REPLICA`/`SOURCE`.
