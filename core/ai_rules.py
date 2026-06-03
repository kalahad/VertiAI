# -*- coding: utf-8 -*-
"""
VertiAI - Rule-Based AI Module (Session 2)
ระบบ AI แบบกฎเกณฑ์ที่อธิบายได้ (Explainable / Rule-Based Weighted Scoring System)
อ้างอิงเกณฑ์ตาราง 2.1 (AI_PVW v1.5) และ FR-3 (PRD ver 1.00)
รับ dict 'indices' จาก core.sounding.compute_indices()  คืนผลภาษาไทยที่อ่านง่าย + ตัวเลขดิบ
"""

# ==================== เกณฑ์ฝนหลวงระดับชาติ (ตาราง 2.1 AI_PVW) ====================
# (index, ผ่านเมื่อ, น้ำหนักคะแนน) — รวมน้ำหนัก = 100
NATIONAL_RULES = {
    "CAPE":    {"label": "CAPE",    "unit": "J/kg", "pass": lambda v: v is not None and v >= 1000, "weight": 25},
    "CIN":     {"label": "CIN",     "unit": "J/kg", "pass": lambda v: v is not None and -50 <= v <= 0, "weight": 15},
    "LI":      {"label": "Lifted Index", "unit": "°C", "pass": lambda v: v is not None and v <= -2, "weight": 15},
    "PWAT":    {"label": "PWAT",    "unit": "mm",   "pass": lambda v: v is not None and v >= 40, "weight": 20},
    "K_INDEX": {"label": "K-Index", "unit": "°C",   "pass": lambda v: v is not None and v >= 35, "weight": 15},
    "LCL_p":   {"label": "LCL",     "unit": "hPa",  "pass": lambda v: v is not None and v <= 950, "weight": 4},
    "LFC_p":   {"label": "LFC",     "unit": "hPa",  "pass": lambda v: v is not None and v <= 750, "weight": 3},
    "EL_p":    {"label": "EL",      "unit": "hPa",  "pass": lambda v: v is not None and v <= 250, "weight": 3},
}


def assess_rain_chance(indices):
    """
    ประเมินโอกาสเกิดฝนแบบ Weighted Scoring (อธิบายได้)
    คืน {level, score, summary_th, reasons[]}
    - กฎฐาน FR-3: CAPE>1000 และ CIN>-50 และ RH@700>60% => 'โอกาสเกิดฝนสูง'
    """
    score = 0
    reasons = []
    for key, rule in NATIONAL_RULES.items():
        v = indices.get(key)
        passed = rule["pass"](v)
        if passed:
            score += rule["weight"]
        vtxt = "N/A" if v is None else f"{v:.1f} {rule['unit']}"
        reasons.append({
            "index": rule["label"],
            "value": v,
            "value_text": vtxt,
            "passed": passed,
            "weight": rule["weight"],
            "note": ("ผ่านเกณฑ์ฝนหลวง" if passed else "ยังไม่ถึงเกณฑ์"),
        })

    # กฎฐานหลักตาม FR-3 (มีน้ำหนักในการตัดสินระดับ)
    cape = indices.get("CAPE")
    cin = indices.get("CIN")
    rh700 = indices.get("RH_700")
    base_rule = (cape is not None and cape > 1000 and
                 cin is not None and cin > -50 and
                 rh700 is not None and rh700 > 60)

    # จัดระดับจากคะแนนรวม + กฎฐาน
    if base_rule and score >= 60:
        level, summary = "สูง", "โอกาสเกิดฝนสูง: บรรยากาศไม่เสถียร ความชื้นเพียงพอ เหมาะต่อการก่อตัวของเมฆฝน"
    elif score >= 60:
        level, summary = "สูง", "โอกาสเกิดฝนสูง: ดัชนีเสถียรภาพส่วนใหญ่ผ่านเกณฑ์"
    elif score >= 35:
        level, summary = "ปานกลาง", "โอกาสเกิดฝนปานกลาง: มีศักยภาพแต่บางปัจจัยยังไม่เอื้ออำนวย"
    else:
        level, summary = "ต่ำ", "โอกาสเกิดฝนต่ำ: บรรยากาศค่อนข้างเสถียรหรือความชื้นไม่เพียงพอ"

    if rh700 is not None:
        reasons.append({
            "index": "RH @700hPa", "value": rh700, "value_text": f"{rh700:.0f} %",
            "passed": rh700 > 60, "weight": 0,
            "note": "ความชื้นชั้นกลางเพียงพอ" if rh700 > 60 else "ความชื้นชั้นกลางไม่เพียงพอ",
        })

    return {"level": level, "score": int(score), "summary_th": summary, "reasons": reasons}


