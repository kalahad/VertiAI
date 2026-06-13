# -*- coding: utf-8 -*-
"""
VertiAI — Sounding Interpreter (Session 10)
Rule-based role-specific report engine สำหรับ AI Panel
ไม่เรียก AI API ภายนอก — ใช้ composite rules จาก indices ที่คำนวณแล้ว

รองรับ 8 บทบาท: rainmaking, meteorologist, researcher,
                farmer, factory, tourist, pilot, general

คืน RoleReport dict สำหรับแต่ละบทบาท:
{
  role, role_label_th, headline, level,       # สรุประดับ
  sections: [{ title, items:[str], level }],  # รายละเอียดแต่ละหัวข้อ
  action_items: [str],                        # สิ่งที่ต้องทำ
  cautions: [str],                            # ข้อควรระวัง
  metadata: {score, timestamp}
}
"""

from datetime import datetime

# ─────────────────────────────────────────────────────────────
# ตัวช่วย: แปลงค่าดิบเป็นข้อความสรุป
# ─────────────────────────────────────────────────────────────

def _lvl3(val, good_thr, warn_thr, higher_is_better=True):
    """คืน 'good' / 'warn' / 'bad' จากค่าและเกณฑ์ 2 ขั้น"""
    if val is None:
        return "neutral"
    if higher_is_better:
        return "good" if val >= good_thr else ("warn" if val >= warn_thr else "bad")
    else:
        return "good" if val <= good_thr else ("warn" if val <= warn_thr else "bad")


def _cape_text(cape):
    if cape is None:
        return "ไม่มีข้อมูล CAPE"
    if cape >= 2500:
        return f"CAPE {cape:.0f} J/kg — ไม่เสถียรรุนแรง (Very Unstable) โอกาสพายุฝนฟ้าคะนองสูงมาก"
    if cape >= 1000:
        return f"CAPE {cape:.0f} J/kg — ไม่เสถียร (Unstable) เหมาะต่อการก่อตัวของฝน"
    if cape >= 500:
        return f"CAPE {cape:.0f} J/kg — ไม่เสถียรปานกลาง (Marginally Unstable)"
    return f"CAPE {cape:.0f} J/kg — บรรยากาศค่อนข้างเสถียร โอกาสฝนต่ำ"


def _cin_text(cin):
    if cin is None:
        return "ไม่มีข้อมูล CIN"
    if -20 <= cin <= 0:
        return f"CIN {cin:.0f} J/kg — ชั้นยับยั้งบางมาก ฝนปะทุได้ง่าย"
    if -50 <= cin < -20:
        return f"CIN {cin:.0f} J/kg — ชั้นยับยั้งอยู่ในเกณฑ์ (ต้องมีแรงกระตุ้น)"
    if -100 <= cin < -50:
        return f"CIN {cin:.0f} J/kg — ชั้นยับยั้งค่อนข้างแข็งแรง"
    return f"CIN {cin:.0f} J/kg — ชั้นยับยั้งแข็งแรงมาก ฝนปะทุยาก"


def _pwat_text(pwat):
    if pwat is None:
        return "ไม่มีข้อมูล PWAT"
    if pwat >= 55:
        return f"PWAT {pwat:.0f} mm — ความชื้นสูงมาก (Saturated Column)"
    if pwat >= 40:
        return f"PWAT {pwat:.0f} mm — ความชื้นเพียงพอสำหรับฝน"
    if pwat >= 25:
        return f"PWAT {pwat:.0f} mm — ความชื้นปานกลาง"
    return f"PWAT {pwat:.0f} mm — ความชื้นต่ำ บรรยากาศแห้ง"


def _ki_text(ki):
    if ki is None:
        return "ไม่มีข้อมูล K-Index"
    if ki >= 40:
        return f"K-Index {ki:.1f} — ความเสี่ยงพายุฝนฟ้าคะนองสูงมาก"
    if ki >= 35:
        return f"K-Index {ki:.1f} — ศักยภาพพายุสูง เหมาะต่อการทำฝนหลวง"
    if ki >= 25:
        return f"K-Index {ki:.1f} — ศักยภาพพายุปานกลาง"
    return f"K-Index {ki:.1f} — ศักยภาพพายุต่ำ"


def _li_text(li):
    if li is None:
        return "ไม่มีข้อมูล Lifted Index"
    if li <= -6:
        return f"Lifted Index {li:.1f}°C — ไม่เสถียรรุนแรงมาก"
    if li <= -2:
        return f"Lifted Index {li:.1f}°C — ไม่เสถียร (เกณฑ์ทำฝน ≤ −2)"
    if li <= 2:
        return f"Lifted Index {li:.1f}°C — ใกล้เป็นกลาง"
    return f"Lifted Index {li:.1f}°C — บรรยากาศเสถียร"


