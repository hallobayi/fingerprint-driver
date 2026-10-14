"""
zk_sdk.py — Binding ctypes ke SDK ZKTeco (32-bit).

Kenapa file ini ada:
    DLL SDK ZKTeco (plcommpro.dll, zkemkeeper.dll, dst) adalah **32-bit i386**,
    sedangkan Python utama di mesin ini 64-bit. 64-bit Python TIDAK BISA memuat
    DLL 32-bit (WinError 193), jadi kita WAJIB memakai Python 32-bit.

    Skrip ini sengaja memuat DLL lewat jalur absolut + SetDllDirectoryW supaya
    tidak bergantung pada hasil Register_SDK.bat (yang butuh Administrator).
    Jadi tool bisa jalan langsung dari folder SDK di workspace.

Fungsi yang dipakai (terverifikasi ada di export table plcommpro.dll):
    Connect, Disconnect, SetDeviceParam, GetDeviceParam, PullLastError

Catatan stdcall:
    Export di DLL ini memakai __stdcall. Untuk fungsi yang namanya TIDAK
    terdekorasi pada tabel export (mis. "Connect"), ctypes.WinDLL dipakai
    supaya konvensi pemanggilan benar.
"""

from __future__ import annotations

import ctypes
import os
import sys
from ctypes import c_char_p, c_int, c_void_p

# ---------------------------------------------------------------------------
# Lokasi SDK
# ---------------------------------------------------------------------------

# Folder SDK bawaan workspace ini.
DEFAULT_SDK_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "Software Attendance - X100C",
    "files",
    "sdk",
)


class SdkError(RuntimeError):
    """Kesalahan yang berasal dari lapisan SDK / DLL."""


def require_32bit() -> None:
    """Pastikan interpreter yang jalan 32-bit. Gagal cepat dengan pesan jelas."""
    if sys.maxsize > 2 ** 32:
        raise SdkError(
            "Python yang dipakai 64-bit, tetapi DLL SDK ZKTeco 32-bit.\n"
            "Jalankan tool ini dengan Python 32-bit:\n"
            r"  C:\Users\asus\.workbuddy-ai\binaries\python\x86-embed\python.exe"
        )


# ---------------------------------------------------------------------------
# Kelas pembungkus SDK
# ---------------------------------------------------------------------------


