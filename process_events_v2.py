# ============================================================
# created by: Dimas Didik
# Gabungan: Filter event + Proses waveform MSEED
# ============================================================

import pandas as pd
import re
import subprocess
import os
import shutil
from obspy import read, UTCDateTime, Stream
import glob

# ============================================================
# -------------------- BAGIAN 1 : FILTER ---------------------
# ============================================================

# -----------------------------
# Konfigurasi filter
# -----------------------------
lat_min, lat_max = -12.0, -7.0        # rentang lintang (decimal degrees)
lon_min, lon_max = 118.8, 125.5       # rentang bujur (decimal degrees)

mag_min, mag_max = 0.0, 9.0           # rentang magnitudo
depth_min, depth_max = 0, 1000        # rentang kedalaman (km)

# -----------------------------
# Baca data
# -----------------------------
filename = "list_event.txt"

with open(filename, "r", encoding="utf-8") as f:
    lines = f.readlines()

# cari baris yang ada timestamp
pattern = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")
data_lines = [line.strip("| \n") for line in lines if pattern.search(line)]
records = [re.split(r"\s*\|\s*", line.strip()) for line in data_lines]

# semua kolom
all_columns = [
    "Origin Time (GMT)",
    "Status",
    "cnt_origin",
    "Magnitude",
    "Magnitude Type",
    "cnt_mag",
    "Latitude",
    "Longitude",
    "Depth",
    "Remarks"
]

df = pd.DataFrame(records, columns=all_columns)

# Ambil kolom penting
df = df[["Origin Time (GMT)", "Magnitude", "Latitude", "Longitude", "Depth", "Remarks"]]

# Pisah Origin Time
df[["Date", "Time"]] = df["Origin Time (GMT)"].str.split(" ", expand=True)

# Ubah kolom Date jadi datetime
df["Date"] = pd.to_datetime(df["Date"], format="%Y-%m-%d")

# Tambah kolom DayOfYear (001–366)
df["DayOfYear"] = df["Date"].dt.strftime("%j")

# Tambah kolom YearDay (akumulasi sejak tanggal paling awal)
min_date = df["Date"].min()
df["YearDay"] = (df["Date"] - min_date).dt.days + 1

# Konversi Magnitude
df["Magnitude"] = pd.to_numeric(df["Magnitude"], errors="coerce")

# Bersihkan koordinat & depth
def parse_coord(val):
    num, hemi = val.split()
    num = float(num)
    if hemi.upper() in ["S", "W"]:
        num *= -1
    return num

df["Latitude"] = df["Latitude"].apply(parse_coord)
df["Longitude"] = df["Longitude"].apply(parse_coord)
df["Depth"] = df["Depth"].str.replace(" km", "").astype(float)

# -----------------------------
# Filter kombinasi
# -----------------------------
df_filtered = df[
    (df["Latitude"].between(lat_min, lat_max)) &
    (df["Longitude"].between(lon_min, lon_max)) &
    (df["Magnitude"].between(mag_min, mag_max)) &
    (df["Depth"].between(depth_min, depth_max))
]

df_filtered = df_filtered[[
    "Date", "Time", "Magnitude", "Latitude", "Longitude",
    "Depth", "DayOfYear", "YearDay", "Remarks"
]]

# -----------------------------
# Simpan ke CSV
# -----------------------------
csv_file = "gempa_filtered.csv"
df_filtered.to_csv(csv_file, index=False)

print(f"[INFO] Data tersaring: {len(df_filtered)} event → disimpan ke {csv_file}")

# ============================================================
# -------------------- BAGIAN 2 : PROSES ---------------------
# ============================================================

# ===========================
# BACA DATA GEMPA
# ===========================
df = pd.read_csv(csv_file)
df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

# ===========================
# PARAMETER TRIM
# ===========================
before_event = 60     # detik sebelum origin time
after_event  = 300    # detik sesudah origin time
folder_path  = "./mseed_download"       # hasil download_by_day.sh
output_dir   = r"E:\DATA ARRIVAL DAN WAVEFORM SEISCOMP ALOR\WAVEFORM"   # folder hasil trim
station_filter = []   # contoh: ["PAFM", "ABCD"], kosong [] = semua
failed_logfile = os.path.join(output_dir, "failed.log")

os.makedirs(output_dir, exist_ok=True)

# ===========================
# FUNGSI
# ===========================
def sanitize_filename(text):
    text = text.strip()
    text = text.replace(" ", "_")
    text = re.sub(r"[^A-Za-z0-9_\-]", "", text)
    return text

