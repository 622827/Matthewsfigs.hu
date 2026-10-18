(() => {
  const EN = {
    "nav.about":"About",
    "home.setsTitle":"Featured sets","home.setsAll":"All sets","home.figsTitle":"Featured minifigures","home.figsAll":"All minifigures",
    "cat.sets.kicker":"Shop","cat.sets.title":"Sets","cat.sets.lead":"Only sealed (MISB) LEGO® sets, mostly from the Star Wars universe. Search by set number or keyword.",
    "cat.sets.ph":"Set number or keyword, e.g. 75391, Clone, Microfighter…",
    "cat.figs.kicker":"Shop","cat.figs.title":"Minifigures","cat.figs.lead":"Minifigures from the Star Wars universe and beyond. Search by name, number or keyword.",
    "cat.figs.ph":"Name, number or keyword, e.g. Rex, sw0314, 501st…",
    "cat.go":"Search","cat.popular":"Popular:","cat.results":"results","cat.for":" for","cat.ask":"Ask us on Messenger",
    "sort.pd":"Price: high to low","sort.pa":"Price: low to high","sort.na":"Name: A–Z","nav.sets":"Sets","nav.figs":"Minifigures","nav.shop":"Shop",
    "about.kicker":"About us","about.title":"Who we are",
    "about.p1":"Matthew's Fig Supply Co. is a LEGO® set and minifigure shop based in Budapest. We buy sealed sets in bulk, so we can sell them below retail. We only sell sets sealed (MISB), and every figure is checked one by one.",
    "about.p2":"If something isn't in stock, we'll source it: a rare figure, a long-retired set or a whole wanted list. We ship within Hungary and abroad, and you can pick up your order in person in Budapest.",
    "about.name":"The name? Csikós Máté translates to Matthew Horseman in English. \"Fig\" stands for minifigures, and the fig on the logo is a little pun.",
    "about.f1t":"What we sell","about.f1":"Sealed sets, minifigures, parts",
    "about.f2t":"Main theme","about.f2":"Star Wars, plus Minecraft and Castle",
    "about.f3t":"Where to buy","about.f3":"Our BrickLink store, Messenger or in person",
    "about.f4t":"Based in","about.f5t":"Languages","about.f5":"Hungarian and English","nav.sourcing":"Sourcing","nav.order":"How to order","nav.contact":"Contact",
    "hero.kicker":"LEGO® sets · minifigures · parts",
    "hero.title":"If we don't have it,<br>we can get it.",
    "hero.lead":"Bulk LEGO® sets and minifigures below retail. Looking for a rare figure or a long-retired set? Message us and we'll source it within a few weeks.",
    "hero.cta1":"Browse the shop","hero.cta2":"Message us",
    "stats.lots":"lots in stock","stats.praise":"positive feedback","stats.ship":"ships in Hungary & abroad","stats.place":"pickup in Budapest",
    "shop.title":"Shop","shop.updated":"Updated:","shop.sets":"Sets","shop.figs":"Minifigures","shop.parts":"Parts","shop.all":"All",
    "shop.search":"Search by name or number…","shop.condAll":"Any condition","shop.condNew":"New","shop.condUsed":"Used",
    "shop.empty":"Nothing found. Message us and we'll source it!","shop.more":"Show more",
    "src.title":"You dream it, we source it",
    "src.c1t":"Bulk sets","src.c1":"Sealed LEGO® sets at great prices.",
    "src.c2t":"Retired sets","src.c2":"Looking for a retired or hard-to-find set? We'll find it.",
    "src.c3t":"Rare minifigures","src.c3":"Missing a character for your collection? Just send us a message.",
    "src.c4t":"Extra services","src.c4":"Part-outs, wanted list fulfilment and valuation.",
    "ord.title":"How to order",
    "ord.s1t":"Pick","ord.s1":"Browse here or in our BrickLink store.",
    "ord.s2t":"Order","ord.s2":"Check out on BrickLink, or message us on Messenger.",
    "ord.s3t":"Receive","ord.s3":"Careful packing, shipping or pickup in Budapest.",
    "ord.bl":"BrickLink store","ord.msg":"Custom request on Messenger",
    "foot.contact":"Contact","foot.inv":"For investors","nav.inv":"Investors",
    "foot.legal":"LEGO® is a trademark of the LEGO Group, which does not sponsor, authorize or endorse this site.",
    "badge.sealed":"Sealed","price.ask":"Ask",
    "parts.title":"Parts","parts.text":"We have {lots} lots ({qty} pieces) of parts in stock. Browse them with colour filters in our BrickLink store.","parts.cta":"Browse parts on BrickLink"
  };
  const HU = {"cat.for":" erre","badge.sealed":"Bontatlan","price.ask":"Érdeklődj",
    "parts.title":"Alkatrészek","parts.text":"{lots} tétel ({qty} darab) alkatrész van raktáron. Színre és típusra szűrve a BrickLink boltunkban böngészheted őket.","parts.cta":"Alkatrészek a BrickLinken"};

  let lang = "hu";
  try { lang = localStorage.getItem("mfs-lang") || (navigator.language.startsWith("hu") ? "hu" : "en"); } catch (e) {}
  const t = k => (lang === "en" ? EN[k] : HU[k]) ?? k;
  const $ = id => document.getElementById(id);
  const PAGE_KIND = document.body.dataset.page;      // "home" | "catalog"
  const TYPE = document.body.dataset.type;           // SET | MINIFIG on catalog pages

  // Remember the Hungarian originals from the markup
  document.querySelectorAll("[data-i18n]").forEach(el => { HU[el.dataset.i18n] = el.innerHTML; });
  document.querySelectorAll("[data-i18n-ph]").forEach(el => { HU[el.dataset.i18nPh] = el.placeholder; });

  function applyLang() {
    document.documentElement.lang = lang;
    document.querySelectorAll("[data-i18n]").forEach(el => { el.innerHTML = t(el.dataset.i18n); });
    document.querySelectorAll("[data-i18n-ph]").forEach(el => { el.placeholder = t(el.dataset.i18nPh); });
    $("langBtn").textContent = lang === "hu" ? "EN" : "HU";
    renderAll(true);
  }
  $("langBtn").onclick = () => {
    lang = lang === "hu" ? "en" : "hu";
    try { localStorage.setItem("mfs-lang", lang); } catch (e) {}
    applyLang();
  };

  // ---------- helpers ----------
  let data = { items: [] };
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;" }[c]));
  const money = v => {
    if (v == null || v === "") return t("price.ask");
    const cur = data.currency || "EUR";
    return new Intl.NumberFormat(lang === "hu" ? "hu-HU" : "en-GB", {
      style: "currency", currency: cur, maximumFractionDigits: cur === "HUF" ? 0 : 2
    }).format(v);
  };
  // 3D product box: sets get their original LEGO box art on a cuboid,
  // minifigures turn like on a display turntable.
  let BOXES = {};   // assets/boxes/index.json: flattened faces cut from the box photos
  const box3d = i => {
    const m = i.type === "SET" ? BOXES[i.no] : null;
    if (!m) return `<div class="stage"><div class="box3d flat still"><img class="f front" loading="lazy" alt="" src="${esc(i.img)}"><i class="f back" style="--art:url('${esc(i.img)}')"></i></div></div>`;
    const W = 134, H = 118;
    let w = W, h = W * m.h; if (h > H) { h = H; w = H / m.h; }
    const d = w * m.d, base = `assets/boxes/${encodeURIComponent(i.no)}`;
    return `<div class="stage"><div class="box3d side-${m.side}" data-side="${m.side}" style="--w:${w.toFixed(1)}px;--h:${h.toFixed(1)}px;--d:${d.toFixed(1)}px;--front:url('${base}-front.jpg');--side:url('${base}-side.jpg');--top:url('${base}-top.jpg')">
      <img class="f front" loading="lazy" alt="" src="${base}-front.jpg">
      <i class="f back"></i><i class="f l"></i><i class="f r"></i><i class="f t"></i><i class="f bt"></i>
    </div></div>`;
  };

  // All boxes turn in step: their angle comes from one shared clock.
  const SPIN_MS = 9000;
  const reduced = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  const now = () => document.timeline ? document.timeline.currentTime : performance.now();
  const angleAt = t => ((t % SPIN_MS) / SPIN_MS) * 360;
  const sync = a => { a.play(); a.startTime = 0; };               // jump back onto the shared clock
  const io = "IntersectionObserver" in window ? new IntersectionObserver(es => es.forEach(e => {
    const a = e.target._spin; if (!a || e.target._hold) return;
    e.isIntersecting ? sync(a) : a.pause();
  }), { rootMargin: "100px" }) : null;
  const rot = (deg, tilt = -12) => `rotateX(${tilt}deg) rotateY(${deg}deg)`;
  const poseOf = box => (box.dataset.side === "right" ? -32 : 32);
  const near = (from, to) => from + ((((to - from) % 360) + 540) % 360 - 180);   // shortest way round

  function initBoxes(root) {
    root.querySelectorAll(".box3d:not([data-ready])").forEach(box => {
      box.dataset.ready = "1";
      const img = box.querySelector(".front");
      img.addEventListener("error", () => box.classList.add("noimg"));
      if (box.classList.contains("still")) return;                // poly / paper bags: plain picture
      const pose = poseOf(box);
      if (reduced || !box.animate) { box.style.transform = rot(pose, -15); return; }

      const spin = box.animate([{ transform: rot(0) }, { transform: rot(360) }], { duration: SPIN_MS, iterations: Infinity });
      spin.startTime = 0;
      box._spin = spin;
      if (io) io.observe(box);

      const card = box.closest(".item");
      let hov = null;
      const hold = () => {                                       // stop and turn to the angled pose
        if (box._hold) return;
        box._hold = true;
        const from = angleAt(spin.currentTime);
        spin.pause();
        if (hov) hov.cancel();
        hov = box.animate([{ transform: rot(from) }, { transform: rot(near(from, pose), -15) }],
                          { duration: 650, easing: "cubic-bezier(.2,.8,.2,1)", fill: "forwards" });
      };
      const release = () => {                                    // glide back into step with the others
        if (!box._hold) return;
        box._hold = false;
        const T = 700, start = near(pose, pose);
        const to = angleAt(now() + T);
        const end = start + ((((to - start) % 360) + 360) % 360);  // keep turning forwards
        if (hov) hov.cancel();
        hov = box.animate([{ transform: rot(pose, -15) }, { transform: rot(end) }], { duration: T, easing: "ease-in-out", fill: "forwards" });
        hov.onfinish = () => { hov.cancel(); hov = null; sync(spin); };
      };
      card.addEventListener("pointerenter", e => { if (e.pointerType === "mouse") hold(); });
      card.addEventListener("pointerleave", e => { if (e.pointerType === "mouse") release(); });
      // phones: first tap stops the box, a second tap opens the product
      card.addEventListener("click", e => {
        if (matchMedia("(hover: hover)").matches) return;
        if (!box._hold) {
          e.preventDefault();
          document.querySelectorAll(".box3d").forEach(b => b !== box && b._release && b._release());
          hold();
        }
      });
      box._release = release;
    });
  }
  document.addEventListener("click", e => {
    if (!e.target.closest(".item")) document.querySelectorAll(".box3d").forEach(b => b._release && b._release());
  });

  const card = i => `
      <a class="item" href="${esc(i.url)}" target="_blank" rel="noopener">
        <div class="item__img">${box3d(i)}</div>
        <div class="item__body">
          <span class="item__no">${esc(i.no)}${i.qty > 1 ? ` · ${i.qty} ${lang === "hu" ? "db" : "pcs"}` : ""}</span>
          <span class="item__name">${esc(i.name)}</span>
          <div class="item__foot">
            <span class="price">${i.from ? `<small>${lang === "hu" ? "" : "from "}</small>` : ""}${money(i.price)}${i.from && lang === "hu" ? "<small>-tól</small>" : ""}</span>
            ${i.type === "SET" ? `<span class="badge">${t("badge.sealed")}</span>` : ""}
          </div>
        </div>
      </a>`;

  // ---------- search ----------
  const norm = s => String(s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  // Keyword shortcuts: one word stands for several names
  const ALIAS = {
    jedi: "jedi|obi-wan|kenobi|ahsoka|anakin|luke|ki-adi|plo koon|shaak|aayla|even piell|coleman|nahdar|barriss|yoda",
    sith: "sith|darth|vader|maul|palpatine|emperor|savage|malak|dooku",
    mando: "mandalorian|fett|din djarin|cobb vanth|sabine|super commando|death watch",
    droid: "droid|r2-d2|r4-|r7-|c-3po|k-2so|astromech|ev-a4",
    minecraft: "steve|alex|creeper|zombie|skeleton, minecraft|illager|blaze|wither|pigman|minecraft",
    birodalmi: "imperial|stormtrooper|snowtrooper|sandtrooper|tie|at-at", imperial: "imperial|stormtrooper|snowtrooper|sandtrooper|tie",
    lazado: "rebel|hoth|endor|luke|leia|chewbacca|han solo", rebel: "rebel|hoth|endor|leia|chewbacca",
    klon: "clone", tasak: "bag|foil|polybag", polybag: "bag|foil|polybag"
  };
  function matcher(query) {
    const q = norm(query).trim();
    if (!q) return () => true;
    // whole phrase alias first (e.g. "battle pack" stays a phrase via the OR syntax)
    const tokens = q.includes("|") ? [q] : q.split(/\s+/);
    const groups = tokens.map(tok => (ALIAS[tok] || tok).split("|").map(x => x.trim()).filter(Boolean));
    return i => {
      const hay = norm(`${i.no} ${i.no.replace(/-1$/, "")} ${i.name}`);
      return groups.every(g => g.some(w => hay.includes(w)));
    };
  }

  // ---------- home page ----------
  function renderHome() {
    document.querySelectorAll("[data-shelf]").forEach(g => {
      const list = data.items.filter(i => i.type === g.dataset.shelf).slice(0, 8);
      g.innerHTML = list.map(card).join("");
      initBoxes(g);
    });
    document.querySelectorAll("[data-count]").forEach(el => {
      el.textContent = data.items.filter(i => i.type === el.dataset.count).length || el.textContent;
    });
    const p = $("partsPanel");
    if (p) {
      const qty = (data.parts_qty || 0).toLocaleString(lang === "hu" ? "hu-HU" : "en-GB");
      p.innerHTML = `<h3>${t("parts.title")}</h3>
        <p>${t("parts.text").replace("{lots}", data.parts_lots || 0).replace("{qty}", qty)}</p>
        <a class="btn btn--gold" href="https://store.bricklink.com/MatthewHorseman#/shop?o={%22itemType%22:%22P%22}" target="_blank" rel="noopener">${t("parts.cta")}</a>`;
    }
  }

  // ---------- catalog pages ----------
  const PAGE = 24;
  let shown = PAGE;
  function renderCatalog(reset) {
    if (reset) shown = PAGE;
    const qv = $("search").value;
    const match = matcher(qv), sort = $("sort").value;
    let list = data.items.filter(i => i.type === TYPE && match(i));
    list.sort(sort === "pa" ? (a, b) => a.price - b.price : sort === "na" ? (a, b) => a.name.localeCompare(b.name) : (a, b) => b.price - a.price);
    $("grid").innerHTML = list.slice(0, shown).map(card).join("");
    initBoxes($("grid"));
    $("count").textContent = list.length;
    $("qlabel").textContent = qv.trim() && !qv.includes("|") ? `${t("cat.for")}: „${qv.trim()}”` : "";
    $("empty").hidden = list.length > 0;
    $("moreBtn").parentElement.hidden = list.length <= shown;
    document.querySelectorAll(".chip").forEach(c => c.classList.toggle("is-on", norm(c.dataset.q) === norm(qv)));
  }
  function syncUrl() {
    const q = $("search").value.trim();
    const u = new URL(location.href);
    q ? u.searchParams.set("q", q) : u.searchParams.delete("q");
    history.replaceState(null, "", u);
  }
  if (PAGE_KIND === "catalog") {
    $("search").value = new URLSearchParams(location.search).get("q") || "";
    let timer;
    $("search").addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => { renderCatalog(true); syncUrl(); }, 120); });
    $("searchForm").addEventListener("submit", e => { e.preventDefault(); renderCatalog(true); syncUrl(); $("search").blur(); });
    $("sort").onchange = () => renderCatalog(true);
    $("moreBtn").onclick = () => { shown += PAGE; renderCatalog(); };
    document.querySelectorAll(".chip").forEach(c => c.onclick = () => {
      $("search").value = c.classList.contains("is-on") ? "" : c.dataset.q;
      renderCatalog(true); syncUrl();
    });
  }

  function renderAll(reset) {
    if (!data.items.length) return;
    PAGE_KIND === "catalog" ? renderCatalog(reset) : renderHome();
  }

  Promise.all([
    fetch("data/inventory.json", { cache: "no-cache" }).then(r => r.json()),
    fetch("assets/boxes/index.json", { cache: "no-cache" }).then(r => r.ok ? r.json() : {}).catch(() => ({}))
  ])
    .then(([d, boxes]) => {
      BOXES = boxes || {};
      const byItem = new Map();
      for (const i of d.items) {
        const k = i.type + ":" + i.no, m = byItem.get(k);
        if (!m) { byItem.set(k, { ...i }); continue; }
        m.qty += i.qty;
        if (i.price !== m.price) m.from = true;
        if (i.price < m.price) { m.price = i.price; m.url = i.url; }
      }
      d.items = [...byItem.values()];
      data = d;
      const lots = $("statLots"); if (lots && d.total_lots) lots.textContent = d.total_lots;
      if (d.updated && $("updated")) $("updated").textContent =
        new Date(d.updated).toLocaleString(lang === "hu" ? "hu-HU" : "en-GB", { dateStyle: "medium", timeStyle: "short" });
      renderAll(true);
    })
    .catch(() => { const e = $("empty"); if (e) e.hidden = false; });

  applyLang();
})();