def assess_rainmaking(indices):
    """
    แนะนำเทคนิคฝนหลวง + เตือนความปลอดภัยแนวดิ่งสำหรับนักบิน
    คืน {technique, freezing_levels, safety, note}
    """
    fl0 = indices.get("FREEZING_0C")     # {pressure_hPa, height_m} หรือ None
    fl_m10 = indices.get("FREEZING_-10C")
    cape = indices.get("CAPE")

    # ตัดสินเทคนิค: ถ้ามีชั้นเย็นยวดยิ่ง (มีระดับ -10°C) และยอดเมฆพัฒนาสูง -> เมฆเย็น
    if fl_m10 is not None and cape is not None and cape >= 1000:
        technique = "เมฆเย็น (Cold Cloud / AgI)"
        note = ("เมฆพัฒนาสูงเหนือระดับเยือกแข็ง มีหยดน้ำเย็นยวดยิ่ง "
                "เหมาะใช้ซิลเวอร์ไอโอไดด์ (AgI) หรือน้ำแข็งแห้ง เร่งกระบวนการ Bergeron-Findeisen")
    elif fl0 is not None:
        technique = "เมฆอุ่น (Warm Cloud)"
        note = ("ฐานเมฆอยู่ในชั้นอุ่น เหมาะโปรยสารดูดความชื้น (เกลือ) เร่งการรวมตัวของหยดน้ำ "
                "ผ่านกระบวนการชนกันและรวมตัว (Collision-Coalescence)")
    else:
        technique = "ยังไม่เหมาะต่อการปฏิบัติการ"
        note = "ไม่พบโครงสร้างเมฆที่ชัดเจนหรือบรรยากาศเสถียรเกินไป"

    # ความปลอดภัยแนวดิ่งสำหรับนักบิน (เพดานบิน/ลมเฉือน)
    safety = {
        "LCL_hPa": indices.get("LCL_p"),
        "LFC_hPa": indices.get("LFC_p"),
        "freezing_0C": fl0,
        "freezing_-10C": fl_m10,
        "note_th": "ใช้ LCL/LFC เป็นแนวเพดานบินอ้างอิง และตรวจลมเฉือน (Wind Shear) จาก Hodograph ก่อนบิน",
    }

    return {
        "technique": technique,
        "freezing_levels": {"0C": fl0, "-10C": fl_m10},
        "safety": safety,
        "note": note,
    }


# ==================== เกณฑ์เฉพาะถิ่น (PRD/AI_PVW) ====================
# RH = ความชื้นสัมพัทธ์(%), WS = ความเร็วลม(นอต), KI = K-Index
REGIONAL_THRESHOLDS = {
    "tung_kula": {
        "name": "ทุ่งกุลาร้องไห้ (ภาคอีสาน)",
        "RH_min": 72.1, "WS_min": 6, "WS_max": 16, "KI_min": 34.8, "KI_max": 38.1,
    },
    "bang_lang": {
        "name": "เขื่อนบางลาง ยะลา (ภาคใต้)",
        "RH_min": 63.3, "WS_max": 15.9,
    },
    # ช่องเผื่อขยาย (ค่าตั้งต้นอิงเกณฑ์ชาติ ปรับได้ในหน้า Settings — Session 5)
    "korat":      {"name": "นครราชสีมา (ภาคอีสาน)", "RH_min": 60, "KI_min": 35},
    "sa_kaeo":    {"name": "สระแก้ว/ฉะเชิงเทรา (ภาคตะวันออก)", "RH_min": 60, "KI_min": 35},
    "to_daeng":   {"name": "ป่าพรุโต๊ะแดง นราธิวาส (ภาคใต้)", "RH_min": 63.3, "WS_max": 15.9},
}


def get_regional_threshold(region, override=None):
    """
    คืนค่าเกณฑ์ที่ใช้งานจริงของ region = ค่าตั้งต้นในโค้ด + override จากผู้ใช้ (ถ้ามี)
    override มาจาก Settings (บันทึกใน SQLite) จะทับเฉพาะคีย์ที่ส่งมา
    """
    base = REGIONAL_THRESHOLDS.get(region)
    if base is None:
        return None
    th = dict(base)
    if override:
        # ทับเฉพาะคีย์ตัวเลขเกณฑ์ (กันการเขียนทับ name โดยไม่ตั้งใจ)
        for k, v in override.items():
            if k in ("RH_min", "WS_min", "WS_max", "KI_min", "KI_max") and v is not None:
                th[k] = v
    return th