def _freezing_text(f0, label="0°C"):
    if f0 is None:
        return f"ไม่พบระดับเยือกแข็ง {label}"
    h = f0.get("height_m")
    p = f0.get("pressure_hPa") or f0.get("pressure_hpa")
    if h and p:
        return f"ระดับเยือกแข็ง {label}: {h:.0f} m ({p:.0f} hPa)"
    if h:
        return f"ระดับเยือกแข็ง {label}: {h:.0f} m"
    return f"ระดับเยือกแข็ง {label}: {p:.0f} hPa"


def _cloud_text(lcl, lfc, el):
    parts = []
    if lcl:
        parts.append(f"ฐานเมฆ (LCL) {lcl:.0f} hPa")
    if lfc:
        parts.append(f"ระดับลอยตัวอิสระ (LFC) {lfc:.0f} hPa")
    if el:
        parts.append(f"ยอดเมฆ (EL) {el:.0f} hPa")
    return " · ".join(parts) if parts else "ไม่พบโครงสร้างเมฆที่ชัดเจน"


# ─────────────────────────────────────────────────────────────
# Template 1: เจ้าหน้าที่ฝนหลวง (rainmaking)
# ─────────────────────────────────────────────────────────────

def _report_rainmaking(idx, ai_result, rm_result):
    score = ai_result.get("score", 0)
    level = "go" if score >= 60 else ("caution" if score >= 35 else "nogo")
    headline_map = {
        "go":      f"ปฏิบัติการได้ (AI Score {score}/100) — บรรยากาศเอื้ออำนวย",
        "caution": f"ระวัง (AI Score {score}/100) — บางปัจจัยยังไม่เพียงพอ",
        "nogo":    f"ยังไม่ควรปฏิบัติการ (AI Score {score}/100) — บรรยากาศไม่เสถียรพอ",
    }

    cape = idx.get("CAPE")
    cin  = idx.get("CIN")
    pwat = idx.get("PWAT")
    ki   = idx.get("K_INDEX")
    lcl  = idx.get("LCL_p")
    lfc  = idx.get("LFC_p")
    el   = idx.get("EL_p")
    f0   = idx.get("FREEZING_0C")
    fm10 = idx.get("FREEZING_NEG10C") or idx.get("FREEZING_-10C")
    shear = idx.get("SHEAR_SFC6KM_KT")

    # ─ section 1: สถานะบรรยากาศ
    atm = [
        _cape_text(cape),
        _cin_text(cin),
        _pwat_text(pwat),
        _ki_text(ki),
    ]

    # ─ section 2: โครงสร้างเมฆ + ระดับเยือกแข็ง
    cloud = [_cloud_text(lcl, lfc, el)]
    if f0:
        cloud.append(_freezing_text(f0, "0°C"))
    if fm10:
        cloud.append(_freezing_text(fm10, "−10°C"))
    else:
        cloud.append("ไม่พบชั้นเย็นยวดยิ่ง (−10°C) — อาจเป็นเมฆอุ่นล้วน")

    # ─ section 3: เทคนิคและสารเพาะ
    technique = rm_result.get("technique", "ยังไม่สามารถระบุ")
    note      = rm_result.get("note", "")
    chem      = rm_result.get("chemical", "NaCl")
    tech_items = [
        f"เทคนิคที่แนะนำ: {technique}",
        note,
        f"สารเพาะฝนที่เหมาะสม: {chem}" if chem != "NaCl" or "เมฆอุ่น" in technique else
        "สารเพาะฝน: เกลือโซเดียมคลอไรด์ (NaCl) — Collision-Coalescence",
    ]
    tech_items = [x for x in tech_items if x]

    # ─ section 4: ความปลอดภัยการบิน
    safety_items = []
    if lcl:
        safety_items.append(f"เพดานบินอ้างอิง (LCL): {lcl:.0f} hPa")
    if f0:
        p0 = f0.get("pressure_hPa") or f0.get("pressure_hpa")
        if p0:
            safety_items.append(f"ระวังน้ำแข็งสะสม: เหนือ {p0:.0f} hPa ({f0.get('height_m',0):.0f} m)")
    if shear is not None:
        tag = "เหมาะสม" if shear <= 25 else ("ระวัง" if shear <= 40 else "อันตราย")
        safety_items.append(f"Wind Shear SFC–6km: {shear:.0f} kt ({tag})")
    if not safety_items:
        safety_items.append("ตรวจสอบ Wind Shear จาก Hodograph ก่อนปฏิบัติการ")

    # ─ action items + cautions
    actions = []
    cautions = []

    if level == "go":
        actions.append("เตรียมอากาศยานและสารเพาะตาม Checklist")
        actions.append(f"ปฏิบัติการระยะเมฆ LCL–EL ({lcl:.0f}–{el:.0f} hPa)" if lcl and el else "กำหนดระยะปฏิบัติการจาก LCL–EL")
        actions.append("ติดตาม Radar/Sounding รอบถัดไปทุก 6 ชม.")
    elif level == "caution":
        actions.append("รอติดตามสภาพอากาศอีก 3–6 ชม. ก่อนตัดสินใจ")
        actions.append("ตรวจ CAPE/CIN ใน Sounding ถัดไป")
    else:
        actions.append("งดปฏิบัติการ — รอรอบ Sounding ถัดไป (06Z/12Z)")

    if cape is not None and cape > 2500:
        cautions.append("CAPE สูงมาก — เสี่ยงพายุรุนแรง ระวัง Thunderstorm ขนาดใหญ่")
    if cin is not None and cin < -100:
        cautions.append("CIN แข็งมาก — ฝนอาจไม่ปะทุแม้ CAPE สูง")
    if shear is not None and shear > 40:
        cautions.append(f"Wind Shear สูง {shear:.0f} kt — เสี่ยงต่อความปลอดภัยการบิน")

    sections = [
        {"title": "สถานะบรรยากาศ",         "items": atm,        "level": _lvl3(score, 60, 35)},
        {"title": "โครงสร้างเมฆ",           "items": cloud,      "level": "neutral"},
        {"title": "เทคนิคและสารเพาะฝน",    "items": tech_items,  "level": "neutral"},
        {"title": "ความปลอดภัยการบิน",      "items": safety_items,"level": "warn" if shear and shear > 40 else "good"},
    ]

    return {
        "role": "rainmaking",
        "role_label_th": "เจ้าหน้าที่ฝนหลวง",
        "headline": headline_map[level],
        "level": level,
        "sections": sections,
        "action_items": actions,
        "cautions": cautions,
        "metadata": {"score": score, "timestamp": datetime.utcnow().isoformat()},
    }


