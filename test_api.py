# -*- coding: utf-8 -*-
"""ทดสอบ Flask API แบบ offline ด้วย test client (Wyoming ถูกบล็อกใน sandbox)"""
import json
from app import app

# ตัวอย่างตาราง text-list รูปแบบเดียวกับ Wyoming (สร้างขึ้นเพื่อทดสอบ parse/compute/ai)
HEADING = "48453 Bangkok Observations at 00Z 01 Dec 2025"
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

client = app.test_client()
results = {}

# 1) /api/stations
r = client.get("/api/stations")
results["stations"] = (r.status_code, r.get_json()["ok"], len(r.get_json()["stations"]))

# 2) /api/login (valid + invalid)
r = client.post("/api/login", json={"role": "pilot"})
results["login_ok"] = (r.status_code, r.get_json())
r = client.post("/api/login", json={"role": "hacker"})
results["login_bad"] = (r.status_code, r.get_json()["ok"])

# 3) /api/upload (วิเคราะห์ตัวอย่าง + regional)
r = client.post("/api/upload?region=tung_kula", data=SAMPLE.encode("utf-8"),
                content_type="text/plain")
j = r.get_json()
results["upload"] = (r.status_code, j["ok"])
if j["ok"]:
    results["indices"] = j["indices"]
    results["WS_repr"] = j["indices"].get("WS_repr")
    results["ai_level"] = (j["ai"]["level"], j["ai"]["score"])
    results["rainmaking"] = j["rainmaking"]["technique"]
    results["regional"] = (j["regional"]["region"], j["regional"]["passed"])

# 4) /api/upload เนื้อหาว่าง -> 400
r = client.post("/api/upload", data=b"", content_type="text/plain")
results["upload_empty"] = r.status_code

# 5) /api/upload ไฟล์ผิดรูปแบบ -> 422
r = client.post("/api/upload", data=b"hello not a sounding", content_type="text/plain")
results["upload_bad"] = r.status_code

# 6) /api/sounding validation (ไม่เรียกเน็ตจริงเพราะ validate ก่อน)
results["snd_bad_station"] = client.get("/api/sounding?station=abc&date=2025-12-01&hour=0").status_code
results["snd_bad_date"] = client.get("/api/sounding?station=48453&date=2025/12/01&hour=0").status_code
results["snd_bad_hour"] = client.get("/api/sounding?station=48453&date=2025-12-01&hour=3").status_code

# 7) /api/history (ว่างได้)
r = client.get("/api/history?station=48453&year=2568")  # ส่ง พ.ศ. -> แปลงเป็น ค.ศ.
results["history"] = (r.status_code, r.get_json()["ok"])

# 8) /api/dam_inflow
r = client.get("/api/dam_inflow?C=0.6&I=25&A=150")
results["dam_inflow"] = (r.status_code, r.get_json().get("Q_m3s"))

# 9) 404
results["notfound"] = client.get("/api/nope").status_code

print(json.dumps(results, ensure_ascii=False, indent=2))
