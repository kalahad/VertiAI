# -*- coding: utf-8 -*-
"""
VertiAI - Flask API (Session 3 + Session 5)
เชื่อม Core Engine (Session 1) + Rule-Based AI (Session 2) เข้ากับ SQLite cache
ทุก endpoint คืน JSON | มี data validation กัน XSS/SQL injection | ตอบ < 2s ด้วย cache
Session 5: เพิ่มหน้า data/settings/landing + เกณฑ์เฉพาะถิ่นที่ปรับได้ + role KPI config

รัน: flask --app app run --debug
"""

import re
import time
import logging
import secrets
import os

import numpy as np
from flask import Flask, request, jsonify, session, render_template

from core import sounding as snd
from core import ai_rules as ai
from core import db
from core import sounding_interpreter as interp

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.environ.get('VERTIAI_SECRET', 'vertiai-dev-key-2026')  # คงที่ข้ามรอบ restart

# ตั้งค่า logging วัดเวลาตอบสนอง (PRD: dashboard < 2s)
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
PERF_BUDGET_MS = 2000   # งบเวลาเป้าหมายต่อคำขอ


def _log_perf(endpoint, station, elapsed_ms, cached):
    """log เวลา + เตือนเมื่อเกินงบ 2 วินาที"""
    tag = "cache" if cached else "live"
    msg = f"{endpoint} station={station} {tag} {elapsed_ms}ms"
    if elapsed_ms > PERF_BUDGET_MS:
        app.logger.warning("SLOW %s (เกินงบ %dms)", msg, PERF_BUDGET_MS)
    else:
        app.logger.info(msg)

# เริ่มฐานข้อมูลตอนสตาร์ท
db.init_db()

# ==================== ค่าคงที่ / รายชื่อสถานี ====================
STATIONS = [
    {"id": "48453", "name": "กรุงเทพฯ (บางนา)", "name_en": "Bangkok"},
    {"id": "48327", "name": "เชียงใหม่", "name_en": "Chiang Mai"},
    {"id": "48407", "name": "อุบลราชธานี", "name_en": "Ubon Ratchathani"},
    {"id": "48568", "name": "สงขลา", "name_en": "Songkhla"},
]
VALID_STATIONS = {s["id"] for s in STATIONS}
VALID_ROLES = {"rainmaking", "meteorologist", "researcher", "farmer",
               "factory", "tourist", "general"}

# region ที่อนุญาตให้ปรับเกณฑ์ในหน้า Settings (ตรงกับ REGIONAL_THRESHOLDS)
VALID_REGIONS = set(ai.REGIONAL_THRESHOLDS.keys())
# คีย์เกณฑ์ที่ปรับได้ + ช่วงค่าที่สมเหตุสมผล (กันค่าเพี้ยน)
THRESHOLD_BOUNDS = {
    "RH_min": (0, 100), "WS_min": (0, 200), "WS_max": (0, 200),
    "KI_min": (-50, 60), "KI_max": (-50, 60),
}

# ==================== Validation (กัน XSS/Injection ตาม PRD Security) ====================
_STATION_RE = re.compile(r"^\d{4,6}$")           # รหัสสถานีเป็นตัวเลขล้วน
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")     # YYYY-MM-DD


def _bad(msg, code=400):
    """คืน error JSON พร้อม HTTP code ที่เหมาะสม"""
    return jsonify({"ok": False, "error": msg}), code


def _representative_ws(profile):
    """
    ความเร็วลมตัวแทน (WS_repr) สำหรับ apply_regional
    ใช้ค่าเฉลี่ยลมชั้นล่าง-กลาง (ความดัน >= 700 hPa) หน่วยนอต
    คืน None หากไม่มีข้อมูลลม
    """
    if not profile:
        return None
    pres = profile.get("pressure") or []
    spd = profile.get("speed") or []
    vals = [s for p, s in zip(pres, spd) if p is not None and p >= 700 and s is not None]
    if not vals:
        return None
    return round(float(np.mean(vals)), 1)


