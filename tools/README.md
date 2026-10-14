# ADMS Tool — Mengaktifkan Menu ADMS pada Mesin Absensi ZKTeco

Alat untuk mengaktifkan menu **ADMS / Cloud Server Setting** pada mesin absensi
ZKTeco (mis. X100C), dengan pengamanan yang tidak dimiliki tool asli
`firmware.exe` dari distributor.

---

## 1. Ringkas: kenapa alat ini ada

Hasil analisis `ADMS-Function-Update.rar` menunjukkan:

> Punya/tidaknya menu ADMS pada mesin **bukan** ditentukan versi firmware,
> melainkan oleh **flag OEM** yang tertulis di device.

Tool `firmware.exe` bawaan RAR itu menulis flag tersebut, tapi:

| Masalah pada `firmware.exe` | Yang dilakukan alat ini |
|---|---|
| Tidak ada preview — langsung Flash | **Dry-run sebagai default**; harus tambah `--apply` |
| Tidak ada backup | **Backup otomatis** ke JSON sebelum menulis |
| Tidak ada verifikasi | **Baca-balik** setelah menulis untuk membuktikan |
| Tidak bisa script massal | Bisa di-loop untuk banyak unit |

Flag yang ditulis: **`IclockSvrFun=1`** (fungsi "iClock Server" → tampil sebagai
ADMS) dan **`~ExtendFmt`**.

---

## 2. Prasyarat

### 2.1 Python 32-bit (WAJIB)

DLL SDK ZKTeco (`plcommpro.dll`, dll) adalah **32-bit i386**. Python 64-bit
**tidak bisa** memuatnya (`WinError 193`). Ini sudah terpasang di mesin ini:

```
C:\Users\asus\.workbuddy-ai\binaries\python\x86-embed\python.exe
```

Peluncur `adms.bat` sudah menunjuk ke path itu otomatis.

> Kalau pindah mesin: unduh **"Windows embeddable package (32-bit)"** dari
> <https://www.python.org/downloads/windows/> dan ekstrak ke path di atas,
> atau ubah variabel `PY32` di dalam `adms.bat`.

### 2.2 Jaringan

- Mesin absensi dan PC harus **satu subnet**.
- Port standar ZKTeco: **4370**.
- Set IP statis di mesin: `Menu → Comm / Network → IP Address`
  (default tool: `192.168.1.201`).

### 2.3 SDK

Folder SDK bawaan workspace ini sudah dipakai otomatis:

```
Software Attendance - X100C\files\sdk\
```

Berisi `plcommpro.dll`, `plrscomm.dll`, `plcomms.dll` — semuanya dimuat lewat
path absolut, jadi **`Register_SDK.bat` tidak diperlukan** (tidak butuh
Administrator).

---

## 3. Cara Pakai

