@echo off
REM Aktifkan environment stageofalor
call "C:\Users\stage\miniconda3\Scripts\activate.bat" stageofalor

REM Pindah ke folder script Python
cd /d "E:\Run_events"

REM Jalankan script
python process_events_v2.py

pause