def _analyze(raw_text, heading=None, region=None):
    """
    pipeline: parse -> compute -> ai (rain/rainmaking/regional)
    เติม WS_repr จาก profile ก่อนเรียก apply_regional (ข้อกำหนด Session 3)
    คืน dict รวมผลทั้งหมด หรือ raise ValueError หาก parse/compute ล้มเหลว
    """
    df = snd.parse_sounding(raw_text)
    if df is None or len(df) == 0:
        raise ValueError("ไม่พบข้อมูลที่ใช้งานได้หลังการ parse")

    computed = snd.compute_indices(df, heading=heading)
    if not computed.get("ok"):
        raise ValueError(computed.get("error", "คำนวณดัชนีไม่สำเร็จ"))

    indices = computed["indices"]
    # เติมความเร็วลมตัวแทนให้ apply_regional ใช้ได้
    indices["WS_repr"] = _representative_ws(computed.get("profile"))

    result = {
        "heading": computed.get("heading"),
        "profile": computed["profile"],
        "indices": indices,
        "inversion_layers": computed.get("inversion_layers", []),
        "pressure_height_map": computed.get("pressure_height_map", []),
        "stable": computed.get("stable"),
        "ai": ai.assess_rain_chance(indices),
        "rainmaking": ai.assess_rainmaking(indices),
    }
    if region:
        override = db.get_region_threshold(region)  # ค่าที่ผู้ใช้ปรับในหน้า Settings
        result["regional"] = ai.apply_regional(indices, region, override=override)
    return result


# ==================== หน้าเว็บ (Frontend) ====================
@app.get("/")
def index():
    """หน้า Dashboard หลัก (Session 4)"""
    return render_template("dashboard.html")


@app.get("/landing")
def landing():
    """หน้า Landing/Guest อธิบายความสามารถ + พันธกิจฝนหลวง (Session 5)"""
    return render_template("landing.html")


@app.get("/data")
def data_portal():
    """หน้าจัดการข้อมูล: อัปโหลด + สืบค้นประวัติ (Session 5)"""
    return render_template("data.html")


@app.get("/settings")
def settings_page():
    """หน้าตั้งค่า role + เกณฑ์เฉพาะถิ่น (Session 5)"""
    return render_template("settings.html")


# ==================== Endpoints ====================
@app.get("/api/stations")
def api_stations():
    """รายชื่อสถานีที่รองรับ"""
    return jsonify({"ok": True, "stations": STATIONS})


@app.get("/api/sounding")
def api_sounding():
    """
    GET /api/sounding?station=&date=YYYY-MM-DD&hour=&region=(optional)
    download -> parse -> compute -> ai | cache ผลใน SQLite (key = station+datetime)
    """
    t0 = time.time()
    station = (request.args.get("station") or "").strip()
    date = (request.args.get("date") or "").strip()
    hour = (request.args.get("hour") or "").strip()
    region = (request.args.get("region") or "").strip() or None

    # --- validate ---
    if not _STATION_RE.match(station):
        return _bad("รหัสสถานีไม่ถูกต้อง (ต้องเป็นตัวเลข)")
    if station not in VALID_STATIONS:
        return _bad(f"ไม่รองรับสถานี {station}")
    if not _DATE_RE.match(date):
        return _bad("รูปแบบวันที่ไม่ถูกต้อง (YYYY-MM-DD)")
    if not hour.isdigit() or int(hour) not in (0, 6, 12, 18):
        return _bad("ชั่วโมงต้องเป็น 00/06/12/18 (UTC)")

    year, month, day = date.split("-")
    hour_i = int(hour)
    key = db.make_key(station, year, month, day, hour_i)

    # --- ใช้ cache ก่อน (ตอบเร็ว < 2s) ---
    cached = db.get_cached(station, key)
    if cached and cached.get("result"):
        out = cached["result"]
        out["cached"] = True
        out["elapsed_ms"] = int((time.time() - t0) * 1000)
        # region อาจต่างจากที่ cache ไว้ -> คำนวณ regional ใหม่จาก indices ที่มี
        if region and out.get("indices"):
            override = db.get_region_threshold(region)
            out["regional"] = ai.apply_regional(out["indices"], region, override=override)
        out["_meta"] = {"station": station, "date": date, "hour": hour_i}
        _log_perf("/api/sounding", station, out["elapsed_ms"], cached=True)
        try: db.save_last_upload(out)
        except Exception: pass
        return jsonify({"ok": True, **out})

    # --- ดึงสด (sandbox อาจถูกบล็อก -> คืน error fallback ตาม FR-1) ---
    dl = snd.download_sounding(station, year, month, day, hour_i)
    if not dl.get("ok"):
        return _bad(dl.get("error", "ดึงข้อมูลไม่สำเร็จ"), code=502)

    try:
        result = _analyze(dl["table_text"], heading=dl.get("heading"), region=region)
    except ValueError as e:
        return _bad(str(e), code=422)

    # --- บันทึก cache + last_result ---
    db.save_cache(station, key, dl["table_text"], result)
    result["cached"] = False
    result["elapsed_ms"] = int((time.time() - t0) * 1000)
    result["_meta"] = {"station": station, "date": date, "hour": hour_i}
    _log_perf("/api/sounding", station, result["elapsed_ms"], cached=False)
    try: db.save_last_upload(result)
    except Exception: pass
    return jsonify({"ok": True, **result})