Semua perintah dijalankan dari folder `tools\`:

```bat
cd D:\PYTHON-DEV\fingerprint-driver\tools
```

### 3.1 Cek SDK (tanpa jaringan)

```bat
adms.bat info
```

### 3.2 Lihat konfigurasi mesin saat ini (baca saja)

```bat
adms.bat status --ip 192.168.1.201
```

Menampilkan identitas device (`~OEMVendor`, `~SerialNumber`, `~Platform`, …)
dan status flag ADMS, lalu memberi kesimpulan apakah ADMS sudah aktif.

### 3.3 Backup konfigurasi OEM asli

```bat
adms.bat backup --ip 192.168.1.201
```

Menghasilkan berkas di `backups\oem-backup_<serial>_<tanggal>.json`.
**Lakukan ini sebelum perubahan apa pun** — ini satu-satunya jalan pulih.

### 3.4 Aktifkan ADMS

**Langkah 1 — dry-run** (lihat apa yang akan berubah, tanpa menyentuh mesin):

```bat
adms.bat enable --ip 192.168.1.201
```

**Langkah 2 — tulis sungguhan:**

```bat
adms.bat enable --ip 192.168.1.201 --apply
```

Saat `--apply`, tool akan otomatis membuat backup dulu, menulis flag,
lalu memverifikasi dengan baca-balik.

**Langkah 3 — power cycle mesin absensi** (matikan lalu hidupkan).

**Langkah 4 — cek menu ADMS / Cloud Server Setting di layar mesin.**

### 3.5 Kalau perlu dikembalikan

```bat
adms.bat restore --file "backups\oem-backup_<serial>_<tanggal>.json" --apply
```

Tanpa `--apply` hanya menampilkan rencana.

---

## 4. Format keluaran backup

```json
{
  "created": "2026-10-14T12:30:00",
  "ip": "192.168.1.201",
  "port": 4370,
  "keys": {
    "~OEMVendor": "ZKSoftware Inc.",
    "~SerialNumber": "1234567890",
    "~DeviceName": "X100C",
    "~Platform": "ZEM500_TFT",
    "~ProductTime": "2019-01-01",
    "~LockFunOn": "1",
    "~IsOnlyRFMachine": "0",
    "~RFCardOn": "0",
    "IclockSvrFun": "0",
    "~ExtendFmt": null
  }
}
```

Nilai `null` berarti SDK gagal membacanya (key mungkin tidak ada di model itu) —
`restore` otomatis melewati nilai `null`.

---

## 5. Arti kode keluar

| Kode | Arti |
|---|---|
| `0` | Sukses |
| `1` | Tulis/verifikasi gagal sebagian |
| `2` | Tidak bisa konek, atau berkas tidak ditemukan |
| `3` | Masalah SDK (mis. salah versi Python) |
| `130` | Dibatalkan pengguna |

---

## 6. Format skrip massal (banyak unit)

Karena `--apply` sudah aman (backup otomatis + verifikasi), banyak unit bisa
diproses berurutan:

```bat
for %I in (192.168.1.201 192.168.1.202 192.168.1.203) do adms.bat enable --ip %I --apply
```

**Saran:** uji **satu unit** dulu sampai menu ADMS benar-benar muncul, baru
lanjut ke sisanya.

---

## 7. Peringatan

> **⚠️ Menulis flag ke model yang tidak kompatibel berpotensi membuat mesin brick.**

- Tool asli punya penjaga dengan pesan
  *"Sorry, Your device is not compatible with this updated !!!"*.
  Alat ini **belum** bisa mendeteksi kompatibilitas sebelum menulis, jadi
  kesalahan model baru ketahuan saat mesin di-restart.
- **Selalu** jalankan `backup` lebih dulu dan simpan berkasnya.
- **Selalu** uji satu unit sebelum menyentuh seluruh armada.
- Kalau tombol/flag salah dan mesin tidak mau boot, pemulihan **hanya** bisa
  lewat backup JSON atau service center — dan tidak selalu berhasil.

---

## 8. Kalau flag tidak bisa ditulis

Beberapa kemungkinan:

| Gejala | Kemungkinan penyebab |
|---|---|
| `Connect(...) gagal` | IP salah / beda subnet / port 4370 tertutup firewall |
| `SetDeviceParam ... gagal (rc=-...)` | Firmware terlalu tua, key tidak dikenali |
| Tulis sukses tapi menu tidak muncul | Model/board tidak mendukung ADMS |
| Verifikasi `[beda]` | Mesin menolak nilai, atau device reset sendiri |

**Alternatif kalau tetap gagal:**

1. **Minta firmware resmi ber-ADMS** ke dealer ZKTeco, upgrade lewat
   `Menu → System → Firmware Upgrade` (via U-disk).
2. **Push/ADMS tanpa menu di mesin** — kalau tujuan sebenarnya data absensi
   masuk otomatis ke server, yang dibutuhkan hanya `IclockSvrFun=1` di sisi
   device plus server yang mengimplementasikan endpoint `/iclock/cdata`,
   `/iclock/getrequest`, `/iclock/devicecmd`.

---

## 9. Berkas dalam folder ini

| Berkas | Fungsi |
|---|---|
| `adms.bat` | Peluncur — otomatis memilih Python 32-bit |
| `adms_tool.py` | Program utama (CLI) |
| `zk_sdk.py` | Binding ctypes ke `plcommpro.dll` |
| `README.md` | Dokumen ini |

Dokumentasi analisis latar belakang: `..\ADMS-X100C-Analisis.md`

Alur kerja teknis (binding SDK 32-bit) juga dicatat sebagai skill yang bisa
dipakai ulang: `~/.workbuddy-ai/skills/zkteco-sdk-32bit-binding/`
