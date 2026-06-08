/* ============================================================
   VertiAI - Dashboard Logic (Session 9)
   Skew-T Log-P + Hodograph (Plotly) + KPI + AI Panel
   + Operation Dashboard + Export JSON/CSV
   ยึดสี/องค์ประกอบเดียวกับ notebook: Temp 'r', Dewpoint 'g',
   Parcel 'k--', LCL 'ko', LFC 'bo', 0°C isotherm cyan '--',
   CAPE แดงจาง / CIN ฟ้าจาง, Inversion ส้มโปร่ง, Hodograph range 80/grid 20
   role default = "rainmaking" (เจ้าหน้าที่ฝนหลวง)
   ============================================================ */

// ---------- ค่าคงที่การวาด Skew-T ----------
const SKEW = 35;
const P_REF = 1000;
const P_TICKS = [1000, 850, 700, 500, 400, 300, 250, 200, 150, 100];
const X_RANGE = [-40, 50];
const Y_RANGE = [Math.log10(1020), Math.log10(100)];

function sx(T, p) { return T + SKEW * (Math.log(P_REF) - Math.log(p)); }
function sy(p) { return Math.log10(p); }

// ---------- i18n ----------
function t(k) { return window.VAI ? window.VAI.t(k) : k; }
function applyI18n() { if (window.VAI) window.VAI.apply(); }

// ---------- KPI_DEFS ----------
const KPI_DEFS = [
  { key: "CAPE", label: "CAPE", unit: "J/kg", tip: "พลังงานศักย์ลอยตัว ยิ่งสูงยิ่งไม่เสถียร (เกณฑ์ฝน ≥1000)",
    fmt: v => v?.toFixed(0), grade: v => v == null ? "" : v >= 1000 ? "good" : v >= 500 ? "warn" : "bad" },
  { key: "CIN", label: "CIN", unit: "J/kg", tip: "พลังงานยับยั้งการลอยตัว (เหมาะ −50..0)",
    fmt: v => v?.toFixed(0), grade: v => v == null ? "" : (v >= -50 && v <= 0) ? "good" : v >= -100 ? "warn" : "bad" },
  { key: "LI", label: "Lifted Index", unit: "°C", tip: "ดัชนียกตัว ค่ายิ่งติดลบยิ่งไม่เสถียร (เกณฑ์ ≤ −2)",
    fmt: v => v?.toFixed(1), grade: v => v == null ? "" : v <= -2 ? "good" : v <= 2 ? "warn" : "bad" },
  { key: "PWAT", label: "PWAT", unit: "mm", tip: "ปริมาณน้ำในบรรยากาศ (เกณฑ์ ≥40)",
    fmt: v => v?.toFixed(0), grade: v => v == null ? "" : v >= 40 ? "good" : v >= 25 ? "warn" : "bad" },
  { key: "K_INDEX", label: "K-Index", unit: "°C", tip: "ศักยภาพพายุฝนฟ้าคะนอง (เกณฑ์ ≥35)",
    fmt: v => v?.toFixed(1), grade: v => v == null ? "" : v >= 35 ? "good" : v >= 25 ? "warn" : "bad" },
  { key: "LCL_p", label: "LCL", unit: "hPa", tip: "ระดับควบแน่นยกตัว (ฐานเมฆ) เกณฑ์ ≤950",
    fmt: v => v?.toFixed(0), grade: v => v == null ? "" : v <= 950 ? "good" : v <= 980 ? "warn" : "bad" },
  { key: "LFC_p", label: "LFC", unit: "hPa", tip: "ระดับลอยตัวอิสระ เกณฑ์ ≤750",
    fmt: v => v?.toFixed(0), grade: v => v == null ? "" : v <= 750 ? "good" : v <= 850 ? "warn" : "bad" },
  { key: "EL_p", label: "EL", unit: "hPa", tip: "ระดับสมดุล (ยอดเมฆ) เกณฑ์ ≤250",
    fmt: v => v?.toFixed(0), grade: v => v == null ? "" : v <= 250 ? "good" : v <= 400 ? "warn" : "bad" },
  { key: "FREEZING_0C", label: "Freezing 0°C", unit: "m", tip: "ระดับเยือกแข็ง 0°C (สำคัญต่อการบินฝนหลวง)",
    fmt: v => v ? v.height_m?.toFixed(0) : null, grade: () => "" },
];

// ---------- สถานะ ----------
let DATA = null;
let _currentStationName = "";

// ============================================================
// เรียก API
// ============================================================
async function analyze() {
  const station = document.getElementById("sel-station").value;
  const date = document.getElementById("sel-date").value;
  const hour = document.getElementById("sel-hour").value;
  const region = document.getElementById("sel-region").value;
  if (!station || !date) { toast(t("err_select")); return; }

  // ตรวจวันที่อนาคต — ข้อมูล Sounding มีเฉพาะวันที่ผ่านมาแล้ว
  const today = new Date().toISOString().slice(0, 10);
  if (date > today) {
    showErr(`ไม่สามารถดึงข้อมูลวันที่ ${date} ได้ — ข้อมูล Upper-Air Sounding มีเฉพาะวันที่ผ่านมาแล้ว กรุณาเลือกวันที่ไม่เกินวันนี้ (${today})`);
    return;
  }

  hideErr();
  hideEmpty();
  setLoading(true);
  setStatus(t("loading"));
  const url = `/api/sounding?station=${station}&date=${date}&hour=${hour}` +
              (region ? `&region=${region}` : "");
  try {
    const res = await fetch(url);
    const j = await res.json();
    if (!j.ok) {
      // Wyoming ไม่พร้อม — ลอง fallback last_upload เงียบ ๆ
      const lu = await tryLastUpload(false, true);
      if (!lu) {
        showErr((j.error || t("err_fetch")) + " — หากอัปโหลดข้อมูลไว้แล้ว กด \"ใช้ข้อมูลที่อัปโหลดไว้\"");
        setStatus(""); setLoading(false);
      }
      return;
    }
    DATA = j;
    DATA._source = j.cached ? "cached" : "live";
    hideEmpty();
    render(j);
    setStatus(`${t("done")} ${j.elapsed_ms ?? "-"} ms ${j.cached ? t("cached") : ""}`);
  } catch (e) {
    showErr(t("err_connect"));
    setStatus("");
  } finally {
    setLoading(false);
  }
}

// ============================================================
// วาดผลทั้งหมด
// ============================================================
// ---------- Data Badge ----------
function stationLabelFromMeta(stationId) {
  // หาชื่อสถานีจาก <option> ใน dropdown ตามรหัสที่อยู่ใน _meta จริง ๆ
  // (ไม่ใช่ตัวเลือกที่ถูกเลือกอยู่ในขณะนี้ — กันปัญหา badge ไม่ sync กับข้อมูลที่แสดง)
  if (!stationId) return "";
  const stEl = document.getElementById("sel-station");
  if (stEl) {
    const opt = Array.from(stEl.options).find(o => o.value === stationId);
    if (opt && opt.textContent) return opt.textContent;
  }
  return stationId;
}
function updateDataBadge(d) {
  const badge = document.getElementById("data-badge");
  if (!badge) return;
  const meta = d._meta || {};
  const station = stationLabelFromMeta(meta.station || "");
  const date    = meta.date    || "";
  const hour    = meta.hour    != null ? (parseInt(meta.hour) === 0 ? "00Z" : parseInt(meta.hour) === 12 ? "12Z" : meta.hour + "Z") : "";
  if (!station && !date) { badge.style.display = "none"; return; }
  let dateStr = date;
  if (date) {
    try {
      const dt = new Date(date + "T00:00:00");
      dateStr = dt.toLocaleDateString("th-TH", { day: "numeric", month: "short", year: "numeric" });
    } catch(e) {}
  }
  badge.textContent = [station, dateStr, hour].filter(Boolean).join(" · ");
  badge.style.display = "inline-block";
}

function render(d) {
  drawSkewT(d);
  drawHodograph(d);
  drawKPI(d.indices);
  drawAI(d.ai, d.rainmaking);
  drawAtmoLayers(d);
  drawLegend(d);
  drawRoleWidget(d);
  drawOperationDashboard(d);
  updateDataBadge(d);
}

