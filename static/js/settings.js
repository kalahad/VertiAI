/* ============================================================
   VertiAI - Settings Logic (Session 5)
   เลือกบทบาท -> /api/login | ปรับเกณฑ์เฉพาะถิ่น -> /api/thresholds
   ============================================================ */
const T = (k) => window.VAI.t(k);
const TH_KEYS = ["RH_min", "WS_min", "WS_max", "KI_min", "KI_max"];
const TH_LABEL = { RH_min: "rh_min", WS_min: "ws_min", WS_max: "ws_max", KI_min: "ki_min", KI_max: "ki_max" };
let SELECTED_ROLE = null;

function setMsg(id, text, ok) {
  const el = document.getElementById(id);
  el.textContent = text;
  el.className = "status-msg " + (ok ? "ok" : "err");
}

// ---------- บทบาท ----------
async function loadRoles() {
  let j;
  try {
    const res = await fetch("/api/roles");
    j = await res.json();
  } catch (e) {
    document.getElementById("role-cards").innerHTML =
      `<div class="empty err">${T("err_load")}</div>`;
    return;
  }
  const lang = window.VAI.getLang();
  SELECTED_ROLE = j.current;
  const box = document.getElementById("role-cards");
  box.innerHTML = "";
  j.roles.forEach(r => {
    const card = document.createElement("div");
    card.className = "role-card" + (r.id === SELECTED_ROLE ? " sel" : "");
    card.dataset.role = r.id;
    card.innerHTML =
      `<div class="rc-name">${r.label[lang] || r.label.th}</div>` +
      `<div class="rc-desc">${T("role_" + r.id + "_d")}</div>`;
    card.addEventListener("click", () => {
      SELECTED_ROLE = r.id;
      document.querySelectorAll(".role-card").forEach(c => c.classList.remove("sel"));
      card.classList.add("sel");
    });
    box.appendChild(card);
  });
  updateBadge();
}

function updateBadge() {
  const badge = document.getElementById("role-badge");
  if (!SELECTED_ROLE) { badge.style.display = "none"; return; }
  badge.textContent = T("role_" + SELECTED_ROLE);
  badge.style.display = "inline-block";
}

async function saveRole() {
  if (!SELECTED_ROLE) return;
  try {
    const res = await fetch("/api/login", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role: SELECTED_ROLE }),
    });
    const j = await res.json();
    if (!j.ok) { setMsg("role-status", j.error || "error", false); return; }
    setMsg("role-status", T("role_saved"), true);
    updateBadge();
  } catch (e) { setMsg("role-status", "error", false); }
}

// ---------- เกณฑ์เฉพาะถิ่น ----------
async function loadThresholds() {
  const box = document.getElementById("threshold-box");
  let j;
  try {
    const res = await fetch("/api/thresholds");
    j = await res.json();
  } catch (e) {
    box.innerHTML = `<div class="empty err">${T("err_load")}</div>`;
    return;
  }
  box.innerHTML = "";
  if (!j.items || !j.items.length) {
    box.innerHTML = `<div class="empty">${T("err_no_data")}</div>`;
    return;
  }
  j.items.forEach(item => box.appendChild(renderRegion(item)));
}

function renderRegion(item) {
  const wrap = document.createElement("div");
  wrap.style.marginBottom = "18px";
  const inputs = TH_KEYS
    .filter(k => k in item.defaults)   // แสดงเฉพาะคีย์ที่ region นั้นใช้จริง
    .map(k => {
      const def = item.defaults[k];
      const ov = item.override[k];
      return `<div class="field">
        <label>${T(TH_LABEL[k])}</label>
        <input type="number" step="0.1" data-key="${k}"
          value="${ov != null ? ov : ""}" placeholder="${def}">
        <span class="def-note">${T("default_prefix")}: ${def}</span>
      </div>`;
    }).join("");

  wrap.innerHTML =
    `<div style="font-weight:600;margin-bottom:6px">${item.name}</div>` +
    `<div class="row" data-region="${item.region}">${inputs}` +
    `<button class="btn primary btn-save-th" type="button">${T("save")}</button>` +
    `<button class="btn btn-reset-th" type="button">${T("reset")}</button>` +
    `<span class="status-msg th-status"></span></div>`;

  const rowEl = wrap.querySelector(".row");
  wrap.querySelector(".btn-save-th").addEventListener("click", () => saveThreshold(rowEl, false));
  wrap.querySelector(".btn-reset-th").addEventListener("click", () => saveThreshold(rowEl, true));
  return wrap;
}

async function saveThreshold(rowEl, reset) {
  const region = rowEl.dataset.region;
  const values = {};
  rowEl.querySelectorAll("input[data-key]").forEach(inp => {
    if (reset) { inp.value = ""; values[inp.dataset.key] = null; }
    else if (inp.value !== "") values[inp.dataset.key] = parseFloat(inp.value);
  });
  const statusEl = rowEl.querySelector(".th-status");
  try {
    const res = await fetch("/api/thresholds", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ region, values }),
    });
    const j = await res.json();
    if (!j.ok) { statusEl.textContent = j.error || "error"; statusEl.className = "status-msg err"; return; }
    statusEl.textContent = reset ? T("threshold_reset") : T("threshold_saved");
    statusEl.className = "status-msg ok";
  } catch (e) { statusEl.textContent = "error"; statusEl.className = "status-msg err"; }
}

// ---------- Unit Settings ----------
const UNIT_DEFAULTS = { wind: "kt", height: "m", temp: "c", pressure: "hpa", energy: "jkg" };
const UNIT_KEY = "VAI_units";

function loadUnitPrefs() {
  let prefs;
  try { prefs = JSON.parse(localStorage.getItem(UNIT_KEY) || "{}"); } catch { prefs = {}; }
  const merged = { ...UNIT_DEFAULTS, ...prefs };
  Object.entries(merged).forEach(([unit, val]) => {
    const radio = document.querySelector(`input[name="unit_${unit}"][value="${val}"]`);
    if (radio) radio.checked = true;
   });
}

function saveUnitPrefs() {
  const prefs = {};
  ["wind", "height", "temp", "pressure", "energy"].forEach(unit => {
    const el = document.querySelector(`input[name="unit_${unit}"]:checked`);
    if (el) prefs[unit] = el.value;
  });
  localStorage.setItem(UNIT_KEY, JSON.stringify(prefs));
  const s = document.getElementById("unit-status");
  s.textContent = "บันทึกหน่วยแล้ว — จะมีผลเมื่อเปิดแดชบอร์ด";
  s.className = "status-msg ok";
}

function resetUnitPrefs() {
  localStorage.setItem(UNIT_KEY, JSON.stringify(UNIT_DEFAULTS));
  loadUnitPrefs();
  const s = document.getElementById("unit-status");
  s.textContent = "รีเซ็ตเป็นค่าเริ่มต้นแล้ว";
  s.className = "status-msg ok";
}

// ---------- init ----------
async function init() {
  await window.VAI.boot();
  await loadRoles();
  await loadThresholds();
  loadUnitPrefs();
  document.getElementById("btn-save-role").addEventListener("click", saveRole);
  document.getElementById("btn-save-units").addEventListener("click", saveUnitPrefs);
  document.getElementById("btn-reset-units").addEventListener("click", resetUnitPrefs);
  document.getElementById("btn-lang").addEventListener("click", async () => {
    await window.VAI.toggleLang(); await loadRoles(); await loadThresholds();
  });
  document.getElementById("btn-theme").addEventListener("click", () => window.VAI.toggleTheme());
}
document.addEventListener("DOMContentLoaded", init);
