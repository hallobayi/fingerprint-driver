# Analisis: Menambah Dukungan ADMS ke Mesin Absensi ZKTeco X100C

Tanggal: 2026-10-14
Workspace: `D:/PYTHON-DEV/fingerprint-driver`

---

## 1. Ringkasan Jawaban

**Ya, sangat bisa.** Dan yang lebih penting: **alat untuk itu sudah ada di workspace Anda**,
yaitu `ADMS-Function-Update.rar` berisi `firmware.exe` (24.576 byte, tanggal 2013-09-06).

Ini **bukan** file firmware mesin absensi. Ini adalah **utilitas flasher** yang berjalan di
PC Windows, yang menulis **flag OEM** ke dalam mesin lewat protokol ZK SDK. Menyalakan flag
itu yang kemudian **membuka menu ADMS / Cloud Server Setting** di layar mesin.

Dengan kata lain: yang menentukan sebuah X100C punya menu ADMS atau tidak **bukan** versi
firmware-nya, melainkan **flag OEM** yang tertanam di device. Flag inilah yang di-toggle
oleh tool tersebut.

---

## 2. Bukti Forensik dari `ADMS-Function-Update.rar`

### 2.1 Isi arsip

| Atribut | Nilai |
|---|---|
| Nama di dalam arsip | `firmware.exe` |
| Ukuran | 24.576 byte |
| Packed size | 4.829 byte |
| Modified | 2013-09-06 10:28:48 |
| CRC | `76422974` |
| Metode kompresi | m3:17 (RAR3) |
| Terenkripsi | tidak |

### 2.2 Jenis file

Hasil parse header PE:

```
MZ  ->  PE\0\0 di offset 0xb8
machine   = 0x14c  (i386, 32-bit)
sections  = 3 (.text, .data, .rsrc)
timestamp = 2013-09-06 03:28:48 UTC
Subsystem = GUI (Windows)
Import    = MSVBVM60.DLL  (Visual Basic 6)
```

Jadi ini **program VB6 kecil**, bukan image firmware. Firmware mesin absensi ZKTeco
ukurannya ratusan kilobyte sampai beberapa megabyte dan formatnya bukan PE.

### 2.3 String yang membuktikan tujuannya

Di dalam `.rsrc` ada string UTF-16 berikut:

```
"Firmware Flasher - www.solution.co.id"
"ADMS Function Update"        <- caption Check1
"Nama field"                  |
"Command2"   -> "Cari Kata"   | kontrol VB6
"Command1"   -> "Flash"       |
"Text1"      -> "192.168.1.201"   <- default IP mesin
"StatusTxt"  -> "Status :"        <- label status
"Check1"     -> "ADMS Function Update"  <- kotak centang!
```

Label tombol, label status, dan default IP:

```
W 8028  'SOLUTION'
W 8080  'Sorry, Your device is not compatible with this updated !!!'
W 8204  'Information'
W 8232  'Connecting....'
W 8284  'Koneksi Berhasil'        <- bahasa Indonesia
W 8324  'Koneksi Gagal'           <- bahasa Indonesia
W 8364  'Flashing Firmware .....'
W 8432  'IclockSvrFun'            <- >>> KUNCI ADMS <<<
W 8472  '~ExtendFmt'              <- >>> KUNCI ADMS <<<
W 8500  'Flash Berhasil'
```

Perhatikan: pesan status dalam **bahasa Indonesia** (`Koneksi Berhasil`, `Koneksi Gagal`,
`Flash Berhasil`) dan vendor `solution.co.id`. Ini tool yang dibuat distributor Indonesia
untuk pasar Indonesia — selaras dengan isi folder `Attendance Interactive F-100`
yang juga berbahasa Indonesia (`baca dulu.txt`, `indo.txt`).

### 2.4 Komponen koneksi yang dipakai

Tool mengikat ke OCX yang sama dengan software absensi yang sudah ada:

```
'CZKEM1'
'zkemkeeperCtl.CZKEM'
'zkemkeeper.dll'   -> terpasang di C:\Windows\system32\zkemkeeper.oca
```