// ---------- Skew-T ----------
function drawSkewT(d) {
  const p = d.profile.pressure, T = d.profile.temperature,
        Td = d.profile.dewpoint, H = d.profile.height, parcel = d.profile.parcel;
  const idx = d.indices;
  const traces = [];

  // เส้น isotherm พื้นหลัง
  for (let iso = -100; iso <= 50; iso += 10) {
    const xs = P_TICKS.map(pp => sx(iso, pp)), ys = P_TICKS.map(sy);
    traces.push({ x: xs, y: ys, mode: "lines", hoverinfo: "skip", showlegend: false,
      line: { color: "rgba(140,140,140,0.18)", width: 1 } });
  }

  // แรเงา CAPE / CIN
  const capeX = [], capeY = [], cinX = [], cinY = [];
  for (let i = 0; i < p.length; i++) {
    const xe = sx(T[i], p[i]), xp = sx(parcel[i], p[i]), y = sy(p[i]);
    if (parcel[i] >= T[i]) { capeX.push(xe, xp, null); capeY.push(y, y, null); }
    else { cinX.push(xe, xp, null); cinY.push(y, y, null); }
  }
  traces.push({ x: capeX, y: capeY, mode: "lines", hoverinfo: "skip", showlegend: false,
    line: { color: "rgba(220,40,40,0.28)", width: 2 }, name: "CAPE" });
  traces.push({ x: cinX, y: cinY, mode: "lines", hoverinfo: "skip", showlegend: false,
    line: { color: "rgba(40,90,220,0.28)", width: 2 }, name: "CIN" });

  // เส้น 0°C isotherm
  traces.push({ x: P_TICKS.map(pp => sx(0, pp)), y: P_TICKS.map(sy),
    mode: "lines", name: "0°C", hoverinfo: "skip",
    line: { color: "#00c2d6", width: 2, dash: "dash" } });

  // Parcel Path
  traces.push({ x: parcel.map((v, i) => sx(v, p[i])), y: p.map(sy),
    mode: "lines", name: "Parcel", line: { color: "#111", width: 1.5, dash: "dash" },
    hovertemplate: "Parcel<br>P %{customdata:.0f} hPa<extra></extra>", customdata: p });

  // Dewpoint
  traces.push({ x: Td.map((v, i) => sx(v, p[i])), y: p.map(sy),
    mode: "lines", name: "Dewpoint", line: { color: "#2ca02c", width: 2.5 },
    customdata: p.map((pp, i) => [pp, Td[i], H[i]]),
    hovertemplate: "Td %{customdata[1]:.1f}°C<br>P %{customdata[0]:.0f} hPa<br>H %{customdata[2]:.0f} m<extra></extra>" });

  // Temperature
  traces.push({ x: T.map((v, i) => sx(v, p[i])), y: p.map(sy),
    mode: "lines", name: "Temperature", line: { color: "#d62728", width: 2.5 },
    customdata: p.map((pp, i) => [pp, T[i], Td[i], H[i]]),
    hovertemplate: "T %{customdata[1]:.1f}°C<br>Td %{customdata[2]:.1f}°C<br>P %{customdata[0]:.0f} hPa<br>H %{customdata[3]:.0f} m<extra></extra>" });

  // จุด LCL / LFC / EL
  const pts = [
    { p: idx.LCL_p, T: idx.LCL_t, name: "LCL", color: "#000" },
    { p: idx.LFC_p, T: idx.LFC_t, name: "LFC", color: "#1f4fff" },
    { p: idx.EL_p,  T: idx.EL_t,  name: "EL",  color: "#7a3cff" },
  ];
  pts.forEach(pt => {
    if (pt.p == null || pt.T == null) return;
    traces.push({ x: [sx(pt.T, pt.p)], y: [sy(pt.p)], mode: "markers+text",
      name: pt.name, text: [pt.name], textposition: "middle right",
      textfont: { size: 11, color: pt.color },
      marker: { size: 9, color: pt.color, line: { color: "#fff", width: 1 } },
      hovertemplate: `${pt.name}<br>P %{customdata:.0f} hPa<extra></extra>`, customdata: [pt.p] });
  });

  // ป้ายความสูง
  const annotations = (d.pressure_height_map || []).map(m => ({
    xref: "paper", x: 0.012, y: sy(m.pressure), yanchor: "middle",
    text: `${m.height} m`, showarrow: false,
    font: { size: 9, color: themeColor("--accent") },
    bgcolor: "rgba(255,255,255,0.0)",
  }));

  // แถบ Inversion
  const shapes = (d.inversion_layers || []).map(([bottom, top]) => ({
    type: "rect", xref: "paper", x0: 0, x1: 1,
    yref: "y", y0: sy(bottom), y1: sy(top),
    fillcolor: "rgba(255,165,0,0.18)", line: { width: 0 }, layer: "below",
  }));

  // ---------- Wind Barbs (WMO standard) ----------
  const wb_u = d.profile.u, wb_v = d.profile.v, wb_spd = d.profile.speed;
  const MAX_WIND = 150;

  traces.push({ x: [0, 0], y: [Y_RANGE[0], Y_RANGE[1]],
    xaxis: "x2", yaxis: "y", mode: "lines", hoverinfo: "skip", showlegend: false,
    line: { color: "rgba(140,140,140,0.22)", width: 1, dash: "dot" } });

  const SHAFT_X  = 0.52;
  const AR       = 60 / 634;
  const SHAFT_Y  = SHAFT_X * AR;
  const BARB_LEN = 0.38;
  const BARB_SP  = 0.22;

  const skipN = Math.max(1, Math.floor(p.length / 20));

  for (let i = 0; i < p.length; i += skipN) {
    const ui = wb_u[i], vi = wb_v[i], si = wb_spd[i];
    if (!isFinite(ui) || !isFinite(vi) || Math.abs(ui) > MAX_WIND) continue;
    const speed = Math.sqrt(ui * ui + vi * vi);
    const yi    = sy(p[i]);
    const col   = speed > 50 ? "#c0392b" : speed > 25 ? "#e67e22" : "#2980b9";

    if (speed < 2.5) {
      traces.push({ x: [0], y: [yi], xaxis: "x2", yaxis: "y", mode: "markers",
        marker: { size: 8, color: "rgba(0,0,0,0)", line: { color: col, width: 1.5 } },
        showlegend: false, hoverinfo: "skip" });
      continue;
    }

    const dx = -ui / speed, dy = -vi / speed;
    const tx = dx * SHAFT_X, ty = yi + dy * SHAFT_Y;
    traces.push({ x: [0, tx], y: [yi, ty], xaxis: "x2", yaxis: "y", mode: "lines",
      line: { color: col, width: 2 }, showlegend: false, hoverinfo: "skip" });

    const pxPix = dy * 634, pyPix = -dx * 60;
    const pLen  = Math.sqrt(pxPix * pxPix + pyPix * pyPix);
    const bx = (pxPix / pLen) * BARB_LEN * SHAFT_X;
    const by = (pyPix / pLen) * BARB_LEN * SHAFT_Y;

    let spd5 = Math.round(speed / 5) * 5;
    const pennants  = Math.floor(spd5 / 50); spd5 -= pennants * 50;
    const longBarbs = Math.floor(spd5 / 10); spd5 -= longBarbs * 10;
    const shortBarbs = Math.round(spd5 / 5);

    let tPos = 1.0;
    for (let k = 0; k < pennants; k++) {
      const px0 = tx * tPos, py0 = yi + (ty - yi) * tPos;
      const t2  = Math.max(0, tPos - BARB_SP);
      const px2 = tx * t2, py2 = yi + (ty - yi) * t2;
      traces.push({ x: [px0, px0 + bx, px2, px0], y: [py0, py0 + by, py2, py0],
        xaxis: "x2", yaxis: "y", mode: "lines",
        fill: "toself", fillcolor: col, line: { color: col, width: 0.5 },
        showlegend: false, hoverinfo: "skip" });
      tPos -= BARB_SP;
    }
    for (let k = 0; k < longBarbs; k++) {
      const px0 = tx * tPos, py0 = yi + (ty - yi) * tPos;
      traces.push({ x: [px0, px0 + bx], y: [py0, py0 + by],
        xaxis: "x2", yaxis: "y", mode: "lines",
        line: { color: col, width: 1.8 }, showlegend: false, hoverinfo: "skip" });
      tPos -= BARB_SP;
    }
    for (let k = 0; k < shortBarbs; k++) {
      const px0 = tx * tPos, py0 = yi + (ty - yi) * tPos;
      traces.push({ x: [px0, px0 + bx * 0.5], y: [py0, py0 + by * 0.5],
        xaxis: "x2", yaxis: "y", mode: "lines",
        line: { color: col, width: 1.8 }, showlegend: false, hoverinfo: "skip" });
      tPos -= BARB_SP;
    }

    const wdir = Math.round((Math.atan2(-ui, -vi) * 180 / Math.PI + 360) % 360);
    traces.push({ x: [0], y: [yi], xaxis: "x2", yaxis: "y", mode: "markers",
      marker: { size: 4, color: col },
      customdata: [[p[i], Math.round(speed), wdir]],
      hovertemplate: "P %{customdata[0]:.0f} hPa | %{customdata[1]:.0f} kt %{customdata[2]}°<extra></extra>",
      showlegend: false });
  }

  annotations.push({ xref: "x2", x: 0, yref: "paper", y: 1.015,
    text: "Wind (kt)", showarrow: false,
    font: { size: 10, color: themeColor("--text-soft") },
    xanchor: "center", yanchor: "bottom" });

  const layout = baseLayout();
  layout.shapes = shapes;
  layout.annotations = annotations;
  layout.xaxis = {
    title: "Temperature (°C)", range: X_RANGE, zeroline: false,
    domain: [0, 0.86], gridcolor: "rgba(0,0,0,0)", color: themeColor("--text-soft"),
    tickvals: [-40, -30, -20, -10, 0, 10, 20, 30, 40, 50],
  };
  layout.xaxis2 = {
    domain: [0.88, 1.0], anchor: "y",
    range: [-1, 1], zeroline: false, showgrid: false,
    showticklabels: false, fixedrange: true,
    color: themeColor("--text-soft"),
  };
  layout.yaxis = {
    title: "Pressure (hPa)", range: [Y_RANGE[0], Y_RANGE[1]],
    autorange: false,
    tickvals: P_TICKS.map(sy), ticktext: P_TICKS.map(String),
    gridcolor: themeColor("--border"), color: themeColor("--text-soft"),
  };
  layout.showlegend = false;   // legend แยกไปแสดงใน zone-legend แทน
  layout.margin = { l: 52, r: 8, t: 10, b: 28 };

  Plotly.react("skewt", traces, layout, { responsive: true, displayModeBar: false, autosizable: true });
  // resize 2 รอบ: รอบแรกหลัง paint, รอบสองหลัง layout settle
  requestAnimationFrame(() => {
    Plotly.Plots.resize(document.getElementById("skewt"));
    setTimeout(() => Plotly.Plots.resize(document.getElementById("skewt")), 120);
  });
}