# ─────────────────────────────────────────────────────────────
# Template 2: นักอุตุนิยมวิทยา (meteorologist)
# ─────────────────────────────────────────────────────────────

def _report_meteorologist(idx, ai_result, rm_result):
    score = ai_result.get("score", 0)
    cape  = idx.get("CAPE")
    cin   = idx.get("CIN")
    li    = idx.get("LI")
    pwat  = idx.get("PWAT")
    ki    = idx.get("K_INDEX")
    lcl   = idx.get("LCL_p")
    lfc   = idx.get("LFC_p")
    el    = idx.get("EL_p")
    f0    = idx.get("FREEZING_0C")
    shear = idx.get("SHEAR_SFC6KM_KT")
    rh700 = idx.get("RH_700")

    # ─ stability analysis
    stability = []
    stability.append(_cape_text(cape))
    stability.append(_cin_text(cin))
    stability.append(_li_text(li))
    if rh700 is not None:
        stability.append(f"RH @700 hPa: {rh700:.0f}% — {'ชื้น' if rh700 > 60 else 'แห้ง'}")

    # ─ thermodynamic profile
    thermo = [
        _pwat_text(pwat),
        _ki_text(ki),
        _cloud_text(lcl, lfc, el),
    ]
    if f0:
        thermo.append(_freezing_text(f0, "0°C"))

    # ─ dynamic analysis
    dynamic = []
    if shear is not None:
        dynamic.append(f"Wind Shear (SFC–6km): {shear:.0f} kt")
        if shear >= 40:
            dynamic.append("→ Supercell/Multi-cell storm เป็นไปได้")
        elif shear >= 20:
            dynamic.append("→ Organized convection เป็นไปได้")
        else:
            dynamic.append("→ Convection แบบแยกส่วน (Ordinary Cell)")
    else:
        dynamic.append("ไม่มีข้อมูล Wind Shear")

    # ─ forecast summary
    storm_prob = "สูงมาก" if score >= 70 else ("สูง" if score >= 60 else ("ปานกลาง" if score >= 35 else "ต่ำ"))
    forecast = [
        f"โอกาสเกิดฝนฟ้าคะนอง: {storm_prob} (คะแนน AI {score}/100)",
        f"สรุป: {ai_result.get('summary_th', '')}",
    ]
    reasons_pass = [r for r in ai_result.get("reasons", []) if r.get("passed")]
    reasons_fail = [r for r in ai_result.get("reasons", []) if not r.get("passed")]
    if reasons_pass:
        forecast.append("ผ่านเกณฑ์: " + ", ".join(r["index"] for r in reasons_pass))
    if reasons_fail:
        forecast.append("ไม่ผ่านเกณฑ์: " + ", ".join(r["index"] for r in reasons_fail))

    actions = [
        "ออก Terminal Aerodrome Forecast (TAF) ระดับ Moderate–Severe" if score >= 60 else
        "ออกคำเตือนอากาศเลวร้าย (SIGMET/AIRMET) หากศักยภาพสูงขึ้น",
        "ติดตาม Sounding ทุก 6 ชม. และ Radar ต่อเนื่อง",
        "ประสานกรมอุตุนิยมวิทยา/RMU หากพบ Mesoscale Convective System",
    ]
    cautions = []
    if cape is not None and cape > 2000:
        cautions.append("CAPE สูงมาก — เตรียมประกาศเตือนภัยระดับสูง")
    if ki is not None and ki > 40:
        cautions.append("K-Index สูงมาก — ความเสี่ยงพายุฝนฟ้าคะนองรุนแรงมาก")

    return {
        "role": "meteorologist",
        "role_label_th": "นักอุตุนิยมวิทยา",
        "headline": f"ผลวิเคราะห์บรรยากาศ — คะแนน {score}/100 (โอกาสฝนฟ้าคะนอง: {storm_prob})",
        "level": "good" if score >= 60 else ("warn" if score >= 35 else "bad"),
        "sections": [
            {"title": "เสถียรภาพ (Stability)",          "items": stability, "level": _lvl3(score, 60, 35)},
            {"title": "อุณหพลศาสตร์ (Thermodynamics)",  "items": thermo,    "level": "neutral"},
            {"title": "พลศาสตร์ (Dynamics / Shear)",    "items": dynamic,   "level": "warn" if shear and shear > 35 else "neutral"},
            {"title": "พยากรณ์สรุป",                    "items": forecast,  "level": _lvl3(score, 60, 35)},
        ],
        "action_items": actions,
        "cautions": cautions,
        "metadata": {"score": score, "timestamp": datetime.utcnow().isoformat()},
    }


