@echo on
echo ================================
echo  Mulai eksekusi skrip
echo ================================

setlocal enabledelayedexpansion

REM === Ambil tanggal sekarang dengan wmic (format: YYYYMMDDhhmmss) ===
for /f "tokens=2 delims==." %%i in ('wmic os get LocalDateTime /value') do set LDT=%%i

set YEAR=!LDT:~0,4!
set MONTH=!LDT:~4,2!
set DAY=!LDT:~6,2!

echo [DEBUG] Tanggal sekarang = !YEAR!-!MONTH!-!DAY!

REM === Hitung bulan sebelumnya ===
set /a PREVMONTH=1%MONTH%-1-100
set PREVYEAR=!YEAR!

if !PREVMONTH! lss 1 (
    set /a PREVMONTH=12
    set /a PREVYEAR=!YEAR!-1
)

REM Pastikan format bulan 2 digit
set PREVMONTH=0!PREVMONTH!
set PREVMONTH=!PREVMONTH:~-2!

REM === Debug output ===
echo [DEBUG] Bulan sekarang   : !MONTH!
echo [DEBUG] Tahun sekarang   : !YEAR!
echo [DEBUG] Bulan sebelumnya : !PREVMONTH!
echo [DEBUG] Tahun sebelumnya : !PREVYEAR!
echo.

REM === Tentukan nama file output dan folder ===
set OUTDIR=E:\Run_events
set OUTFILENAME=list_event.txt
if not exist "!OUTDIR!" mkdir "!OUTDIR!"

REM === Jalankan perintah SSH di server (buat file /tmp/list_event.txt) ===
ssh -i "%USERPROFILE%\.ssh\id_rsa_alor" sysop@172.25.106.13 ^
  "SEISCOMP_ROOT=/home/sysop/seiscomp PATH=/home/sysop/seiscomp/bin:\$PATH /home/sysop/bin/list_event !PREVYEAR!/!PREVMONTH!/01 !YEAR!/!MONTH!/01"

REM === Ambil hasil file dari server ke Windows ===
scp -i "%USERPROFILE%\.ssh\id_rsa_alor" ^
  sysop@172.25.106.13:/tmp/list_events.txt "!OUTDIR!\!OUTFILENAME!"

REM === Cek errorlevel ===
if errorlevel 1 (
    echo [ERROR] Proses gagal dijalankan.
) else (
    echo [INFO] Hasil berhasil disimpan di: !OUTDIR!\!OUTFILENAME!
)

echo ================================
echo  Selesai
echo ================================
pause