def apply_regional(indices, region, override=None):
    """
    ตรวจดัชนีกับเกณฑ์เฉพาะถิ่น คืนผ่าน/ไม่ผ่านพร้อมเหตุผลรายดัชนี
    ใช้ RH@700hPa เป็นตัวแทนความชื้น และความเร็วลมเฉลี่ยชั้นล่างเป็นตัวแทน WS
    override = ค่าเกณฑ์ที่ผู้ใช้ปรับในหน้า Settings (Session 5)
    """
    th = get_regional_threshold(region, override)
    if th is None:
        return {"ok": False, "error": f"ไม่พบเกณฑ์ของพื้นที่: {region}"}

    rh = indices.get("RH_700")
    ki = indices.get("K_INDEX")
    ws = indices.get("WS_repr")  # ความเร็วลมตัวแทน (เติมจาก app/profile ได้)

    checks = []
    if "RH_min" in th:
        ok = rh is not None and rh >= th["RH_min"]
        checks.append({"index": "RH", "ok": ok,
                       "detail": f"ต้องการ ≥ {th['RH_min']}% | วัดได้ {('N/A' if rh is None else f'{rh:.0f}%')}"})
    if "WS_min" in th or "WS_max" in th:
        lo, hi = th.get("WS_min", 0), th.get("WS_max", 999)
        ok = ws is not None and lo <= ws <= hi
        rng = f"{th.get('WS_min','')}-{th.get('WS_max','')}".strip("-")
        checks.append({"index": "Wind Speed", "ok": ok,
                       "detail": f"ต้องการ {rng} นอต | วัดได้ {('N/A' if ws is None else f'{ws:.1f} นอต')}"})
    if "KI_min" in th:
        lo, hi = th.get("KI_min"), th.get("KI_max", 999)
        ok = ki is not None and lo <= ki <= hi
        rng = f"{th.get('KI_min')}-{th.get('KI_max','')}".strip("-")
        checks.append({"index": "K-Index", "ok": ok,
                       "detail": f"ต้องการ {rng} | วัดได้ {('N/A' if ki is None else f'{ki:.1f}')}"})

    passed_all = all(c["ok"] for c in checks) if checks else False
    return {
        "ok": True,
        "region": th["name"],
        "passed": passed_all,
        "summary_th": ("เข้าเกณฑ์เหมาะสมทำฝนหลวงเฉพาะพื้นที่" if passed_all
                       else "ยังไม่เข้าเกณฑ์เฉพาะพื้นที่ครบทุกข้อ"),
        "checks": checks,
    }


# ==================== ประเมินน้ำไหลลงเขื่อน (Q = CIA) ====================
def estimate_dam_inflow(C, I, A):
    """
    สูตร Rational Method: Q = C * I * A
    C = สัมประสิทธิ์การไหลบ่า (0-1), I = ความเข้มฝน (mm/hr), A = พื้นที่รับน้ำ (ตร.กม.)
    คืนปริมาณน้ำไหลลงเขื่อนโดยประมาณ (ลบ.ม./วินาที)
    """
    # แปลงหน่วย: mm/hr * km^2 -> m^3/s  (ตัวคูณ 0.2778 ของ Rational Method แบบเมตริก)
    Q = C * I * A * 0.2778
    return {
        "Q_m3s": round(Q, 2),
        "inputs": {"C": C, "I_mm_hr": I, "A_km2": A},
        "note": "ประมาณการน้ำไหลลงเขื่อนเพื่อภารกิจเติมน้ำต้นทุน (Rational Method Q=CIA)",
    }


# ==================== TEST ====================
if __name__ == "__main__":
    import json
    # ค่าตัวอย่างจาก PRD/AI_PVW (สถานี 48453)
    sample = {
        "CAPE": 1284, "CIN": -38, "LI": -3.2, "PWAT": 48.2,
        "K_INDEX": 36.4, "LCL_p": 920, "LFC_p": 700, "EL_p": 215,
        "RH_700": 68,
        "FREEZING_0C": {"pressure_hPa": 560, "height_m": 4900},
        "FREEZING_-10C": {"pressure_hPa": 440, "height_m": 6700},
        "WS_repr": 12,
    }

    print("=== assess_rain_chance ===")
    print(json.dumps(assess_rain_chance(sample), indent=2, ensure_ascii=False))

    print("\n=== assess_rainmaking ===")
    print(json.dumps(assess_rainmaking(sample), indent=2, ensure_ascii=False))

    print("\n=== apply_regional: tung_kula ===")
    print(json.dumps(apply_regional(sample, "tung_kula"), indent=2, ensure_ascii=False))

    print("\n=== estimate_dam_inflow ===")
    print(json.dumps(estimate_dam_inflow(0.6, 25, 150), indent=2, ensure_ascii=False))