# ─────────────────────────────────────────────────────────────
# Template 3: นักวิจัย (researcher)
# ─────────────────────────────────────────────────────────────

def _report_researcher(idx, ai_result, rm_result):
    score = ai_result.get("score", 0)

    # ─ full indices dump with academic labels
    index_rows = []
    fields = [
        ("CAPE",           "CAPE",           "J/kg",  "Convective Available Potential Energy"),
        ("CIN",            "CIN",            "J/kg",  "Convective INhibition"),
        ("LI",             "Lifted Index",   "°C",    "Stability index (surface parcel lifted to 500 hPa)"),
        ("PWAT",           "PWAT",           "mm",    "Precipitable Water (column integral)"),
        ("K_INDEX",        "K-Index",        "°C",    "K = T850 − T500 + Td850 − (T700 − Td700)"),
        ("LCL_p",          "LCL",            "hPa",   "Lifting Condensation Level"),
        ("LFC_p",          "LFC",            "hPa",   "Level of Free Convection"),
        ("EL_p",           "EL",             "hPa",   "Equilibrium Level (cloud top proxy)"),
        ("RH_700",         "RH @700",        "%",     "Relative Humidity mid-troposphere"),
        ("SHEAR_SFC6KM_KT","Wind Shear 0–6km","kt",  "Deep-layer shear (storm organisation)"),
    ]
    for key, label, unit, desc in fields:
        v = idx.get(key)
        if key == "FREEZING_0C":
            continue
        val_str = f"{v:.2f}" if isinstance(v, (int, float)) and v is not None else "N/A"
        index_rows.append(f"{label} = {val_str} {unit}  [{desc}]")

    f0   = idx.get("FREEZING_0C")
    fm10 = idx.get("FREEZING_NEG10C") or idx.get("FREEZING_-10C")
    if f0:
        index_rows.append(_freezing_text(f0, "0°C") + "  [Ice crystal / mixed-phase boundary]")
    if fm10:
        index_rows.append(_freezing_text(fm10, "−10°C") + "  [AgI seeding reference level]")

    # ─ classification (convective mode)
    cape  = idx.get("CAPE")
    shear = idx.get("SHEAR_SFC6KM_KT")
    mode  = []
    if cape is not None and shear is not None:
        if cape > 1000 and shear > 40:
            mode.append("Convective mode: Supercell / Severe MCS (CAPE↑ + Shear↑)")
        elif cape > 1000 and shear > 20:
            mode.append("Convective mode: Organized Multicell / Squall Line")
        elif cape > 500:
            mode.append("Convective mode: Ordinary Cell (Pulse) — weak shear")
        else:
            mode.append("Convective mode: Stratiform / weak convection")
    else:
        mode.append("Convective mode: ไม่สามารถระบุได้ (ข้อมูลไม่ครบ)")

    # Bergeron–Findeisen potential
    if f0 and fm10:
        mode.append("Bergeron–Findeisen process: เป็นไปได้ — มีทั้งระดับ 0°C และ −10°C")
    elif f0:
        mode.append("Warm-rain (Collision-Coalescence) dominant — ไม่พบชั้น −10°C")

    # ─ data quality notes
    reasons = ai_result.get("reasons", [])
    missing = [r["index"] for r in reasons if r.get("value") is None]
    dq = [f"ดัชนีที่ขาดหายไป: {', '.join(missing)}"] if missing else ["ดัชนีครบถ้วน"]

    actions = [
        "บันทึกผลลงฐานข้อมูลวิจัย (VertiAI DB / Export JSON)",
        "เทียบกับ radiosonde profile จาก TMD ก่อนนำไปวิเคราะห์ต่อ",
        "พิจารณา uncertainty: Parcel path สมมติ surface-based, อาจต้องเทียบ ML/MU CAPE",
    ]
    cautions = [
        "ค่าจาก University of Wyoming Archive — ตรวจ QC flag ก่อนใช้ในงานวิจัย",
        "Wind profile ใช้ geopotential height — ตรวจสอบ surface wind reference",
    ]

    return {
        "role": "researcher",
        "role_label_th": "นักวิจัย",
        "headline": f"ผลวิเคราะห์เต็มรูปแบบ (AI Score {score}/100) — สำหรับงานวิจัย",
        "level": "neutral",
        "sections": [
            {"title": "ดัชนีครบชุด (Full Index Table)",     "items": index_rows, "level": "neutral"},
            {"title": "Convective Mode Classification",       "items": mode,       "level": "neutral"},
            {"title": "Data Quality Notes",                   "items": dq,         "level": "neutral"},
        ],
        "action_items": actions,
        "cautions": cautions,
        "metadata": {"score": score, "timestamp": datetime.utcnow().isoformat()},
    }