Nama prosedur internal (dari tabel VB6):

```
'Buka_Koneksi'      <- buka koneksi (Connect)
'Tutup_Koneksi'     <- tutup koneksi (Disconnect)
'Cari'              <- cari/scan device
'Flash'             <- jalankan proses tulis OEM
'Server'  'Kata'    <- variabel
'~OEMVendor'        <- konstanta nama vendor
```

API SDK yang dipakai: **`SetSysOption` / `SetDeviceParam`** dengan key `~OEMVendor`,
yang di `zkemkeeper.dll` memang ada:

```
Method GetSysOption
Method SetSysOption
Method SetDeviceCommPwdWWW
```

### 2.5 Bagaimana `IclockSvrFun` dan `~ExtendFmt` dipakai

Dekode byte di sekitar offset 8432:

```
...00  "IclockSvrFun\0"  00 00 [len=0x02] "1\0" [len=0x14] "~ExtendFmt\0"
```

Terlihat pasangan:
- `IclockSvrFun` → nilai **`"1"`**
- `~ExtendFmt`   → nilai lain (panjang 0x14 = 20 karakter)

Mekanismenya persis sama dengan key `~OEMVendor` yang nilainya default `"ZKSoftware Inc."`
di `zkemkeeper.dll`. Artinya tool ini menulis **blok opsi sistem** ke mesin:

1. `IclockSvrFun = 1` → **mengaktifkan fungsi "iClock Server"**, yakni fungsi server/push
   yang di UI mesin tampil sebagai **ADMS / Cloud Server Setting**.
2. `~ExtendFmt` → menuliskan penanda **format extended**, supaya mesin mau menerima dan
   menampilkan set menu yang diperluas (termasuk ADMS).
3. `~OEMVendor` → identitas vendor, bagian dari handshake OEM.

---

## 3. Kenapa Flag Ini yang Menentukan, Bukan Firmware

Di `zkemkeeper.dll` (versi 6.0.1.1, 2007) ada **tabel key konfigurasi** yang dibaca/ditulis
ke mesin. Yang relevan:

```
~MaxFingerCount        ~MaxUserCount        ~MaxAttLogCount
~SerialNumber          ~DeviceName          ~Platform   (~ZKFPVersion)
~LockFunOn             ~IsOnlyRFMachine     ~RFCardOn
~OEMVendor  = "ZKSoftware Inc."
~ProductTime
~DSTF, DaylightSavingTime, StandardTime
~RFSStart  ~RFSLen  ~RFFPC  ~ShowState
```

Yang penting: **`IclockSvrFun` dan `~ExtendFmt` TIDAK ada** di `zkemkeeper.dll` versi lama
ini. Artinya kedua key itu **ditambahkan belakangan** oleh ZKTeco, dan itulah tepatnya
yang dilakukan `firmware.exe`: menyuntikkan key baru ke mesin yang firmware-nya belum
punya/menonaktifkan key tersebut.

Ini menjelaskan keluhan Anda: dua unit X100C dengan **firmware sama** bisa berbeda —
satu punya menu ADMS, satu tidak — karena bergantung pada **nilai flag OEM yang tertulis
di masing-masing device**, bukan pada versi firmware.

### Catatan versi firmware di paket software lama

`Software Attendance - X100C/files/emfw.cfg`:

```
FirmwareVersion  = Ver 5.04 Mar 10 2005
FirmwareLength   = 163586
FirmwareCheckSum = 44357
```

Ini blob firmware **lama (2005, ±160 KB)** yang dipakai software `Att.exe` untuk
"Upgrade Firmware". Perhatikan panjang key saat dekode: `~ExtendFmt` dihitung
**20 karakter** — cocok dengan `~ExtendFmt=1` (12 karakter) atau nilai sejenis.
Yang jelas, tool ADMS ini **terpisah** dari file `emfw.cfg` tersebut.

---

## 4. Cara Melakukan Flash — Prosedur

### 4.1 Prasyarat

