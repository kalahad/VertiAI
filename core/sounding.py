# -*- coding: utf-8 -*-
"""
VertiAI - Core Sounding Engine (Session 1)
พอร์ตตรรกะจาก ReadSounding_11_from_ReadSounding_10.ipynb (ทำงานได้จริงแล้ว)
แยกเป็น 3 ฟังก์ชันที่เรียกซ้ำได้: download_sounding / parse_sounding / compute_indices
หมายเหตุ: ทุกค่าทางอุตุนิยมวิทยาคำนวณด้วย MetPy เท่านั้น ไม่คำนวณเอง
"""

import io
import re
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
import requests

import metpy.calc as mpcalc
from metpy.units import units


# ==================== PART 1: Download ====================
def download_sounding(station_id, year, month, day, hour):
    """
    ดึงข้อมูล Sounding จาก University of Wyoming (region=seasia, TEXT:LIST)
    คืนค่า dict: {ok, heading, table_text, error}
    - มีระบบ fallback ตาม FR-1 หากแหล่งข้อมูลภายนอกล่ม/ไม่มีข้อมูล
    """
    base_url = "http://weather.uwyo.edu/cgi-bin/sounding"
    region = "seasia"
    data_type = "TEXT%3ALIST"  # = TEXT:LIST

    # ประกอบ FROM/TO เป็นรูปแบบ DDHH ตาม notebook
    dd = f"{int(day):02d}"
    hh = f"{int(hour):02d}"
    ddhh = f"{dd}{hh}"
    mm = f"{int(month):02d}"

    url = (
        f"{base_url}?region={region}&TYPE={data_type}"
        f"&YEAR={year}&MONTH={mm}&FROM={ddhh}&TO={ddhh}&STNM={station_id}"
    )

    # User-Agent ตาม notebook (กันการถูกบล็อก)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/114.0.0.0 Safari/537.36"
        )
    }

    result = {"ok": False, "heading": None, "table_text": None, "error": None, "url": url}

    try:
        resp = requests.get(url, headers=headers, timeout=30)
    except requests.exceptions.RequestException as e:
        # Fallback: เครือข่าย/แหล่งข้อมูลล่ม
        result["error"] = f"ไม่สามารถเชื่อมต่อแหล่งข้อมูลได้: {e}"
        return result

    if resp.status_code != 200:
        result["error"] = f"HTTP {resp.status_code}: ไม่สามารถเชื่อมต่อเว็บไซต์ได้"
        return result

    if "<H2>" not in resp.text:
        result["error"] = "ไม่พบข้อมูล Sounding สำหรับวันและเวลานี้"
        return result

    # แยกข้อความและหัวเรื่องด้วย BeautifulSoup (เหมือน notebook)
    soup = BeautifulSoup(resp.text, "html.parser")
    heading_tag = soup.find("h2")
    if not heading_tag:
        result["error"] = "ไม่พบ Heading (H2) ในหน้าผลลัพธ์"
        return result
    heading = heading_tag.text.strip()

    plain_text = soup.get_text(separator="\n")
    lines = plain_text.splitlines()

    # ตัดเฉพาะตาราง: ตั้งแต่หัวคอลัมน์ PRES...HGHT ถึงก่อน "Station information..."
    start_index = next(
        (i for i, line in enumerate(lines) if "PRES" in line and "HGHT" in line), None
    )
    end_index = next(
        (i for i, line in enumerate(lines) if "Station information and sounding indices" in line),
        None,
    )

    if start_index is None or end_index is None:
        result["error"] = "ไม่พบตารางข้อมูล Sounding ในหน้าผลลัพธ์"
        return result

    sounding_data_table = lines[start_index - 1 : end_index - 1]
    table_text = heading + "\n" + "\n".join(sounding_data_table)

    result.update({"ok": True, "heading": heading, "table_text": table_text})
    return result


# ==================== PART 2: Parse ====================
COL_NAMES = ["PRES", "HGHT", "TEMP", "DWPT", "RELH", "MIXR",
             "DRCT", "SKNT", "THTA", "THTE", "THTV"]


