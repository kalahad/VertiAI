# VertiAI — วิเคราะห์โครงสร้างบรรยากาศแนวดิ่งด้วย MetPy + AI เชิงกฎ

VertiAI เป็นเว็บแอปพลิเคชันสนับสนุนภารกิจ **ฝนหลวง** และการพยากรณ์ฝน โดยวิเคราะห์ข้อมูล
หยั่งอากาศแนวดิ่ง (radiosonde sounding) ด้วย [MetPy](https://unidata.github.io/MetPy/)
แล้วแสดงผลเป็น Skew-T Log-P, Hodograph, ดัชนีเสถียรภาพ (KPI) และการประเมินโอกาสฝน
แบบ **อธิบายเหตุผลได้** (rule-based AI ไม่ใช่กล่องดำ) พร้อมเกณฑ์เฉพาะถิ่นที่ปรับได้

> ค่าทางอุตุนิยมวิทยาทุกตัวคำนวณจาก MetPy เท่านั้น เพื่อความถูกต้องเชิงวิชาการ

---

## คุณสมบัติหลัก

- **Skew-T Log-P เชิงโต้ตอบ** — เส้นอุณหภูมิ/จุดน้ำค้าง/parcel, แรเงา CAPE/CIN, ไฮไลต์ชั้นผกผัน (inversion) อัตโนมัติ, จุด LCL/LFC/EL, เส้น 0°C
- **Hodograph** — เวกเตอร์ลมตามระดับ ระบายสีตามความเร็ว
- **ดัชนีเสถียรภาพ (KPI)** — CAPE, CIN, Lifted Index, PWAT, K-Index, LCL/LFC/EL, ระดับเยือกแข็ง 0°C พร้อมเกณฑ์สีเขียว/เหลือง/แดงตามเกณฑ์ฝนหลวง
- **AI ประเมินโอกาสฝน + เทคนิคฝนหลวง** — ให้คะแนน 0-100 พร้อมเหตุผลรายดัชนี
- **เกณฑ์เฉพาะถิ่น** — ปรับ RH/ลม/K-Index รายภูมิภาค (ทุ่งกุลาร้องไห้, บางลาง, นครราชสีมา, สระแก้ว, ป่าพรุโต๊ะแดง) บันทึกลง SQLite
- **บทบาทผู้ใช้ (Role)** — นักบิน / นักอุตุนิยมวิทยา / นักวิจัย / เกษตรกร เน้น KPI ต่างกัน
- **พอร์ทัลข้อมูล** — อัปโหลดไฟล์ sounding (HTML/text-list) และสืบค้นประวัติจากแคช (รองรับ พ.ศ. และ ค.ศ.)
- **2 ภาษา (ไทย/อังกฤษ) + Dark/Light** — สลับได้โดยไม่ reload จดจำสถานะข้าม session

---

## ความต้องการของระบบ

- Python **3.11**
- การเชื่อมต่ออินเทอร์เน็ตเพื่อดึงข้อมูลสดจาก University of Wyoming (สำหรับโหมด live)

---

## การติดตั้ง

```bash
# 1. สร้าง virtual environment (แนะนำ)
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 2. ติดตั้ง dependencies
pip install -r requirements.txt
```

## การรัน

```bash
flask --app app run --debug
# หรือ
python app.py
```

เปิดเบราว์เซอร์ที่ `http://127.0.0.1:5000/`

| เส้นทาง | หน้า |
|---------|------|
| `/`         | แดชบอร์ดหลัก (Skew-T + KPI + AI) |
| `/landing`  | หน้าแนะนำ + พันธกิจฝนหลวง |
| `/data`     | อัปโหลดข้อมูล + สืบค้นประวัติ |
| `/settings` | ตั้งค่าบทบาท + เกณฑ์เฉพาะถิ่น |

> หากดิสก์ที่รันมีปัญหา SQLite I/O ให้กำหนดตำแหน่งฐานข้อมูลชั่วคราว:
> `VERTIAI_DB=/tmp/vertiai.db flask --app app run`

---

## โครงสร้างโปรเจกต์

```
vertiai/
├── app.py                  # Flask API + เส้นทางหน้าเว็บ + logging วัดเวลา (<2s)
├── requirements.txt
├── core/
│   ├── sounding.py         # ดาวน์โหลด/parse sounding + คำนวณดัชนีด้วย MetPy
│   ├── ai_rules.py         # rule-based AI: โอกาสฝน, เทคนิคฝนหลวง, เกณฑ์เฉพาะถิ่น
│   └── db.py               # SQLite: cache ผล + region_thresholds
├── static/
│   ├── css/app.css         # ธีม Dark/Light (CSS variables)
│   ├── js/
│   │   ├── i18n.js         # โมดูลร่วม i18n + theme (localStorage)
│   │   ├── skewt.js        # ลอจิกแดชบอร์ด (Plotly)
│   │   ├── data.js         # พอร์ทัลข้อมูล
│   │   └── settings.js     # ตั้งค่า
│   └── i18n/{th,en}.json   # พจนานุกรม 2 ภาษา (ตรงกัน)
├── templates/              # dashboard / landing / data / settings
└── data/vertiai.db         # SQLite (สร้างอัตโนมัติ)
```

---

## API โดยย่อ

| Method | Endpoint | คำอธิบาย |
|--------|----------|----------|
| GET  | `/api/stations` | รายชื่อสถานี |
| GET  | `/api/sounding?station=&date=YYYY-MM-DD&hour=&region=` | ดึง+วิเคราะห์ (มีแคช) |
| POST | `/api/upload` | อัปโหลดไฟล์/ข้อความ sounding |
| GET  | `/api/history?station=&year=` | ประวัติจากแคช (รองรับ พ.ศ./ค.ศ.) |
| GET/POST | `/api/thresholds` | อ่าน/บันทึกเกณฑ์เฉพาะถิ่น |
| GET  | `/api/roles`, POST `/api/login`, GET `/api/me`, POST `/api/logout` | บทบาทผู้ใช้ |
| GET  | `/api/dam_inflow?C=&I=&A=` | ประเมินน้ำไหลลงเขื่อน (Q=CIA) |

ทุก endpoint คืน JSON และมี validation กัน XSS/SQL injection

---

## หมายเหตุด้านประสิทธิภาพ

ระบบบันทึก log เวลาตอบสนองของ `/api/sounding` ทุกคำขอ และเตือน (`SLOW ...`)
เมื่อเกินงบ 2 วินาที (`PERF_BUDGET_MS`) ผลที่ดึงสดจะถูกแคชใน SQLite
คำขอซ้ำจะตอบจากแคชในระดับมิลลิวินาที

---

## เมื่อดึงข้อมูล Wyoming ไม่สำเร็จ

ทุกหน้ามีสถานะ empty/error ชัดเจน หาก Wyoming ถูกบล็อกหรือยังไม่มีข้อมูลรอบนั้น
แดชบอร์ดจะแสดงแถบแจ้งเตือนพร้อมปุ่ม **ลองใหม่** และทางเลือก **อัปโหลดไฟล์เอง**
ที่หน้า `/data`
