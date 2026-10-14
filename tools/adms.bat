@echo off
REM ===================================================================
REM  adms.bat - peluncur ADMS tool
REM
REM  Kenapa file ini ada:
REM    DLL SDK ZKTeco 32-bit, jadi tool HARUS jalan di Python 32-bit.
REM    Peluncur ini memilih interpreter 32-bit yang benar secara otomatis,
REM    sehingga pengguna tidak perlu mengingat path panjang.
REM ===================================================================

setlocal
set "HERE=%~dp0"
set "PY32=C:\Users\asus\.workbuddy-ai\binaries\python\x86-embed\python.exe"

if not exist "%PY32%" (
    echo.
    echo   [ERROR] Python 32-bit tidak ditemukan di:
    echo     %PY32%
    echo.
    echo   DLL SDK ZKTeco 32-bit, sehingga Python 64-bit tidak bisa dipakai.
    echo   Unduh "Windows embeddable package (32-bit)" dari python.org
    echo   lalu ekstrak ke folder di atas.
    echo.
    exit /b 3
)

"%PY32%" "%HERE%adms_tool.py" %*
exit /b %ERRORLEVEL%
