/* ============================================================
   VertiAI - Data Portal Logic (Session 5)
   อัปโหลดไฟล์/ข้อความ -> /api/upload | สืบค้นประวัติ -> /api/history
   ============================================================ */
const T = (k) => window.VAI.t(k);
const REGIONS = [
  { id: "tung_kula", th: "ทุ่งกุลาร้องไห้", en: "Tung Kula (NE)" },
  { id: "bang_lang", th: "เขื่อนบางลาง", en: "Bang Lang (South)" },
  { id: "korat", th: "นครราชสีมา", en: "Korat (NE)" },
  { id: "sa_kaeo", th: "สระแก้ว", en: "Sa Kaeo (East)" },
  { id: "to_daeng", th: "ป่าพรุโต๊ะแดง", en: "To Daeng (South)" },
];

function setMsg(id, text, ok) {
  const el = document.getElementById(id);
  el.textContent = text;
  el.className = "status-msg " + (ok ? "ok" : "err");
}

// ---------- อัปโหลด ----------
async function doUpload() {
  const file = document.getElementById("up-file").files[0];
  const text = document.getElementById("up-text").value.trim();
  const region = document.getElementById("up-region").value;
  if (!file && !text) { setMsg("up-status", T("upload_fail"), false); return; }

  const url = "/api/upload" + (region ? `?region=${region}` : "");
  let opts;
  if (file) {
    const fd = new FormData(); fd.append("file", file);
    opts = { method: "POST", body: fd };
  } else {
    opts = { method: "POST", headers: { "Content-Type": "text/plain" }, body: text };
  }
  setMsg("up-status", T("loading"), true);
  try {
    const res = await fetch(url, opts);
    const j = await res.json();
    if (!j.ok) { setMsg("up-status", j.error || T("upload_fail"), false); return; }
    setMsg("up-status", T("upload_ok"), true);
    renderResult(j);
  } catch (e) { setMsg("up-status", T("upload_fail"), false); }
}

// แสดงสรุปดัชนีและ AI Assessment หลังอัปโหลด
function renderResult(j) {
  const idx = j.indices || {};
  const ai = j.ai || {};
  const rm = j.rainmaking || {};
  const box = document.getElementById("up-result");

  const scoreColor = ai.score >= 60 ? "var(--good)" : ai.score >= 35 ? "var(--warn)" : "var(--bad)";
  const lvlLabel = ai.score >= 60 ? "สูง" : ai.score >= 35 ? "ปานกลาง" : "ต่ำ";

  const rows = [
    ["CAPE", idx.CAPE != null ? idx.CAPE.toFixed(0) + " J/kg" : "—"],
    ["CIN",  idx.CIN  != null ? idx.CIN.toFixed(0)  + " J/kg" : "—"],
    ["Lifted Index", idx.LI != null ? idx.LI.toFixed(1) + " °C" : "—"],
    ["PWAT", idx.PWAT != null ? idx.PWAT.toFixed(0) + " mm" : "—"],
    ["K-Index", idx.K_INDEX != null ? idx.K_INDEX.toFixed(1) + " °C" : "—"],
    ["LCL", idx.LCL_p != null ? idx.LCL_p.toFixed(0) + " hPa" : "—"],
    ["LFC", idx.LFC_p != null ? idx.LFC_p.toFixed(0) + " hPa" : "—"],
    ["EL",  idx.EL_p  != null ? idx.EL_p.toFixed(0)  + " hPa" : "—"],
  ];

  const reasons = (ai.reasons || []).map(r =>
    `<div style="display:flex;gap:8px;align-items:center;padding:5px 9px;border-radius:8px;
       background:var(--panel-2);border:1px solid var(--border);font-size:12.5px;margin-bottom:4px">
      <span style="width:9px;height:9px;border-radius:50%;flex:none;
        background:${r.passed ? "var(--good)" : "var(--bad)"}"></span>
      <span style="flex:1">${r.index}</span>
      <span style="color:var(--text-soft)">${r.value_text}</span>
    </div>`
  ).join("");

  box.innerHTML = `
    <div class="panel" style="margin:0">
      <div style="display:flex;align-items:center;gap:18px;flex-wrap:wrap;margin-bottom:14px">
        <div style="text-align:center">
          <div style="font-size:42px;font-weight:900;color:${scoreColor};line-height:1">${ai.score ?? "—"}</div>
          <div style="font-size:13px;color:var(--text-soft)">/100</div>
        </div>
        <div>
          <div style="font-size:22px;font-weight:800;color:${scoreColor}">โอกาสฝน${lvlLabel}</div>
          <div style="font-size:13px;color:var(--text-soft);margin-top:2px">${ai.summary_th || ""}</div>
        </div>
      </div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:8px;margin-bottom:12px">
        ${rows.map(r => `<div style="padding:8px 10px;border-radius:9px;background:var(--panel-2);border:1px solid var(--border)">
          <div style="font-size:11px;color:var(--text-soft)">${r[0]}</div>
          <div style="font-size:16px;font-weight:700">${r[1]}</div>
        </div>`).join("")}
      </div>
      ${reasons ? `<div style="margin-bottom:12px">${reasons}</div>` : ""}
      ${rm.technique ? `<div style="padding:10px 12px;border-radius:10px;background:var(--accent-soft);font-size:12.5px">
        <b style="color:var(--accent)">เทคนิคฝนหลวง:</b> ${rm.technique}<br>${rm.note || ""}
      </div>` : ""}
      <div style="margin-top:14px;text-align:center">
        <a class="btn primary" href="/" style="text-decoration:none">ดูผลเต็มรูปแบบบนแดชบอร์ด &rarr;</a>
      </div>
    </div>`;
}