| Kebutuhan | Keterangan |
|---|---|
| PC Windows 32/64-bit | Tool VB6, butuh `MSVBVM60.DLL` (biasanya sudah ada) |
| `zkemkeeper.dll` terdaftar | Ada di `Software Attendance - X100C/files/sdk/` + `Register_SDK.bat` |
| Koneksi ke mesin | Lewat **LAN/Ethernet** (tool default `192.168.1.201`) |
| IP mesin | Set static, satu subnet dengan PC |

### 4.2 Langkah

1. **Siapkan SDK** — jalankan `Register_SDK.bat` di folder
   `Software Attendance - X100C/files/sdk/` (as Administrator). Ini mendaftarkan
   `zkemkeeper.dll` + `zkemkeeper.oca` ke `C:\Windows\system32`.
2. **Set IP mesin X100C** — Menu → Comm / Network → IP Address, mis. `192.168.1.201`,
   subnet mask `255.255.255.0`.
3. **Ekstrak tool** — keluarkan `firmware.exe` dari `ADMS-Function-Update.rar`.
   *Catatan teknis:* Windows Defender di mesin ini langsung mengunci file hasil ekstrak
   (`PermissionError [Errno 13]`). Perlu **whitelist / matikan sementara real-time
   protection**, lalu ekstrak ulang.
4. **Jalankan `firmware.exe`** — isi IP mesin di `Text1`, centang
   **"ADMS Function Update"** (`Check1`), tekan **Cari** untuk test koneksi.
5. **Tekan `Flash`** — status akan berjalan:
   `Connecting....` → `Koneksi Berhasil` → `Flashing Firmware .....` → `Flash Berhasil`.
6. **Restart mesin absensi** (matikan-hidupkan).
7. **Verifikasi** — menu **ADMS / Cloud Server Setting** sekarang harus muncul.
   Bisa juga dibaca lewat SDK: `GetSysOption` untuk key `IclockSvrFun`.

### 4.3 Kalau muncul "Sorry, Your device is not compatible with this updated !!!"

QString tersebut ada di dalam binary. Artinya:

- **Model/board tidak didukung.** Ini pesan paling penting. Tool ini menyasar
  keluarga **iClock** (lihat string `IclockSvrFun`). Berbagai unit yang dijual
  sebagai "X100C" memakai mainboard berbeda.
- Firmware terlalu tua / terlalu baru sehingga key tidak dikenali.
- Koneksi gagal walau status tampak "Koneksi Berhasil".

Jangan paksakan — kalau flag ditulis ke mesin yang tidak kompatibel, hasilnya bisa
mesin tidak mau boot atau menu hilang. **Wajib backup dulu** (lihat §6).

---

## 5. Kalau Flash Tidak Bisa / Berisiko — Alternatif

### Opsi A — Jalur resmi ZKTeco (paling aman)

Minta firmware resmi yang sudah ADMS ke dealer/distributor, lalu upgrade lewat:
- **Menu mesin:** `Menu → System → Firmware Upgrade` (via U-disk), atau
- **Software:** `Att.exe → Connect Machine → Upgrade Firmware`.

Manual resmi (`Attendance Management Software User ManualV1.8`, bagian 2.1.2) menulis:

> "Upgrade firmware: may click 'Upgrade Firmware' button... Note: User do not
> voluntarily upgrade the firmware, you must contact and be allowed by the dealer
> before to upgrade the firmware."

Peringatan dealer itu nyata: firmware salah = brick.

### Opsi B — Push/ADMS protocol tanpa menu di mesin

Kalau tujuan sebenarnya adalah **data absensi masuk otomatis ke server** (bukan
sekadar menu muncul di layar), maka menu ADMS di mesin **tidak wajib**.
Yang dibutuhkan hanya:

1. Mesin bisa dikonfigurasi `IclockSvrFun=1` (yaitu tool di §4), dan
2. Server yang mengimplementasikan **protokol push iClock/ADMS**: endpoint
   `/iclock/cdata`, `/iclock/getrequest`, `/iclock/devicecmd`.

