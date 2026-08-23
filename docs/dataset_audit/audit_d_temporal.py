# -*- coding: utf-8 -*-
"""TAHAP 3 - Audit waktu & kalender dataset synthetic (READ-ONLY).

Menghasilkan: 33, 34, 35, 36, 41, t3_stats.json. Dataset real hanya pembanding
(SELECT-only). Tidak mengubah dataset/generator/model.
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


def pct(n, d):
    return round(100.0 * n / d, 4) if d else 0.0


def write_csv(name, header, rows):
    with (OUT / name).open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows([header] + rows)
    print(f"[OK] {name} ({len(rows)} baris)")


synth = pd.read_csv(SVC / "dataset" / "generator" / "raw" / "audit_log_dataset.csv",
                    encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
ts = pd.to_datetime(synth["timestamp"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
N = len(synth)

# ------------------------------------------------ 33 distribusi jam detail
INTERVALS = [
    ("<07:00", lambda h: h < 7),
    ("07:00-07:59", lambda h: h == 7),
    ("08:00-08:59", lambda h: h == 8),
    ("09:00-09:59", lambda h: h == 9),
    ("10:00-10:59", lambda h: h == 10),
    ("11:00-11:59", lambda h: h == 11),
    ("12:00-12:59", lambda h: h == 12),
    ("13:00-13:59", lambda h: h == 13),
    ("14:00-14:59", lambda h: h == 14),
    ("15:00-15:59", lambda h: h == 15),
    ("16:00-16:59", lambda h: h == 16),
    (">=17:00", lambda h: h >= 17),
]
hr = ts.dt.hour
rows33 = []
for label, fn in INTERVALS:
    c = int(fn(hr).sum())
    rows33.append([label, c, pct(c, N)])
b_before = int((hr < 8).sum())
b_office = int(((hr >= 8) & (hr <= 15)).sum())
b_after = int((hr >= 16).sum())
for label, c in (("KELOMPOK sebelum jam kerja (<08:00)", b_before),
                 ("KELOMPOK jam kerja 08:00-15:59", b_office),
                 ("KELOMPOK setelah jam kerja (>=16:00)", b_after)):
    rows33.append([label, c, pct(c, N)])
write_csv("33_hourly_distribution_detailed.csv",
          ["time_interval", "record_count", "percentage"], rows33)

# ------------------------------------------------ 34 aktivitas per tanggal
by_date = ts.dt.date.value_counts().sort_index()
d34 = []
for d, c in by_date.items():
    d34.append([str(d), DAY_ID[pd.Timestamp(d).dayofweek], int(c)])
stats_daily = {
    "unique_dates": int(len(by_date)),
    "max_date": str(by_date.idxmax()), "max_count": int(by_date.max()),
    "min_date": str(by_date.idxmin()), "min_count": int(by_date.min()),
    "mean_per_date": round(float(by_date.mean()), 4),
    "median_per_date": float(by_date.median()),
}
write_csv("34_daily_activity_distribution.csv", ["date", "day_of_week", "record_count"], d34)

# ------------------------------------------------ 35/36 hari dalam minggu
dow = ts.dt.dayofweek
rows35 = [[DAY_ID[i], int((dow == i).sum()), pct(int((dow == i).sum()), N)] for i in range(7)]
write_csv("35_weekday_distribution.csv", ["day_of_week", "record_count", "percentage"], rows35)
wk = int((dow < 5).sum())
we = int((dow >= 5).sum())
write_csv("36_workday_weekend_distribution.csv",
          ["day_category", "record_count", "percentage"],
          [["WORKDAY", wk, pct(wk, N)], ["WEEKEND", we, pct(we, N)],
           ["HOLIDAY", "NEEDS_VERIFICATION", "-"],
           ["UNKNOWN", 0, 0.0]])

# ------------------------------------------------ real pembanding (SELECT-only)
real_rows = []
try:
    import psycopg2

    conn = psycopg2.connect(host="localhost", port=5432, dbname="sistem_arsip_digital",
                            user="postgres", password="qethipen29", connect_timeout=5)
    cur = conn.cursor()
    cur.execute("SELECT waktu FROM audit_log ORDER BY id")
    real_rows = [r[0] for r in cur.fetchall()]
    conn.rollback()
    conn.close()
except Exception as exc:  # noqa: BLE001
    print("[DB] gagal:", repr(exc))
rt = pd.to_datetime(pd.Series(real_rows)) if len(real_rows) else None
rhr = rt.dt.hour if rt is not None else None
rdow = rt.dt.dayofweek if rt is not None else None
NR = len(real_rows)


def bucket(h):
    if h < 8:
        return "<08:00"
    if h <= 15:
        return "08:00-15:59"
    if h == 16:
        return "16:00-16:59"
    return ">=17:00"


rows41 = []
for ds, series_h, series_dw, n in (
    ("synthetic_raw", hr, dow, N),
    ("postgresql_real", rhr, rdow, NR),
):
    if n == 0:
        continue
    vc = series_h.map(bucket).value_counts()
    for cat in ["<08:00", "08:00-15:59", "16:00-16:59", ">=17:00"]:
        c = int(vc.get(cat, 0))
        rows41.append([ds, cat, "(semua hari)", c, pct(c, n)])
    wkd = int((series_dw < 5).sum())
    wed = int((series_dw >= 5).sum())
    rows41.append([ds, "(semua jam)", "WORKDAY", wkd, pct(wkd, n)])
    rows41.append([ds, "(semua jam)", "WEEKEND", wed, pct(wed, n)])
write_csv("41_temporal_synthetic_vs_real.csv",
          ["dataset", "time_category", "day_category", "record_count", "percentage"], rows41)

# ------------------------------------------------ statistik pendukung laporan
we_office = int(((dow >= 5) & ((hr >= 8) & (hr <= 15))).sum())
we_outside = int((dow >= 5).sum()) - we_office
wd_outside = int((dow < 5).sum()) - int(((dow < 5) & ((hr >= 8) & (hr <= 15))).sum())
llj_mask = synth["anomaly_type"] == "login_luar_jam"
stats = {
    "total": N,
    "before_8": b_before, "office_8_16": b_office, "after_16": b_after,
    "workday": wk, "weekend": we,
    "workday_outside": wd_outside, "weekend_outside": we_outside, "weekend_office": we_office,
    "hourly_counts": {f"{h:02d}": int((hr == h).sum()) for h in range(24)},
    "daily": stats_daily,
    "login_luar_jam_total": int(llj_mask.sum()),
    "login_luar_jam_hours_0_6": int((hr[llj_mask] <= 6).sum()),
    "normal_before_7": int(((~llj_mask) & (hr < 7)).sum()),
    "at_0700_exact": int((ts.dt.time.astype(str) == "07:00:00").sum()),
    "at_1700_exact": int((ts.dt.time.astype(str) == "17:00:00").sum()),
    "session_chain_min_gap": None,
}
# gap antaraktivitas sesi (dependency antar timestamp)
g = synth.sort_values(["session_id", "timestamp"]).copy()
g["gap_s"] = pd.to_datetime(g["timestamp"]).diff().dt.total_seconds()
same_sess = g["session_id"] == g["session_id"].shift()
stats["session_chain_min_gap"] = float(g.loc[same_sess, "gap_s"].min())
stats["session_chain_max_gap"] = float(g.loc[same_sess, "gap_s"].max())
stats["session_chain_median_gap"] = float(g.loc[same_sess, "gap_s"].median())
stats["first_activity_at_070000"] = int(((ts.dt.time.astype(str) == "07:00:00") &
                                         (synth["activity"] == "Login")).sum())
(OUT / "t3_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
print("[OK] t3_stats.json")
print(json.dumps({k: v for k, v in stats.items() if k != "hourly_counts"}, indent=2))