@app.post("/api/upload")
def api_upload():
    """
    POST /api/upload — รับไฟล์ HTML/text-list (TMD/Wyoming) แล้ว parse ด้วย logic เดิม
    รับได้ทั้ง multipart (field 'file') หรือ raw text ใน body
    """
    raw = None
    if "file" in request.files:
        f = request.files["file"]
        raw = f.read().decode("utf-8", errors="ignore")
    elif request.data:
        raw = request.data.decode("utf-8", errors="ignore")
    elif request.form.get("text"):
        raw = request.form.get("text")

    if not raw or not raw.strip():
        return _bad("ไม่พบเนื้อหาไฟล์ที่อัปโหลด")
    # จำกัดขนาดกันยิงไฟล์ใหญ่ (กัน DoS)
    if len(raw) > 2_000_000:
        return _bad("ไฟล์ใหญ่เกินกำหนด (จำกัด ~2MB)", code=413)

    region = (request.args.get("region") or "").strip() or None
    try:
        result = _analyze(raw, heading="อัปโหลดโดยผู้ใช้", region=region)
    except ValueError as e:
        return _bad(str(e), code=422)
    except Exception:
        # parse ล้มเหลวจากไฟล์ผิดรูปแบบ
        return _bad("ไฟล์ไม่ถูกรูปแบบตาราง Sounding (text-list)", code=422)

    result["cached"] = False
    # บันทึกลง DB แทน session cookie (หลีกเลี่ยง 4KB cookie limit)
    try:
        db.save_last_upload(result)
    except Exception:
        pass
    return jsonify({"ok": True, **result})


@app.get("/api/last_upload")
def api_last_upload():
    """คืนผลอัปโหลดล่าสุดจาก DB — ใช้เมื่อ Wyoming ล่ม"""
    result = db.get_last_upload()
    if not result:
        return _bad("ยังไม่มีข้อมูลที่อัปโหลดไว้", code=404)
    return jsonify({"ok": True, **result})


@app.get("/api/history")
def api_history():
    """GET /api/history?station=&year= — รายการผลที่ cache ไว้ (รองรับ ค.ศ.2020-2024 / พ.ศ.2563-2567)"""
    station = (request.args.get("station") or "").strip() or None
    year = (request.args.get("year") or "").strip() or None

    if station and not _STATION_RE.match(station):
        return _bad("รหัสสถานีไม่ถูกต้อง")
    if year:
        if not year.isdigit():
            return _bad("ปีไม่ถูกต้อง")
        yi = int(year)
        # รองรับการส่งเป็น พ.ศ. -> แปลงเป็น ค.ศ. อัตโนมัติ
        if yi > 2500:
            yi -= 543
        year = str(yi)

    items = db.list_history(station, year)
    return jsonify({"ok": True, "count": len(items), "items": items})