# ─────────────────────────────────────────────────────────────
# Template 4: เกษตรกร (farmer)
# ─────────────────────────────────────────────────────────────

def _report_farmer(idx, ai_result, rm_result):
    score = ai_result.get("score", 0)
    cape  = idx.get("CAPE")
    pwat  = idx.get("PWAT")
    ki    = idx.get("K_INDEX")

    rain_chance = "สูง" if score >= 60 else ("ปานกลาง" if score >= 35 else "ต่ำ")
    rain_level  = "good" if score >= 60 else ("warn" if score >= 35 else "bad")

    # ─ rain outlook
    outlook = [
        f"โอกาสฝนตกวันนี้: {rain_chance} ({score}/100 คะแนน)",
        _pwat_text(pwat),
        _ki_text(ki),
    ]
    if cape is not None:
        if cape >= 1000:
            outlook.append("บรรยากาศไม่เสถียร — ฝนอาจตกหนักในช่วงบ่าย-เย็น")
        elif cape >= 500:
            outlook.append("บรรยากาศไม่เสถียรเล็กน้อย — ฝนเป็นบางพื้นที่")
        else:
            outlook.append("บรรยากาศเสถียร — ฝนน้อยหรือไม่มีฝน")

    # ─ crop advice
    crops = []
    if score >= 60:
        crops.append("โอกาสฝนสูง — เตรียมระบายน้ำในแปลง ป้องกันน้ำท่วมแฉะ")
        crops.append("ชะลอการใส่ปุ๋ยพื้นผิว — ฝนอาจชะล้างก่อนดูดซึม")
        crops.append("ตรวจความแข็งแรงค้ำยันต้นไม้ผล หากลมกระโชก")
    elif score >= 35:
        crops.append("โอกาสฝนปานกลาง — เตรียมน้ำสำรองไว้บ้าง")
        crops.append("ติดตามพยากรณ์อีก 6–12 ชม. ก่อนตัดสินใจรดน้ำ")
    else:
        crops.append("ฝนน้อย — เตรียมระบบชลประทาน/รดน้ำตามปกติ")
        crops.append("อากาศร้อนแห้ง — ระวังโรคพืชจากความชื้นต่ำ")

    actions = crops[:]
    actions.append("ดูพยากรณ์อากาศรายวันจากกรมอุตุนิยมวิทยาประกอบ")

    cautions = []
    if cape is not None and cape > 2000:
        cautions.append("ระวังพายุฝนฟ้าคะนองรุนแรง — หลีกเลี่ยงกลางแจ้งช่วงบ่าย")

    return {
        "role": "farmer",
        "role_label_th": "เกษตรกร",
        "headline": f"พยากรณ์ฝนสำหรับเกษตรกร — โอกาสฝน{rain_chance}วันนี้",
        "level": rain_level,
        "sections": [
            {"title": "พยากรณ์ฝนวันนี้",      "items": outlook, "level": rain_level},
            {"title": "คำแนะนำการเกษตร",       "items": crops,   "level": "neutral"},
        ],
        "action_items": actions,
        "cautions": cautions,
        "metadata": {"score": score, "timestamp": datetime.utcnow().isoformat()},
    }


# ─────────────────────────────────────────────────────────────
# Template 5: นักท่องเที่ยว (tourist)
# ─────────────────────────────────────────────────────────────

