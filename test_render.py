# -*- coding: utf-8 -*-
"""ทดสอบ render dashboard ด้วย headless chromium + seed cache (ไม่ต้องต่อเน็ต)"""
import threading, time, json
from app import app
from core import db, sounding as snd, ai_rules as ai

# --- seed cache ด้วยตัวอย่าง sounding (เลี่ยง Wyoming ที่ถูกบล็อก) ---
HEADING = "48453 Bangkok Observations at 00Z 02 Jun 2026"
SAMPLE = HEADING + """
-----------------------------------------------------------------------------
   PRES   HGHT   TEMP   DWPT   RELH   MIXR   DRCT   SKNT   THTA   THTE   THTV
    hPa     m      C      C      %    g/kg    deg   knot     K      K      K
-----------------------------------------------------------------------------
 1008.0     11   26.4   24.4     89  19.34    180      8  298.5  354.1  301.9
 1000.0     85   25.8   23.8     88  18.90    185     10  299.0  353.8  302.4
  925.0    770   22.0   20.5     91  17.10    200     14  302.5  352.0  305.5
  850.0   1500   18.0   16.0     88  14.20    210     16  305.5  348.0  308.1
  700.0   3170    9.0    6.0     81   8.50    220     18  311.0  337.0  312.6
  500.0   5890   -6.0   -9.0     78   3.80    240     22  320.0  333.5  320.8
  400.0   7590  -16.0  -20.0     70   1.90    250     26  327.0  334.0  327.4
  300.0   9690  -33.0  -42.0     45   0.45    260     34  335.0  337.5  335.1
  250.0  10960  -44.0  -55.0     35   0.15    265     40  340.0  341.0  340.0
  200.0  12420  -57.0  -68.0     28   0.04    270     45  346.0  346.5  346.0
"""
df = snd.parse_sounding(SAMPLE)
comp = snd.compute_indices(df, heading=HEADING)
idx = comp["indices"]
import numpy as np
low = [s for p_, s in zip(comp["profile"]["pressure"], comp["profile"]["speed"]) if p_ >= 700]
idx["WS_repr"] = round(float(np.mean(low)), 1)
result = {"heading": HEADING, "profile": comp["profile"], "indices": idx,
          "inversion_layers": comp["inversion_layers"], "pressure_height_map": comp["pressure_height_map"],
          "stable": comp["stable"], "ai": ai.assess_rain_chance(idx), "rainmaking": ai.assess_rainmaking(idx)}
key = db.make_key("48453", 2026, 6, 2, 0)
db.save_cache("48453", key, SAMPLE, result)
print("seeded cache:", key, "| CAPE", round(idx["CAPE"]), "| inversion layers", len(comp["inversion_layers"]))

# --- รัน Flask ใน thread ---
srv = threading.Thread(target=lambda: app.run(port=5055, use_reloader=False), daemon=True)
srv.start(); time.sleep(1.5)

# --- headless render ---
from playwright.sync_api import sync_playwright
errors = []
with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--disable-gpu"])
    pg = b.new_page()
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto("http://127.0.0.1:5055/", wait_until="networkidle")
    pg.select_option("#sel-station", "48453")
    pg.fill("#sel-date", "2026-06-02")
    pg.select_option("#sel-hour", "0")
    pg.select_option("#sel-region", "tung_kula")
    pg.click("#btn-analyze")
    pg.wait_for_timeout(2500)
    checks = pg.evaluate("""() => ({
        skewt_traces: (document.querySelector('#skewt .plot-container') ? window.Plotly.d3 ? 1 : 1 : 0),
        skewt_svg: document.querySelectorAll('#skewt svg').length,
        hodo_svg: document.querySelectorAll('#hodo svg').length,
        gauge_svg: document.querySelectorAll('#gauge svg').length,
        kpi_cards: document.querySelectorAll('#kpi-grid .kpi').length,
        reasons: document.querySelectorAll('#reasons .reason').length,
        ai_level: document.querySelector('#ai-level').textContent,
        rainmaking_visible: document.querySelector('#rainmaking').style.display,
        status: document.querySelector('#status').textContent,
    })""")
    pg.screenshot(path="/tmp/vertiai_dashboard.png", full_page=True)
    # ทดสอบ dark mode
    pg.click("#btn-theme"); pg.wait_for_timeout(800)
    pg.screenshot(path="/tmp/vertiai_dark.png", full_page=True)
    b.close()

print("CONSOLE ERRORS:", errors if errors else "none")
print(json.dumps(checks, ensure_ascii=False, indent=2))