def parse_sounding(raw_text):
    """
    แปลงตารางข้อความ -> pandas.DataFrame (logic เดียวกับ notebook)
    raw_text คือผลจาก download_sounding()['table_text']
    บรรทัดแรกเป็น heading จึง skiprows=4 เพื่อข้ามหัวตาราง/หน่วย
    """
    df = pd.read_csv(
        io.StringIO(raw_text),
        sep=r"\s+",            # delim_whitespace (เลิกใช้แล้ว) -> ใช้ regex แทน
        skiprows=4,
        names=COL_NAMES,
        engine="python",
    )
    df = df.dropna()
    df = df.apply(pd.to_numeric, errors="coerce")
    df = df.dropna()

    # เปลี่ยนชื่อคอลัมน์ให้ใช้งานง่าย (ตาม notebook)
    df = df.rename(columns={
        "PRES": "pressure",
        "HGHT": "height",
        "TEMP": "temperature",
        "DWPT": "dewpoint",
        "DRCT": "direction",
        "SKNT": "speed",
    })
    return df


# ==================== PART 3: Compute Indices ====================
def _safe_mag(q, unit=None):
    """ดึง magnitude อย่างปลอดภัย คืน None ถ้าเป็น nan/None"""
    if q is None:
        return None
    try:
        v = q.to(unit).magnitude if unit else q.magnitude
    except Exception:
        v = getattr(q, "magnitude", q)
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    return float(v)


def _level_for_temp(p, T, height, target_c):
    """
    หา Freezing Level: ระดับความดัน/ความสูงแรกที่อุณหภูมิข้าม target_c (เช่น 0, -10)
    ใช้ interpolation เชิงเส้นระหว่างสองชั้นที่คร่อมค่า
    """
    Tm = T.to("degC").magnitude
    pm = p.to("hPa").magnitude
    hm = np.asarray(height)
    for i in range(len(Tm) - 1):
        t0, t1 = Tm[i], Tm[i + 1]
        if (t0 - target_c) * (t1 - target_c) <= 0 and t0 != t1:
            frac = (target_c - t0) / (t1 - t0)
            pr = pm[i] + frac * (pm[i + 1] - pm[i])
            ht = hm[i] + frac * (hm[i + 1] - hm[i])
            return {"pressure_hPa": round(float(pr), 1), "height_m": round(float(ht), 0)}
    return None