def log_message(msg, logfile=None):
    print(msg)
    if logfile:
        with open(logfile, "a", encoding="utf-8") as f:
            f.write(msg + "\n")

def write_failed(row, origin_time, day_str, year):
    failed_line = (
        f"{origin_time.strftime('%Y-%m-%d')},"
        f"{origin_time.strftime('%H:%M:%S')},"
        f"{row['Magnitude']},{row['Latitude']},{row['Longitude']},"
        f"{row['Depth']},{day_str},{year},\"{row['Remarks']}\""
    )
    with open(failed_logfile, "a", encoding="utf-8") as f:
        f.write(failed_line + "\n")

# ===========================
# COUNTERS
# ===========================
total_success = 0
total_failed = 0

with open(failed_logfile, "w", encoding="utf-8") as f:
    f.write("Date,Time,Magnitude,Latitude,Longitude,Depth,DayOfYear,Year,Remarks\n")

# ===========================
# PROSES SETIAP EVENT
# ===========================
for idx, row in df.iterrows():
    if pd.isna(row["DayOfYear"]) or pd.isna(row["Date"]):
        print(f"[SKIP] Data kosong pada baris {idx}")
        continue

    day_str = str(int(row["DayOfYear"])).zfill(3)
    year = pd.to_datetime(row["Date"]).year

    year_output_dir = os.path.join(output_dir, str(year))
    os.makedirs(year_output_dir, exist_ok=True)
    logfile = os.path.join(year_output_dir, f"{year}.log")

    event_time = pd.to_datetime(f"{row['Date'].date()} {str(row['Time']).split('.')[0]}")
    origin_time = UTCDateTime(event_time.to_pydatetime())

    start_time = origin_time - before_event
    end_time   = origin_time + after_event

    date_str = origin_time.strftime("%Y%m%d")
    time_str = origin_time.strftime("%H%M%S")
    mag_str  = f"Mag{row['Magnitude']:.1f}"
    depth_str = f"Depth{int(row['Depth'])}"
    remarks_str = sanitize_filename(str(row['Remarks']))
    file_name = f"{date_str}_{time_str}_{mag_str}_{depth_str}_{remarks_str}.mseed"
    output_file = os.path.join(year_output_dir, file_name)

    log_message(f"\n=== Event {origin_time} (Day {day_str}, Year {year}) ===", logfile)

    # 1. Download
    try:
        subprocess.run(
            ["wsl", "./download_by_day.sh", day_str, str(year)],
            check=True
        )
    except subprocess.CalledProcessError as e:
        log_message(f"[FAILED] Download gagal untuk Day {day_str} Year {year}: {e}", logfile)
        write_failed(row, origin_time, day_str, year)
        total_failed += 1
        continue

    # 2. Proses MSEED
    combined_stream = Stream()
    files = glob.glob(os.path.join(folder_path, "*"))

    for file_path in files:
        try:
            st = read(file_path)
        except Exception as e:
            log_message(f"[SKIP] {file_path}: {e}", logfile)
            continue

        for tr in st:
            if station_filter and tr.stats.station not in station_filter:
                continue

            if tr.stats.endtime >= start_time and tr.stats.starttime <= end_time:
                tr_trimmed = tr.copy().trim(
                    starttime=start_time,
                    endtime=end_time,
                    pad=True,
                    fill_value=0
                )
                combined_stream += tr_trimmed

    if len(combined_stream) > 0:
        combined_stream.write(output_file, format="MSEED")
        log_message(f"[SAVED] {output_file}", logfile)
        total_success += 1
    else:
        log_message(f"[FAILED] Tidak ada data untuk event {origin_time}", logfile)
        write_failed(row, origin_time, day_str, year)
        total_failed += 1

    # 4. Bersihkan folder download
    for f in os.listdir(folder_path):
        fpath = os.path.join(folder_path, f)
        try:
            if os.path.isfile(fpath) or os.path.islink(fpath):
                os.unlink(fpath)
            elif os.path.isdir(fpath):
                shutil.rmtree(fpath)
        except Exception as e:
            log_message(f"[ERROR] Gagal hapus {fpath}: {e}", logfile)

# ===========================
# REKAP
# ===========================
print("\n=== Semua event selesai diproses ===")
print(f"Total event input: {len(df)}")
print(f"Total berhasil   : {total_success}")
print(f"Total gagal      : {total_failed}")
print(f"Daftar event gagal tersimpan di: {failed_logfile}")
