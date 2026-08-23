# -*- coding: utf-8 -*-
"""TAHAP 3E - Kalender tanggal merah 2025 + matriks hari x jam (READ-ONLY).

Sumber kalender: SKB 3 Menteri No. 1017/2024, No. 2/2024, No. 2/2024
(Hari Libur Nasional & Cuti Bersama 2025), diverifikasi dari setkab.go.id
pada 2026-08-23. Precedence klasifikasi: HOLIDAY > WEEKEND > WORKDAY.
Menghasilkan: 37_holiday_calendar_audit.csv, 39_temporal_matrix.csv,
t3_holiday_stats.json.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
SVC = REPO / "ai-service"
OUT = Path(__file__).resolve().parent
DAY_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]

# (tanggal, nama) - libur nasional lalu cuti bersama, sesuai daftar resmi
LN = [
    ("2025-01-01", "Tahun Baru Masehi"),
    ("2025-01-27", "Isra Mikraj Nabi Muhammad saw."),
    ("2025-01-29", "Tahun Baru Imlek 2576 Kongzili"),
    ("2025-03-29", "Hari Suci Nyepi (Tahun Baru Saka 1947)"),
    ("2025-03-31", "Idulfitri 1446 Hijriah (hari ke-1)"),
    ("2025-04-01", "Idulfitri 1446 Hijriah (hari ke-2)"),
    ("2025-04-18", "Wafat Yesus Kristus"),
    ("2025-04-20", "Kebangkitan Yesus Kristus (Paskah)"),
    ("2025-05-01", "Hari Buruh Internasional"),
    ("2025-05-12", "Hari Raya Waisak 2569 BE"),
    ("2025-05-29", "Kenaikan Yesus Kristus"),
    ("2025-06-01", "Hari Lahir Pancasila"),
    ("2025-06-06", "Iduladha 1446 Hijriah"),
    ("2025-06-27", "1 Muharam Tahun Baru Islam 1447 Hijriah"),
    ("2025-08-17", "Proklamasi Kemerdekaan RI"),
    ("2025-09-05", "Maulid Nabi Muhammad saw."),
    ("2025-12-25", "Kelahiran Yesus Kristus (Natal)"),
]
CB = [
    ("2025-01-28", "Cuti Bersama Tahun Baru Imlek 2576 Kongzili"),
    ("2025-03-28", "Cuti Bersama Hari Suci Nyepi"),
    ("2025-04-02", "Cuti Bersama Idulfitri 1446 Hijriah"),
    ("2025-04-03", "Cuti Bersama Idulfitri 1446 Hijriah"),
    ("2025-04-04", "Cuti Bersama Idulfitri 1446 Hijriah"),
    ("2025-04-07", "Cuti Bersama Idulfitri 1446 Hijriah"),
    ("2025-05-13", "Cuti Bersama Hari Raya Waisak 2569 BE"),
    ("2025-05-30", "Cuti Bersama Kenaikan Yesus Kristus"),
    ("2025-06-09", "Cuti Bersama Iduladha 1446 Hijriah"),
    ("2025-12-26", "Cuti Bersama Kelahiran Yesus Kristus"),
]
STATUS = "TERVERIFIKASI"

synth = pd.read_csv(SVC / "dataset" / "generator" / "raw" / "audit_log_dataset.csv",
                    encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
ts = pd.to_datetime(synth["timestamp"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
N = len(synth)
date_str = ts.dt.strftime("%Y-%m-%d")
cnt_by_date = date_str.value_counts()

holiday_map = {d: nm for d, nm in LN}
holiday_map.update({d: nm for d, nm in CB})

rows37 = []
for d, nm in LN + CB:
    rows37.append([d, DAY_ID[pd.Timestamp(d).dayofweek], nm, STATUS,
                   int(cnt_by_date.get(d, 0))])
with (OUT / "37_holiday_calendar_audit.csv").open("w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows([["date", "day_of_week", "holiday_name", "holiday_status",
                              "activity_count"]] + rows37)
print("[OK] 37_holiday_calendar_audit.csv")

# ------------------------------------------------ klasifikasi hari analitis
is_hol = date_str.isin(holiday_map)
dow = ts.dt.dayofweek
day_cat = pd.Series("WORKDAY", index=synth.index)
day_cat[dow >= 5] = "WEEKEND"
day_cat[is_hol] = "HOLIDAY"  # precedence HOLIDAY > WEEKEND

hr = ts.dt.hour
time_cat = pd.Series("WORKING_HOURS", index=synth.index)
time_cat[hr < 8] = "BEFORE_WORKING_HOURS"
time_cat[hr >= 16] = "AFTER_WORKING_HOURS"


def pct(n):
    return round(100.0 * n / N, 4)


rows39 = []
for dc in ["WORKDAY", "WEEKEND", "HOLIDAY"]:
    for tc in ["WORKING_HOURS", "BEFORE_WORKING_HOURS", "AFTER_WORKING_HOURS"]:
        c = int(((day_cat == dc) & (time_cat == tc)).sum())
        rows39.append([dc, tc, c, pct(c)])
c_unk = int((~day_cat.isin(["WORKDAY", "WEEKEND", "HOLIDAY"])).sum())
rows39.append(["UNKNOWN", "(semua)", c_unk, pct(c_unk)])
with (OUT / "39_temporal_matrix.csv").open("w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows([["day_category", "time_category", "record_count",
                              "percentage"]] + rows39)
print("[OK] 39_temporal_matrix.csv")

# ------------------------------------------------ statistik untuk laporan
hol_mask = is_hol
h_ts = ts[hol_mask]
h_act = synth.loc[hol_mask, "activity"].value_counts()
h_hour = h_ts.dt.hour.value_counts().sort_index()
stats = {
    "source": "SKB 3 Menteri No.1017/2024, No.2/2024, No.2/2024 via setkab.go.id (akses 2026-08-23)",
    "n_libur_nasional": len(LN), "n_cuti_bersama": len(CB), "n_holiday_dates": len(LN) + len(CB),
    "holiday_overlap_weekend": int(sum(1 for d, _ in LN + CB if pd.Timestamp(d).dayofweek >= 5)),
    "activities_on_holiday": int(hol_mask.sum()),
    "pct_activities_on_holiday": pct(int(hol_mask.sum())),
    "holiday_working": int(((day_cat == "HOLIDAY") & (time_cat == "WORKING_HOURS")).sum()),
    "holiday_before": int(((day_cat == "HOLIDAY") & (time_cat == "BEFORE_WORKING_HOURS")).sum()),
    "holiday_after": int(((day_cat == "HOLIDAY") & (time_cat == "AFTER_WORKING_HOURS")).sum()),
    "holiday_per_date": {d: int(cnt_by_date.get(d, 0)) for d, _ in LN + CB},
    "holiday_activity_types": h_act.to_dict(),
    "holiday_hours": {f"{int(h):02d}": int(c) for h, c in h_hour.items()},
    "holiday_anomaly_labels": synth.loc[hol_mask, "anomaly_type"].value_counts().to_dict(),
    "weekend_nonholiday": int(((day_cat == "WEEKEND")).sum()),
    "workday_nonholiday": int(((day_cat == "WORKDAY")).sum()),
}
(OUT / "t3_holiday_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
print(json.dumps(stats, indent=2))