def _report_tourist(idx, ai_result, rm_result):
    score = ai_result.get("score", 0)
    cape  = idx.get("CAPE", 0) or 0
    pwat  = idx.get("PWAT", 30) or 30
    ki    = idx.get("K_INDEX", 20) or 20

    # คะแนนท่องเที่ยว (ยิ่งฝนมาก คะแนนท่องเที่ยวยิ่งต่ำ)
    t_score = max(10, 100 - score)
    t_level = "good" if t_score >= 70 else ("warn" if t_score >= 45 else "bad")

    headline_map = {
        "good": f"สภาพอากาศดีเยี่ยม — เหมาะท่องเที่ยวกลางแจ้ง ({t_score}/100)",
        "warn": f"ควรระวัง — มีโอกาสฝน เตรียมร่มหรือเสื้อกันฝน ({t_score}/100)",
        "bad":  f"ไม่แนะนำกิจกรรมกลางแจ้ง — โอกาสฝนฟ้าคะนองสูง ({t_score}/100)",
    }

    weather = [
        f"ดัชนีท่องเที่ยว: {t_score}/100",
        _pwat_text(pwat),
    ]
    if cape >= 1000:
        weather.append("บรรยากาศไม่เสถียร — ฝนอาจตกฉับพลันช่วงบ่าย")
    elif cape >= 500:
        weather.append("โอกาสฝนบางพื้นที่ช่วงบ่าย")
    else:
        weather.append("ท้องฟ้าค่อนข้างแจ่มใส")

    activities = []
    if t_score >= 70:
        activities += ["ชายหาด / ว่ายน้ำ: เหมาะมาก", "เดินป่า / ไต่เขา: เหมาะ",
                       "ปั่นจักรยาน: เหมาะ", "ถ่ายภาพกลางแจ้ง: เหมาะมาก"]
    elif t_score >= 45:
        activities += ["ท่องเที่ยวในร่ม/พิพิธภัณฑ์: เหมาะ",
                       "ชายหาด: ระวัง — พกร่มไว้",
                       "เดินป่าช่วงเช้า: ยังได้ หลีกเลี่ยงตอนบ่าย"]
    else:
        activities += ["ท่องเที่ยวในร่ม: แนะนำ", "หลีกเลี่ยงกิจกรรมกลางแจ้ง",
                       "กิจกรรมทางน้ำ: ไม่แนะนำ"]

    actions = [
        "ตรวจพยากรณ์อากาศรายชั่วโมงก่อนออกเดินทาง",
        "พกร่มหรือเสื้อกันฝนไว้เสมอในช่วงฤดูฝน",
    ]
    cautions = []
    if cape > 2000:
        cautions.append("ระวังพายุฝนฟ้าคะนองรุนแรง — หลีกเลี่ยงพื้นที่โล่ง/ยอดเขา")

    return {
        "role": "tourist",
        "role_label_th": "นักท่องเที่ยว",
        "headline": headline_map[t_level],
        "level": t_level,
        "sections": [
            {"title": "สภาพอากาศวันนี้",       "items": weather,     "level": t_level},
            {"title": "กิจกรรมที่แนะนำ",        "items": activities,  "level": t_level},
        ],
        "action_items": actions,
        "cautions": cautions,
        "metadata": {"score": t_score, "timestamp": datetime.utcnow().isoformat()},
    }


# ─────────────────────────────────────────────────────────────
# Template 6: โรงงานอุตสาหกรรม (factory)
# ─────────────────────────────────────────────────────────────

def _report_factory(idx, ai_result, rm_result):
    score = ai_result.get("score", 0)
    pwat  = idx.get("PWAT")
    ki    = idx.get("K_INDEX")
    lcl   = idx.get("LCL_p")
    cape  = idx.get("CAPE")
    ws    = idx.get("SURFACE_WIND_KT") or idx.get("WS_repr")

    # mixing layer (ฐานเมฆ LCL เป็น proxy)
    mixing = []
    if lcl:
        mixing.append(f"ฐานชั้นผสม (LCL): {lcl:.0f} hPa — {'ชั้นผสมต่ำ เสี่ยงสะสมมลพิษ' if lcl > 900 else 'ชั้นผสมปกติ'}")
    if ws is not None:
        mixing.append(f"ลมพื้นผิว: {ws:.0f} kt — {'ระบายได้ดี' if ws > 5 else 'ระบายต่ำ ระวังมลพิษสะสม'}")
    if pwat:
        mixing.append(_pwat_text(pwat))

    rain_risk = [
        f"โอกาสฝน: {'สูง — อาจกระทบการขนส่ง/กลางแจ้ง' if score >= 60 else 'ปานกลาง' if score >= 35 else 'ต่ำ'}",
        _ki_text(ki),
    ]

    safety = []
    if cape is not None and cape > 1000:
        safety.append("ระวังฟ้าผ่า — ตรวจ Lightning Protection System")
    if lcl and lcl > 900:
        safety.append("PM2.5 อาจสูงขึ้น — ตรวจ Stack emission และ Scrubber")
    if ws is not None and ws < 5:
        safety.append("ลมอ่อนมาก — กลิ่น/ฟูมโรงงานสะสมในพื้นที่ใกล้เคียง")

    if not safety:
        safety.append("สภาพอากาศปกติ — ระบบระบายอากาศทำงานได้ตามปกติ")

    actions = [
        "ตรวจสอบ Stack Emission Report ประจำวัน",
        "หากฝนตกหนัก: ตรวจ runoff จากพื้นที่จัดเก็บสารเคมี",
    ]
    cautions = []
    if cape and cape > 1500:
        cautions.append("ระวังฟ้าผ่าและลมกระโชกแรง — ตรวจสอบหลังคาและโครงสร้างชั่วคราว")

    return {
        "role": "factory",
        "role_label_th": "โรงงานอุตสาหกรรม",
        "headline": f"ประเมินสภาพอากาศโรงงาน — โอกาสฝน {'สูง' if score >= 60 else 'ปานกลาง' if score >= 35 else 'ต่ำ'}",
        "level": "warn" if score >= 35 else "good",
        "sections": [
            {"title": "ชั้นผสมและการระบาย",   "items": mixing,    "level": "neutral"},
            {"title": "ความเสี่ยงฝนและพายุ",   "items": rain_risk, "level": _lvl3(score, 60, 35)},
            {"title": "ความปลอดภัยโรงงาน",    "items": safety,    "level": "warn" if safety and "ระวัง" in safety[0] else "good"},
        ],
        "action_items": actions,
        "cautions": cautions,
        "metadata": {"score": score, "timestamp": datetime.utcnow().isoformat()},
    }