// ---------- Hodograph ----------
function drawHodograph(d) {
  const rawU = d.profile.u, rawV = d.profile.v, rawSpd = d.profile.speed, rawH = d.profile.height;
  const MAX_WIND = 80;
  const u = [], v = [], spd = [], H = [];
  for (let i = 0; i < rawU.length; i++) {
    const ui = rawU[i], vi = rawV[i], si = rawSpd[i];
    if (!isFinite(ui) || !isFinite(vi) || Math.abs(ui) > MAX_WIND || Math.abs(vi) > MAX_WIND) continue;
    u.push(ui); v.push(vi); spd.push(si); H.push(rawH[i]);
  }
  const maxComp = Math.min(80, Math.max(20, ...u.map(Math.abs), ...v.map(Math.abs)) + 10);
  const traces = [];

  for (let r = 20; r <= maxComp; r += 20) {
    const cx = [], cy = [];
    for (let a = 0; a <= 360; a += 6) { cx.push(r * Math.cos(a * Math.PI / 180)); cy.push(r * Math.sin(a * Math.PI / 180)); }
    traces.push({ x: cx, y: cy, mode: "lines", hoverinfo: "skip", showlegend: false,
      line: { color: "rgba(140,140,140,0.3)", width: 1 } });
    traces.push({ x: [r * 0.707], y: [r * 0.707], mode: "text",
      text: [`${r}kt`], textfont: { size: 8, color: "rgba(120,120,120,0.7)" },
      hoverinfo: "skip", showlegend: false });
  }
  traces.push({ x: [-maxComp, maxComp], y: [0, 0], mode: "lines", hoverinfo: "skip", showlegend: false,
    line: { color: "rgba(140,140,140,0.3)", width: 1 } });
  traces.push({ x: [0, 0], y: [-maxComp, maxComp], mode: "lines", hoverinfo: "skip", showlegend: false,
    line: { color: "rgba(140,140,140,0.3)", width: 1 } });

  const layers = [
    { label: "0-3 km",  color: "#2196F3", maxH: 3000 },
    { label: "3-6 km",  color: "#4CAF50", maxH: 6000 },
    { label: "6-9 km",  color: "#FF9800", maxH: 9000 },
    { label: ">9 km",   color: "#9C27B0", maxH: Infinity },
  ];
  let prevLayer = -1, segU = [], segV = [], segH = [], segSpd = [];
  const pushSeg = (lIdx) => {
    if (segU.length < 1) return;
    traces.push({ x: segU, y: segV, mode: "lines+markers", name: layers[lIdx].label,
      line: { color: layers[lIdx].color, width: 2.5 },
      marker: { size: 4, color: layers[lIdx].color },
      customdata: segH.map((h, i) => [h, segSpd[i]]),
      hovertemplate: "ลม %{customdata[1]:.0f} kt<br>H %{customdata[0]:.0f} m<extra></extra>" });
  };
  for (let i = 0; i < u.length; i++) {
    const lIdx = layers.findIndex(l => H[i] < l.maxH);
    if (lIdx !== prevLayer) {
      if (prevLayer >= 0) { segU.push(u[i]); segV.push(v[i]); pushSeg(prevLayer); }
      segU = [u[i]]; segV = [v[i]]; segH = [H[i]]; segSpd = [spd[i]]; prevLayer = lIdx;
    } else { segU.push(u[i]); segV.push(v[i]); segH.push(H[i]); segSpd.push(spd[i]); }
  }
  if (prevLayer >= 0) pushSeg(prevLayer);

  const layout = baseLayout();
  layout.margin = { l: 28, r: 8, t: 8, b: 24 };
  layout.xaxis = { range: [-maxComp, maxComp], zeroline: false, showgrid: false,
    color: themeColor("--text-soft"), fixedrange: true, title: { text: "U (kt)", font: { size: 10 } } };
  layout.yaxis = { range: [-maxComp, maxComp], zeroline: false, showgrid: false,
    color: themeColor("--text-soft"), fixedrange: true, title: { text: "V (kt)", font: { size: 10 } } };
  layout.showlegend = true;
  layout.legend = { orientation: "h", x: 0.5, xanchor: "center", y: -0.22,
                    font: { size: 9 }, bgcolor: "rgba(0,0,0,0)" };
  Plotly.react("hodo", traces, layout, { responsive: true, displayModeBar: false });
}

// ---------- KPI ----------
function drawKPI(idx) {
  const grid = document.getElementById("kpi-grid");
  grid.innerHTML = "";
  const KPI_WITH_UNITS = KPI_DEFS.map(def => {
    const d2 = { ...def };
    if (["CAPE", "CIN"].includes(def.key)) {
      d2.unit = energyUnit();
      d2.fmt = v => v != null ? cvtEnergy(v)?.toFixed(getUnits().energy === "kj" ? 2 : 0) : null;
    } else if (def.key === "FREEZING_0C") {
      d2.unit = heightUnit();
      d2.fmt = v => v ? cvtHeight(v.height_m)?.toFixed(0) : null;
    }
    return d2;
  });
  KPI_WITH_UNITS.forEach(def => {
    const raw = idx[def.key];
    const val = def.fmt(raw);
    const g = def.grade(raw);
    const el = document.createElement("div");
    const focus = ROLE_FOCUS.includes(def.key) ? " focus" : "";
    el.className = "kpi " + (g || "") + focus;
    el.title = def.tip;
    el.innerHTML =
      `<div class="k-name">${def.label} <span class="info">i</span></div>` +
      `<div class="k-val">${val ?? "—"} <span class="k-unit">${val != null ? def.unit : ""}</span></div>`;
    grid.appendChild(el);
  });
}