class ZkSdk:
    """Pembungkus tipis untuk plcommpro.dll.

    Semua method mengembalikan bool (True = sukses) dan menyimpan pesan error
    terakhir di `self.last_error` supaya bisa ditampilkan ke pengguna.
    """

    def __init__(self, sdk_dir: str | None = None) -> None:
        require_32bit()

        self.sdk_dir = os.path.abspath(sdk_dir or DEFAULT_SDK_DIR)
        dll_path = os.path.join(self.sdk_dir, "plcommpro.dll")

        if not os.path.isfile(dll_path):
            raise SdkError(f"plcommpro.dll tidak ditemukan di: {dll_path}")

        self.last_error: str = ""
        self._handle: c_void_p | None = None
        self._connected: bool = False

        # Beri tahu Windows di mana mencari DLL pendamping (plrscomm, plcomms, ...).
        # Tanpa ini, plcommpro.dll gagal resolve dependensinya.
        try:
            ctypes.windll.kernel32.SetDllDirectoryW(self.sdk_dir)
        except Exception:
            # Tidak fatal — cwd + PATH di bawah biasanya cukup.
            pass
        os.environ["PATH"] = self.sdk_dir + os.pathsep + os.environ.get("PATH", "")

        old_cwd = os.getcwd()
        try:
            os.chdir(self.sdk_dir)
            self._dll = ctypes.WinDLL(dll_path)
        except OSError as exc:
            raise SdkError(
                f"Gagal memuat plcommpro.dll\n  path : {dll_path}\n  error: {exc}"
            ) from exc
        finally:
            os.chdir(old_cwd)

        self._bind()

    # -- binding ------------------------------------------------------------

    def _bind(self) -> None:
        """Deklarasikan signature setiap fungsi SDK yang dipakai."""

        # int Connect(const char *ip, int port)
        self._Connect = self._dll.Connect
        self._Connect.argtypes = [c_char_p, c_int]
        self._Connect.restype = c_int

        # int Disconnect(void *handle)
        self._Disconnect = self._dll.Disconnect
        self._Disconnect.argtypes = [c_void_p]
        self._Disconnect.restype = c_int

        # int SetDeviceParam(void *handle, const char *item, const char *value)
        self._SetDeviceParam = self._dll.SetDeviceParam
        self._SetDeviceParam.argtypes = [c_void_p, c_char_p, c_char_p]
        self._SetDeviceParam.restype = c_int

        # int GetDeviceParam(void *handle, char *buffer, int bufsize, const char *item)
        self._GetDeviceParam = self._dll.GetDeviceParam
        self._GetDeviceParam.argtypes = [c_void_p, c_char_p, c_int, c_char_p]
        self._GetDeviceParam.restype = c_int

        # const char *PullLastError(void)   -- nama bervariasi antar versi SDK
        try:
            self._PullLastError = self._dll.PullLastError
            self._PullLastError.argtypes = []
            self._PullLastError.restype = c_char_p
        except AttributeError:
            self._PullLastError = None

    # -- helper -------------------------------------------------------------

    def _err(self, context: str) -> str:
        """Ambil pesan error terakhir dari SDK, gabungkan dengan konteks."""
        detail = ""
        if self._PullLastError is not None:
            try:
                raw = self._PullLastError()
                if raw:
                    detail = raw.decode("utf-8", "replace").strip()
            except Exception:
                pass
        return f"{context}{(' -> ' + detail) if detail else ''}"

    @property
    def connected(self) -> bool:
        return self._connected

    # -- API publik ---------------------------------------------------------

    def connect(self, ip: str, port: int = 4370, timeout_ms: int = 5000) -> bool:
        """Buka koneksi ke mesin absensi lewat TCP/IP.

        Port standar ZKTeco = 4370.
        """
        if self._connected:
            self.disconnect()

        # Connect() mengembalikan HANDLE (bukan status).
        handle = self._Connect(ip.encode("utf-8"), c_int(port))
        if not handle:
            self.last_error = self._err(f"Connect({ip}:{port}) gagal")
            return False

        self._handle = c_void_p(handle)
        self._connected = True
        self.last_error = ""
        return True

    def disconnect(self) -> None:
        if self._handle:
            try:
                self._Disconnect(self._handle)
            except Exception:
                pass
        self._handle = None
        self._connected = False

    def set_param(self, item: str, value: str) -> bool:
        """Tulis satu parameter device. Contoh: ('IclockSvrFun', '1')."""
        if not self._connected:
            self.last_error = "Belum terkoneksi ke mesin."
            return False

        rc = self._SetDeviceParam(
            self._handle, item.encode("utf-8"), value.encode("utf-8")
        )
        if rc != 0:
            self.last_error = self._err(f"SetDeviceParam('{item}'='{value}') gagal (rc={rc})")
            return False

        self.last_error = ""
        return True

    def get_param(self, item: str, bufsize: int = 4096) -> str | None:
        """Baca satu parameter device. Mengembalikan None kalau gagal.

        GetDeviceParam menulis hasilnya sebagai teks ke buffer yang kita
        sediakan, dengan bentuk "key=value".
        """
        if not self._connected:
            self.last_error = "Belum terkoneksi ke mesin."
            return None

        buf = ctypes.create_string_buffer(bufsize)
        rc = self._GetDeviceParam(self._handle, buf, bufsize, item.encode("utf-8"))
        if rc != 0:
            self.last_error = self._err(f"GetDeviceParam('{item}') gagal (rc={rc})")
            return None

        self.last_error = ""
        return buf.value.decode("utf-8", "replace").strip()

    def get_param_value(self, item: str) -> str | None:
        """Seperti get_param, tetapi mengembalikan HANYA nilai (setelah '=')."""
        raw = self.get_param(item)
        if raw is None:
            return None
        # SDK mengembalikan "~OEMVendor=ZKSoftware Inc." (tanpa atau dengan '~').
        if "=" in raw:
            return raw.split("=", 1)[1].strip()
        return raw.strip()

    def __enter__(self) -> "ZkSdk":
        return self

    def __exit__(self, *exc: object) -> None:
        self.disconnect()


# ---------------------------------------------------------------------------
# Utilitas mandiri (tidak butuh koneksi)
# ---------------------------------------------------------------------------


def sdk_summary(sdk_dir: str | None = None) -> str:
    """Ringkas status SDK: folder, arsitektur DLL, dan interpreter."""
    d = os.path.abspath(sdk_dir or DEFAULT_SDK_DIR)
    lines = [f"Folder SDK : {d}", f"Interpreter: {sys.version.split()[0]} "
             f"({'32-bit' if sys.maxsize <= 2 ** 32 else '64-bit'})"]

    if not os.path.isdir(d):
        lines.append("Status     : FOLDER TIDAK ADA")
        return "\n".join(lines)

    for name in ("plcommpro.dll", "zkemkeeper.dll", "plrscomm.dll", "plcomms.dll"):
        p = os.path.join(d, name)
        if os.path.isfile(p):
            size = os.path.getsize(p)
            lines.append(f"  [ok]   {name:<20} {size:>9,} byte")
        else:
            lines.append(f"  [--]   {name:<20} tidak ada")
    return "\n".join(lines)