@app.delete("/api/history")
def api_delete_history():
    """DELETE /api/history?datetime_utc=&station= — ลบ cache entry"""
    datetime_utc = (request.args.get("datetime_utc") or "").strip()
    station      = (request.args.get("station") or "").strip() or None
    if not datetime_utc:
        return _bad("ต้องระบุ datetime_utc")
    if station and not _STATION_RE.match(station):
        return _bad("รหัสสถานีไม่ถูกต้อง")
    db.delete_cache(datetime_utc, station)
    return jsonify({"ok": True})


@app.post("/api/login")
def api_login():
    """
    POST /api/login {role} — auth ง่าย ๆ ตั้ง role เก็บใน session
    role: pilot / meteorologist / researcher / farmer
    """
    data = request.get_json(silent=True) or request.form
    role = (data.get("role") or "").strip().lower()
    if role not in VALID_ROLES:
        return _bad(f"role ไม่ถูกต้อง (เลือก: {', '.join(sorted(VALID_ROLES))})")
    session["role"] = role
    return jsonify({"ok": True, "role": role})


@app.get("/api/me")
def api_me():
    """ตรวจ role ปัจจุบันใน session"""
    return jsonify({"ok": True, "role": session.get("role")})


@app.post("/api/logout")
def api_logout():
    """ออกจากระบบ ล้าง session"""
    session.clear()
    return jsonify({"ok": True})


@app.get("/api/dam_inflow")
def api_dam_inflow():
    """GET /api/dam_inflow?C=&I=&A= — ประเมินน้ำไหลลงเขื่อน (Q=CIA)"""
    try:
        C = float(request.args.get("C"))
        I = float(request.args.get("I"))
        A = float(request.args.get("A"))
    except (TypeError, ValueError):
        return _bad("ต้องระบุ C, I, A เป็นตัวเลข")
    return jsonify({"ok": True, **ai.estimate_dam_inflow(C, I, A)})


# ==================== Role-based KPI config (Session 5) ====================
# แต่ละ role เน้น KPI ต่างกัน (frontend ใช้ไฮไลต์การ์ด KPI)
ROLE_KPI_FOCUS = {
    "rainmaking":    ["FREEZING_0C", "LCL_p", "LFC_p", "EL_p", "CAPE", "PWAT"],
    "meteorologist": ["CAPE", "CIN", "LI", "K_INDEX", "PWAT"],
    "researcher":    ["CAPE", "CIN", "LI", "PWAT", "K_INDEX",
                      "LCL_p", "LFC_p", "EL_p", "FREEZING_0C"],
    "farmer":        ["CAPE", "PWAT", "K_INDEX"],
    "factory":       ["PWAT", "K_INDEX", "LCL_p"],        # มลพิษ/Mixing Layer/ฝน
    "tourist":       ["CAPE", "PWAT", "K_INDEX", "LI"],   # สภาพอากาศทั่วไป
    "general":       ["CAPE", "PWAT", "K_INDEX"],          # ประชาชนทั่วไป
}
ROLE_LABELS = {
    "rainmaking":    {"th": "เจ้าหน้าที่ฝนหลวง", "en": "Rainmaking Officer"},
    "meteorologist": {"th": "นักอุตุนิยมวิทยา", "en": "Meteorologist"},
    "researcher":    {"th": "นักวิจัย", "en": "Researcher"},
    "farmer":        {"th": "เกษตรกร", "en": "Farmer"},
    "factory":       {"th": "โรงงานอุตสาหกรรม", "en": "Factory"},
    "tourist":       {"th": "นักท่องเที่ยว", "en": "Tourist"},
    "general":       {"th": "ประชาชนทั่วไป", "en": "General Public"},
}
ROLE_ORDER = ["rainmaking", "meteorologist", "researcher", "farmer",
              "factory", "tourist", "general"]