// ---------- AI Panel ----------
function drawAI(ai, rm) {
  const levelEl = document.getElementById("ai-level");
  const sumEl = document.getElementById("ai-summary");
  const cls = ai.level === "สูง" ? "l-high" : ai.level === "ปานกลาง" ? "l-mid" : "l-low";
  levelEl.className = "ai-level " + cls;
  levelEl.textContent = `${ai.level} (${ai.score})`;
  sumEl.textContent = ai.summary_th;

  Plotly.react("gauge", [{
    type: "indicator", mode: "gauge+number", value: ai.score,
    number: { suffix: "", font: { size: 22, color: themeColor("--text") } },
    gauge: {
      axis: { range: [0, 100], tickwidth: 1, tickcolor: themeColor("--text-soft") },
      bar: { color: ai.score >= 60 ? "#16a34a" : ai.score >= 35 ? "#d97706" : "#dc2626" },
      bgcolor: "rgba(0,0,0,0)", borderwidth: 0,
      steps: [
        { range: [0, 35],   color: "rgba(220,38,38,0.12)" },
        { range: [35, 60],  color: "rgba(217,119,6,0.12)" },
        { range: [60, 100], color: "rgba(22,163,74,0.12)" },
      ],
    },
  }], { margin: { l: 14, r: 14, t: 6, b: 0 }, height: 110, paper_bgcolor: "rgba(0,0,0,0)" },
  { responsive: true, displayModeBar: false });

  const rc = document.getElementById("reasons");
  rc.innerHTML = "";
  ai.reasons.forEach(r => {
    const el = document.createElement("div");
    el.className = "reason";
    el.innerHTML = `<span class="dot ${r.passed ? "pass" : "fail"}"></span>` +
      `<span class="r-name">${r.index}</span><span class="r-val">${r.value_text}</span>`;
    rc.appendChild(el);
  });

  const rmEl = document.getElementById("rainmaking");
  rmEl.style.display = "block";
  rmEl.innerHTML = `<b>${t("technique")}:</b> ${rm.technique}<br>${rm.note}`;
}


// ============================================================
// Skew-T Legend Panel (Session 9 — แยกออกจาก Plotly chart)
// ============================================================
function drawLegend(d) {
  const el = document.getElementById("skewt-legend-content");
  if (!el) return;
  const idx = d.indices || {};

  // ตรวจว่ามี inversion layers ไหม
  const hasInv = d.inversion_layers && d.inversion_layers.length > 0;
  // CAPE/CIN
  const cape = idx.CAPE != null ? idx.CAPE.toFixed(0) : null;
  const cin  = idx.CIN  != null ? idx.CIN.toFixed(0)  : null;

  const items = [
    { type: "line", color: "#d62728", dash: false, label: "Temperature (T)", note: "" },
    { type: "line", color: "#2ca02c", dash: false, label: "Dewpoint (Td)", note: "" },
    { type: "line", color: "#111",    dash: true,  label: "Parcel Path", note: "เส้นทางอนุภาคอากาศ" },
    { type: "line", color: "#00c2d6", dash: true,  label: "0°C Isotherm", note: "เส้นอุณหภูมิ 0°C" },
    { type: "area", color: "rgba(220,40,40,0.45)",  label: "CAPE",
      note: cape ? `${cape} J/kg — พลังงานลอยตัว` : "พลังงานลอยตัว" },
    { type: "area", color: "rgba(40,90,220,0.45)",  label: "CIN",
      note: cin  ? `${cin} J/kg — พลังงานยับยั้ง`   : "พลังงานยับยั้ง" },
    hasInv ? { type: "band", label: "Inversion Layer", note: "ชั้นผกผันอุณหภูมิ" } : null,
    { type: "dot", color: "#111",    label: "LCL",
      note: idx.LCL_p ? `${idx.LCL_p.toFixed(0)} hPa — ฐานเมฆ` : "ระดับควบแน่นยกตัว" },
    { type: "dot", color: "#1f4fff", label: "LFC",
      note: idx.LFC_p ? `${idx.LFC_p.toFixed(0)} hPa — ระดับลอยตัวอิสระ` : "ระดับลอยตัวอิสระ" },
    { type: "dot", color: "#7a3cff", label: "EL",
      note: idx.EL_p  ? `${idx.EL_p.toFixed(0)} hPa — ยอดเมฆ (EL)` : "ระดับสมดุล (ยอดเมฆ)" },
  ].filter(Boolean);

  const rows = items.map(item => {
    let icon = "";
    if (item.type === "line") {
      const borderStyle = item.dash
        ? `border-top: 2.5px dashed ${item.color}; background: none;`
        : `background: ${item.color};`;
      icon = `<span class="skt-leg-line${item.dash ? " dashed" : ""}" style="${borderStyle}"></span>`;
    } else if (item.type === "area") {
      icon = `<span class="skt-leg-area" style="background:${item.color};"></span>`;
    } else if (item.type === "band") {
      icon = `<span class="skt-leg-band"></span>`;
    } else if (item.type === "dot") {
      icon = `<span class="skt-leg-dot" style="background:${item.color};border:2px solid #fff;box-shadow:0 0 0 1px ${item.color}"></span>`;
    }
    return `<div class="skt-leg-item">
      ${icon}
      <span><b>${item.label}</b>${item.note ? `<span style="color:var(--text-soft);font-size:11px;margin-left:4px">${item.note}</span>` : ""}</span>
    </div>`;
  }).join("");

  // แสดง wind barb legend แยกส่วน
  const windLegend = `
  <div style="margin-top:12px;padding-top:10px;border-top:1px solid var(--border)">
    <div style="font-size:12px;font-weight:700;color:var(--text-soft);margin-bottom:8px">Wind Barb (kt)</div>
    <div style="display:flex;gap:18px;flex-wrap:wrap;font-size:12px">
      <span style="display:flex;align-items:center;gap:6px"><span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#2980b9"></span>≤ 25 kt</span>
      <span style="display:flex;align-items:center;gap:6px"><span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#e67e22"></span>26–50 kt</span>
      <span style="display:flex;align-items:center;gap:6px"><span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#c0392b"></span>> 50 kt</span>
      <span style="color:var(--text-soft)">| Short barb = 5 kt · Long = 10 kt · Pennant = 50 kt</span>
    </div>
  </div>`;

  el.innerHTML = `<div class="skt-legend">${rows}</div>${windLegend}`;
}

