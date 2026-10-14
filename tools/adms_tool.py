"""
adms_tool.py — Kelola flag ADMS pada mesin absensi ZKTeco.

Latar belakang (hasil analisis ADMS-Function-Update.rar):
    Punya/tidaknya menu ADMS pada X100C ditentukan oleh FLAG OEM yang tertulis
    di device, BUKAN oleh versi firmware. Tool VB6 `firmware.exe` dari distributor
    (solution.co.id) menulis flag itu lewat SetSysOption/SetDeviceParam.

    Key kunci: IclockSvrFun = 1  (fungsi "iClock Server" -> tampil sebagai ADMS)
               ~ExtendFmt      (penanda format extended)
               ~OEMVendor      (identitas vendor, bagian handshake OEM)

Kenapa tool ini ada:
    `firmware.exe` menulis flag secara buta: tidak ada preview, tidak ada backup,
    tidak ada verifikasi. Tool ini melakukan hal yang sama tetapi dengan:
      1. backup konfigurasi OEM asli SEBELUM menulis apa pun
      2. mode dry-run sebagai DEFAULT (tanpa --apply tidak ada yang berubah)
      3. baca-balik sesudah menulis untuk membuktikan flag benar-benar masuk

Pemakaian:
    python adms_tool.py status   --ip 192.168.1.201
    python adms_tool.py backup   --ip 192.168.1.201
    python adms_tool.py enable   --ip 192.168.1.201            # dry-run
    python adms_tool.py enable   --ip 192.168.1.201 --apply    # sungguhan
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys

# Pastikan modul tetangga bisa di-import walau dijalankan dari folder lain.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from zk_sdk import DEFAULT_SDK_DIR, SdkError, ZkSdk  # noqa: E402

# ---------------------------------------------------------------------------
# Key OEM yang dibaca/ditulis
# ---------------------------------------------------------------------------

# Urutan pentin: identitas dulu (untuk backup), baru flag fungsional.
IDENTITY_KEYS = [
    "~OEMVendor",
    "~SerialNumber",
    "~DeviceName",
    "~Platform",
    "~ProductTime",
]

FUNCTION_KEYS = [
    "~LockFunOn",
    "~IsOnlyRFMachine",
    "~RFCardOn",
]

# Flag yang menjadi inti ADMS.
ADMS_KEYS = [
    "IclockSvrFun",
    "~ExtendFmt",
]

ALL_KEYS = IDENTITY_KEYS + FUNCTION_KEYS + ADMS_KEYS

DEFAULT_IP = "192.168.1.201"
DEFAULT_PORT = 4370

BACKUP_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "backups",
)


# ---------------------------------------------------------------------------
# Tampilan
# ---------------------------------------------------------------------------


def hr(char: str = "-", width: int = 66) -> str:
    return char * width


def banner() -> None:
    print(hr("="))
    print("  ADMS TOOL - ZKTeco fingerprint terminal")
    print("  Menulis flag OEM secara terkontrol (backup + verifikasi)")
    print(hr("="))


def mask(value: str | None) -> str:
    if value is None:
        return "<tidak terbaca>"
    return value if value else "<kosong>"


# ---------------------------------------------------------------------------
# Operasi
# ---------------------------------------------------------------------------


def read_all(sdk: ZkSdk) -> dict[str, str | None]:
    """Baca semua key. Mengembalikan dict key -> nilai (None bila gagal)."""
    out: dict[str, str | None] = {}
    for key in ALL_KEYS:
        out[key] = sdk.get_param_value(key)
    return out


def cmd_status(args: argparse.Namespace) -> int:
    """Baca dan tampilkan konfigurasi OEM saat ini. Tidak mengubah apa pun."""
    banner()
    print(f"  Mode    : BACA SAJA (tidak mengubah apa pun)")
    print(f"  Target  : {args.ip}:{args.port}")
    print(hr())

    with ZkSdk(args.sdk_dir) as sdk:
        if not sdk.connect(args.ip, args.port):
            print(f"\n  [GAGAL] {sdk.last_error}")
            return 2
        print("  Koneksi : berhasil\n")

        print("  -- Identitas device " + hr("-", 44))
        for key in IDENTITY_KEYS:
            print(f"    {key:<18} : {mask(sdk.get_param_value(key))}")

        print("\n  -- Fungsi dasar " + hr("-", 47))
        for key in FUNCTION_KEYS:
            print(f"    {key:<18} : {mask(sdk.get_param_value(key))}")

        print("\n  -- Flag ADMS (penentu menu ADMS) " + hr("-", 30))
        adms_on = False
        for key in ADMS_KEYS:
            value = sdk.get_param_value(key)
            print(f"    {key:<18} : {mask(value)}")
            if key == "IclockSvrFun" and (value or "").strip() in ("1", "true", "True"):
                adms_on = True

        print()
        print(hr())
        if adms_on:
            print("  KESIMPULAN: IclockSvrFun=1 -> ADMS kemungkinan SUDAH aktif.")
            print("              Kalau menu tetap tidak muncul, cek versi firmware.")
        else:
            print("  KESIMPULAN: IclockSvrFun tidak aktif -> menu ADMS kemungkinan")
            print("              BELUM muncul. Jalankan: enable")
        print(hr())
    return 0


def cmd_backup(args: argparse.Namespace) -> int:
    """Simpan konfigurasi OEM asli ke berkas JSON. Wajib sebelum menulis."""
    banner()
    print("  Mode   : BACKUP (baca saja)")
    print(f"  Target : {args.ip}:{args.port}")
    print(hr())

    with ZkSdk(args.sdk_dir) as sdk:
        if not sdk.connect(args.ip, args.port):
            print(f"\n  [GAGAL] {sdk.last_error}")
            return 2

        data = read_all(sdk)
        device = (data.get("~SerialNumber") or "unknown").strip() or "unknown"
        device_safe = "".join(c for c in device if c.isalnum() or c in "-_") or "unknown"

    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(BACKUP_DIR, f"oem-backup_{device_safe}_{stamp}.json")

    payload = {
        "created": _dt.datetime.now().isoformat(timespec="seconds"),
        "ip": args.ip,
        "port": args.port,
        "sdk_dir": os.path.abspath(args.sdk_dir or DEFAULT_SDK_DIR),
        "keys": data,
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)

    print("\n  -- Nilai yang tersimpan " + hr("-", 42))
    for key, value in data.items():
        print(f"    {key:<18} : {mask(value)}")

    print()
    print(hr("="))
    print(f"  Backup tersimpan di:\n    {path}")
    print(hr("="))
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    """Tulis balik konfigurasi dari berkas backup. Untuk pemulihan."""
    banner()
    print(f"  Berkas backup : {args.file}")
    print(f"  Target        : {args.ip}:{args.port}")
    print(hr())

    if not os.path.isfile(args.file):
        print(f"\n  [GAGAL] Berkas tidak ditemukan: {args.file}")
        return 2

    with open(args.file, encoding="utf-8") as fh:
        payload = json.load(fh)
    keys = payload.get("keys", {})

    print("\n  -- Rencana tulis balik " + hr("-", 42))
    plan = [(k, v) for k, v in keys.items() if v is not None and str(v).strip()]
    for key, value in plan:
        print(f"    {key:<18} = {value}")
    if not plan:
        print("    (tidak ada nilai yang bisa ditulis)")
        return 1

    if not args.apply:
        print()
        print(hr())
        print("  DRY-RUN: tidak ada yang diubah.")
        print("  Tambahkan --apply untuk benar-benar menulis.")
        print(hr())
        return 0

    with ZkSdk(args.sdk_dir) as sdk:
        if not sdk.connect(args.ip, args.port):
            print(f"\n  [GAGAL] {sdk.last_error}")
            return 2

        ok_count = 0
        for key, value in plan:
            if sdk.set_param(key, str(value)):
                print(f"    [ok]   {key} = {value}")
                ok_count += 1
            else:
                print(f"    [GAGAL] {key}: {sdk.last_error}")

        # Verifikasi
        print("\n  -- Verifikasi baca-balik " + hr("-", 38))
        mismatch = 0
        for key, value in plan:
            back = sdk.get_param_value(key)
            good = (back or "").strip() == str(value).strip()
            print(f"    {'[cocok]' if good else '[beda ]'} {key:<18} : {mask(back)}")
            if not good:
                mismatch += 1

    print()
    print(hr("="))
    print(f"  Tulis {ok_count}/{len(plan)} berhasil, {mismatch} tidak cocok saat verifikasi.")
    print("  Restart mesin absensi agar perubahan terbaca.")
    print(hr("="))
    return 0 if mismatch == 0 else 1


def cmd_enable(args: argparse.Namespace) -> int:
    """Tulis flag ADMS. DEFAULT dry-run; butuh --apply untuk menulis."""
    banner()
    print(f"  Target : {args.ip}:{args.port}")
    print(hr())

    plan = {
        "IclockSvrFun": "1",
        "~ExtendFmt": args.extend_fmt,
    }
    if args.oem_vendor:
        plan["~OEMVendor"] = args.oem_vendor

    print("\n  -- Rencana penulisan flag ADMS " + hr("-", 33))
    for key, value in plan.items():
        print(f"    {key:<18} = {value}")

    # --- Ambil snapshot dulu, apa pun mode-nya, supaya user punya cadangan. ---
    print("\n  -- Snapshot konfigurasi sebelum perubahan " + hr("-", 24))
    with ZkSdk(args.sdk_dir) as sdk:
        if not sdk.connect(args.ip, args.port):
            print(f"\n  [GAGAL] {sdk.last_error}")
            return 2
        before = read_all(sdk)

        for key in ("~SerialNumber", "~OEMVendor", "IclockSvrFun", "~ExtendFmt"):
            print(f"    {key:<18} : {mask(before.get(key))}")

        if not args.apply:
            print()
            print(hr())
            print("  DRY-RUN: TIDAK ADA yang diubah pada mesin.")
            print("  Yang akan berubah setelah --apply:")
            for key, value in plan.items():
                cur = before.get(key)
                print(f"    {key:<18} : {mask(cur)}  ->  {value}")
            print()
            print("  Tambahkan --apply untuk benar-benar menulis.")
            print(hr())
            return 0

        # --- Simpan backup otomatis SEBELUM menulis. ---
        os.makedirs(BACKUP_DIR, exist_ok=True)
        device = (before.get("~SerialNumber") or "unknown").strip() or "unknown"
        device_safe = "".join(c for c in device if c.isalnum() or c in "-_") or "unknown"
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        path = os.path.join(BACKUP_DIR, f"oem-backup_{device_safe}_{stamp}.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "created": _dt.datetime.now().isoformat(timespec="seconds"),
                    "ip": args.ip,
                    "reason": "otomatis sebelum enable ADMS",
                    "keys": before,
                },
                fh,
                indent=2,
                ensure_ascii=False,
            )
        print(f"\n    Backup otomatis: {path}")

        # --- Tulis. ---
        print("\n  -- Menulis flag ADMS " + hr("-", 43))
        write_fail = 0
        for key, value in plan.items():
            if sdk.set_param(key, value):
                print(f"    [ok]    {key} = {value}")
            else:
                print(f"    [GAGAL] {key}: {sdk.last_error}")
                write_fail += 1

        # --- Verifikasi baca-balik. ---
        print("\n  -- Verifikasi baca-balik (bukti flag benar-benar masuk) " + hr("-", 10))
        mismatch = 0
        for key, value in plan.items():
            back = sdk.get_param_value(key)
            good = (back or "").strip() == str(value).strip()
            print(f"    {'[cocok]' if good else '[beda ]'} {key:<18} : {mask(back)}")
            if not good:
                mismatch += 1

    print()
    print(hr("="))
    if write_fail == 0 and mismatch == 0:
        print("  HASIL: SEMUA flag berhasil ditulis dan terverifikasi.")
        print("  LANGKAH BERIKUTNYA:")
        print("    1. Matikan lalu hidupkan mesin absensi (power cycle).")
        print("    2. Cek menu ADMS / Cloud Server Setting di layar mesin.")
        print("    3. Kalau menu belum muncul, jalankan: status")
        print(f"    4. Bila perlu kembalikan: restore --file \"{path}\" --apply")
    else:
        print(f"  HASIL: {write_fail} gagal tulis, {mismatch} tidak cocok.")
        print("  JANGAN ulangi berulang kali. Cek koneksi, lalu coba: status")
        print(f"  Pemulihan tersedia di: {path}")
    print(hr("="))
    return 0 if (write_fail == 0 and mismatch == 0) else 1


def cmd_info(args: argparse.Namespace) -> int:
    """Tampilkan status SDK tanpa menyentuh jaringan."""
    from zk_sdk import sdk_summary

    banner()
    print(sdk_summary(args.sdk_dir))
    print(hr())
    print("  Perintah yang tersedia:")
    print("    status   --ip <IP>                 baca konfigurasi OEM")
    print("    backup   --ip <IP>                 simpan konfigurasi ke JSON")
    print("    enable   --ip <IP> [--apply]       tulis flag ADMS (default dry-run)")
    print("    restore  --file <JSON> [--apply]   tulis balik dari backup")
    print(hr())
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="adms_tool.py",
        description="Kelola flag ADMS pada mesin absensi ZKTeco (backup + verifikasi).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Contoh:\n"
            "  python adms_tool.py info\n"
            "  python adms_tool.py status --ip 192.168.1.201\n"
            "  python adms_tool.py enable --ip 192.168.1.201\n"
            "  python adms_tool.py enable --ip 192.168.1.201 --apply\n"
        ),
    )
    parser.add_argument(
        "--sdk-dir", default=None,
        help=f"folder berisi plcommpro.dll (default: {DEFAULT_SDK_DIR})",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_info = sub.add_parser("info", help="status SDK, tanpa jaringan")
    p_info.set_defaults(func=cmd_info)

    for name, func, helptext in (
        ("status", cmd_status, "baca konfigurasi OEM saat ini"),
        ("backup", cmd_backup, "simpan konfigurasi OEM ke berkas JSON"),
    ):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("--ip", default=DEFAULT_IP)
        p.add_argument("--port", type=int, default=DEFAULT_PORT)
        p.set_defaults(func=func)

    p_en = sub.add_parser("enable", help="tulis flag ADMS (default dry-run)")
    p_en.add_argument("--ip", default=DEFAULT_IP)
    p_en.add_argument("--port", type=int, default=DEFAULT_PORT)
    p_en.add_argument(
        "--apply", action="store_true",
        help="benar-benar menulis ke mesin (tanpa ini = dry-run)",
    )
    p_en.add_argument(
        "--extend-fmt", default="1",
        help="nilai untuk ~ExtendFmt (default: 1)",
    )
    p_en.add_argument(
        "--oem-vendor", default=None,
        help="nilai ~OEMVendor; biarkan kosong agar tidak diubah",
    )
    p_en.set_defaults(func=cmd_enable)

    p_re = sub.add_parser("restore", help="tulis balik konfigurasi dari backup")
    p_re.add_argument("--file", required=True, help="berkas JSON hasil backup")
    p_re.add_argument("--ip", default=DEFAULT_IP)
    p_re.add_argument("--port", type=int, default=DEFAULT_PORT)
    p_re.add_argument(
        "--apply", action="store_true",
        help="benar-benar menulis ke mesin (tanpa ini = dry-run)",
    )
    p_re.set_defaults(func=cmd_restore)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except SdkError as exc:
        print(f"\n  [ERROR SDK] {exc}\n")
        return 3
    except KeyboardInterrupt:
        print("\n  Dibatalkan oleh pengguna.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