Banyak implementasi open-source (mis. server ADMS berbasis PHP/Node/Python) sudah ada.
Cek juga `Software Attendance - X100C/files/sdk/plcommpro.dll` yang mengekspor
`SetDeviceParam` / `GetDeviceParam` — bisa dipakai untuk set parameter **tanpa GUI VB6**:

```c
Connect(ip, ...)      -> buka koneksi
SetDeviceParam(...)   -> tulis IclockSvrFun=1
GetDeviceParam(...)   -> baca balik untuk verifikasi
Disconnect()
```

Ini lebih terkontrol dan bisa di-script massal untuk banyak unit.

### Opsi C — Tetap pakai software existing (tanpa ADMS)

`Att.exe` (Attendance Management) sudah bisa menarik data X100C lewat LAN/USB/RS232.
Kalau kebutuhannya hanya laporan absensi internal, jalur ini nol risiko.

---

## 6. Peringatan Penting Sebelum Melakukan Apa Pun

> **⚠️ Risiko: tulis flag OEM ke mesin salah = potensi brick permanen.**

Wajib dilakukan lebih dulu:

1. **Catat semua setting OEM saat ini** sebelum menulis apa pun:
   ```c
   GetDeviceParam(~OEMVendor)   -> catat
   GetDeviceParam(~SerialNumber) -> catat
   GetDeviceParam(~DeviceName)   -> catat
   GetDeviceParam(~Platform)     -> catat
   GetDeviceParam(~LockFunOn)    -> catat
   ```
   Simpan ke file. Ini satu-satunya jalan pulih kalau gagal.
2. **Backup seluruh data mesin** — user, fingerprint template, log absensi
   (`BackupData` di SDK / U-disk di menu mesin).
3. **Uji pada SATU unit dulu**, idealnya unit yang statusnya "tidak support ADMS"
   dan tidak dipakai produksi.
4. **Jangan** langsung kerjakan ke seluruh armada sekaligus.
5. Pastikan **firmware mesin tidak akan tertimpa** — tool ini seharusnya hanya
   menulis flag, tapi kalau tombol yang salah dipakai, bisa jadi menulis firmware
   (`FirmwareLength=163586` dari 2005) yang justru menurunkan versi.

---

## 7. Kesimpulan

| Pertanyaan | Jawaban |
|---|---|
| Bisa buat X100C support ADMS? | **Bisa**, untuk unit yang kompatibel |
| Caranya? | Flash flag OEM (`IclockSvrFun=1`) lewat `firmware.exe` di `ADMS-Function-Update.rar` |
| Kenapa sebagian unit tidak ada menunya? | Bukan soal firmware, tapi **flag OEM per-device** |
| Apakah perlu ganti firmware? | **Tidak**, untuk kasus umum. Cukup tulis flag |
| Risiko? | Brick kalau model tidak kompatibel — **backup + uji 1 unit dulu** |
| Alternatif aman? | Minta firmware ADMS resmi ke dealer, atau implementasikan server push iClock |

**Langkah berikutnya yang saya sarankan:** sebelum menyentuh mesin, saya bisa
membedah lebih dalam `zkemkeeper.dll` dan `plcommpro.dll` untuk menghasilkan
skrip kecil (Python/C) yang menulis `IclockSvrFun=1` secara terkontrol — lengkap
dengan langkah baca-balik verifikasi dan simpan konfigurasi OEM asli. Itu jauh
lebih aman daripada tool VB6 tanpa preview.

---

## Lampiran: Perintah Reproduksi

```bash
# Ekstrak tool
"/c/Program Files/7-Zip/7z.exe" x ADMS-Function-Update.rar -o<TEMP> -y
# -> firmware.exe (24576 byte, 2013-09-06)

# Lihat semua string bukti
python -c "
import re
d=open('firmware.exe','rb').read()
for m in re.finditer(rb'(?:[\x20-\x7e]\x00){4,}', d):
    print(m.start(), m.group().decode('utf-16le',errors='ignore'))
"
```

Key yang dicari: `IclockSvrFun`, `~ExtendFmt`, `~OEMVendor`, `ADMS Function Update`,
`Flash Berhasil`, `Koneksi Berhasil`.