// ============================================================
// Operation Dashboard (Session 9)
// ============================================================
function drawOperationDashboard(d) {
  const zone = document.getElementById("zone-ops");
  if (!zone) return;

  const idx = d.indices;
  const ai  = d.ai || {};
  const rm  = d.rainmaking || {};

  // --- Station name ---
  const stEl = document.getElementById("sel-station");
  const stText = stEl ? (stEl.options[stEl.selectedIndex]?.text || "") : "";
  const dateVal = document.getElementById("sel-date")?.value || "";
  const hourVal = document.getElementById("sel-hour")?.value || "0";

  // --- Source badge ---
  const src = d._source || "live";
  const srcClass = src === "upload" ? "upload" : src === "cached" ? "cached" : "live";
  const srcLabel = src === "upload" ? "Upload (ไฟล์ที่อัปโหลด)" : src === "cached" ? "Cache (Wyoming)" : "Wyoming Live";
  const srcDot = src === "upload" ? "▲" : src === "cached" ? "◆" : "●";

  // --- Go/No-Go ---
  const score = ai.score || 0;
  let goClass = "nogo", goText = "NO-GO";
  if (score >= 60) { goClass = "go"; goText = "GO"; }
  else if (score >= 35) { goClass = "caution"; goText = "CAUTION"; }

  // --- KPI Chips ---
  const chips = [
    { lbl: "CAPE", val: idx.CAPE != null ? idx.CAPE.toFixed(0) : "—", unit: "J/kg",
      g: idx.CAPE >= 1000 ? "good" : idx.CAPE >= 500 ? "warn" : idx.CAPE != null ? "bad" : "" },
    { lbl: "PWAT", val: idx.PWAT != null ? idx.PWAT.toFixed(0) : "—", unit: "mm",
      g: idx.PWAT >= 40 ? "good" : idx.PWAT >= 25 ? "warn" : idx.PWAT != null ? "bad" : "" },
    { lbl: "K-Index", val: idx.K_INDEX != null ? idx.K_INDEX.toFixed(1) : "—", unit: "°C",
      g: idx.K_INDEX >= 35 ? "good" : idx.K_INDEX >= 25 ? "warn" : idx.K_INDEX != null ? "bad" : "" },
    { lbl: "LCL", val: idx.LCL_p != null ? idx.LCL_p.toFixed(0) : "—", unit: "hPa",
      g: idx.LCL_p <= 950 ? "good" : idx.LCL_p <= 980 ? "warn" : idx.LCL_p != null ? "bad" : "" },
    { lbl: "AI Score", val: score, unit: "/100",
      g: score >= 60 ? "good" : score >= 35 ? "warn" : "bad" },
  ];

  const chipsHTML = chips.map(c =>
    `<div class="ops-kpi-chip ${c.g}">
      <span class="ck-lbl">${c.lbl}</span>
      <span class="ck-val">${c.val}</span>
      <span class="ck-lbl">${c.unit}</span>
    </div>`).join("");

  zone.innerHTML = `
  <div class="ops-dashboard">
    <div class="ops-section" style="min-width:160px">
      <div class="ops-label">แหล่งข้อมูล</div>
      <div><span class="ops-source-badge ${srcClass}">${srcDot} ${srcLabel}</span></div>
      <div class="ops-value" style="font-size:12px;margin-top:2px">${stText}</div>
      <div style="font-size:11px;color:var(--text-soft)">${dateVal} · ${parseInt(hourVal) === 0 ? "00Z" : "12Z"}</div>
    </div>
    <div class="ops-section" style="min-width:100px;align-items:center">
      <div class="ops-label">การตัดสิน</div>
      <div class="ops-go-badge ${goClass}">${goText}</div>
      <div style="font-size:11px;color:var(--text-soft);margin-top:2px">${score}/100</div>
    </div>
    <div class="ops-section grow">
      <div class="ops-label">ดัชนีหลัก (KPI Strip)</div>
      <div class="ops-kpi-row">${chipsHTML}</div>
    </div>
    <div class="ops-section" style="min-width:180px">
      <div class="ops-label">เทคนิคฝนหลวงที่แนะนำ</div>
      <div class="ops-value" style="font-size:13px">${rm.technique || "—"}</div>
      <div style="font-size:11px;color:var(--text-soft);margin-top:2px;line-height:1.4">${rm.note || ""}</div>
    </div>
    <div class="ops-export-btns">
      <div class="ops-label" style="padding:0 0 2px 0">Export Data</div>
      <button class="btn-export json" onclick="exportJSON()">⬇ JSON</button>
      <button class="btn-export csv"  onclick="exportCSV()">⬇ CSV</button>
    </div>
  </div>`;
}

