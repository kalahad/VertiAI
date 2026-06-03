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
