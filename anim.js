/* Közös animációk (a csikoscsapat.hu mintájára): minden kattintásra visszajelzés
   (hullám + lenyomás), oldalak be-/kifakulása, megjelenő panelek beúszása. */
(function () {
  if (window.__mfAnim) return; window.__mfAnim = 1;
  var rm = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var st = document.createElement("style");
  st.textContent =
    "@keyframes mfPage{from{opacity:0}to{opacity:1}}@keyframes mfPageIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}" +
    "@keyframes mfRip{from{transform:translate(-50%,-50%) scale(0);opacity:.35}to{transform:translate(-50%,-50%) scale(1);opacity:0}}" +
    "@keyframes mfPop{0%{transform:scale(1)}40%{transform:scale(.94)}100%{transform:scale(1)}}" +
    "body{animation:mfPage .35s ease backwards}" +
    "body.mf-leave{opacity:0;transition:opacity .18s ease}" +
    "button,summary,[role=button],[role=tab],select,input[type=submit],.btn,.lchip,.chip-pop,.inv-btn,.foot__inv,.want{transition:transform .15s ease,filter .15s ease,box-shadow .2s ease,background-color .2s ease,border-color .2s ease,color .2s ease,opacity .2s ease}" +
    "button:not(:disabled):active,summary:active,[role=button]:active,[role=tab]:active,input[type=submit]:active,a.btn:active,a.inv-btn:active,a.foot__inv:active,a.want:active{transform:scale(.95)}" +
    "a{transition:color .2s ease,opacity .2s ease,background-color .2s ease}" +
    "a:active{opacity:.7}" +
    ".mf-rip{position:fixed;z-index:2147483000;width:140px;height:140px;border-radius:50%;background:currentColor;pointer-events:none;animation:mfRip .55s ease-out forwards}" +
    ".mf-pop{animation:mfPop .3s ease}" +
    "details>summary~*{animation:mfPageIn .3s ease both}" +
    "@keyframes mfIn{from{opacity:0;transform:translateY(12px) scale(.985)}to{opacity:1;transform:none}}" +
    ".mf-in{animation:mfIn .42s cubic-bezier(.22,1,.36,1) both}" +
    "dialog[open]{animation:mfIn .3s cubic-bezier(.22,1,.36,1) both}" +
    "input,select,textarea{transition:border-color .2s ease,box-shadow .2s ease,background-color .2s ease}" +
    "input:focus,select:focus,textarea:focus{box-shadow:0 0 0 3px rgba(255,205,3,.35)}" +
    "button:not(:disabled):hover,summary:hover,[role=tab]:hover,a.btn:hover,a.inv-btn:hover{filter:brightness(1.07)}" +
    "input[type=checkbox],input[type=radio]{transition:transform .15s ease}" +
    "input[type=checkbox]:active,input[type=radio]:active{transform:scale(.8)}" +
    "@media (prefers-reduced-motion:reduce){.mf-in,body,body.mf-leave,.mf-rip,.mf-pop,details>summary~*,dialog[open]{animation:none!important;transition:none!important}.mf-rip{display:none}}";
  document.head.appendChild(st);
  if (rm) return;

  // hullám a kattintás helyén
  var SEL = "button,a,summary,[role=button],[role=tab],select,.lchip";
  document.addEventListener("pointerdown", function (e) {
    var t = e.target.closest && e.target.closest(SEL); if (!t || t.disabled) return;
    var r = document.createElement("span"); r.className = "mf-rip";
    r.style.color = getComputedStyle(t).color || "#888";
    r.style.left = e.clientX + "px"; r.style.top = e.clientY + "px";
    document.body.appendChild(r); setTimeout(function () { r.remove(); }, 600);
  }, { passive: true });

  document.addEventListener("click", function (e) {
    // lenyomás-animáció a gombokon
    var t = e.target.closest && e.target.closest("button,summary,[role=tab],.lchip,input[type=checkbox],input[type=radio]");
    if (t) { t.classList.remove("mf-pop"); void t.offsetWidth; t.classList.add("mf-pop"); setTimeout(function () { t.classList.remove("mf-pop"); }, 350); }
    // oldalváltáskor kifakulás
    var a = e.target.closest && e.target.closest("a[href]");
    if (!a || e.defaultPrevented || e.metaKey || e.ctrlKey || e.shiftKey || e.button) return;
    var h = a.getAttribute("href") || "";
    if (a.target === "_blank" || a.hasAttribute("download") || /^(#|mailto:|tel:|javascript:|blob:)/.test(h) || a.origin !== location.origin) return;
    if (a.pathname === location.pathname && a.search === location.search) return;
    e.preventDefault(); document.body.classList.add("mf-leave");
    setTimeout(function () { location.href = a.href; }, 170);
  });

  // ami a felhasználó művelete után megjelenik (panel, új sor, belépés utáni oldal), beúszik
  var lastIn = 0, t0 = Date.now();
  ["pointerdown", "keydown", "change"].forEach(function (n) { document.addEventListener(n, function () { lastIn = Date.now(); }, true); });
  function animIn(el) {
    if (el.nodeType !== 1 || /^(SCRIPT|STYLE|LINK|OPTION|TR|TD|TH|LI|BR|DIALOG)$/.test(el.tagName) || /mf-/.test(el.className || "")) return;
    if (el.closest(".stage,.box3d,.fig3d")) return;   // a forgó 3D modelleket nem bántjuk
    var cs = getComputedStyle(el); if (cs.display === "none" || cs.position === "fixed" || (cs.animationName && cs.animationName !== "none")) return;
    el.classList.add("mf-in");
    setTimeout(function () { el.classList.remove("mf-in"); }, 600);
  }
  new MutationObserver(function (ms) {
    if (Date.now() - lastIn > 1500 || Date.now() - t0 < 500) return;
    var added = [];
    ms.forEach(function (m) {
      if (m.type === "attributes") { if (m.attributeName === "hidden" && !m.target.hidden) animIn(m.target); }
      else m.addedNodes.forEach(function (n) { if (n.nodeType === 1) added.push(n); });
    });
    if (added.length && added.length <= 3) added.forEach(animIn);
  }).observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ["hidden"] });
  window.addEventListener("pageshow", function (e) { if (e.persisted) document.body.classList.remove("mf-leave"); });
})();