// ---------- Export JSON ----------
function exportJSON() {
  if (!DATA) { toast("ยังไม่มีข้อมูล — กด วิเคราะห์ ก่อน"); return; }
  const blob = new Blob([JSON.stringify(DATA, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  const stEl = document.getElementById("sel-station");
  const station = stEl ? stEl.value : "vertiai";
  const date = document.getElementById("sel-date")?.value || "unknown";
  a.href = url; a.download = `vertiai_${station}_${date}.json`;
  a.click(); URL.revokeObjectURL(url);
}

// ---------- Export CSV (profile data) ----------
function exportCSV() {
  if (!DATA) { toast("ยังไม่มีข้อมูล — กด วิเคราะห์ ก่อน"); return; }
  const p = DATA.profile;
  const cols = ["pressure", "temperature", "dewpoint", "height", "speed", "u", "v"];
  const labels = ["P (hPa)", "T (°C)", "Td (°C)", "H (m)", "Speed (kt)", "U (kt)", "V (kt)"];
  const rows = [labels.join(",")];
  const n = (p.pressure || []).length;
  for (let i = 0; i < n; i++) {
    rows.push(cols.map(c => {
      const v = p[c]?.[i];
      return v != null && isFinite(v) ? v.toFixed(2) : "";
    }).join(","));
  }
  // append indices
  rows.push(""); rows.push("# Indices");
  const idx = DATA.indices || {};
  Object.entries(idx).forEach(([k, v]) => {
    if (typeof v === "number" && isFinite(v)) rows.push(`${k},${v.toFixed(4)}`);
  });

  const blob = new Blob([rows.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  const stEl = document.getElementById("sel-station");
  const station = stEl ? stEl.value : "vertiai";
  const date = document.getElementById("sel-date")?.value || "unknown";
  a.href = url; a.download = `vertiai_${station}_${date}.csv`;
  a.click(); URL.revokeObjectURL(url);
}

// ============================================================
// Helper
// ============================================================
function themeColor(varName) {
  return getComputedStyle(document.body).getPropertyValue(varName).trim() || "#888";
}
function baseLayout() {
  return {
    paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: "Segoe UI, Sarabun, sans-serif", color: themeColor("--text") },
    margin: { l: 52, r: 16, t: 28, b: 40 }, hovermode: "closest",
  };
}
function setLoading(on) { document.getElementById("layout").classList.toggle("is-loading", on); }
function hideEmpty() { const el = document.getElementById("empty-overlay"); if (el) el.style.display = "none"; }
function showErr(msg) {
  const bar = document.getElementById("errbar");
  const m = document.getElementById("errbar-msg");
  if (m) m.textContent = msg;
  if (bar) {
    bar.style.display = "flex";
    if (!document.getElementById("btn-use-upload")) {
      const btn = document.createElement("button");
      btn.id = "btn-use-upload"; btn.className = "btn ghost";
      btn.textContent = "ใช้ข้อมูลที่อัปโหลดไว้";
      btn.addEventListener("click", () => tryLastUpload(true));
      bar.querySelector(".errbar-actions")?.appendChild(btn);
    }
  }
}
function hideErr() { const bar = document.getElementById("errbar"); if (bar) bar.style.display = "none"; }
function setStatus(s) { document.getElementById("status").textContent = s; }
function toast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg; el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 3000);
}
async function tryLastUpload(showToastOnFail, showWarnBar) {
  try {
    const res = await fetch("/api/last_upload");
    const j = await res.json();
    if (!j.ok) {
      if (showToastOnFail) toast("ยังไม่มีข้อมูลที่อัปโหลดไว้ — ไปที่หน้า 'ข้อมูล' เพื่ออัปโหลดก่อน");
      return false;
    }
    DATA = j; DATA._source = "upload";
    // sync ฟอร์มเลือกสถานี/วันที่/เวลา ให้ตรงกับข้อมูลที่ auto-restore มาแสดงจริง
    // (กันปัญหา dropdown ค้างค่า default ขณะที่ badge/กราฟแสดงผลของอีกสถานีหนึ่ง)
    const meta = j._meta || {};
    if (meta.station) {
      const stEl = document.getElementById("sel-station");
      if (stEl && stEl.querySelector(`option[value="${meta.station}"]`)) stEl.value = meta.station;
    }
    if (meta.date) {
      const dEl = document.getElementById("sel-date");
      if (dEl) dEl.value = meta.date;
    }
    if (meta.hour != null) {
      const hEl = document.getElementById("sel-hour");
      if (hEl && hEl.querySelector(`option[value="${meta.hour}"]`)) hEl.value = String(meta.hour);
    }
    hideEmpty(); render(j);
    setStatus("แสดงข้อมูลจาก Upload ล่าสุด");
    setLoading(false);
    // แสดง warning bar (สีเหลือง) แทนการซ่อน error — ให้ผู้ใช้รู้ว่า Wyoming ไม่พร้อม
    if (showWarnBar) {
      const bar = document.getElementById("errbar");
      const m = document.getElementById("errbar-msg");
      if (m) m.textContent = "Wyoming ไม่พร้อมใช้งาน — กำลังแสดงข้อมูลจากการอัปโหลดล่าสุดแทน";
      if (bar) { bar.style.display = "flex"; bar.className = "errbar warn"; }
    } else {
      hideErr();
    }
    return true;
  } catch (e) { return false; }
}

// ---------- ธีม / ภาษา ----------
function toggleTheme() { window.VAI.toggleTheme(); if (DATA) render(DATA); }
async function toggleLang() { await window.VAI.toggleLang(); if (DATA) render(DATA); }

// ============================================================
// Unit Conversion
// ============================================================
const UNIT_KEY = "VAI_units";
const UNIT_DEFAULTS = { wind: "kt", height: "m", temp: "c", pressure: "hpa", energy: "jkg" };
function getUnits() {
  try { return { ...UNIT_DEFAULTS, ...JSON.parse(localStorage.getItem(UNIT_KEY) || "{}") }; }
  catch { return { ...UNIT_DEFAULTS }; }
}
function cvtWind(kt)    { if (kt == null || !isFinite(kt)) return null; const u = getUnits().wind; if (u === "ms") return kt * 0.5144; if (u === "mph") return kt * 1.15078; return kt; }
function windUnit()     { const u = getUnits().wind; return u === "ms" ? "m/s" : u === "mph" ? "mph" : "kt"; }
function cvtHeight(m)   { if (m == null || !isFinite(m)) return null; return getUnits().height === "ft" ? m * 3.28084 : m; }
function heightUnit()   { return getUnits().height === "ft" ? "ft" : "m"; }
function cvtTemp(c)     { if (c == null || !isFinite(c)) return null; return getUnits().temp === "f" ? c * 9 / 5 + 32 : c; }
function tempUnit()     { return getUnits().temp === "f" ? "°F" : "°C"; }
function cvtEnergy(j)   { if (j == null || !isFinite(j)) return null; return getUnits().energy === "kj" ? j / 1000 : j; }
function energyUnit()   { return getUnits().energy === "kj" ? "kJ/kg" : "J/kg"; }
function cvtPressure(h) { if (h == null || !isFinite(h)) return null; if (getUnits().pressure === "inhg") return h * 0.02953; return h; }
function pressureUnit() { const u = getUnits().pressure; return u === "inhg" ? "inHg" : u === "mb" ? "mb" : "hPa"; }

// ============================================================
// 5-layer Atmospheric Description
// ============================================================
const ATM_LAYERS = [
  { id: "bl",    name: "Boundary Layer (BL)", pMin: 850, pMax: 1050, kmRange: "0–1.5 km",  color: "#e67e22" },
  { id: "low",   name: "Low Troposphere",     pMin: 700, pMax: 850,  kmRange: "1.5–3 km",  color: "#3498db" },
  { id: "mid",   name: "Mid Troposphere",     pMin: 500, pMax: 700,  kmRange: "3–5.5 km",  color: "#2ecc71" },
  { id: "upper", name: "Upper Troposphere",   pMin: 300, pMax: 500,  kmRange: "5.5–9 km",  color: "#9b59b6" },
  { id: "tropo", name: "Tropopause Layer",    pMin: 100, pMax: 300,  kmRange: "9–12 km",   color: "#e74c3c" },
];

function computeLayerStats(d, layer) {
  const p = d.profile.pressure, T = d.profile.temperature,
        Td = d.profile.dewpoint, spd = d.profile.speed, H = d.profile.height;
  const idx = p.reduce((acc, pi, i) => { if (pi <= layer.pMax && pi >= layer.pMin) acc.push(i); return acc; }, []);
  if (!idx.length) return null;
  const avg = (arr, ix) => { const v = ix.map(i => arr[i]).filter(v => v != null && isFinite(v)); return v.length ? v.reduce((a,b)=>a+b,0)/v.length : null; };
  const avgT = avg(T, idx), avgTd = avg(Td, idx), avgSpd = avg(spd, idx);
  const avgRH = avgT != null && avgTd != null
    ? Math.round(100 * Math.exp(17.625 * avgTd / (243.04 + avgTd)) / Math.exp(17.625 * avgT / (243.04 + avgT))) : null;
  let lapse = null;
  if (idx.length >= 2) {
    const i0 = idx[0], i1 = idx[idx.length-1];
    const dH = (H[i1] - H[i0]) / 1000;
    lapse = dH > 0 ? (T[i0] - T[i1]) / dH : null;
  }
  const moisture = avgRH != null ? (avgRH >= 80 ? "saturated" : avgRH >= 60 ? "moist" : "dry") : "dry";
  const stability = lapse != null ? (lapse > 9.8 ? "unstable" : "stable") : "stable";
  return { avgT, avgSpd, avgRH, lapse, moisture, stability, pRange: `${layer.pMin}–${layer.pMax} hPa` };
}

function drawAtmoLayers(d) {
  // คำอธิบาย 5 ระดับ อยู่ใน zone-atmo (Row 2 Col 1) — ไม่ append ใน zone-skewt อีก
  const box = document.getElementById("atmo-layers");
  if (!box) return;
  box.innerHTML = "";
  ATM_LAYERS.forEach(layer => {
    const s = computeLayerStats(d, layer);
    if (!s) return;
    const Td = s.avgT != null ? cvtTemp(s.avgT).toFixed(1) : "—";
    const Sw = s.avgSpd != null ? cvtWind(s.avgSpd).toFixed(0) : "—";
    const div = document.createElement("div");
    div.className = "atmo-layer";
    div.style.cssText = `border-left:4px solid ${layer.color};border-radius:9px;padding:9px 12px;background:var(--panel-2);border:1px solid var(--border);font-size:12.5px;margin-bottom:5px`;
    div.innerHTML = `<div style="display:flex;justify-content:space-between;margin-bottom:4px">
      <span style="font-weight:700;font-size:13px;color:${layer.color}">${layer.name}</span>
      <span style="font-size:11px;color:var(--text-soft)">${s.pRange} | ${layer.kmRange}</span></div>
      <div style="display:flex;gap:12px;flex-wrap:wrap;color:var(--text-soft)">
        <span>T avg: <b style="color:var(--text)">${Td} ${tempUnit()}</b></span>
        <span>RH: <b style="color:var(--text)">${s.avgRH != null ? s.avgRH+"%" : "—"}</b></span>
        <span>Wind: <b style="color:var(--text)">${Sw} ${windUnit()}</b></span>
        ${s.lapse != null ? `<span>Lapse: <b style="color:var(--text)">${s.lapse.toFixed(1)} °C/km</b></span>` : ""}
        <span style="font-size:10px;font-weight:700;padding:2px 7px;border-radius:6px;color:#fff;background:${s.moisture==="saturated"?"#16a34a":s.moisture==="moist"?"#2980b9":"#e67e22"}">${s.moisture}</span>
        <span style="font-size:10px;font-weight:700;padding:2px 7px;border-radius:6px;color:#fff;background:${s.stability==="unstable"?"#c0392b":"#7f8c8d"}">${s.stability}</span>
      </div>`;
    box.appendChild(div);
  });
}

// ============================================================
// Tourist Intelligence Card
// ============================================================
function _drawTouristCard(el, idx, ai, d) {
  let score = 100;
  const cape = idx.CAPE ?? 0, ki = idx.K_INDEX ?? 20;
  const pwat = idx.PWAT ?? 30, li = idx.LI ?? 0;
  const wind = idx.SURFACE_WIND_KT ?? 5;

  if (cape > 2000) score -= 40; else if (cape > 1000) score -= 25; else if (cape > 500) score -= 12;
  if (ki > 38) score -= 30; else if (ki > 32) score -= 18; else if (ki > 25) score -= 8;
  if (pwat > 55) score -= 15; else if (pwat > 45) score -= 8;
  if (li < -4) score -= 20; else if (li < -2) score -= 10;
  if (wind > 35) score -= 15; else if (wind > 25) score -= 6;
  score = Math.max(5, Math.min(100, Math.round(score)));

  const lvl = score >= 70 ? "good" : score >= 45 ? "warn" : "bad";
  const ringColor = lvl === "good" ? "#16a34a" : lvl === "warn" ? "#d97706" : "#dc2626";
  const headline = score >= 70 ? "สภาพอากาศเหมาะท่องเที่ยว" :
                   score >= 45 ? "ควรระมัดระวัง — มีโอกาสฝน" : "ไม่แนะนำกิจกรรมกลางแจ้ง";

  const acts = [
    { name: "ชายหาด / ว่ายน้ำ", icon: "🏖", ok: score >= 70 && wind < 20 },
    { name: "เดินป่า / ไต่เขา",  icon: "🥾", ok: score >= 60 },
    { name: "ท่องเที่ยวในเมือง", icon: "🏛", ok: score >= 40 },
    { name: "ปั่นจักรยาน",       icon: "🚴", ok: score >= 65 && wind < 25 },
    { name: "ถ่ายภาพกลางแจ้ง",  icon: "📷", ok: score >= 50 },
    { name: "อาหารกลางแจ้ง",    icon: "🍽", ok: score >= 55 },
  ];

  const tips = [];
  if (cape > 1000) tips.push("บรรยากาศไม่เสถียรสูง — หลีกเลี่ยงพื้นที่โล่งช่วงบ่าย");
  if (ki > 35)     tips.push("K-Index สูง — โอกาสเกิดพายุฝนฟ้าคะนองสูง");
  if (pwat > 50)   tips.push("ความชื้นสูงมาก — ควรพกร่มและเสื้อกันฝน");
  if (wind > 25)   tips.push("ลมแรง — ระวังกิจกรรมทางน้ำและกิจกรรมบนที่สูง");
  if (li < -2)     tips.push("บรรยากาศไม่เสถียร — ฝนอาจตกฉับพลัน");
  if (score >= 70) tips.push("สภาพอากาศดี เหมาะแก่การท่องเที่ยวกลางแจ้ง");

  const r = 36, circ = 2 * Math.PI * r;
  const dash = (score / 100) * circ;

  const stats = [
    { icon: "⛅", label: "โอกาสฝน (AI Score)", val: ai.score >= 60 ? "สูง" : ai.score >= 35 ? "ปานกลาง" : "ต่ำ",
      note: ai.score + "/100", cls: ai.score >= 60 ? "warn" : ai.score >= 35 ? "" : "good" },
    { icon: "💧", label: "ความชื้นรวม (PWAT)", val: pwat.toFixed(0) + " mm",
      note: pwat > 50 ? "สูงมาก" : pwat > 35 ? "ปานกลาง" : "ต่ำ", cls: pwat > 50 ? "warn" : "" },
    { icon: "🌡", label: "ความไม่เสถียร (CAPE)", val: cape.toFixed(0) + " J/kg",
      note: cape > 1000 ? "ไม่เสถียร" : cape > 500 ? "ปานกลาง" : "เสถียร",
      cls: cape > 1000 ? "bad" : cape > 500 ? "warn" : "good" },
    { icon: "💨", label: "ลมพื้นผิว", val: cvtWind(wind).toFixed(0) + " " + windUnit(),
      note: wind > 30 ? "แรงมาก" : wind > 20 ? "ปานกลาง" : "เบา",
      cls: wind > 30 ? "bad" : wind > 20 ? "warn" : "good" },
    { icon: "⛈", label: "ความเสี่ยงพายุ (K-Index)", val: ki.toFixed(1) + " °C",
      note: ki > 35 ? "เสี่ยงสูง" : ki > 25 ? "ปานกลาง" : "ต่ำ",
      cls: ki > 35 ? "bad" : ki > 25 ? "warn" : "good" },
    { icon: "☁", label: "ฐานเมฆ (LCL)", val: idx.LCL_p ? idx.LCL_p.toFixed(0) + " hPa" : "—",
      note: idx.LCL_p ? (idx.LCL_p > 900 ? "เมฆต่ำ" : "ปกติ") : "—",
      cls: idx.LCL_p && idx.LCL_p > 900 ? "warn" : "" },
  ];

  el.innerHTML =
    `<div class="tourist-header">
      <div class="tourist-score-ring">
        <svg viewBox="0 0 90 90">
          <circle cx="45" cy="45" r="${r}" fill="none" stroke="var(--border)" stroke-width="8"/>
          <circle cx="45" cy="45" r="${r}" fill="none" stroke="${ringColor}" stroke-width="8"
            stroke-dasharray="${dash.toFixed(1)} ${circ.toFixed(1)}"
            stroke-dashoffset="${(circ/4).toFixed(1)}"
            stroke-linecap="round" transform="rotate(-90 45 45)"/>
        </svg>
        <div class="tourist-score-val">
          <span class="tsv-num" style="color:${ringColor}">${score}</span>
          <span class="tsv-lbl">Tourism</span>
        </div>
      </div>
      <div class="tourist-title">
        <h3 style="color:${ringColor}">${headline}</h3>
        <p>${tips.length ? tips.slice(0,2).join(" · ") : "สภาพอากาศเหมาะสมสำหรับกิจกรรมกลางแจ้ง"}</p>
      </div>
    </div>
    <div class="tourist-grid">
      ${stats.map(s =>
        `<div class="tourist-stat ${s.cls}">
          <div class="ts-icon">${s.icon}</div>
          <div class="ts-label">${s.label}</div>
          <div class="ts-val">${s.val}</div>
          <div class="ts-note">${s.note}</div>
        </div>`).join("")}
    </div>
    <div style="margin-bottom:10px">
      <div style="font-size:12px;color:var(--text-soft);margin-bottom:8px;font-weight:600">กิจกรรมที่แนะนำวันนี้</div>
      <div class="tourist-activities">
        ${acts.map(a =>
          `<div class="act-badge ${a.ok ? "ok" : score >= 45 ? "warn" : "no"}">
            <span>${a.icon}</span><span>${a.name}</span>
            <span style="font-size:11px">${a.ok ? "✓" : score >= 45 ? "⚠" : "✗"}</span>
          </div>`).join("")}
      </div>
    </div>
    ${tips.length >= 3 ? `<div class="tourist-tips"><b>คำแนะนำ:</b> ${tips.slice(2).join(" · ")}</div>` : ""}`;
}

// ============================================================
// Role-based KPI Strip (Session 7 + Session 9 — rainmaking role)
// ============================================================
function drawRoleWidget(d) {
  const role = window._VAI_ROLE || "rainmaking";
  // ใช้ zone-role (full-width, อยู่ก่อน zone-atmo ใน DOM)
  const zone = document.getElementById("zone-role");

  if (role === "meteorologist" || role === "researcher") {
    if (zone) zone.style.display = "none";
    return;
  }
  if (!zone) return;
  zone.style.display = "";   // แสดง
  zone.className = "";
  zone.style.gridColumn = "1 / -1";
  zone.innerHTML = "";
  const strip = zone;   // alias เพื่อให้โค้ดด้านล่างทำงานได้เหมือนเดิม
  strip.style.display = "flex";

  const idx = d.indices;
  const rm = d.rainmaking || {};
  const ai = d.ai || {};
  const score = ai.score || 0;

  // ---- Tourist Dashboard ----
  if (role === "tourist") {
    strip.className = "tourist-card";
    strip.style.padding = "";
    strip.style.display = "block";
    _drawTouristCard(strip, idx, ai, d);
    return;
  }

  // ---- Farmer / General ----
  if (role === "farmer" || role === "general") {
    const lvl = score >= 60 ? "high" : score >= 35 ? "mid" : "low";
    const roleMsg = {
      farmer:  ["ระวังน้ำท่วมแปลง เตรียมระบาย", "ติดตามสถานการณ์ต่อเนื่อง", "สภาพดีสำหรับการเกษตร"],
      general: ["โอกาสฝนสูง — เตรียมรับมือ", "โอกาสฝนปานกลาง — ติดตาม", "ท้องฟ้าแจ่มใส"],
    };
    const msgs = roleMsg[role] || roleMsg.general;
    const scoreColor = lvl === "high" ? "var(--good)" : lvl === "mid" ? "var(--warn)" : "var(--bad)";
    strip.style.padding = "0"; strip.style.display = "flex";
    strip.innerHTML = `<div class="traffic-card">
      <div class="traffic-light">
        <div class="tl-dot red-l${lvl === "high" ? " active" : ""}">H</div>
        <div class="tl-dot yellow-l${lvl === "mid" ? " active" : ""}">M</div>
        <div class="tl-dot green-l${lvl === "low" ? " active" : ""}">L</div>
      </div>
      <div class="traffic-text">
        <h3 style="color:${scoreColor}">${lvl === "high" ? "โอกาสฝนสูง" : lvl === "mid" ? "โอกาสฝนปานกลาง" : "โอกาสฝนต่ำ"} (${score}/100)</h3>
        <p>${msgs[lvl === "high" ? 0 : lvl === "mid" ? 1 : 2]}<br>
        <small style="color:var(--text-soft)">CAPE: ${idx.CAPE?.toFixed(0) ?? "—"} J/kg | PWAT: ${idx.PWAT?.toFixed(0) ?? "—"} mm | K: ${idx.K_INDEX?.toFixed(1) ?? "—"}</small></p>
      </div>
    </div>`;
    return;
  }

  // ---- Rainmaking (เจ้าหน้าที่ฝนหลวง) ----
  if (role === "rainmaking") {
    const f0p = idx.FREEZING_0C?.pressure_hpa, f10p = idx.FREEZING_NEG10C?.pressure_hpa;
    const shear = idx.SHEAR_SFC6KM_KT;
    const cards = [
      { icon: "🌧", label: "CAPE", val: idx.CAPE != null ? `${cvtEnergy(idx.CAPE).toFixed(0)} ${energyUnit()}` : "—",
        status: idx.CAPE >= 1000 ? "ไม่เสถียร (ดี)" : idx.CAPE >= 500 ? "ปานกลาง" : "เสถียร",
        g: idx.CAPE >= 1000 ? "good" : idx.CAPE >= 500 ? "warn" : "bad" },
      { icon: "💧", label: "PWAT", val: idx.PWAT != null ? `${idx.PWAT.toFixed(0)} mm` : "—",
        status: idx.PWAT >= 40 ? "ความชื้นสูง (ดี)" : idx.PWAT >= 25 ? "ปานกลาง" : "ต่ำ",
        g: idx.PWAT >= 40 ? "good" : idx.PWAT >= 25 ? "warn" : "bad" },
      { icon: "❄", label: "0°C Level", val: f0p ? `${cvtPressure(f0p).toFixed(0)} ${pressureUnit()}` : "—",
        status: f0p ? (f0p < 700 ? "ปลอดภัยบิน" : "ระมัดระวัง") : "—",
        g: f0p ? (f0p < 700 ? "good" : "warn") : "" },
      { icon: "💨", label: "Shear SFC-6km", val: shear != null ? `${cvtWind(shear).toFixed(0)} ${windUnit()}` : "—",
        status: shear != null ? (shear <= 25 ? "เหมาะสม" : shear <= 40 ? "ปานกลาง" : "สูง") : "—",
        g: shear != null ? (shear <= 25 ? "good" : shear <= 40 ? "warn" : "bad") : "" },
      { icon: "🧪", label: "สารเพาะฝน", val: rm.chemical || "NaCl",
        status: rm.technique || "—", g: "" },
    ];
    cards.forEach(c => {
      const div = document.createElement("div");
      div.className = `role-kpi-card ${c.g}`;
      div.innerHTML = `<div class="rk-icon">${c.icon}</div><div class="rk-label">${c.label}</div><div class="rk-val">${c.val}</div><div class="rk-status ${c.g}">${c.status}</div>`;
      strip.appendChild(div);
    });
    return;
  }

  // ---- Factory ----
  if (role === "factory") {
    const pwatG = idx.PWAT >= 40 ? "good" : idx.PWAT >= 25 ? "warn" : "bad";
    const cards = [
      { icon: "💧", label: "PWAT", val: idx.PWAT != null ? `${idx.PWAT.toFixed(0)} mm` : "—",
        status: idx.PWAT >= 40 ? "ความชื้นสูง" : "ความชื้นต่ำ", g: pwatG },
      { icon: "💨", label: "Wind", val: idx.SURFACE_WIND_KT != null ? `${cvtWind(idx.SURFACE_WIND_KT).toFixed(0)} ${windUnit()}` : "—",
        status: idx.SURFACE_WIND_KT < 20 ? "ปกติ" : "แรง",
        g: idx.SURFACE_WIND_KT < 20 ? "good" : idx.SURFACE_WIND_KT < 35 ? "warn" : "bad" },
      { icon: "📊", label: "K-Index", val: idx.K_INDEX != null ? `${idx.K_INDEX.toFixed(1)} °C` : "—",
        status: idx.K_INDEX >= 35 ? "เสี่ยงพายุ" : "ปกติ",
        g: idx.K_INDEX >= 35 ? "bad" : idx.K_INDEX >= 25 ? "warn" : "good" },
      { icon: "☁", label: "LCL", val: idx.LCL_p != null ? `${cvtPressure(idx.LCL_p).toFixed(0)} ${pressureUnit()}` : "—",
        status: idx.LCL_p <= 950 ? "เมฆต่ำ-มลพิษ" : "ปกติ",
        g: idx.LCL_p <= 950 ? "warn" : "good" },
    ];
    cards.forEach(c => {
      const div = document.createElement("div");
      div.className = `role-kpi-card ${c.g}`;
      div.innerHTML = `<div class="rk-icon">${c.icon}</div><div class="rk-label">${c.label}</div><div class="rk-val">${c.val}</div><div class="rk-status ${c.g}">${c.status}</div>`;
      strip.appendChild(div);
    });
  }
}

// ---------- KPI focus ตามบทบาท ----------
let ROLE_FOCUS = [];

// ---------- Role Layout ----------
function applyRoleLayout(role) {
  const skewt   = document.getElementById("zone-skewt");
  const kpiHodo = document.getElementById("zone-kpi-hodo");
  const aiPanel = document.getElementById("zone-ai");
  const qnav    = document.getElementById("quick-nav");
  if (!skewt) return;
  const simpleRoles = ["farmer", "general", "tourist", "factory"];
  const proRoles    = ["rainmaking", "meteorologist", "researcher"];
  if (simpleRoles.includes(role)) {
    skewt.style.display = "none"; kpiHodo.style.display = "none";
    if (aiPanel) aiPanel.style.display = "none";
    if (qnav)   qnav.style.display = "none";
  } else {
    skewt.style.display = ""; kpiHodo.style.display = "";
    if (aiPanel) aiPanel.style.display = "";
    if (qnav)   qnav.style.display = proRoles.includes(role) ? "flex" : "none";
  }
}

// ---------- เริ่มต้น ----------
async function init() {
  if (window.VAI) await window.VAI.boot();
  applyI18n();

  try {
    const r = await fetch("/api/roles");
    const j = await r.json();
    const cur = j.current;
    const badge = document.getElementById("role-badge");
    window._VAI_ROLE = cur || "rainmaking";
    applyRoleLayout(window._VAI_ROLE);
    if (cur) {
      const def = j.roles.find(x => x.id === cur);
      ROLE_FOCUS = def ? def.focus : [];
      if (badge && def) { badge.textContent = def.label[window.VAI.getLang()] || cur; badge.style.display = "inline-block"; }
    } else if (badge) { badge.style.display = "none"; }
  } catch (e) { /* ไม่มี role */ }

  try {
    const res = await fetch("/api/stations");
    const j = await res.json();
    const sel = document.getElementById("sel-station");
    j.stations.forEach(s => {
      const o = document.createElement("option");
      o.value = s.id; o.textContent = `${s.name} (${s.id})`; sel.appendChild(o);
    });
  } catch (e) { toast(t("err_stations")); }

  const d = new Date(); d.setDate(d.getDate() - 1);
  document.getElementById("sel-date").value = d.toISOString().slice(0, 10);

  document.getElementById("btn-analyze").addEventListener("click", analyze);
  const retryBtn = document.getElementById("btn-retry");
  if (retryBtn) retryBtn.addEventListener("click", analyze);
  document.getElementById("btn-theme").addEventListener("click", toggleTheme);
  document.getElementById("btn-lang").addEventListener("click", toggleLang);

  // โหลดผลวิเคราะห์ล่าสุดอัตโนมัติ (Wyoming หรือ Upload)
  tryLastUpload();
}

document.addEventListener("DOMContentLoaded", init);