# ─────────────────────────────────────────────────────────────
# Template 7: ประชาชนทั่วไป (general)
# ─────────────────────────────────────────────────────────────

def _report_general(idx, ai_result, rm_result):
    score = ai_result.get("score", 0)
    cape  = idx.get("CAPE")
    pwat  = idx.get("PWAT")

    rain_chance = "สูง" if score >= 60 else ("ปานกลาง" if score >= 35 else "ต่ำ")
    level       = "good" if score >= 60 else ("warn" if score >= 35 else "bad")

    simple = [
        f"โอกาสฝน: {rain_chance}",
        _pwat_text(pwat),
    ]
    if cape is not None:
        if cape >= 1000:
            simple.append("ควรเตรียมร่มหรือหลีกเลี่ยงกิจกรรมกลางแจ้งช่วงบ่าย")
        else:
            simple.append("สภาพอากาศค่อนข้างปกติ")

    actions = [
        "ติดตามพยากรณ์อากาศจากช่องทางราชการ (กรมอุตุนิยมวิทยา / TNN Weather)",
        "พกร่มหรือเสื้อกันฝนในช่วงฤดูฝน",
    ]
    cautions = []
    if cape is not None and cape > 2000:
        cautions.append("ระวังพายุฝนฟ้าคะนองรุนแรง")

    return {
        "role": "general",
        "role_label_th": "ประชาชนทั่วไป",
        "headline": f"สรุปสภาพอากาศ — โอกาสฝน{rain_chance}วันนี้",
        "level": level,
        "sections": [
            {"title": "สรุปสภาพอากาศ", "items": simple, "level": level},
        ],
        "action_items": actions,
        "cautions": cautions,
        "metadata": {"score": score, "timestamp": datetime.utcnow().isoformat()},
    }


# ─────────────────────────────────────────────────────────────
# Template 8: นักบิน / การบิน (pilot)
# มุมมองความปลอดภัยการบิน: convection/CB, turbulence/shear,
# icing (ระดับเยือกแข็ง), ceiling/cloud tops, ลมพื้นผิว
# ─────────────────────────────────────────────────────────────