// ---------- ประวัติ ----------
async function doHistory() {
  const station = document.getElementById("h-station").value;
  const year = document.getElementById("h-year").value;
  const qs = new URLSearchParams();
  if (station) qs.set("station", station);
  if (year) qs.set("year", year);
  try {
    const res = await fetch("/api/history?" + qs.toString());
    const j = await res.json();
    renderHistory(j.items || []);
  } catch (e) {
    document.getElementById("history-box").innerHTML =
      `<div class="empty err">${T("err_load")}</div>`;
  }
}

function renderHistory(items) {
  const box = document.getElementById("history-box");
  if (!items.length) {
    box.innerHTML = `<div class="empty">${T("no_history")}</div>`;
    return;
  }
  box.innerHTML =
    `<table class="tbl"><thead><tr>` +
    `<th>${T("col_station")}</th><th>${T("col_datetime")}</th><th>${T("col_created")}</th><th style="width:60px"></th>` +
    `</tr></thead><tbody>` +
    items.map(it =>
      `<tr data-dt="${it.datetime_utc}" data-st="${it.station}">`+
      `<td>${it.station}</td><td>${it.datetime_utc}</td><td>${it.created_at}</td>`+
      `<td><button class="btn-del" title="ลบ" onclick="deleteRow(this)">✕</button></td></tr>`
    ).join("") +
    `</tbody></table>`;
}

async function deleteRow(btn) {
  const row = btn.closest('tr');
  const dt  = row.dataset.dt;
  const st  = row.dataset.st;
  if (!confirm(`ลบ ${st} / ${dt} ออกจากแคช?`)) return;
  btn.disabled = true; btn.textContent = '...';
  try {
    const res = await fetch(`/api/history?datetime_utc=${encodeURIComponent(dt)}&station=${st}`, { method: 'DELETE' });
    const j = await res.json();
    if (j.ok) { row.style.opacity='0'; setTimeout(()=>row.remove(),300); }
    else { btn.disabled=false; btn.textContent='✕'; alert(j.error||'ลบไม่สำเร็จ'); }
  } catch(e) { btn.disabled=false; btn.textContent='✕'; }
}

// ---------- init ----------
async function init() {
  await window.VAI.boot();
  const lang = window.VAI.getLang();

  // เติม region ในกล่องอัปโหลด
  const upRegion = document.getElementById("up-region");
  REGIONS.forEach(r => {
    const o = document.createElement("option");
    o.value = r.id; o.textContent = r[lang] || r.th;
    upRegion.appendChild(o);
  });

  // เติมสถานีในกล่องประวัติ
  try {
    const res = await fetch("/api/stations");
    const j = await res.json();
    const sel = document.getElementById("h-station");
    j.stations.forEach(s => {
      const o = document.createElement("option");
      o.value = s.id; o.textContent = `${lang === "en" ? s.name_en : s.name} (${s.id})`;
      sel.appendChild(o);
    });
  } catch (e) {
    setMsg("up-status", T("err_stations"), false);
  }

  // ปีย้อนหลัง (พ.ศ. 2563-2567 = ค.ศ. 2020-2024)
  const ySel = document.getElementById("h-year");
  for (let y = 2024; y >= 2020; y--) {
    const o = document.createElement("option");
    o.value = String(y); o.textContent = `${y} / พ.ศ.${y + 543}`;
    ySel.appendChild(o);
  }

  document.getElementById("btn-upload").addEventListener("click", doUpload);
  document.getElementById("btn-history").addEventListener("click", doHistory);
  document.getElementById("btn-lang").addEventListener("click", () => window.VAI.toggleLang());
  document.getElementById("btn-theme").addEventListener("click", () => window.VAI.toggleTheme());
  doHistory();   // โหลดประวัติเริ่มต้น
}
document.addEventListener("DOMContentLoaded", init);
