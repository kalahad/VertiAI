/* ============================================================
   VertiAI - Shared i18n + Theme (Session 5)
   โหลด /static/i18n/{lang}.json แล้วใช้ร่วมทุกหน้า สลับภาษา/ธีมโดยไม่ reload
   จดจำค่าใน localStorage ให้สถานะคงเดิมข้ามหน้า
   ============================================================ */
window.VAI = (function () {
  let LANG = localStorage.getItem("vai_lang") || "th";
  let DICT = {};

  async function load() {
    try {
      const r = await fetch(`/static/i18n/${LANG}.json`, { cache: "no-cache" });
      DICT = await r.json();
    } catch (e) { DICT = {}; }
  }
  function t(k) { return (DICT && DICT[k]) || k; }

  // แทนข้อความตาม data-i18n (textContent) และ data-i18n-ph (placeholder)
  function apply(root) {
    (root || document).querySelectorAll("[data-i18n]").forEach(el => {
      el.textContent = t(el.dataset.i18n);
    });
    (root || document).querySelectorAll("[data-i18n-ph]").forEach(el => {
      el.placeholder = t(el.dataset.i18nPh);
    });
    const lb = document.getElementById("btn-lang");
    if (lb) lb.textContent = t("lang_btn");
  }
  async function setLang(l) {
    LANG = l; localStorage.setItem("vai_lang", l);
    document.documentElement.lang = l;
    await load(); apply();
  }
  async function toggleLang() { await setLang(LANG === "th" ? "en" : "th"); }
  function getLang() { return LANG; }

  // ---------- ธีม ----------
  function initTheme() {
    const th = localStorage.getItem("vai_theme") || "light";
    document.documentElement.setAttribute("data-theme", th);
    const bt = document.getElementById("btn-theme");
    if (bt) bt.textContent = th === "dark" ? "☀️" : "🌙";
  }
  function toggleTheme() {
    const dark = document.documentElement.getAttribute("data-theme") === "dark";
    const nt = dark ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", nt);
    localStorage.setItem("vai_theme", nt);
    const bt = document.getElementById("btn-theme");
    if (bt) bt.textContent = nt === "dark" ? "☀️" : "🌙";
    return nt;
  }

  // ตั้งค่าเริ่มต้นให้ปุ่มภาษา/ธีม + โหลดดิกชันนารีครั้งแรก
  async function boot() {
    initTheme();
    document.documentElement.lang = LANG;
    await load(); apply();
  }
  return { load, t, apply, setLang, toggleLang, getLang, initTheme, toggleTheme, boot };
})();


/* ─── Mobile nav toggle (hamburger) — จุดงานค้าง #1 ───
   ฉีดปุ่ม ☰ เข้า .topbar ทุกหน้า (ใช้ i18n.js ร่วมกัน) แล้วสลับ .nav-open
   ทำงานเฉพาะจอ <=768px ตาม CSS; ปิดเมนูเมื่อคลิกลิงก์/นอกเมนู/ขยายจอ */
document.addEventListener("DOMContentLoaded", function () {
  var bar = document.querySelector(".topbar");
  var nav = bar && bar.querySelector(".nav");
  if (!bar || !nav || bar.querySelector(".nav-toggle")) return;

  var btn = document.createElement("button");
  btn.className = "nav-toggle";
  btn.id = "nav-toggle";
  btn.type = "button";
  btn.setAttribute("aria-label", "เมนูนำทาง");
  btn.setAttribute("aria-expanded", "false");
  btn.innerHTML = "\u2630"; // ☰

  var lang = document.getElementById("btn-lang");
  if (lang) bar.insertBefore(btn, lang); else bar.appendChild(btn);

  function setOpen(open) {
    bar.classList.toggle("nav-open", open);
    btn.setAttribute("aria-expanded", open ? "true" : "false");
  }
  btn.addEventListener("click", function (e) {
    e.stopPropagation();
    setOpen(!bar.classList.contains("nav-open"));
  });
  nav.addEventListener("click", function (e) {
    if (e.target.tagName === "A") setOpen(false);
  });
  document.addEventListener("click", function (e) {
    if (bar.classList.contains("nav-open") && !bar.contains(e.target)) setOpen(false);
  });
  window.addEventListener("resize", function () {
    if (window.innerWidth > 768) setOpen(false);
  });
});