@app.get("/api/roles")
def api_roles():
    """ข้อมูล role ทั้งหมด + KPI ที่เน้น + role ปัจจุบัน (สำหรับ Settings/Dashboard)"""
    roles = [
        {"id": r, "label": ROLE_LABELS[r], "focus": ROLE_KPI_FOCUS[r]}
        for r in ROLE_ORDER
    ]
    return jsonify({"ok": True, "roles": roles, "current": session.get("role") or "rainmaking"})


@app.get("/api/thresholds")
def api_get_thresholds():
    """
    คืนเกณฑ์เฉพาะถิ่นทั้งหมด = ค่าตั้งต้น (โค้ด) ผสาน override (SQLite)
    ใช้แสดงในหน้า Settings + ระบุว่าค่าใดถูกปรับแล้ว
    """
    overrides = db.get_all_region_thresholds()
    items = []
    for region, base in ai.REGIONAL_THRESHOLDS.items():
        ov = overrides.get(region)
        effective = ai.get_regional_threshold(region, ov)
        items.append({
            "region": region,
            "name": base.get("name", region),
            "defaults": {k: v for k, v in base.items() if k != "name"},
            "override": ov or {},
            "effective": {k: v for k, v in effective.items() if k != "name"},
        })
    return jsonify({"ok": True, "items": items})


@app.post("/api/thresholds")
def api_save_thresholds():
    """
    บันทึกเกณฑ์เฉพาะถิ่นที่ปรับ {region, values:{RH_min,WS_min,WS_max,KI_min,KI_max}}
    ตรวจ region/คีย์/ช่วงค่า ก่อนบันทึกลง SQLite (กันค่าเพี้ยน/injection)
    """
    data = request.get_json(silent=True) or {}
    region = (data.get("region") or "").strip()
    values = data.get("values") or {}
    if region not in VALID_REGIONS:
        return _bad(f"ไม่รองรับพื้นที่ {region}")
    if not isinstance(values, dict):
        return _bad("values ต้องเป็น object")

    cleaned = {}
    for k, v in values.items():
        if k not in THRESHOLD_BOUNDS:
            continue
        if v is None or v == "":
            continue
        try:
            fv = float(v)
        except (TypeError, ValueError):
            return _bad(f"ค่า {k} ต้องเป็นตัวเลข")
        lo, hi = THRESHOLD_BOUNDS[k]
        if not (lo <= fv <= hi):
                return _bad(f"ค่า {k} ต้องอยู่ในช่วง {lo}–{hi}")
        cleaned[k] = fv

    db.save_region_threshold(region, cleaned)
    return jsonify({"ok": True, "region": region, "saved": cleaned})


@app.get("/api/role_report")
def api_role_report():
    """
    GET /api/role_report?role=<role>
    สร้างรายงานเฉพาะกลุ่มจากข้อมูล last_upload/last_analysis
    ไม่ต้องดึงข้อมูลใหม่ — ใช้ผลที่ cache ไว้แล้ว (FR-AI-Panel)
    คืน RoleReport dict รวม sections / action_items / cautions
    """
    role = (request.args.get("role") or "").strip().lower()
    if not role:
        role = session.get("role") or "rainmaking"
    if role not in VALID_ROLES:
        return _bad(f"role ไม่ถูกต้อง (เลือก: {', '.join(sorted(VALID_ROLES))})")

    # ดึงข้อมูลล่าสุดจาก DB
    result = db.get_last_upload()
    if not result:
        return _bad("ยังไม่มีข้อมูลที่วิเคราะห์ไว้ — กด วิเคราะห์ ก่อน", code=404)

    indices  = result.get("indices") or {}
    ai_r     = result.get("ai")        or ai.assess_rain_chance(indices)
    rm_r     = result.get("rainmaking") or ai.assess_rainmaking(indices)

    report = interp.generate_role_report(indices, ai_r, rm_r, role)
    report["_meta"] = result.get("_meta", {})
    return jsonify({"ok": True, **report})


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