def _report_pilot(idx, ai_result, rm_result):
    score = ai_result.get("score", 0)
    cape  = idx.get("CAPE")
    ki    = idx.get("K_INDEX")
    li    = idx.get("LI")
    lcl   = idx.get("LCL_p")
    el    = idx.get("EL_p")
    f0    = idx.get("FREEZING_0C")
    shear = idx.get("SHEAR_SFC6KM_KT")
    ws    = idx.get("SURFACE_WIND_KT") or idx.get("WS_repr")
    pwat  = idx.get("PWAT")

    # ระดับอันตรายการบิน: convection มาก = อันตรายมาก (ตรงข้ามกับฝนหลวง)
    hazard = "bad" if score >= 60 else ("warn" if score >= 35 else "good")
    hazard_word = {"bad": "สูง", "warn": "ปานกลาง", "good": "ต่ำ"}[hazard]

    # ─ Convective hazard (CB / thunderstorm)
    convection = [
        f"ศักยภาพ Convection/CB: {hazard_word} (AI Score {score}/100)",
        _cape_text(cape),
        _ki_text(ki),
        _li_text(li),
    ]
    if el:
        convection.append(f"ยอดเมฆโดยประมาณ (EL): {el:.0f} hPa — ใช้ประเมินเพดาน CB tops")

    # ─ Turbulence & Wind Shear
    turbulence = []
    if shear is not None:
        turbulence.append(f"Wind Shear (SFC–6km): {shear:.0f} kt")
        if shear >= 40:
            turbulence.append("→ เสี่ยง Low-Level Wind Shear (LLWS) รุนแรง ระวังช่วง Approach/Departure")
        elif shear >= 20:
            turbulence.append("→ Wind Shear ปานกลาง อาจมี Turbulence ในชั้นล่าง")
        else:
            turbulence.append("→ Wind Shear ต่ำ สภาพการบินชั้นล่างค่อนข้างนิ่ง")
    else:
        turbulence.append("ไม่มีข้อมูล Wind Shear")
    if cape is not None and cape > 1500:
        turbulence.append("CAPE สูง — คาดมี Convective Turbulence ใกล้/ใต้ CB")

    # ─ Icing (ระดับเยือกแข็ง + ความชื้น)
    icing = []
    if f0:
        icing.append(_freezing_text(f0, "0°C"))
        h = f0.get("height_m")
        if h:
            icing.append(f"ชั้นเสี่ยงน้ำแข็งเกาะ (Airframe Icing) ประมาณ 0°C ถึง −20°C เหนือ {h:.0f} m หากบินในเมฆ")
    else:
        icing.append("ไม่พบระดับเยือกแข็ง — ประเมินความเสี่ยงน้ำแข็งเกาะไม่ได้")
    if pwat is not None and pwat >= 40:
        icing.append(_pwat_text(pwat) + " — เมฆหนา เพิ่มโอกาส Icing ในชั้นเย็น")

    # ─ Ceiling & Surface wind
    ceiling = []
    if lcl:
        ceiling.append(f"ฐานเมฆโดยประมาณ (LCL): {lcl:.0f} hPa — ใช้ประเมินเพดานบิน (Ceiling)")
    if ws is not None:
        ceiling.append(f"ลมพื้นผิว: {ws:.0f} kt — {'ระวัง Crosswind ขณะ Take-off/Landing' if ws >= 15 else 'ลมพื้นผิวอยู่ในเกณฑ์ปกติ'}")

    actions = [
        "ตรวจสอบ METAR/TAF และ SIGMET/AIRMET ของสนามบินต้นทาง–ปลายทางก่อนบิน",
        "วางแผนเส้นทางเลี่ยง CB cells และเผื่อเชื้อเพลิงสำรอง (Alternate/Holding)",
    ]
    if hazard == "bad":
        actions.append("พิจารณาเลื่อน/ปรับเวลาเที่ยวบินหากเส้นทางตัดผ่านแนวพายุ")

    cautions = []
    if score >= 60:
        cautions.append("ศักยภาพพายุฝนฟ้าคะนองสูง — เสี่ยง CB, ฟ้าผ่า, ลมเฉือนแรง และ Microburst")
    if shear is not None and shear >= 40:
        cautions.append("Wind Shear รุนแรง — ระวัง LLWS ในขั้น Approach/Departure")
    if f0 and pwat is not None and pwat >= 40:
        cautions.append("เสี่ยง Airframe Icing เมื่อบินในเมฆเหนือระดับเยือกแข็ง")

    return {
        "role": "pilot",
        "role_label_th": "นักบิน / การบิน",
        "headline": f"ประเมินความปลอดภัยการบิน — ระดับอันตรายจากสภาพอากาศ: {hazard_word} (AI Score {score}/100)",
        "level": hazard,
        "sections": [
            {"title": "อันตรายจาก Convection / CB", "items": convection, "level": hazard},
            {"title": "Turbulence และ Wind Shear",   "items": turbulence, "level": _lvl3(shear, 40, 20) if shear is not None else "neutral"},
            {"title": "ความเสี่ยงน้ำแข็งเกาะ (Icing)", "items": icing,      "level": "neutral"},
            {"title": "เพดานบินและลมพื้นผิว",          "items": ceiling,    "level": "neutral"},
        ],
        "action_items": actions,
        "cautions": cautions,
        "metadata": {"score": score, "timestamp": datetime.utcnow().isoformat()},
    }


# ─────────────────────────────────────────────────────────────
# Entry point หลัก
# ─────────────────────────────────────────────────────────────

_REPORT_FN = {
    "rainmaking":    _report_rainmaking,
    "meteorologist": _report_meteorologist,
    "researcher":    _report_researcher,
    "farmer":        _report_farmer,
    "tourist":       _report_tourist,
    "factory":       _report_factory,
    "pilot":         _report_pilot,
    "general":       _report_general,
}


def generate_role_report(indices, ai_result, rainmaking_result, role="rainmaking"):
    """
    สร้างรายงานเฉพาะกลุ่มจาก indices + ผล AI ที่คำนวณแล้ว
    คืน RoleReport dict
    """
    fn = _REPORT_FN.get(role, _report_general)
    return fn(indices, ai_result, rainmaking_result)


# ─────────────────────────────────────────────────────────────
# TEST (python -m core.sounding_interpreter)
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    from core.ai_rules import assess_rain_chance, assess_rainmaking

    sample_idx = {
        "CAPE": 1284, "CIN": -38, "LI": -3.2, "PWAT": 48.2,
        "K_INDEX": 36.4, "LCL_p": 920, "LFC_p": 700, "EL_p": 215,
        "RH_700": 68, "SHEAR_SFC6KM_KT": 28,
        "FREEZING_0C":  {"pressure_hPa": 560, "height_m": 4900},
        "FREEZING_NEG10C": {"pressure_hPa": 440, "height_m": 6700},
        "WS_repr": 12, "SURFACE_WIND_KT": 8,
    }
    ai_r  = assess_rain_chance(sample_idx)
    rm_r  = assess_rainmaking(sample_idx)

    for role in _REPORT_FN:
        report = generate_role_report(sample_idx, ai_r, rm_r, role)
        print(f"\n{'='*60}")
        print(f"ROLE: {role}  |  {report['headline']}")
        for s in report["sections"]:
            print(f"  [{s['title']}]")
            for item in s["items"][:2]:
                print(f"    · {item}")
        print(f"  Actions: {report['action_items'][0]}")