def compute_indices(df, heading=None):
    """
    คำนวณดัชนีเสถียรภาพด้วย MetPy (เหมือน notebook + เพิ่มตาม PRD)
    คืน dict พร้อมข้อมูลสำหรับ plot (profile, u, v, inversion, pressure->height map)
    """
    if df is None or len(df) == 0:
        return {"ok": False, "error": "ไม่มีข้อมูลที่ใช้งานได้ใน DataFrame"}

    # แนบหน่วยให้ตัวแปร (ตาม notebook)
    p = df["pressure"].values * units.hPa
    T = df["temperature"].values * units.degC
    Td = df["dewpoint"].values * units.degC
    wind_speed = df["speed"].values * units.knots
    wind_dir = df["direction"].values * units.degrees
    u, v = mpcalc.wind_components(wind_speed, wind_dir)

    # --- ดัชนีหลัก (เหมือน notebook) ---
    lcl_p, lcl_t = mpcalc.lcl(p[0], T[0], Td[0])
    parcel_prof = mpcalc.parcel_profile(p, T[0], Td[0]).to("degC")
    cape, cin = mpcalc.cape_cin(p, T, Td, parcel_prof)

    # LFC (อาจ None เมื่อบรรยากาศเสถียร) -> จัดการปลอดภัย
    try:
        lfc_p, lfc_t = mpcalc.lfc(p, T, Td)
    except Exception:
        lfc_p, lfc_t = None, None

    # --- ดัชนีเพิ่มตาม PRD ---
    try:
        el_p, el_t = mpcalc.el(p, T, Td, parcel_prof)
    except Exception:
        el_p, el_t = None, None
    try:
        li = mpcalc.lifted_index(p, T, parcel_prof)
        # บางเวอร์ชันคืน array -> เอาค่าแรก
        li = np.atleast_1d(li)[0]
    except Exception:
        li = None
    try:
        pwat = mpcalc.precipitable_water(p, Td)
    except Exception:
        pwat = None
    try:
        kindex = mpcalc.k_index(p, T, Td)
    except Exception:
        kindex = None

    # --- Freezing Level 0°C และ -10°C (สำคัญต่อบทบาทนักบิน) ---
    height_vals = df["height"].values
    fl_0 = _level_for_temp(p, T, height_vals, 0.0)
    fl_m10 = _level_for_temp(p, T, height_vals, -10.0)

    # --- RH ที่ 700 hPa (ใช้ในกฎ AI) ---
    rh700 = None
    if "RELH" in df.columns or "relh" in df.columns:
        col = "RELH" if "RELH" in df.columns else "relh"
        idx = (df["pressure"] - 700).abs().idxmin()
        rh700 = float(df.loc[idx, col])

    # --- Inversion layers: ช่วงที่ np.diff(T) > 0 (เหมือน notebook) ---
    Tm = T.magnitude
    pm = p.magnitude
    dT = np.diff(Tm)
    inversion_layers = []
    for i in range(len(dT)):
        if dT[i] > 0:
            inversion_layers.append([float(pm[i]), float(pm[i + 1])])  # [bottom, top]

    # --- mapping pressure -> height ที่ระดับมาตรฐาน (เหมือน notebook) ---
    df_h = df.dropna(subset=["height"])
    pressure_levels = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
    ph_map = []
    for pres in pressure_levels:
        closest = df_h.iloc[(df_h["pressure"] - pres).abs().argsort()[:1]]
        if len(closest):
            ph_map.append({"pressure": pres, "height": int(closest["height"].values[0])})

    result = {
        "ok": True,
        "heading": heading,
        # ค่าดัชนี (ตัวเลขล้วน หน่วยมาตรฐาน)
        "indices": {
            "CAPE": _safe_mag(cape, "J/kg"),
            "CIN": _safe_mag(cin, "J/kg"),
            "LI": _safe_mag(li),
            "PWAT": _safe_mag(pwat, "mm"),
            "K_INDEX": _safe_mag(kindex, "delta_degC") or _safe_mag(kindex),
            "LCL_p": _safe_mag(lcl_p, "hPa"),
            "LCL_t": _safe_mag(lcl_t, "degC"),
            "LFC_p": _safe_mag(lfc_p, "hPa"),
            "LFC_t": _safe_mag(lfc_t, "degC"),
            "EL_p": _safe_mag(el_p, "hPa"),
            "EL_t": _safe_mag(el_t, "degC"),
            "RH_700": rh700,
            "FREEZING_0C": fl_0,
            "FREEZING_-10C": fl_m10,
        },
        # ข้อมูลสำหรับ plot (Session 4)
        "profile": {
            "pressure": [float(x) for x in pm],
            "temperature": [float(x) for x in Tm],
            "dewpoint": [float(x) for x in Td.magnitude],
            "height": [float(x) for x in height_vals],
            "u": [float(x) for x in u.magnitude],
            "v": [float(x) for x in v.magnitude],
            "speed": [float(x) for x in wind_speed.magnitude],
            "parcel": [float(x) for x in parcel_prof.magnitude],
        },
        "inversion_layers": inversion_layers,
        "pressure_height_map": ph_map,
        "stable": (_safe_mag(lfc_p, "hPa") is None),  # ไม่มี LFC = บรรยากาศเสถียร
    }
    return result


# ==================== MAIN TEST ====================
if __name__ == "__main__":
    # ทดสอบจริงกับสถานีบางนา 48453 (ปรับวันที่ได้ตรงนี้)
    STATION = "48453"
    YEAR, MONTH, DAY, HOUR = 2025, 12, 1, 0

    print("=" * 60)
    print(f"STEP 1: Download {STATION} {YEAR}-{MONTH:02d}-{DAY:02d} {HOUR:02d}Z")
    print("=" * 60)
    dl = download_sounding(STATION, YEAR, MONTH, DAY, HOUR)
    if not dl["ok"]:
        print("ERROR:", dl["error"])
        print("URL:", dl["url"])
        raise SystemExit(1)
    print("Heading:", dl["heading"])

    print("\nSTEP 2: Parse")
    df = parse_sounding(dl["table_text"])
    print(df.head())
    print("rows:", len(df))

    print("\nSTEP 3: Compute indices")
    out = compute_indices(df, heading=dl["heading"])
    import json
    print(json.dumps(out["indices"], indent=2, ensure_ascii=False))
    print("inversion layers:", len(out["inversion_layers"]))
    print("stable atmosphere:", out["stable"])
